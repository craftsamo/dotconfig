import { tool } from "../define"
import { exec, runGh } from "../exec"
import { assertWritable, getIssue, parseIssueRef, resolveRepo } from "../github"

/**
 * Linked development branches over `gh issue develop`. A PR from such a
 * branch enters the issue's closing references without a keyword, so the
 * first merge closes the issue; the description says when that is wanted.
 */

async function remoteBranchExists(branch: string, repo: string, cwd?: string): Promise<boolean> {
  const res = await exec(["gh", "api", `repos/${repo}/branches/${encodeURIComponent(branch)}`], { cwd })
  return res.ok
}

function parseBranchFromOutput(out: string): string | null {
  // gh prints the new branch as a plain tree URL: host/owner/repo/tree/<branch>.
  const m = out.match(/\/tree\/(.+?)(\s|$)/)
  return m ? m[1] : null
}

export const develop = tool({
  description:
    "Create a development branch linked to an issue (shown in its Development panel), or reuse the linked branch that already exists. A PR opened from the branch closes the issue on merge EVEN WITHOUT a closing keyword, so use it only when the first merge should close the issue (a single-PR task); a multi-layer stack takes plain branches. Verifies `base` exists on the remote (gh otherwise falls back to the default branch silently). Needs write permission.",
  args: {
    issue: tool.schema.string().describe("Issue number, #N, owner/repo#N or URL."),
    repo: tool.schema.string().optional(),
    branch: tool.schema.string().optional().describe("Branch name; gh derives one from the title when omitted."),
    base: tool.schema.string().optional().describe("Remote branch to start from (default: the repository's default branch)."),
    checkout: tool.schema.boolean().optional().describe("Check the new branch out locally (only when one is created)."),
    branchRepo: tool.schema.string().optional().describe("owner/repo to create the branch in, when not the issue's repository."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const ref = parseIssueRef(args.issue)
    const repo = await resolveRepo(ref.repo ?? args.repo, cwd)
    assertWritable(repo)
    const r = repo.nameWithOwner
    const existing = (await getIssue(r, ref.number, { comments: 0, cwd })).linkedBranches
    if (existing.length) {
      return JSON.stringify({
        ok: true,
        created: false,
        repo: r,
        issue: ref.number,
        branch: existing[0],
        linkedBranches: existing,
        note: args.checkout ? "branch already linked; not recreated and not checked out" : "branch already linked; not recreated",
      })
    }
    if (args.base && !(await remoteBranchExists(args.base, args.branchRepo ?? r, cwd))) {
      throw new Error(`Base branch "${args.base}" not found on ${args.branchRepo ?? r}; gh issue develop would silently fall back to the default branch.`)
    }
    const argv = ["issue", "develop", String(ref.number), "--repo", r]
    if (args.branch) argv.push("--name", args.branch)
    if (args.base) argv.push("--base", args.base)
    if (args.checkout) argv.push("--checkout")
    if (args.branchRepo) argv.push("--branch-repo", args.branchRepo)
    const out = await runGh(argv, cwd)
    const branch = args.branch ?? parseBranchFromOutput(out)
    if (!branch) throw new Error(`gh issue develop succeeded but printed no branch:\n${out}`)
    return JSON.stringify({ ok: true, created: true, repo: r, foreign: repo.foreign, issue: ref.number, branch, base: args.base ?? null, linkedBranches: [branch] })
  },
})
