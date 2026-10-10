import { tool } from "../define"
import { tryGit } from "../exec"

const branchOf = async (directory: string) => {
  const res = await tryGit(["symbolic-ref", "--quiet", "--short", "HEAD"], directory)
  return res.ok ? res.stdout.trim() : null
}

export const worktree = tool({
  description:
    "Create, list or remove task worktrees through OpenCode's worktree service — the same path the TUI's new-worktree uses — so they are recorded in OpenCode's inventory. create: a new branch (`branch`, or `name` as the branch) cut from the freshly fetched remote default branch, at ~/Worktrees/<repository>/<branch with / as ->; an existing local branch is checked out as is. remove: the worktree, then its branch only once merged into the default branch (or its PR merged). Creating does not move the session: call session_move (through execute) to work there. OpenCode V2 only.",
  args: {
    action: tool.schema.enum(["create", "list", "remove"]).describe("What to do."),
    branch: tool.schema.string().optional().describe("create: the branch, e.g. feat/short-name."),
    name: tool.schema.string().optional().describe("create: a name without slashes, used as the branch when `branch` is omitted."),
    directory: tool.schema.string().optional().describe("remove: the worktree's absolute path."),
    force: tool.schema.boolean().optional().describe("remove: discard uncommitted changes in it (default false)."),
  },
  async execute(args, context) {
    const service = context.worktrees
    if (!service) throw new Error("Worktree operations need OpenCode V2.")
    if (args.action === "list") return JSON.stringify({ worktrees: await service.list() }, null, 2)

    if (args.action === "create") {
      const branch = args.branch?.trim() || args.name?.trim()
      if (!branch) throw new Error("create needs `branch` (or `name`).")
      if (args.name?.includes("/")) throw new Error("`name` cannot contain '/'; pass it as `branch` instead.")
      const { directory } = await service.create({ name: branch.replaceAll("/", "-"), branch })
      return JSON.stringify(
        {
          directory,
          branch: await branchOf(directory),
          next: `To work there, move this session with session_move({ directory: "${directory}" }) through execute, in its own call.`,
        },
        null,
        2,
      )
    }

    const directory = args.directory?.trim()
    if (!directory) throw new Error("remove needs `directory`.")
    if (directory === context.worktree) throw new Error("This session works in that worktree; move it elsewhere before removing it.")
    const branch = await branchOf(directory)
    await service.remove({ directory, force: args.force ?? false })
    const kept = branch ? (await tryGit(["show-ref", "--verify", "--quiet", `refs/heads/${branch}`], context.worktree)).ok : false
    return JSON.stringify(
      {
        removed: directory,
        branch,
        branchDeleted: Boolean(branch) && !kept,
        ...(kept ? { note: `${branch} is kept: it has not landed on the default branch.` } : {}),
      },
      null,
      2,
    )
  },
})
