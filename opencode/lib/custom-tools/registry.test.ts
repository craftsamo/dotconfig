import { describe as suite, expect, test } from "bun:test"
import { load, skip } from "./testing/deps"

const describe = suite.skipIf(skip)
const { default: plugin } = await load(() => import("../../plugins/custom-tools"))

describe("registry", () => {
  test("registers only the remaining custom tool ids in V1", async () => {
    const ids = Object.keys((await plugin.server()).tool).sort()
    expect(ids).toEqual(["web_ui_check", "x_search"])
    expect(ids.some((id) => id.startsWith("git_"))).toBe(false)
  })

  test("registers only the remaining custom tool ids in V2", async () => {
    const ids: string[] = []
    await plugin.setup({
      location: { directory: "/unused" },
      session: { get: async () => ({}) },
      integration: { connection: { active: async () => undefined, resolve: async () => undefined } },
      tool: {
        transform: async (callback) => {
          callback({ add: (tool) => ids.push(tool.name as string) })
        },
      },
    })
    expect(ids.sort()).toEqual(["web_ui_check", "x_search"])
    expect(ids.some((id) => id.startsWith("git_"))).toBe(false)
  })
})
