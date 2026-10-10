import { existsSync, statSync } from "fs"
import { tool } from "../define"
import { exec, runGit, tryGit, withTempFile } from "../exec"
import { commitlint, lintMessage, type Violation } from "./lint"
import { checkRewrite, currentBranch, needsForcePush } from "./rewrite"
import { dedupe, scanDiff, scanSecrets } from "./secrets"

const lines = (text: string) => text.split("\n").map((l) => l.trim()).filter(Boolean)
const tail = (text: string, n = 40) => text.trim().split("\n").slice(-n).join("\n")
const HOOKS = ["pre-commit", "prepare-commit-msg", "commit-msg", "post-commit"]

/** The commit hooks that would run here. */
async function activeHooks(cwd: string): Promise<string[]> {
  const found: string[] = []
  for (const name of HOOKS) {
    const path = await tryGit(["rev-parse", "--path-format=absolute", "--git-path", `hooks/${name}`], cwd)
    if (path.ok && existsSync(path.stdout.trim()) && (statSync(path.stdout.trim()).mode & 0o111) !== 0) found.push(name)
  }
  return found
}

export const commit = tool({
  description:
    "Commit what is staged, with the message checked and committed byte for byte. Lints the message (built-in rules plus the repository's commitlint, as git_commit_lint does), scans the staged diff for secrets, then runs `git commit -F` on that same message file, so hooks see exactly the linted text. Commits only the index: no -a, no --no-verify, and nothing staged is refused (except an amend that rewords). amend replaces HEAD; fixup commits `fixup! <subject>` of an earlier commit for git_rebase to fold in. Both follow git_amend_check's rule: a task branch's own commits, even pushed (then needsForcePush), never the default branch, a commit already on it or held by another remote branch, or a branch GitHub protects. Stops before committing on a refused rewrite, a lint error or a secret finding; reports a hook rejection with its output, and files a hook changed or left modified. Returns the new commit's sha, subject and stat, and what remains uncommitted.",
  args: {
    message: tool.schema
      .string()
      .optional()
      .describe("The full commit message: subject, blank line, body wrapped as it should land. Optional with amend (keeps HEAD's message) and ignored with fixup."),
    amend: tool.schema.boolean().optional().describe("Replace HEAD with it plus the staged changes (and `message`, when given)."),
    fixup: tool.schema.string().optional().describe("Commit the staged changes as a fixup of this earlier commit of the branch (sha or ref)."),
    acceptSecretFindings: tool.schema
      .boolean()
      .optional()
      .describe("Commit despite secret findings. Only after judging every finding a false positive (fixture, integrity hash)."),
    allowTrailers: tool.schema.boolean().optional().describe("Permit attribution/generated trailers (default false)."),
    subjectMax: tool.schema.number().optional().describe("Hard subject length limit (default 72)."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const amend = args.amend ?? false
    const fixup = args.fixup?.trim()
    if (amend && fixup) throw new Error("Pass amend or fixup, not both.")
    const nothingStaged = (await tryGit(["diff", "--cached", "--quiet"], cwd)).ok
    if (nothingStaged && !(amend && args.message?.trim()))
      throw new Error(
        amend
          ? "Nothing is staged; an amend needs staged changes or a new message."
          : "Nothing is staged. Stage the changes for this commit first (git add <path>, or git_stage_hunks).",
      )

    let target: string | null = null
    let rewriteWarnings: string[] = []
    if (amend || fixup) {
      const resolved = await tryGit(["rev-parse", "--verify", "--quiet", `${amend ? "HEAD" : fixup}^{commit}`], cwd)
      if (!resolved.ok) throw new Error(`Unknown commit: ${amend ? "HEAD" : fixup}.`)
      target = resolved.stdout.trim()
      if (fixup && !(await tryGit(["merge-base", "--is-ancestor", target, "HEAD"], cwd)).ok)
        throw new Error(`${fixup} is not a commit of this branch; a fixup can only target one.`)
      const check = await checkRewrite(cwd, target)
      if (!check.allowed)
        return JSON.stringify({ committed: false, stoppedAt: "rewrite", refusals: check.refusals, warnings: check.warnings }, null, 2)
      rewriteWarnings = check.warnings
    }

    let raw: string
    if (fixup) raw = `fixup! ${(await runGit(["log", "-1", "--format=%s", target!], cwd)).trim()}\n`
    else if (args.message?.trim()) raw = args.message
    else if (amend) raw = await runGit(["log", "-1", "--format=%B", "HEAD"], cwd)
    else throw new Error("The message is empty.")

    // Normalize once the way git would (trailing blanks, blank-line runs), then
    // commit verbatim: what was linted is what lands, whatever commit.cleanup says.
    const normalized = await exec(["git", "stripspace"], { cwd, stdin: raw.replace(/\r\n/g, "\n") })
    const message = normalized.ok ? normalized.stdout : raw.replace(/\r\n/g, "\n").replace(/\s+$/, "") + "\n"
    if (!message.trim()) throw new Error("The message is empty.")
    return withTempFile("opencode-commit", ".txt", message, async (file) => {
      // A generated fixup subject is git's, not the author's; only the repository's commitlint judges it.
      const violations: Violation[] = fixup ? [] : lintMessage(message.trimEnd(), args.allowTrailers ?? false, args.subjectMax ?? 72)
      const checked = await commitlint(file, cwd)
      violations.push(...checked.violations)
      const errors = violations.filter((v) => v.severity === "error")
      const warnings = violations.filter((v) => v.severity === "warning")
      const lint = { commitlint: checked.status, hook: checked.hook, errors, warnings }
      if (errors.length) return JSON.stringify({ committed: false, stoppedAt: "lint", ...lint }, null, 2)

      // Snapshot the index before scanning it, so content a hook stages later is told apart.
      const stagedTree = (await runGit(["write-tree"], cwd)).trim()
      const scan = await scanSecrets({ target: "staged" }, cwd)
      if (scan.findings.length && !args.acceptSecretFindings)
        return JSON.stringify({ committed: false, stoppedAt: "secrets", gitleaksRan: scan.gitleaksRan, findings: scan.findings, ...lint }, null, 2)

      const unstagedBefore = new Set(lines(await runGit(["diff", "--name-only"], cwd)))
      const res = await exec(["git", "commit", "--cleanup=verbatim", ...(amend ? ["--amend"] : []), "-F", file], { cwd, signal: context.signal })
      const unstagedAfter = lines(await runGit(["diff", "--name-only"], cwd))
      const leftModified = unstagedAfter.filter((f) => !unstagedBefore.has(f))

      if (!res.ok) {
        const hooks = await activeHooks(cwd)
        return JSON.stringify(
          {
            committed: false,
            // Not every failure is a hook's: identity, signing, a lock or unmerged paths fail here too.
            stoppedAt: res.killed ? "stopped" : hooks.length ? "hook" : "commit",
            hooks,
            exitCode: res.code,
            output: tail(`${res.stdout}\n${res.stderr}`),
            leftModified,
            ...lint,
          },
          null,
          2,
        )
      }

      const sha = (await runGit(["rev-parse", "HEAD"], cwd)).trim()
      const changedByHook = lines(await runGit(["diff", "--name-only", stagedTree, "HEAD^{tree}"], cwd))
      // A hook that staged content bypassed the scan above; scan what it added.
      const hookFindings = changedByHook.length
        ? dedupe(scanDiff(await runGit(["diff", "--no-color", "--unified=0", stagedTree, "HEAD^{tree}"], cwd)))
        : []
      const landed = await runGit(["log", "-1", "--format=%B"], cwd)
      const status = await runGit(["status", "--porcelain=v1"], cwd)
      const remaining = { staged: 0, unstaged: 0, untracked: 0 }
      for (const l of status.split("\n").filter(Boolean)) {
        if (l.startsWith("??")) remaining.untracked++
        else {
          if (l[0] !== " ") remaining.staged++
          if (l[1] !== " ") remaining.unstaged++
        }
      }
      return JSON.stringify(
        {
          committed: true,
          sha,
          subject: landed.split("\n")[0],
          messageMatches: landed.trimEnd() === message.trimEnd(),
          stat: (await runGit(["show", "--stat", "--format=", "HEAD"], cwd)).trim(),
          ...(amend ? { amended: target, needsForcePush: await needsForcePush(cwd, (await currentBranch(cwd))!) } : {}),
          ...(fixup ? { fixupOf: target, next: "Fold it in with git_rebase (action: start, keepBase: true)." } : {}),
          ...(rewriteWarnings.length ? { rewriteWarnings } : {}),
          changedByHook,
          hookFindings,
          leftModified,
          remaining,
          ...lint,
        },
        null,
        2,
      )
    })
  },
})
