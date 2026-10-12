import { afterEach, describe as suite, expect, test } from "bun:test"
import { load, skip } from "./testing/deps"
import type { Fixture, GhRule } from "./testing/repo"

const describe = suite.skipIf(skip)
const { labelOnly, parseWorkflow, reacts } = await load(() => import("./pr-meta"))
const { fixture, runWithFakeGh } = await load(() => import("./testing/repo"))

const fixtures: Fixture[] = []
afterEach(() => {
  while (fixtures.length) fixtures.pop()!.cleanup()
})

describe("workflow reading", () => {
  test("reads label-only job conditions", () => {
    expect(labelOnly("github.event.label.name == 'deploy'")).toEqual(["deploy"])
    expect(labelOnly("${{ github.event.label.name == \"a\" || 'b' == github.event.label.name }}")).toEqual(["a", "b"])
    expect(labelOnly("contains(github.event.pull_request.labels.*.name, 'deploy')")).toBeNull()
    expect(labelOnly("github.event.label.name == 'a' && github.actor == 'x'")).toBeNull()
    expect(labelOnly(undefined)).toBeNull()
  })

  test("defaults pull_request to opened, synchronize and reopened", () => {
    const wf = parseWorkflow("ci.yml", "on: pull_request\njobs:\n  t:\n    runs-on: x\n")
    expect(reacts(wf, "pull_request", "opened")).toBe(true)
    expect(reacts(wf, "pull_request", "labeled", "bug")).toBe(false)
    const list = parseWorkflow("ci.yml", "on: [push, pull_request_target]\njobs:\n  t: {}\n")
    expect(reacts(list, "pull_request_target", "assigned")).toBe(false)
    expect(reacts(list, "pull_request", "opened")).toBe(false)
  })

  test("runs on a listed type unless every job is limited to other labels, compared as Actions does", () => {
    const text = (cond: string) =>
      `on:\n  pull_request:\n    types: [labeled, assigned]\njobs:\n  a:\n    if: ${cond}\n    runs-on: x\n  b:\n    if: github.event.label.name == 'ship'\n`
    const limited = parseWorkflow("l.yml", text("github.event.label.name == 'DEPLOY'"))
    expect(reacts(limited, "pull_request", "labeled", "bug")).toBe(false)
    expect(reacts(limited, "pull_request", "labeled", "deploy")).toBe(true)
    expect(reacts(limited, "pull_request", "labeled", "ship")).toBe(true)
    expect(reacts(limited, "pull_request", "assigned")).toBe(false)
    // A skipped run still completes, and a workflow_run workflow can chain off it.
    expect(reacts(limited, "pull_request", "labeled", "bug", true)).toBe(true)
    // Workflow-level concurrency lets a run whose jobs all skip cancel a running one.
    const grouped = parseWorkflow("g.yml", `concurrency:\n  group: deploy\n  cancel-in-progress: true\n${text("github.event.label.name == 'deploy'")}`)
    expect(reacts(grouped, "pull_request", "labeled", "bug")).toBe(true)
    const open = parseWorkflow("o.yml", text("github.actor == 'me'"))
    expect(reacts(open, "pull_request", "labeled", "bug")).toBe(true)
    expect(reacts(open, "pull_request", "assigned")).toBe(true)
  })

  test("marks unparsable YAML and `on` shapes it does not understand", () => {
    expect(parseWorkflow("x.yml", "on: [unclosed").error).toBeDefined()
    expect(parseWorkflow("x.yml", "on:\n  - pull_request: {}\njobs: {}\n").error).toBeDefined()
    expect(parseWorkflow("x.yml", "on:\n  workflow_run:\n    workflows: [CI]\njobs: {}\n").workflowRun).toBe(true)
  })
})

describe("gh_pr_meta", () => {
  const DEFAULT_SHA = "a".repeat(40)
  const setup = (workflows: Record<string, string> = {}) => {
    const f = fixture()
    fixtures.push(f)
    const head = f.commit("init", { "a.txt": "a\n", ...Object.fromEntries(Object.entries(workflows).map(([k, v]) => [`.github/workflows/${k}`, v])) })
    return { f, head }
  }
  const pr = (head: string, extra: Record<string, unknown> = {}) => ({
    number: 5,
    state: "OPEN",
    title: "feat: thing",
    author: { login: "author1" },
    headRefOid: head,
    baseRefName: "main",
    labels: [],
    assignees: [],
    reviewRequests: [],
    milestone: null,
    ...extra,
  })
  const rules = (head: string, extra: GhRule[] = [], prExtra: Record<string, unknown> = {}): GhRule[] => [
    ...extra,
    { re: "^api user --jq", out: "me\n" },
    { re: "^repo view --json nameWithOwner", out: '{"nameWithOwner":"o/r"}' },
    { re: "^repo view o/r --json defaultBranchRef", out: '{"defaultBranchRef":{"name":"main"}}' },
    { re: "^api repos/o/r/commits/main --jq", out: `${DEFAULT_SHA}\n` },
    { re: "^pr view 5 --repo o/r --json number,state", out: JSON.stringify(pr(head, prExtra)) },
    { re: "^api --paginate --slurp repos/o/r/hooks", out: "[[]]" },
    { re: "^api --paginate --slurp repos/o/r/rules/branches/main", out: "[[]]" },
    { re: "^api --paginate --slurp repos/o/r/milestones", out: '[[{"title":"v1"}]]' },
    { re: "^api repos/o/r/assignees/", out: "" },
    { re: "^api repos/o/r/collaborators/", out: "" },
    { re: "^api repos/o/r/contents/", out: "HTTP 404: Not Found", code: 1 },
    { re: "^api repos/o/\\.github/contents/", out: "HTTP 404: Not Found", code: 1 },
    { re: "^label list --repo o/r", out: '[{"name":"bug"},{"name":"Deploy"},{"name":"enhancement"},{"name":"needs,care"}]' },
    { re: "^pr edit 5 --repo o/r", out: "" },
  ]
  const meta = (f: Fixture, args: any, r: GhRule[]) => runWithFakeGh(f, { module: "gh", name: "pr_meta", args: { prs: ["5"], ...args } }, r)
  const apply = (f: Fixture, args: any, r: GhRule[]) => runWithFakeGh(f, { module: "gh", name: "pr_meta_apply", args: { prs: ["5"], ...args } }, r)
  const onDefault = (name: string, text: string) => [
    { re: `^api repos/o/r/contents/\\.github/workflows\\?ref=${DEFAULT_SHA}`, out: JSON.stringify([{ type: "file", path: `.github/workflows/${name}` }]) },
    { re: `^api -H Accept: application/vnd\\.github\\.raw\\+json repos/o/r/contents/\\.github/workflows/${name.replace(".", "\\.")}`, out: text },
  ]
  const deployOnTarget = onDefault(
    "deploy.yml",
    "on:\n  pull_request_target:\n    types: [labeled]\njobs:\n  ship:\n    if: github.event.label.name == 'deploy'\n    runs-on: x\n",
  )

  test("applies a change nothing reacts to without asking", () => {
    const { f, head } = setup()
    const res = meta(f, { labels: { add: ["bug"] }, assignees: { add: ["@me"] } }, rules(head))
    expect(res.out.applied).toEqual([
      {
        pr: "#5",
        changes: [
          { kind: "label", op: "add", value: "bug", source: "request" },
          { kind: "assignee", op: "add", value: "me", source: "request" },
        ],
      },
    ])
    expect(res.out.pending).toEqual([])
    expect(res.out.token).toBeUndefined()
    expect(res.calls).toContain("pr edit 5 --repo o/r --add-label=bug --add-assignee=me")
  })

  test("holds back a label a default-branch workflow runs on, whatever its case", () => {
    const { f, head } = setup()
    const res = meta(f, { labels: { add: ["bug", "deploy"] } }, rules(head, deployOnTarget))
    expect(res.out.applied[0].changes.map((c: any) => c.value)).toEqual(["bug"])
    expect(res.out.pending[0].changes[0]).toMatchObject({ value: "Deploy" })
    expect(res.out.pending[0].changes[0].reasons.join(" ")).toContain("deploy.yml")
    expect(res.out.token).toMatch(/^[0-9a-f]{12}$/)
    expect(res.calls.filter((c) => c.startsWith("pr edit"))).toEqual(["pr edit 5 --repo o/r --add-label=bug"])
  })

  test("stops trusting job conditions when a workflow_run workflow could chain", () => {
    const { f, head } = setup()
    const chained = [
      { re: `^api repos/o/r/contents/\\.github/workflows\\?ref=${DEFAULT_SHA}`, out: JSON.stringify([{ type: "file", path: ".github/workflows/deploy.yml" }, { type: "file", path: ".github/workflows/after.yml" }]) },
      deployOnTarget[1],
      { re: "^api -H Accept: application/vnd\\.github\\.raw\\+json repos/o/r/contents/\\.github/workflows/after\\.yml", out: "on:\n  workflow_run:\n    workflows: [deploy]\njobs:\n  t: {}\n" },
    ]
    const res = meta(f, { labels: { add: ["bug"] } }, rules(head, chained))
    expect(res.out.applied).toEqual([])
    expect(res.out.pending[0].changes[0].reasons.join(" ")).toContain("workflow_run")
  })

  test("reads the PR head's own workflows and its base's for pull_request", () => {
    const { f, head } = setup({ "assign.yml": "on:\n  pull_request:\n    types: [assigned]\njobs:\n  t:\n    runs-on: x\n" })
    const res = meta(f, { assignees: { add: ["@me"] } }, rules(head))
    expect(res.out.applied).toEqual([])
    expect(res.out.pending[0].changes[0].reasons.join(" ")).toContain("assign.yml (the PR's head)")

    const plain = setup()
    const baseHas = onDefault("milestone.yml", "on:\n  pull_request:\n    types: [milestoned]\njobs:\n  t: {}\n")
    const onBase = meta(plain.f, { milestone: "v1" }, rules(plain.head, baseHas))
    expect(onBase.out.pending[0].changes[0].reasons.join(" ")).toContain("milestone.yml (main) runs on pull_request milestoned")
  })

  test("asks before notifying people and refuses what does not exist or would be split", () => {
    const { f, head } = setup()
    const res = meta(f, { reviewers: { add: ["alice", "author1"] }, labels: { add: ["nope"] }, milestone: "v2" }, rules(head))
    expect(res.out.pending[0].changes).toEqual([expect.objectContaining({ kind: "reviewer", value: "alice", reasons: ["notifies alice"] })])
    expect(res.out.invalid[0].changes.map((c: any) => c.value)).toEqual(["nope", "author1", "v2"])
    expect(res.calls.some((c) => c.startsWith("pr edit"))).toBe(false)
    expect(meta(f, { labels: { add: ["needs,care"] } }, rules(head)).error).toContain("comma")
  })

  test("treats unreadable webhooks as not harmless", () => {
    const { f, head } = setup()
    const res = meta(f, { labels: { add: ["bug"] } }, rules(head, [{ re: "^api --paginate --slurp repos/o/r/hooks", out: "HTTP 403", code: 1 }]))
    expect(res.out.applied).toEqual([])
    expect(res.out.pending[0].changes[0].reasons[0]).toContain("webhooks")
  })

  test("leaves a PR alone when it moved while being judged", () => {
    const { f, head } = setup()
    const moved = [{ re: "^pr view 5 --repo o/r --json number,state", out: JSON.stringify(pr(head)), times: 1 }]
    const res = meta(f, { labels: { add: ["bug"] } }, rules(head, moved, { headRefOid: "b".repeat(40) }))
    expect(res.out.applied).toEqual([])
    expect(res.out.moved).toEqual(["#5"])
    expect(res.calls.some((c) => c.startsWith("pr edit"))).toBe(false)
  })

  test("applies pending changes only with a current token", () => {
    const { f, head } = setup()
    const r = rules(head, deployOnTarget)
    const { token } = meta(f, { labels: { add: ["deploy"] } }, r).out
    expect(apply(f, { labels: { add: ["deploy"] }, token: "000000000000" }, r).error).toContain("changed since gh_pr_meta")
    const res = apply(f, { labels: { add: ["deploy"] }, token }, r)
    expect(res.out.applied[0].changes).toEqual([{ kind: "label", op: "add", value: "Deploy", source: "request" }])
    expect(res.calls).toContain("pr edit 5 --repo o/r --add-label=Deploy")
    // A changed milestone changes the consequences, and so the token.
    const ms = rules(head, [], { milestone: { title: "v0" } })
    const before = meta(f, { milestone: "v1" }, rules(head, onDefault("m.yml", "on:\n  pull_request_target:\n    types: [milestoned]\njobs:\n  t: {}\n")))
    const after = meta(f, { milestone: "v1" }, [...onDefault("m.yml", "on:\n  pull_request_target:\n    types: [milestoned, demilestoned]\njobs:\n  t: {}\n"), ...ms])
    expect(before.out.token).not.toBe(after.out.token)
  })

  test("refuses an inferred label gh would split on its comma", () => {
    const { f, head } = setup()
    const merged = Array.from({ length: 5 }, (_, i) => ({ number: i + 1, title: "x", labels: [{ name: "needs,care" }], assignees: [], milestone: null }))
    const res = meta(f, { infer: true }, rules(head, [{ re: "^pr list --repo o/r --state merged --author @me", out: JSON.stringify(merged) }]))
    expect(res.out.applied).toEqual([])
    expect(res.out.invalid[0].changes[0]).toMatchObject({ value: "needs,care", source: "habit" })
  })

  test("asks when the head and the base hold different versions of one workflow", () => {
    const { f, head } = setup({ "ci.yml": "on: push\njobs:\n  t: {}\n" })
    const res = meta(f, { labels: { add: ["bug"] } }, rules(head, onDefault("ci.yml", "on: [push]\njobs:\n  t: {}\n")))
    expect(res.out.applied).toEqual([])
    expect(res.out.pending[0].changes[0].reasons.join(" ")).toContain("ci.yml differs between the PR's head and main")
  })

  test("applies nothing when a webhook appears between judging and applying", () => {
    const { f, head } = setup()
    const hook = JSON.stringify([[{ id: 9, active: true, events: ["pull_request"], config: { url: "https://ci.example.com/x" } }]])
    const res = meta(f, { labels: { add: ["bug"] } }, rules(head, [{ re: "^api --paginate --slurp repos/o/r/hooks", out: "[[]]", times: 1 }, { re: "^api --paginate --slurp repos/o/r/hooks", out: hook }]))
    expect(res.out.applied).toEqual([])
    expect(res.out.moved).toEqual(["#5"])
    expect(res.calls.some((c) => c.startsWith("pr edit"))).toBe(false)
  })

  test("infers your habitual assignee and labels from merged PRs", () => {
    const { f, head } = setup()
    const merged = Array.from({ length: 6 }, (_, i) => ({
      number: i + 1,
      title: i < 4 ? "feat: x" : "fix: y",
      labels: i < 4 ? [{ name: "enhancement" }] : [],
      assignees: i < 5 ? [{ login: "me" }] : [],
      milestone: null,
    }))
    const res = meta(f, { infer: true }, rules(head, [{ re: "^pr list --repo o/r --state merged --author @me", out: JSON.stringify(merged) }]))
    expect(res.out.habits[0]).toMatchObject({ pr: "#5", sample: 6, selfAssigned: 5, labels: [{ name: "enhancement", count: 4, of: 6, scope: "all" }] })
    expect(res.out.applied[0].changes).toEqual([
      { kind: "assignee", op: "add", value: "me", source: "habit" },
      { kind: "label", op: "add", value: "enhancement", source: "habit" },
    ])
  })
})
