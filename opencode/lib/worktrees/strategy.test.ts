import { afterEach, beforeEach, describe, expect, test } from "bun:test"
import { chmodSync, existsSync, mkdirSync, realpathSync, rmSync, writeFileSync } from "fs"
import { join } from "path"
import * as git from "../custom-tools/git"
import { fixture, type Fixture } from "../custom-tools/testing/repo"
import { createWorktree, listWorktrees, removeWorktree, repositoryName, strategy, targetPath } from "./strategy"

const fixtures: Fixture[] = []
afterEach(() => {
  while (fixtures.length) fixtures.pop()!.cleanup()
})

/** A clone of a bare `<root>/remote/dotconfig.git`, with a commit on main that origin lacks. */
function setup() {
  const f = fixture("worktrees-")
  fixtures.push(f)
  f.commit("init", { "a.txt": "a\n" })
  const remote = join(f.root, "remote", "dotconfig.git")
  mkdirSync(remote, { recursive: true })
  Bun.spawnSync(["git", "init", "-q", "--bare", remote])
  f.git("remote", "add", "origin", remote)
  f.git("push", "-q", "origin", "main")
  f.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
  const local = f.commit("local only")
  const root = join(f.root, "Worktrees")
  return { f, root, local }
}

describe("worktree strategy", () => {
  test("names the repository after origin, else its checkout", async () => {
    const { f } = setup()
    expect(await repositoryName(f.dir)).toBe("dotconfig")
    f.git("remote", "set-url", "origin", "git@github.com:o/other.git")
    expect(await repositoryName(f.dir)).toBe("other")
    f.git("remote", "remove", "origin")
    expect(await repositoryName(f.dir)).toBe("repo")
    expect(targetPath("/w", "dotconfig", "feat/a-b")).toBe("/w/dotconfig/feat-a-b")
  })

  test("cuts a new branch from the fetched default branch, with hooks off", async () => {
    const { f, root, local } = setup()
    f.write(".git/hooks/post-checkout", "#!/bin/sh\ntouch \"$PWD/hook-ran\"\n")
    chmodSync(join(f.dir, ".git", "hooks", "post-checkout"), 0o755)
    const created = await createWorktree({ sourceDirectory: f.dir, branch: "feat/x", root })
    expect(created).toMatchObject({ branch: "feat/x", base: "origin/main", fetched: true, existingBranch: false })
    expect(created.directory).toBe(realpathSync(join(root, "dotconfig", "feat-x")))
    const wt = (...a: string[]) => Bun.spawnSync(["git", "-C", created.directory, ...a]).stdout.toString().trim()
    expect(wt("symbolic-ref", "--short", "HEAD")).toBe("feat/x")
    expect(Bun.spawnSync(["git", "-C", created.directory, "merge-base", "--is-ancestor", local, "HEAD"]).exitCode).toBe(1)
    expect(wt("config", "--get", "branch.feat/x.remote")).toBe("")
    expect(existsSync(join(created.directory, "hook-ran"))).toBe(false)
    await expect(createWorktree({ sourceDirectory: f.dir, branch: "feat/x", root })).rejects.toThrow(/already exists/)
    await expect(createWorktree({ sourceDirectory: f.dir, branch: "bad..name", root })).rejects.toThrow(/not a valid branch name/)
  })

  test("checks an existing branch out as is, and starts from HEAD without a remote", async () => {
    const { f, root, local } = setup()
    f.git("branch", "topic")
    const existing = await createWorktree({ sourceDirectory: f.dir, branch: "topic", root })
    expect(existing).toMatchObject({ existingBranch: true, fetched: null })
    expect(Bun.spawnSync(["git", "-C", existing.directory, "rev-parse", "HEAD"]).stdout.toString().trim()).toBe(local)
    f.git("remote", "remove", "origin")
    const offline = await createWorktree({ sourceDirectory: f.dir, branch: "solo", root })
    expect(offline).toMatchObject({ base: "HEAD", fetched: null })
    expect(offline.directory).toBe(realpathSync(join(root, "repo", "solo")))
  })

  test("starts a new branch from a given ref, refusing an unknown one or an existing branch with it", async () => {
    const { f, root, local } = setup()
    const from = await createWorktree({ sourceDirectory: f.dir, branch: "from-main", start: "main", root })
    expect(from).toMatchObject({ base: "main", existingBranch: false })
    expect(Bun.spawnSync(["git", "-C", from.directory, "rev-parse", "HEAD"]).stdout.toString().trim()).toBe(local)
    await expect(createWorktree({ sourceDirectory: f.dir, branch: "x", start: "no-such-ref", root })).rejects.toThrow(/not a commit here/)
    f.git("branch", "taken")
    await expect(createWorktree({ sourceDirectory: f.dir, branch: "taken", start: "main", root })).rejects.toThrow(/already exists/)
  })

  test("finds the default branch from the remote when origin/HEAD is not recorded", async () => {
    const { f, root } = setup()
    f.git("symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
    expect(await createWorktree({ sourceDirectory: f.dir, branch: "y", root })).toMatchObject({ base: "origin/main" })
  })

  test("removes a worktree, deleting its branch only once merged", async () => {
    const { f, root } = setup()
    const merged = await createWorktree({ sourceDirectory: f.dir, branch: "done", root })
    expect(await removeWorktree({ directory: merged.directory, force: false })).toMatchObject({ branch: "done", branchDeleted: true })
    expect(existsSync(merged.directory)).toBe(false)

    const open = await createWorktree({ sourceDirectory: f.dir, branch: "open", root })
    Bun.spawnSync(["git", "-C", open.directory, "commit", "-q", "--allow-empty", "-m", "wip"])
    expect(await removeWorktree({ directory: open.directory, force: false })).toMatchObject({ branchDeleted: false, reason: "not merged into the default branch" })
    expect(f.git("branch", "--list", "open").trim()).toBe("open")

    const dirty = await createWorktree({ sourceDirectory: f.dir, branch: "dirty", root })
    Bun.write(join(dirty.directory, "a.txt"), "changed\n")
    const err = await removeWorktree({ directory: dirty.directory, force: false }).catch((e) => e)
    expect(err.forceRequired).toBe(true)
    expect(await removeWorktree({ directory: dirty.directory, force: true })).toMatchObject({ branchDeleted: true })

    expect(await removeWorktree({ directory: join(root, "dotconfig", "gone"), force: false })).toMatchObject({ reason: "already gone" })
    f.git("branch", "master", "main")
    const master = await createWorktree({ sourceDirectory: f.dir, branch: "master", root })
    expect(await removeWorktree({ directory: master.directory, force: false })).toMatchObject({ branchDeleted: false, reason: "a default branch is never deleted" })
  })

  test("trusts a merged PR only when it is this repository's and ends at the branch's tip", async () => {
    const { f, root } = setup()
    const bin = join(f.root, "bin")
    mkdirSync(bin)
    const answer = join(f.root, "prs.json")
    writeFileSync(join(bin, "gh"), `#!/bin/sh\ncat "${answer}"\n`)
    chmodSync(join(bin, "gh"), 0o755)
    const path = process.env.PATH
    process.env.PATH = `${bin}:${path}`
    try {
      const squash = async (prs: (tip: string) => unknown[]) => {
        const wt = await createWorktree({ sourceDirectory: f.dir, branch: `sq-${Math.random().toString(36).slice(2, 8)}`, root })
        Bun.spawnSync(["git", "-C", wt.directory, "commit", "-q", "--allow-empty", "-m", "squashed upstream"])
        const tip = Bun.spawnSync(["git", "-C", wt.directory, "rev-parse", "HEAD"]).stdout.toString().trim()
        writeFileSync(answer, JSON.stringify(prs(tip)))
        return removeWorktree({ directory: wt.directory, force: false })
      }
      expect(await squash((tip) => [{ headRefOid: tip, isCrossRepository: false }])).toMatchObject({ branchDeleted: true })
      expect(await squash(() => [{ headRefOid: "0".repeat(40), isCrossRepository: false }])).toMatchObject({ branchDeleted: false })
      expect(await squash((tip) => [{ headRefOid: tip, isCrossRepository: true }])).toMatchObject({ branchDeleted: false })
    } finally {
      process.env.PATH = path
    }
  })

  test("lists the roots and only the live worktrees it owns, and nothing outside Git", async () => {
    const { f, root } = setup()
    const owned = await createWorktree({ sourceDirectory: f.dir, branch: "mine", root })
    const gone = await createWorktree({ sourceDirectory: f.dir, branch: "gone", root })
    rmSync(gone.directory, { recursive: true, force: true })
    f.git("worktree", "add", "-q", "-b", "elsewhere", join(f.root, "elsewhere"))
    expect(await listWorktrees(f.dir, root)).toEqual([
      { directory: f.dir, type: "root" },
      { directory: owned.directory, type: "worktree" },
    ])
    expect(await listWorktrees(f.root, root)).toEqual([])
  })

  test("the V2 definition names the branch after the suggested directory and starts from `branch`", async () => {
    const { f, root } = setup()
    const s = strategy(root)
    const { directory } = await s.create({ sourceDirectory: f.dir, directory: "/suggested/parent/quick-fix" })
    expect(directory).toBe(realpathSync(join(root, "dotconfig", "quick-fix")))
    expect(Bun.spawnSync(["git", "-C", directory, "symbolic-ref", "--short", "HEAD"]).stdout.toString().trim()).toBe("quick-fix")
    const started = await s.create({ sourceDirectory: f.dir, directory: "/suggested/parent/off-main", branch: "main" })
    expect(Bun.spawnSync(["git", "-C", started.directory, "symbolic-ref", "--short", "HEAD"]).stdout.toString().trim()).toBe("off-main")
  })
})

describe("git_worktree", () => {
  let previous: string | undefined
  beforeEach(() => {
    previous = process.env.DOTCONFIG_WORKTREE_ROOT
  })
  afterEach(() => {
    if (previous === undefined) delete process.env.DOTCONFIG_WORKTREE_ROOT
    else process.env.DOTCONFIG_WORKTREE_ROOT = previous
  })
  const run = async (f: Fixture, root: string, args: any) => {
    process.env.DOTCONFIG_WORKTREE_ROOT = root
    const refreshes: number[] = []
    const worktrees = {
      refresh: async () => {
        refreshes.push(1)
      },
      list: async () => (await listWorktrees(f.dir, root)).map((w) => ({ directory: w.directory })),
    }
    const out = JSON.parse(await git.worktree.execute(args, { worktree: f.dir, oauthAccess: async () => undefined, worktrees }))
    return { ...out, refreshed: refreshes.length }
  }

  test("creates, lists and removes, refreshing the inventory", async () => {
    const { f, root } = setup()
    const created = await run(f, root, { action: "create", branch: "feat/tool" })
    expect(created).toMatchObject({ branch: "feat/tool", base: "origin/main", refreshed: 1, directory: realpathSync(join(root, "dotconfig", "feat-tool")) })
    expect(created.next).toContain("session_move")
    expect((await run(f, root, { action: "list" })).worktrees).toHaveLength(2)
    expect(await run(f, root, { action: "remove", directory: created.directory })).toMatchObject({ branch: "feat/tool", branchDeleted: true, refreshed: 1 })
  })

  test("refuses V1, a missing branch, uncommitted changes and the session's own worktree", async () => {
    const { f, root } = setup()
    await expect(git.worktree.execute({ action: "list" }, { worktree: f.dir, oauthAccess: async () => undefined })).rejects.toThrow(/V2/)
    await expect(run(f, root, { action: "create" })).rejects.toThrow(/needs `branch`/)
    const dirty = await run(f, root, { action: "create", branch: "dirty" })
    writeFileSync(join(dirty.directory, "a.txt"), "changed\n")
    await expect(run(f, root, { action: "remove", directory: dirty.directory })).rejects.toThrow(/discards those changes/)
    await expect(run(f, root, { action: "remove", directory: `${f.dir}/` })).rejects.toThrow(/works in that worktree/)
  })
})
