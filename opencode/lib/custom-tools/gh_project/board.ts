import { tool } from "../define"
import { exec, runGh, runGhJson } from "../exec"
import { assertWrite } from "../github/gate"
import {
  DEFAULT_TITLE,
  ensureField,
  getFields,
  graphql,
  parseProjectRef,
  parseRepoRef,
  projectById,
  projectsByTitle,
  resolveProject,
  resolveRepo,
  restBase,
  REST_API_VERSION,
  sameName,
  viewerLogin,
  type Field,
  type FieldSpec,
  type Project,
  type RepoContext,
  type Resolved,
} from "../github"

/**
 * The board itself: which one a call means, creating one with the standard
 * schema and views, linking it to a repository, and keeping fields and views
 * in place. The standard schema is small on purpose — Status, Start and
 * Target — because milestone, repository, parent issue, sub-issue progress
 * and type are built-in fields GitHub fills from the issues.
 */

export const STANDARD_FIELDS: FieldSpec[] = [
  { name: "Status", dataType: "SINGLE_SELECT", options: [{ name: "Todo", color: "GRAY" }, { name: "In Progress", color: "YELLOW" }, { name: "Done", color: "GREEN" }, { name: "Cancelled", color: "RED" }] },
  { name: "Start", dataType: "DATE" },
  { name: "Target", dataType: "DATE" },
]

export type ViewSpec = { name: string; layout: "table" | "board" | "roadmap"; filter?: string; visibleFields?: string[] }

export const STANDARD_VIEWS: ViewSpec[] = [
  { name: "Kanban", layout: "board", filter: "-status:Done -status:Cancelled", visibleFields: ["Title", "Assignees", "Repository", "Parent issue", "Target"] },
  { name: "Backlog", layout: "table", filter: "-status:Done -status:Cancelled", visibleFields: ["Title", "Status", "Repository", "Milestone", "Parent issue", "Sub-issues progress", "Target"] },
  { name: "Roadmap", layout: "roadmap", filter: "-status:Cancelled" },
]

const summary = (r: Resolved) => ({
  project: { id: r.project.id, number: r.project.number, title: r.project.title, url: r.project.url, owner: r.project.owner.login, ownerType: r.project.owner.type, viewerCanUpdate: r.project.viewerCanUpdate },
  route: r.route,
  considered: r.considered,
})

/** The repository context when there is one; a call outside a repository still resolves by owner. */
async function repoOrNull(repo: string | undefined, cwd?: string): Promise<RepoContext | null> {
  try {
    return await resolveRepo(repo, cwd)
  } catch {
    return null
  }
}

export async function resolveBoard(args: { project?: string; owner?: string; repo?: string }, cwd?: string): Promise<Resolved & { repo: RepoContext | null }> {
  const repo = await repoOrNull(args.repo, cwd)
  const resolved = await resolveProject({ project: args.project, owner: args.owner, repo, cwd })
  return { ...resolved, repo }
}

export function assertUpdatable(project: Project): void {
  if (!project.viewerCanUpdate) throw new Error(`Project ${project.owner.login}/${project.number} "${project.title}" is read-only for the viewer.`)
}

const fieldSummary = (f: Field) => ({ name: f.name, dataType: f.dataType, options: f.options?.map((o) => o.name), iterations: f.iterations?.map((i) => i.title) })

export const resolve = tool({
  description:
    "Which project board a call would use, and its fields, read-only. With nothing explicit the route is: a project linked to the repository → the owning organization's board titled \"Roadmap\" → the viewer's own \"Roadmap\"; a route is skipped when its board is missing or read-only, and the result lists every route considered. Pass `project` (URL, owner/N, number with `owner`, or a title) to pin one. Run it before writing to a board for the first time in a session.",
  args: {
    project: tool.schema.string().optional().describe("URL, owner/N, number (with owner) or title."),
    owner: tool.schema.string().optional().describe('Owner login or "@me", scoping a number or title.'),
    repo: tool.schema.string().optional().describe("owner/repo the call is about. Defaults to the current repository."),
  },
  async execute(args, context) {
    const r = await resolveBoard(args, context.worktree)
    const fields = await getFields(r.project.id, context.worktree)
    return JSON.stringify({ ...summary(r), repo: r.repo?.nameWithOwner ?? null, fields: fields.map(fieldSummary) }, null, 2)
  },
})

export const link = tool({
  description: "Link a project to a repository (so it resolves first for calls about that repository), or unlink it. Idempotent. Needs admin on the repository and write on the project.",
  args: {
    project: tool.schema.string().describe("URL, owner/N, number (with owner) or title."),
    owner: tool.schema.string().optional(),
    repo: tool.schema.string().optional().describe("owner/repo. Defaults to the current repository."),
    unlink: tool.schema.boolean().optional(),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const repo = await resolveRepo(args.repo, cwd)
    const { project } = await resolveProject({ project: args.project, owner: args.owner, repo, cwd })
    assertUpdatable(project)
    const [owner, name] = repo.nameWithOwner.split("/")
    const data = await graphql(`query($owner:String!,$name:String!){repository(owner:$owner,name:$name){projectsV2(first:50){nodes{id}}}}`, { owner, name }, cwd)
    const linked = (data?.repository?.projectsV2?.nodes ?? []).some((p: any) => p.id === project.id)
    const want = !args.unlink
    if (linked === want) return JSON.stringify({ ok: true, unchanged: true, linked: want, project: `${project.owner.login}/${project.number}`, repo: repo.nameWithOwner })
    await assertWrite(context, "gh_project_link", [`${project.owner.login}/${project.number}`, repo.nameWithOwner], { op: "board_link", project: `${project.owner.login}/${project.number}`, repo: repo.nameWithOwner, unlink: !want })
    await runGh(["project", want ? "link" : "unlink", String(project.number), "--owner", project.owner.login, "--repo", repo.nameWithOwner], cwd)
    return JSON.stringify({ ok: true, unchanged: false, linked: want, project: `${project.owner.login}/${project.number}`, repo: repo.nameWithOwner })
  },
})

async function viewNames(projectId: string, cwd?: string): Promise<string[]> {
  const data = await graphql("query($id:ID!){node(id:$id){... on ProjectV2{views(first:50){nodes{name}}}}}", { id: projectId }, cwd)
  return (data?.node?.views?.nodes ?? []).map((v: any) => String(v.name))
}

/** Creates a saved view through the REST projectsV2 views API when none of that name exists. */
export async function ensureView(project: Project, spec: ViewSpec, cwd?: string): Promise<{ created: boolean; view: string; skippedFields: string[] }> {
  const existing = await viewNames(project.id, cwd)
  if (existing.some((n) => sameName(n, spec.name))) return { created: false, view: spec.name, skippedFields: [] }
  const base = restBase(project)
  const params = ["-f", `name=${spec.name}`, "-f", `layout=${spec.layout}`]
  if (spec.filter) params.push("-f", `filter=${spec.filter}`)
  // A column the board lacks is skipped and reported: a view is created once,
  // so a caller repairs it in the UI rather than by re-running.
  const skippedFields: string[] = []
  if (spec.layout !== "roadmap" && spec.visibleFields?.length) {
    const restFields: any[] = (await runGhJson(["api", "-H", REST_API_VERSION, `${base}/projectsV2/${project.number}/fields`, "--paginate"], cwd)) ?? []
    for (const name of spec.visibleFields) {
      const f = restFields.find((x) => sameName(x.name, name))
      if (f?.id != null) params.push("-F", `visible_fields[]=${f.id}`)
      else skippedFields.push(name)
    }
  }
  const post = (root: string) => exec(["gh", "api", "--method", "POST", "-H", REST_API_VERSION, `${root}/projectsV2/${project.number}/views`, ...params], { cwd })
  let res = await post(base)
  // The views route names its user segment `{user_id}` where the field and
  // project routes take `{username}`; when the login is not found, the
  // account's numeric id is tried before giving up.
  if (!res.ok && project.owner.type === "User" && /404|Not Found/i.test(res.stderr + res.stdout)) {
    const id = (await runGh(["api", `users/${project.owner.login}`, "--jq", ".id"], cwd)).trim()
    if (id) res = await post(`/users/${id}`)
  }
  if (!res.ok) throw new Error(`creating view "${spec.name}" failed (exit ${res.code}):\n${res.stderr.trim() || res.stdout.trim()}`)
  return { created: true, view: spec.name, skippedFields }
}

export const create = tool({
  description:
    'Create a project board, or reuse the one of that title the owner already has, and bring it to the standard shape in one call: Status (Todo / In Progress / Done / Cancelled), Start and Target date fields, the Kanban / Backlog / Roadmap views, and optionally a link to a repository. Milestone, Repository, Parent issue, Sub-issues progress and Type are built-in fields GitHub fills from the issues, so none are created. Projects are owned by a user or an organization: pass `owner` as a login or "@me". Optionally seed from a template project (`template`: URL, owner/N, or a title of the viewer\'s) to carry its views. Idempotent.',
  args: {
    owner: tool.schema.string().describe('Owner login, or "@me".'),
    title: tool.schema.string().optional().describe('Default "Roadmap".'),
    template: tool.schema.string().optional().describe("Project to copy when creating: URL, owner/N, or a title (searched under the viewer)."),
    linkRepo: tool.schema.string().optional().describe('owner/repo to link, or "current" for the working tree\'s repository.'),
    views: tool.schema.boolean().optional().describe("Ensure the standard views (default true)."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const title = args.title?.trim() || DEFAULT_TITLE
    const login = args.owner.trim() === "@me" ? await viewerLogin(cwd) : args.owner.trim()
    const existing = await projectsByTitle(login, title, cwd)
    if (existing.length > 1) throw new Error(`${existing.length} open projects titled "${title}" for ${login}; rename or close the extra ones first.`)
    await assertWrite(context, "gh_project_create", [login], { op: "board_create", owner: login, title, template: args.template ?? null, link_repo: args.linkRepo ?? null, reuse: Boolean(existing[0]) })
    let project: Project | null = existing[0] ?? null
    let createdNew = false
    let copiedFrom: string | null = null
    if (!project) {
      createdNew = true
      let created: any = null
      if (args.template) {
        const ref = parseProjectRef(args.template, "@me")
        const tmpl = (await resolveProject({ project: ref.number !== undefined ? `${ref.owner}/${ref.number}` : ref.title, owner: ref.owner ?? "@me", cwd })).project
        created = await runGhJson(["project", "copy", String(tmpl.number), "--source-owner", tmpl.owner.login, "--target-owner", login, "--title", title, "--format", "json"], cwd)
        copiedFrom = `${tmpl.owner.login}/${tmpl.number}`
      } else {
        created = await runGhJson(["project", "create", "--owner", login, "--title", title, "--format", "json"], cwd)
      }
      if (!created?.id) throw new Error("gh project create returned no project.")
      project = await projectById(created.id, cwd)
    }
    assertUpdatable(project)
    let fields = await getFields(project.id, cwd)
    const fieldChanges: Record<string, unknown> = {}
    for (const spec of STANDARD_FIELDS) {
      const r = await ensureField(project, fields, spec, cwd)
      if (r.created || r.addedOptions.length) {
        fieldChanges[spec.name] = r.created ? "created" : { addedOptions: r.addedOptions }
        fields = await getFields(project.id, cwd)
      }
    }
    const views: Record<string, string> = {}
    if (args.views !== false) {
      for (const v of STANDARD_VIEWS) {
        const r = await ensureView(project, v, cwd)
        views[v.name] = !r.created ? "exists" : r.skippedFields.length ? `created (columns not on the board: ${r.skippedFields.join(", ")})` : "created"
      }
    }
    let linked: string | null = null
    if (args.linkRepo) {
      const repo = args.linkRepo === "current" ? (await resolveRepo(undefined, cwd)).nameWithOwner : parseRepoRef(args.linkRepo)
      await runGh(["project", "link", String(project.number), "--owner", project.owner.login, "--repo", repo], cwd)
      linked = repo
    }
    return JSON.stringify(
      { ok: true, createdNew, copiedFrom, project: { id: project.id, number: project.number, title: project.title, url: project.url, owner: project.owner.login }, fields: fieldChanges, views, linked },
      null,
      2,
    )
  },
})

export const field_ensure = tool({
  description:
    "Make sure a custom field exists on the board: created when missing; for SINGLE_SELECT, missing options are appended (existing options keep their ids, so nothing already set moves). Built-in field names (Milestone, Repository, Type, ...) are refused: GitHub fills those from the issues. Board resolved as in gh_project_resolve.",
  args: {
    name: tool.schema.string(),
    dataType: tool.schema.enum(["TEXT", "SINGLE_SELECT", "DATE", "NUMBER"]),
    options: tool.schema.array(tool.schema.string()).optional().describe('SINGLE_SELECT option names; "Name:COLOR" sets a color (GRAY, BLUE, GREEN, YELLOW, ORANGE, RED, PINK, PURPLE).'),
    project: tool.schema.string().optional(),
    owner: tool.schema.string().optional(),
    repo: tool.schema.string().optional(),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const { project, route } = await resolveBoard(args, cwd)
    assertUpdatable(project)
    const options = args.options?.map((o) => {
      const m = o.match(/^(.*?):([A-Z]+)$/)
      return m ? { name: m[1], color: m[2] } : { name: o }
    })
    await assertWrite(context, "gh_project_field_ensure", [`${project.owner.login}/${project.number}`], { op: "field_ensure", project: `${project.owner.login}/${project.number}`, name: args.name, data_type: args.dataType, options: args.options ?? [] })
    const r = await ensureField(project, await getFields(project.id, cwd), { name: args.name, dataType: args.dataType, options }, cwd)
    return JSON.stringify({ ok: true, project: `${project.owner.login}/${project.number}`, route, field: args.name, created: r.created, addedOptions: r.addedOptions })
  },
})

export const view_ensure = tool({
  description:
    "Make sure a saved view of that name exists on the board (case-insensitive), creating it through the REST projectsV2 views API when missing: layout table / board / roadmap, a Projects filter, and the field columns to show. Grouping, sort and roadmap date binding are not settable through the API; set those once in the UI. Board resolved as in gh_project_resolve.",
  args: {
    name: tool.schema.string(),
    layout: tool.schema.enum(["table", "board", "roadmap"]),
    filter: tool.schema.string().optional().describe('Projects filter, e.g. "-status:Done".'),
    visibleFields: tool.schema.array(tool.schema.string()).optional().describe("Field names shown as columns (table / board)."),
    project: tool.schema.string().optional(),
    owner: tool.schema.string().optional(),
    repo: tool.schema.string().optional(),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const { project, route } = await resolveBoard(args, cwd)
    assertUpdatable(project)
    await assertWrite(context, "gh_project_view_ensure", [`${project.owner.login}/${project.number}`], { op: "view_ensure", project: `${project.owner.login}/${project.number}`, name: args.name, layout: args.layout, filter: args.filter ?? null })
    const r = await ensureView(project, { name: args.name, layout: args.layout, filter: args.filter, visibleFields: args.visibleFields }, cwd)
    return JSON.stringify({ ok: true, project: `${project.owner.login}/${project.number}`, route, ...r })
  },
})
