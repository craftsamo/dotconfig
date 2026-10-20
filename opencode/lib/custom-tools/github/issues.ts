import { graphql, paginate } from "./gql"
import { ISSUE_PROJECT_ITEMS } from "./items"
import { readKind } from "./kind"

/**
 * Issue reads shared by the issue and project tools: one full picture of an
 * issue (hierarchy, dependencies, board memberships, linked branches and
 * PRs) and the lighter list shape.
 */

export type IssueBrief = { number: number; title: string; url: string; state: string; repo: string }

export type IssueDetail = {
  id: string
  number: number
  title: string
  url: string
  state: string
  stateReason: string | null
  repo: string
  body: string
  author: string | null
  assignees: string[]
  labels: string[]
  milestone: { number: number; title: string; dueOn: string | null } | null
  issueType: string | null
  kind: string | null
  parent: IssueBrief | null
  subIssues: IssueBrief[]
  subIssuesSummary: { total: number; completed: number; percent: number } | null
  blockedBy: IssueBrief[]
  blocking: IssueBrief[]
  linkedBranches: string[]
  closingPullRequests: { number: number; title: string; url: string; state: string; merged: boolean }[]
  projects: { itemId: string; archived: boolean; number: number; title: string; url: string; projectId: string }[]
  comments: { author: string | null; createdAt: string; body: string; url: string }[]
  commentCount: number
  createdAt: string
  updatedAt: string
}

const BRIEF = "number title url state repository{nameWithOwner}"
const brief = (n: any): IssueBrief => ({ number: n.number, title: n.title, url: n.url, state: n.state, repo: n.repository?.nameWithOwner ?? "" })

const DETAIL_QUERY = `query($owner:String!,$name:String!,$n:Int!,$comments:Int!){repository(owner:$owner,name:$name){issue(number:$n){
 id number title url state stateReason body createdAt updatedAt author{login}
 repository{nameWithOwner}
 assignees(first:20){nodes{login}} labels(first:30){nodes{name}}
 milestone{number title dueOn} issueType{name}
 parent{${BRIEF}}
 subIssues(first:100){nodes{${BRIEF}}} subIssuesSummary{total completed percentCompleted}
 linkedBranches(first:20){nodes{ref{name}}}
 closedByPullRequestsReferences(first:20,includeClosedPrs:true){nodes{number title url state merged}}
 ${ISSUE_PROJECT_ITEMS}
 comments(last:$comments){totalCount nodes{author{login} createdAt body url}}
}}}`

const DEPS_QUERY = `query($owner:String!,$name:String!,$n:Int!){repository(owner:$owner,name:$name){issue(number:$n){blockedBy(first:50){nodes{${BRIEF}}} blocking(first:50){nodes{${BRIEF}}}}}}`

export async function getIssue(repo: string, number: number, options: { comments?: number; cwd?: string } = {}): Promise<IssueDetail> {
  const [owner, name] = repo.split("/")
  const cwd = options.cwd
  const data = await graphql(DETAIL_QUERY, { owner, name, n: number, comments: options.comments ?? 5 }, cwd)
  const i = data?.repository?.issue
  if (!i) throw new Error(`Issue ${repo}#${number} not found.`)
  let blockedBy: IssueBrief[] = []
  let blocking: IssueBrief[] = []
  try {
    const d = await graphql(DEPS_QUERY, { owner, name, n: number }, cwd)
    blockedBy = (d?.repository?.issue?.blockedBy?.nodes ?? []).map(brief)
    blocking = (d?.repository?.issue?.blocking?.nodes ?? []).map(brief)
  } catch {
    // Issue dependencies are not in every schema the viewer can reach; the picture stays usable without them.
  }
  const labels = (i.labels?.nodes ?? []).map((l: any) => l.name)
  return {
    id: i.id,
    number: i.number,
    title: i.title,
    url: i.url,
    state: i.state,
    stateReason: i.stateReason ?? null,
    repo: i.repository?.nameWithOwner ?? repo,
    body: i.body ?? "",
    author: i.author?.login ?? null,
    assignees: (i.assignees?.nodes ?? []).map((a: any) => a.login),
    labels,
    milestone: i.milestone ? { number: i.milestone.number, title: i.milestone.title, dueOn: i.milestone.dueOn ?? null } : null,
    issueType: i.issueType?.name ?? null,
    kind: readKind(i.issueType?.name, labels),
    parent: i.parent ? brief(i.parent) : null,
    subIssues: (i.subIssues?.nodes ?? []).map(brief),
    subIssuesSummary: i.subIssuesSummary ? { total: i.subIssuesSummary.total, completed: i.subIssuesSummary.completed, percent: i.subIssuesSummary.percentCompleted } : null,
    blockedBy,
    blocking,
    linkedBranches: (i.linkedBranches?.nodes ?? []).map((b: any) => b.ref?.name).filter(Boolean),
    closingPullRequests: (i.closedByPullRequestsReferences?.nodes ?? []).map((p: any) => ({ number: p.number, title: p.title, url: p.url, state: p.state, merged: Boolean(p.merged) })),
    projects: (i.projectItems?.nodes ?? []).map((p: any) => ({ itemId: p.id, archived: Boolean(p.isArchived), number: p.project?.number, title: p.project?.title, url: p.project?.url, projectId: p.project?.id })),
    comments: (i.comments?.nodes ?? []).map((c: any) => ({ author: c.author?.login ?? null, createdAt: c.createdAt, body: c.body ?? "", url: c.url })),
    commentCount: i.comments?.totalCount ?? 0,
    createdAt: i.createdAt,
    updatedAt: i.updatedAt,
  }
}

export type IssueRow = {
  number: number
  title: string
  url: string
  state: string
  kind: string | null
  labels: string[]
  assignees: string[]
  milestone: string | null
  parent: number | null
  subIssues: { total: number; completed: number } | null
  updatedAt: string
}

const LIST_QUERY = `query($q:String!,$first:Int!,$after:String){search(type:ISSUE,query:$q,first:$first,after:$after){issueCount pageInfo{hasNextPage endCursor}nodes{... on Issue{number title url state updatedAt issueType{name} labels(first:20){nodes{name}} assignees(first:10){nodes{login}} milestone{title} parent{number} subIssuesSummary{total completed}}}}}`

/** Issues matching a GitHub search query (the `is:issue` qualifier is added when absent). */
export async function searchIssues(query: string, options: { limit?: number; cwd?: string } = {}): Promise<IssueRow[]> {
  const q = /\bis:issue\b/.test(query) ? query : `is:issue ${query}`
  const limit = options.limit ?? 50
  const nodes = await paginate<any>(LIST_QUERY, { q, first: Math.min(limit, 100) }, (d) => d?.search, { limit, cwd: options.cwd })
  return nodes
    .filter((n) => n?.number)
    .map((n) => {
      const labels = (n.labels?.nodes ?? []).map((l: any) => l.name)
      return {
        number: n.number,
        title: n.title,
        url: n.url,
        state: n.state,
        kind: readKind(n.issueType?.name, labels),
        labels,
        assignees: (n.assignees?.nodes ?? []).map((a: any) => a.login),
        milestone: n.milestone?.title ?? null,
        parent: n.parent?.number ?? null,
        subIssues: n.subIssuesSummary ? { total: n.subIssuesSummary.total, completed: n.subIssuesSummary.completed } : null,
        updatedAt: n.updatedAt,
      }
    })
}

export async function issueNodeId(repo: string, number: number, cwd?: string): Promise<string> {
  const [owner, name] = repo.split("/")
  const data = await graphql("query($owner:String!,$name:String!,$n:Int!){repository(owner:$owner,name:$name){issue(number:$n){id}}}", { owner, name, n: number }, cwd)
  const id = data?.repository?.issue?.id
  if (!id) throw new Error(`Issue ${repo}#${number} not found.`)
  return id
}
