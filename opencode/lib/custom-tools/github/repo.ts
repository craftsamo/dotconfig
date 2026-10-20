import { runGh } from "../exec"
import { graphql } from "./gql"
import { parseRepoRef } from "./refs"

/**
 * The repository a tool call is about, with what the viewer may do there.
 * Resolved once per call from an explicit `repo` argument or the working
 * tree's remote, so every tool reports the same facts: who owns it (user or
 * organization), the viewer's permission and whether the viewer owns it.
 * Writes to a repository the viewer does not own are allowed but the tools
 * say so in their result (`foreign: true`).
 */

export type OwnerType = "User" | "Organization"
export type Permission = "ADMIN" | "MAINTAIN" | "WRITE" | "TRIAGE" | "READ" | null

export type RepoContext = {
  id: string
  nameWithOwner: string
  owner: { login: string; id: string; type: OwnerType }
  name: string
  defaultBranch: string | null
  isPrivate: boolean
  viewer: string
  permission: Permission
  /** Whether the viewer is the owner, or a member of the owning organization. */
  foreign: boolean
  canWrite: boolean
}

export type IssueType = { id: string; name: string; isEnabled: boolean }

const REPO_QUERY =
  "query($owner:String!,$name:String!){viewer{login}repository(owner:$owner,name:$name){id nameWithOwner name isPrivate viewerPermission defaultBranchRef{name}owner{__typename login id}}}"

async function currentRepo(cwd?: string): Promise<string> {
  const out = (await runGh(["repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"], cwd)).trim()
  if (!out) throw new Error("Could not resolve the current repository; pass `repo` as owner/repo.")
  return out
}

export async function resolveRepo(repo: string | undefined, cwd?: string): Promise<RepoContext> {
  const nameWithOwner = repo?.trim() ? parseRepoRef(repo) : await currentRepo(cwd)
  const [owner, name] = nameWithOwner.split("/")
  const data = await graphql(REPO_QUERY, { owner, name }, cwd)
  const r = data?.repository
  if (!r) throw new Error(`Repository "${nameWithOwner}" not found or not accessible.`)
  const viewer: string = data.viewer?.login ?? ""
  const type: OwnerType = r.owner?.__typename === "Organization" ? "Organization" : "User"
  const permission: Permission = r.viewerPermission ?? null
  let foreign = type === "User" ? r.owner.login !== viewer : true
  if (type === "Organization") foreign = !(await isOrgMember(r.owner.login, cwd))
  return {
    id: r.id,
    nameWithOwner: r.nameWithOwner,
    owner: { login: r.owner.login, id: r.owner.id, type },
    name: r.name,
    defaultBranch: r.defaultBranchRef?.name ?? null,
    isPrivate: Boolean(r.isPrivate),
    viewer,
    permission,
    foreign,
    canWrite: permission === "ADMIN" || permission === "MAINTAIN" || permission === "WRITE",
  }
}

async function isOrgMember(login: string, cwd?: string): Promise<boolean> {
  try {
    const data = await graphql("query($login:String!){organization(login:$login){viewerIsAMember}}", { login }, cwd)
    return Boolean(data?.organization?.viewerIsAMember)
  } catch {
    return false
  }
}

/** The organization's Issue Types, or null when the owner is a user (Issue Types are organization-only). */
export async function issueTypes(ctx: RepoContext, cwd?: string): Promise<IssueType[] | null> {
  if (ctx.owner.type !== "Organization") return null
  try {
    const data = await graphql(
      "query($login:String!){organization(login:$login){issueTypes(first:25){nodes{id name isEnabled}}}}",
      { login: ctx.owner.login },
      cwd,
    )
    return (data?.organization?.issueTypes?.nodes ?? []).map((t: any) => ({ id: t.id, name: t.name, isEnabled: Boolean(t.isEnabled) }))
  } catch {
    return null
  }
}

/** Writes need write permission; the tools report it rather than let gh fail halfway. */
export function assertWritable(repo: RepoContext): void {
  if (!repo.canWrite) {
    throw new Error(`No write permission on ${repo.nameWithOwner} (viewer permission: ${repo.permission ?? "none"}).`)
  }
}

/** `--repo owner/repo` appended to a gh argv. */
export const withRepo = (argv: string[], repo: string): string[] => [...argv, "--repo", repo]
