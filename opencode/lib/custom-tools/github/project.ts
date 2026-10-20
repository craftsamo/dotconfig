import { runGh } from "../exec"
import { graphql, lit, paginate } from "./gql"
import { parseProjectRef, sameName } from "./refs"
import type { OwnerType, RepoContext } from "./repo"

/**
 * Which GitHub Project (v2) a call is about, and its fields.
 *
 * Projects are owned by a user or an organization only; a repository can
 * link one. The default route, when nothing is explicit, follows that:
 *   1. explicit  — a `project` argument (URL, owner/N, number, or title)
 *   2. linked    — a project linked to the repository (title match if given)
 *   3. org       — the owning organization's board titled DEFAULT_TITLE
 *   4. user      — the viewer's own board titled DEFAULT_TITLE
 * A route is skipped when its project does not exist or the viewer cannot
 * update it; the result says which routes were considered and why each was
 * passed over, so a caller never writes to a board by surprise.
 */

export const DEFAULT_TITLE = "Roadmap"
export const REST_API_VERSION = "X-GitHub-Api-Version: 2026-03-10"

export type Project = {
  id: string
  number: number
  title: string
  url: string
  closed: boolean
  owner: { login: string; type: OwnerType }
  viewerCanUpdate: boolean
}

export type Route = "explicit" | "linked" | "org" | "user"
export type Considered = { route: Route; outcome: string }
export type Resolved = { project: Project; route: Route; considered: Considered[] }

const PROJECT_FIELDS = "id number title url closed viewerCanUpdate owner{__typename ... on User{login} ... on Organization{login}}"

function toProject(p: any): Project {
  return {
    id: p.id,
    number: p.number,
    title: p.title,
    url: p.url,
    closed: Boolean(p.closed),
    owner: { login: p.owner?.login ?? "", type: p.owner?.__typename === "Organization" ? "Organization" : "User" },
    viewerCanUpdate: Boolean(p.viewerCanUpdate),
  }
}

async function ownerType(login: string, cwd?: string): Promise<OwnerType | null> {
  try {
    const data = await graphql("query($login:String!){repositoryOwner(login:$login){__typename}}", { login }, cwd)
    const t = data?.repositoryOwner?.__typename
    return t === "Organization" ? "Organization" : t === "User" ? "User" : null
  } catch {
    return null
  }
}

async function projectByNumber(login: string, number: number, cwd?: string): Promise<Project | null> {
  const type = await ownerType(login, cwd)
  if (!type) return null
  const field = type === "Organization" ? "organization" : "user"
  try {
    const data = await graphql(`query($login:String!,$n:Int!){${field}(login:$login){projectV2(number:$n){${PROJECT_FIELDS}}}}`, { login, n: number }, cwd)
    const p = data?.[field]?.projectV2
    return p ? toProject(p) : null
  } catch {
    return null
  }
}

async function projectsByTitle(login: string | "@me", title: string, cwd?: string): Promise<Project[]> {
  const root = login === "@me" ? "viewer" : (await ownerType(login, cwd)) === "Organization" ? "organization" : "user"
  const sel = root === "viewer" ? "viewer" : `${root}(login:$login)`
  const vars = root === "viewer" ? { q: title } : { login, q: title }
  const decl = root === "viewer" ? "$q:String!" : "$login:String!,$q:String!"
  try {
    const data = await graphql(`query(${decl}){${sel}{projectsV2(first:20,query:$q){nodes{${PROJECT_FIELDS}}}}}`, vars, cwd)
    const nodes: any[] = data?.[root]?.projectsV2?.nodes ?? []
    return nodes.map(toProject).filter((p) => sameName(p.title, title) && !p.closed)
  } catch {
    return []
  }
}

async function linkedProjects(repo: RepoContext, cwd?: string): Promise<Project[]> {
  const [owner, name] = repo.nameWithOwner.split("/")
  const data = await graphql(
    `query($owner:String!,$name:String!){repository(owner:$owner,name:$name){projectsV2(first:20){nodes{${PROJECT_FIELDS}}}}}`,
    { owner, name },
    cwd,
  )
  return (data?.repository?.projectsV2?.nodes ?? []).map(toProject).filter((p: Project) => !p.closed)
}

export type ResolveInput = {
  /** URL, `owner/N`, a number (with `owner`), or a title. */
  project?: string
  /** Owner login or "@me"; scopes a number or title. */
  owner?: string
  repo?: RepoContext | null
  /** Title used on the linked / org / user routes. Defaults to DEFAULT_TITLE. */
  title?: string
  cwd?: string
}

export async function resolveProject(input: ResolveInput): Promise<Resolved> {
  const considered: Considered[] = []
  const cwd = input.cwd
  const ref = parseProjectRef(input.project, input.owner?.trim() || undefined)
  const title = input.title?.trim() || DEFAULT_TITLE

  if (ref.number !== undefined || ref.title !== undefined || ref.owner !== undefined) {
    const login = ref.owner ?? (ref.number !== undefined ? input.repo?.owner.login : undefined)
    if (ref.number !== undefined) {
      if (!login) throw new Error(`Project ${ref.number} needs an owner: pass owner/N, a project URL, or \`owner\`.`)
      const p = await projectByNumber(login === "@me" ? await viewerLogin(cwd) : login, ref.number, cwd)
      if (!p) throw new Error(`Project ${login}/${ref.number} not found or not accessible.`)
      return { project: p, route: "explicit", considered: [{ route: "explicit", outcome: `${login}/${ref.number}` }] }
    }
    if (ref.title !== undefined && ref.owner) {
      const found = await projectsByTitle(ref.owner, ref.title, cwd)
      if (!found.length) throw new Error(`No open project titled "${ref.title}" for owner "${ref.owner}".`)
      return { project: found[0], route: "explicit", considered: [{ route: "explicit", outcome: `${ref.owner}/"${ref.title}"` }] }
    }
    if (ref.title === undefined && ref.owner) {
      const found = await projectsByTitle(ref.owner, title, cwd)
      if (!found.length) throw new Error(`No open project titled "${title}" for owner "${ref.owner}". Create it with gh_project_create.`)
      return { project: found[0], route: "explicit", considered: [{ route: "explicit", outcome: `${ref.owner}/"${title}"` }] }
    }
  }
  // Only a title (no owner): search the routes below for that title.
  const wanted = ref.title ?? title
  const explicitTitle = ref.title !== undefined

  if (input.repo) {
    const linked = await linkedProjects(input.repo, cwd)
    const match = explicitTitle ? linked.filter((p) => sameName(p.title, wanted)) : linked
    const writable = match.filter((p) => p.viewerCanUpdate)
    if (writable.length === 1 || (writable.length > 1 && !explicitTitle)) {
      const pick = writable.find((p) => sameName(p.title, wanted)) ?? writable[0]
      considered.push({ route: "linked", outcome: `${pick.owner.login}/${pick.number} "${pick.title}"` + (writable.length > 1 ? ` (of ${writable.length} linked)` : "") })
      return { project: pick, route: "linked", considered }
    }
    if (writable.length > 1) {
      throw new Error(
        `${writable.length} linked projects titled "${wanted}" on ${input.repo.nameWithOwner}; pass \`project\` as a URL or owner/N.`,
      )
    }
    considered.push({
      route: "linked",
      outcome: !linked.length ? "no project linked to the repository" : match.length ? "linked project is read-only for the viewer" : `no linked project titled "${wanted}"`,
    })
    if (input.repo.owner.type === "Organization") {
      const found = (await projectsByTitle(input.repo.owner.login, wanted, cwd)).filter((p) => p.viewerCanUpdate)
      if (found.length) {
        considered.push({ route: "org", outcome: `${found[0].owner.login}/${found[0].number} "${found[0].title}"` })
        return { project: found[0], route: "org", considered }
      }
      considered.push({ route: "org", outcome: `no writable project titled "${wanted}" in ${input.repo.owner.login}` })
    } else {
      considered.push({ route: "org", outcome: "repository is user-owned" })
    }
  } else {
    considered.push({ route: "linked", outcome: "no repository context" })
    considered.push({ route: "org", outcome: "no repository context" })
  }

  const own = await projectsByTitle("@me", wanted, cwd)
  if (own.length) {
    considered.push({ route: "user", outcome: `${own[0].owner.login}/${own[0].number} "${own[0].title}"` })
    return { project: own[0], route: "user", considered }
  }
  considered.push({ route: "user", outcome: `no project titled "${wanted}" owned by the viewer` })
  throw new Error(
    `No project resolved for "${wanted}": ${considered.map((c) => `${c.route}: ${c.outcome}`).join("; ")}. Pass \`project\` explicitly or create one with gh_project_create.`,
  )
}

export async function viewerLogin(cwd?: string): Promise<string> {
  const data = await graphql("query{viewer{login}}", {}, cwd)
  return data?.viewer?.login ?? ""
}

export async function projectById(id: string, cwd?: string): Promise<Project> {
  const data = await graphql(`query($id:ID!){node(id:$id){... on ProjectV2{${PROJECT_FIELDS}}}}`, { id }, cwd)
  if (!data?.node?.id) throw new Error(`Project ${id} not found.`)
  return toProject(data.node)
}

// ---- Fields ----

export type FieldOption = { id: string; name: string; color?: string; description?: string }
export type Iteration = { id: string; title: string; startDate: string; duration: number }
export type Field = { id: string; name: string; dataType: string; options?: FieldOption[]; iterations?: Iteration[] }

const FIELDS_QUERY =
  "query($id:ID!,$after:String){node(id:$id){... on ProjectV2{fields(first:50,after:$after){pageInfo{hasNextPage endCursor}nodes{__typename ... on ProjectV2FieldCommon{id name dataType} ... on ProjectV2SingleSelectField{options{id name color description}} ... on ProjectV2IterationField{configuration{iterations{id title startDate duration}}}}}}}}"

export async function getFields(projectId: string, cwd?: string): Promise<Field[]> {
  const nodes = await paginate<any>(FIELDS_QUERY, { id: projectId }, (d) => d?.node?.fields, { cwd, limit: 200 })
  return nodes
    .filter((f) => f?.id)
    .map((f) => ({
      id: f.id,
      name: f.name,
      dataType: f.dataType,
      options: f.options,
      iterations: f.configuration?.iterations,
    }))
}

export function findField(fields: Field[], name: string): Field {
  const f = fields.find((x) => sameName(x.name, name))
  if (!f) throw new Error(`Field "${name}" not found. Available: ${fields.map((x) => x.name).join(", ")}`)
  return f
}

/** Built-in field names GitHub reserves; a custom field cannot take one. */
export const BUILTIN_FIELD_NAMES = new Set([
  "title", "assignees", "labels", "milestone", "repository", "reviewers", "linked pull requests",
  "parent issue", "sub-issues progress", "type", "status", "tracks", "tracked by",
])

/** Built-in field types whose values come from the issue itself, not from the board. */
const BUILTIN_TYPES = new Set(["TITLE", "ASSIGNEES", "LABELS", "MILESTONE", "REPOSITORY", "LINKED_PULL_REQUESTS", "REVIEWERS", "PARENT_ISSUE", "SUB_ISSUES_PROGRESS", "ISSUE_TYPE", "TRACKS", "TRACKED_BY"])

/** Sets one field on an item, or clears it when `value` is null. */
export async function setItemField(projectId: string, itemId: string, field: Field, value: string | null, cwd?: string): Promise<void> {
  if (BUILTIN_TYPES.has(field.dataType)) {
    throw new Error(`"${field.name}" is a built-in field; set it on the issue (gh_issue_update) rather than on the board.`)
  }
  const base = ["project", "item-edit", "--id", itemId, "--project-id", projectId, "--field-id", field.id]
  if (value === null) {
    await runGh([...base, "--clear"], cwd)
    return
  }
  switch (field.dataType) {
    case "SINGLE_SELECT": {
      const opt = (field.options ?? []).find((o) => sameName(o.name, value))
      if (!opt) throw new Error(`Option "${value}" not in field "${field.name}". Options: ${(field.options ?? []).map((o) => o.name).join(", ")}`)
      await runGh([...base, "--single-select-option-id", opt.id], cwd)
      return
    }
    case "ITERATION": {
      const it = (field.iterations ?? []).find((i) => sameName(i.title, value) || i.id === value)
      if (!it) throw new Error(`Iteration "${value}" not in field "${field.name}". Iterations: ${(field.iterations ?? []).map((i) => i.title).join(", ")}`)
      await runGh([...base, "--iteration-id", it.id], cwd)
      return
    }
    case "NUMBER":
      await runGh([...base, "--number", value], cwd)
      return
    case "DATE":
      await runGh([...base, "--date", value], cwd)
      return
    default:
      await runGh([...base, "--text", value], cwd)
  }
}

/** Applies `fields` (name -> value, null clears) to an item; returns the names applied. */
export async function applyFields(projectId: string, itemId: string, fields: Field[], values: Record<string, string | null>, cwd?: string): Promise<string[]> {
  const applied: string[] = []
  for (const [name, value] of Object.entries(values)) {
    await setItemField(projectId, itemId, findField(fields, name), value, cwd)
    applied.push(name)
  }
  return applied
}

function optionsLiteral(opts: FieldOption[]): string {
  return `[${opts
    .map((o) => [o.id ? `id:${lit(o.id)}` : null, `name:${lit(o.name)}`, `color:${o.color || "GRAY"}`, `description:${lit(o.description ?? "")}`].filter(Boolean).join(","))
    .map((s) => `{${s}}`)
    .join(",")}]`
}

export type SelectSpec = { name: string; color?: string }

/**
 * Ensures a single-select field has every option in `wanted`, keeping existing
 * options (and their ids, so assignments survive) and adding the missing ones.
 * Returns the names added.
 */
export async function ensureSelectOptions(field: Field, wanted: SelectSpec[], cwd?: string): Promise<string[]> {
  const existing = field.options ?? []
  const toAdd = wanted.filter((w) => !existing.some((o) => sameName(o.name, w.name)))
  if (!toAdd.length) return []
  const merged: FieldOption[] = [
    ...existing.map((o) => ({ id: o.id, name: o.name, color: o.color, description: o.description ?? "" })),
    ...toAdd.map((w) => ({ id: "", name: w.name, color: w.color, description: "" })),
  ]
  const mutation = `mutation{updateProjectV2Field(input:{fieldId:${lit(field.id)},singleSelectOptions:${optionsLiteral(merged)}}){projectV2Field{... on ProjectV2SingleSelectField{id}}}}`
  await graphql(mutation, {}, cwd)
  return toAdd.map((w) => w.name)
}

export type FieldSpec = { name: string; dataType: "TEXT" | "NUMBER" | "DATE" | "SINGLE_SELECT"; options?: SelectSpec[] }

/** Creates a field when missing, else tops up its options. Returns what changed. */
export async function ensureField(project: Project, fields: Field[], spec: FieldSpec, cwd?: string): Promise<{ created: boolean; addedOptions: string[]; field: Field }> {
  const existing = fields.find((f) => sameName(f.name, spec.name))
  if (existing) {
    const addedOptions = spec.dataType === "SINGLE_SELECT" && spec.options?.length ? await ensureSelectOptions(existing, spec.options, cwd) : []
    return { created: false, addedOptions, field: existing }
  }
  if (BUILTIN_FIELD_NAMES.has(spec.name.trim().toLowerCase())) {
    throw new Error(`"${spec.name}" is a built-in field name; GitHub refuses a custom field with it. Pick another name.`)
  }
  const argv = ["project", "field-create", String(project.number), "--owner", project.owner.login, "--name", spec.name, "--data-type", spec.dataType]
  if (spec.dataType === "SINGLE_SELECT") {
    const opts = spec.options ?? []
    if (!opts.length) throw new Error("SINGLE_SELECT needs at least one option.")
    argv.push("--single-select-options", opts.map((o) => o.name).join(","))
  }
  await runGh(argv, cwd)
  const refreshed = await getFields(project.id, cwd)
  const field = findField(refreshed, spec.name)
  if (spec.dataType === "SINGLE_SELECT" && spec.options?.some((o) => o.color)) {
    // field-create cannot set colors; one update pass paints them.
    const painted = (field.options ?? []).map((o) => ({ ...o, color: spec.options!.find((w) => sameName(w.name, o.name))?.color ?? o.color }))
    await graphql(`mutation{updateProjectV2Field(input:{fieldId:${lit(field.id)},singleSelectOptions:${optionsLiteral(painted)}}){projectV2Field{... on ProjectV2SingleSelectField{id}}}}`, {}, cwd)
  }
  return { created: true, addedOptions: [], field }
}

/** The REST base for a project owner (`/orgs/<login>` or `/users/<login>`). */
export const restBase = (project: Project) => (project.owner.type === "Organization" ? `/orgs/${project.owner.login}` : `/users/${project.owner.login}`)
