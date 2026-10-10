import { existsSync, mkdirSync, realpathSync, rmdirSync } from "fs"
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

/** ~/Worktrees; tests point DOTCONFIG_WORKTREE_ROOT elsewhere. */
export const worktreeRoot = () => process.env.DOTCONFIG_WORKTREE_ROOT || join(homedir(), "Worktrees")
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
  // origin/HEAD is only recorded by a clone; ask the remote when it is missing.
  const remote = await git(directory, ["ls-remote", "--symref", "origin", "HEAD"], FETCH_TIMEOUT_MS)
  const named = remote.stdout.match(/^ref: refs\/heads\/(\S+)\s+HEAD/m)?.[1]
  for (const ref of [named ? `origin/${named}` : "", "origin/main", "origin/master"].filter(Boolean))
    if ((await git(directory, ["rev-parse", "--verify", "--quiet", `${ref}^{commit}`])).ok) return ref
  return null
}

export type Created = { directory: string; branch: string; base: string; fetched: boolean | null; existingBranch: boolean }

/**
 * Creates the worktree for `branch`: a new branch from `start` (default: the
 * freshly fetched remote default branch, or HEAD in a repository without
 * origin), or an existing local branch checked out as is when no `start` is
 * given.
 */
export async function createWorktree(input: { sourceDirectory: string; branch: string; start?: string; root?: string }): Promise<Created> {
  const { sourceDirectory, branch } = input
  if (!(await git(sourceDirectory, ["check-ref-format", "--branch", branch])).ok || branch.startsWith("-"))
    throw new Error(`${branch} is not a valid branch name; use something like task/short-name.`)
  const root = input.root ?? worktreeRoot()
  const target = targetPath(root, await repositoryName(sourceDirectory), branch)
  if (existsSync(target)) throw new Error(`${target} already exists; pick another name.`)
  const existingBranch = (await git(sourceDirectory, ["show-ref", "--verify", "--quiet", `refs/heads/${branch}`])).ok
  const start = input.start?.trim()
  if (existingBranch && start) throw new Error(`Branch ${branch} already exists; leave out the starting ref to check it out, or pick a new name.`)

  let base = branch
  let fetched: boolean | null = null
  if (!existingBranch) {
    const remotes = (await gitOut(sourceDirectory, ["remote"])).split("\n")
    if (remotes.includes("origin")) fetched = (await git(sourceDirectory, ["fetch", "--quiet", "origin"], FETCH_TIMEOUT_MS)).ok
    if (start) {
      if (start.startsWith("-") || !(await git(sourceDirectory, ["rev-parse", "--verify", "--quiet", `${start}^{commit}`])).ok)
        throw new Error(`${start} is not a commit here; start from a branch, tag or sha.`)
      base = start
    } else if (remotes.includes("origin")) {
      const def = await defaultRef(sourceDirectory)
      if (!def) throw new Error("origin's default branch is unknown here; pass a starting ref.")
      base = def
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

/**
 * Whether `branch` has landed: an ancestor of the default branch, or the head
 * of a merged PR from this repository whose head commit is the branch's tip
 * (a squash or rebase merge leaves no ancestry). A PR matched by name alone
 * could be an older branch of the same name, or one from a fork.
 */
async function merged(main: string, branch: string, tip: string): Promise<boolean> {
  const def = await defaultRef(main)
  if (def && (await git(main, ["merge-base", "--is-ancestor", `refs/heads/${branch}`, def])).ok) return true
  const pr = await exec(["gh", "pr", "list", "--head", branch, "--state", "merged", "--json", "headRefOid,isCrossRepository", "--limit", "20"], {
    cwd: main,
    env: gitEnv(),
    timeoutMs: 20_000,
  })
  if (!pr.ok) return false
  try {
    return (JSON.parse(pr.stdout) as { headRefOid?: string; isCrossRepository?: boolean }[]).some(
      (p) => p.isCrossRepository === false && p.headRefOid === tip,
    )
  } catch {
    return false
  }
}

/** Removes the worktree, then its branch only when the branch has landed on the default branch. */
export async function removeWorktree(input: { directory: string; force: boolean }): Promise<Removed> {
  // Already gone (deleted by hand): nothing to remove; `git worktree prune` drops the record.
  if (!existsSync(input.directory)) return { directory: input.directory, branch: null, branchDeleted: false, reason: "already gone" }
  const main = await mainCheckout(input.directory)
  const head = await git(input.directory, ["symbolic-ref", "--quiet", "--short", "HEAD"])
  const branch = head.ok ? head.stdout.trim() : null
  const tip = branch ? (await git(input.directory, ["rev-parse", "HEAD"])).stdout.trim() : ""
  const res = await git(main, ["worktree", "remove", ...(input.force ? ["--force"] : []), input.directory])
  if (!res.ok) {
    const message = res.stderr.trim() || "git worktree remove failed"
    const dirty = /modified or untracked|is dirty/i.test(message)
    const error = new Error(dirty ? `${message}. Removing it with force discards those changes.` : message)
    if (dirty) Object.assign(error, { forceRequired: true })
    throw error
  }
  // Drop the repository's folder under the root once its last worktree is gone.
  try {
    rmdirSync(dirname(input.directory))
  } catch {
    // not empty
  }
  if (!branch) return { directory: input.directory, branch, branchDeleted: false, reason: "detached HEAD" }
  const def = (await defaultRef(main))?.replace(/^origin\//, "")
  if (["main", "master", def].includes(branch)) return { directory: input.directory, branch, branchDeleted: false, reason: "a default branch is never deleted" }
  if (!(await merged(main, branch, tip))) return { directory: input.directory, branch, branchDeleted: false, reason: "not merged into the default branch" }
  const del = await git(main, ["branch", "-D", branch])
  return del.ok
    ? { directory: input.directory, branch, branchDeleted: true }
    : { directory: input.directory, branch, branchDeleted: false, reason: del.stderr.trim().slice(0, 200) }
}

/** The repository roots plus the worktrees this strategy places under `root`; nothing outside Git. */
export async function listWorktrees(sourceDirectory: string, root = worktreeRoot()) {
  const res = await git(sourceDirectory, ["worktree", "list", "--porcelain"])
  if (!res.ok) return []
  const owned = (existsSync(root) ? realpathSync.native(root) : root) + sep
  return res.stdout
    .split("\n\n")
    .map((block) => block.split("\n"))
    .filter((lines) => lines[0]?.startsWith("worktree "))
    .flatMap((lines, i) => {
      const directory = lines[0].slice(9)
      if (i === 0) return [{ directory, type: "root" as const }]
      // A worktree deleted by hand stays listed as prunable until `git worktree prune`.
      if (lines.some((l) => l.startsWith("prunable"))) return []
      return directory.startsWith(owned) ? [{ directory, type: "worktree" as const }] : []
    })
}

/**
 * The V2 WorktreeDefinition. OpenCode suggests `<worktree.directory>/<name>`:
 * the name becomes the new branch, and `branch` is the starting ref (V2's
 * contract), not a branch name.
 */
export function strategy(root = worktreeRoot()) {
  return {
    id: "dotconfig.worktrees",
    async create(input: { sourceDirectory: string; directory: string; branch?: string }) {
      const created = await createWorktree({ sourceDirectory: input.sourceDirectory, branch: basename(input.directory), start: input.branch, root })
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
