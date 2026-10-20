import { tool } from "../define"
import { runGh, runGhJson } from "../exec"
import { addIssueToBoard, applyKind, assertWritable, getIssue, parseIssueRef, resolveRepo, sameName, withRepo } from "../github"
import { relateIssue } from "./relate"

/**
 * Writes to issues. Guards, since custom tools bypass the shell permission
 * gates: a write needs write permission on the repository (reported, not
 * guessed), a repository the viewer does not own is flagged `foreign` in the
 * result, closing needs a reason, and nothing here deletes.
 */

/** A milestone by title; created when absent and `create` is set. */
export async function ensureMilestone(repo: string, title: string, create: boolean, cwd?: string): Promise<{ number: number; title: string; created: boolean }> {
  const list: any[] = (await runGhJson(["api", "--paginate", "--slurp", `repos/${repo}/milestones?state=all&per_page=100`], cwd))?.flat() ?? []
  const found = list.find((m) => sameName(m.title, title))
  if (found) return { number: found.number, title: found.title, created: false }
  if (!create) throw new Error(`Milestone "${title}" not found in ${repo}. Pass createMilestone:true to create it.`)
  const made = await runGhJson(["api", `repos/${repo}/milestones`, "-f", `title=${title}`], cwd)
  return { number: made.number, title: made.title, created: true }
}

export const numberFromIssueUrl = (out: string): number => {
  const m = out.match(/\/issues\/(\d+)\s*$/m)
  if (!m) throw new Error(`gh did not print the issue URL:\n${out}`)
  return parseInt(m[1], 10)
}

export const create = tool({
  description:
    "Create an issue and settle its place in one call: title and body, kind (an Issue Type on an organization repository, else a type:<kind> label created on first use), labels, assignees, milestone (by title; created when createMilestone is set), a parent issue, blocked-by dependencies, and optionally a project board item with field values (project resolved explicit → linked → org → user). Needs write permission; a repository the viewer does not own is reported as foreign. Returns the issue number and URL with what was applied.",
  args: {
    title: tool.schema.string(),
    body: tool.schema.string().optional().describe("Markdown body."),
    repo: tool.schema.string().optional().describe("owner/repo. Defaults to the current repository."),
    kind: tool.schema.string().optional().describe("feature, bug, task, chore, ... Lands as an Issue Type when the organization defines it, else as a type:<kind> label."),
    labels: tool.schema.array(tool.schema.string()).optional(),
    assignees: tool.schema.array(tool.schema.string()).optional().describe('Logins; "@me" for the viewer.'),
    milestone: tool.schema.string().optional().describe("Milestone title."),
    createMilestone: tool.schema.boolean().optional().describe("Create the milestone when it does not exist (default false)."),
    parent: tool.schema.string().optional().describe("Parent issue: number, #N, owner/repo#N or URL."),
    blockedBy: tool.schema.array(tool.schema.string()).optional().describe("Issues this one is blocked by."),
    addToProject: tool.schema.boolean().optional().describe("Also add the issue to a project board (default false)."),
    project: tool.schema.string().optional().describe("Project to add to: URL, owner/N, number or title. Omit to resolve linked → org → user."),
    owner: tool.schema.string().optional().describe('Project owner login or "@me" when `project` is a number or title.'),
    fields: tool.schema.record(tool.schema.string(), tool.schema.string()).optional().describe('Board field values to set after adding, e.g. {"Status":"Todo"}.'),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const repo = await resolveRepo(args.repo, cwd)
    assertWritable(repo)
    const argv = withRepo(["issue", "create", "--title", args.title, "--body", args.body ?? ""], repo.nameWithOwner)
    for (const l of args.labels ?? []) argv.push("--label", l)
    for (const a of args.assignees ?? []) argv.push("--assignee", a)
    let milestone: { number: number; title: string; created: boolean } | null = null
    if (args.milestone) {
      milestone = await ensureMilestone(repo.nameWithOwner, args.milestone, Boolean(args.createMilestone), cwd)
      argv.push("--milestone", milestone.title)
    }
    const out = await runGh(argv, cwd)
    const number = numberFromIssueUrl(out)
    const url = `https://github.com/${repo.nameWithOwner}/issues/${number}`

    // The issue exists from here on: a later step that fails is reported
    // beside it, so the caller fixes that step instead of creating a twin.
    const errors: Record<string, string> = {}
    const step = async <T>(name: string, run: () => Promise<T>): Promise<T | null> => {
      try {
        return await run()
      } catch (error) {
        errors[name] = (error as Error).message
        return null
      }
    }
    const kind = args.kind ? await step("kind", () => applyKind(repo, number, args.kind!, cwd)) : null
    const relations =
      args.parent || args.blockedBy?.length
        ? await step("relations", () => relateIssue(repo, number, { parent: args.parent, addBlockedBy: args.blockedBy }, cwd))
        : null
    const board = args.addToProject ? await step("board", () => addIssueToBoard(repo, url, { project: args.project, owner: args.owner, fields: args.fields }, cwd)) : null

    return JSON.stringify(
      { ok: Object.keys(errors).length === 0, repo: repo.nameWithOwner, foreign: repo.foreign, issue: { number, url, title: args.title }, kind, milestone, relations, board, errors },
      null,
      2,
    )
  },
})

export const update = tool({
  description:
    'Change an issue: title, body (replace, or append a dated section), kind, labels and assignees added / removed, milestone (title; "" clears), and state — close with a required reason (completed, not planned, duplicate) and an optional closing comment, or reopen. Needs write permission; a repository the viewer does not own is reported as foreign. Never deletes.',
  args: {
    issue: tool.schema.string().describe("Issue number, #N, owner/repo#N or URL."),
    repo: tool.schema.string().optional(),
    title: tool.schema.string().optional(),
    body: tool.schema.string().optional().describe("New body (replaces)."),
    appendBody: tool.schema.string().optional().describe("Markdown appended to the body as a new section."),
    kind: tool.schema.string().optional(),
    addLabels: tool.schema.array(tool.schema.string()).optional(),
    removeLabels: tool.schema.array(tool.schema.string()).optional(),
    addAssignees: tool.schema.array(tool.schema.string()).optional(),
    removeAssignees: tool.schema.array(tool.schema.string()).optional(),
    milestone: tool.schema.string().optional().describe('Milestone title; "" clears.'),
    createMilestone: tool.schema.boolean().optional(),
    state: tool.schema.enum(["open", "closed"]).optional(),
    reason: tool.schema.enum(["completed", "not planned", "duplicate"]).optional().describe("Required when closing."),
    comment: tool.schema.string().optional().describe("Comment posted before a state change."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const ref = parseIssueRef(args.issue)
    const repo = await resolveRepo(ref.repo ?? args.repo, cwd)
    assertWritable(repo)
    const n = String(ref.number)
    const r = repo.nameWithOwner
    const changed: string[] = []
    if (args.state === "closed" && !args.reason) throw new Error("Closing needs `reason`: completed, not planned or duplicate.")
    if (args.body !== undefined && args.appendBody !== undefined) throw new Error("Pass body or appendBody, not both.")

    const edit = withRepo(["issue", "edit", n], r)
    const untouched = edit.length
    if (args.title !== undefined) edit.push("--title", args.title), changed.push("title")
    if (args.body !== undefined) edit.push("--body", args.body), changed.push("body")
    if (args.appendBody !== undefined) {
      const current = (await getIssue(r, ref.number, { comments: 0, cwd })).body
      edit.push("--body", `${current.trimEnd()}\n\n${args.appendBody.trim()}\n`)
      changed.push("body (appended)")
    }
    for (const l of args.addLabels ?? []) edit.push("--add-label", l)
    for (const l of args.removeLabels ?? []) edit.push("--remove-label", l)
    for (const a of args.addAssignees ?? []) edit.push("--add-assignee", a)
    for (const a of args.removeAssignees ?? []) edit.push("--remove-assignee", a)
    if (args.addLabels?.length || args.removeLabels?.length) changed.push("labels")
    if (args.addAssignees?.length || args.removeAssignees?.length) changed.push("assignees")
    let milestone: { number: number; title: string; created: boolean } | null = null
    if (args.milestone !== undefined) {
      if (args.milestone === "") edit.push("--remove-milestone")
      else {
        milestone = await ensureMilestone(r, args.milestone, Boolean(args.createMilestone), cwd)
        edit.push("--milestone", milestone.title)
      }
      changed.push("milestone")
    }
    if (edit.length > untouched) await runGh(edit, cwd)

    const kind = args.kind ? await applyKind(repo, ref.number, args.kind, cwd) : null
    if (kind) changed.push("kind")

    if (args.comment) {
      await runGh(withRepo(["issue", "comment", n, "--body", args.comment], r), cwd)
      changed.push("comment")
    }
    if (args.state === "closed") {
      await runGh(withRepo(["issue", "close", n, "--reason", args.reason!], r), cwd)
      changed.push(`closed (${args.reason})`)
    } else if (args.state === "open") {
      await runGh(withRepo(["issue", "reopen", n], r), cwd)
      changed.push("reopened")
    }
    return JSON.stringify({ ok: true, repo: r, foreign: repo.foreign, issue: ref.number, changed, kind, milestone })
  },
})

export const comment = tool({
  description: "Post a comment on an issue (a progress note, a decision, a hand-off). Needs write permission; a repository the viewer does not own is reported as foreign.",
  args: {
    issue: tool.schema.string().describe("Issue number, #N, owner/repo#N or URL."),
    body: tool.schema.string().describe("Markdown."),
    repo: tool.schema.string().optional(),
  },
  async execute(args, context) {
    const ref = parseIssueRef(args.issue)
    const repo = await resolveRepo(ref.repo ?? args.repo, context.worktree)
    assertWritable(repo)
    const out = await runGh(withRepo(["issue", "comment", String(ref.number), "--body", args.body], repo.nameWithOwner), context.worktree)
    return JSON.stringify({ ok: true, repo: repo.nameWithOwner, foreign: repo.foreign, issue: ref.number, url: out.trim() || null })
  },
})
