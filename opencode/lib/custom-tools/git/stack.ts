import { existsSync, readFileSync, realpathSync } from "fs"
import { join } from "path"
import { tool } from "../define"
import { exec, runGit, tryGit, withTempFile } from "../exec"
import { conflictMap } from "./conflicts"
import { ghApi, localStack } from "./related"
import { currentBranch, forcePushBlock } from "./rewrite"
import { applyChanges, assess, environmentUnchanged, metaArgs, prTarget, type Assessment, type Judged, type MetaRequest, type Target } from "../pr-meta"
import { dedupe, scanDiff, scanSecrets } from "./secrets"
import { defaultRef, operation } from "./state"

/**
 * Native GitHub stacks (`gh stack`, the github/gh-stack extension) as three
 * tools, split by what they touch, because a tool's permission is decided once
 * per call and cannot ask halfway through:
 * - `git_stack` (allow) works on local branches only: split a branch into
 *   layers, add a layer, rebase the stack.
 * - `git_publish_preview` (allow, read-only) shows what publishing would do
 *   and pins it in a token.
 * - `git_publish` (ask) pushes and creates or links PRs, and only the
 *   exact state a preview showed: its token covers the remote, the base and
 *   every layer's local and remote commit, so anything that moved since the
 *   preview is refused rather than published. The commits leave through one
 *   leased push of the pinned shas; gh stack's own pushing commands (push,
 *   submit, sync) are never run, only `link`, which pushes nothing.
 * Publishing covers a plain branch too, as a stack of one layer that is never
 * linked: its base may be any branch on origin, while a stack's trunk is
 * always the remote default branch. No tool merges or unstacks; those stay
 * gated shell commands.
 */

const tail = (text: string, n = 40) => text.trim().split("\n").slice(-n).join("\n")
const COMMITS_MAX = 30

// gh and git never wait on a prompt or an editor here.
const NON_INTERACTIVE = {
  GH_PROMPT_DISABLED: "1",
  GH_NO_UPDATE_NOTIFIER: "1",
  GIT_TERMINAL_PROMPT: "0",
  GIT_EDITOR: "true",
  GIT_SEQUENCE_EDITOR: "true",
  NO_COLOR: "1",
}

const gh = (argv: string[], cwd: string, signal?: AbortSignal) =>
  exec(["gh", ...argv], { cwd, env: { ...process.env, ...NON_INTERACTIVE }, signal })

const ghStack = (argv: string[], cwd: string, signal?: AbortSignal) => gh(["stack", ...argv], cwd, signal)

async function ghJson(argv: string[], cwd: string): Promise<any> {
  const res = await gh(argv, cwd)
  if (!res.ok) return undefined
  const out = res.stdout.trim()
  try {
    return out ? JSON.parse(out) : null
  } catch {
    return undefined
  }
}

const output = (res: { stdout: string; stderr: string }) => tail(`${res.stdout}\n${res.stderr}`)

async function defaultName(cwd: string): Promise<string> {
  const def = await defaultRef(cwd)
  if (!def) throw new Error("The remote default branch is unknown here (no origin/HEAD, origin/main or origin/master); run `git remote set-head origin --auto` first.")
  return def.slice(def.indexOf("/") + 1)
}

/** Every change gh stack counts as uncommitted, untracked files included. */
async function dirtyFiles(cwd: string): Promise<string[]> {
  return (await runGit(["status", "--porcelain=v1"], cwd)).split("\n").filter(Boolean).slice(0, 20)
}

const sha = async (cwd: string, ref: string) => (await tryGit(["rev-parse", "--verify", "--quiet", `${ref}^{commit}`], cwd)).stdout.trim() || null

const isAncestor = async (cwd: string, a: string, b: string) => (await tryGit(["merge-base", "--is-ancestor", a, b], cwd)).ok

async function checkNewBranch(cwd: string, name: string): Promise<void> {
  if (!name.trim() || name.startsWith("-")) throw new Error(`\`${name}\` is not a branch name.`)
  if (!(await tryGit(["check-ref-format", "--branch", name], cwd)).ok) throw new Error(`\`${name}\` is not a valid branch name.`)
  if (await sha(cwd, `refs/heads/${name}`)) throw new Error(`A local branch ${name} already exists.`)
  if (await sha(cwd, `refs/remotes/origin/${name}`)) throw new Error(`origin already has a branch ${name}.`)
}

async function requireStack(cwd: string) {
  const branch = await currentBranch(cwd)
  if (!branch) throw new Error("HEAD is detached; check out a branch of the stack first.")
  const stack = await localStack(branch, cwd)
  if (!stack) throw new Error(`${branch} is not part of a local gh stack (\`gh stack view\` knows no stack for it). Create one with git_stack split.`)
  return { branch, stack }
}

const subjects = async (cwd: string, range: string) => {
  const list = (await tryGit(["log", "--reverse", "--format=%h %s", range], cwd)).stdout.split("\n").filter(Boolean)
  return { count: list.length, items: list.slice(0, COMMITS_MAX), truncated: list.length > COMMITS_MAX }
}

/** Where gh stack keeps its rebase state: the repository's common git directory. */
async function rebaseStateFile(cwd: string): Promise<string> {
  const common = (await runGit(["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd)).trim()
  return join(common, "gh-stack-rebase-state")
}

async function layerHeads(cwd: string, names: string[]): Promise<Record<string, string | null>> {
  const out: Record<string, string | null> = {}
  for (const name of names) out[name] = await sha(cwd, `refs/heads/${name}`)
  return out
}

const real = (p: string) => (existsSync(p) ? realpathSync(p) : p)

/**
 * Remote branches outside the stack (and its trunk) that hold a commit of it:
 * the rewrite rule's "shared" case, which a stack rebase must not break either.
 * A branch holds a commit of a layer exactly when it holds one of the roots of
 * that layer's own commits; every layer is asked, since layers awaiting a
 * restack carry diverged copies of the commits below them.
 */
async function sharedHolders(cwd: string, trunk: string, names: string[]): Promise<string[]> {
  const from = (await sha(cwd, `refs/remotes/origin/${trunk}`)) ? `refs/remotes/origin/${trunk}` : trunk
  const roots = new Set<string>()
  for (const name of names) {
    const rows = (await tryGit(["rev-list", "--parents", `refs/heads/${name}`, "--not", from], cwd)).stdout
      .split("\n")
      .filter(Boolean)
      .map((l) => l.split(" "))
    const inRange = new Set(rows.map((r) => r[0]))
    for (const r of rows) if (r.slice(1).every((p) => !inRange.has(p))) roots.add(r[0])
  }
  if (!roots.size) return []
  const own = new Set([trunk, ...names].map((n) => `origin/${n}`))
  return (await tryGit(["branch", "-r", ...[...roots].flatMap((r) => ["--contains", r]), "--format=%(refname:short)"], cwd)).stdout
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l && !l.endsWith("/HEAD") && !own.has(l))
}

// ------------------------------------------------------------------ plan --

type Layer = {
  position: number
  branch: string
  local: string | null
  remote: string | null
  merged: boolean
  push: "none" | "create" | "fast-forward" | "force" | "skip"
  base: string
  commits: { count: number; items: string[]; truncated: boolean }
  pr: { number: number; base: string; draft: boolean; url: string; autoMerge: boolean } | null
}

type Refusal = { rule: string; message: string }

type PR = { number: number; headRefName: string; baseRefName: string; isDraft: boolean; url: string; isCrossRepository: boolean; autoMergeRequest: unknown }

/** The open PR of each branch, asked per branch so no list limit hides one; undefined when any lookup fails. */
async function openPRs(repo: string, cwd: string, names: string[]): Promise<Map<string, PR> | undefined> {
  const map = new Map<string, PR>()
  for (const name of names) {
    const list = await ghJson(
      ["pr", "list", "--repo", repo, "--state", "open", "--head", name, "--json", "number,headRefName,baseRefName,isDraft,url,isCrossRepository,autoMergeRequest"],
      cwd,
    )
    if (!Array.isArray(list)) return undefined
    const pr = list.find((p: PR) => p.headRefName === name && !p.isCrossRepository)
    if (pr) map.set(name, pr)
  }
  return map
}

async function lsRemote(cwd: string, names: string[]): Promise<Map<string, string> | undefined> {
  const res = await exec(["git", "ls-remote", "--heads", "origin", ...names.map((n) => `refs/heads/${n}`)], {
    cwd,
    env: { ...process.env, GIT_TERMINAL_PROMPT: "0" },
  })
  if (!res.ok) return undefined
  const map = new Map<string, string>()
  for (const line of res.stdout.split("\n")) {
    const [hash, ref] = line.trim().split(/\s+/)
    if (hash && ref?.startsWith("refs/heads/")) map.set(ref.slice("refs/heads/".length), hash)
  }
  return map
}

/** `owner/repo` of a github.com URL (https, ssh or scp form) and nothing else. */
function githubOf(url: string): string | null {
  const m = url
    .trim()
    .match(/^(?:https:\/\/(?:[^@/\s]+@)?github\.com\/|ssh:\/\/git@github\.com(?::22)?\/|git@github\.com:)([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+?)(?:\.git)?\/?$/)
  return m ? m[1] : null
}

/** A repository on this machine: pushing there publishes nothing (tests, local mirrors). */
const isLocal = (url: string) => url.startsWith("/") || url.startsWith("file://")

/**
 * origin's GitHub repository, from its configured URL, and where it pushes.
 * Every push URL counts (git pushes to all of them), so origin must have
 * exactly one, it must be where fetches come from, and after URL rewriting
 * (insteadOf) it must still be that GitHub repository — or a local one.
 */
async function originOf(cwd: string): Promise<{ repo: string | null; pushUrl: string; refusals: Refusal[] }> {
  const refusals: Refusal[] = []
  const configured = (await tryGit(["config", "--get", "remote.origin.url"], cwd)).stdout.trim()
  const urls = async (push: boolean) =>
    (await tryGit(["remote", "get-url", "--all", ...(push ? ["--push"] : []), "origin"], cwd)).stdout.split("\n").map((u) => u.trim()).filter(Boolean)
  const fetchUrls = await urls(false)
  const pushUrls = await urls(true)
  const repo = configured ? githubOf(configured) : null
  if (!repo) refusals.push({ rule: "remote", message: "origin is not a github.com repository; native stacks live on GitHub." })
  if (pushUrls.length !== 1 || fetchUrls.length !== 1 || pushUrls[0] !== fetchUrls[0])
    refusals.push({ rule: "remote", message: "origin must push to exactly one URL, the one it fetches from; publish from a plain origin." })
  else if (repo && !isLocal(pushUrls[0]) && githubOf(pushUrls[0])?.toLowerCase() !== repo.toLowerCase())
    refusals.push({ rule: "remote", message: `origin's URL is rewritten to ${pushUrls[0]}, which is not ${repo}; publish where GitHub's checks apply.` })
  return { repo, pushUrl: pushUrls.join(" "), refusals }
}

/**
 * Pushes exactly the pinned commits: one atomic push of `<sha>:refs/heads/<layer>`
 * per layer that moves, each leased on the remote commit the preview saw (an
 * absent branch must still be absent). Hooks run; tags and submodules stay put.
 */
async function pushPinned(cwd: string, layers: Layer[], signal?: AbortSignal) {
  const moving = layers.filter((l) => !l.merged && l.local && l.push !== "none" && l.push !== "skip")
  if (!moving.length) return { ok: true, pushed: [] as string[], output: "Nothing to push." }
  const argv = [
    "git",
    "push",
    "--atomic",
    "--porcelain",
    "--no-follow-tags",
    "--recurse-submodules=no",
    ...moving.map((l) => `--force-with-lease=refs/heads/${l.branch}:${l.remote ?? ""}`),
    "origin",
    ...moving.map((l) => `${l.local}:refs/heads/${l.branch}`),
  ]
  const res = await exec(argv, { cwd, env: { ...process.env, GIT_TERMINAL_PROMPT: "0" }, signal })
  return { ok: res.ok, pushed: res.ok ? moving.map((l) => l.branch) : [], output: output(res) }
}

/**
 * The publication the current branch would make, what blocks it, and the
 * token that pins it. A branch in a native stack publishes every layer on the
 * default branch; any other branch publishes as one layer — a plain PR — on
 * `base`, else its open PR's base, else the default branch.
 */
type MetaOpts = MetaRequest & { infer?: boolean }
type PlanOpts = { base?: string; meta?: MetaOpts; layerMeta?: { branch: string; meta: MetaOpts }[] }

const union = (a?: string[], b?: string[]) => (a || b ? [...new Set([...(a ?? []), ...(b ?? [])])] : undefined)

/** A layer's metadata: the shared request with its own added on top. */
function mergeMeta(common?: MetaOpts, own?: MetaOpts): MetaOpts {
  const pair = (k: "labels" | "assignees" | "reviewers") => {
    const add = union(common?.[k]?.add, own?.[k]?.add)
    const remove = union(common?.[k]?.remove, own?.[k]?.remove)
    return add || remove ? { ...(add ? { add } : {}), ...(remove ? { remove } : {}) } : undefined
  }
  const m: MetaOpts = {}
  for (const k of ["labels", "assignees", "reviewers"] as const) {
    const v = pair(k)
    if (v) m[k] = v
  }
  const milestone = own?.milestone ?? common?.milestone
  if (milestone) m.milestone = milestone
  if (own?.removeMilestone ?? common?.removeMilestone) m.removeMilestone = true
  if (own?.infer ?? common?.infer) m.infer = true
  return m
}

const isEmptyMeta = (m: MetaOpts) => !m.labels && !m.assignees && !m.reviewers && !m.milestone && !m.removeMilestone && !m.infer

type LayerMeta = { branch: string; pr: number | null; changes: Judged[]; habits?: unknown }

async function plan(cwd: string, opts: PlanOpts = {}) {
  const branch = await currentBranch(cwd)
  if (!branch) throw new Error("HEAD is detached; check out the branch to publish first.")
  const stack = await localStack(branch, cwd)
  const mode: "stack" | "plain" = stack ? "stack" : "plain"
  const what = stack ? "the stack" : branch
  const refusals: Refusal[] = []
  const warnings: string[] = []
  const defName = await defaultName(cwd)
  const names: string[] = stack ? stack.layers.map((l: any) => l.head) : [branch]
  const mergedFlags: boolean[] = stack ? stack.layers.map((l: any) => Boolean(l.merged)) : [false]
  const explicitBase = opts.base?.trim() || undefined
  if (explicitBase && (explicitBase.startsWith("-") || !(await tryGit(["check-ref-format", "--branch", explicitBase], cwd)).ok))
    throw new Error(`\`${explicitBase}\` is not a branch name.`)
  if (stack && explicitBase && explicitBase !== (stack.trunk ?? defName))
    throw new Error("A stack's base is its trunk, the default branch; `base` applies to a plain branch only.")

  if (stack) {
    const trunk = stack.trunk ?? defName
    if (trunk !== defName)
      refusals.push({ rule: "trunk", message: `The stack's trunk is ${trunk}, not the default branch ${defName}; closing keywords do not fire there. Re-create it on ${defName}.` })
  }
  if (names.includes(defName))
    refusals.push({ rule: "default-branch", message: stack ? `${defName} is a layer of this stack; it is never published as one.` : `${branch} is the default branch; publish from a task branch.` })
  const op = await operation(cwd)
  if (op) refusals.push({ rule: "operation", message: `A ${op} is in progress; finish or abort it first.` })
  if (existsSync(await rebaseStateFile(cwd))) refusals.push({ rule: "operation", message: "A gh stack rebase is in progress; git_stack rebase continue or abort it first." })
  const dirty = await dirtyFiles(cwd)
  if (dirty.length) refusals.push({ rule: "dirty", message: `Uncommitted or untracked files (${dirty.slice(0, 5).join(", ")}); commit or stash them, only committed work is published.` })

  const { repo, pushUrl, refusals: remoteRefusals } = await originOf(cwd)
  refusals.push(...remoteRefusals)

  let githubDefault: string | undefined
  if (repo) {
    // Fail closed: gh resolves its own target repository, which must be known to be origin's.
    const view = await ghJson(["repo", "view", "--json", "nameWithOwner,viewerPermission,defaultBranchRef"], cwd)
    if (!view) refusals.push({ rule: "repository", message: "Could not read the repository gh targets; its target, your permission and the default branch are unknown." })
    else {
      if (String(view.nameWithOwner).toLowerCase() !== repo.toLowerCase())
        refusals.push({
          rule: "cross-repository",
          message: `gh targets ${view.nameWithOwner} but origin is ${repo}; these tools publish within one repository. Open a PR from a fork with the shell (gh pr create).`,
        })
      if (!["WRITE", "MAINTAIN", "ADMIN"].includes(view.viewerPermission))
        refusals.push({ rule: "permission", message: `You have ${view.viewerPermission ?? "no"} access to ${repo}; the branches must live in the repository itself.` })
      githubDefault = view.defaultBranchRef?.name || undefined
    }
  }
  if (githubDefault && !stack && branch === githubDefault)
    refusals.push({ rule: "default-branch", message: `${branch} is the default branch; publish from a task branch.` })

  const prs = repo ? await openPRs(repo, cwd, names) : undefined
  // Without them a publication cannot tell an existing draft from a new PR.
  if (repo && !prs) refusals.push({ rule: "pull-requests", message: "Could not list the open PRs; their state and draft flags are unknown." })

  // The bottom layer's base: a stack's trunk; a plain branch's explicit base, else its PR's, else the default branch.
  const existingBase = !stack ? prs?.get(branch)?.baseRefName : undefined
  const trunk: string = stack ? (stack.trunk ?? defName) : (explicitBase ?? existingBase ?? githubDefault ?? defName)
  if (stack && githubDefault && githubDefault !== trunk)
    refusals.push({ rule: "trunk", message: `GitHub's default branch is ${githubDefault}, not the stack's trunk ${trunk}; run \`git remote set-head origin --auto\` and re-create the stack on it.` })
  if (!stack && trunk === branch) refusals.push({ rule: "base", message: `${branch} cannot be its own base.` })
  const retarget = !stack && existingBase && explicitBase && existingBase !== explicitBase ? { from: existingBase, to: explicitBase } : null

  const remote = await lsRemote(cwd, [trunk, ...names])
  if (!remote) warnings.push("Could not read origin's branches (ls-remote failed); remote state is as of the last fetch.")
  const remoteOf = async (name: string) => (remote ? (remote.get(name) ?? null) : await sha(cwd, `refs/remotes/origin/${name}`))
  const trunkRemote = await remoteOf(trunk)
  if (!trunkRemote) refusals.push({ rule: "base", message: `origin has no branch ${trunk} to base ${what} on.` })

  // Where the bottom layer's own commits start: the trunk as origin has it, else locally, else the default branch.
  const trunkRef =
    (await sha(cwd, `refs/remotes/origin/${trunk}`)) ? `refs/remotes/origin/${trunk}` : (await sha(cwd, `refs/heads/${trunk}`)) ? `refs/heads/${trunk}` : (await defaultRef(cwd))!
  const layers: Layer[] = []
  for (const [i, name] of names.entries()) {
    const local = await sha(cwd, `refs/heads/${name}`)
    const remoteSha = await remoteOf(name)
    const merged = mergedFlags[i]
    if (!local && !merged) refusals.push({ rule: "missing", message: `Layer ${name} has no local branch; restore it with \`gh stack checkout\`.` })
    let push: Layer["push"] = "none"
    if (merged) push = "skip"
    else if (local && !remoteSha) push = "create"
    else if (local && remoteSha && remoteSha !== local) {
      const known = (await tryGit(["cat-file", "-e", `${remoteSha}^{commit}`], cwd)).ok
      push = known && (await isAncestor(cwd, remoteSha, local)) ? "fast-forward" : "force"
    }
    const below = i === 0 ? trunkRef : `refs/heads/${names[i - 1]}`
    const pr = prs?.get(name)
    layers.push({
      position: i + 1,
      branch: name,
      local,
      remote: remoteSha,
      merged,
      push,
      base: i === 0 ? trunk : names[i - 1],
      commits: local ? await subjects(cwd, `${below}..refs/heads/${name}`) : { count: 0, items: [], truncated: false },
      pr: pr ? { number: pr.number, base: pr.baseRefName, draft: pr.isDraft, url: pr.url, autoMerge: pr.autoMergeRequest != null } : null,
    })
  }

  const active = layers.filter((l) => !l.merged)
  for (const l of active) if (l.local && !l.commits.count) warnings.push(`Layer ${l.branch} has no commits of its own; GitHub will not open a PR for it.`)

  // Each layer must sit on the one below, and the bottom on the base's latest commit.
  const rebaseWith = stack ? "git_stack rebase" : `git_rebase (onto ${trunk})`
  if (stack?.needsRebase) refusals.push({ rule: "rebase", message: "A layer no longer sits on the one below it; run git_stack rebase first." })
  const bottom = active[0]?.local
  if (bottom && trunkRemote) {
    const known = (await tryGit(["cat-file", "-e", `${trunkRemote}^{commit}`], cwd)).ok
    if (!known || !(await isAncestor(cwd, trunkRemote, bottom)))
      refusals.push({ rule: "rebase", message: `${stack ? "The stack" : branch} is behind origin/${trunk}; run ${rebaseWith} first so it is built on its latest state.` })
  }

  if (repo)
    for (const l of active.filter((x) => x.push === "force")) {
      const block = await forcePushBlock(repo, l.branch, cwd)
      if (block === undefined) warnings.push(`Could not read GitHub's protection for ${l.branch}; GitHub still refuses the push if it is protected.`)
      else if (block) refusals.push({ rule: "protected", message: `${l.branch} cannot be force-pushed: ${block}.` })
    }

  const top = active[active.length - 1]
  let secrets = { gitleaksRan: false, findings: [] as any[] }
  if (top?.local && (await runGit(["rev-list", "--merges", `${trunkRef}..refs/heads/${top.branch}`], cwd)).trim())
    refusals.push({ rule: "merges", message: `${stack ? "The stack" : branch} contains merge commits; publish linear history. Rebase with ${rebaseWith}.` })
  if (top?.local) {
    // The net diff hides a secret one layer adds and a later one removes, yet
    // the lower branch still publishes it: scan every commit's own diff too.
    const range = `${trunkRef}..refs/heads/${top.branch}`
    const net = await scanSecrets({ target: "range", range }, cwd)
    const perCommit = scanDiff(await runGit(["log", "-p", "--format=", "--no-color", "--unified=0", "--no-merges", "--no-ext-diff", range], cwd))
    secrets = { gitleaksRan: net.gitleaksRan, findings: dedupe([...net.findings, ...perCommit]) }
  }

  // Metadata the publication sets, judged per layer as gh_pr_meta judges it.
  const meta: LayerMeta[] = []
  let metaInfo: Pick<Assessment, "environment"> | null = null
  const metaDigests: string[] = []
  const metaShas: Record<string, string | null> = {}
  const known = new Set(active.map((l) => l.branch))
  for (const m of opts.layerMeta ?? []) if (!known.has(m.branch)) throw new Error(`${m.branch} is not being published here (${[...known].join(", ")}).`)
  const wanted = active.map((l) => ({ l, request: mergeMeta(opts.meta, opts.layerMeta?.find((m) => m.branch === l.branch)?.meta) })).filter((x) => !isEmptyMeta(x.request))
  if (wanted.length && !repo) refusals.push({ rule: "metadata", message: "PR metadata needs a GitHub repository." })
  else if (wanted.length) {
    const groups = new Map<string, { request: MetaOpts; items: { l: Layer; target: Target }[] }>()
    for (const { l, request } of wanted) {
      if (!l.local) continue
      // A layer's base is the layer below, read at the commit about to be pushed.
      const below = active[active.indexOf(l) - 1]
      const baseSha = below?.local ?? undefined
      const subject = l.commits.items[0]
      let target: Target = {
        id: l.branch,
        number: null,
        headSha: l.local,
        base: l.base,
        baseSha,
        author: null,
        labels: [],
        assignees: [],
        reviewers: [],
        milestone: null,
        typeHint: subject ? subject.slice(subject.indexOf(" ") + 1) : null,
      }
      if (l.pr) {
        try {
          // Judged against the commit about to be pushed and the base it will have.
          target = { ...(await prTarget(repo!, String(l.pr.number), cwd)), headSha: l.local, base: l.base, baseSha }
        } catch {
          refusals.push({ rule: "metadata", message: `Could not read PR #${l.pr.number}'s current metadata.` })
          continue
        }
      }
      const key = JSON.stringify(request)
      if (!groups.has(key)) groups.set(key, { request, items: [] })
      groups.get(key)!.items.push({ l, target })
    }
    for (const { request, items } of groups.values()) {
      const a = await assess({ repo: repo!, defaultBranch: githubDefault ?? defName, targets: items.map((i) => i.target), request, infer: request.infer, cwd })
      metaInfo ??= { environment: a.environment }
      metaDigests.push(a.digest)
      Object.assign(metaShas, a.shas)
      for (const [i, t] of a.targets.entries()) meta.push({ branch: items[i].l.branch, pr: t.number, changes: t.changes, ...(t.habits ? { habits: t.habits } : {}) })
    }
  }

  const token = new Bun.CryptoHasher("sha1")
    .update(
      JSON.stringify({
        mode,
        repo,
        pushUrl,
        trunk,
        trunkRemote,
        retarget,
        layers: layers.map((l) => [l.branch, l.local, l.remote, l.merged]),
        meta: [opts.meta ?? null, opts.layerMeta ?? null, metaDigests, meta.map((m) => [m.branch, m.changes.map((c) => [c.kind, c.op, c.value, c.status])])],
      }),
    )
    .digest("hex")
    .slice(0, 12)

  return { mode, branch, repo, trunk, trunkRemote, retarget, layers, prs, meta, metaInfo, metaShas, refusals, warnings, secrets, token }
}

const summary = (p: Awaited<ReturnType<typeof plan>>) => ({
  mode: p.mode,
  repo: p.repo,
  base: p.trunk,
  current: p.branch,
  ...(p.retarget ? { retarget: p.retarget } : {}),
  layers: p.layers,
  nativeStack:
    p.mode === "plain"
      ? "A plain branch publishes as one ordinary PR; adopt it as a stack (git_stack split) to build layers on it."
      : p.layers.filter((l) => !l.merged).length >= 2
        ? "GitHub links two or more PRs into a native stack."
        : "A single layer publishes as an ordinary PR: GitHub forms a stack from two PRs, so linking waits for the next layer.",
  ...(p.meta.length
    ? {
        metadata: {
          layers: p.meta.map((m) => ({
            branch: m.branch,
            pr: m.pr,
            changes: m.changes.map(({ kind, op, value, source, status, reasons }) => ({ kind, op, value, source, status, reasons })),
            ...(m.habits ? { habits: m.habits } : {}),
          })),
          note: "Publishing applies every harmless and every approval change shown here, since the publication itself is approved; invalid and unchanged ones are skipped.",
          ...p.metaInfo,
        },
      }
    : {}),
  secretScan: { pass: p.secrets.findings.length === 0, gitleaksRan: p.secrets.gitleaksRan, findings: p.secrets.findings },
  refusals: p.refusals,
  warnings: p.warnings,
  token: p.token,
})

// ------------------------------------------------------------ git_stack --

async function split(cwd: string, at: string[], names: string[]) {
  const branch = await currentBranch(cwd)
  if (!branch) throw new Error("HEAD is detached; check out the task branch first.")
  const op = await operation(cwd)
  if (op) throw new Error(`A ${op} is in progress; finish or abort it first.`)
  const defName = await defaultName(cwd)
  if (branch === defName) throw new Error(`${branch} is the default branch; move the work to a task branch first.`)
  const dirty = await dirtyFiles(cwd)
  if (dirty.length) throw new Error(`Commit or stash these first (gh stack refuses untracked files too): ${dirty.join(", ")}`)
  if (await localStack(branch, cwd)) throw new Error(`${branch} is already a layer of a stack; add layers with git_stack add.`)
  if (at.length !== names.length) throw new Error("`at` and `names` must list the same number of entries: one cut and one branch name per lower layer.")

  const def = (await defaultRef(cwd))!
  const mergeBase = (await runGit(["merge-base", "HEAD", def], cwd)).trim()
  const commits = (await runGit(["rev-list", "--reverse", `${mergeBase}..HEAD`], cwd)).split("\n").filter(Boolean)
  if (commits.length < at.length + 1)
    throw new Error(`${branch} has ${commits.length} commit(s) of its own; ${at.length + 1} layer(s) need at least ${at.length + 1}.`)
  if ((await runGit(["rev-list", "--merges", `${mergeBase}..HEAD`], cwd)).trim())
    throw new Error(`${branch} contains merge commits; stack layers must be linear. Rebase it onto ${def} first (git_rebase).`)

  const cuts: string[] = []
  for (const ref of at) {
    if (ref.trim().startsWith("-")) throw new Error("`at` must name commits, not options.")
    const hash = await sha(cwd, ref.trim())
    const index = hash ? commits.indexOf(hash) : -1
    if (index < 0) throw new Error(`${ref} is not one of ${branch}'s own commits (${def}..HEAD).`)
    if (index === commits.length - 1) throw new Error(`${ref} is the branch tip; the top layer (${branch}) needs at least one commit above the last cut.`)
    if (cuts.length && index <= commits.indexOf(cuts[cuts.length - 1])) throw new Error("`at` must list cuts from the bottom up, each above the previous one.")
    cuts.push(hash!)
  }
  const seen = new Set<string>([branch])
  for (const name of names) {
    if (seen.has(name)) throw new Error(`Branch name ${name} is used twice.`)
    seen.add(name)
    await checkNewBranch(cwd, name)
  }

  const created: [string, string][] = []
  const rollback = async () => {
    for (const [name, hash] of created) await tryGit(["update-ref", "-d", `refs/heads/${name}`, hash], cwd)
  }
  try {
    for (const [i, name] of names.entries()) {
      await runGit(["branch", "--no-track", name, cuts[i]], cwd)
      created.push([name, cuts[i]])
    }
  } catch (error) {
    await rollback()
    throw error
  }
  const res = await ghStack(["init", "--base", defName, ...names, branch], cwd)
  if (!res.ok) {
    await rollback()
    throw new Error(`gh stack init failed; the new branches were removed:\n${output(res)}`)
  }

  const layers = []
  const all = [...names, branch]
  for (const [i, name] of all.entries())
    layers.push({ position: i + 1, branch: name, commits: await subjects(cwd, `${i === 0 ? mergeBase : all[i - 1]}..${name}`) })
  const warnings: string[] = []
  const existing = await ghJson(["pr", "list", "--head", branch, "--state", "open", "--json", "number,url"], cwd)
  if (Array.isArray(existing) && existing.length && names.length)
    warnings.push(
      `${branch} already has PR #${existing[0].number}; publishing makes it the top layer on ${names[names.length - 1]}. Narrow its title and body to that layer's commits.`,
    )
  return {
    split: true,
    trunk: defName,
    current: branch,
    layers,
    ...(warnings.length ? { warnings } : {}),
    next: names.length
      ? "Preview with git_publish_preview, then publish with git_publish submit."
      : "Add the next layer with git_stack add, commit its work, then git_publish_preview and git_publish submit.",
  }
}

async function add(cwd: string, name: string) {
  const { branch, stack } = await requireStack(cwd)
  const op = await operation(cwd)
  if (op) throw new Error(`A ${op} is in progress; finish or abort it first.`)
  await checkNewBranch(cwd, name)
  const top = stack.layers[stack.layers.length - 1].head
  if (branch !== top) {
    const dirty = await dirtyFiles(cwd)
    if (dirty.length) throw new Error(`New layers go on top (${top}); commit or stash before switching there: ${dirty.join(", ")}`)
    const res = await ghStack(["top"], cwd)
    if (!res.ok) throw new Error(`gh stack top failed:\n${output(res)}`)
  }
  const res = await ghStack(["add", name], cwd)
  if (!res.ok) throw new Error(`gh stack add failed:\n${output(res)}`)
  const after = await localStack(name, cwd)
  return {
    added: name,
    on: top,
    position: after?.position ?? null,
    size: after?.size ?? null,
    next: "Commit this layer's work (git_commit), then git_publish_preview and git_publish submit.",
  }
}

async function rebase(cwd: string, action: "start" | "continue" | "abort", scope: "all" | "downstack" | "upstack", noTrunk: boolean, signal?: AbortSignal) {
  const stateFile = await rebaseStateFile(cwd)
  let before: Record<string, string | null> | null = null
  let names: string[] = []
  let res
  if (action === "start") {
    const { stack } = await requireStack(cwd)
    if (existsSync(stateFile)) throw new Error("A gh stack rebase is already in progress: continue or abort it.")
    const op = await operation(cwd)
    if (op) throw new Error(`A ${op} is in progress; finish or abort it first.`)
    const dirty = await dirtyFiles(cwd)
    if (dirty.length) throw new Error(`Commit or stash these first (gh stack refuses untracked files too): ${dirty.join(", ")}`)
    names = stack.layers.map((l: any) => l.head)
    before = await layerHeads(cwd, names)
    const shared = await sharedHolders(cwd, stack.trunk ?? (await defaultName(cwd)), names)
    if (shared.length)
      throw new Error(
        `Other remote branches also hold this stack's commits (${shared.slice(0, 5).join(", ")}); rewriting them would break that work. Make new commits instead.`,
      )
    const argv = ["rebase", ...(scope === "downstack" ? ["--downstack"] : scope === "upstack" ? ["--upstack"] : []), ...(noTrunk ? ["--no-trunk"] : [])]
    res = await ghStack(argv, cwd, signal)
  } else {
    if (!existsSync(stateFile)) throw new Error("No gh stack rebase is in progress.")
    const state = JSON.parse(readFileSync(stateFile, "utf8"))
    names = state.stackBranches ?? []
    if (action === "continue") {
      const where = state.worktrees?.owners?.[state.worktrees?.pending]?.path ?? state.worktrees?.origin?.path ?? cwd
      const unmerged = (await runGit(["diff", "--name-only", "--diff-filter=U"], where)).split("\n").filter(Boolean)
      if (unmerged.length)
        return {
          rebased: false,
          stoppedAt: "conflicts",
          layer: state.worktrees?.pending ?? null,
          worktree: where,
          unresolved: unmerged,
          conflicts: await conflictMap(where),
          next: "These files are still unmerged: resolve them and `git add` each before continuing.",
        }
    }
    res = await ghStack(["rebase", action === "continue" ? "--continue" : "--abort"], cwd, signal)
    if (action === "abort") {
      if (!res.ok) throw new Error(`gh stack rebase --abort failed:\n${output(res)}`)
      return { aborted: true, branch: await currentBranch(cwd), output: output(res) }
    }
  }

  if (existsSync(stateFile)) {
    const state = JSON.parse(readFileSync(stateFile, "utf8"))
    const pending = state.worktrees?.pending ?? null
    const where = state.worktrees?.owners?.[pending]?.path ?? state.worktrees?.origin?.path ?? cwd
    return {
      rebased: false,
      stoppedAt: "conflicts",
      layer: pending,
      worktree: where,
      ...(real(where) !== real(cwd) ? { note: `The conflict is in another worktree (${where}); resolve and \`git add\` there.` } : {}),
      before,
      conflicts: await conflictMap(where),
      output: output(res),
      next: "Resolve each file (ours is the layer below, theirs the commit being replayed; lockfiles are regenerated), `git add` it, then git_stack rebase continue; abort restores every layer.",
    }
  }
  if (!res.ok) return { rebased: false, stoppedAt: "rebase", exitCode: res.code, before, output: output(res) }
  const after = await layerHeads(cwd, names)
  return {
    rebased: true,
    branch: await currentBranch(cwd),
    ...(before ? { before, moved: names.filter((n) => before![n] !== after[n]) } : {}),
    after,
    output: output(res),
    next: "Run the quick check, then git_publish_preview and git_publish push (or submit).",
  }
}

export const stack = tool({
  description:
    "Work with a native GitHub stack (gh stack) locally; never pushes (git_publish_preview and git_publish publish it). split: cut the current branch's own commits into layers — `at` lists the last commit of each lower layer bottom-up, `names` their new branch names; the current branch becomes the top layer and the trunk is the default branch; with no cuts it adopts the branch (and its PR) as a one-layer stack, so add can build on an unmerged PR (refuses the default branch, uncommitted or untracked files, merge commits, an existing stack). add: append a new layer branch on top of the stack (switches to the top first). rebase: `gh stack rebase` without an editor — start (scope all/downstack/upstack, noTrunk), continue, abort; on conflicts returns the conflict map and the layer and worktree they are in; returns each layer's commit before and after.",
  args: {
    action: tool.schema.enum(["split", "add", "rebase"]).describe("split, add or rebase."),
    at: tool.schema.array(tool.schema.string()).optional().describe("split: the last commit of each lower layer, bottom-up."),
    names: tool.schema.array(tool.schema.string()).optional().describe("split: a new branch name per entry of `at`, bottom-up."),
    name: tool.schema.string().optional().describe("add: the new layer's branch name."),
    step: tool.schema.enum(["start", "continue", "abort"]).optional().describe("rebase: start (default), continue or abort."),
    scope: tool.schema.enum(["all", "downstack", "upstack"]).optional().describe("rebase start: all layers (default), trunk up to the current one, or the current one up."),
    noTrunk: tool.schema.boolean().optional().describe("rebase start: only rebase layers onto each other; do not fetch or rebase onto the trunk."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    let out: unknown
    if (args.action === "split") out = await split(cwd, args.at ?? [], args.names ?? [])
    else if (args.action === "add") {
      if (!args.name) throw new Error("add requires `name`.")
      out = await add(cwd, args.name.trim())
    } else out = await rebase(cwd, args.step ?? "start", args.scope ?? "all", Boolean(args.noTrunk), context.signal)
    return JSON.stringify(out, null, 2)
  },
})

// ---------------------------------------- git_publish_preview / git_publish --

function publishMetaArgs() {
  const meta = tool.schema.object(metaArgs)
  return {
    meta: meta
      .optional()
      .describe("PR metadata for every published PR (labels, assignees, reviewers, milestone, infer), judged in the preview and set on publishing."),
    layerMeta: tool.schema
      .array(tool.schema.object({ branch: tool.schema.string(), meta }))
      .optional()
      .describe("Stack only: metadata for one layer, added on top of `meta`."),
  }
}

export const publish_preview = tool({
  description:
    "Preview what git_publish would do for the current branch, read-only. A branch in a native stack publishes every layer on the default branch; any other branch publishes as one plain PR on `base` (else its open PR's base, else the default branch; `retarget` shows an existing PR's base change). Shows each layer's commits against the one below, whether its push creates, fast-forwards or force-pushes, its PR, refusals (dirty tree, behind the base, merges, fork/cross-repository, redirected or multiple push URLs, unreadable gh target or PR list, protected branch, a base missing on origin, a stack off the default branch), a secret scan of every commit, and the `token` git_publish requires. With `meta` (and `layerMeta` for one layer of a stack) it also judges the labels, assignees, review requests and milestone each PR will get, as gh_pr_meta does (harmless, approval with reasons, invalid, unchanged; `infer` adds your habitual assignee and labels). Show it to the user before publishing.",
  args: {
    base: tool.schema.string().optional().describe("Plain branch only: the PR's base branch (default: its open PR's base, else the default branch)."),
    ...publishMetaArgs(),
  },
  async execute(args, context) {
    return JSON.stringify(summary(await plan(context.worktree, { base: args.base, meta: args.meta, layerMeta: args.layerMeta })), null, 2)
  },
})

type PRState = Record<string, { number: number; base: string; draft: boolean; url: string; autoMerge: boolean } | null>

function stateOf(prs: Map<string, PR>, names: string[]): PRState {
  const out: PRState = {}
  for (const name of names) {
    const pr = prs.get(name)
    out[name] = pr ? { number: pr.number, base: pr.baseRefName, draft: pr.isDraft, url: pr.url, autoMerge: pr.autoMergeRequest != null } : null
  }
  return out
}

/** The open PRs of these layers, or undefined when they could not be listed (never "none"). */
async function prState(repo: string, cwd: string, names: string[]): Promise<PRState | undefined> {
  const prs = await openPRs(repo, cwd, names)
  return prs ? stateOf(prs, names) : undefined
}

async function verify(cwd: string, p: Awaited<ReturnType<typeof plan>>, before: PRState) {
  const active = p.layers.filter((l) => !l.merged)
  const remote = await lsRemote(cwd, active.map((l) => l.branch))
  const after = await prState(p.repo!, cwd, active.map((l) => l.branch))
  const layers = []
  for (const [i, l] of active.entries()) {
    const remoteSha = remote?.get(l.branch) ?? null
    const pr = after ? after[l.branch] : undefined
    const expectedBase = i === 0 ? p.trunk : active[i - 1].branch
    layers.push({
      position: l.position,
      branch: l.branch,
      pushed: remote ? remoteSha === l.local : null,
      pr,
      ...(pr && pr.base !== expectedBase ? { baseMismatch: `PR base is ${pr.base}, expected ${expectedBase}` } : {}),
    })
  }
  const autoMergeDisabled = Object.entries(before)
    .filter(([name, pr]) => pr?.autoMerge && after?.[name] && !after[name]!.autoMerge)
    .map(([, pr]) => pr!.number)
  let native: unknown = null
  const firstPR = layers.find((l) => l.pr)?.pr
  if (firstPR && p.mode === "stack") {
    const membership = await ghApi(`repos/${p.repo}/pulls/${firstPR.number}`, ".stack", cwd)
    native = membership?.number ? { stack: membership.number, size: membership.size ?? null } : null
  }
  return {
    layers,
    nativeStack: native,
    ...(autoMergeDisabled.length ? { autoMergeDisabled } : {}),
    ...(after ? {} : { prsUnread: "Could not re-read the PRs after publishing; check them with gh_pr_status." }),
  }
}

const UNAVAILABLE = /stacks? (are |is )?(not available|unavailable|not enabled)|ErrStacksUnavailable/i

/**
 * Set the metadata the preview judged, on each layer's PR. The publication's
 * own approval covers every change the preview showed, harmless or not.
 */
async function applyMeta(cwd: string, p: Awaited<ReturnType<typeof plan>>, prNumbers: Map<string, number>) {
  if (!p.meta.length) return {}
  const applied = []
  const skipped = []
  const errors: string[] = []
  // The workflows, bots and rules judged were read at these commits; if one moved, judge again.
  if (!(await environmentUnchanged(p.repo!, p.metaShas, cwd)))
    return { metadata: { applied, notApplied: "A branch the metadata judgment read moved during publishing; set it with gh_pr_meta, which judges again." } }
  for (const m of p.meta) {
    const todo = m.changes.filter((c) => c.status === "harmless" || c.status === "approval")
    if (!todo.length) continue
    const number = prNumbers.get(m.branch)
    if (!number) {
      skipped.push({ branch: m.branch, reason: "it has no PR (submit opens one)" })
      continue
    }
    const res = await applyChanges(p.repo!, number, todo, cwd)
    if (res.ok) applied.push({ pr: number, changes: todo.map(({ kind, op, value, source }) => ({ kind, op, value, source })) })
    else errors.push(`#${number}: ${res.output}`)
  }
  return { metadata: { applied, ...(skipped.length ? { skipped } : {}), ...(errors.length ? { errors } : {}) } }
}

export const publish = tool({
  description:
    "Publish the current branch exactly as git_publish_preview showed it: every layer of its native stack, or a plain branch as one PR. Pass the preview's `token` (and the same `base`, `meta` and `layerMeta`); the metadata the preview judged is set on each PR once it exists, this approval covering it: if any layer, the base or the remote moved since, it refuses. Re-checks every refusal first (dirty tree, behind the base, fork/cross-repository, unreadable gh target or PR list, protected branch, a stack off the default branch, more than one push URL) and the secret scan (every commit, not only the net diff). push: one atomic `git push` of exactly the pinned commits to origin, each leased on the remote commit the preview saw. submit: that push, then a PR for each layer without one (`gh pr create` on the layer below or the base; ready unless `draft`; title and body from `prs`, else the layer's first commit subject), existing PRs keep their draft state and get `prs` titles and bodies, a plain PR's base changes when the preview showed `retarget`, and two or more stack PRs are linked with `gh stack link --base <default>` — none of these steps pushes; if stacks are unavailable it returns stacksUnavailable with the PRs left unlinked. link: link existing open PRs of this repository (numbers, bottom-up) into a stack on the default branch, always with an explicit --base. Afterwards it re-reads each layer's remote commit, PR, base and draft state, the native stack, and which PRs lost auto-merge. Never merges or unstacks.",
  args: {
    action: tool.schema.enum(["push", "submit", "link"]).describe("push, submit or link."),
    token: tool.schema.string().optional().describe("push / submit: the token from git_publish_preview."),
    base: tool.schema.string().optional().describe("push / submit, plain branch only: the same `base` the preview was given."),
    ...publishMetaArgs(),
    draft: tool.schema.boolean().optional().describe("submit: leave newly created PRs as drafts (default: ready for review)."),
    prs: tool.schema
      .array(tool.schema.object({ branch: tool.schema.string(), title: tool.schema.string().optional(), body: tool.schema.string().optional() }))
      .optional()
      .describe("submit: title and body per layer branch, applied once its PR exists."),
    numbers: tool.schema.array(tool.schema.string()).optional().describe("link: PR numbers of this repository, bottom-up (two or more)."),
    acceptSecretFindings: tool.schema.boolean().optional().describe("push / submit: publish despite secret-scan findings the user confirmed are not secrets."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    if (args.action === "link") return JSON.stringify(await link(cwd, args.numbers ?? []), null, 2)

    if (!args.token) throw new Error("Pass the token from git_publish_preview; publishing needs the state the user saw.")
    const p = await plan(cwd, { base: args.base, meta: args.meta, layerMeta: args.layerMeta })
    if (p.token !== args.token.trim())
      throw new Error("The branch changed since the preview (a layer, the base or the remote moved, or another `base` was passed); run git_publish_preview again and confirm it.")
    if (p.refusals.length) return JSON.stringify({ published: false, refusals: p.refusals, warnings: p.warnings }, null, 2)
    if (p.secrets.findings.length && !args.acceptSecretFindings)
      return JSON.stringify({ published: false, stoppedAt: "secrets", findings: p.secrets.findings, next: "Remove the secret from the commits, or confirm with the user that these are not secrets and pass acceptSecretFindings." }, null, 2)
    const known = new Set(p.layers.map((l) => l.branch))
    for (const entry of args.prs ?? []) if (!known.has(entry.branch)) throw new Error(`${entry.branch} is not being published here (${[...known].join(", ")}).`)

    const activeLayers = p.layers.filter((l) => !l.merged)
    const active = activeLayers.map((l) => l.branch)
    // plan() refuses when the PRs cannot be listed, so this is a reliable "before".
    const before = stateOf(p.prs!, active)
    const warnings = p.warnings.length ? { warnings: p.warnings } : {}

    // The previewed commits leave the machine through this one pinned, leased push;
    // gh stack is only left to open and link PRs for branches already there.
    const pushed = await pushPinned(cwd, p.layers, context.signal)
    if (!pushed.ok)
      return JSON.stringify({ published: false, stoppedAt: "push", output: pushed.output, ...(await verify(cwd, p, before)), ...warnings }, null, 2)
    if (args.action === "push") {
      const metaResult = await applyMeta(cwd, p, new Map(activeLayers.filter((l) => before[l.branch]).map((l) => [l.branch, before[l.branch]!.number])))
      return JSON.stringify({ published: true, action: "push", ...(await verify(cwd, p, before)), ...metaResult, output: pushed.output, ...warnings }, null, 2)
    }

    // submit: open a PR for each layer that has none, then link a stack's PRs.
    // None of these steps pushes, so nothing but the pinned commits leaves.
    const errors: string[] = []
    // PRs open on GitHub's branches, which must hold the pinned commits (origin may be a local mirror).
    for (const l of activeLayers) {
      const read = await gh(["api", `repos/${p.repo}/branches/${l.branch.split("/").map(encodeURIComponent).join("/")}`, "--jq", ".commit.sha"], cwd)
      const onGitHub = read.ok ? read.stdout.trim() || null : null
      if (onGitHub !== l.local) errors.push(`GitHub's ${l.branch} is at ${onGitHub ?? "an unreadable commit"}, not the pinned ${l.local}; no PR was opened or linked.`)
    }
    if (errors.length) return JSON.stringify({ published: false, stoppedAt: "github", errors, ...(await verify(cwd, p, before)), ...warnings }, null, 2)
    const entries = new Map((args.prs ?? []).map((e) => [e.branch, e]))
    const numbers: string[] = []
    const prNumbers = new Map<string, number>()
    for (const [i, l] of activeLayers.entries()) {
      const entry = entries.get(l.branch)
      const existing = before[l.branch]
      if (existing) {
        numbers.push(String(existing.number))
        prNumbers.set(l.branch, existing.number)
        // Only a plain PR's base moves here; a stack's bases are gh stack link's.
        const newBase = p.mode === "plain" && p.retarget ? p.retarget.to : undefined
        if (newBase || (entry && (entry.title !== undefined || entry.body !== undefined))) {
          const edit = (bodyFile?: string) =>
            gh(
              [
                "pr",
                "edit",
                String(existing.number),
                "--repo",
                p.repo!,
                ...(newBase ? ["--base", newBase] : []),
                ...(entry?.title !== undefined ? ["--title", entry.title] : []),
                ...(bodyFile ? ["--body-file", bodyFile] : []),
              ],
              cwd,
            )
          const done = entry?.body !== undefined ? await withTempFile("opencode-pr-body", ".md", entry.body, edit) : await edit()
          if (!done.ok) errors.push(`#${existing.number} base/title/body update failed: ${output(done)}`)
        }
        continue
      }
      const first = l.commits.items[0]
      const title = entry?.title ?? (first ? first.slice(first.indexOf(" ") + 1) : "")
      if (!title) {
        errors.push(`${l.branch} has no commits of its own; no PR was opened for it or the layers above.`)
        break
      }
      const base = i === 0 ? p.trunk : activeLayers[i - 1].branch
      const create = (bodyFile: string) =>
        gh(
          ["pr", "create", "--repo", p.repo!, "--base", base, "--head", l.branch, "--title", title, "--body-file", bodyFile, ...(args.draft ? ["--draft"] : [])],
          cwd,
          context.signal,
        )
      const res = await withTempFile("opencode-pr-body", ".md", entry?.body ?? "", create)
      const number = res.ok ? res.stdout.match(/\/pull\/(\d+)/)?.[1] : undefined
      if (!number) {
        errors.push(`Opening the PR for ${l.branch} failed; the layers above were left without PRs: ${output(res)}`)
        break
      }
      numbers.push(number)
      prNumbers.set(l.branch, Number(number))
    }

    let linked: { ok: boolean; output: string } | null = null
    let stacksUnavailable = false
    if (p.mode === "stack" && !errors.length && numbers.length >= 2) {
      const res = await ghStack(["link", "--base", p.trunk, ...numbers], cwd, context.signal)
      linked = { ok: res.ok, output: output(res) }
      stacksUnavailable = !res.ok && UNAVAILABLE.test(`${res.stdout}\n${res.stderr}`)
      if (!res.ok && !stacksUnavailable) errors.push(`Linking the PRs into a stack failed: ${linked.output}`)
    }
    const metaResult = await applyMeta(cwd, p, prNumbers)
    const result = await verify(cwd, p, before)
    return JSON.stringify(
      {
        published: !errors.length && !stacksUnavailable,
        action: "submit",
        ...result,
        ...metaResult,
        ...(linked ? { link: linked } : {}),
        ...(stacksUnavailable
          ? {
              stacksUnavailable: true,
              next: "Stacks are unavailable for this repository: the PRs exist, each based on the layer below, but are not linked; tell the user, or close them and open one plain PR.",
            }
          : {}),
        ...(errors.length ? { errors } : {}),
        ...warnings,
      },
      null,
      2,
    )
  },
})

async function link(cwd: string, numbers: string[]) {
  if (numbers.length < 2) throw new Error("link needs two or more PR numbers, bottom-up.")
  for (const n of numbers) if (!/^\d+$/.test(n.trim())) throw new Error(`${n} is not a PR number; link takes numbers only (branches would be pushed unchecked).`)
  const { repo, refusals } = await originOf(cwd)
  if (refusals.length || !repo) throw new Error(refusals.map((r) => r.message).join(" "))
  // gh stack link takes no repository flag: gh's own target must be known to be origin's.
  const view = await ghJson(["repo", "view", "--json", "nameWithOwner,viewerPermission,defaultBranchRef"], cwd)
  if (!view) throw new Error("Could not read the repository gh targets; link refuses without it.")
  if (String(view.nameWithOwner).toLowerCase() !== repo.toLowerCase())
    throw new Error(`gh targets ${view.nameWithOwner} but origin is ${repo}; native stacks cannot span a fork and its upstream.`)
  if (!["WRITE", "MAINTAIN", "ADMIN"].includes(view.viewerPermission)) throw new Error(`You have ${view.viewerPermission ?? "no"} access to ${repo}.`)
  const defName: string = view.defaultBranchRef?.name ?? (await defaultName(cwd))
  const before = []
  for (const n of numbers) {
    const pr = await ghJson(["pr", "view", n.trim(), "--repo", repo, "--json", "number,state,baseRefName,headRefName,isCrossRepository,isDraft"], cwd)
    if (!pr) throw new Error(`Could not read PR #${n} in ${repo}.`)
    if (pr.state !== "OPEN") throw new Error(`PR #${n} is ${pr.state}; only open PRs are linked.`)
    if (pr.isCrossRepository) throw new Error(`PR #${n} comes from a fork; native stacks cannot include it.`)
    if (pr.headRefName === defName) throw new Error(`PR #${n} is from the default branch.`)
    before.push(pr)
  }
  const res = await ghStack(["link", "--base", defName, ...numbers.map((n) => n.trim())], cwd)
  const after = []
  for (const [i, n] of numbers.entries()) {
    const pr = await ghJson(["pr", "view", n.trim(), "--repo", repo, "--json", "number,baseRefName,isDraft,url"], cwd)
    const expected = i === 0 ? defName : before[i - 1].headRefName
    after.push({
      number: Number(n),
      baseBefore: before[i].baseRefName,
      base: pr?.baseRefName ?? null,
      draft: pr?.isDraft ?? null,
      url: pr?.url ?? null,
      ...(pr && pr.baseRefName !== expected ? { baseMismatch: `expected ${expected}` } : {}),
    })
  }
  const membership = await ghApi(`repos/${repo}/pulls/${numbers[0].trim()}`, ".stack", cwd)
  return {
    linked: res.ok,
    trunk: defName,
    prs: after,
    nativeStack: membership?.number ? { stack: membership.number, size: membership.size ?? null } : null,
    output: output(res),
  }
}
