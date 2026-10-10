import { afterEach, describe, expect, test } from "bun:test"
import { normalizeCheck, overall } from "./gh"
import { fixture, runWithFakeGh, type Fixture, type GhRule } from "./testing/repo"

const fixtures: Fixture[] = []
afterEach(() => {
  while (fixtures.length) fixtures.pop()!.cleanup()
})
const status = (args: Record<string, unknown>, rules: GhRule[]) => {
  const f = fixture()
  fixtures.push(f)
  return runWithFakeGh(f, { module: "gh", name: "pr_status", args }, rules)
}

const run = (name: string, conclusion: string | null, job = 1) => ({
  __typename: "CheckRun",
  name,
  workflowName: "CI",
  status: conclusion ? "COMPLETED" : "IN_PROGRESS",
  conclusion: conclusion ?? "",
  detailsUrl: `https://github.com/o/r/actions/runs/9/job/${job}`,
})
const view = (rollup: unknown[], extra: Record<string, unknown> = {}) =>
  JSON.stringify({
    number: 7,
    title: "Thing",
    url: "https://github.com/o/r/pull/7",
    state: "OPEN",
    isDraft: false,
    baseRefName: "main",
    headRefName: "feat/x",
    headRefOid: "abc",
    mergeable: "MERGEABLE",
    mergeStateStatus: "CLEAN",
    reviewDecision: "",
    closingIssuesReferences: [{ number: 12 }],
    statusCheckRollup: rollup,
    latestReviews: [{ author: { login: "rev" }, state: "COMMENTED", body: "nit" }],
    ...extra,
  })
const threads = JSON.stringify({
  data: {
    repository: {
      pullRequest: {
        reviewThreads: {
          nodes: [
            { isResolved: true, isOutdated: false, path: "a.ts", line: 1, comments: { nodes: [{ body: "done" }] } },
            { isResolved: false, isOutdated: false, path: "b.ts", line: 4, comments: { nodes: [{ author: { login: "rev" }, body: "fix this", url: "u" }] } },
          ],
        },
      },
    },
  },
})

describe("normalizeCheck / overall", () => {
  test("folds check runs and commit statuses into buckets", () => {
    expect(normalizeCheck(run("a", "SUCCESS")).bucket).toBe("pass")
    expect(normalizeCheck(run("a", "TIMED_OUT")).bucket).toBe("fail")
    expect(normalizeCheck(run("a", "SKIPPED")).bucket).toBe("skipping")
    expect(normalizeCheck(run("a", null)).bucket).toBe("pending")
    expect(normalizeCheck({ __typename: "StatusContext", context: "ci/x", state: "ERROR", targetUrl: "t" })).toEqual({
      name: "ci/x",
      workflow: null,
      bucket: "fail",
      state: "ERROR",
      url: "t",
    })
    expect(overall([])).toBe("no_checks")
    expect(overall([normalizeCheck(run("a", "SUCCESS")), normalizeCheck(run("b", null))])).toBe("pending")
    expect(overall([normalizeCheck(run("a", "FAILURE")), normalizeCheck(run("b", null))])).toBe("fail")
  })
})

describe("gh_pr_status", () => {
  test("reports the PR, its checks, reviews and unresolved threads", () => {
    const res = status({}, [
      { re: "^pr view --json number", out: view([run("test", "SUCCESS"), run("lint", "SKIPPED")]) },
      { re: "^api graphql", out: threads },
    ])
    expect(res.out).toMatchObject({
      pr: { number: 7, head: "feat/x", headSha: "abc" },
      mergeable: "MERGEABLE",
      closingIssues: [12],
      checks: { overall: "pass", counts: { pass: 1, skipping: 1, fail: 0 } },
      failedLogs: [],
      reviews: [{ author: "rev", state: "COMMENTED" }],
      unresolvedThreads: [{ path: "b.ts", line: 4, author: "rev", body: "fix this" }],
      waited: { polls: 1, endedBy: "not_waiting" },
    })
  })

  test("reads the failed job's log, not the aggregate gate's", () => {
    const res = status({ reviews: false }, [
      { re: "^pr view", out: view([run("test (web)", "FAILURE", 11), run("Required checks", "FAILURE", 12)]) },
      { re: "^run view --job 11 --log-failed --repo o/r", out: "test (web)\tRun tests\t2026 ok line\ntest (web)\tRun tests\t2026 ##[error]Expected 1 to be 2\n" },
    ])
    expect(res.out.checks.overall).toBe("fail")
    expect(res.out.failedLogs).toEqual([
      { name: "test (web)", job: "11", url: "https://github.com/o/r/actions/runs/9/job/11", errors: ["2026 ##[error]Expected 1 to be 2"], tail: "2026 ok line\n2026 ##[error]Expected 1 to be 2" },
    ])
    expect(res.calls.some((c) => c.includes("--job 12"))).toBe(false)
  })

  test("waits through missing and pending checks until they settle", () => {
    const res = status({ wait: true, intervalSec: 1, reviews: false }, [
      { re: "^pr view", out: view([]), times: 1 },
      { re: "^pr view", out: view([run("test", null)]), times: 1 },
      { re: "^pr view", out: view([run("test", "SUCCESS")]) },
    ])
    expect(res.out.checks.overall).toBe("pass")
    expect(res.out.waited).toMatchObject({ polls: 3, endedBy: "complete" })
  })

  test("stops at the first failure, and gives up on checks that never appear", () => {
    const failed = status({ wait: true, intervalSec: 1, reviews: false, logLines: 0 }, [
      { re: "^pr view", out: view([run("a", "FAILURE"), run("b", null)]) },
    ])
    expect(failed.out.waited).toMatchObject({ polls: 1, endedBy: "failed" })

    const none = status({ wait: true, intervalSec: 1, noChecksGraceSec: 1, reviews: false }, [
      { re: "^pr view", out: view([], { mergeable: "CONFLICTING" }) },
    ])
    expect(none.out.waited.endedBy).toBe("no_checks")
    expect(none.out.hints[0]).toMatch(/conflicts with its base/)
  })

  test("times out while checks stay pending", () => {
    const res = status({ wait: true, intervalSec: 1, timeoutSec: 1, reviews: false }, [{ re: "^pr view", out: view([run("slow", null)]) }])
    expect(res.out.waited.endedBy).toBe("timeout")
    expect(res.out.checks.overall).toBe("pending")
  })
})
