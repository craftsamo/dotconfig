import { runGhJson } from "../exec"
import { applyFields, getFields, resolveProject, type Project, type Route } from "./project"
import type { RepoContext } from "./repo"

/** Adding an existing issue or PR (by URL) to a board and setting its fields; shared by gh_issue_create and gh_project_item_add. */

export type BoardResult = {
  project: { id: string; number: number; title: string; url: string; owner: string; route: Route }
  itemId: string
  fieldsApplied: string[]
}

export async function addUrlToProject(project: Project, route: Route, url: string, fields: Record<string, string> | undefined, cwd?: string): Promise<BoardResult> {
  const added = await runGhJson(["project", "item-add", String(project.number), "--owner", project.owner.login, "--url", url, "--format", "json"], cwd)
  const itemId: string = added?.id
  if (!itemId) throw new Error(`gh project item-add returned no item id for ${url}.`)
  const fieldsApplied = fields && Object.keys(fields).length ? await applyFields(project.id, itemId, await getFields(project.id, cwd), fields, cwd) : []
  return { project: { id: project.id, number: project.number, title: project.title, url: project.url, owner: project.owner.login, route }, itemId, fieldsApplied }
}

export async function addIssueToBoard(
  repo: RepoContext,
  url: string,
  input: { project?: string; owner?: string; fields?: Record<string, string> },
  cwd?: string,
): Promise<BoardResult> {
  const { project, route } = await resolveProject({ project: input.project, owner: input.owner, repo, cwd })
  if (!project.viewerCanUpdate) throw new Error(`Project ${project.owner.login}/${project.number} "${project.title}" is read-only for the viewer.`)
  return addUrlToProject(project, route, url, input.fields, cwd)
}
