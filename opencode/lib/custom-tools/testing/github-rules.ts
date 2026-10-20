import type { GhRule } from "./repo"

/**
 * Canned fake-gh answers for the GitHub tools' tests. Each helper returns the
 * rule for one call the shared ../github layer makes, keyed on the shape of
 * its query, so a test lists only what its scenario needs.
 */

export const gql = (data: unknown) => JSON.stringify({ data })

export const issueUrl = (repo: string, n: number) => `https://github.com/${repo}/issues/${n}`
const brief = (repo: string, n: number, title = `Issue ${n}`, state = "OPEN") => ({ number: n, title, url: issueUrl(repo, n), state, repository: { nameWithOwner: repo } })

/** The working tree's repository, when a tool is called without `repo`. */
export const currentRepo = (repo: string): GhRule => ({ re: "^repo view --json nameWithOwner", out: repo })

/** The repository context: owner type and the viewer's permission. */
export const repoContext = (repo: string, options: { type?: "User" | "Organization"; permission?: string | null; viewer?: string; member?: boolean } = {}): GhRule[] => {
  const [owner, name] = repo.split("/")
  const type = options.type ?? "User"
  const rules: GhRule[] = [
    {
      re: `repository\\(owner:\\$owner,name:\\$name\\)\\{id nameWithOwner.* -f owner=${owner} -f name=${name}$`,
      out: gql({
        viewer: { login: options.viewer ?? owner },
        repository: {
          id: `R_${name}`,
          nameWithOwner: repo,
          name,
          isPrivate: false,
          viewerPermission: options.permission === undefined ? "ADMIN" : options.permission,
          defaultBranchRef: { name: "main" },
          owner: { __typename: type, login: owner, id: `O_${owner}` },
        },
      }),
    },
  ]
  if (type === "Organization") {
    rules.push({ re: "organization\\(login:\\$login\\)\\{viewerIsAMember\\}", out: gql({ organization: { viewerIsAMember: options.member ?? true } }) })
  }
  return rules
}

export const orgIssueTypes = (names: string[]): GhRule => ({
  re: "issueTypes\\(first:25\\)",
  out: gql({ organization: { issueTypes: { nodes: names.map((n) => ({ id: `IT_${n}`, name: n, isEnabled: true })) } } }),
})

export type IssueSeed = {
  repo: string
  number: number
  title?: string
  body?: string
  state?: string
  labels?: string[]
  issueType?: string | null
  parent?: number | null
  subIssues?: number[]
  blockedBy?: number[]
  blocking?: number[]
  linkedBranches?: string[]
  milestone?: { number: number; title: string } | null
  projects?: { itemId: string; number: number; title: string; projectId?: string }[]
}

/** The two reads getIssue makes: the detail query and the guarded dependencies query. */
export const issueDetail = (seed: IssueSeed): GhRule[] => {
  const { repo, number } = seed
  return [
    {
      re: `issue\\(number:\\$n\\)\\{\\s*id number title url state stateReason body`,
      out: gql({
        repository: {
          issue: {
            id: `I_${number}`,
            number,
            title: seed.title ?? `Issue ${number}`,
            url: issueUrl(repo, number),
            state: seed.state ?? "OPEN",
            stateReason: null,
            body: seed.body ?? "",
            createdAt: "2026-10-01T00:00:00Z",
            updatedAt: "2026-10-02T00:00:00Z",
            author: { login: "me" },
            repository: { nameWithOwner: repo },
            assignees: { nodes: [] },
            labels: { nodes: (seed.labels ?? []).map((name) => ({ name })) },
            milestone: seed.milestone ?? null,
            issueType: seed.issueType ? { name: seed.issueType } : null,
            parent: seed.parent ? brief(repo, seed.parent, "Parent") : null,
            subIssues: { nodes: (seed.subIssues ?? []).map((n) => brief(repo, n)) },
            subIssuesSummary: { total: seed.subIssues?.length ?? 0, completed: 0, percentCompleted: 0 },
            linkedBranches: { nodes: (seed.linkedBranches ?? []).map((name) => ({ ref: { name } })) },
            closedByPullRequestsReferences: { nodes: [] },
            projectItems: { nodes: (seed.projects ?? []).map((p) => ({ id: p.itemId, isArchived: false, project: { id: p.projectId ?? `PVT_${p.number}`, number: p.number, title: p.title, url: `https://github.com/users/o/projects/${p.number}` } })) },
            comments: { totalCount: 0, nodes: [] },
          },
        },
      }),
    },
    {
      re: "blockedBy\\(first:50\\)",
      out: gql({ repository: { issue: { blockedBy: { nodes: (seed.blockedBy ?? []).map((n) => brief(repo, n)) }, blocking: { nodes: (seed.blocking ?? []).map((n) => brief(repo, n)) } } } }),
    },
  ]
}

export type ProjectSeed = { owner: string; type?: "User" | "Organization"; number: number; title?: string; canUpdate?: boolean; closed?: boolean }
export const projectNode = (p: ProjectSeed) => ({
  id: `PVT_${p.owner}_${p.number}`,
  number: p.number,
  title: p.title ?? "Roadmap",
  url: `https://github.com/${p.type === "Organization" ? "orgs" : "users"}/${p.owner}/projects/${p.number}`,
  closed: p.closed ?? false,
  viewerCanUpdate: p.canUpdate ?? true,
  owner: { __typename: p.type ?? "User", login: p.owner },
})

export const ownerType = (login: string, type: "User" | "Organization" | null): GhRule => ({
  re: `repositoryOwner\\(login:\\$login\\)\\{__typename\\}\\} -f login=${login}$`,
  out: gql({ repositoryOwner: type ? { __typename: type } : null }),
})

/** Projects linked to the repository. */
export const linkedProjects = (projects: ProjectSeed[]): GhRule => ({
  re: "repository\\(owner:\\$owner,name:\\$name\\)\\{projectsV2\\(first:20\\)",
  out: gql({ repository: { projectsV2: { nodes: projects.map(projectNode) } } }),
})

/** Projects of an owner (organization / user / viewer) matching a title search. */
export const ownerProjects = (root: "organization" | "user" | "viewer", projects: ProjectSeed[]): GhRule => ({
  re: root === "viewer" ? "\\{viewer\\{projectsV2\\(first:20,query:\\$q\\)" : `${root}\\(login:\\$login\\)\\{projectsV2\\(first:20,query:\\$q\\)`,
  out: gql({ [root]: { projectsV2: { nodes: projects.map(projectNode) } } }),
})

export const projectByNumber = (root: "organization" | "user", p: ProjectSeed): GhRule => ({
  re: `${root}\\(login:\\$login\\)\\{projectV2\\(number:\\$n\\)`,
  out: gql({ [root]: { projectV2: projectNode(p) } }),
})

export type FieldSeed = { id?: string; name: string; dataType: string; options?: string[] }
export const projectFields = (fields: FieldSeed[]): GhRule => ({
  re: "fields\\(first:50,after:\\$after\\)",
  out: gql({
    node: {
      fields: {
        pageInfo: { hasNextPage: false, endCursor: null },
        nodes: fields.map((f) => ({
          __typename: f.dataType === "SINGLE_SELECT" ? "ProjectV2SingleSelectField" : "ProjectV2Field",
          id: f.id ?? `F_${f.name}`,
          name: f.name,
          dataType: f.dataType,
          options: f.options?.map((o) => ({ id: `OPT_${o}`, name: o, color: "GRAY", description: "" })),
        })),
      },
    },
  }),
})

export const STANDARD_FIELDS: FieldSeed[] = [
  { name: "Title", dataType: "TITLE" },
  { name: "Status", dataType: "SINGLE_SELECT", options: ["Todo", "In Progress", "Done"] },
  { name: "Milestone", dataType: "MILESTONE" },
  { name: "Target", dataType: "DATE" },
]
