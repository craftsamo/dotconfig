import { tool } from "../define"
import { exec } from "../exec"
import { assertWritable, getIssue, parseIssueRef, resolveRepo, sameName, type IssueBrief, type RepoContext } from "../github"

/**
 * Hierarchy (parent / sub-issues) and dependencies (blocked by / blocking),
 * over `gh issue edit`. GitHub refuses a duplicate link, so every add and
 * remove is checked against the issue's current relations first and the
 * ones already in the wanted state are reported as `unchanged`; a duplicate
 * past the read's page limit is folded into `unchanged` too. A related issue
 * in another repository is a write there as well: that repository is
 * resolved and checked, and reported under `otherRepos`.
 */

export type RelateInput = {
  parent?: string
  removeParent?: boolean
  addSubIssues?: string[]
  removeSubIssues?: string[]
  addBlockedBy?: string[]
  removeBlockedBy?: string[]
  addBlocking?: string[]
  removeBlocking?: string[]
}

type Diff = { added: string[]; removed: string[]; unchanged: string[] }

export type RelateResult = {
  parent?: { set: string } | { removed: true } | { unchanged: string | null }
  subIssues?: Diff
  blockedBy?: Diff
  blocking?: Diff
  otherRepos: { repo: string; foreign: boolean }[]
}

const url = (repo: string, n: number) => `https://github.com/${repo}/issues/${n}`
const key = (repo: string, n: number) => `${repo.toLowerCase()}#${n}`
const keyOf = (b: IssueBrief) => key(b.repo, b.number)

type Target = { key: string; url: string; repo: string }

function normalize(refs: string[] | undefined, repo: string): Target[] {
  return (refs ?? []).map((r) => {
    const ref = parseIssueRef(r, repo)
    const rp = ref.repo ?? repo
    return { key: key(rp, ref.number), url: url(rp, ref.number), repo: rp }
  })
}

const ALREADY = /already|duplicate|not (a|an) (sub-issue|blocker)|does not have/i

async function edit(issue: string, repo: string, flag: string, target: Target, cwd?: string): Promise<"done" | "unchanged"> {
  const res = await exec(["gh", "issue", "edit", issue, flag, target.url, "--repo", repo], { cwd })
  if (res.ok) return "done"
  if (ALREADY.test(res.stderr + res.stdout)) return "unchanged"
  throw new Error(`gh issue edit ${issue} ${flag} ${target.url} failed (exit ${res.code}):\n${res.stderr.trim() || res.stdout.trim()}`)
}

async function diff(issue: string, repo: string, current: IssueBrief[], add: string[] | undefined, remove: string[] | undefined, flags: [string, string], cwd?: string): Promise<Diff> {
  const have = new Set(current.map(keyOf))
  const out: Diff = { added: [], removed: [], unchanged: [] }
  for (const t of normalize(add, repo)) {
    if (have.has(t.key)) out.unchanged.push(t.key)
    else (await edit(issue, repo, flags[0], t, cwd)) === "done" ? out.added.push(t.key) : out.unchanged.push(t.key)
  }
  for (const t of normalize(remove, repo)) {
    if (!have.has(t.key)) out.unchanged.push(t.key)
    else (await edit(issue, repo, flags[1], t, cwd)) === "done" ? out.removed.push(t.key) : out.unchanged.push(t.key)
  }
  return out
}

export async function relateIssue(repo: RepoContext, number: number, input: RelateInput, cwd?: string): Promise<RelateResult> {
  const r = repo.nameWithOwner
  const n = String(number)
  if (input.parent !== undefined && input.removeParent) throw new Error("Pass parent or removeParent, not both.")

  // Every other repository a relation touches is written to as well.
  const others = new Map<string, { repo: string; foreign: boolean }>()
  const refs = [input.parent, ...(input.addSubIssues ?? []), ...(input.removeSubIssues ?? []), ...(input.addBlockedBy ?? []), ...(input.removeBlockedBy ?? []), ...(input.addBlocking ?? []), ...(input.removeBlocking ?? [])]
  for (const t of normalize(refs.filter((x): x is string => typeof x === "string"), r)) {
    if (sameName(t.repo, r) || others.has(t.repo.toLowerCase())) continue
    const ctx = await resolveRepo(t.repo, cwd)
    assertWritable(ctx)
    others.set(t.repo.toLowerCase(), { repo: ctx.nameWithOwner, foreign: ctx.foreign })
  }

  const current = await getIssue(r, number, { comments: 0, cwd })
  const needsDeps = Boolean(input.addBlockedBy?.length || input.removeBlockedBy?.length || input.addBlocking?.length || input.removeBlocking?.length)
  if (needsDeps && current.dependenciesError) throw new Error(`Could not read the issue's dependencies: ${current.dependenciesError}`)
  const out: RelateResult = { otherRepos: [...others.values()] }

  if (input.parent !== undefined) {
    const [want] = normalize([input.parent], r)
    if (current.parent && keyOf(current.parent) === want.key) out.parent = { unchanged: want.key }
    else {
      await edit(n, r, "--parent", want, cwd)
      out.parent = { set: want.key }
    }
  } else if (input.removeParent) {
    if (!current.parent) out.parent = { unchanged: null }
    else {
      const res = await exec(["gh", "issue", "edit", n, "--remove-parent", "--repo", r], { cwd })
      if (!res.ok) throw new Error(`gh issue edit ${n} --remove-parent failed:\n${res.stderr.trim()}`)
      out.parent = { removed: true }
    }
  }
  if (input.addSubIssues?.length || input.removeSubIssues?.length) {
    out.subIssues = await diff(n, r, current.subIssues, input.addSubIssues, input.removeSubIssues, ["--add-sub-issue", "--remove-sub-issue"], cwd)
  }
  if (input.addBlockedBy?.length || input.removeBlockedBy?.length) {
    out.blockedBy = await diff(n, r, current.blockedBy, input.addBlockedBy, input.removeBlockedBy, ["--add-blocked-by", "--remove-blocked-by"], cwd)
  }
  if (input.addBlocking?.length || input.removeBlocking?.length) {
    out.blocking = await diff(n, r, current.blocking, input.addBlocking, input.removeBlocking, ["--add-blocking", "--remove-blocking"], cwd)
  }
  return out
}

export const relate = tool({
  description:
    "Set how an issue relates to others: its parent (set or remove), sub-issues added or removed (100 per parent, 8 levels deep), and blocked-by / blocking dependencies added or removed. Idempotent: relations already in the wanted state are reported as unchanged instead of re-sent (GitHub refuses duplicates). Issues may live in other repositories (owner/repo#N or URL); each such repository needs write permission too and is listed in the result. Needs write permission on the issue's repository.",
  args: {
    issue: tool.schema.string().describe("The issue whose relations change: number, #N, owner/repo#N or URL."),
    repo: tool.schema.string().optional(),
    parent: tool.schema.string().optional().describe("Parent issue to set."),
    removeParent: tool.schema.boolean().optional(),
    addSubIssues: tool.schema.array(tool.schema.string()).optional(),
    removeSubIssues: tool.schema.array(tool.schema.string()).optional(),
    addBlockedBy: tool.schema.array(tool.schema.string()).optional().describe("Issues that must finish before this one."),
    removeBlockedBy: tool.schema.array(tool.schema.string()).optional(),
    addBlocking: tool.schema.array(tool.schema.string()).optional().describe("Issues this one holds up."),
    removeBlocking: tool.schema.array(tool.schema.string()).optional(),
  },
  async execute(args, context) {
    const ref = parseIssueRef(args.issue)
    const repo = await resolveRepo(ref.repo ?? args.repo, context.worktree)
    assertWritable(repo)
    const { issue: _i, repo: _r, ...input } = args
    const result = await relateIssue(repo, ref.number, input, context.worktree)
    return JSON.stringify({ ok: true, repo: repo.nameWithOwner, foreign: repo.foreign, issue: ref.number, ...result }, null, 2)
  },
})
