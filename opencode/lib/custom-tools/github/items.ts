import { graphql, paginate } from "./gql"

/**
 * One flat shape for a project item, whatever its content is. Field values
 * (custom and built-in) are flattened by field name; the content carries the
 * issue's own facts (state, milestone, parent, sub-issue progress, type) so a
 * caller reads a board and its issues in one pass.
 */

export type ItemContent =
  | { type: "DraftIssue"; id: string; title: string; body: string }
  | {
      type: "Issue" | "PullRequest"
      id: string
      number: number
      title: string
      url: string
      state: string
      repo: string
      milestone: string | null
      labels: string[]
      assignees: string[]
      issueType: string | null
      parent: { number: number; title: string; url: string; repo: string } | null
      subIssues: { total: number; completed: number; percent: number } | null
    }

export type Item = {
  id: string
  archived: boolean
  fields: Record<string, unknown>
  content: ItemContent | null
}

export const ITEM_FRAGMENT = `id isArchived
fieldValues(first:50){nodes{
 ... on ProjectV2ItemFieldTextValue{text field{... on ProjectV2FieldCommon{name}}}
 ... on ProjectV2ItemFieldNumberValue{number field{... on ProjectV2FieldCommon{name}}}
 ... on ProjectV2ItemFieldDateValue{date field{... on ProjectV2FieldCommon{name}}}
 ... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2FieldCommon{name}}}
 ... on ProjectV2ItemFieldIterationValue{title startDate duration field{... on ProjectV2FieldCommon{name}}}
 ... on ProjectV2ItemFieldMilestoneValue{milestone{title} field{... on ProjectV2FieldCommon{name}}}
 ... on ProjectV2ItemFieldRepositoryValue{repository{nameWithOwner} field{... on ProjectV2FieldCommon{name}}}
 ... on ProjectV2ItemFieldLabelValue{labels(first:20){nodes{name}} field{... on ProjectV2FieldCommon{name}}}
 ... on ProjectV2ItemFieldUserValue{users(first:10){nodes{login}} field{... on ProjectV2FieldCommon{name}}}
 ... on ProjectV2ItemFieldPullRequestValue{pullRequests(first:10){nodes{number url}} field{... on ProjectV2FieldCommon{name}}}
}}
content{__typename
 ... on DraftIssue{id title body}
 ... on Issue{id number title url state repository{nameWithOwner} milestone{title} issueType{name} labels(first:20){nodes{name}} assignees(first:10){nodes{login}} parent{number title url repository{nameWithOwner}} subIssuesSummary{total completed percentCompleted}}
 ... on PullRequest{id number title url state repository{nameWithOwner} milestone{title} labels(first:20){nodes{name}} assignees(first:10){nodes{login}}}
}`

function fieldValue(v: any): unknown {
  if (!v || !v.field?.name) return undefined
  if ("text" in v) return v.text
  if ("number" in v) return v.number
  if ("date" in v) return v.date
  if ("title" in v && "startDate" in v) return { title: v.title, startDate: v.startDate, duration: v.duration }
  if ("name" in v) return v.name
  if ("milestone" in v) return v.milestone?.title ?? null
  if ("repository" in v) return v.repository?.nameWithOwner ?? null
  if ("labels" in v) return (v.labels?.nodes ?? []).map((l: any) => l.name)
  if ("users" in v) return (v.users?.nodes ?? []).map((u: any) => u.login)
  if ("pullRequests" in v) return (v.pullRequests?.nodes ?? []).map((p: any) => p.number)
  return undefined
}

export function normalizeContent(c: any): ItemContent | null {
  if (!c?.__typename) return null
  if (c.__typename === "DraftIssue") return { type: "DraftIssue", id: c.id, title: c.title ?? "", body: c.body ?? "" }
  if (c.__typename !== "Issue" && c.__typename !== "PullRequest") return null
  return {
    type: c.__typename,
    id: c.id,
    number: c.number,
    title: c.title ?? "",
    url: c.url,
    state: c.state,
    repo: c.repository?.nameWithOwner ?? "",
    milestone: c.milestone?.title ?? null,
    labels: (c.labels?.nodes ?? []).map((l: any) => l.name),
    assignees: (c.assignees?.nodes ?? []).map((a: any) => a.login),
    issueType: c.issueType?.name ?? null,
    parent: c.parent ? { number: c.parent.number, title: c.parent.title, url: c.parent.url, repo: c.parent.repository?.nameWithOwner ?? "" } : null,
    subIssues: c.subIssuesSummary ? { total: c.subIssuesSummary.total, completed: c.subIssuesSummary.completed, percent: c.subIssuesSummary.percentCompleted } : null,
  }
}

export function normalizeItem(it: any): Item {
  const fields: Record<string, unknown> = {}
  for (const v of it?.fieldValues?.nodes ?? []) {
    const value = fieldValue(v)
    if (value !== undefined) fields[v.field.name] = value
  }
  return { id: it.id, archived: Boolean(it.isArchived), fields, content: normalizeContent(it.content) }
}

const ITEMS_QUERY = `query($id:ID!,$after:String){node(id:$id){... on ProjectV2{items(first:50,after:$after){pageInfo{hasNextPage endCursor}nodes{${ITEM_FRAGMENT}}}}}}`

export async function listItems(projectId: string, options: { limit?: number; cwd?: string } = {}): Promise<Item[]> {
  const nodes = await paginate<any>(ITEMS_QUERY, { id: projectId }, (d) => d?.node?.items, { limit: options.limit, cwd: options.cwd })
  return nodes.map(normalizeItem)
}

const ITEM_QUERY = `query($id:ID!){node(id:$id){... on ProjectV2Item{project{id} ${ITEM_FRAGMENT}}}}`

export async function getItem(itemId: string, cwd?: string): Promise<{ projectId: string; item: Item }> {
  const data = await graphql(ITEM_QUERY, { id: itemId }, cwd)
  if (!data?.node?.id) throw new Error(`Project item ${itemId} not found.`)
  return { projectId: data.node.project?.id, item: normalizeItem(data.node) }
}

/** The issue's own project memberships: item ids per project, so a tool can update the board from an issue. */
export const ISSUE_PROJECT_ITEMS = "projectItems(first:20){nodes{id isArchived project{id number title url}}}"
