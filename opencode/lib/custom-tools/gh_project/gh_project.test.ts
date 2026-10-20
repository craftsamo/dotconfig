import { afterEach, describe as suite, expect, test } from "bun:test"
import { load, skip } from "../testing/deps"
import {
  currentRepo,
  gql,
  issueUrl,
  linkedProjects,
  ownerProjects,
  ownerType,
  projectFields,
  projectItem,
  projectItems,
  projectNode,
  projectNodeById,
  projectViews,
  repoContext,
  STANDARD_FIELDS,
} from "../testing/github-rules"
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
  return runWithFakeGh(f, { module: "gh_project", name, args }, rules)
}
const REPO = "me/web"
const BOARD = { owner: "me", number: 5 }
const PVT = projectNode(BOARD).id

describe("gh_project_resolve", () => {
  test("reports the board, the route taken, the routes considered and the fields", () => {
    const res = call("resolve", {}, [
      currentRepo(REPO),
      ...repoContext(REPO),
      linkedProjects([]),
      ownerProjects("viewer", [BOARD]),
      projectFields(STANDARD_FIELDS),
    ])
    expect(res.ok).toBe(true)
    expect(res.out).toMatchObject({
      project: { number: 5, owner: "me", viewerCanUpdate: true },
      route: "user",
      considered: [{ route: "linked" }, { route: "org", outcome: "repository is user-owned" }, { route: "user" }],
      repo: REPO,
    })
    expect(res.out.fields.map((f: any) => f.name)).toEqual(["Title", "Status", "Milestone", "Target"])
    expect(res.out.fields[1].options).toEqual(["Todo", "In Progress", "Done"])
  })

  test("pins a project by URL without a repository", () => {
    const res = call("resolve", { project: "https://github.com/orgs/acme/projects/3" }, [
      { re: "^repo view", code: 1 },
      ownerType("acme", "Organization"),
      { re: "organization\\(login:\\$login\\)\\{projectV2\\(number:\\$n\\)", out: gql({ organization: { projectV2: projectNode({ owner: "acme", type: "Organization", number: 3, title: "Team" }) } }) },
      projectFields([]),
    ])
    expect(res.out).toMatchObject({ project: { number: 3, owner: "acme", ownerType: "Organization", title: "Team" }, route: "explicit", repo: null })
  })
})

describe("gh_project_create", () => {
  test("creates the board, brings it to the standard shape and links the repository", () => {
    const res = call("create", { owner: "@me", linkRepo: "current" }, [
      { re: "^api graphql -f query=query\\{viewer\\{login\\}\\}", out: gql({ viewer: { login: "me" } }) },
      ownerType("me", "User"),
      ownerProjects("user", []),
      { re: "^project create --owner me --title Roadmap", out: JSON.stringify({ id: PVT, number: 5 }) },
      projectNodeById(BOARD),
      { re: "fields\\(first:50,after:\\$after\\)", times: 1, out: gql({ node: { fields: { pageInfo: {}, nodes: [{ __typename: "ProjectV2SingleSelectField", id: "F_Status", name: "Status", dataType: "SINGLE_SELECT", options: [{ id: "OPT_Todo", name: "Todo", color: "GRAY" }, { id: "OPT_Done", name: "Done", color: "GREEN" }] }] } } }) },
      { re: "updateProjectV2Field.*name:\"In Progress\".*name:\"Cancelled\"", out: gql({}) },
      // The field list grows as create reads it back after each change.
      { ...projectFields([{ name: "Status", dataType: "SINGLE_SELECT", options: ["Todo", "In Progress", "Done", "Cancelled"] }]), times: 1 },
      { ...projectFields([{ name: "Status", dataType: "SINGLE_SELECT", options: ["Todo", "In Progress", "Done", "Cancelled"] }, { name: "Start", dataType: "DATE" }]), times: 2 },
      projectFields([{ name: "Status", dataType: "SINGLE_SELECT", options: ["Todo", "In Progress", "Done", "Cancelled"] }, { name: "Start", dataType: "DATE" }, { name: "Target", dataType: "DATE" }]),
      { re: "^project field-create 5 --owner me --name Start --data-type DATE", out: "" },
      { re: "^project field-create 5 --owner me --name Target --data-type DATE", out: "" },
      projectViews(["Roadmap"]),
      { re: "^api -H X-GitHub-Api-Version: 2026-03-10 /users/me/projectsV2/5/fields --paginate", out: JSON.stringify([{ id: 1, name: "Title" }, { id: 2, name: "Status" }, { id: 3, name: "Assignees" }, { id: 4, name: "Repository" }, { id: 5, name: "Milestone" }, { id: 6, name: "Parent issue" }, { id: 7, name: "Sub-issues progress" }]) },
      { re: "^api --method POST -H X-GitHub-Api-Version: 2026-03-10 /users/me/projectsV2/5/views -f name=Kanban -f layout=board -f filter=-status:Done -status:Cancelled -F visible_fields\\[\\]=1 -F visible_fields\\[\\]=3 -F visible_fields\\[\\]=4 -F visible_fields\\[\\]=6$", out: "{}" },
      { re: "^api --method POST .*/views -f name=Backlog -f layout=table .* -F visible_fields\\[\\]=1 -F visible_fields\\[\\]=2 -F visible_fields\\[\\]=4 -F visible_fields\\[\\]=5 -F visible_fields\\[\\]=6 -F visible_fields\\[\\]=7$", out: "{}" },
      currentRepo(REPO),
      ...repoContext(REPO),
      { re: "^project link 5 --owner me --repo me/web", out: "" },
    ])
    expect(res.ok).toBe(true)
    expect(res.out).toMatchObject({
      createdNew: true,
      project: { number: 5, owner: "me" },
      fields: { Status: { addedOptions: ["In Progress", "Cancelled"] }, Start: "created", Target: "created" },
      views: { Kanban: "created (columns not on the board: Target)", Backlog: "created (columns not on the board: Target)", Roadmap: "exists" },
      linked: REPO,
    })
  })

  test("reuses an existing board of that title", () => {
    const res = call("create", { owner: "me", views: false }, [
      ownerType("me", "User"),
      ownerProjects("user", [BOARD]),
      projectFields([{ name: "Status", dataType: "SINGLE_SELECT", options: ["Todo", "In Progress", "Done", "Cancelled"] }, { name: "Start", dataType: "DATE" }, { name: "Target", dataType: "DATE" }]),
    ])
    expect(res.out).toMatchObject({ createdNew: false, fields: {}, views: {}, linked: null })
    expect(res.calls.some((c) => c.startsWith("project create"))).toBe(false)
  })
})

describe("gh_project_link", () => {
  test("links once and reports an existing link as unchanged", () => {
    const rules = [
      ...repoContext(REPO),
      ownerType("me", "User"),
      ownerProjects("user", [BOARD]),
      { re: "projectsV2\\(first:50\\)\\{nodes\\{id\\}\\}", out: gql({ repository: { projectsV2: { nodes: [] } } }) },
      { re: "^project link 5 --owner me --repo me/web", out: "" },
    ]
    const first = call("link", { project: "Roadmap", owner: "me", repo: REPO }, rules)
    expect(first.out).toMatchObject({ unchanged: false, linked: true })
    const again = call("link", { project: "Roadmap", owner: "me", repo: REPO }, [...rules.slice(0, 3), { re: "projectsV2\\(first:50\\)\\{nodes\\{id\\}\\}", out: gql({ repository: { projectsV2: { nodes: [{ id: PVT }] } } }) }])
    expect(again.out).toMatchObject({ unchanged: true, linked: true })
  })
})

describe("gh_project_field_ensure / view_ensure", () => {
  test("creates a field with colored options, tops up options later, and refuses built-in names", () => {
    const base = [...repoContext(REPO), linkedProjects([BOARD])]
    const created = call("field_ensure", { name: "Area", dataType: "SINGLE_SELECT", options: ["Web:BLUE", "Infra"], repo: REPO }, [
      ...base,
      { re: "fields\\(first:50,after:\\$after\\)", times: 1, out: gql({ node: { fields: { pageInfo: {}, nodes: [] } } }) },
      { re: "^project field-create 5 --owner me --name Area --data-type SINGLE_SELECT --single-select-options Web,Infra$", out: "" },
      projectFields([{ name: "Area", dataType: "SINGLE_SELECT", options: ["Web", "Infra"] }]),
      { re: "updateProjectV2Field.*name:\"Web\",color:BLUE.*name:\"Infra\",color:GRAY", out: gql({}) },
    ])
    expect(created.out).toMatchObject({ created: true, addedOptions: [], route: "linked" })

    const topped = call("field_ensure", { name: "Area", dataType: "SINGLE_SELECT", options: ["Web", "Docs"], repo: REPO }, [
      ...base,
      projectFields([{ name: "Area", dataType: "SINGLE_SELECT", options: ["Web", "Infra"] }]),
      { re: "updateProjectV2Field.*id:\"OPT_Web\".*id:\"OPT_Infra\".*name:\"Docs\"", out: gql({}) },
    ])
    expect(topped.out).toMatchObject({ created: false, addedOptions: ["Docs"] })

    const builtin = call("field_ensure", { name: "Milestone", dataType: "TEXT", repo: REPO }, [...base, projectFields([])])
    expect(builtin.ok).toBe(false)
    expect(builtin.error).toMatch(/built-in field name/)
  })

  test("refuses a field that exists with another type, and an option name with a comma", () => {
    const base = [...repoContext(REPO), linkedProjects([BOARD])]
    const mismatch = call("field_ensure", { name: "Target", dataType: "TEXT", repo: REPO }, [...base, projectFields(STANDARD_FIELDS)])
    expect(mismatch.error).toMatch(/exists as DATE, not TEXT/)
    const comma = call("field_ensure", { name: "Area", dataType: "SINGLE_SELECT", options: ["Web, Mobile"], repo: REPO }, [...base, projectFields([])])
    expect(comma.error).toMatch(/contains a comma/)
  })

  test("creates a missing view and leaves an existing one alone", () => {
    const base = [...repoContext(REPO), linkedProjects([BOARD])]
    const exists = call("view_ensure", { name: "kanban", layout: "board", repo: REPO }, [...base, projectViews(["Kanban"])])
    expect(exists.out).toMatchObject({ created: false, view: "kanban" })
    const made = call("view_ensure", { name: "Bugs", layout: "table", filter: "label:type:bug", repo: REPO }, [
      ...base,
      projectViews(["Kanban"]),
      { re: "^api --method POST -H X-GitHub-Api-Version: 2026-03-10 /users/me/projectsV2/5/views -f name=Bugs -f layout=table -f filter=label:type:bug$", out: "{}" },
    ])
    expect(made.out).toMatchObject({ created: true, view: "Bugs", skippedFields: [] })
  })

  test("reports columns the board lacks, and retries a user board's views route with the numeric id", () => {
    const res = call("view_ensure", { name: "Bugs", layout: "table", visibleFields: ["Title", "Nope"], repo: REPO }, [
      ...repoContext(REPO),
      linkedProjects([BOARD]),
      projectViews([]),
      { re: "^api -H X-GitHub-Api-Version: 2026-03-10 /users/me/projectsV2/5/fields --paginate", out: JSON.stringify([{ id: 1, name: "Title" }]) },
      { re: "^api --method POST -H X-GitHub-Api-Version: 2026-03-10 /users/me/projectsV2/5/views", code: 1, out: "gh: Not Found (HTTP 404)" },
      { re: "^api users/me --jq .id", out: "4242\n" },
      { re: "^api --method POST -H X-GitHub-Api-Version: 2026-03-10 /users/4242/projectsV2/5/views -f name=Bugs -f layout=table -F visible_fields\\[\\]=1$", out: "{}" },
    ])
    expect(res.ok).toBe(true)
    expect(res.out).toMatchObject({ created: true, skippedFields: ["Nope"] })
  })
})

describe("gh_project_item_list", () => {
  test("flattens items and filters by status, content type, repository and title", () => {
    const items = projectItems([
      { id: "PVTI_1", status: "Todo", issue: { repo: REPO, number: 1, title: "Login page" } },
      { id: "PVTI_2", status: "Done", issue: { repo: REPO, number: 2, title: "Logout" } },
      { id: "PVTI_3", status: "Todo", draft: { id: "DI_3", title: "Login idea" } },
      { id: "PVTI_4", status: "Todo", archived: true, issue: { repo: "acme/other", number: 9, title: "Login elsewhere" } },
    ])
    const base = [...repoContext(REPO), linkedProjects([BOARD]), items]
    const all = call("item_list", { repo: REPO }, base)
    expect(all.out.count).toBe(3)
    expect(all.out.items[0]).toMatchObject({ id: "PVTI_1", fields: { Status: "Todo" }, content: { type: "Issue", number: 1, repo: REPO } })

    expect(call("item_list", { repo: REPO, status: "-Done", includeArchived: true }, base).out.items.map((i: any) => i.id)).toEqual(["PVTI_1", "PVTI_3", "PVTI_4"])
    expect(call("item_list", { repo: REPO, status: "-Done,-Todo", includeArchived: true }, base).out.items.map((i: any) => i.id)).toEqual([])
    expect(call("item_list", { repo: REPO, status: "done, todo" }, base).out.items.map((i: any) => i.id)).toEqual(["PVTI_1", "PVTI_2", "PVTI_3"])
    expect(call("item_list", { repo: REPO, contentRepo: "current", includeArchived: true }, base).out.items.map((i: any) => i.id)).toEqual(["PVTI_1", "PVTI_2"])
    expect(call("item_list", { status: "todo", contentType: "draft", project: "me/5" }, [ownerType("me", "User"), { re: "user\\(login:\\$login\\)\\{projectV2\\(number:\\$n\\)", out: gql({ user: { projectV2: projectNode(BOARD) } }) }, items]).out.items.map((i: any) => i.id)).toEqual(["PVTI_3"])
    expect(call("item_list", { repo: REPO, search: "login" }, base).out.items.map((i: any) => i.id)).toEqual(["PVTI_1", "PVTI_3"])
    expect(all.out.truncated).toBe(false)

    const noRepo = call("item_list", { project: "me/5", contentRepo: "current" }, [{ re: "^repo view", code: 1 }, ownerType("me", "User"), { re: "user\\(login:\\$login\\)\\{projectV2\\(number:\\$n\\)", out: gql({ user: { projectV2: projectNode(BOARD) } }) }])
    expect(noRepo.error).toMatch(/contentRepo "current" needs a repository/)
  })
})

describe("gh_project_item_add / item_set / item_promote", () => {
  test("adds an issue by reference and a draft by title, setting fields", () => {
    const base = [...repoContext(REPO), linkedProjects([BOARD])]
    const issue = call("item_add", { url: "7", repo: REPO, fields: { Status: "Todo" } }, [
      ...base,
      { re: `^project item-add 5 --owner me --url ${issueUrl(REPO, 7)} --format json`, out: JSON.stringify({ id: "PVTI_7" }) },
      projectFields(STANDARD_FIELDS),
      { re: "^project item-edit --id PVTI_7 --project-id PVT_me_5 --field-id F_Status --single-select-option-id OPT_Todo", out: "" },
    ])
    expect(issue.out).toMatchObject({ kind: "content", itemId: "PVTI_7", fieldsApplied: ["Status"] })

    const draft = call("item_add", { title: "Idea", body: "later", repo: REPO }, [...base, { re: "^project item-create 5 --owner me --title Idea --format json --body later$", out: JSON.stringify({ id: "PVTI_8" }) }])
    expect(draft.out).toMatchObject({ kind: "draft", itemId: "PVTI_8", fieldsApplied: [] })
  })

  test("sets, clears, appends to a draft and archives from the item id alone", () => {
    const res = call("item_set", { item: "PVTI_3", fields: { Status: "Done" }, clear: ["Target"], appendBody: "- note", archived: true }, [
      projectItem(PVT, { id: "PVTI_3", status: "Todo", draft: { id: "DI_3", title: "Idea", body: "body" } }),
      projectNodeById(BOARD),
      projectFields(STANDARD_FIELDS),
      { re: "^project item-edit --id PVTI_3 --project-id PVT_me_5 --field-id F_Status --single-select-option-id OPT_Done", out: "" },
      { re: "^project item-edit --id PVTI_3 --project-id PVT_me_5 --field-id F_Target --clear", out: "" },
      { re: "^project item-edit --id DI_3 --body body\\n\\n- note\\n$", out: "" },
      { re: "^project item-archive 5 --owner me --id PVTI_3$", out: "" },
    ])
    expect(res.ok).toBe(true)
    expect(res.out.changed).toEqual(["Status", "Target (cleared)", "body (appended)", "archived"])

    const builtin = call("item_set", { item: "PVTI_3", fields: { Milestone: "v1" } }, [projectItem(PVT, { id: "PVTI_3", draft: { id: "DI_3", title: "Idea" } }), projectNodeById(BOARD), projectFields(STANDARD_FIELDS)])
    expect(builtin.ok).toBe(false)
    expect(builtin.error).toMatch(/built-in field; set it on the issue/)

    const issueTitle = call("item_set", { item: "PVTI_1", title: "x" }, [projectItem(PVT, { id: "PVTI_1", issue: { repo: REPO, number: 1 } }), projectNodeById(BOARD)])
    expect(issueTitle.error).toMatch(/drafts only/)
    const both = call("item_set", { item: "PVTI_3", body: "a", appendBody: "b" }, [projectItem(PVT, { id: "PVTI_3", draft: { id: "DI_3", title: "Idea" } }), projectNodeById(BOARD)])
    expect(both.error).toMatch(/not both/)
    const readOnly = call("item_set", { item: "PVTI_3", archived: true }, [projectItem(PVT, { id: "PVTI_3", draft: { id: "DI_3", title: "Idea" } }), projectNodeById({ ...BOARD, canUpdate: false })])
    expect(readOnly.error).toMatch(/read-only for the viewer/)
  })

  test("promotes a draft into an issue with kind and milestone", () => {
    const res = call("item_promote", { item: "PVTI_3", repo: REPO, kind: "feature", milestone: "v1" }, [
      ...repoContext(REPO),
      projectItem(PVT, { id: "PVTI_3", draft: { id: "DI_3", title: "Idea" } }),
      projectNodeById(BOARD),
      { re: "convertProjectV2DraftIssueItemToIssue\\(input:\\{itemId:\"PVTI_3\",repositoryId:\"R_web\"\\}", out: gql({ convertProjectV2DraftIssueItemToIssue: { item: { id: "PVTI_3", content: { number: 30, url: issueUrl(REPO, 30) } } } }) },
      { re: "^issue view 30 --json labels", out: JSON.stringify({ labels: [] }) },
      { re: "^label list", out: JSON.stringify([{ name: "type:feature" }]) },
      { re: "^issue edit 30 --add-label type:feature", out: "" },
      { re: "^api --paginate --slurp repos/me/web/milestones", out: JSON.stringify([[{ number: 2, title: "v1" }]]) },
      { re: "^issue edit 30 --repo me/web --milestone v1$", out: "" },
    ])
    expect(res.ok).toBe(true)
    expect(res.out).toMatchObject({ ok: true, issue: { number: 30 }, kind: { via: "label", name: "type:feature" }, milestone: { number: 2, created: false }, errors: {} })

    const notDraft = call("item_promote", { item: "PVTI_1", repo: REPO }, [...repoContext(REPO), projectItem(PVT, { id: "PVTI_1", issue: { repo: REPO, number: 1 } })])
    expect(notDraft.ok).toBe(false)
    expect(notDraft.error).toMatch(/not a draft/)
    const noWrite = call("item_promote", { item: "PVTI_3", repo: REPO }, [...repoContext(REPO, { permission: "READ" })])
    expect(noWrite.error).toMatch(/No write permission/)
  })
})
