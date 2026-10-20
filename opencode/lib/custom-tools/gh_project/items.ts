import { tool } from "../define"
import { runGh, runGhJson } from "../exec"
import { addUrlToProject, applyFields, applyKind, getFields, getItem, graphql, listItems, lit, parseIssueRef, projectById, resolveRepo, sameName, type Item } from "../github"
import { ensureMilestone } from "../gh_issue/write"
import { assertUpdatable, resolveBoard } from "./board"

/**
 * Items on a board: listing with the built-in fields flattened, adding an
 * issue / PR or a draft note, setting fields, archiving (never deleting), and
 * turning a draft into an issue. An item id (PVTI_...) names its board, so
 * item_set and item_promote need no project argument.
 */

const CONTENT_TYPES = { issue: "Issue", pr: "PullRequest", draft: "DraftIssue" } as const

export const item_list = tool({
  description:
    "List a board's items, read-only, with every field flattened by name (custom and built-in: Status, Milestone, Repository, Parent issue, Sub-issues progress, ...) and the content's own facts (number, state, kind, parent, sub-issue progress). Filters: status (option name), contentType issue / pr / draft, repo (owner/repo of the content), search (title substring), includeArchived. Paginates up to `limit` (default 100). Board resolved as in gh_project_resolve.",
  args: {
    status: tool.schema.string().optional().describe('Status option name, e.g. "In Progress"; "-Done" excludes one.'),
    contentType: tool.schema.enum(["issue", "pr", "draft"]).optional(),
    contentRepo: tool.schema.string().optional().describe('Only items whose issue or PR lives in this owner/repo ("current" for the working tree\'s).'),
    search: tool.schema.string().optional().describe("Case-insensitive substring of the title."),
    includeArchived: tool.schema.boolean().optional(),
    limit: tool.schema.number().optional(),
    project: tool.schema.string().optional(),
    owner: tool.schema.string().optional(),
    repo: tool.schema.string().optional().describe("Repository context for resolving the board. Defaults to the current repository."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const { project, route, repo } = await resolveBoard(args, cwd)
    const limit = args.limit ?? 100
    const all = await listItems(project.id, { limit: Math.max(limit * 4, 500), cwd })
    const status = args.status?.trim()
    const exclude = status?.startsWith("-") ? status.slice(1) : null
    const want = args.contentType ? CONTENT_TYPES[args.contentType] : null
    const repoFilter = args.contentRepo === "current" ? repo?.nameWithOwner ?? null : args.contentRepo ?? null
    const items = all
      .filter((it) => args.includeArchived || !it.archived)
      .filter((it) => !status || (exclude ? !sameName(it.fields.Status, exclude) : sameName(it.fields.Status, status)))
      .filter((it) => !want || it.content?.type === want)
      .filter((it) => !repoFilter || (it.content && it.content.type !== "DraftIssue" && sameName(it.content.repo, repoFilter)))
      .filter((it) => !args.search || titleOf(it).toLowerCase().includes(args.search.toLowerCase()))
      .slice(0, limit)
    return JSON.stringify({ project: `${project.owner.login}/${project.number}`, title: project.title, url: project.url, route, count: items.length, items }, null, 2)
  },
})

const titleOf = (it: Item) => (it.content?.type === "DraftIssue" ? it.content.title : it.content?.title) ?? String(it.fields.Title ?? "")

export const item_add = tool({
  description:
    'Add to a board: an existing issue or PR (`url`, or owner/repo#N), or a draft note (`title` + `body`; a draft lives only on the board, has no repository, labels or milestone, and becomes an issue with gh_project_item_promote). Sets field values in the same call, e.g. {"Status":"Todo","Target":"2026-12-01"}. Board resolved as in gh_project_resolve. Returns the item id (PVTI_...).',
  args: {
    url: tool.schema.string().optional().describe("Issue or PR URL, or owner/repo#N."),
    title: tool.schema.string().optional().describe("Draft title (when no url)."),
    body: tool.schema.string().optional().describe("Draft body."),
    fields: tool.schema.record(tool.schema.string(), tool.schema.string()).optional(),
    project: tool.schema.string().optional(),
    owner: tool.schema.string().optional(),
    repo: tool.schema.string().optional(),
  },
  async execute(args, context) {
    const cwd = context.worktree
    if (!args.url && !args.title) throw new Error("Pass `url` (an issue or PR) or `title` (a draft).")
    if (args.url && args.title) throw new Error("Pass url or title, not both.")
    const { project, route, repo } = await resolveBoard(args, cwd)
    assertUpdatable(project)
    if (args.url) {
      const ref = parseIssueRef(args.url, repo?.nameWithOwner)
      if (!ref.repo) throw new Error("A bare issue number needs `repo` or a repository in the working tree.")
      const url = /^https?:/.test(args.url.trim()) ? args.url.trim() : `https://github.com/${ref.repo}/issues/${ref.number}`
      const r = await addUrlToProject(project, route, url, args.fields, cwd)
      return JSON.stringify({ ok: true, kind: "content", url, ...r }, null, 2)
    }
    const argv = ["project", "item-create", String(project.number), "--owner", project.owner.login, "--title", args.title!, "--format", "json"]
    if (args.body) argv.push("--body", args.body)
    const created = await runGhJson(argv, cwd)
    const itemId: string = created?.id
    if (!itemId) throw new Error("gh project item-create returned no item id.")
    const fieldsApplied = args.fields && Object.keys(args.fields).length ? await applyFields(project.id, itemId, await getFields(project.id, cwd), args.fields, cwd) : []
    return JSON.stringify({ ok: true, kind: "draft", project: { id: project.id, number: project.number, title: project.title, url: project.url, owner: project.owner.login, route }, itemId, title: args.title, fieldsApplied }, null, 2)
  },
})

export const item_set = tool({
  description:
    'Change an item on a board: field values by name ({"Status":"Done"}; built-in fields such as Milestone are set on the issue with gh_issue_update), fields to clear, a draft\'s title or body, and archive / unarchive. Never deletes. The item id (PVTI_..., from gh_project_item_list or gh_issue_view) names the board.',
  args: {
    item: tool.schema.string().describe("Project item id (PVTI_...)."),
    fields: tool.schema.record(tool.schema.string(), tool.schema.string()).optional(),
    clear: tool.schema.array(tool.schema.string()).optional().describe("Field names to clear."),
    title: tool.schema.string().optional().describe("New title (drafts only)."),
    body: tool.schema.string().optional().describe("New body (drafts only)."),
    appendBody: tool.schema.string().optional().describe("Markdown appended to a draft's body."),
    archived: tool.schema.boolean().optional().describe("true archives the item, false restores it."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const { projectId, item } = await getItem(args.item, cwd)
    const project = await projectById(projectId, cwd)
    assertUpdatable(project)
    const changed: string[] = []
    const values: Record<string, string | null> = { ...(args.fields ?? {}) }
    for (const name of args.clear ?? []) values[name] = null
    if (Object.keys(values).length) {
      const applied = await applyFields(project.id, args.item, await getFields(project.id, cwd), values, cwd)
      changed.push(...applied.map((n) => (values[n] === null ? `${n} (cleared)` : n)))
    }
    if (args.title !== undefined || args.body !== undefined || args.appendBody !== undefined) {
      if (item.content?.type !== "DraftIssue") throw new Error("title / body apply to drafts only; edit an issue with gh_issue_update.")
      if (args.body !== undefined && args.appendBody !== undefined) throw new Error("Pass body or appendBody, not both.")
      const argv = ["project", "item-edit", "--id", item.content.id]
      if (args.title !== undefined) argv.push("--title", args.title), changed.push("title")
      if (args.body !== undefined) argv.push("--body", args.body), changed.push("body")
      if (args.appendBody !== undefined) argv.push("--body", `${item.content.body.trimEnd()}\n\n${args.appendBody.trim()}\n`), changed.push("body (appended)")
      await runGh(argv, cwd)
    }
    if (args.archived !== undefined && args.archived !== item.archived) {
      const argv = ["project", "item-archive", String(project.number), "--owner", project.owner.login, "--id", args.item]
      if (!args.archived) argv.push("--undo")
      await runGh(argv, cwd)
      changed.push(args.archived ? "archived" : "unarchived")
    }
    return JSON.stringify({ ok: true, project: `${project.owner.login}/${project.number}`, item: args.item, changed })
  },
})

export const item_promote = tool({
  description:
    "Turn a draft item into a real issue in a repository: the draft's title and body become the issue, the item stays on the board with its field values, and the built-in Repository / Milestone / Type fields start to apply. Optionally sets the kind (Issue Type or type:* label), labels and a milestone (created when createMilestone is set). Needs write permission on the repository.",
  args: {
    item: tool.schema.string().describe("Project item id (PVTI_...) of a draft."),
    repo: tool.schema.string().describe("owner/repo to create the issue in."),
    kind: tool.schema.string().optional(),
    labels: tool.schema.array(tool.schema.string()).optional(),
    milestone: tool.schema.string().optional(),
    createMilestone: tool.schema.boolean().optional(),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const repo = await resolveRepo(args.repo, cwd)
    if (!repo.canWrite) throw new Error(`No write permission on ${repo.nameWithOwner} (viewer permission: ${repo.permission ?? "none"}).`)
    const { item } = await getItem(args.item, cwd)
    if (item.content?.type !== "DraftIssue") throw new Error(`Item ${args.item} is not a draft (${item.content?.type ?? "no content"}).`)
    const mutation = `mutation{convertProjectV2DraftIssueItemToIssue(input:{itemId:${lit(args.item)},repositoryId:${lit(repo.id)}}){item{id content{... on Issue{number url}}}}}`
    const data = await graphql(mutation, {}, cwd)
    const issue = data?.convertProjectV2DraftIssueItemToIssue?.item?.content
    if (!issue?.number) throw new Error("Conversion returned no issue.")
    const errors: Record<string, string> = {}
    const step = async <T>(name: string, run: () => Promise<T>): Promise<T | null> => {
      try {
        return await run()
      } catch (error) {
        errors[name] = (error as Error).message
        return null
      }
    }
    const kind = args.kind ? await step("kind", () => applyKind(repo, issue.number, args.kind!, cwd)) : null
    let milestone: { number: number; title: string; created: boolean } | null = null
    if (args.labels?.length || args.milestone) {
      await step("edit", async () => {
        const argv = ["issue", "edit", String(issue.number), "--repo", repo.nameWithOwner]
        for (const l of args.labels ?? []) argv.push("--add-label", l)
        if (args.milestone) {
          milestone = await ensureMilestone(repo.nameWithOwner, args.milestone, Boolean(args.createMilestone), cwd)
          argv.push("--milestone", milestone.title)
        }
        await runGh(argv, cwd)
      })
    }
    return JSON.stringify({ ok: Object.keys(errors).length === 0, item: args.item, repo: repo.nameWithOwner, foreign: repo.foreign, issue: { number: issue.number, url: issue.url }, kind, milestone, errors }, null, 2)
  },
})
