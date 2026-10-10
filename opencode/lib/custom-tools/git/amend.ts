import { tool } from "../define"
import { runGit, tryGit } from "../exec"

export const amend_check = tool({
  description:
    "Classify whether a commit can be safely amended or fixed up in place (local and unpushed) or must be corrected with a new linked-fix commit (already published). Checks whether the commit is HEAD, is in the branch's upstream, and is on any remote branch. Read-only; never rewrites history. Returns a recommendation of amend / fixup / linked-fix.",
  args: {
    sha: tool.schema.string().optional().describe("Commit to check. Defaults to HEAD."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const ref = args.sha?.trim() || "HEAD"
    const sha = (await runGit(["rev-parse", ref], cwd)).trim()
    const head = (await runGit(["rev-parse", "HEAD"], cwd)).trim()
    const isHead = sha === head

    let hasUpstream = false
    let inUpstream = false
    const up = await tryGit(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd)
    if (up.ok) {
      hasUpstream = true
      inUpstream = (await tryGit(["merge-base", "--is-ancestor", sha, "@{u}"], cwd)).ok
    }

    const rb = await tryGit(["branch", "-r", "--contains", sha], cwd)
    const remoteBranches = rb.ok ? rb.stdout.split("\n").map((s) => s.trim()).filter(Boolean) : []
    const pushed = inUpstream || remoteBranches.length > 0

    let recommendation: "amend" | "fixup" | "linked-fix"
    let reason: string
    if (pushed) {
      recommendation = "linked-fix"
      reason = "Commit is already published; do not rewrite it. Make a new commit that links it."
    } else if (isHead) {
      recommendation = "amend"
      reason = "Commit is local, unpushed, and is HEAD; `git commit --amend` is safe."
    } else {
      recommendation = "fixup"
      reason = "Commit is local and unpushed but not HEAD; use `git commit --fixup` + `git rebase --autosquash`."
    }

    return JSON.stringify({ sha, ref, isHead, hasUpstream, inUpstream, remoteBranches, pushed, recommendation, reason }, null, 2)
  },
})
