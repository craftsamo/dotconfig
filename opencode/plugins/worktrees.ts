import { strategy } from "../lib/worktrees/strategy"

/**
 * Registers the dotconfig worktree strategy (lib/worktrees/strategy.ts) with
 * OpenCode V2, so the TUI's new worktree, the server API and the
 * `git_worktree` tool all create task branches under ~/Worktrees the way the
 * Hermes workspace does. Adding a strategy makes it the default; worktrees
 * recorded under another strategy keep their owner. V1 has no worktree
 * strategies, so there is no `server()` entry.
 */
export default {
  id: "dotconfig.worktrees",
  async setup(ctx: { worktree: { transform(cb: (editor: { add(definition: unknown): void }) => void): Promise<unknown> } }) {
    await ctx.worktree.transform((editor) => editor.add(strategy()))
  },
}
