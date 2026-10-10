import { strategy } from "../lib/worktrees/strategy"

/**
 * Registers the dotconfig worktree strategy (lib/worktrees/strategy.ts) with
 * OpenCode V2, so the TUI's new worktree, the server API and the
 * `git_worktree` tool all create task branches under ~/Worktrees the way the
 * Hermes workspace does. Adding a strategy makes it the default; worktrees
 * recorded under another strategy keep their owner. V1 has no worktree
 * strategies, so there is no `server()` entry.
 */

// OpenCode offers a forced removal only for its own Worktree.OperationError
// with forceRequired; newer @opencode/plugin releases export it. Without it
// the refusal still reaches the person, just without the force prompt.
async function operationError(): Promise<(new (input: { message: string; forceRequired?: boolean }) => Error) | undefined> {
  try {
    const plugin: any = await import("@opencode/plugin")
    return plugin?.Worktree?.OperationError
  } catch {
    return undefined
  }
}

export default {
  id: "dotconfig.worktrees",
  async setup(ctx: { worktree: { transform(cb: (editor: { add(definition: unknown): void }) => void): Promise<unknown> } }) {
    const base = strategy()
    const OperationError = await operationError()
    await ctx.worktree.transform((editor) =>
      editor.add({
        ...base,
        async remove(input: { directory: string; force: boolean }) {
          try {
            await base.remove(input)
          } catch (error: any) {
            if (OperationError && error?.forceRequired) throw new OperationError({ message: error.message, forceRequired: true })
            throw error
          }
        },
      }),
    )
  },
}
