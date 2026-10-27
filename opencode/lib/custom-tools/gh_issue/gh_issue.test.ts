import { afterEach, describe as suite, expect, test } from "bun:test"
import { load, skip } from "../testing/deps"
import { currentRepo, gql, issueDetail, issueUrl, linkedProjects, orgIssueTypes, ownerProjects, ownerType, projectFields, repoContext, STANDARD_FIELDS } from "../testing/github-rules"
import type { Fixture, GhRule } from "../testing/repo"

const describe = suite.skipIf(skip)
const { fixture, runWithFakeGh } = await load(() => import("../testing/repo"))

const fixtures: Fixture[] = []
afterEach(() => {
  while (fixtures.length) fixtures.pop()!.cleanup()
})
const call = (name: string, args: Record<string, unknown>, rules: GhRule[]) => {
  const f = fixture()
  fixtures.push(f)
  return runWithFakeGh(f, { module: "gh_issue", name, args }, rules)
}
const REPO = "me/web"
const ORG_REPO = "acme/web"
const search = (nodes: unknown[]) => ({ re: "search\\(type:ISSUE", out: gql({ search: { issueCount: nodes.length, pageInfo: { hasNextPage: false, endCursor: null }, nodes } }) })

describe("gh_issue_view", () => {
  test("reads the whole picture of an issue from the current repository", () => {
    const res = call("view", { issue: "12" }, [
      currentRepo(REPO),
      ...repoContext(REPO),
      ...issueDetail({ repo: REPO, number: 12, title: "Thing", labels: ["type:bug"], parent: 3, subIssues: [13, 14], blockedBy: [11], linkedBranches: ["12-thing"], projects: [{ itemId: "PVTI_1", number: 5, title: "Roadmap" }] }),
    ])
    expect(res.ok).toBe(true)
    expect(res.out).toMatchObject({
      repo: REPO,
      foreign: false,
      issue: { number: 12, title: "Thing", kind: "bug", parent: { number: 3 }, subIssues: [{ number: 13 }, { number: 14 }], blockedBy: [{ number: 11 }], linkedBranches: ["12-thing"], projects: [{ itemId: "PVTI_1", number: 5 }] },
    })
  })

  test("takes owner/repo#N and keeps the picture when the dependencies query is refused", () => {
    const res = call("view", { issue: `${ORG_REPO}#7` }, [
      ...repoContext(ORG_REPO, { type: "Organization", viewer: "me", member: false }),
      issueDetail({ repo: ORG_REPO, number: 7, issueType: "Bug" })[0],
      { re: "blockedBy\\(first:50\\)", code: 1, out: "" },
    ])
    expect(res.ok).toBe(true)
    expect(res.out).toMatchObject({ repo: ORG_REPO, foreign: true, issue: { number: 7, kind: "Bug", blockedBy: [], blocking: [] } })
    expect(res.calls.some((c) => c.startsWith("repo view"))).toBe(false)
  })
})

describe("gh_issue_list", () => {
  test("builds the search from the filters, with kind as a type on an organization and a label elsewhere", () => {
    const org = call("list", { repo: ORG_REPO, kind: "bug", milestone: "v1", assignee: "@me", query: "sort:updated-desc" }, [
      ...repoContext(ORG_REPO, { type: "Organization" }),
      orgIssueTypes(["Bug", "Feature"]),
      search([{ number: 1, title: "A", url: issueUrl(ORG_REPO, 1), state: "OPEN", updatedAt: "t", issueType: { name: "Bug" }, labels: { nodes: [] }, assignees: { nodes: [] }, milestone: { title: "v1" }, parent: null, subIssuesSummary: null }]),
    ])
    expect(org.out.query).toBe(`repo:${ORG_REPO} state:open type:"Bug" milestone:"v1" assignee:@me sort:updated-desc`)
    expect(org.out.issues).toEqual([{ number: 1, title: "A", url: issueUrl(ORG_REPO, 1), state: "OPEN", kind: "Bug", labels: [], assignees: [], milestone: "v1", parent: null, subIssues: null, updatedAt: "t" }])

    const user = call("list", { repo: REPO, kind: "bug", state: "all", milestone: "none" }, [...repoContext(REPO), search([])])
    expect(user.out.query).toBe(`repo:${REPO} label:"type:bug" no:milestone`)
  })

  test("lists a parent's sub-issues instead of searching", () => {
    const res = call("list", { repo: REPO, parent: "3", state: "all" }, [...repoContext(REPO), ...issueDetail({ repo: REPO, number: 3, subIssues: [4, 5] })])
    expect(res.out).toMatchObject({ parent: { number: 3 }, count: 2, issues: [{ number: 4 }, { number: 5 }] })
    expect(res.calls.some((c) => c.includes("search(type:ISSUE"))).toBe(false)
  })
})

describe("gh_issue_create", () => {
  test("creates the issue, then settles kind, parent, dependency and board in order", () => {
    const res = call(
      "create",
      { title: "New", body: "b", repo: ORG_REPO, kind: "feature", milestone: "v1", createMilestone: true, parent: "3", blockedBy: ["2"], addToProject: true, fields: { Status: "Todo" } },
      [
        ...repoContext(ORG_REPO, { type: "Organization" }),
        { re: "^api --paginate --slurp repos/acme/web/milestones\\?state=all", out: "[[]]" },
        { re: "^api repos/acme/web/milestones -f title=v1", out: JSON.stringify({ number: 9, title: "v1" }) },
        { re: "^issue create --title New", out: `${issueUrl(ORG_REPO, 20)}\n` },
        orgIssueTypes(["Feature"]),
        { re: "^issue view 20 --json labels", out: JSON.stringify({ labels: [] }) },
        { re: "^issue edit 20 --type Feature", out: "" },
        ...issueDetail({ repo: ORG_REPO, number: 20 }),
        { re: "^issue edit 20 --parent", out: "" },
        { re: "^issue edit 20 --add-blocked-by", out: "" },
        linkedProjects([{ owner: "acme", type: "Organization", number: 4 }]),
        { re: "^project item-add 4 --owner acme --url", out: JSON.stringify({ id: "PVTI_9" }) },
        projectFields(STANDARD_FIELDS),
        { re: "^project item-edit --id PVTI_9 .* --single-select-option-id OPT_Todo", out: "" },
      ],
    )
    expect(res.ok).toBe(true)
    expect(res.out).toMatchObject({
      issue: { number: 20, url: issueUrl(ORG_REPO, 20) },
      kind: { via: "type", name: "Feature", removedLabels: [] },
      milestone: { number: 9, created: true },
      relations: { parent: { set: `${ORG_REPO}#3` }, blockedBy: { added: [`${ORG_REPO}#2`], unchanged: [] }, otherRepos: [] },
      board: { project: { number: 4, route: "linked" }, itemId: "PVTI_9", fieldsApplied: ["Status"] },
      errors: {},
    })
    expect(res.calls.find((c) => c.startsWith("issue create"))).toContain("--milestone v1")
  })

  test("labels the kind on a user repository, creating the label once", () => {
    const res = call("create", { title: "Bug", repo: REPO, kind: "bug" }, [
      ...repoContext(REPO),
      { re: "^issue create", out: `${issueUrl(REPO, 2)}\n` },
      { re: "^issue view 2 --json labels", out: JSON.stringify({ labels: [] }) },
      { re: "^label list", out: "[]" },
      { re: "^label create type:bug --color D73A4A", out: "" },
      { re: "^issue edit 2 --add-label type:bug", out: "" },
    ])
    expect(res.out.kind).toEqual({ kind: "bug", via: "label", name: "type:bug", removedLabels: [] })
  })

  test("keeps the issue in the result when a later step fails", () => {
    const res = call("create", { title: "x", repo: REPO, parent: "99" }, [
      ...repoContext(REPO),
      { re: "^issue create", out: `${issueUrl(REPO, 3)}\n` },
      ...issueDetail({ repo: REPO, number: 3 }),
      { re: "^issue edit 3 --parent", code: 1, out: "" },
    ])
    expect(res.ok).toBe(true)
    expect(res.out).toMatchObject({ ok: false, issue: { number: 3 }, relations: null })
    expect(res.out.errors.relations).toMatch(/--parent/)
  })

  test("refuses without write permission", () => {
    const res = call("create", { title: "x", repo: REPO }, [...repoContext(REPO, { permission: "READ" })])
    expect(res.ok).toBe(false)
    expect(res.error).toMatch(/No write permission on me\/web/)
    expect(res.calls.some((c) => c.startsWith("issue create"))).toBe(false)
  })
})

describe("gh_issue_update", () => {
  test("edits in one gh call, appends to the body, and closes only with a reason", () => {
    const res = call("update", { issue: "5", repo: REPO, appendBody: "## Decision\nship it", addLabels: ["area:web"], milestone: "", comment: "done", state: "closed", reason: "completed" }, [
      ...repoContext(REPO),
      ...issueDetail({ repo: REPO, number: 5, body: "Spec\n" }),
      { re: "^issue edit 5 --repo me/web --body Spec\\n\\n## Decision\\nship it\\n --add-label area:web --remove-milestone$", out: "" },
      { re: "^issue comment 5 --body done", out: "" },
      { re: "^issue close 5 --reason completed", out: "" },
    ])
    expect(res.ok).toBe(true)
    expect(res.out.changed).toEqual(["body (appended)", "labels", "milestone", "comment", "closed (completed)"])

    const noReason = call("update", { issue: "5", repo: REPO, state: "closed" }, [...repoContext(REPO)])
    expect(noReason.ok).toBe(false)
    expect(noReason.error).toMatch(/Closing needs `reason`/)
  })

  test("switching the kind takes the old type: label off, and falls back to a label when --type is refused", () => {
    const switched = call("update", { issue: "6", repo: REPO, kind: "bug" }, [
      ...repoContext(REPO),
      { re: "^issue view 6 --json labels", out: JSON.stringify({ labels: [{ name: "type:feature" }, { name: "area:web" }] }) },
      { re: "^label list", out: JSON.stringify([{ name: "type:bug" }]) },
      { re: "^issue edit 6 --add-label type:bug", out: "" },
      { re: "^issue edit 6 --remove-label type:feature", out: "" },
    ])
    expect(switched.out.kind).toEqual({ kind: "bug", via: "label", name: "type:bug", removedLabels: ["type:feature"] })

    const oldGh = call("update", { issue: "6", repo: ORG_REPO, kind: "bug" }, [
      ...repoContext(ORG_REPO, { type: "Organization" }),
      orgIssueTypes(["Bug"]),
      { re: "^issue view 6 --json labels", out: JSON.stringify({ labels: [] }) },
      { re: "^issue edit 6 --type Bug", code: 1, out: "unknown flag: --type" },
      { re: "^label list", out: "[]" },
      { re: "^label create type:bug", out: "" },
      { re: "^issue edit 6 --add-label type:bug", out: "" },
    ])
    expect(oldGh.out.kind).toMatchObject({ via: "label", name: "type:bug", note: expect.stringContaining("labelled instead") })
  })
})

describe("gh_issue_relate", () => {
  test("skips relations already in place, sends the rest as URLs, and checks the other repository", () => {
    const res = call("relate", { issue: "3", repo: REPO, parent: "1", addSubIssues: ["4", "5"], removeSubIssues: ["6", "7"], addBlockedBy: [`${ORG_REPO}#9`] }, [
      ...repoContext(REPO),
      ...repoContext(ORG_REPO, { type: "Organization", viewer: "me", member: false, permission: "WRITE" }),
      ...issueDetail({ repo: REPO, number: 3, parent: 1, subIssues: [4, 7] }),
      { re: "^issue edit 3 --add-sub-issue " + issueUrl(REPO, 5), out: "" },
      { re: "^issue edit 3 --remove-sub-issue " + issueUrl(REPO, 7), out: "" },
      { re: "^issue edit 3 --add-blocked-by " + issueUrl(ORG_REPO, 9), out: "" },
    ])
    expect(res.ok).toBe(true)
    expect(res.out).toMatchObject({
      parent: { unchanged: `${REPO}#1` },
      subIssues: { added: [`${REPO}#5`], removed: [`${REPO}#7`], unchanged: [`${REPO}#4`, `${REPO}#6`] },
      blockedBy: { added: [`${ORG_REPO}#9`] },
      otherRepos: [{ repo: ORG_REPO, foreign: true }],
    })
    expect(res.calls.filter((c) => c.startsWith("issue edit"))).toHaveLength(3)
  })

  test("folds a duplicate GitHub refuses into unchanged, and refuses dependencies it could not read", () => {
    const dup = call("relate", { issue: "3", repo: REPO, addSubIssues: ["8"] }, [
      ...repoContext(REPO),
      ...issueDetail({ repo: REPO, number: 3 }),
      { re: "^issue edit 3 --add-sub-issue", code: 1, out: "GraphQL: Issue may not contain duplicate sub-issues" },
    ])
    expect(dup.out.subIssues).toEqual({ added: [], removed: [], unchanged: [`${REPO}#8`] })

    const noDeps = call("relate", { issue: "3", repo: REPO, addBlockedBy: ["2"] }, [
      ...repoContext(REPO),
      issueDetail({ repo: REPO, number: 3 })[0],
      { re: "blockedBy\\(first:50\\)", code: 1, out: "" },
    ])
    expect(noDeps.ok).toBe(false)
    expect(noDeps.error).toMatch(/Could not read the issue's dependencies/)
  })
})

describe("gh_issue_develop", () => {
  test("reuses a linked branch, else verifies the base and creates one", () => {
    const reused = call("develop", { issue: "8", repo: REPO, checkout: true }, [...repoContext(REPO), ...issueDetail({ repo: REPO, number: 8, linkedBranches: ["8-thing"] })])
    expect(reused.out).toMatchObject({ created: false, branch: "8-thing" })

    const created = call("develop", { issue: "8", repo: REPO, base: "release" }, [
      ...repoContext(REPO),
      ...issueDetail({ repo: REPO, number: 8 }),
      { re: "^api repos/me/web/branches/release", out: "{}" },
      { re: "^issue develop 8 --repo me/web --base release", out: "github.com/me/web/tree/8-thing\n" },
    ])
    expect(created.out).toMatchObject({ created: true, branch: "8-thing", base: "release" })

    const badBase = call("develop", { issue: "8", repo: REPO, base: "nope" }, [...repoContext(REPO), ...issueDetail({ repo: REPO, number: 8 }), { re: "^api repos/me/web/branches/nope", code: 1 }])
    expect(badBase.ok).toBe(false)
    expect(badBase.error).toMatch(/not found on me\/web/)
  })
})

describe("the session's permission gate", () => {
  const gated = (gate: "record" | "deny" | "hermes") => (name: string, args: Record<string, unknown>, rules: GhRule[]) => {
    const f = fixture()
    fixtures.push(f)
    return runWithFakeGh(f, { module: "gh_issue", name, args, gate }, rules)
  }
  const rules = [...repoContext(REPO), { re: "^issue edit 5 --repo me/web --body tick", out: "" }]

  test("a write asserts with the tool id, the issue and what it changes before gh runs", () => {
    const res = gated("record")("update", { issue: "5", repo: REPO, body: "tick" }, rules)
    expect(res.ok).toBe(true)
    expect(res.asserted).toEqual([{ action: "gh_issue_update", resources: [`${REPO}#5`], metadata: { op: "issue_edit", repo: REPO, number: 5, body: "tick" }, message: undefined }])
    expect(res.calls.some((c) => c.startsWith("issue edit"))).toBe(true)
  })

  test("a refused assertion stops the write before gh runs", () => {
    const res = gated("deny")("update", { issue: "5", repo: REPO, body: "tick" }, rules)
    expect(res.ok).toBe(false)
    expect(res.error).toMatch(/permission denied/)
    expect(res.calls.some((c) => c.startsWith("issue edit"))).toBe(false)
  })

  test("a session driven by Hermes gets no write on a runtime without the gate", () => {
    const res = gated("hermes")("update", { issue: "5", repo: REPO, body: "tick" }, rules)
    expect(res.ok).toBe(false)
    expect(res.error).toMatch(/driven by Hermes/)
    expect(res.calls.some((c) => c.startsWith("issue edit"))).toBe(false)
    const develop = gated("record")("develop", { issue: "8", repo: REPO, branch: "task/issue-8", base: "main" }, [
      ...repoContext(REPO),
      ...issueDetail({ repo: REPO, number: 8 }),
      { re: "^api repos/me/web/branches/main", out: "{}" },
      { re: "^issue develop 8 --repo me/web --name task/issue-8 --base main", out: "github.com/me/web/tree/task/issue-8\n" },
    ])
    expect(develop.asserted).toEqual([{ action: "gh_issue_develop", resources: [`${REPO}#8`, REPO], metadata: { op: "issue_develop", repo: REPO, number: 8, branch: "task/issue-8", base: "main", branch_repo: REPO }, message: undefined }])
  })
})

describe("project resolution through gh_issue_create", () => {
  test("falls through linked → org → user and reports the routes considered", () => {
    const res = call("create", { title: "x", repo: ORG_REPO, addToProject: true }, [
      ...repoContext(ORG_REPO, { type: "Organization" }),
      { re: "^issue create", out: `${issueUrl(ORG_REPO, 1)}\n` },
      linkedProjects([{ owner: "acme", type: "Organization", number: 4, canUpdate: false }]),
      ownerType("acme", "Organization"),
      ownerProjects("organization", []),
      ownerProjects("viewer", [{ owner: "me", number: 2 }]),
      { re: "^project item-add 2 --owner me --url", out: JSON.stringify({ id: "PVTI_2" }) },
    ])
    expect(res.ok).toBe(true)
    expect(res.out.board).toMatchObject({ project: { owner: "me", number: 2, route: "user" }, itemId: "PVTI_2" })
  })

  test("refuses to pick among several writable linked boards without a title", () => {
    const res = call("create", { title: "x", repo: REPO, addToProject: true }, [
      ...repoContext(REPO),
      { re: "^issue create", out: `${issueUrl(REPO, 1)}\n` },
      linkedProjects([
        { owner: "me", number: 1, title: "Alpha" },
        { owner: "me", number: 2, title: "Beta" },
      ]),
    ])
    expect(res.out.board).toBeNull()
    expect(res.out.errors.board).toMatch(/2 writable projects are linked to me\/web/)

    const titled = call("create", { title: "x", repo: REPO, addToProject: true, project: "Beta" }, [
      ...repoContext(REPO),
      { re: "^issue create", out: `${issueUrl(REPO, 1)}\n` },
      linkedProjects([
        { owner: "me", number: 1, title: "Alpha" },
        { owner: "me", number: 2, title: "Beta" },
      ]),
      { re: "^project item-add 2 --owner me --url", out: JSON.stringify({ id: "PVTI_2" }) },
    ])
    expect(titled.out.board).toMatchObject({ project: { number: 2, route: "linked" } })
  })

  test("fails with the routes considered when no board resolves", () => {
    const res = call("create", { title: "x", repo: REPO, addToProject: true }, [
      ...repoContext(REPO),
      { re: "^issue create", out: `${issueUrl(REPO, 1)}\n` },
      linkedProjects([]),
      ownerProjects("viewer", []),
    ])
    expect(res.out.ok).toBe(false)
    expect(res.out.errors.board).toMatch(/linked: no project linked to the repository; org: repository is user-owned; user: no project titled "Roadmap"/)
  })
})
