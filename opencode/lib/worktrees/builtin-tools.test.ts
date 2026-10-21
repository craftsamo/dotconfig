import { describe, expect, test } from "bun:test"
import plugin from "../../plugins/worktrees"
import { BUILTIN_WORKTREE_WRITES, removeBuiltinWorktreeWrites } from "./builtin-tools"

// OpenCode registers a namespaced tool under `<namespace>_<name>`.
const registry = () =>
  new Map(
    ["opencode_worktree_create", "opencode_worktree_list", "opencode_worktree_remove", "opencode_session_move", "git_worktree"].map(
      (id) => [id, { id }],
    ),
  )

describe("built-in worktree writes", () => {
  test("create and remove leave the registry; list and the dotconfig tool stay", () => {
    const tools = registry()
    removeBuiltinWorktreeWrites({ remove: (id) => tools.delete(id) })
    expect([...tools.keys()].sort()).toEqual(["git_worktree", "opencode_session_move", "opencode_worktree_list"])
  })

  test("a release without them is left as it is", () => {
    const tools = new Map([["git_worktree", {}]])
    removeBuiltinWorktreeWrites({ remove: (id) => tools.delete(id) })
    expect([...tools.keys()]).toEqual(["git_worktree"])
  })

  test("the plugin registers the strategy and takes the writes out", async () => {
    const tools = registry()
    const strategies: unknown[] = []
    await plugin.setup({
      worktree: { transform: async (cb) => cb({ add: (definition) => strategies.push(definition) }) },
      tool: { transform: async (cb) => cb({ remove: (id) => tools.delete(id) }) },
    })
    expect(strategies).toHaveLength(1)
    for (const id of BUILTIN_WORKTREE_WRITES) expect(tools.has(id)).toBe(false)
    expect(tools.has("opencode_worktree_list")).toBe(true)
  })
})
