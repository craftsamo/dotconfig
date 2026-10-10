import { existsSync, realpathSync } from "fs"
import { createWorktree, mainCheckout, removeWorktree } from "../../worktrees/strategy"
import { tool } from "../define"

const real = (p: string) => (existsSync(p) ? realpathSync(p) : p)

export const worktree = tool({
  description:
    "Create, list or remove task worktrees the way the TUI's new-worktree does (the same strategy), and refresh OpenCode's worktree inventory so they are listed there. create: a new `branch` cut from `from` (default: the freshly fetched remote default branch) at ~/Worktrees/<repository>/<branch with / as ->; an existing local branch is checked out as is. remove: the worktree, refusing uncommitted changes, then its branch only once it has landed on the default branch (an ancestor, or the head of a merged PR from this repository). Creating does not move the session: call session_move (through execute) to work there. OpenCode V2 only.",
  args: {
    action: tool.schema.enum(["create", "list", "remove"]).describe("What to do."),
    branch: tool.schema.string().optional().describe("create: the new (or existing) branch, e.g. feat/short-name."),
    from: tool.schema.string().optional().describe("create: the starting ref for a new branch (default: the remote default branch)."),
    directory: tool.schema.string().optional().describe("remove: the worktree's absolute path."),
  },
  async execute(args, context) {
    const service = context.worktrees
    if (!service) throw new Error("Worktree operations need OpenCode V2.")
    if (args.action === "list") return JSON.stringify({ worktrees: await service.list() }, null, 2)

    if (args.action === "create") {
      const branch = args.branch?.trim()
      if (!branch) throw new Error("create needs `branch`.")
      const created = await createWorktree({ sourceDirectory: await mainCheckout(context.worktree), branch, start: args.from })
      await service.refresh()
      return JSON.stringify(
        {
          ...created,
          ...(created.fetched === false ? { warning: `fetching origin failed: ${created.base} is as of the last fetch` } : {}),
          next: `To work there, move this session with session_move({ directory: "${created.directory}" }) through execute, in its own call.`,
        },
        null,
        2,
      )
    }

    const directory = args.directory?.trim()
    if (!directory) throw new Error("remove needs `directory`.")
    if (real(directory) === real(context.worktree))
      throw new Error("This session works in that worktree; move it elsewhere before removing it.")
    // Uncommitted changes are never discarded here; a person can force it from the TUI or the shell.
    const removed = await removeWorktree({ directory, force: false })
    await service.refresh()
    return JSON.stringify(removed, null, 2)
  },
})
