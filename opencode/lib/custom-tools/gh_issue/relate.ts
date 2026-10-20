import { tool } from "../define"
import { runGh } from "../exec"
import { assertWritable, getIssue, parseIssueRef, resolveRepo, withRepo, type IssueBrief, type RepoContext } from "../github"

/**
 * Hierarchy (parent / sub-issues) and dependencies (blocked by / blocking),
 * over `gh issue edit`. GitHub refuses a duplicate link, so every add and
 * remove is checked against the issue's current relations first and the
 * ones already in the wanted state are reported as `unchanged`.
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

export type RelateResult = {
  parent?: { set: string } | { removed: true } | { unchanged: string | null }
  subIssues?: { added: string[]; removed: string[]; unchanged: string[] }
  blockedBy?: { added: string[]; removed: string[]; unchanged: string[] }
  blocking?: { added: string[]; removed: string[]; unchanged: string[] }
}

const url = (repo: string, n: number) => `https://github.com/${repo}/issues/${n}`
const key = (b: IssueBrief) => `${b.repo}#${b.number}`

function normalize(refs: string[] | undefined, repo: string): { key: string; url: string }[] {
  return (refs ?? []).map((r) => {
    const ref = parseIssueRef(r, repo)
    const rp = ref.repo ?? repo
    return { key: `${rp}#${ref.number}`, url: url(rp, ref.number) }
  })
}

async function diff(
  issue: string,
  repo: string,
  current: IssueBrief[],
  add: string[] | undefined,
  remove: string[] | undefined,
  flags: [string, string],
  cwd?: string,
): Promise<{ added: string[]; removed: string[]; unchanged: string[] }> {
  const have = new Set(current.map(key))
  const unchanged: string[] = []
  const added: string[] = []
  const removed: string[] = []
  for (const t of normalize(add, repo)) {
    if (have.has(t.key)) unchanged.push(t.key)
    else {
      await runGh(withRepo(["issue", "edit", issue, flags[0], t.url], repo), cwd)
      added.push(t.key)
    }
  }
  for (const t of normalize(remove, repo)) {
    if (!have.has(t.key)) unchanged.push(t.key)
    else {
      await runGh(withRepo(["issue", "edit", issue, flags[1], t.url], repo), cwd)
      removed.push(t.key)
    }
  }
  return { added, removed, unchanged }
}

export async function relateIssue(repo: RepoContext, number: number, input: RelateInput, cwd?: string): Promise<RelateResult> {
  const r = repo.nameWithOwner
  const n = String(number)
  const current = await getIssue(r, number, { comments: 0, cwd })
  const out: RelateResult = {}

  if (input.parent !== undefined && input.removeParent) throw new Error("Pass parent or removeParent, not both.")
  if (input.parent !== undefined) {
    const [want] = normalize([input.parent], r)
    if (current.parent && key(current.parent) === want.key) out.parent = { unchanged: want.key }
    else {
      await runGh(withRepo(["issue", "edit", n, "--parent", want.url], r), cwd)
      out.parent = { set: want.key }
    }
  } else if (input.removeParent) {
    if (!current.parent) out.parent = { unchanged: null }
    else {
      await runGh(withRepo(["issue", "edit", n, "--remove-parent"], r), cwd)
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
    "Set how an issue relates to others: its parent (set or remove), sub-issues added or removed (100 per parent, 8 levels deep), and blocked-by / blocking dependencies added or removed. Idempotent: relations already in the wanted state are reported as unchanged instead of re-sent (GitHub refuses duplicates). Issues may live in other repositories (owner/repo#N or URL). Needs write permission on the issue's repository.",
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
