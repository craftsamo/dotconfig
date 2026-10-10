import { mkdtempSync, realpathSync, rmSync } from "fs"
import { tmpdir } from "os"
import { dirname, join } from "path"
import { tool } from "../define"
import { exec, runGit, tryGit } from "../exec"
import { defaultRef } from "./state"

const COMMITS_MAX = 30
const TAIL_LINES = 40
// The scratch checkout must not run the repository's checkout hooks.
const NO_HOOKS = ["-c", "core.hooksPath=/dev/null"]

const tail = (text: string) => text.trim().split("\n").slice(-TAIL_LINES).join("\n")

export const verify_commits = tool({
  description:
    "Check that every commit of a branch passes on its own: checks each commit of `base..HEAD` out, oldest first, in a throwaway detached worktree (checkout hooks off) and runs `command` there with `sh -c`, after an optional one-time `setup` such as installing dependencies. Stops at the first failing commit unless keepGoing. The worktree under TMPDIR is removed afterwards; the session's own checkout, index and stash are untouched. Returns per-commit pass/fail with duration and the output tail of failures. Runs arbitrary commands, so every call asks for approval.",
  args: {
    command: tool.schema.string().describe('The check to run at each commit, e.g. "bun test lib" or "pnpm -s typecheck".'),
    base: tool.schema.string().optional().describe("Commits after this ref are checked. Default: the merge-base with the remote default branch."),
    setup: tool.schema.string().optional().describe('Run once in the worktree before the first check, e.g. "bun install --frozen-lockfile".'),
    cwd: tool.schema.string().optional().describe("Directory inside the repository to run setup and command in (relative path)."),
    keepGoing: tool.schema.boolean().optional().describe("Check every commit even after a failure (default false)."),
    timeoutSec: tool.schema.number().optional().describe("Per-commit limit for the command, and for setup (default 600)."),
  },
  async execute(args, context) {
    const repo = context.worktree
    let base = args.base?.trim()
    if (!base) {
      const def = await defaultRef(repo)
      if (!def) throw new Error("No remote default branch is known here; pass `base`.")
      base = (await runGit(["merge-base", "HEAD", def], repo)).trim()
    }
    const commits = (await runGit(["rev-list", "--reverse", `${base}..HEAD`], repo)).split("\n").filter(Boolean)
    if (!commits.length) throw new Error(`No commits between ${base} and HEAD.`)
    if (commits.length > COMMITS_MAX) throw new Error(`${commits.length} commits after ${base}; check at most ${COMMITS_MAX} at once (pass a nearer base).`)
    const rel = args.cwd?.trim() || "."
    if (rel.startsWith("/") || rel.split("/").includes("..")) throw new Error("cwd must be a relative path inside the repository.")
    const timeoutMs = Math.max(args.timeoutSec ?? 600, 1) * 1000

    const dir = join(realpathSync(mkdtempSync(join(process.env.TMPDIR ?? tmpdir(), "opencode-verify-"))), "tree")
    await runGit([...NO_HOOKS, "worktree", "add", "--detach", "--quiet", dir, commits[0]], repo)
    const results: { sha: string; subject: string; ok: boolean; seconds: number; exitCode?: number; killed?: string; output?: string }[] = []
    let setupResult: { ok: boolean; output?: string } | null = null
    try {
      const work = join(dir, rel)
      if (args.setup) {
        const res = await exec(["sh", "-c", args.setup], { cwd: work, timeoutMs, signal: context.signal })
        setupResult = res.ok ? { ok: true } : { ok: false, output: tail(`${res.stdout}\n${res.stderr}`) }
      }
      if (!setupResult || setupResult.ok) {
        for (const sha of commits) {
          if (context.signal?.aborted) break
          await runGit([...NO_HOOKS, "checkout", "--quiet", "--detach", sha], dir)
          const subject = (await runGit(["log", "-1", "--format=%s", sha], dir)).trim()
          const started = Date.now()
          const res = await exec(["sh", "-c", args.command], { cwd: work, timeoutMs, signal: context.signal })
          const entry: (typeof results)[number] = { sha: sha.slice(0, 12), subject, ok: res.ok, seconds: Math.round((Date.now() - started) / 100) / 10 }
          if (!res.ok) Object.assign(entry, { exitCode: res.code, killed: res.killed, output: tail(`${res.stdout}\n${res.stderr}`) })
          results.push(entry)
          if (!res.ok && !args.keepGoing) break
        }
      }
    } finally {
      await tryGit(["worktree", "remove", "--force", dir], repo)
      rmSync(dirname(dir), { recursive: true, force: true })
      await tryGit(["worktree", "prune"], repo)
    }
    const failed = results.filter((r) => !r.ok)
    return JSON.stringify(
      {
        base,
        command: args.command,
        total: commits.length,
        checked: results.length,
        pass: Boolean(setupResult?.ok ?? true) && !failed.length && results.length === commits.length,
        setup: setupResult,
        firstFailure: failed[0]?.sha ?? null,
        results,
      },
      null,
      2,
    )
  },
})
