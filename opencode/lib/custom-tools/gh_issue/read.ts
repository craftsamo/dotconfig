import { tool } from "../define"
import { getIssue, issueTypes, parseIssueRef, resolveRepo, sameName, searchIssues, LABEL_PREFIX } from "../github"

export const view = tool({
  description:
    "Read one issue in full, in one call: body, state and reason, kind (Issue Type or type:* label), labels, assignees, milestone, parent and sub-issues with progress, blocked-by / blocking dependencies, linked development branches, PRs that close it, the project boards it sits on (with the item ids gh_project_item_set takes) and the latest comments. Read-only. The issue may be a number (current repo), #N, owner/repo#N or a URL.",
  args: {
    issue: tool.schema.string().describe("Issue number, #N, owner/repo#N or URL."),
    repo: tool.schema.string().optional().describe("owner/repo when the issue is given as a bare number. Defaults to the current repository."),
    comments: tool.schema.number().optional().describe("How many of the latest comments to include (default 5, 0 for none)."),
  },
  async execute(args, context) {
    const ref = parseIssueRef(args.issue)
    const repo = await resolveRepo(ref.repo ?? args.repo, context.worktree)
    const issue = await getIssue(repo.nameWithOwner, ref.number, { comments: args.comments ?? 5, cwd: context.worktree })
    return JSON.stringify({ repo: repo.nameWithOwner, foreign: repo.foreign, issue }, null, 2)
  },
})

export const list = tool({
  description:
    'List issues of a repository with filters, read-only: state, kind (matched against the organization\'s Issue Types, else the type:* label), milestone, label, assignee, parent (the sub-issues of that issue) and free GitHub search qualifiers in `query` (e.g. "no:milestone -label:wontfix sort:updated-desc"). Paginates up to `limit` (default 50). Returns number, title, state, kind, labels, assignees, milestone, parent number and sub-issue progress per issue.',
  args: {
    repo: tool.schema.string().optional().describe("owner/repo. Defaults to the current repository."),
    state: tool.schema.enum(["open", "closed", "all"]).optional().describe("Default open."),
    kind: tool.schema.string().optional().describe("Kind to match: an Issue Type name on an organization repository, else the type:<kind> label."),
    milestone: tool.schema.string().optional().describe('Milestone title, or "none" for issues without one.'),
    label: tool.schema.string().optional().describe("A label every result must carry."),
    assignee: tool.schema.string().optional().describe('Login, "@me", or "none".'),
    parent: tool.schema.string().optional().describe("Parent issue (number, #N, owner/repo#N or URL): list its sub-issues instead of searching."),
    query: tool.schema.string().optional().describe("Extra GitHub search qualifiers and words."),
    limit: tool.schema.number().optional().describe("Max results (default 50)."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const repo = await resolveRepo(args.repo, cwd)
    const limit = args.limit ?? 50
    if (args.parent) {
      const ref = parseIssueRef(args.parent, repo.nameWithOwner)
      const parent = await getIssue(ref.repo ?? repo.nameWithOwner, ref.number, { comments: 0, cwd })
      const state = args.state ?? "open"
      const subs = parent.subIssues.filter((s) => state === "all" || s.state.toLowerCase() === state).slice(0, limit)
      return JSON.stringify({ repo: repo.nameWithOwner, parent: { number: parent.number, title: parent.title, url: parent.url }, count: subs.length, issues: subs }, null, 2)
    }
    const parts = [`repo:${repo.nameWithOwner}`]
    const state = args.state ?? "open"
    if (state !== "all") parts.push(`state:${state}`)
    if (args.kind) {
      const types = await issueTypes(repo, cwd)
      const type = types?.find((t) => sameName(t.name, args.kind))
      parts.push(type ? `type:"${type.name}"` : `label:"${LABEL_PREFIX}${args.kind.toLowerCase()}"`)
    }
    if (args.milestone) parts.push(args.milestone === "none" ? "no:milestone" : `milestone:"${args.milestone}"`)
    if (args.label) parts.push(`label:"${args.label}"`)
    if (args.assignee) parts.push(args.assignee === "none" ? "no:assignee" : `assignee:${args.assignee}`)
    if (args.query?.trim()) parts.push(args.query.trim())
    const query = parts.join(" ")
    const issues = await searchIssues(query, { limit, cwd })
    return JSON.stringify({ repo: repo.nameWithOwner, query, count: issues.length, issues }, null, 2)
  },
})
