import { describe, expect, test } from "bun:test"
import plugin from "../plugins/builtin-worktree-tools"
import { BUILTIN_WORKTREE_WRITES, removeBuiltinWorktreeWrites } from "./builtin-worktree-tools"

/** OpenCode registers a namespaced tool under `<namespace>_<name>`. */
const registry = () =>
  new Map(
    ["opencode_worktree_create", "opencode_worktree_list", "opencode_worktree_remove", "opencode_session_move", "git_worktree_add", "git_worktree_remove"].map(
      (id) => [id, { id }],
    ),
  )

describe("built-in worktree writes", () => {
  test("create and remove leave the registry; list, session moving and git-tools stay", () => {
    const tools = registry()
    removeBuiltinWorktreeWrites({ remove: (id) => tools.delete(id) })
    expect([...tools.keys()].sort()).toEqual(["git_worktree_add", "git_worktree_remove", "opencode_session_move", "opencode_worktree_list"])
  })

  test("a release without them is left as it is", () => {
    const tools = new Map([["git_worktree_add", {}]])
    removeBuiltinWorktreeWrites({ remove: (id) => tools.delete(id) })
    expect([...tools.keys()]).toEqual(["git_worktree_add"])
  })

  test("the V2-only plugin takes the writes out without a worktree strategy context", async () => {
    const tools = registry()
    await plugin.setup({
      tool: { transform: async (cb) => cb({ remove: (id) => tools.delete(id) }) },
    })
    expect("server" in plugin).toBe(false)
    for (const id of BUILTIN_WORKTREE_WRITES) expect(tools.has(id)).toBe(false)
    expect(tools.has("opencode_worktree_list")).toBe(true)
    expect(tools.has("opencode_session_move")).toBe(true)
  })
})
