import { existsSync, mkdirSync, realpathSync } from "fs"
import { homedir } from "os"
import { basename, dirname, join, sep } from "path"
import { exec } from "../custom-tools/exec"

/**
 * The worktree strategy every OpenCode entry point shares — the TUI's new
 * worktree, the server API and the `git_worktree` tool — and the layout the
 * Hermes `opencode_session workspace` uses: a task branch of its own, cut
 * from the freshly fetched remote default branch, at
 * `<root>/<repository>/<branch with / as ->`.
 *
 * Git runs without hooks and with a minimal environment: hooks are code the
 * repository controls, and this process is the OpenCode service, which holds
 * every session's secrets.
 */

export const DEFAULT_ROOT = join(homedir(), "Worktrees")
const FETCH_TIMEOUT_MS = 60_000
const ENV_NAMES = new Set(["PATH", "HOME", "USER", "LOGNAME", "SHELL", "LANG", "TERM", "TMPDIR", "TZ", "SSH_AUTH_SOCK"])
const SAFE_GIT = ["-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false"]

export function gitEnv(): Record<string, string> {
  const env: Record<string, string> = {}
  for (const [k, v] of Object.entries(process.env))
    if (v !== undefined && (ENV_NAMES.has(k) || k.startsWith("LC_") || k.startsWith("XDG_"))) env[k] = v
  env.GIT_TERMINAL_PROMPT = "0"
  return env
}

async function git(cwd: string, args: string[], timeoutMs?: number) {
  return exec(["git", ...SAFE_GIT, "-C", cwd, ...args], { env: gitEnv(), timeoutMs })
}

async function gitOut(cwd: string, args: string[]): Promise<string> {
  const res = await git(cwd, args)
  if (!res.ok) throw new Error(`git ${args.slice(0, 2).join(" ")} failed: ${(res.stderr.trim() || res.stdout.trim() || "no output").slice(0, 300)}`)
  return res.stdout.trim()
}

/** The main checkout of the repository `directory` belongs to. */
export async function mainCheckout(directory: string): Promise<string> {
  const common = await gitOut(directory, ["rev-parse", "--path-format=absolute", "--git-common-dir"])
  return dirname(common)
}

/** The repository's name on its origin remote (`dotconfig` for ~/.config), else its checkout's directory name. */
export async function repositoryName(directory: string): Promise<string> {
  const url = await git(directory, ["remote", "get-url", "origin"])
  const fromUrl = url.ok ? url.stdout.trim().replace(/\/+$/, "").split(/[/:]/).pop()?.replace(/\.git$/, "") : ""
  return fromUrl || basename(await mainCheckout(directory))
}

/** `<root>/<repository>/<branch with / as ->`. */
export const targetPath = (root: string, repository: string, branch: string) => join(root, repository, branch.replaceAll("/", "-"))

async function defaultRef(directory: string): Promise<string | null> {
  const head = await git(directory, ["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"])
  if (head.ok && head.stdout.trim()) return head.stdout.trim()
  for (const ref of ["origin/main", "origin/master"])
    if ((await git(directory, ["rev-parse", "--verify", "--quiet", `${ref}^{commit}`])).ok) return ref
  return null
}

export type Created = { directory: string; branch: string; base: string; fetched: boolean | null; existingBranch: boolean }

/**
 * Creates the worktree for `branch` (a new branch from the fetched remote
 * default branch, or an existing local branch checked out as is).
 */
export async function createWorktree(input: { sourceDirectory: string; branch: string; root?: string }): Promise<Created> {
  const { sourceDirectory, branch } = input
  if (!(await git(sourceDirectory, ["check-ref-format", "--branch", branch])).ok || branch.startsWith("-"))
    throw new Error(`${branch} is not a valid branch name; use something like task/short-name.`)
  const root = input.root ?? DEFAULT_ROOT
  const target = targetPath(root, await repositoryName(sourceDirectory), branch)
  if (existsSync(target)) throw new Error(`${target} already exists; pick another name.`)
  const existingBranch = (await git(sourceDirectory, ["show-ref", "--verify", "--quiet", `refs/heads/${branch}`])).ok

  let base = branch
  let fetched: boolean | null = null
  if (!existingBranch) {
    const remotes = (await gitOut(sourceDirectory, ["remote"])).split("\n")
    if (remotes.includes("origin")) {
      fetched = (await git(sourceDirectory, ["fetch", "--quiet", "origin"], FETCH_TIMEOUT_MS)).ok
      base = (await defaultRef(sourceDirectory)) ?? "HEAD"
    } else base = "HEAD"
  }
  mkdirSync(dirname(target), { recursive: true })
  const args = existingBranch ? ["worktree", "add", target, branch] : ["worktree", "add", "--no-track", "-b", branch, target, base]
  await gitOut(sourceDirectory, args)
  // The service files a worktree by its real path; a symlinked spelling
  // (/var for /private/var) would land it outside its project.
  return { directory: realpathSync(target), branch, base, fetched, existingBranch }
}

export type Removed = { directory: string; branch: string | null; branchDeleted: boolean; reason?: string }

async function merged(main: string, branch: string): Promise<boolean> {
  const def = await defaultRef(main)
  if (def && (await git(main, ["merge-base", "--is-ancestor", branch, def])).ok) return true
  // A squash or rebase merge leaves no ancestry; ask GitHub whether its PR merged.
  const pr = await exec(["gh", "pr", "list", "--head", branch, "--state", "merged", "--json", "number", "--limit", "1"], {
    cwd: main,
    env: gitEnv(),
    timeoutMs: 20_000,
  })
  return pr.ok && /"number"/.test(pr.stdout)
}

/** Removes the worktree, then its branch only when the branch has landed on the default branch. */
export async function removeWorktree(input: { directory: string; force: boolean }): Promise<Removed> {
  const main = await mainCheckout(input.directory)
  const head = await git(input.directory, ["symbolic-ref", "--quiet", "--short", "HEAD"])
  const branch = head.ok ? head.stdout.trim() : null
  const res = await git(main, ["worktree", "remove", ...(input.force ? ["--force"] : []), input.directory])
  if (!res.ok) {
    const message = res.stderr.trim() || "git worktree remove failed"
    const error = new Error(/modified or untracked|is dirty|locked/i.test(message) ? `${message}. Remove it with force to discard those changes.` : message)
    if (/modified or untracked|is dirty/i.test(message)) Object.assign(error, { forceRequired: true })
    throw error
  }
  if (!branch) return { directory: input.directory, branch, branchDeleted: false, reason: "detached HEAD" }
  if (!(await merged(main, branch))) return { directory: input.directory, branch, branchDeleted: false, reason: "not merged into the default branch" }
  const del = await git(main, ["branch", "-D", branch])
  return del.ok
    ? { directory: input.directory, branch, branchDeleted: true }
    : { directory: input.directory, branch, branchDeleted: false, reason: del.stderr.trim().slice(0, 200) }
}

/** The repository roots plus the worktrees this strategy places under `root`. */
export async function listWorktrees(sourceDirectory: string, root = DEFAULT_ROOT) {
  const out = await gitOut(sourceDirectory, ["worktree", "list", "--porcelain"])
  const dirs = out
    .split("\n")
    .filter((l) => l.startsWith("worktree "))
    .map((l) => l.slice(9))
  const owned = (existsSync(root) ? realpathSync.native(root) : root) + sep
  return dirs.flatMap((directory, i) =>
    i === 0 ? [{ directory, type: "root" as const }] : directory.startsWith(owned) ? [{ directory, type: "worktree" as const }] : [],
  )
}

/** The V2 WorktreeDefinition. OpenCode suggests `<worktree.directory>/<name>`; the name is the branch unless one is given. */
export function strategy(root = DEFAULT_ROOT) {
  return {
    id: "dotconfig.worktrees",
    async create(input: { sourceDirectory: string; directory: string; branch?: string }) {
      const created = await createWorktree({ sourceDirectory: input.sourceDirectory, branch: input.branch || basename(input.directory), root })
      return { directory: created.directory }
    },
    async remove(input: { directory: string; force: boolean }) {
      await removeWorktree(input)
    },
    async list(sourceDirectory: string) {
      return listWorktrees(sourceDirectory, root)
    },
  }
}
