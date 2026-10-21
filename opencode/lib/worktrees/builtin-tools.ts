/**
 * OpenCode 2.0.27 added Code Mode tools that create and remove worktrees.
 * worktree_create asks for no permission at all, and worktree_remove asks
 * under `edit` and can force a removal that discards files, so neither the
 * agents' `git_worktree` denies nor Hermes' rulesets reach them. Worktrees
 * here are made and removed only through `git_worktree` (and the TUI), so
 * both are taken out of the registry for every agent; worktree_list only
 * reads and stays. Missing ids are ignored, so releases without these tools
 * are unaffected.
 */
export const BUILTIN_WORKTREE_WRITES = ["opencode_worktree_create", "opencode_worktree_remove"] as const

export function removeBuiltinWorktreeWrites(editor: { remove(id: string): void }): void {
  for (const id of BUILTIN_WORKTREE_WRITES) editor.remove(id)
}
