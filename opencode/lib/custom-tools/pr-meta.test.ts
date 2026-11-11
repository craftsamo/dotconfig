import { afterEach, describe as suite, expect, test } from "bun:test"
import type { Assessment, Judged } from "./pr-meta"
import { load, skip } from "./testing/deps"
import type { Fixture, GhRule } from "./testing/repo"

const describe = suite.skipIf(skip)
const { applyChanges, assess, environmentUnchanged, labelOnly, parseWorkflow, prTarget, reacts } = await load(() => import("./pr-meta"))
const { fixture, withFakeGh } = await load(() => import("./testing/repo"))

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

describe("pr-meta engine", () => {
  const REPO = "o/r"
  const DEFAULT_SHA = "a".repeat(40)
  const MOVED_SHA = "b".repeat(40)
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
  const onDefault = (name: string, text: string): GhRule[] => [
    { re: `^api repos/o/r/contents/\\.github/workflows\\?ref=${DEFAULT_SHA}`, out: JSON.stringify([{ type: "file", path: `.github/workflows/${name}` }]) },
    { re: `^api -H Accept: application/vnd\\.github\\.raw\\+json repos/o/r/contents/\\.github/workflows/${name.replace(".", "\\.")}`, out: text },
  ]
  const deployOnTarget = onDefault(
    "deploy.yml",
    "on:\n  pull_request_target:\n    types: [labeled]\njobs:\n  ship:\n    if: github.event.label.name == 'deploy'\n    runs-on: x\n",
  )
  const mergedPrs = (count: number, make: (i: number) => Record<string, unknown>): GhRule => ({
    re: "^pr list --repo o/r --state merged --author @me",
    out: JSON.stringify(Array.from({ length: count }, (_, i) => ({ number: i + 1, title: "x", labels: [], assignees: [], milestone: null, ...make(i) }))),
  })

  const assessPr = async (f: Fixture, request: Parameters<typeof assess>[0]["request"], infer = false) =>
    assess({ repo: REPO, defaultBranch: "main", targets: [await prTarget(REPO, "5", f.dir)], request, infer, cwd: f.dir })
  const judged = (f: Fixture, r: GhRule[], request: Parameters<typeof assess>[0]["request"], infer = false) => withFakeGh(f, r, () => assessPr(f, request, infer))
  const changesOf = (a: Assessment) => a.targets[0].changes
  const reasonsOf = (c: Judged) => c.reasons.join(" ")

  test("judges a change nothing reacts to harmless, and applies it as one gh pr edit", async () => {
    const { f, head } = setup()
    const { value, calls } = await withFakeGh(f, rules(head), async () => {
      const a = await assessPr(f, { labels: { add: ["bug"] }, assignees: { add: ["@me"] } })
      return { a, applied: await applyChanges(REPO, 5, changesOf(a), f.dir) }
    })
    expect(value.a.viewer).toBe("me")
    expect(changesOf(value.a)).toEqual([
      { kind: "label", op: "add", value: "bug", source: "request", status: "harmless", reasons: [] },
      { kind: "assignee", op: "add", value: "me", source: "request", status: "harmless", reasons: [] },
    ])
    expect(value.applied.ok).toBe(true)
    expect(calls.filter((c) => c.startsWith("pr edit"))).toEqual(["pr edit 5 --repo o/r --add-label=bug --add-assignee=me"])
  })

  test("holds back a label a default-branch workflow runs on, whatever its case", async () => {
    const { f, head } = setup()
    const { value, calls } = await judged(f, rules(head, deployOnTarget), { labels: { add: ["bug", "deploy"] } })
    const [bug, deploy] = changesOf(value)
    expect(bug).toMatchObject({ value: "bug", status: "harmless" })
    expect(deploy).toMatchObject({ value: "Deploy", status: "approval" })
    expect(reasonsOf(deploy)).toContain("deploy.yml (main) runs on pull_request_target labeled")
    expect(value.environment.workflowsDefault).toEqual([".github/workflows/deploy.yml"])
    expect(value.digest).toMatch(/^[0-9a-f]{12}$/)
    expect(calls.some((c) => c.startsWith("pr edit"))).toBe(false)
  })

  test("stops trusting job conditions when a workflow_run workflow could chain", async () => {
    const { f, head } = setup()
    const chained = [
      { re: `^api repos/o/r/contents/\\.github/workflows\\?ref=${DEFAULT_SHA}`, out: JSON.stringify([{ type: "file", path: ".github/workflows/deploy.yml" }, { type: "file", path: ".github/workflows/after.yml" }]) },
      deployOnTarget[1],
      { re: "^api -H Accept: application/vnd\\.github\\.raw\\+json repos/o/r/contents/\\.github/workflows/after\\.yml", out: "on:\n  workflow_run:\n    workflows: [deploy]\njobs:\n  t: {}\n" },
    ]
    const { value } = await judged(f, rules(head, chained), { labels: { add: ["bug"] } })
    expect(value.environment.chained).toBe(true)
    expect(changesOf(value)[0].status).toBe("approval")
    expect(reasonsOf(changesOf(value)[0])).toContain("workflow_run")
  })

  test("reads the PR head's own workflows and its base's for pull_request", async () => {
    const { f, head } = setup({ "assign.yml": "on:\n  pull_request:\n    types: [assigned]\njobs:\n  t:\n    runs-on: x\n" })
    const { value } = await judged(f, rules(head), { assignees: { add: ["@me"] } })
    expect(changesOf(value)[0].status).toBe("approval")
    expect(reasonsOf(changesOf(value)[0])).toContain("assign.yml (the PR's head)")

    const plain = setup()
    const baseHas = onDefault("milestone.yml", "on:\n  pull_request:\n    types: [milestoned]\njobs:\n  t: {}\n")
    const onBase = await judged(plain.f, rules(plain.head, baseHas), { milestone: "v1" })
    expect(reasonsOf(changesOf(onBase.value)[0])).toContain("milestone.yml (main) runs on pull_request milestoned")
  })

  test("asks before notifying people and refuses what does not exist or would be split", async () => {
    const { f, head } = setup()
    const r = rules(head, [{ re: "^api repos/o/r/collaborators/ghost", out: "HTTP 404: Not Found", code: 1 }])
    const { value, calls } = await judged(f, r, { reviewers: { add: ["alice", "ghost", "author1"] }, labels: { add: ["nope"] }, milestone: "v2" })
    const changes = changesOf(value)
    expect(changes.map((c) => [c.value, c.status])).toEqual([
      ["nope", "invalid"],
      ["alice", "approval"],
      ["ghost", "invalid"],
      ["author1", "invalid"],
      ["v2", "invalid"],
    ])
    expect(changes[1]).toMatchObject({ kind: "reviewer", reasons: ["notifies alice"] })
    expect(reasonsOf(changes[2])).toContain("ghost cannot review")
    expect(reasonsOf(changes[3])).toContain("author cannot review")
    expect(calls.some((c) => c.startsWith("pr edit"))).toBe(false)
    await expect(judged(f, rules(head), { labels: { add: ["needs,care"] } })).rejects.toThrow("comma")
  })

  test("treats unreadable webhooks as not harmless", async () => {
    const { f, head } = setup()
    const { value } = await judged(f, rules(head, [{ re: "^api --paginate --slurp repos/o/r/hooks", out: "HTTP 403", code: 1 }]), { labels: { add: ["bug"] } })
    expect(value.environment.hooks).toBe("unreadable")
    expect(changesOf(value)[0].status).toBe("approval")
    expect(changesOf(value)[0].reasons[0]).toContain("webhooks")
  })

  test("asks when the head and the base hold different versions of one workflow", async () => {
    const { f, head } = setup({ "ci.yml": "on: push\njobs:\n  t: {}\n" })
    const { value } = await judged(f, rules(head, onDefault("ci.yml", "on: [push]\njobs:\n  t: {}\n")), { labels: { add: ["bug"] } })
    expect(changesOf(value)[0].status).toBe("approval")
    expect(reasonsOf(changesOf(value)[0])).toContain("ci.yml differs between the PR's head and main")
  })

  test("marks changes the PR already has or lacks as unchanged", async () => {
    const { f, head } = setup()
    const has = rules(head, [], { labels: [{ name: "bug" }], assignees: [{ login: "me" }], milestone: { title: "v1" } })
    const { value } = await judged(f, has, { labels: { add: ["bug"], remove: ["enhancement"] }, assignees: { add: ["@me"] }, milestone: "v1" })
    expect(changesOf(value).map((c) => [c.kind, c.value, c.status, c.reasons[0]])).toEqual([
      ["label", "bug", "unchanged", "already labeled"],
      ["label", "enhancement", "unchanged", "not labeled"],
      ["assignee", "me", "unchanged", "already assigned"],
      ["milestone", "v1", "unchanged", "milestone already set"],
    ])
    const bare = await judged(f, rules(head), { removeMilestone: true })
    expect(changesOf(bare.value)).toMatchObject([{ kind: "milestone", op: "remove", status: "unchanged", reasons: ["no milestone"] }])
  })

  test("refuses an inferred label gh would split on its comma", async () => {
    const { f, head } = setup()
    const { value } = await judged(f, rules(head, [mergedPrs(5, () => ({ labels: [{ name: "needs,care" }] }))]), {}, true)
    expect(changesOf(value)).toHaveLength(1)
    expect(changesOf(value)[0]).toMatchObject({ value: "needs,care", source: "habit", status: "invalid" })
  })

  test("infers your habitual assignee and labels from merged PRs", async () => {
    const { f, head } = setup()
    const merged = mergedPrs(6, (i) => ({
      title: i < 4 ? "feat: x" : "fix: y",
      labels: i < 4 ? [{ name: "enhancement" }] : [],
      assignees: i < 5 ? [{ login: "me" }] : [],
    }))
    const { value } = await judged(f, rules(head, [merged]), {}, true)
    expect(value.targets[0].habits).toMatchObject({ sample: 6, selfAssigned: 5, labels: [{ name: "enhancement", count: 4, of: 6, scope: "all" }] })
    expect(changesOf(value)).toEqual([
      { kind: "assignee", op: "add", value: "me", source: "habit", status: "harmless", reasons: [] },
      { kind: "label", op: "add", value: "enhancement", source: "habit", status: "harmless", reasons: [] },
    ])
  })

  test("infers a label from PRs of the same type when too few PRs overall carry it", async () => {
    const { f, head } = setup()
    const merged = mergedPrs(6, (i) => ({ title: i < 3 ? "feat(ui): x" : "fix: y", labels: i < 3 ? [{ name: "bug" }] : [] }))
    const { value } = await judged(f, rules(head, [merged]), {}, true)
    expect(value.targets[0].habits?.labels).toEqual([{ name: "bug", count: 3, of: 3, scope: "feat" }])
    expect(changesOf(value).map((c) => [c.kind, c.value, c.source])).toEqual([["label", "bug", "habit"]])
  })

  test("stops when the merged PRs to infer from cannot be read", async () => {
    const { f, head } = setup()
    await expect(judged(f, rules(head, [{ re: "^pr list --repo o/r --state merged", out: "HTTP 500", code: 1 }]), {}, true)).rejects.toThrow("merged PRs")
  })

  test("changes the digest with the consequences a pending change rests on", async () => {
    const { f, head } = setup()
    const milestoned = (types: string) => onDefault("m.yml", `on:\n  pull_request_target:\n    types: [${types}]\njobs:\n  t: {}\n`)
    const before = await judged(f, rules(head, milestoned("milestoned")), { milestone: "v1" })
    expect((await judged(f, rules(head, milestoned("milestoned")), { milestone: "v1" })).value.digest).toBe(before.value.digest)
    // A replaced milestone also fires demilestoned, and the PR's current milestone is part of what was approved.
    const after = await judged(f, rules(head, milestoned("milestoned, demilestoned"), { milestone: { title: "v0" } }), { milestone: "v1" })
    expect(after.value.digest).not.toBe(before.value.digest)
    expect((await judged(f, rules(head, milestoned("milestoned")), { milestone: "v1", labels: { add: ["bug"] } })).value.digest).not.toBe(before.value.digest)
  })

  describe("environment re-check", () => {
    const hook = JSON.stringify([[{ id: 9, active: true, events: ["pull_request"], config: { url: "https://ci.example.com/x" } }]])
    const recheck = async (f: Fixture, r: GhRule[]) => {
      const { value } = await withFakeGh(f, r, async () => {
        const a = await assessPr(f, { labels: { add: ["bug"] } })
        return { a, unchanged: await environmentUnchanged(REPO, a.shas, f.dir) }
      })
      return value
    }

    test("passes while branches, webhooks and rules read as they did", async () => {
      const { f, head } = setup()
      const res = await recheck(f, rules(head))
      expect(Object.keys(res.a.shas).sort()).toEqual(["@hooks", "@rules:main", "main"])
      expect(res.unchanged).toBe(true)
    })

    test("fails when a webhook appears between judging and applying", async () => {
      const { f, head } = setup()
      const res = await recheck(f, rules(head, [{ re: "^api --paginate --slurp repos/o/r/hooks", out: "[[]]", times: 1 }, { re: "^api --paginate --slurp repos/o/r/hooks", out: hook }]))
      expect(changesOf(res.a)[0].status).toBe("harmless")
      expect(res.unchanged).toBe(false)
    })

    test("fails when a ruleset mandating workflows appears between judging and applying", async () => {
      const { f, head } = setup()
      const mandate = { re: "^api --paginate --slurp repos/o/r/rules/branches/main", out: '[[{"type":"workflows"}]]' }
      const res = await recheck(f, rules(head, [{ re: "^api --paginate --slurp repos/o/r/rules/branches/main", out: "[[]]", times: 1 }, mandate]))
      expect(res.unchanged).toBe(false)
    })

    test("fails when the default branch moves between judging and applying", async () => {
      const { f, head } = setup()
      const res = await recheck(f, rules(head, [{ re: "^api repos/o/r/commits/main --jq", out: `${DEFAULT_SHA}\n`, times: 1 }, { re: "^api repos/o/r/commits/main --jq", out: `${MOVED_SHA}\n` }]))
      expect(res.unchanged).toBe(false)
    })

    test("fails when a branch commit has become unreadable", async () => {
      const { f, head } = setup()
      const res = await recheck(f, rules(head, [{ re: "^api repos/o/r/commits/main --jq", out: `${DEFAULT_SHA}\n`, times: 1 }, { re: "^api repos/o/r/commits/main --jq", code: 1 }]))
      expect(res.unchanged).toBe(false)
    })
  })

  describe("prTarget", () => {
    const read = (f: Fixture, r: GhRule[], n = "5") => withFakeGh(f, r, () => prTarget(REPO, n, f.dir)).then((res) => res.value)

    test("reads what the PR carries", async () => {
      const { f, head } = setup()
      const extra = {
        labels: [{ name: "bug" }],
        assignees: [{ login: "me" }],
        reviewRequests: [{ login: "alice" }, { slug: "core", organization: { login: "o" } }],
        milestone: { title: "v1" },
      }
      expect(await read(f, rules(head, [], extra))).toEqual({
        id: "#5",
        number: 5,
        headSha: head,
        base: "main",
        author: "author1",
        labels: ["bug"],
        assignees: ["me"],
        reviewers: ["alice", "o/core"],
        milestone: "v1",
        typeHint: "feat: thing",
      })
    })

    test("refuses a closed PR, a number that is not one, and a PR it cannot read", async () => {
      const { f, head } = setup()
      await expect(read(f, rules(head, [], { state: "MERGED" }))).rejects.toThrow("is MERGED")
      await expect(read(f, rules(head), "5; rm")).rejects.toThrow("not a PR number")
      await expect(read(f, [])).rejects.toThrow("Could not read PR #5")
    })
  })

  describe("applyChanges", () => {
    const change = (kind: Judged["kind"], op: Judged["op"], value: string): Judged => ({ kind, op, value, source: "request", status: "harmless", reasons: [] })

    test("passes one flag per value, and clears a milestone without a value", async () => {
      const { f, head } = setup()
      const { value, calls } = await withFakeGh(f, rules(head), async () => [
        await applyChanges(REPO, 5, [change("label", "remove", "bug"), change("reviewer", "add", "alice"), change("milestone", "add", "v1")], f.dir),
        await applyChanges(REPO, 5, [change("assignee", "remove", "me"), change("milestone", "remove", "")], f.dir),
        await applyChanges(REPO, 5, [], f.dir),
      ])
      expect(value.map((res) => res.ok)).toEqual([true, true, true])
      expect(value[2]).toEqual({ ok: true, output: "" })
      expect(calls.filter((c) => c.startsWith("pr edit"))).toEqual([
        "pr edit 5 --repo o/r --remove-label=bug --add-reviewer=alice --milestone=v1",
        "pr edit 5 --repo o/r --remove-assignee=me --remove-milestone",
      ])
    })

    test("reports a failed edit with gh's output", async () => {
      const { f, head } = setup()
      const { value } = await withFakeGh(f, rules(head, [{ re: "^pr edit", out: "could not add label", code: 1 }]), () =>
        applyChanges(REPO, 5, [change("label", "add", "bug")], f.dir),
      )
      expect(value.ok).toBe(false)
      expect(value.output).toContain("could not add label")
    })
  })
})
