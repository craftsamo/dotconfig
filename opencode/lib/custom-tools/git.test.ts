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
      "git_amend_check",
      "git_commit_lint",
      "git_history_digest",
      "git_provenance",
      "git_related_scan",
      "git_secret_scan",
      "git_stage_hunks",
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
    await expect(git.stage_hunks.execute({ hunks: [9] }, ctx(f))).rejects.toThrow("No hunks matched the selection.")
    f.write("b.txt", "x\n")
    f.git("add", "b.txt")
    f.git("commit", "-q", "-m", "b")
    f.write("b.txt", `id ${AWS_KEY}\n`)
    const out = await run(git.stage_hunks, f, { paths: ["b.txt"], hunks: [1], denySecrets: true })
    expect(out.mode).toBe("blocked")
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
    expect(await lint(f, "feat(x): add a thing\n\nExplain why.")).toEqual({ pass: true, commitlintRan: false, errors: [], warnings: [] })
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
    expect(await lint(f, "feat: fine")).toMatchObject({ pass: true, commitlintRan: true })
    const bad = await lint(f, "feat: BAD")
    expect(bad).toMatchObject({ pass: false, commitlintRan: true })
    expect(bad.errors[0]).toMatchObject({ rule: "commitlint", message: "rejected by commitlint" })
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
      commit: { sha, subject: "feat: add", author: "Test" },
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
