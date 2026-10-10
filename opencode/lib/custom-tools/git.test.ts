import { afterEach, describe, expect, test } from "bun:test"
import { chmodSync, mkdirSync, writeFileSync } from "fs"
import { join } from "path"
import plugin from "../../plugins/custom-tools"
import * as git from "./git"
import { fixture, runWithFakeGh, type Fixture } from "./testing/repo"

// Characterization tests: they pin the tools' current behavior so the
// lib/custom-tools/git refactor can be checked against them.

const fixtures: Fixture[] = []
const repo = () => {
  const f = fixture()
  fixtures.push(f)
  return f
}
afterEach(() => {
  while (fixtures.length) fixtures.pop()!.cleanup()
})

const ctx = (f: Fixture) => ({ worktree: f.dir, oauthAccess: async () => undefined })
const run = async (spec: { execute: (args: any, context: any) => Promise<string> }, f: Fixture, args: any = {}) =>
  JSON.parse(await spec.execute(args, ctx(f)))

// Built at runtime so this file itself carries no key-shaped literal.
const AWS_KEY = "AKIA" + "IOSFODNN7EXAMPLE"
const HIGH_ENTROPY = "Zx8Qp2Lr7Vb4Nt6H" + "k9Wm3Jc5Fd1Gs0Ya"
const lines = (n: number, edit: Record<number, string> = {}) =>
  Array.from({ length: n }, (_, i) => edit[i + 1] ?? `line ${i + 1}`).join("\n") + "\n"

describe("registry", () => {
  test("registers the same tool ids", async () => {
    const ids = Object.keys((await plugin.server()).tool).sort()
    expect(ids).toEqual([
      "gh_pr_status",
      "git_amend_check",
      "git_commit",
      "git_commit_lint",
      "git_conflicts",
      "git_history_digest",
      "git_provenance",
      "git_related_scan",
      "git_secret_scan",
      "git_stage_hunks",
      "git_state",
      "git_verify_commits",
      "git_worktree",
      "github_project_create",
      "github_project_field_ensure",
      "github_project_issue_develop",
      "github_project_issue_link",
      "github_project_item_add",
      "github_project_item_list",
      "github_project_item_note",
      "github_project_item_promote",
      "github_project_item_set",
      "github_project_view_ensure",
      "web_ui_check",
      "x_search",
    ])
  })
})

describe("git_secret_scan", () => {
  test("finds a known key prefix in the staged diff and redacts it", async () => {
    const f = repo()
    f.commit("init", { "a.ts": "export {}\n" })
    f.write("a.ts", `export const id = "${AWS_KEY}"\n`)
    f.git("add", "a.ts")
    const out = await run(git.secret_scan, f)
    const builtin = out.findings.filter((x: any) => x.source === "builtin")
    expect(out.pass).toBe(false)
    expect(out.target).toBe("staged")
    expect(builtin).toContainEqual(expect.objectContaining({ file: "a.ts", line: 1, rule: "aws-access-key-id" }))
    expect(JSON.stringify(out)).not.toContain(AWS_KEY)
  })

  test("passes a clean staged diff and ignores unstaged changes", async () => {
    const f = repo()
    f.commit("init", { "a.ts": "export {}\n" })
    f.write("a.ts", "export const a = 1\n")
    f.git("add", "a.ts")
    f.write("b.ts", `export const id = "${AWS_KEY}"\n`)
    const out = await run(git.secret_scan, f)
    expect(out.findings.filter((x: any) => x.source === "builtin")).toEqual([])
  })

  test("exempts lockfiles from the entropy heuristic only", async () => {
    const f = repo()
    f.commit("init")
    f.write("pnpm-lock.yaml", `value: ${HIGH_ENTROPY}\n`)
    f.write("src/a.ts", `export const value = "${HIGH_ENTROPY}"\n`)
    f.git("add", "-A")
    const out = await run(git.secret_scan, f)
    const rules = out.findings.filter((x: any) => x.source === "builtin").map((x: any) => `${x.file}:${x.rule}`)
    expect(rules).toEqual(["src/a.ts:high-entropy"])
  })

  test("scans the worktree and a range on request", async () => {
    const f = repo()
    f.commit("init", { "a.ts": "export {}\n" })
    f.write("a.ts", `export const id = "${AWS_KEY}"\n`)
    const worktree = await run(git.secret_scan, f, { target: "worktree" })
    expect(worktree.findings.some((x: any) => x.rule === "aws-access-key-id")).toBe(true)
    f.commit("leak")
    const range = await run(git.secret_scan, f, { target: "range", range: "HEAD~1..HEAD" })
    expect(range.findings.some((x: any) => x.rule === "aws-access-key-id")).toBe(true)
    await expect(git.secret_scan.execute({ target: "range" }, ctx(f))).rejects.toThrow(/requires `range`/)
  })
})

describe("git_stage_hunks", () => {
  const twoHunks = (f: Fixture) => {
    f.commit("init", { "a.txt": lines(30) })
    f.write("a.txt", lines(30, { 2: "first change", 29: "second change" }))
  }

  test("lists unstaged hunks with stable ids", async () => {
    const f = repo()
    twoHunks(f)
    const out = await run(git.stage_hunks, f)
    expect(out.mode).toBe("list")
    expect(out.count).toBe(2)
    expect(out.hunks.map((h: any) => [h.id, h.file, h.added, h.removed, h.binary])).toEqual([
      [1, "a.txt", 1, 1, false],
      [2, "a.txt", 1, 1, false],
    ])
    expect(f.git("diff", "--cached", "--name-only")).toBe("")
  })

  test("stages exactly the selected hunk, including the file's last hunk", async () => {
    const f = repo()
    twoHunks(f)
    const out = await run(git.stage_hunks, f, { hunks: [2] })
    expect(out.mode).toBe("staged")
    expect(out.stagedHunkIds).toEqual([2])
    const cached = f.git("diff", "--cached")
    expect(cached).toContain("+second change")
    expect(cached).not.toContain("first change")
    expect(f.git("diff")).toContain("+first change")
  })

  test("selects by include and exclude regexes", async () => {
    const f = repo()
    twoHunks(f)
    const out = await run(git.stage_hunks, f, { include: "change", exclude: "first" })
    expect(out.stagedHunkIds).toEqual([2])
  })

  test("refuses an empty selection and secret-bearing hunks", async () => {
    const f = repo()
    twoHunks(f)
    await expect(git.stage_hunks.execute({ include: "nothing-like-this" }, ctx(f))).rejects.toThrow("No hunks matched the selection.")
    f.write("b.txt", "x\n")
    f.git("add", "b.txt")
    f.git("commit", "-q", "-m", "b")
    f.write("b.txt", `id ${AWS_KEY}\n`)
    const out = await run(git.stage_hunks, f, { paths: ["b.txt"], hunks: [1], denySecrets: true })
    expect(out.mode).toBe("blocked")
    expect(f.git("diff", "--cached", "--name-only")).toBe("")
  })

  test("stages a later hunk at its own place when an earlier one is left out", async () => {
    // Two identical blocks, and an unselected insertion above them that shifts
    // the second hunk's new-side start onto the other block.
    const block = (n: number) => ["ctx a", "ctx b", "ctx c", "value = old", "ctx d", "ctx e", "ctx f", `unique ${n}`]
    const base = [...lines(20).trimEnd().split("\n"), ...block(1), ...lines(12).trimEnd().split("\n"), ...block(2)]
    const f = repo()
    f.commit("init", { "a.txt": base.join("\n") + "\n" })
    const edited = [...base]
    edited.splice(2, 0, ...Array.from({ length: 16 }, (_, i) => `inserted ${i}`))
    const changed = edited.map((l) => (l === "value = old" ? "value = new" : l))
    f.write("a.txt", changed.join("\n") + "\n")
    const list = await run(git.stage_hunks, f)
    expect(list.count).toBe(3)
    await run(git.stage_hunks, f, { hunks: [2], token: list.token })
    const staged = f.git("show", ":a.txt").split("\n")
    expect(staged.indexOf("value = new")).toBe(base.indexOf("value = old"))
    expect(staged.filter((l) => l === "value = old")).toHaveLength(1)
    expect(staged).not.toContain("inserted 0")
  })

  test("refuses unknown ids, a stale listing and paths outside the repository", async () => {
    const f = repo()
    twoHunks(f)
    await expect(git.stage_hunks.execute({ hunks: [1, 9] }, ctx(f))).rejects.toThrow("Unknown hunk id(s): 9")
    const all = await run(git.stage_hunks, f)
    const scoped = await run(git.stage_hunks, f, { paths: ["a.txt"] })
    expect(scoped.token).toBe(all.token)
    f.write("b.txt", "new\n")
    f.git("add", "-N", "b.txt")
    await expect(git.stage_hunks.execute({ hunks: [1], token: all.token }, ctx(f))).rejects.toThrow(/changed since that listing/)
    await expect(git.stage_hunks.execute({ paths: ["/elsewhere/x.txt"] }, ctx(f))).rejects.toThrow(/outside this session's repository/)
    await expect(git.stage_hunks.execute({ paths: ["../x.txt"] }, ctx(f))).rejects.toThrow(/outside/)
    expect(f.git("diff", "--cached", "--name-only")).toBe("")
  })

  test("lists binary changes but never stages them", async () => {
    const f = repo()
    f.commit("init", { "a.txt": "a\n" })
    writeFileSync(join(f.dir, "img.bin"), Buffer.from([0, 1, 2, 0, 3]))
    f.git("add", "img.bin")
    f.git("commit", "-q", "-m", "bin")
    writeFileSync(join(f.dir, "img.bin"), Buffer.from([0, 9, 9, 0, 3]))
    f.write("a.txt", "b\n")
    const list = await run(git.stage_hunks, f)
    expect(list.hunks.find((h: any) => h.file === "img.bin")).toMatchObject({ binary: true, header: "(binary)" })
    const out = await run(git.stage_hunks, f, { include: "." })
    expect(f.git("diff", "--cached", "--name-only").trim()).toBe("a.txt")
    expect(out.stagedHunkIds).toHaveLength(1)
  })
})

describe("git_amend_check", () => {
  test("recommends amend for local HEAD, fixup for an older local commit, linked-fix once pushed", async () => {
    const f = repo()
    f.commit("one")
    const two = f.commit("two")
    expect((await run(git.amend_check, f)).recommendation).toBe("amend")
    expect(await run(git.amend_check, f, { sha: "HEAD~1" })).toMatchObject({ recommendation: "fixup", isHead: false, pushed: false })

    const remote = join(f.root, "remote.git")
    Bun.spawnSync(["git", "init", "-q", "--bare", remote])
    f.git("remote", "add", "origin", remote)
    f.git("push", "-q", "-u", "origin", "main")
    expect(await run(git.amend_check, f)).toMatchObject({
      sha: two,
      recommendation: "linked-fix",
      hasUpstream: true,
      inUpstream: true,
      remoteBranches: ["origin/main"],
    })
  })
})

describe("git_commit_lint", () => {
  const lint = (f: Fixture, message: string, extra: any = {}) => run(git.commit_lint, f, { message, ...extra })
  const rules = (out: any) => [...out.errors, ...out.warnings].map((v: any) => `${v.severity}:${v.rule}`).sort()

  test("passes a clean conventional message without commitlint", async () => {
    const f = repo()
    expect(await lint(f, "feat(x): add a thing\n\nExplain why.")).toEqual({
      pass: true,
      commitlintRan: false,
      commitlint: "not-configured",
      hook: null,
      errors: [],
      warnings: [],
    })
  })

  test("fails when a commit-msg hook runs a commitlint that is not installed", async () => {
    const husky = repo()
    husky.write(".husky/commit-msg", "# lint\npnpm exec commitlint --edit $1\n")
    const out = await lint(husky, "feat: fine")
    expect(out).toMatchObject({ pass: false, commitlint: "not-installed", hook: "pnpm exec commitlint --edit $1" })
    expect(out.errors[0].rule).toBe("commitlint-not-installed")

    const custom = repo()
    custom.write("hooks/commit-msg", "npx --no -- commitlint --edit $1\n")
    custom.git("config", "core.hooksPath", "hooks")
    expect(await lint(custom, "feat: fine")).toMatchObject({ pass: false, hook: "npx --no -- commitlint --edit $1" })

    const configOnly = repo()
    configOnly.write("package.json", '{"commitlint": {"extends": ["@commitlint/config-conventional"]}}')
    const warned = await lint(configOnly, "feat: fine")
    expect(warned).toMatchObject({ pass: true, commitlint: "not-installed", hook: null })
    expect(warned.warnings.map((w: any) => w.rule)).toEqual(["commitlint-not-installed"])
  })

  test("reports subject, structure and body problems", async () => {
    const f = repo()
    expect(rules(await lint(f, "x".repeat(73)))).toEqual(["error:subject-hard-max", "warning:conventional"])
    expect(rules(await lint(f, `feat: ${"y".repeat(50)}`))).toEqual(["warning:subject-target"])
    expect(rules(await lint(f, "feat: a.\nbody"))).toEqual(["error:blank-line", "warning:subject-period"])
    expect(rules(await lint(f, "Update stuff"))).toEqual(["warning:conventional"])
    expect(rules(await lint(f, "Merge branch 'x'"))).toEqual([])
    expect(rules(await lint(f, `feat: a\n\n${"z".repeat(80)}\n- ${"b".repeat(80)}\n\`\`\`\n${"c".repeat(80)}\n\`\`\``))).toEqual([
      "warning:body-wrap",
    ])
    expect(rules(await lint(f, "feat: a\n\nCo-authored-by: X <x@y>"))).toEqual(["warning:trailer"])
    expect(rules(await lint(f, "feat: a\n\nCo-authored-by: X <x@y>", { allowTrailers: true }))).toEqual([])
    expect(rules(await lint(f, "feat: a 🎉"))).toEqual(["warning:emoji"])
    expect(rules(await lint(f, "feat: a\n\nTouch src/foo/bar.ts and line 10."))).toEqual([
      "warning:line-numbers",
      "warning:path-enumeration",
    ])
    expect(rules(await lint(f, `feat: ${"w".repeat(70)}`, { subjectMax: 60 }))).toEqual(["error:subject-hard-max"])
  })

  test("runs the repository's commitlint binary and treats its failure as an error", async () => {
    const f = repo()
    const bin = join(f.dir, "node_modules", ".bin")
    mkdirSync(bin, { recursive: true })
    writeFileSync(join(bin, "commitlint"), '#!/bin/sh\nif grep -q BAD "$2"; then echo "rejected by commitlint"; exit 1; fi\n')
    chmodSync(join(bin, "commitlint"), 0o755)
    expect(await lint(f, "feat: fine")).toMatchObject({ pass: true, commitlintRan: true, commitlint: "ran" })
    const bad = await lint(f, "feat: BAD")
    expect(bad).toMatchObject({ pass: false, commitlintRan: true })
    expect(bad.errors[0]).toMatchObject({ rule: "commitlint", message: "rejected by commitlint" })
  })
})

describe("git_commit", () => {
  const hook = (f: Fixture, name: string, script: string) => {
    f.write(`.git/hooks/${name}`, `#!/bin/sh\n${script}\n`)
    chmodSync(join(f.dir, ".git", "hooks", name), 0o755)
  }
  const body = "Explain why, wrapped the way it\nshould land in the history."

  test("commits exactly the staged changes with the message as written", async () => {
    const f = repo()
    f.commit("init", { "a.txt": "a\n", "b.txt": "b\n" })
    f.write("a.txt", "a2\n")
    f.write("b.txt", "b2\n")
    f.write("new.txt", "n\n")
    f.git("add", "a.txt")
    const out = await run(git.commit, f, { message: `feat: change a\n\n${body}\n` })
    expect(out).toMatchObject({
      committed: true,
      subject: "feat: change a",
      messageMatches: true,
      changedByHook: [],
      leftModified: [],
      remaining: { staged: 0, unstaged: 1, untracked: 1 },
      commitlint: "not-configured",
    })
    expect(out.sha).toBe(f.git("rev-parse", "HEAD").trim())
    expect(f.git("log", "-1", "--format=%B")).toBe(`feat: change a\n\n${body}\n\n`)
    expect(f.git("show", "--name-only", "--format=", "HEAD").trim()).toBe("a.txt")
  })

  test("refuses when nothing is staged", async () => {
    const f = repo()
    f.commit("init", { "a.txt": "a\n" })
    f.write("a.txt", "b\n")
    await expect(git.commit.execute({ message: "feat: x" }, ctx(f))).rejects.toThrow(/Nothing is staged/)
  })

  test("stops before committing on a lint error or a secret finding", async () => {
    const f = repo()
    const head = f.commit("init", { "a.txt": "a\n" })
    f.write("a.txt", `id ${AWS_KEY}\n`)
    f.git("add", "a.txt")
    const lint = await run(git.commit, f, { message: "x".repeat(80) })
    expect(lint).toMatchObject({ committed: false, stoppedAt: "lint" })
    const secret = await run(git.commit, f, { message: "feat: add id" })
    expect(secret).toMatchObject({ committed: false, stoppedAt: "secrets" })
    expect(JSON.stringify(secret)).not.toContain(AWS_KEY)
    expect(f.git("rev-parse", "HEAD").trim()).toBe(head)
    expect(await run(git.commit, f, { message: "feat: add id", acceptSecretFindings: true })).toMatchObject({ committed: true })
  })

  test("stops when the hook's commitlint is not installed", async () => {
    const f = repo()
    f.commit("init")
    f.write(".husky/commit-msg", "pnpm exec commitlint --edit $1\n")
    f.git("add", ".husky/commit-msg")
    expect(await run(git.commit, f, { message: "chore: add hook" })).toMatchObject({
      committed: false,
      stoppedAt: "lint",
      commitlint: "not-installed",
    })
  })

  test("reports a hook rejection with its output", async () => {
    const f = repo()
    const head = f.commit("init", { "a.txt": "a\n" })
    hook(f, "commit-msg", 'echo "subject rejected by policy" >&2\nexit 1')
    f.write("a.txt", "b\n")
    f.git("add", "a.txt")
    const out = await run(git.commit, f, { message: "feat: x" })
    expect(out).toMatchObject({ committed: false, stoppedAt: "hook", exitCode: 1 })
    expect(out.output).toContain("subject rejected by policy")
    expect(f.git("rev-parse", "HEAD").trim()).toBe(head)
  })

  test("reports files a hook rewrote into the commit or left modified, and scans what it staged", async () => {
    const f = repo()
    f.commit("init", { "a.txt": "a\n", "b.txt": "b\n" })
    hook(f, "pre-commit", `echo formatted >> a.txt\necho "id ${AWS_KEY}" > c.txt\ngit add a.txt c.txt\necho touched >> b.txt`)
    f.write("a.txt", "a2\n")
    f.git("add", "a.txt")
    const out = await run(git.commit, f, { message: "feat: x" })
    expect(out).toMatchObject({ committed: true, changedByHook: ["a.txt", "c.txt"], leftModified: ["b.txt"] })
    expect(out.hookFindings).toContainEqual(expect.objectContaining({ file: "c.txt", rule: "aws-access-key-id" }))
  })

  test("lands the normalized message verbatim, whatever commit.cleanup says", async () => {
    const f = repo()
    f.commit("init", { "a.txt": "a\n" })
    f.git("config", "commit.cleanup", "strip")
    f.write("a.txt", "b\n")
    f.git("add", "a.txt")
    const out = await run(git.commit, f, { message: "feat: x  \r\n\r\n\r\n#123 stays a line\n\n\n" })
    expect(out).toMatchObject({ committed: true, messageMatches: true })
    expect(f.git("log", "-1", "--format=%B")).toBe("feat: x\n\n#123 stays a line\n\n")
  })

  test("does not blame a hook when there is none", async () => {
    const f = repo()
    f.commit("init", { "a.txt": "a\n" })
    f.write("a.txt", "b\n")
    f.git("add", "a.txt")
    f.git("config", "commit.gpgsign", "true")
    f.git("config", "gpg.program", join(f.root, "no-such-gpg"))
    const out = await run(git.commit, f, { message: "feat: x" })
    expect(out).toMatchObject({ committed: false, stoppedAt: "commit", hooks: [] })
    expect(out.output).toMatch(/gpg/i)
  })
})

describe("git_state", () => {
  const withOrigin = (f: Fixture) => {
    const remote = join(f.root, "remote.git")
    Bun.spawnSync(["git", "init", "-q", "--bare", remote])
    f.git("remote", "add", "origin", remote)
    f.git("push", "-q", "-u", "origin", "main")
    f.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
  }

  test("summarizes the branch, its base, changes, stashes and worktrees", async () => {
    const f = repo()
    f.commit("init", { "a.txt": "a\n", "b.txt": "b\n", "c d.txt": "c\n" })
    withOrigin(f)
    f.git("switch", "-q", "-c", "feat/x")
    f.commit("feat: one")
    f.commit("feat: two")
    f.write("a.txt", "a2\n")
    f.git("stash", "push", "-q")
    f.write("a.txt", "a3\n")
    f.git("add", "a.txt")
    f.write("b.txt", "b2\n")
    f.write("c d.txt", "c2\n")
    f.git("mv", "c d.txt", "e f.txt")
    f.write("new.txt", "n\n")
    const out = await run(git.state, f, { pr: false })
    expect(out).toMatchObject({
      root: f.dir,
      branch: "feat/x",
      detached: false,
      unborn: false,
      upstream: null,
      base: { ref: "origin/main", ahead: 2, behind: 0, commitsTruncated: false },
      operation: null,
      conflicted: [],
      staged: { count: 2, items: [{ path: "a.txt", status: "M" }, { path: "c d.txt -> e f.txt", status: "R" }] },
      unstaged: { count: 2, items: [{ path: "b.txt", status: "M" }, { path: "e f.txt", status: "M" }] },
      untracked: { count: 1, items: ["new.txt"] },
      clean: false,
      worktrees: [{ path: f.dir, branch: "feat/x", current: true }],
      pr: null,
    })
    expect(out.base.commits.map((c: string) => c.replace(/^\w+ /, ""))).toEqual(["feat: two", "feat: one"])
    expect(out.stashes).toHaveLength(1)
    expect(out.head).toBe(f.git("rev-parse", "HEAD").trim())
  })

  test("reports a merge in progress with its conflicts, and the upstream", async () => {
    const f = repo()
    f.commit("init", { "a.txt": "a\n" })
    withOrigin(f)
    f.git("switch", "-q", "-c", "other")
    f.commit("other", { "a.txt": "other\n" })
    f.git("switch", "-q", "main")
    f.commit("main", { "a.txt": "main\n" })
    Bun.spawnSync(["git", "merge", "-q", "other"], { cwd: f.dir })
    const out = await run(git.state, f, { pr: false })
    expect(out).toMatchObject({ branch: "main", operation: "merge", conflicted: ["a.txt"], upstream: { ref: "origin/main", ahead: 1, behind: 0 } })
  })

  test("handles an unborn branch, and finds the branch's PR", () => {
    const f = repo()
    const res = runWithFakeGh(f, { module: "git", name: "state" }, [])
    expect(res.out).toMatchObject({ branch: "main", unborn: true, head: null, base: null, clean: true, pr: null })
    f.commit("init")
    const withPr = runWithFakeGh(f, { module: "git", name: "state" }, [
      { re: "^pr view --json number", out: '{"number":4,"title":"T","state":"OPEN","isDraft":false}' },
    ])
    expect(withPr.out.pr).toMatchObject({ number: 4, state: "OPEN" })
  })
})

describe("git_conflicts", () => {
  const diverge = (f: Fixture) => {
    f.commit("init", { "a.txt": "one\nshared\nthree\n", "pnpm-lock.yaml": "lock: 1\n", "gone.txt": "g\n" })
    f.git("switch", "-q", "-c", "topic")
    f.commit("topic change", { "a.txt": "one\ntopic\nthree\n", "pnpm-lock.yaml": "lock: topic\n", "gone.txt": "g2\n" })
    f.git("switch", "-q", "main")
    f.git("rm", "-q", "gone.txt")
    f.commit("main change", { "a.txt": "one\nmain\nthree\n", "pnpm-lock.yaml": "lock: main\n" })
  }

  test("maps a merge's conflicts, sides and regions, and flags the lockfile", async () => {
    const f = repo()
    f.git("config", "merge.conflictStyle", "diff3")
    diverge(f)
    Bun.spawnSync(["git", "merge", "-q", "topic"], { cwd: f.dir })
    const out = await run(git.conflicts, f)
    expect(out.operation).toBe("merge")
    expect(out.sides.ours.subject).toBe("main change")
    expect(out.sides.theirs).toMatchObject({ ref: "MERGE_HEAD", subject: "topic change" })
    const byPath = Object.fromEntries(out.files.map((x: any) => [x.path, x]))
    expect(byPath["a.txt"]).toMatchObject({
      kind: "both modified",
      regionCount: 1,
      regions: [{ line: 2, ours: ["main"], base: ["shared"], theirs: ["topic"], truncated: false }],
    })
    expect(byPath["pnpm-lock.yaml"]).toMatchObject({ lockfile: true })
    expect(byPath["pnpm-lock.yaml"].resolve).toContain("pnpm install --lockfile-only")
    expect(byPath["gone.txt"]).toMatchObject({ kind: "deleted by us", regions: [] })
    const only = await run(git.conflicts, f, { paths: ["a.txt"] })
    expect(only.count).toBe(1)
  })

  test("explains ours and theirs in a rebase", async () => {
    const f = repo()
    diverge(f)
    f.git("switch", "-q", "topic")
    Bun.spawnSync(["git", "rebase", "-q", "main"], { cwd: f.dir, env: { ...process.env, GIT_EDITOR: ":" } })
    const out = await run(git.conflicts, f)
    expect(out.operation).toBe("rebase")
    expect(out.sides.ours.subject).toBe("main change")
    expect(out.sides.theirs).toMatchObject({ ref: "REBASE_HEAD", subject: "topic change" })
    expect(out.sides.note).toMatch(/rebased onto/)
  })

  test("returns nothing outside a conflicted operation", async () => {
    const f = repo()
    f.commit("init")
    expect(await run(git.conflicts, f)).toMatchObject({ operation: null, count: 0, files: [] })
  })
})

describe("git_verify_commits", () => {
  // Each commit must hold a file "ok" containing "yes" to pass.
  const check = "test \"$(cat ok)\" = yes"

  test("checks each commit in a scratch worktree and stops at the first failure", async () => {
    const f = repo()
    const base = f.commit("init", { ok: "yes\n" })
    f.commit("one", { "a.txt": "1\n" })
    const broken = f.commit("broken", { ok: "no\n" })
    f.commit("fixed", { ok: "yes\n" })
    f.write("dirty.txt", "local work\n")
    const out = await run(git.verify_commits, f, { base, command: check })
    expect(out).toMatchObject({ total: 3, checked: 2, pass: false, firstFailure: broken.slice(0, 12) })
    expect(out.results.map((r: any) => [r.subject, r.ok])).toEqual([
      ["one", true],
      ["broken", false],
    ])
    const all = await run(git.verify_commits, f, { base, command: check, keepGoing: true })
    expect(all.results.map((r: any) => r.ok)).toEqual([true, false, true])
    expect(f.git("worktree", "list").trim().split("\n")).toHaveLength(1)
    expect(f.git("status", "--porcelain")).toBe("?? dirty.txt\n")
  })

  test("runs setup once, defaults the base to the remote default branch, and refuses an empty range", async () => {
    const f = repo()
    f.commit("init", { ok: "yes\n" })
    const remote = join(f.root, "remote.git")
    Bun.spawnSync(["git", "init", "-q", "--bare", remote])
    f.git("remote", "add", "origin", remote)
    f.git("push", "-q", "origin", "main")
    f.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    await expect(git.verify_commits.execute({ command: "true" }, ctx(f))).rejects.toThrow(/No commits between/)
    f.commit("two", { "sub/x.txt": "x\n" })
    const out = await run(git.verify_commits, f, { command: "test -f marker && test -f x.txt", setup: "touch marker", cwd: "sub" })
    expect(out).toMatchObject({ total: 1, pass: true, setup: { ok: true } })
    const failedSetup = await run(git.verify_commits, f, { command: "true", setup: "echo cannot install; exit 4" })
    expect(failedSetup).toMatchObject({ pass: false, checked: 0, setup: { ok: false, output: "cannot install" } })
    await expect(git.verify_commits.execute({ command: "true", cwd: "../x" }, ctx(f))).rejects.toThrow(/relative path inside/)
  })
})

describe("git_history_digest", () => {
  test("tolerates an unborn HEAD", () => {
    const f = repo()
    const res = runWithFakeGh(f, { module: "git", name: "history_digest" }, [])
    expect(res.ok).toBe(true)
    expect(res.out).toMatchObject({ commitSampleSize: 0, conventionalRatio: 0, prTitles: [], prTemplate: null })
  })

  test("summarizes subjects, convention files, the PR template and merged PR titles", () => {
    const f = repo()
    f.commit("feat(api): one", { "commitlint.config.js": "module.exports = {}\n", ".github/PULL_REQUEST_TEMPLATE.md": "## x\n" })
    f.commit("fix(api): two")
    f.commit("fix(web): three")
    f.commit("plain subject")
    const res = runWithFakeGh(f, { module: "git", name: "history_digest", args: { limit: 10 } }, [
      { re: "^pr list --state merged", out: '["Add a (#3)"]' },
    ])
    expect(res.out).toEqual({
      commitSampleSize: 4,
      conventionalRatio: 0.75,
      typeFrequency: { feat: 1, fix: 2 },
      scopes: ["web", "api"],
      commitConfigFiles: ["commitlint.config.js"],
      commitSubjects: ["plain subject", "fix(web): three", "fix(api): two", "feat(api): one"],
      prTitles: ["Add a (#3)"],
      prTemplate: ".github/PULL_REQUEST_TEMPLATE.md",
    })
  })
})

describe("git_provenance", () => {
  const github = (sha: string) => [
    { re: "^repo view --json nameWithOwner", out: "o/r\n" },
    { re: `^api repos/o/r/commits/${sha}/pulls`, out: '[{"number":5,"title":"Add","state":"MERGED"}]' },
    { re: "^pr view 5 --json closingIssuesReferences", out: '[{"number":9,"title":"Bug"}]' },
  ]

  test("traces a sha to its PRs and the issues they close", () => {
    const f = repo()
    const sha = f.commit("feat: add", { "a.txt": "a\n" })
    const res = runWithFakeGh(f, { module: "git", name: "provenance", args: { sha } }, github(sha))
    expect(res.out).toMatchObject({
      commit: { sha, subject: "feat: add", author: "Test", source: "local" },
      repo: "o/r",
      pulls: [{ number: 5 }],
      issues: [{ number: 9, title: "Bug", viaPR: 5 }],
      links: { commit: sha.slice(0, 8), prs: ["#5"], issues: ["#9"] },
    })
  })

  test("locates the commit by blame or by the oldest pickaxe hit", () => {
    const f = repo()
    const first = f.commit("feat: add needle", { "a.txt": "needle\nb\n" })
    const second = f.commit("fix: edit", { "a.txt": "needle!\nb\n" })
    const blame = runWithFakeGh(f, { module: "git", name: "provenance", args: { file: "a.txt", lines: "1,1" } }, github(second))
    expect(blame.out).toMatchObject({ commit: { sha: second }, locatedBy: "blame a.txt:1,1" })
    const pick = runWithFakeGh(f, { module: "git", name: "provenance", args: { token: "needle" } }, github(first))
    expect(pick.out.commit.sha).toBe(first)
    expect(pick.out.pickaxe).toEqual({ hits: 1, newest: first.slice(0, 8), oldest: first.slice(0, 8) })
  })

  test("reads a commit this clone lacks from GitHub, and says when neither has it", () => {
    const f = repo()
    f.commit("local")
    const full = "abcdef1".padEnd(40, "0")
    const res = runWithFakeGh(f, { module: "git", name: "provenance", args: { sha: "abcdef1", repo: "up/stream" } }, [
      { re: "^api repos/up/stream/commits/abcdef1 --jq", out: JSON.stringify({ sha: full, subject: "feat: far", author: "U", date: "2026-01-01T00:00:00Z" }) },
      { re: `^api repos/up/stream/commits/${full}/pulls`, out: '[{"number":3,"title":"Far","state":"MERGED"}]' },
      { re: "^pr view 3 --json closingIssuesReferences .* --repo up/stream$", out: "[]" },
    ])
    expect(res.out).toMatchObject({ commit: { sha: full, subject: "feat: far", source: "github" }, repo: "up/stream", pulls: [{ number: 3 }] })
    const missing = runWithFakeGh(f, { module: "git", name: "provenance", args: { sha: "abcdef1", repo: "up/stream" } }, [])
    expect(missing.error).toMatch(/neither in this clone .* nor in up\/stream on GitHub/)
  })

  test("refuses blame against another repository and lines not committed yet", () => {
    const f = repo()
    f.commit("init", { "a.txt": "a\nb\n" })
    const foreign = runWithFakeGh(f, { module: "git", name: "provenance", args: { file: "a.txt", lines: "1,1", repo: "up/stream" } }, [
      { re: "^repo view --json nameWithOwner", out: "o/r\n" },
    ])
    expect(foreign.error).toMatch(/local clone, which is o\/r, not up\/stream/)
    f.write("a.txt", "changed\nb\n")
    const dirty = runWithFakeGh(f, { module: "git", name: "provenance", args: { file: "a.txt", lines: "1,1" } }, [])
    expect(dirty.error).toMatch(/not committed yet/)
    const zero = runWithFakeGh(f, { module: "git", name: "provenance", args: { sha: "0".repeat(40) } }, [])
    expect(zero.error).toMatch(/uncommitted changes/)
  })

  test("returns no PRs when GitHub has none, and needs an anchor", () => {
    const f = repo()
    const sha = f.commit("local")
    const res = runWithFakeGh(f, { module: "git", name: "provenance", args: { sha } }, [{ re: "^repo view", out: "o/r\n" }])
    expect(res.out).toMatchObject({ pulls: [], issues: [], links: { prs: [], issues: [] } })
    const none = runWithFakeGh(f, { module: "git", name: "provenance", args: {} }, [])
    expect(none).toMatchObject({ ok: false, error: "Provide `sha`, `file` + `lines`, or `token`/`regex`." })
  })
})

describe("git_related_scan", () => {
  test("collects explicit refs, the open PR, search candidates and no stack", () => {
    const f = repo()
    f.commit("init")
    f.git("switch", "-q", "-c", "feat/56-thing")
    f.commit("feat: thing\n\nCloses #12")
    f.commit("fix: more\n\nSee #34 and closes #12")
    const res = runWithFakeGh(f, { module: "git", name: "related_scan" }, [
      { re: "^repo view --json defaultBranchRef", out: "main\n" },
      { re: "^repo view --json nameWithOwner", out: "o/r\n" },
      { re: "^pr list --head feat/56-thing --state open", out: '{"number":7,"title":"Thing","url":"u"}' },
      // The branch number is dropped from the keywords, leaving a double space.
      { re: "^issue list --state open --search feat  thing", out: '[{"number":1,"title":"Idea"}]' },
      { re: "^pr list --state open --search feat  thing", out: '[{"number":7,"title":"Thing"},{"number":8,"title":"Other"}]' },
      { re: "^stack view", code: 1 },
      { re: "^api repos/o/r/pulls/7", out: "null" },
    ])
    expect(res.out).toEqual({
      base: "main",
      head: "feat/56-thing",
      repo: "o/r",
      existingPR: { number: 7, title: "Thing", url: "u" },
      closes: [{ number: 12, source: "commit" }],
      refs: [
        { number: 34, source: "commit-or-branch" },
        { number: 56, source: "commit-or-branch" },
      ],
      issueCandidates: [{ number: 1, title: "Idea", source: "search" }],
      relatedPRs: [{ number: 8, title: "Other", source: "search" }],
      stack: null,
    })
  })
})
