import { afterEach, describe, expect, test } from "bun:test"
import { chmodSync, existsSync, mkdirSync, realpathSync } from "fs"
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
  })

  test("lists the roots and only the worktrees it owns", async () => {
    const { f, root } = setup()
    const owned = await createWorktree({ sourceDirectory: f.dir, branch: "mine", root })
    f.git("worktree", "add", "-q", "-b", "elsewhere", join(f.root, "elsewhere"))
    expect(await listWorktrees(f.dir, root)).toEqual([
      { directory: f.dir, type: "root" },
      { directory: owned.directory, type: "worktree" },
    ])
  })

  test("the V2 definition takes the branch from the suggested name when none is given", async () => {
    const { f, root } = setup()
    const s = strategy(root)
    const { directory } = await s.create({ sourceDirectory: f.dir, directory: "/suggested/parent/quick-fix" })
    expect(directory).toBe(realpathSync(join(root, "dotconfig", "quick-fix")))
    expect(Bun.spawnSync(["git", "-C", directory, "symbolic-ref", "--short", "HEAD"]).stdout.toString().trim()).toBe("quick-fix")
  })
})

describe("git_worktree", () => {
  const service = (root: string) => {
    const s = strategy(root)
    return (source: string) => ({
      create: async (input: { name?: string; branch?: string }) => s.create({ sourceDirectory: source, directory: `/x/${input.name}`, branch: input.branch }),
      remove: (input: { directory: string; force: boolean }) => s.remove(input),
      list: async () => (await s.list(source)).map((w) => ({ directory: w.directory })),
    })
  }
  const run = async (f: Fixture, root: string, args: any) =>
    JSON.parse(await git.worktree.execute(args, { worktree: f.dir, oauthAccess: async () => undefined, worktrees: service(root)(f.dir) }))

  test("creates, lists and removes through the service", async () => {
    const { f, root } = setup()
    const created = await run(f, root, { action: "create", branch: "feat/tool" })
    expect(created).toMatchObject({ branch: "feat/tool", directory: realpathSync(join(root, "dotconfig", "feat-tool")) })
    expect(created.next).toContain("session_move")
    expect((await run(f, root, { action: "list" })).worktrees).toHaveLength(2)
    expect(await run(f, root, { action: "remove", directory: created.directory })).toMatchObject({ branch: "feat/tool", branchDeleted: true })
  })

  test("refuses V1, bad names and removing the session's own worktree", async () => {
    const { f, root } = setup()
    await expect(git.worktree.execute({ action: "list" }, { worktree: f.dir, oauthAccess: async () => undefined })).rejects.toThrow(/V2/)
    await expect(run(f, root, { action: "create", name: "a/b" })).rejects.toThrow(/cannot contain/)
    await expect(run(f, root, { action: "create" })).rejects.toThrow(/needs `branch`/)
    await expect(run(f, root, { action: "remove", directory: f.dir })).rejects.toThrow(/works in that worktree/)
  })
})
