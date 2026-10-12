import { tool } from "./define"
import { exec, tryGit } from "./exec"

/**
 * Pull-request metadata — labels, assignees, review requests, a milestone —
 * applied without asking when nothing reacts to it, and only after approval
 * otherwise. A tool's permission is decided once per call, so the split is two
 * tools: `gh_pr_meta` (allow) applies the harmless changes and returns the rest
 * with a token; `gh_pr_meta_apply` (ask) applies those once the token still
 * matches what was judged.
 *
 * A change is harmless when no workflow runs on its activity type, no
 * label-driven merge bot is configured (labels only), no repository webhook
 * takes pull_request events, no ruleset mandates a workflow from elsewhere,
 * and it notifies nobody else. `pull_request` workflows come from the merge
 * ref, judged as the union of the PR head's and its base's workflows;
 * `pull_request_target` ones from the default branch. Every tree is read at a
 * commit, and the commits are checked again right before anything is applied.
 * Anything unreadable or unparsable counts as not harmless. GitHub Apps that
 * subscribe without a repository webhook, and organization webhooks, are not
 * visible here.
 *
 * Labels, milestones, assignees and reviewers must already exist: nothing is
 * created. Never closes, merges or comments.
 */

const NON_INTERACTIVE = { GH_PROMPT_DISABLED: "1", GH_NO_UPDATE_NOTIFIER: "1", NO_COLOR: "1" }
const gh = (argv: string[], cwd: string) => exec(["gh", ...argv], { cwd, env: { ...process.env, ...NON_INTERACTIVE } })
const tail = (text: string, n = 20) => text.trim().split("\n").slice(-n).join("\n")
const out = (res: { stdout: string; stderr: string }) => tail(`${res.stdout}\n${res.stderr}`)
const sha1 = (value: unknown) => new Bun.CryptoHasher("sha1").update(JSON.stringify(value)).digest("hex").slice(0, 12)

async function ghJson(argv: string[], cwd: string): Promise<any> {
  const res = await gh(argv, cwd)
  if (!res.ok) return undefined
  try {
    return res.stdout.trim() ? JSON.parse(res.stdout) : null
  } catch {
    return undefined
  }
}

/** Every page of a REST list, flattened; undefined when any page is unreadable. */
async function ghPages(path: string, cwd: string): Promise<any[] | undefined> {
  const pages = await ghJson(["api", "--paginate", "--slurp", path], cwd)
  return Array.isArray(pages) ? pages.flatMap((p: any) => (Array.isArray(p) ? p : [])) : undefined
}

/** A REST read: its body, `absent` for a 404, or `unreadable` for anything else. */
async function ghRead(path: string, cwd: string, raw = false): Promise<{ body: string } | "absent" | "unreadable"> {
  const res = await gh(["api", ...(raw ? ["-H", "Accept: application/vnd.github.raw+json"] : []), path], cwd)
  if (res.ok) return { body: res.stdout }
  return /HTTP 404|Not Found/i.test(`${res.stdout}\n${res.stderr}`) ? "absent" : "unreadable"
}

const enc = (path: string) => path.split("/").map(encodeURIComponent).join("/")

/** The commit a branch of the repository points at, or null when unreadable. */
async function branchSha(repo: string, branch: string, cwd: string): Promise<string | null> {
  const res = await gh(["api", `repos/${repo}/commits/${enc(branch)}`, "--jq", ".sha"], cwd)
  const sha = res.ok ? res.stdout.trim() : ""
  return /^[0-9a-f]{40}$/.test(sha) ? sha : null
}

// ------------------------------------------------------------- requests --

export type MetaRequest = {
  labels?: { add?: string[]; remove?: string[] }
  assignees?: { add?: string[]; remove?: string[] }
  reviewers?: { add?: string[]; remove?: string[] }
  milestone?: string
  removeMilestone?: boolean
}

export const metaArgs = {
  labels: tool.schema
    .object({ add: tool.schema.array(tool.schema.string()).optional(), remove: tool.schema.array(tool.schema.string()).optional() })
    .optional()
    .describe("Labels to add or remove; they must already exist in the repository."),
  assignees: tool.schema
    .object({ add: tool.schema.array(tool.schema.string()).optional(), remove: tool.schema.array(tool.schema.string()).optional() })
    .optional()
    .describe('Logins to assign or unassign; "@me" is you.'),
  reviewers: tool.schema
    .object({ add: tool.schema.array(tool.schema.string()).optional(), remove: tool.schema.array(tool.schema.string()).optional() })
    .optional()
    .describe('Users, "org/team" or "@copilot" to request or un-request a review from. Only when the user asked: it notifies them.'),
  milestone: tool.schema.string().optional().describe("Milestone title to set; it must exist and be open."),
  removeMilestone: tool.schema.boolean().optional().describe("Clear the milestone."),
  infer: tool.schema
    .boolean()
    .optional()
    .describe("Also add what your merged PRs here habitually carry: yourself as assignee, and labels on at least 60% of them (or of PRs of the same type)."),
}

type Kind = "label" | "assignee" | "reviewer" | "milestone"
export type Change = { kind: Kind; op: "add" | "remove"; value: string; source: "request" | "habit" }
export type Judged = Change & { status: "harmless" | "approval" | "invalid" | "unchanged"; reasons: string[] }

const ACTIVITY: Record<Kind, Record<"add" | "remove", string>> = {
  label: { add: "labeled", remove: "unlabeled" },
  assignee: { add: "assigned", remove: "unassigned" },
  reviewer: { add: "review_requested", remove: "review_request_removed" },
  milestone: { add: "milestoned", remove: "demilestoned" },
}

function changesOf(req: MetaRequest): Change[] {
  const list: Change[] = []
  const push = (kind: Kind, op: "add" | "remove", values?: string[]) => {
    for (const v of values ?? []) if (v.trim()) list.push({ kind, op, value: v.trim(), source: "request" })
  }
  push("label", "add", req.labels?.add)
  push("label", "remove", req.labels?.remove)
  push("assignee", "add", req.assignees?.add)
  push("assignee", "remove", req.assignees?.remove)
  push("reviewer", "add", req.reviewers?.add)
  push("reviewer", "remove", req.reviewers?.remove)
  if (req.milestone?.trim()) list.push({ kind: "milestone", op: "add", value: req.milestone.trim(), source: "request" })
  if (req.removeMilestone) list.push({ kind: "milestone", op: "remove", value: "", source: "request" })
  for (const c of list) {
    if (c.value.startsWith("-")) throw new Error(`\`${c.value}\` is not a ${c.kind}.`)
    // gh splits these flags' values on commas, which would apply something never judged.
    if (c.kind !== "milestone" && c.value.includes(",")) throw new Error(`\`${c.value}\`: a ${c.kind} with a comma cannot be set here; gh would split it.`)
  }
  return list
}

// ------------------------------------------------------------ automation --

type Trigger = { event: "pull_request" | "pull_request_target"; types: string[] }
type Workflow = {
  path: string
  digest: string
  triggers: Trigger[]
  workflowRun: boolean
  /** Workflow-level concurrency: even a run whose jobs all skip can cancel another. */
  concurrency: boolean
  jobLabels: (string[] | null)[]
  error?: string
}
type Workflows = Workflow[] | "unreadable"

const DEFAULT_TYPES = ["opened", "synchronize", "reopened"]
const LABEL_IS = /^\(?\s*(?:github\.event\.label\.name\s*==\s*(['"])([^'"]+)\1|(['"])([^'"]+)\3\s*==\s*github\.event\.label\.name)\s*\)?$/

/** The label names a job's `if` is limited to, when it says only "the label added or removed is X (or Y)". */
export function labelOnly(condition: unknown): string[] | null {
  if (typeof condition !== "string") return null
  const body = condition.trim().replace(/^\$\{\{\s*/, "").replace(/\s*\}\}$/, "")
  const names: string[] = []
  for (const part of body.split("||")) {
    const m = part.trim().match(LABEL_IS)
    if (!m) return null
    names.push(m[2] ?? m[4])
  }
  return names.length ? names : null
}

export function parseWorkflow(path: string, text: string): Workflow {
  const digest = new Bun.CryptoHasher("sha1").update(text).digest("hex")
  const broken = (error: string): Workflow => ({ path, digest, triggers: [], workflowRun: false, concurrency: false, jobLabels: [], error })
  let doc: any
  try {
    doc = Bun.YAML.parse(text)
  } catch {
    return broken("unparsable YAML")
  }
  // YAML 1.1 readers turn `on` into true; accept either.
  const on = doc?.on ?? doc?.true
  if (on == null) return broken("no `on` trigger")
  let events: Record<string, any>
  if (typeof on === "string") events = { [on]: null }
  else if (Array.isArray(on)) {
    if (!on.every((e) => typeof e === "string")) return broken("an `on` list this reader does not understand")
    events = Object.fromEntries(on.map((e: string) => [e, null]))
  } else if (typeof on === "object") events = on
  else return broken("an `on` value this reader does not understand")
  const triggers: Trigger[] = []
  for (const event of ["pull_request", "pull_request_target"] as const) {
    if (!(event in events)) continue
    const types = events[event]?.types
    triggers.push({ event, types: types == null ? DEFAULT_TYPES : (Array.isArray(types) ? types : [types]).map(String) })
  }
  const jobs = doc?.jobs && typeof doc.jobs === "object" ? Object.values(doc.jobs) : []
  return {
    path,
    digest,
    triggers,
    workflowRun: "workflow_run" in events,
    concurrency: doc?.concurrency != null,
    jobLabels: jobs.map((j: any) => labelOnly(j?.if)),
  }
}

/**
 * Whether the workflow runs for this activity (and, for label activities,
 * this label). A run whose every job is limited to other labels still counts
 * when `chained` is set: its completion can start a workflow_run workflow.
 */
export function reacts(wf: Workflow, event: Trigger["event"], activity: string, label?: string, chained = false): boolean {
  const trigger = wf.triggers.find((t) => t.event === event)
  if (!trigger || !trigger.types.includes(activity)) return false
  if (chained || wf.concurrency || !wf.jobLabels.length || wf.jobLabels.some((names) => names === null)) return true
  // Every job is limited to named labels (compared as Actions does, ignoring case).
  const want = label?.toLowerCase()
  return (activity === "labeled" || activity === "unlabeled") && want !== undefined && wf.jobLabels.some((names) => names!.some((n) => n.toLowerCase() === want))
}

const WORKFLOW_FILE = /^\.github\/workflows\/[^/]+\.ya?ml$/

async function workflowsAtRemote(repo: string, ref: string, cwd: string): Promise<Workflows> {
  const dir = await ghRead(`repos/${repo}/contents/.github/workflows?ref=${encodeURIComponent(ref)}`, cwd)
  if (dir === "absent") return []
  if (dir === "unreadable") return "unreadable"
  let entries: any[]
  try {
    entries = JSON.parse(dir.body)
  } catch {
    return "unreadable"
  }
  const list: Workflow[] = []
  for (const e of Array.isArray(entries) ? entries : []) {
    if (e?.type !== "file" || !WORKFLOW_FILE.test(e.path)) continue
    const file = await ghRead(`repos/${repo}/contents/${enc(e.path)}?ref=${encodeURIComponent(ref)}`, cwd, true)
    if (typeof file === "string") return "unreadable"
    list.push(parseWorkflow(e.path, file.body))
  }
  return list
}

async function workflowsAtLocal(sha: string, cwd: string): Promise<Workflows | null> {
  if (!(await tryGit(["cat-file", "-e", `${sha}^{commit}`], cwd)).ok) return null
  const names = (await tryGit(["ls-tree", "-r", "--name-only", sha, "--", ".github/workflows"], cwd)).stdout.split("\n").filter((p) => WORKFLOW_FILE.test(p))
  const list: Workflow[] = []
  for (const path of names) {
    const res = await tryGit(["show", `${sha}:${path}`], cwd)
    if (!res.ok) return "unreadable"
    list.push(parseWorkflow(path, res.stdout))
  }
  return list
}

const workflowsAt = async (repo: string, sha: string | null, cwd: string): Promise<Workflows> =>
  sha ? ((await workflowsAtLocal(sha, cwd)) ?? (await workflowsAtRemote(repo, sha, cwd))) : "unreadable"

const BOT_FILES = [
  ".mergify.yml",
  ".mergify.yaml",
  ".mergify/config.yml",
  ".mergify/config.yaml",
  ".github/mergify.yml",
  ".github/mergify.yaml",
  ".kodiak.toml",
  ".github/.kodiak.toml",
  ".bulldozer.yml",
]
const ORG_BOT_FILES = [".kodiak.toml", "bulldozer.yml"]

export type Environment = {
  defaultBranch: string
  /** Every branch's commit the judgment read, checked again before applying. */
  shas: Record<string, string | null>
  workflowsDefault: Workflows
  /** pull_request workflows of each base branch, by branch. */
  workflowsBase: Record<string, Workflows>
  /** A default-branch workflow_run workflow can chain off any run. */
  chained: boolean
  bots: string[] | "unreadable"
  hooks: string[] | "unreadable"
  mandated: string[] | "unreadable"
}

/**
 * What in the repository could react to metadata changes, read once per call
 * at fixed commits. A base given with a commit (a stack layer about to be
 * pushed) is read at that commit; every other branch at its GitHub commit.
 */
export async function environment(repo: string, defaultBranch: string, bases: { name: string; sha?: string }[], cwd: string): Promise<Environment> {
  const shas: Record<string, string | null> = {}
  const pinned = new Map(bases.filter((b) => b.sha).map((b) => [b.name, b.sha!]))
  for (const b of new Set([defaultBranch, ...bases.map((x) => x.name)])) if (!pinned.has(b)) shas[b] = await branchSha(repo, b, cwd)
  const workflowsDefault = await workflowsAt(repo, shas[defaultBranch], cwd)
  const workflowsBase: Record<string, Workflows> = {}
  for (const b of new Set(bases.map((x) => x.name)))
    workflowsBase[b] = pinned.has(b) ? await workflowsAt(repo, pinned.get(b)!, cwd) : b === defaultBranch ? workflowsDefault : await workflowsAt(repo, shas[b], cwd)
  const chained = workflowsDefault === "unreadable" || workflowsDefault.some((w) => w.workflowRun || !!w.error)

  let bots: string[] | "unreadable" = []
  const at = shas[defaultBranch]
  if (!at) bots = "unreadable"
  else
    for (const path of BOT_FILES) {
      const r = await ghRead(`repos/${repo}/contents/${enc(path)}?ref=${at}`, cwd)
      if (r === "unreadable") {
        bots = "unreadable"
        break
      }
      if (r !== "absent") bots.push(path)
    }
  if (bots !== "unreadable") {
    const owner = repo.split("/")[0]
    for (const path of ORG_BOT_FILES) {
      // The organization's .github repository may hold a shared bot config; unreadable there means no access, not a config.
      const r = await ghRead(`repos/${owner}/.github/contents/${enc(path)}`, cwd)
      if (typeof r !== "string") bots.push(`${owner}/.github/${path}`)
    }
  }

  // Webhooks and rules change without a commit: their readings are fingerprinted
  // with the branch commits and read again right before anything is applied.
  const hooks = await hooksNow(repo, cwd)
  shas[`${SIGNAL}hooks`] = sha1(hooks)
  let mandated: string[] | "unreadable" = []
  for (const base of new Set(bases.map((b) => b.name))) {
    const rules = await rulesNow(repo, base, cwd)
    shas[`${SIGNAL}rules:${base}`] = sha1(rules)
    if (rules === "unreadable") mandated = "unreadable"
    else if (mandated !== "unreadable") mandated.push(...rules)
  }

  return { defaultBranch, shas, workflowsDefault, workflowsBase, chained, bots, hooks, mandated }
}

const SIGNAL = "@"

/** Repository webhooks that take pull_request events. */
async function hooksNow(repo: string, cwd: string): Promise<string[] | "unreadable"> {
  const list = await ghPages(`repos/${repo}/hooks?per_page=100`, cwd)
  if (!list) return "unreadable"
  return list
    .filter((h: any) => h?.active !== false && (h?.events ?? []).some((e: string) => e === "pull_request" || e === "*"))
    .map((h: any) => {
      let host = "no url"
      try {
        host = new URL(String(h.config?.url)).host
      } catch {}
      return `hook ${h.id} (${host})`
    })
}

/** Rulesets on a branch that mandate workflows from elsewhere. */
async function rulesNow(repo: string, base: string, cwd: string): Promise<string[] | "unreadable"> {
  const rules = await ghPages(`repos/${repo}/rules/branches/${enc(base)}?per_page=100`, cwd)
  if (!rules) return "unreadable"
  return rules.filter((r: any) => r?.type === "workflows").map(() => `ruleset workflows on ${base}`)
}

/**
 * Whether everything the judgment read is as it was: every branch at the same
 * commit, and the webhooks and branch rules reading the same.
 */
export async function environmentUnchanged(repo: string, shas: Record<string, string | null>, cwd: string): Promise<boolean> {
  for (const [key, was] of Object.entries(shas)) {
    if (key === `${SIGNAL}hooks`) {
      if (sha1(await hooksNow(repo, cwd)) !== was) return false
    } else if (key.startsWith(`${SIGNAL}rules:`)) {
      if (sha1(await rulesNow(repo, key.slice(`${SIGNAL}rules:`.length), cwd)) !== was) return false
    } else if (!was || (await branchSha(repo, key, cwd)) !== was) return false
  }
  return true
}

// --------------------------------------------------------------- targets --

export type Target = {
  /** "#12" for a PR, the branch name before its PR exists. */
  id: string
  number: number | null
  headSha: string
  base: string
  /** null before the PR exists: then it will be the viewer. */
  author: string | null
  labels: string[]
  assignees: string[]
  reviewers: string[]
  milestone: string | null
  /** A PR title or commit subject whose `type:` picks type-specific label habits. */
  typeHint?: string | null
  /** The base's commit when it is known locally and not yet on GitHub (a lower stack layer). */
  baseSha?: string
}

type RepoFacts = {
  labels: string[] | null
  milestones: string[] | null
  assignable: Map<string, boolean>
  reviewable: Map<string, boolean>
}

async function checkLogin(repo: string, kind: "assignees" | "collaborators", login: string, cwd: string): Promise<boolean> {
  const r = await ghRead(`repos/${repo}/${kind}/${encodeURIComponent(login)}`, cwd)
  return typeof r !== "string"
}

const same = (a: string, b: string) => a.toLowerCase() === b.toLowerCase()
const find = (list: string[], v: string) => list.find((x) => same(x, v))

/** Judge each change for one target: invalid, unchanged, harmless, or needing approval (with why). */
async function judge(
  repo: string,
  viewer: string,
  target: Target,
  changes: Change[],
  env: Environment,
  workflowsHead: Workflows,
  facts: RepoFacts,
  cwd: string,
): Promise<Judged[]> {
  const result: Judged[] = []
  for (const c of changes) {
    let value = c.kind === "assignee" && c.value === "@me" ? viewer : c.value
    const invalid = (why: string) => result.push({ ...c, value, status: "invalid", reasons: [why] })
    const unchanged = (why: string) => result.push({ ...c, value, status: "unchanged", reasons: [why] })
    // Inferred values too: gh splits these flags' values on commas.
    if (c.kind !== "milestone" && value.includes(",")) {
      invalid(`a ${c.kind} with a comma cannot be set here; gh would split it`)
      continue
    }

    if (c.kind === "label") {
      if (facts.labels === null) {
        invalid("could not read the repository's labels")
        continue
      }
      const canonical = find(facts.labels, value)
      if (c.op === "add" && !canonical) {
        invalid(`no label "${value}" in ${repo}; labels are not created here`)
        continue
      }
      value = canonical ?? value
      if (c.op === "add" ? find(target.labels, value) : !find(target.labels, value)) {
        unchanged(c.op === "add" ? "already labeled" : "not labeled")
        continue
      }
    } else if (c.kind === "assignee") {
      if (c.op === "add" ? find(target.assignees, value) : !find(target.assignees, value)) {
        unchanged(c.op === "add" ? "already assigned" : "not assigned")
        continue
      }
      if (c.op === "add") {
        const key = value.toLowerCase()
        if (!facts.assignable.has(key)) facts.assignable.set(key, value === "@copilot" || (await checkLogin(repo, "assignees", value, cwd)))
        if (!facts.assignable.get(key)) {
          invalid(`${value} cannot be assigned in ${repo}`)
          continue
        }
      }
    } else if (c.kind === "reviewer") {
      // A PR not opened yet will be yours.
      if (same(value, target.author ?? viewer)) {
        invalid("the PR's author cannot review it")
        continue
      }
      if (c.op === "add" ? find(target.reviewers, value) : !find(target.reviewers, value)) {
        unchanged(c.op === "add" ? "review already requested" : "no review request")
        continue
      }
      if (c.op === "add" && value !== "@copilot") {
        const key = value.toLowerCase()
        if (!facts.reviewable.has(key)) {
          const [org, team] = value.split("/")
          const ok = team
            ? typeof (await ghRead(`orgs/${encodeURIComponent(org)}/teams/${encodeURIComponent(team)}`, cwd)) !== "string"
            : await checkLogin(repo, "collaborators", value, cwd)
          facts.reviewable.set(key, ok)
        }
        if (!facts.reviewable.get(key)) {
          invalid(`${value} cannot review in ${repo}`)
          continue
        }
      }
    } else {
      if (c.op === "add") {
        if (facts.milestones === null) {
          invalid("could not read the repository's milestones")
          continue
        }
        const canonical = find(facts.milestones, value)
        if (!canonical) {
          invalid(`no open milestone "${value}" in ${repo}; milestones are not created here`)
          continue
        }
        value = canonical
        if (target.milestone === value) {
          unchanged("milestone already set")
          continue
        }
      } else if (!target.milestone) {
        unchanged("no milestone")
        continue
      }
    }

    const reasons: string[] = []
    const activities = [ACTIVITY[c.kind][c.op]]
    if (c.kind === "milestone" && c.op === "add" && target.milestone) activities.push("demilestoned")
    // Anyone but you: a review request always notifies, and @copilot spends AI credits.
    if (value === "@copilot") reasons.push(c.kind === "reviewer" ? "requests a Copilot review, which uses AI credits" : "assigns Copilot, which uses AI credits")
    else if (c.kind === "reviewer" || (c.kind === "assignee" && !same(value, viewer))) reasons.push(`notifies ${value}`)
    const label = c.kind === "label" ? value : undefined
    const baseWorkflows = env.workflowsBase[target.base] ?? "unreadable"
    // Git may merge two versions of one workflow into a third neither describes.
    if (workflowsHead !== "unreadable" && baseWorkflows !== "unreadable")
      for (const h of workflowsHead) {
        const b = baseWorkflows.find((x) => x.path === h.path)
        if (b && b.digest !== h.digest) reasons.push(`${h.path} differs between the PR's head and ${target.base}; the merged version may run`)
      }
    for (const activity of activities) {
      // pull_request runs the merge ref's workflows: those of the head and of the base, together.
      for (const [event, wfs, where] of [
        ["pull_request", workflowsHead, "the PR's head"],
        ["pull_request", baseWorkflows, target.base],
        ["pull_request_target", env.workflowsDefault, env.defaultBranch],
      ] as const) {
        if (wfs === "unreadable") {
          reasons.push(`could not read the workflows on ${where}`)
          continue
        }
        for (const wf of wfs) {
          if (wf.error) reasons.push(`${wf.path} (${where}): ${wf.error}, so it may run`)
          else if (reacts(wf, event, activity, label, env.chained))
            reasons.push(`${wf.path} (${where}) runs on ${event} ${activity}${env.chained ? " (a workflow_run workflow may chain off it)" : ""}`)
        }
      }
    }
    if (c.kind === "label") {
      if (env.bots === "unreadable") reasons.push("could not check for label-driven merge bots")
      else for (const b of env.bots) reasons.push(`merge bot config ${b} may act on labels`)
    }
    if (env.hooks === "unreadable") reasons.push("could not read the repository's webhooks (admin access is needed)")
    else for (const h of env.hooks) reasons.push(`${h} receives pull_request events`)
    if (env.mandated === "unreadable") reasons.push("could not read the branch rules")
    else for (const m of env.mandated) reasons.push(`${m} may run workflows from another repository`)

    result.push({ ...c, value, status: reasons.length ? "approval" : "harmless", reasons: [...new Set(reasons)] })
  }
  return result
}

// ----------------------------------------------------------------- habits --

const TYPE = /^(\w+)(?:\([^)]*\))?!?:/

export type Habits = {
  sample: number
  selfAssigned: number
  labels: { name: string; count: number; of: number; scope: string }[]
  suggestions: { milestone?: { title: string; count: number; of: number } }
}

/** What your recently merged PRs carry, for a PR of this `type:` (if any). */
function habitsOf(list: any[], viewer: string, typeHint: string | null): Habits & { changes: Change[] } {
  const n = list.length
  const changes: Change[] = []
  const selfAssigned = list.filter((p: any) => (p.assignees ?? []).some((a: any) => same(String(a.login), viewer))).length
  if (n >= 5 && selfAssigned / n >= 0.6) changes.push({ kind: "assignee", op: "add", value: viewer, source: "habit" })

  const count = (prs: any[]) => {
    const m = new Map<string, number>()
    for (const p of prs) for (const l of new Set<string>((p.labels ?? []).map((x: any) => String(x.name)))) m.set(l, (m.get(l) ?? 0) + 1)
    return m
  }
  const labels: Habits["labels"] = []
  if (n >= 5) for (const [name, c] of count(list)) if (c / n >= 0.6) labels.push({ name, count: c, of: n, scope: "all" })
  const type = typeHint?.match(TYPE)?.[1]?.toLowerCase() ?? null
  if (type) {
    const sameType = list.filter((p: any) => String(p.title).match(TYPE)?.[1]?.toLowerCase() === type)
    if (sameType.length >= 3)
      for (const [name, c] of count(sameType))
        if (c / sameType.length >= 0.6 && !labels.some((l) => l.name === name)) labels.push({ name, count: c, of: sameType.length, scope: type })
  }
  for (const l of labels) changes.push({ kind: "label", op: "add", value: l.name, source: "habit" })

  const suggestions: Habits["suggestions"] = {}
  const ms = new Map<string, number>()
  for (const p of list) if (p.milestone?.title) ms.set(p.milestone.title, (ms.get(p.milestone.title) ?? 0) + 1)
  const top = [...ms.entries()].sort((a, b) => b[1] - a[1])[0]
  if (top && n >= 5 && top[1] / n >= 0.6) suggestions.milestone = { title: top[0], count: top[1], of: n }
  return { sample: n, selfAssigned, labels, suggestions, changes }
}

// ------------------------------------------------------------ assessment --

export type Assessment = {
  repo: string
  viewer: string
  targets: { id: string; number: number | null; headSha: string; changes: Judged[]; habits?: Habits }[]
  environment: { workflowsDefault: string[] | "unreadable"; chained: boolean; bots: Environment["bots"]; hooks: Environment["hooks"]; mandated: Environment["mandated"] }
  /** Branch commits the judgment read; applying first checks they have not moved. */
  shas: Record<string, string | null>
  digest: string
}

/** Judge a metadata request against each target (a PR, or a layer about to become one). */
export async function assess(opts: {
  repo: string
  defaultBranch: string
  targets: Target[]
  request: MetaRequest
  infer?: boolean
  cwd: string
}): Promise<Assessment> {
  const { repo, cwd } = opts
  const viewer = String((await gh(["api", "user", "--jq", ".login"], cwd)).stdout.trim())
  if (!viewer) throw new Error("Could not read your GitHub login (gh auth status).")
  const requested = changesOf(opts.request)
  const merged = opts.infer
    ? await ghJson(["pr", "list", "--repo", repo, "--state", "merged", "--author", "@me", "--limit", "30", "--json", "number,title,labels,assignees,milestone"], cwd)
    : undefined
  if (opts.infer && !Array.isArray(merged)) throw new Error("Could not read your merged PRs to infer habits.")

  const env = await environment(repo, opts.defaultBranch, opts.targets.map((t) => ({ name: t.base, sha: t.baseSha })), cwd)
  const labelList = await ghJson(["label", "list", "--repo", repo, "--limit", "1000", "--json", "name"], cwd)
  const msList = await ghPages(`repos/${repo}/milestones?state=open&per_page=100`, cwd)
  const facts: RepoFacts = {
    labels: Array.isArray(labelList) ? labelList.map((l: any) => String(l.name)) : null,
    milestones: msList ? msList.map((m: any) => String(m.title)) : null,
    assignable: new Map(),
    reviewable: new Map(),
  }

  const heads = new Map<string, Workflows>()
  const targets: Assessment["targets"] = []
  for (const t of opts.targets) {
    if (!heads.has(t.headSha)) heads.set(t.headSha, await workflowsAt(repo, t.headSha, cwd))
    const habit = merged ? habitsOf(merged, viewer, t.typeHint ?? null) : undefined
    const changes = [...requested]
    for (const h of habit?.changes ?? []) if (!changes.some((c) => c.kind === h.kind && c.op === "add" && same(c.value, h.value))) changes.push(h)
    const judged = await judge(repo, viewer, t, changes, env, heads.get(t.headSha)!, facts, cwd)
    targets.push({ id: t.id, number: t.number, headSha: t.headSha, changes: judged, ...(habit ? { habits: { sample: habit.sample, selfAssigned: habit.selfAssigned, labels: habit.labels, suggestions: habit.suggestions } } : {}) })
  }

  const wfDigest = (w: Workflows) => (w === "unreadable" ? "unreadable" : w.map((x) => `${x.path}@${x.digest}`).sort())
  // What the pending changes rest on: who asks, at which commits, with which consequences.
  const digest = sha1({
    repo,
    viewer,
    request: opts.request,
    infer: !!opts.infer,
    shas: env.shas,
    bases: opts.targets.map((t) => [t.base, t.baseSha ?? null]),
    env: { b: env.bots, h: env.hooks, m: env.mandated, c: env.chained },
    heads: [...heads.entries()].map(([sha, w]) => [sha, wfDigest(w)]),
    // The milestone a pending change replaces or clears is part of what was approved.
    pending: targets.map((t, i) => [
      t.id,
      t.headSha,
      t.changes.filter((c) => c.status === "approval").map((c) => [c.kind, c.op, c.value, c.reasons, c.kind === "milestone" ? opts.targets[i].milestone : null]),
    ]),
  })

  return {
    repo,
    viewer,
    targets,
    environment: {
      workflowsDefault: env.workflowsDefault === "unreadable" ? "unreadable" : env.workflowsDefault.map((w) => w.path),
      chained: env.chained,
      bots: env.bots,
      hooks: env.hooks,
      mandated: env.mandated,
    },
    shas: env.shas,
    digest,
  }
}

/** Apply the given changes to one PR with `gh pr edit`, one flag per value. */
export async function applyChanges(repo: string, number: number, changes: Judged[], cwd: string) {
  if (!changes.length) return { ok: true, output: "" }
  const flag: Record<Kind, Record<"add" | "remove", string>> = {
    label: { add: "--add-label", remove: "--remove-label" },
    assignee: { add: "--add-assignee", remove: "--remove-assignee" },
    reviewer: { add: "--add-reviewer", remove: "--remove-reviewer" },
    milestone: { add: "--milestone", remove: "--remove-milestone" },
  }
  const argv = ["pr", "edit", String(number), "--repo", repo]
  for (const c of changes) argv.push(...(c.kind === "milestone" && c.op === "remove" ? [flag.milestone.remove] : [`${flag[c.kind][c.op]}=${c.value}`]))
  const res = await gh(argv, cwd)
  return { ok: res.ok, output: out(res) }
}

// ------------------------------------------------------------------ tools --

const REPO = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/

export async function prTarget(repo: string, n: string, cwd: string): Promise<Target> {
  if (!/^\d+$/.test(n.trim())) throw new Error(`${n} is not a PR number.`)
  const pr = await ghJson(
    ["pr", "view", n.trim(), "--repo", repo, "--json", "number,state,title,author,headRefOid,baseRefName,labels,assignees,reviewRequests,milestone"],
    cwd,
  )
  if (!pr) throw new Error(`Could not read PR #${n} in ${repo}.`)
  if (pr.state !== "OPEN") throw new Error(`PR #${n} is ${pr.state}; metadata is set on open PRs only.`)
  return {
    id: `#${pr.number}`,
    number: pr.number,
    headSha: pr.headRefOid,
    base: pr.baseRefName,
    author: pr.author?.login ?? null,
    labels: (pr.labels ?? []).map((l: any) => String(l.name)),
    assignees: (pr.assignees ?? []).map((a: any) => String(a.login)),
    reviewers: (pr.reviewRequests ?? []).map((r: any) => String(r.login ?? (r.slug && r.organization?.login ? `${r.organization.login}/${r.slug}` : r.name ?? ""))),
    milestone: pr.milestone?.title ?? null,
    typeHint: pr.title ?? null,
  }
}

/** The parts of a PR a judgment rests on, to compare right before applying. */
const stateOf = (t: Target) => sha1([t.headSha, t.base, [...t.labels].sort(), [...t.assignees].sort(), [...t.reviewers].sort(), t.milestone])

async function run(args: any, cwd: string) {
  const repo = args.repo?.trim() || (await ghJson(["repo", "view", "--json", "nameWithOwner"], cwd))?.nameWithOwner
  if (!repo || !REPO.test(repo)) throw new Error("Could not resolve the repository; pass `repo` as owner/name.")
  const numbers: string[] = args.prs ?? []
  if (!numbers.length) throw new Error("Pass the PR numbers in `prs`.")
  const view = await ghJson(["repo", "view", repo, "--json", "defaultBranchRef"], cwd)
  const defaultBranch = view?.defaultBranchRef?.name
  if (!defaultBranch) throw new Error(`Could not read ${repo}'s default branch.`)
  const targets: Target[] = []
  for (const n of numbers) targets.push(await prTarget(repo, n, cwd))
  const request: MetaRequest = {
    labels: args.labels,
    assignees: args.assignees,
    reviewers: args.reviewers,
    milestone: args.milestone,
    removeMilestone: args.removeMilestone,
  }
  const assessment = await assess({ repo, defaultBranch, targets, request, infer: args.infer, cwd })
  return { repo, targets, assessment }
}

/** Apply, per PR, only if nothing the judgment read has moved since; otherwise leave it for a new judgment. */
async function applyWhereCurrent(repo: string, targets: Target[], assessment: Assessment, pick: (c: Judged) => boolean, cwd: string) {
  const applied = []
  const moved: string[] = []
  const errors: string[] = []
  for (const [i, t] of assessment.targets.entries()) {
    const todo = t.changes.filter(pick)
    if (!todo.length) continue
    // Checked again before each PR: a webhook, rule or branch may move during a multi-PR run.
    if (!(await environmentUnchanged(repo, assessment.shas, cwd)))
      return { applied, moved: assessment.targets.slice(i).map((x) => x.id), errors, envMoved: true }
    let now: Target | null = null
    try {
      now = await prTarget(repo, String(t.number), cwd)
    } catch {}
    if (!now || stateOf(now) !== stateOf(targets[i])) {
      moved.push(t.id)
      continue
    }
    const res = await applyChanges(repo, t.number!, todo, cwd)
    if (res.ok) applied.push({ pr: t.id, changes: todo.map(({ kind, op, value, source }) => ({ kind, op, value, source })) })
    else errors.push(`${t.id}: ${res.output}`)
  }
  return { applied, moved, errors, envMoved: false }
}

async function reread(repo: string, targets: Target[], cwd: string) {
  const now = []
  for (const t of targets) {
    try {
      const r = await prTarget(repo, String(t.number), cwd)
      now.push({ pr: r.id, labels: r.labels, assignees: r.assignees, reviewers: r.reviewers, milestone: r.milestone })
    } catch {
      now.push({ pr: t.id, unread: true })
    }
  }
  return now
}

const report = (targets: Assessment["targets"], pick: (c: Judged) => boolean) =>
  targets.map((t) => ({ pr: t.id, changes: t.changes.filter(pick).map(({ kind, op, value, source, reasons }) => ({ kind, op, value, source, reasons })) })).filter((t) => t.changes.length)

const movedNote = (r: { moved: string[]; envMoved: boolean }) =>
  r.moved.length
    ? { moved: r.moved, next: r.envMoved ? "A branch the judgment read moved before applying; nothing was applied. Run gh_pr_meta again." : "These PRs changed while being judged and were left alone; run gh_pr_meta again for them." }
    : {}

export const pr_meta = tool({
  description:
    "Add or remove labels, assignees, review requests and a milestone on one or more open PRs (a stack's layers too). Applies at once each change nothing reacts to — no workflow runs on its activity type (pull_request: the PR head's and its base's workflows; pull_request_target: the default branch's), no label-driven merge bot (labels), no repository webhook taking pull_request events, no ruleset-mandated workflow, nobody else notified — and returns the rest as `pending` with their reasons and a `token` for gh_pr_meta_apply, which asks. Unreadable or unparsable signals count as not harmless, and a PR or branch that moved while being judged is left alone. Labels, milestones, users and teams must exist; nothing is created; values with commas are refused; the PR's author cannot be its reviewer. `infer` adds what your merged PRs here habitually carry (yourself as assignee, labels on at least 60% of them, or of PRs of the same `type:`) and suggests a habitual milestone. Reviewers only when the user asked. Reports what changed, re-read from GitHub.",
  args: {
    prs: tool.schema.array(tool.schema.string()).describe("PR numbers."),
    repo: tool.schema.string().optional().describe("owner/name (default: the current repository)."),
    ...metaArgs,
  },
  async execute(args, context) {
    const cwd = context.worktree
    const { repo, targets, assessment } = await run(args, cwd)
    const result = await applyWhereCurrent(repo, targets, assessment, (c) => c.status === "harmless", cwd)
    const pending = report(assessment.targets, (c) => c.status === "approval")
    return JSON.stringify(
      {
        repo,
        applied: result.applied,
        ...movedNote(result),
        pending,
        ...(pending.length && !result.moved.length
          ? { token: assessment.digest, next: "Show the pending changes and their reasons to the user; apply them with gh_pr_meta_apply (same arguments and this token) once they agree." }
          : {}),
        invalid: report(assessment.targets, (c) => c.status === "invalid"),
        unchanged: report(assessment.targets, (c) => c.status === "unchanged"),
        habits: assessment.targets.filter((t) => t.habits).map((t) => ({ pr: t.id, ...t.habits })),
        environment: assessment.environment,
        now: await reread(repo, targets, cwd),
        ...(result.errors.length ? { errors: result.errors } : {}),
      },
      null,
      2,
    )
  },
})

export const pr_meta_apply = tool({
  description:
    "Apply the metadata changes gh_pr_meta returned as `pending`, after the user agreed. Pass the same arguments and its `token`: it judges again and refuses if anything the judgment rested on changed (a commit of the head or a base, a workflow, a bot config, a webhook, a ruleset, the pending changes and their reasons). Applies every remaining valid change, then re-reads the PRs.",
  args: {
    prs: tool.schema.array(tool.schema.string()).describe("PR numbers, as given to gh_pr_meta."),
    repo: tool.schema.string().optional().describe("owner/name, as given to gh_pr_meta."),
    token: tool.schema.string().describe("The token gh_pr_meta returned."),
    ...metaArgs,
  },
  async execute(args, context) {
    const cwd = context.worktree
    const { repo, targets, assessment } = await run(args, cwd)
    if (assessment.digest !== args.token.trim())
      throw new Error("What the judgment rested on changed since gh_pr_meta (a commit, workflow, bot config, webhook, ruleset or the pending changes); run gh_pr_meta again and show the new result.")
    const result = await applyWhereCurrent(repo, targets, assessment, (c) => c.status === "approval" || c.status === "harmless", cwd)
    return JSON.stringify(
      {
        repo,
        applied: result.applied,
        ...movedNote(result),
        invalid: report(assessment.targets, (c) => c.status === "invalid"),
        now: await reread(repo, targets, cwd),
        ...(result.errors.length ? { errors: result.errors } : {}),
      },
      null,
      2,
    )
  },
})
