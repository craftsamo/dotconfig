import { tool } from "@opencode-ai/plugin"

/**
 * Generic GitHub Projects (v2) toolset, plus the issue-lifecycle operations
 * that surround a promoted board item (parent/sub-issue hierarchy and linked
 * development branches).
 *
 * Board operations are intentionally schema-agnostic: they operate on any
 * project and resolve field / option ids by NAME at runtime (nothing is
 * hard-coded, so adding or renaming options never makes them stale). The
 * "Roadmap" conventions (which board, which fields, per-Kind body guidance)
 * live in the `manage-github-projects` skill, not here.
 *
 * Issue-lifecycle operations (`issue_link`, `issue_develop`) take an issue
 * number — typically the one returned by `item_promote` — and manage sub-issue
 * hierarchy and linked development branches. They are thin, idempotent
 * wrappers over `gh` (>= 2.94.0 for sub-issue links).
 *
 * Defaults: when `owner` is omitted it is taken from the current repo's remote
 * (falling back to "@me"); when `project` is omitted a project titled "Roadmap"
 * is used.
 *
 * Items are GitHub Project DRAFT issues by default — no repo issue and no local
 * file is created. There is deliberately no delete operation (archive in the UI
 * instead).
 */

const DEFAULT_TITLE = "Roadmap"
const TEMPLATE_OWNER = "@me"
const TEMPLATE_TITLE = "Roadmap Template"
const REST_API_VERSION = "X-GitHub-Api-Version: 2026-03-10"

async function runGh(argv: string[], cwd?: string): Promise<string> {
  let p = Bun.$`gh ${argv}`
  if (cwd) p = p.cwd(cwd)
  const res = await p.nothrow().quiet()
  if (res.exitCode !== 0) {
    const err = res.stderr.toString().trim() || res.stdout.toString().trim()
    throw new Error(`gh ${argv.join(" ")} failed (exit ${res.exitCode}):\n${err}`)
  }
  return res.stdout.toString()
}

async function runGhJson(argv: string[], cwd?: string): Promise<any> {
  const out = (await runGh(argv, cwd)).trim()
  return out ? JSON.parse(out) : null
}

async function resolveOwner(owner: string | undefined, cwd?: string): Promise<string> {
  if (owner && owner.trim()) return owner.trim()
  try {
    const login = (await runGh(["repo", "view", "--json", "owner", "--jq", ".owner.login"], cwd)).trim()
    if (login) return login
  } catch {
    // not a repo / no remote / not resolvable
  }
  return "@me"
}

async function resolveProject(owner: string, project?: string): Promise<{ number: number; id: string }> {
  const p = (project ?? "").trim()
  let number: number | undefined
  if (/^\d+$/.test(p)) number = parseInt(p, 10)
  if (number === undefined) {
    const title = p || DEFAULT_TITLE
    const list = await runGhJson(["project", "list", "--owner", owner, "--format", "json", "-L", "100"])
    const found = (list?.projects ?? []).find((x: any) => x.title === title)
    if (!found) {
      throw new Error(
        `No project titled "${title}" for owner "${owner}". Create it with github_project_create, then add fields with github_project_field_ensure.`,
      )
    }
    number = found.number
  }
  const view = await runGhJson(["project", "view", String(number), "--owner", owner, "--format", "json"])
  return { number: number!, id: view.id }
}

async function findProjectNumber(owner: string, title: string): Promise<number | undefined> {
  const list = await runGhJson(["project", "list", "--owner", owner, "--format", "json", "-L", "100"])
  return (list?.projects ?? []).find((x: any) => x.title === title)?.number
}

async function getFields(projectNodeId: string): Promise<any[]> {
  // field-list (porcelain) cannot distinguish TEXT/NUMBER/DATE (all "ProjectV2Field"),
  // so query GraphQL for the precise dataType plus single-select options.
  const q =
    "query($id:ID!){node(id:$id){... on ProjectV2{fields(first:50){nodes{__typename ... on ProjectV2FieldCommon{id name dataType} ... on ProjectV2SingleSelectField{options{id name color description}}}}}}}"
  const data = await runGhJson(["api", "graphql", "-f", `query=${q}`, "-f", `id=${projectNodeId}`])
  return data?.data?.node?.fields?.nodes ?? []
}

function findField(fields: any[], name: string): any {
  const f = fields.find((x: any) => String(x.name).toLowerCase() === name.toLowerCase())
  if (!f) throw new Error(`Field "${name}" not found. Available: ${fields.map((x: any) => x.name).join(", ")}`)
  return f
}

async function setItemField(projectId: string, itemId: string, field: any, value: string): Promise<void> {
  const base = ["project", "item-edit", "--id", itemId, "--project-id", projectId, "--field-id", field.id]
  if (field.dataType === "SINGLE_SELECT") {
    const opt = (field.options ?? []).find((o: any) => String(o.name).toLowerCase() === String(value).toLowerCase())
    if (!opt) {
      throw new Error(
        `Option "${value}" not in field "${field.name}". Options: ${(field.options ?? []).map((o: any) => o.name).join(", ")}`,
      )
    }
    await runGh([...base, "--single-select-option-id", opt.id])
  } else if (field.dataType === "NUMBER") {
    await runGh([...base, "--number", String(value)])
  } else if (field.dataType === "DATE") {
    await runGh([...base, "--date", String(value)])
  } else {
    await runGh([...base, "--text", String(value)])
  }
}

function gqlStr(s: string): string {
  // JSON string escaping is a valid GraphQL string literal for our values.
  return JSON.stringify(s ?? "")
}

function optionsToGraphQL(opts: { id?: string; name: string; color?: string; description?: string }[]): string {
  const body = opts
    .map((o) => {
      const parts = [
        o.id ? `id:${gqlStr(o.id)}` : null,
        `name:${gqlStr(o.name)}`,
        `color:${o.color || "GRAY"}`, // enum value, must stay unquoted
        `description:${gqlStr(o.description ?? "")}`,
      ].filter(Boolean)
      return `{${parts.join(",")}}`
    })
    .join(",")
  return `[${body}]`
}

// GitHub Projects reserves these built-in field display names; creating a
// custom field with the same name fails (e.g. the issue "Type" field on org
// boards). Mirror a built-in we carry through promote with the "_"-prefixed
// stand-in convention (`_Repository`, `_Milestone`); otherwise pick a plain name.
const RESERVED_FIELD_NAMES = new Set([
  "title", "assignees", "labels", "milestone", "repository", "reviewers",
  "linked pull requests", "parent issue", "sub-issues progress", "type",
])

function assertCreatableFieldName(name: string): void {
  if (RESERVED_FIELD_NAMES.has(name.trim().toLowerCase())) {
    throw new Error(
      `"${name}" is a reserved GitHub built-in field name and cannot be created as a custom field. ` +
        `Use a plain custom name (e.g. "Kind" instead of "Type"), or mirror a built-in carried through ` +
        `promote with the "_"-prefixed stand-in convention (e.g. "_Repository", "_Milestone").`,
    )
  }
}

// ---- Canonical "Roadmap" schema applied by github_project_create ----
const ROADMAP_SELECTS: Record<string, [string, string][]> = {
  Status: [["Todo", "GRAY"], ["In Progress", "YELLOW"], ["Done", "GREEN"], ["Cancelled", "RED"]],
  Kind: [["Feature", "GREEN"], ["Enhancement", "BLUE"], ["Bug Fix", "RED"], ["Chore", "GRAY"], ["Design", "PURPLE"], ["Test", "YELLOW"]],
  Area: [
    ["Frontend", "BLUE"], ["Backend", "GREEN"], ["Infra", "ORANGE"], ["Docs", "GRAY"], ["UI/UX", "PINK"],
    ["Config", "YELLOW"], ["CI/CD", "PURPLE"], ["Skills", "RED"], ["Tooling", "ORANGE"], ["Other", "GRAY"],
  ],
}
const ROADMAP_SIMPLE: [string, string][] = [["_Repository", "TEXT"], ["_Milestone", "TEXT"], ["Start date", "DATE"], ["Target date", "DATE"]]

// Ensure a single-select field exists with the given option names AND colors.
// Existing options are matched by name and keep their ids (assignments survive),
// missing options are added, and any extra pre-existing options are preserved.
async function ensureSelectField(owner: string, number: number, projectId: string, name: string, optionColors: [string, string][]): Promise<void> {
  let fields = await getFields(projectId)
  let field = fields.find((f: any) => String(f.name).toLowerCase() === name.toLowerCase())
  if (!field) {
    assertCreatableFieldName(name)
    const names = optionColors.map(([n]) => n).join(",")
    await runGh(["project", "field-create", String(number), "--owner", owner, "--name", name, "--data-type", "SINGLE_SELECT", "--single-select-options", names])
    fields = await getFields(projectId)
    field = fields.find((f: any) => String(f.name).toLowerCase() === name.toLowerCase())
    if (!field) throw new Error(`Failed to create field "${name}".`)
  }
  const existing: any[] = field.options ?? []
  const byName = new Map(existing.map((o: any) => [String(o.name).toLowerCase(), o]))
  const merged: any[] = optionColors.map(([n, color]) => {
    const ex: any = byName.get(n.toLowerCase())
    return ex ? { id: ex.id, name: ex.name, color, description: ex.description ?? "" } : { name: n, color, description: "" }
  })
  for (const o of existing) {
    if (!optionColors.find(([n]) => n.toLowerCase() === String(o.name).toLowerCase())) {
      merged.push({ id: o.id, name: o.name, color: o.color, description: o.description ?? "" })
    }
  }
  const mutation = `mutation{updateProjectV2Field(input:{fieldId:${gqlStr(field.id)},singleSelectOptions:${optionsToGraphQL(merged)}}){projectV2Field{... on ProjectV2SingleSelectField{id}}}}`
  await runGh(["api", "graphql", "-f", `query=${mutation}`])
}

async function ensureSimpleField(owner: string, number: number, projectId: string, name: string, dataType: string): Promise<void> {
  const fields = await getFields(projectId)
  if (fields.find((f: any) => String(f.name).toLowerCase() === name.toLowerCase())) return
  assertCreatableFieldName(name)
  await runGh(["project", "field-create", String(number), "--owner", owner, "--name", name, "--data-type", dataType])
}

export const create = tool({
  description:
    'Create a GitHub Projects (v2) board and set up the standard "Roadmap" schema in one call: Status (Todo/In Progress/Done/Cancelled), Kind and Area — all with colors — plus _Repository, _Milestone and Start/Target date. A new board is seeded by copying the "Roadmap Template" board (carrying its saved views) when that template exists, else created bare. If a project with the title already exists for the owner it is reused. Idempotent (safe to re-run to repair/refresh the schema). Returns number, id and URL.',
  args: {
    owner: tool.schema.string().describe('Owner login, or "@me" for the current user. Use an org login for a team board.'),
    title: tool.schema.string().optional().describe('Project title. Defaults to "Roadmap".'),
  },
  async execute(args) {
    const title = args.title?.trim() || DEFAULT_TITLE
    const list = await runGhJson(["project", "list", "--owner", args.owner, "--format", "json", "-L", "100"])
    let proj = (list?.projects ?? []).find((p: any) => p.title === title)
    const createdNew = !proj
    let copiedFrom: string | null = null
    if (!proj) {
      // Seed a new board by copying the canonical template (carries its saved
      // views + date fields). Skip when creating the template itself, or if the
      // template is absent; fall back to a bare project on any copy failure.
      if (title !== TEMPLATE_TITLE) {
        const tmpl = await findProjectNumber(TEMPLATE_OWNER, TEMPLATE_TITLE)
        if (tmpl) {
          try {
            proj = await runGhJson(["project", "copy", String(tmpl), "--source-owner", TEMPLATE_OWNER, "--target-owner", args.owner, "--title", title, "--format", "json"])
            copiedFrom = `${TEMPLATE_OWNER}/${TEMPLATE_TITLE}#${tmpl}`
          } catch {
            // fall back to a bare project below
          }
        }
      }
      if (!proj) {
        proj = await runGhJson(["project", "create", "--owner", args.owner, "--title", title, "--format", "json"])
      }
    }
    const number = proj.number
    const view = await runGhJson(["project", "view", String(number), "--owner", args.owner, "--format", "json"])
    const projectId = view.id
    for (const [name, optionColors] of Object.entries(ROADMAP_SELECTS)) {
      await ensureSelectField(args.owner, number, projectId, name, optionColors)
    }
    for (const [name, dataType] of ROADMAP_SIMPLE) {
      await ensureSimpleField(args.owner, number, projectId, name, dataType)
    }
    return JSON.stringify({ ok: true, createdNew, copiedFrom, number, id: projectId, url: view.url ?? proj.url, title })
  },
})

export const field_ensure = tool({
  description:
    "Idempotently ensure a field exists on a project. Creates it if missing. For SINGLE_SELECT, also appends any missing options (existing options and their ids/colors are preserved). owner defaults to the current repo owner (else @me); project defaults to a board titled \"Roadmap\".",
  args: {
    name: tool.schema.string().describe('Field name, e.g. "Kind" or "Area".'),
    dataType: tool.schema.enum(["TEXT", "SINGLE_SELECT", "DATE", "NUMBER"]).describe("Field data type."),
    options: tool.schema
      .array(tool.schema.string())
      .optional()
      .describe("Option names for SINGLE_SELECT (created on first run, appended if missing on later runs)."),
    owner: tool.schema.string().optional().describe('Owner login or "@me". Defaults to current repo owner, else @me.'),
    project: tool.schema.string().optional().describe('Project number or title. Defaults to "Roadmap".'),
  },
  async execute(args, context) {
    const owner = await resolveOwner(args.owner, context.worktree)
    const { number, id: projectId } = await resolveProject(owner, args.project)
    const fields = await getFields(projectId)
    const field = fields.find((x: any) => String(x.name).toLowerCase() === args.name.toLowerCase())

    if (!field) {
      assertCreatableFieldName(args.name)
      const argv = ["project", "field-create", String(number), "--owner", owner, "--name", args.name, "--data-type", args.dataType, "--format", "json"]
      if (args.dataType === "SINGLE_SELECT") {
        const opts = args.options ?? []
        if (opts.length === 0) throw new Error("SINGLE_SELECT requires at least one option.")
        argv.push("--single-select-options", opts.join(","))
      }
      const created = await runGhJson(argv)
      return JSON.stringify({ created: true, field: created })
    }

    if (args.dataType === "SINGLE_SELECT" && args.options?.length) {
      const cur = await runGhJson([
        "api",
        "graphql",
        "-f",
        "query=query($id:ID!){node(id:$id){... on ProjectV2SingleSelectField{options{id name color description}}}}",
        "-f",
        `id=${field.id}`,
      ])
      const existing: any[] = cur?.data?.node?.options ?? []
      const existingNames = new Set(existing.map((o: any) => String(o.name).toLowerCase()))
      const toAdd = args.options.filter((n) => !existingNames.has(n.toLowerCase()))
      if (toAdd.length === 0) return JSON.stringify({ created: false, unchanged: true, field: field.name })
      const merged = [
        ...existing.map((o: any) => ({ id: o.id, name: o.name, color: o.color, description: o.description ?? "" })),
        ...toAdd.map((n) => ({ name: n, color: "GRAY", description: "" })),
      ]
      const mutation = `mutation{updateProjectV2Field(input:{fieldId:${gqlStr(field.id)},singleSelectOptions:${optionsToGraphQL(
        merged,
      )}}){projectV2Field{... on ProjectV2SingleSelectField{options{id name}}}}}`
      await runGh(["api", "graphql", "-f", `query=${mutation}`])
      return JSON.stringify({ created: false, addedOptions: toAdd })
    }

    return JSON.stringify({ created: false, unchanged: true, field: field.name })
  },
})

export const item_add = tool({
  description:
    'Add a DRAFT item to a project and set its fields in one call (no repo issue, no local file). Pass field values by name in `fields`, e.g. {"Kind":"Bug Fix","Area":"Backend","Status":"Todo","_Repository":"owner/repo"}; ids are resolved automatically. owner defaults to the current repo owner (else @me); project defaults to a board titled "Roadmap". Returns the project item id (PVTI_...).',
  args: {
    title: tool.schema.string().describe("Item title. Keep it short; put detail in body."),
    body: tool.schema.string().optional().describe("Markdown body. Include only the relevant sections."),
    fields: tool.schema
      .record(tool.schema.string(), tool.schema.string())
      .optional()
      .describe('Field name -> value, e.g. {"Kind":"Feature","Area":"Backend","Status":"Todo","_Repository":"owner/repo"}.'),
    owner: tool.schema.string().optional().describe('Owner login or "@me". Defaults to current repo owner, else @me.'),
    project: tool.schema.string().optional().describe('Project number or title. Defaults to "Roadmap".'),
  },
  async execute(args, context) {
    const owner = await resolveOwner(args.owner, context.worktree)
    const { number, id: projectId } = await resolveProject(owner, args.project)
    const argv = ["project", "item-create", String(number), "--owner", owner, "--title", args.title, "--format", "json"]
    if (args.body) argv.push("--body", args.body)
    const created = await runGhJson(argv)
    const itemId = created.id
    const applied: string[] = []
    if (args.fields && Object.keys(args.fields).length) {
      const fields = await getFields(projectId)
      for (const [name, value] of Object.entries(args.fields)) {
        const f = findField(fields, name)
        await setItemField(projectId, itemId, f, value as string)
        applied.push(name)
      }
    }
    return JSON.stringify({ ok: true, owner, project: number, itemId, title: args.title, fieldsApplied: applied })
  },
})

export const item_set = tool({
  description:
    'Update field values on an existing project item (e.g. move Status to "In Progress" or "Done", change Area). Use the item id (PVTI_...) from github_project_item_list. owner/project default to the current repo owner and a board titled "Roadmap".',
  args: {
    item: tool.schema.string().describe("Project item id (PVTI_...)."),
    fields: tool.schema.record(tool.schema.string(), tool.schema.string()).describe('Field name -> value, e.g. {"Status":"Done"}.'),
    owner: tool.schema.string().optional(),
    project: tool.schema.string().optional(),
  },
  async execute(args, context) {
    const owner = await resolveOwner(args.owner, context.worktree)
    const { id: projectId } = await resolveProject(owner, args.project)
    const fields = await getFields(projectId)
    const applied: string[] = []
    for (const [name, value] of Object.entries(args.fields)) {
      const f = findField(fields, name)
      await setItemField(projectId, args.item, f, value as string)
      applied.push(name)
    }
    return JSON.stringify({ ok: true, item: args.item, fieldsApplied: applied })
  },
})

export const item_list = tool({
  description:
    'List items on a project. Optionally filter with the Projects query syntax, e.g. -status:Done or kind:"Bug Fix" or assignee:@me. Returns id (PVTI_...), title, flattened field values and the draft body. owner/project default to the current repo owner and a board titled "Roadmap".',
  args: {
    query: tool.schema.string().optional().describe('Projects filter, e.g. "-status:Done".'),
    limit: tool.schema.number().optional().describe("Max items (default 50)."),
    owner: tool.schema.string().optional(),
    project: tool.schema.string().optional(),
  },
  async execute(args, context) {
    const owner = await resolveOwner(args.owner, context.worktree)
    const { number } = await resolveProject(owner, args.project)
    const argv = ["project", "item-list", String(number), "--owner", owner, "-L", String(args.limit ?? 50), "--format", "json"]
    if (args.query) argv.push("--query", args.query)
    const data = await runGhJson(argv)
    const items = (data?.items ?? []).map((it: any) => {
      const { content, ...rest } = it
      return { ...rest, draftId: content?.id, body: content?.body, contentType: content?.type }
    })
    return JSON.stringify({ owner, project: number, count: items.length, items }, null, 2)
  },
})

export const item_note = tool({
  description:
    "Append a markdown note to a DRAFT item's body (running log). Use the item id (PVTI_...) from github_project_item_list. owner/project default to the current repo owner and a board titled \"Roadmap\".",
  args: {
    item: tool.schema.string().describe("Project item id (PVTI_...)."),
    text: tool.schema.string().describe("Markdown to append."),
    owner: tool.schema.string().optional(),
    project: tool.schema.string().optional(),
  },
  async execute(args, context) {
    const owner = await resolveOwner(args.owner, context.worktree)
    const { number } = await resolveProject(owner, args.project)
    const data = await runGhJson(["project", "item-list", String(number), "--owner", owner, "-L", "200", "--format", "json"])
    const it = (data?.items ?? []).find((x: any) => x.id === args.item)
    if (!it) throw new Error(`Item ${args.item} not found in project ${number} (${owner}).`)
    if (it.content?.type !== "DraftIssue" || !it.content?.id) {
      throw new Error("item_note only supports draft items. For a real issue, comment on the issue instead.")
    }
    const current: string = it.content.body ?? ""
    const next = `${current.trimEnd()}\n\n${args.text.trim()}\n`
    await runGh(["project", "item-edit", "--id", it.content.id, "--body", next])
    return JSON.stringify({ ok: true, item: args.item, draftId: it.content.id })
  },
})

export const item_promote = tool({
  description:
    'Promote (convert) a DRAFT project item into a real GitHub Issue in the given repo. The draft title/body become the issue; the item stays on the board with its field values; real-issue features (labels, assignees, milestone, the built-in Repository field) become available. If the item has a "_Milestone" value, a matching repo milestone is found-or-created and assigned to the issue. By default clears the "_Repository" and "_Milestone" fields afterwards (now redundant). The board is derived from the item id, so no owner/project is needed.',
  args: {
    item: tool.schema.string().describe("Project item id (PVTI_...) of a DRAFT item, from github_project_item_list."),
    repo: tool.schema.string().describe('Target repository "owner/repo" where the issue is created.'),
    clearFields: tool.schema
      .array(tool.schema.string())
      .optional()
      .describe('Field names to clear after conversion. Defaults to ["_Repository","_Milestone"]. Pass [] to keep all fields.'),
  },
  async execute(args) {
    const repoId = (await runGh(["repo", "view", args.repo, "--json", "id", "--jq", ".id"])).trim()
    if (!repoId) throw new Error(`Could not resolve repository id for "${args.repo}".`)

    // 1. Convert the draft into a real issue.
    const mutation = `mutation{convertProjectV2DraftIssueItemToIssue(input:{itemId:${gqlStr(args.item)},repositoryId:${gqlStr(
      repoId,
    )}}){item{id content{... on Issue{number url}}}}}`
    const res = await runGhJson(["api", "graphql", "-f", `query=${mutation}`])
    const conv = res?.data?.convertProjectV2DraftIssueItemToIssue?.item
    if (!conv) throw new Error(`Convert failed: ${JSON.stringify(res?.errors ?? res)}`)
    const content = conv.content ?? null
    const issueNumber: number | undefined = content?.number

    // 2. Read the item's project, fields and the _Milestone value (post-convert it is preserved).
    const q =
      "query($id:ID!,$mname:String!){node(id:$id){... on ProjectV2Item{project{id fields(first:50){nodes{... on ProjectV2FieldCommon{id name}}}} ms:fieldValueByName(name:$mname){... on ProjectV2ItemFieldTextValue{text}}}}}"
    const data = await runGhJson(["api", "graphql", "-f", `query=${q}`, "-f", `id=${args.item}`, "-f", "mname=_Milestone"])
    const project = data?.data?.node?.project
    const fields: any[] = project?.fields?.nodes ?? []
    const milestoneTitle: string | undefined = (data?.data?.node?.ms?.text ?? "").trim() || undefined

    // 3. Sync _Milestone -> a real repo milestone (find-or-create) and assign it to the issue.
    let milestone: any = null
    if (milestoneTitle && issueNumber) {
      const list = await runGhJson(["api", `repos/${args.repo}/milestones?state=all&per_page=100`])
      milestone = (list ?? []).find((m: any) => m.title === milestoneTitle)
      if (!milestone) milestone = await runGhJson(["api", `repos/${args.repo}/milestones`, "-f", `title=${milestoneTitle}`])
      if (milestone?.number != null) {
        // PATCH by milestone number is reliable; `gh issue edit --milestone` can silently no-op.
        await runGh(["api", "-X", "PATCH", `repos/${args.repo}/issues/${issueNumber}`, "-F", `milestone=${milestone.number}`])
      }
    }

    // 4. Clear now-redundant fields (the built-in Repository / Milestone cover them).
    const toClear = args.clearFields ?? ["_Repository", "_Milestone"]
    const cleared: string[] = []
    if (toClear.length && project?.id) {
      for (const name of toClear) {
        const f = fields.find((x: any) => x?.name && String(x.name).toLowerCase() === name.toLowerCase())
        if (!f) continue
        await runGh(["project", "item-edit", "--id", args.item, "--project-id", project.id, "--field-id", f.id, "--clear"])
        cleared.push(name)
      }
    }

    return JSON.stringify({
      ok: true,
      item: args.item,
      repo: args.repo,
      issue: content ? { number: content.number, url: content.url } : null,
      milestone: milestone ? { number: milestone.number, title: milestone.title } : null,
      clearedFields: cleared,
    })
  },
})

// ---- Views (REST projectsV2 views API) ----
// GraphQL/gh cannot create views; the REST projectsV2 views endpoint can set
// name, layout, filter and visible columns. Grouping / sort / roadmap zoom &
// date-binding are NOT settable via the API (UI only) — which is why the
// standard boards are seeded by copying the UI-configured "Roadmap Template".
async function resolveRestBase(owner: string): Promise<string> {
  let login = owner
  if (login === "@me") login = (await runGh(["api", "user", "--jq", ".login"])).trim()
  const type = (await runGh(["api", `users/${login}`, "--jq", ".type"])).trim()
  return type === "Organization" ? `/orgs/${login}` : `/users/${login}`
}

async function getViewNames(projectNodeId: string): Promise<string[]> {
  const q = "query($id:ID!){node(id:$id){... on ProjectV2{views(first:50){nodes{name}}}}}"
  const data = await runGhJson(["api", "graphql", "-f", `query=${q}`, "-f", `id=${projectNodeId}`])
  return (data?.data?.node?.views?.nodes ?? []).map((v: any) => String(v.name))
}

export const view_ensure = tool({
  description:
    'Idempotently ensure a saved VIEW exists on a project, via the REST projectsV2 views API (gh/GraphQL cannot create views). Creates the view only if no view of that name exists (case-insensitive). `layout` is "table", "board" or "roadmap"; optional `filter` (Projects filter syntax) and `visibleFields` (field NAMES → columns; ignored for roadmap). LIMITATION: grouping, sort, and roadmap zoom / date-binding are NOT settable via the API — configure those once in the UI (the standard boards inherit them by copying the "Roadmap Template"). owner defaults to the current repo owner (else @me); project defaults to "Roadmap".',
  args: {
    name: tool.schema.string().describe('View name, e.g. "Kanban" or "Backlog".'),
    layout: tool.schema.enum(["table", "board", "roadmap"]).describe("View layout."),
    filter: tool.schema.string().optional().describe('Projects filter, e.g. "-status:Done -status:Cancelled".'),
    visibleFields: tool.schema.array(tool.schema.string()).optional().describe("Field names to show as columns (table/board only)."),
    owner: tool.schema.string().optional().describe('Owner login or "@me". Defaults to current repo owner, else @me.'),
    project: tool.schema.string().optional().describe('Project number or title. Defaults to "Roadmap".'),
  },
  async execute(args, context) {
    const owner = await resolveOwner(args.owner, context.worktree)
    const { number, id: projectId } = await resolveProject(owner, args.project)
    const existing = await getViewNames(projectId)
    if (existing.some((n) => n.toLowerCase() === args.name.toLowerCase())) {
      return JSON.stringify({ created: false, unchanged: true, view: args.name })
    }
    const base = await resolveRestBase(owner)
    const path = `${base}/projectsV2/${number}/views`
    const argv = ["api", "--method", "POST", "-H", REST_API_VERSION, path, "-f", `name=${args.name}`, "-f", `layout=${args.layout}`]
    if (args.filter) argv.push("-f", `filter=${args.filter}`)
    if (args.layout !== "roadmap" && args.visibleFields?.length) {
      const restFields: any[] = (await runGhJson(["api", "-H", REST_API_VERSION, `${base}/projectsV2/${number}/fields`, "--paginate"])) ?? []
      const byName = new Map(restFields.map((f: any) => [String(f.name).toLowerCase(), f.id]))
      for (const fn of args.visibleFields) {
        const fid = byName.get(fn.toLowerCase())
        if (fid != null) argv.push("-F", `visible_fields[]=${fid}`)
      }
    }
    const created = await runGhJson(argv)
    return JSON.stringify({ created: true, view: { number: created?.number, name: created?.name, layout: created?.layout } })
  },
})

// ---- Issue lifecycle: hierarchy & linked development branches ----
// Thin idempotent wrappers over `gh issue edit --add-sub-issue / --parent`
// (gh >= 2.94.0) and `gh issue develop`. They take an issue number — typically
// returned by item_promote — and operate on the current repo, or pass `repo`.

function withRepo(argv: string[], repo?: string): string[] {
  return repo ? [...argv, "--repo", repo] : argv
}

async function resolveRepo(repo: string | undefined, cwd?: string): Promise<string> {
  if (repo && repo.trim()) return repo.trim()
  const r = (await runGh(["repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"], cwd)).trim()
  if (!r) throw new Error("Could not resolve current repository; pass `repo` as owner/repo.")
  return r
}

// Issue Types are an org-repo feature. Missing type / unsupported repo -> warn, don't fail.
async function setIssueType(issue: string, type: string, repo?: string, cwd?: string): Promise<boolean> {
  try {
    await runGh(withRepo(["issue", "edit", issue, "--type", type], repo), cwd)
    return true
  } catch {
    return false
  }
}

async function remoteBranchExists(branch: string, repo: string, cwd?: string): Promise<boolean> {
  try {
    await runGh(["api", `repos/${repo}/branches/${encodeURIComponent(branch)}`], cwd)
    return true
  } catch {
    return false
  }
}

async function listLinkedBranches(issue: string, repo?: string, cwd?: string): Promise<string[]> {
  // `gh issue develop --list` prints one branch per line as "name\turl" (or just name).
  const out = await runGh(withRepo(["issue", "develop", "--list", issue], repo), cwd)
  return out
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => l.split("\t")[0].trim())
    .filter(Boolean)
}

function parseBranchFromOutput(out: string): string | null {
  // gh prints the new branch as a plain (NOT percent-encoded) tree URL:
  // "host/owner/repo/tree/<branch>" — see cli/cli's develop.go.
  const m = out.match(/\/tree\/(.+?)(\s|$)/)
  return m ? m[1] : null
}

// Extract the issue number from either a bare number or an issue URL, for
// comparing against the numbers `gh issue view --json subIssues` returns.
function issueRefNumber(ref: string): number | null {
  const trimmed = ref.trim()
  if (/^\d+$/.test(trimmed)) return parseInt(trimmed, 10)
  const m = trimmed.match(/\/issues\/(\d+)(?:[/?#].*)?$/)
  return m ? parseInt(m[1], 10) : null
}

// GitHub's addSubIssue errors ("Issue may not contain duplicate sub-issues")
// on re-adding a sub already under the same parent, and removeSubIssue errors
// similarly on removing one that isn't there — so add/remove need to know the
// parent's current sub-issues to skip subs already in the target state.
async function getSubIssueNumbers(parent: string, repo?: string, cwd?: string): Promise<Set<number>> {
  const data = await runGhJson(withRepo(["issue", "view", parent, "--json", "subIssues"], repo), cwd)
  // `--json subIssues` returns a connection ({ nodes, totalCount }), not a bare
  // array — verified against `gh issue view <n> --json subIssues` output.
  const nums = (data?.subIssues?.nodes ?? [])
    .map((s: any) => s?.number)
    .filter((n: any): n is number => typeof n === "number")
  return new Set<number>(nums)
}

export const issue_link = tool({
  description:
    'Link sub-issues under a parent (epic), or unlink them. On add/set-parent it also sets each sub-issue\'s Issue Type — "Task" by default. Backed by `gh issue edit --add-sub-issue/--parent/--remove-sub-issue/--remove-parent` (gh >= 2.94.0). Idempotent: for add/remove, subs already in the target state are skipped (reported in `unchanged`) rather than re-sent to `gh` (which would otherwise error on a duplicate). Issue Type is best-effort: on a personal repo or when the type is undefined it warns and continues. Operates on the current repo, or pass `repo` as owner/repo.',
  args: {
    parent: tool.schema.string().describe("Parent issue number or URL (for add / remove)."),
    subs: tool.schema.array(tool.schema.string()).describe("Sub-issue numbers or URLs to link / unlink."),
    mode: tool.schema
      .enum(["add", "remove", "set-parent", "remove-parent"])
      .optional()
      .describe(
        '"add" (default): add subs under parent via --add-sub-issue. "set-parent": set each sub\'s parent via --parent. "remove": --remove-sub-issue. "remove-parent": --remove-parent on each sub.',
      ),
    subType: tool.schema
      .string()
      .optional()
      .describe(
        'Issue Type to set on each sub-issue on add/set-parent. Defaults to "Task". Pass "" to skip. Best-effort: warns and continues when Issue Types are unsupported or the type is undefined.',
      ),
    repo: tool.schema.string().optional().describe("Target repository as owner/repo. Defaults to the current repo."),
  },
  async execute(args, context) {
    const mode = args.mode ?? "add"
    const subType = args.subType ?? "Task"
    const cwd = context.worktree

    let applied: string[] = args.subs
    let unchanged: string[] = []

    if (mode === "add" || mode === "remove") {
      // Pre-check against the parent's current sub-issues so a sub already in
      // the target state is skipped instead of re-sent to `gh` (see the
      // getSubIssueNumbers comment for why that would otherwise error).
      const existingNums = await getSubIssueNumbers(args.parent, args.repo, cwd)
      const wantsLinked = mode === "add"
      const targets: string[] = []
      for (const sub of args.subs) {
        const n = issueRefNumber(sub)
        const alreadyInState = n !== null && existingNums.has(n) === wantsLinked
        if (alreadyInState) unchanged.push(sub)
        else targets.push(sub)
      }
      applied = targets
      if (targets.length) {
        const flag = mode === "add" ? "--add-sub-issue" : "--remove-sub-issue"
        await runGh(withRepo(["issue", "edit", args.parent, flag, targets.join(",")], args.repo), cwd)
      }
    } else if (mode === "set-parent") {
      for (const sub of args.subs) {
        await runGh(withRepo(["issue", "edit", sub, "--parent", args.parent], args.repo), cwd)
      }
    } else {
      for (const sub of args.subs) {
        await runGh(withRepo(["issue", "edit", sub, "--remove-parent"], args.repo), cwd)
      }
    }

    // On link operations, set each sub-issue's Type (best-effort) — including
    // subs already linked, in case a prior run linked but didn't tag them.
    let typeSet: string[] = []
    let typeWarned: string[] = []
    if ((mode === "add" || mode === "set-parent") && subType.trim()) {
      for (const sub of args.subs) {
        ;(await setIssueType(sub, subType, args.repo, cwd)) ? typeSet.push(sub) : typeWarned.push(sub)
      }
    }

    return JSON.stringify({
      ok: true,
      mode,
      parent: args.parent,
      applied,
      unchanged,
      type: subType.trim() ? { requested: subType, set: typeSet, warned: typeWarned } : null,
    })
  },
})

export const issue_develop = tool({
  description:
    "Create a linked development branch for an issue (and optionally check it out), or reuse the existing linked branch if one already exists. Backed by `gh issue develop`. The branch shows in the issue's Development panel; a PR opened from it links there automatically. Validates the `base` exists on remote (guards the known silent-fallback bug). Stacked PRs: point `base` at a parent issue's branch. Operates on the current repo, or pass `repo` as owner/repo.",
  args: {
    issue: tool.schema.string().describe("Issue number or URL to create/reuse a development branch for."),
    branch: tool.schema
      .string()
      .optional()
      .describe("Branch name. If omitted, gh derives one from the issue title."),
    base: tool.schema
      .string()
      .optional()
      .describe("Remote branch to create from (defaults to the repo default branch). Verified to exist on remote."),
    checkout: tool.schema
      .boolean()
      .optional()
      .describe("Check out the branch locally after creating it. Only applies when a new branch is created."),
    branchRepo: tool.schema
      .string()
      .optional()
      .describe("owner/repo to create the branch in (defaults to the issue's repo)."),
    repo: tool.schema.string().optional().describe("Target repository as owner/repo. Defaults to the current repo."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const repo = await resolveRepo(args.repo, cwd)

    // 1. Idempotency: reuse an already-linked branch instead of creating a duplicate.
    const existing = await listLinkedBranches(args.issue, repo, cwd)
    if (existing.length) {
      return JSON.stringify({
        ok: true,
        created: false,
        issue: args.issue,
        branch: existing[0],
        repo,
        linkedBranches: existing,
        note: args.checkout
          ? "branch already linked; not recreated (checkout was ignored — checkout it yourself if needed)"
          : "branch already linked; not recreated",
      })
    }

    // 2. Validate base exists on remote (gh otherwise silently falls back to default).
    if (args.base) {
      const ok = await remoteBranchExists(args.base, repo, cwd)
      if (!ok) {
        throw new Error(
          `Base branch "${args.base}" not found on remote ${repo}. gh issue develop would silently fall back to the default branch; refusing.`,
        )
      }
    }

    // 3. Create the linked branch.
    const argv = ["issue", "develop", args.issue, "--repo", repo]
    if (args.branch) argv.push("--name", args.branch)
    if (args.base) argv.push("--base", args.base)
    if (args.checkout) argv.push("--checkout")
    if (args.branchRepo) argv.push("--branch-repo", args.branchRepo)
    const out = await runGh(argv, cwd)
    const branch = args.branch ?? parseBranchFromOutput(out)
    if (!branch) {
      throw new Error(`gh issue develop succeeded but the branch name could not be parsed from output:\n${out}`)
    }

    return JSON.stringify({
      ok: true,
      created: true,
      issue: args.issue,
      branch,
      base: args.base ?? null,
      repo,
      linkedBranches: [branch],
    })
  },
})
