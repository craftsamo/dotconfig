import { describe, expect, test } from "bun:test"
import { normalizeItem } from "./items"
import { readKind } from "./kind"
import { parseIssueRef, parseProjectRef, parseRepoRef, sameName } from "./refs"

// Pure helpers of the shared layer; the gh-backed paths are covered by the
// gh_issue and gh_project tool suites through the fake gh.

describe("refs", () => {
  test("parses issue references in every accepted form", () => {
    expect(parseIssueRef("12", "o/r")).toEqual({ repo: "o/r", number: 12 })
    expect(parseIssueRef("#12")).toEqual({ repo: undefined, number: 12 })
    expect(parseIssueRef("acme/web#7")).toEqual({ repo: "acme/web", number: 7 })
    expect(parseIssueRef("https://github.com/acme/web/issues/7#issuecomment-1")).toEqual({ repo: "acme/web", number: 7 })
    expect(parseIssueRef("https://github.com/acme/web/pull/9")).toEqual({ repo: "acme/web", number: 9 })
    expect(() => parseIssueRef("seven")).toThrow(/Not an issue reference/)
  })

  test("parses repository references", () => {
    expect(parseRepoRef("acme/web")).toBe("acme/web")
    expect(parseRepoRef("https://github.com/acme/web/")).toBe("acme/web")
    expect(parseRepoRef("git@github.com:acme/web.git")).toBe("acme/web")
    expect(() => parseRepoRef("web")).toThrow(/Not a repository reference/)
  })

  test("parses project references", () => {
    expect(parseProjectRef(undefined)).toEqual({ owner: undefined })
    expect(parseProjectRef(undefined, "acme")).toEqual({ owner: "acme" })
    expect(parseProjectRef("https://github.com/orgs/acme/projects/3/views/1")).toEqual({ owner: "acme", number: 3 })
    expect(parseProjectRef("https://github.com/users/me/projects/5")).toEqual({ owner: "me", number: 5 })
    expect(parseProjectRef("acme/3")).toEqual({ owner: "acme", number: 3 })
    expect(parseProjectRef("3", "acme")).toEqual({ owner: "acme", number: 3 })
    expect(parseProjectRef("Roadmap")).toEqual({ owner: undefined, title: "Roadmap" })
  })

  test("sameName ignores case and surrounding space", () => {
    expect(sameName(" In Progress", "in progress")).toBe(true)
    expect(sameName("Done", "Todo")).toBe(false)
  })
})

describe("items", () => {
  test("flattens field values and the content of an issue item", () => {
    const item = normalizeItem({
      id: "PVTI_1",
      isArchived: false,
      fieldValues: {
        nodes: [
          { text: "Thing", field: { name: "Title" } },
          { name: "In Progress", field: { name: "Status" } },
          { date: "2026-11-01", field: { name: "Target" } },
          { number: 3, field: { name: "Points" } },
          { title: "Sprint 2", startDate: "2026-10-20", duration: 14, field: { name: "Iteration" } },
          { milestone: { title: "v1" }, field: { name: "Milestone" } },
          { repository: { nameWithOwner: "acme/web" }, field: { name: "Repository" } },
          { labels: { nodes: [{ name: "type:bug" }] }, field: { name: "Labels" } },
          { users: { nodes: [{ login: "me" }] }, field: { name: "Assignees" } },
          {},
        ],
      },
      content: {
        __typename: "Issue",
        id: "I_1",
        number: 12,
        title: "Thing",
        url: "https://github.com/acme/web/issues/12",
        state: "OPEN",
        repository: { nameWithOwner: "acme/web" },
        milestone: { title: "v1" },
        issueType: null,
        labels: { nodes: [{ name: "type:bug" }] },
        assignees: { nodes: [{ login: "me" }] },
        parent: { number: 3, title: "Epic", url: "u", repository: { nameWithOwner: "acme/web" } },
        subIssuesSummary: { total: 2, completed: 1, percentCompleted: 50 },
      },
    })
    expect(item.fields).toEqual({
      Title: "Thing",
      Status: "In Progress",
      Target: "2026-11-01",
      Points: 3,
      Iteration: { title: "Sprint 2", startDate: "2026-10-20", duration: 14 },
      Milestone: "v1",
      Repository: "acme/web",
      Labels: ["type:bug"],
      Assignees: ["me"],
    })
    expect(item.content).toMatchObject({ type: "Issue", number: 12, repo: "acme/web", milestone: "v1", parent: { number: 3 }, subIssues: { total: 2, completed: 1, percent: 50 } })
  })

  test("keeps a draft's body and tolerates missing content", () => {
    expect(normalizeItem({ id: "PVTI_2", isArchived: true, fieldValues: { nodes: [] }, content: { __typename: "DraftIssue", id: "DI_1", title: "Note", body: "text" } })).toEqual({
      id: "PVTI_2",
      archived: true,
      fields: {},
      content: { type: "DraftIssue", id: "DI_1", title: "Note", body: "text" },
    })
    expect(normalizeItem({ id: "PVTI_3", fieldValues: null, content: null }).content).toBeNull()
  })
})

describe("kind", () => {
  test("reads the kind from an Issue Type first, then a type: label", () => {
    expect(readKind("Bug", ["type:feature"])).toBe("Bug")
    expect(readKind(null, ["area:web", "type:feature"])).toBe("feature")
    expect(readKind(null, [])).toBeNull()
  })
})
