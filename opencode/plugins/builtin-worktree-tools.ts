import { removeBuiltinWorktreeWrites } from "../lib/builtin-worktree-tools"

/** Takes OpenCode V2's built-in worktree writers out of every agent's catalog. */
export default {
  id: "dotconfig.builtin-worktree-tools",
  async setup(ctx: {
    tool: { transform(cb: (editor: Parameters<typeof removeBuiltinWorktreeWrites>[0]) => void): Promise<unknown> }
  }) {
    await ctx.tool.transform(removeBuiltinWorktreeWrites)
  },
}
