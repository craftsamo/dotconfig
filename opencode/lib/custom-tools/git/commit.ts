import { tool } from "../define"
import { exec, runGit, tryGit, withTempFile } from "../exec"
import { commitlint, lintMessage, type Violation } from "./lint"
import { scanSecrets } from "./secrets"

const lines = (text: string) => text.split("\n").map((l) => l.trim()).filter(Boolean)
const tail = (text: string, n = 40) => text.trim().split("\n").slice(-n).join("\n")

export const commit = tool({
  description:
    "Commit what is staged, with the message checked and committed byte for byte. Lints the message (built-in rules plus the repository's commitlint, as git_commit_lint does), scans the staged diff for secrets, then runs `git commit -F` on that same message file, so hooks see exactly the linted text. Commits only the index: no -a, no --amend, no --no-verify, and nothing staged is refused. Stops before committing on a lint error or a secret finding; reports a hook rejection with its output, and files a hook changed or left modified. Returns the new commit's sha, subject and stat, and what remains uncommitted.",
  args: {
    message: tool.schema.string().describe("The full commit message: subject, blank line, body wrapped as it should land."),
    acceptSecretFindings: tool.schema
      .boolean()
      .optional()
      .describe("Commit despite secret findings. Only after judging every finding a false positive (fixture, integrity hash)."),
    allowTrailers: tool.schema.boolean().optional().describe("Permit attribution/generated trailers (default false)."),
    subjectMax: tool.schema.number().optional().describe("Hard subject length limit (default 72)."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    if ((await tryGit(["diff", "--cached", "--quiet"], cwd)).ok)
      throw new Error("Nothing is staged. Stage the changes for this commit first (git add <path>, or git_stage_hunks).")

    const message = args.message.replace(/\r\n/g, "\n").replace(/\s+$/, "") + "\n"
    return withTempFile("opencode-commit", ".txt", message, async (file) => {
      const violations: Violation[] = lintMessage(message.trimEnd(), args.allowTrailers ?? false, args.subjectMax ?? 72)
      const checked = await commitlint(file, cwd)
      violations.push(...checked.violations)
      const errors = violations.filter((v) => v.severity === "error")
      const warnings = violations.filter((v) => v.severity === "warning")
      const lint = { commitlint: checked.status, hook: checked.hook, errors, warnings }
      if (errors.length) return JSON.stringify({ committed: false, stoppedAt: "lint", ...lint }, null, 2)

      const scan = await scanSecrets({ target: "staged" }, cwd)
      if (scan.findings.length && !args.acceptSecretFindings)
        return JSON.stringify({ committed: false, stoppedAt: "secrets", gitleaksRan: scan.gitleaksRan, findings: scan.findings, ...lint }, null, 2)

      const stagedTree = (await runGit(["write-tree"], cwd)).trim()
      const unstagedBefore = new Set(lines(await runGit(["diff", "--name-only"], cwd)))
      const res = await exec(["git", "commit", "-F", file], { cwd })
      const unstagedAfter = lines(await runGit(["diff", "--name-only"], cwd))
      const leftModified = unstagedAfter.filter((f) => !unstagedBefore.has(f))

      if (!res.ok)
        return JSON.stringify(
          { committed: false, stoppedAt: "hook", exitCode: res.code, output: tail(`${res.stdout}\n${res.stderr}`), leftModified, ...lint },
          null,
          2,
        )

      const sha = (await runGit(["rev-parse", "HEAD"], cwd)).trim()
      const changedByHook = lines(await runGit(["diff", "--name-only", stagedTree, "HEAD^{tree}"], cwd))
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
          changedByHook,
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
