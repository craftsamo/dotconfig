import { tool } from "../define"
import { runGit, tryGit } from "../exec"
import { checkRewrite } from "./rewrite"

export const amend_check = tool({
  description:
    "Classify how to correct a commit: amend (it is HEAD), fixup (an earlier commit of this branch, folded in by git_rebase), or linked-fix (a new commit that links it). A task branch's own commits may be rewritten even once pushed; then `needsForcePush` is true. Rewriting is refused, and linked-fix recommended, on the default branch, for a commit already on the default branch or held by another remote branch (layers above it in the same native stack excepted), or when GitHub protects the pushed branch against force pushes. Read-only; never rewrites history.",
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

    const onBranch = isHead || (await tryGit(["merge-base", "--is-ancestor", sha, "HEAD"], cwd)).ok
    const check = onBranch ? await checkRewrite(cwd, sha) : null

    let recommendation: "amend" | "fixup" | "linked-fix"
    let reason: string
    if (!check) {
      recommendation = "linked-fix"
      reason = "The commit is not on this branch; make a new commit that links it."
    } else if (!check.allowed) {
      recommendation = "linked-fix"
      reason = check.refusals.map((r) => r.message).join(" ")
    } else if (isHead) {
      recommendation = "amend"
      reason = check.needsForcePush
        ? "HEAD of a task branch; amend it with git_commit (amend: true), then push with `git push --force-with-lease origin HEAD:refs/heads/<branch>`."
        : "HEAD and not pushed; amend it with git_commit (amend: true)."
    } else {
      recommendation = "fixup"
      reason = `An earlier commit of this branch; commit the fix with git_commit (fixup: sha), then fold it in with git_rebase (keepBase: true)${check.needsForcePush ? " and push with `git push --force-with-lease origin HEAD:refs/heads/<branch>`" : ""}.`
    }

    return JSON.stringify(
      {
        sha,
        ref,
        isHead,
        hasUpstream,
        inUpstream,
        remoteBranches,
        pushed,
        recommendation,
        reason,
        needsForcePush: check?.needsForcePush ?? false,
        refusals: check?.refusals ?? [],
        warnings: check?.warnings ?? [],
      },
      null,
      2,
    )
  },
})
