import { chmodSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from "fs"
import { tmpdir } from "os"
import { dirname, join } from "path"

/** Fixed identity and no user/system config, so fixtures commit the same way on every machine. */
const GIT_ENV = {
  GIT_CONFIG_NOSYSTEM: "1",
  GIT_AUTHOR_NAME: "Test",
  GIT_AUTHOR_EMAIL: "test@example.com",
  GIT_COMMITTER_NAME: "Test",
  GIT_COMMITTER_EMAIL: "test@example.com",
}

export type Fixture = {
  root: string
  dir: string
  git(...args: string[]): string
  write(path: string, content: string): void
  commit(message: string, files?: Record<string, string>): string
  cleanup(): void
}

/** A throwaway repository on `main` with no commits yet. */
export function fixture(prefix = "custom-tools-git-"): Fixture {
  const root = realpathSync(mkdtempSync(join(tmpdir(), prefix)))
  const dir = join(root, "repo")
  mkdirSync(dir)
  const globalConfig = join(root, "gitconfig")
  writeFileSync(globalConfig, "[commit]\n\tgpgsign = false\n[init]\n\tdefaultBranch = main\n")
  const env = { ...process.env, ...GIT_ENV, GIT_CONFIG_GLOBAL: globalConfig }

  const git = (...args: string[]) => {
    const res = Bun.spawnSync(["git", ...args], { cwd: dir, env })
    if (res.exitCode !== 0) throw new Error(`git ${args.join(" ")}: ${res.stderr.toString()}`)
    return res.stdout.toString()
  }
  const write = (path: string, content: string) => {
    mkdirSync(dirname(join(dir, path)), { recursive: true })
    writeFileSync(join(dir, path), content)
  }
  const commit = (message: string, files: Record<string, string> = {}) => {
    for (const [path, content] of Object.entries(files)) write(path, content)
    git("add", "-A")
    git("commit", "-q", "--allow-empty", "-m", message)
    return git("rev-parse", "HEAD").trim()
  }

  git("init", "-q", "-b", "main")
  return { root, dir, git, write, commit, cleanup: () => rmSync(root, { recursive: true, force: true }) }
}

export type GhRule = { re: string; out?: string; code?: number }

const RUN_TOOL = join(import.meta.dir, "run-tool.ts")

/**
 * Runs a tool in a child process whose PATH starts with a fake `gh` that
 * answers from `rules` (first regex matching the space-joined arguments).
 * Unmatched calls exit 1, like an unreachable GitHub.
 */
export function runWithFakeGh(
  f: Fixture,
  tool: { module: string; name: string; args?: Record<string, unknown> },
  rules: GhRule[],
): { ok: boolean; out?: any; error?: string; calls: string[] } {
  const bin = join(f.root, "bin")
  mkdirSync(bin, { recursive: true })
  const log = join(f.root, "gh-calls.log")
  writeFileSync(log, "")
  const gh = join(bin, "gh")
  writeFileSync(
    gh,
    [
      "#!/usr/bin/env bun",
      'import { appendFileSync } from "fs"',
      'const args = process.argv.slice(2).join(" ")',
      'appendFileSync(process.env.FAKE_GH_LOG!, args + "\\n")',
      'for (const r of JSON.parse(process.env.FAKE_GH_RULES ?? "[]")) {',
      '  if (new RegExp(r.re).test(args)) { process.stdout.write(r.out ?? ""); process.exit(r.code ?? 0) }',
      "}",
      'process.stderr.write("fake gh: no rule for " + args)',
      "process.exit(1)",
      "",
    ].join("\n"),
  )
  chmodSync(gh, 0o755)
  const res = Bun.spawnSync(["bun", RUN_TOOL], {
    cwd: f.dir,
    env: {
      ...process.env,
      PATH: `${bin}:${process.env.PATH}`,
      FAKE_GH_RULES: JSON.stringify(rules),
      FAKE_GH_LOG: log,
      TOOL_INPUT: JSON.stringify({ ...tool, cwd: f.dir }),
    },
  })
  const text = res.stdout.toString()
  if (!text) throw new Error(`run-tool produced no output: ${res.stderr.toString()}`)
  const calls = readFileSync(log, "utf8").split("\n").filter(Boolean)
  return { ...JSON.parse(text), calls }
}
