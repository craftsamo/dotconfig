import { describe, expect, test } from "bun:test"
import { mkdtempSync, readFileSync, rmSync } from "node:fs"
import { join } from "node:path"
import { setupAntigravityGuard } from "./index"

type GuardContext = Parameters<typeof setupAntigravityGuard>[0]
type Hook = GuardContext["session"]["hook"]
type RequestEvent = Parameters<Parameters<Hook>[1]>[0]

function fixture() {
  const hooks: {
    kind: Parameters<Hook>[0]
    callback: Parameters<Hook>[1]
    options: Parameters<Hook>[2]
    disposed: boolean
  }[] = []
  const ctx: GuardContext = {
    session: {
      async hook(kind, callback, options) {
        const hook = { kind, callback, options, disposed: false }
        hooks.push(hook)
        return {
          async dispose() {
            hook.disposed = true
          },
        }
      },
    },
  }
  return { ctx, hooks }
}

function request(id = "antigravity-gemini-4-hydrogen-low"): RequestEvent {
  return {
    sessionID: "session",
    model: { providerID: "google", id },
    system: [{ type: "text", text: "Use tools.opencode.session_move" }],
  }
}

describe("Antigravity guard", () => {
  test("registers all request kinds for Google and disposes them", async () => {
    const f = fixture()
    const cleanup = await setupAntigravityGuard(f.ctx)
    expect(f.hooks.map(({ kind, options }) => ({ kind, options }))).toEqual([
      { kind: "context", options: { providerID: "google" } },
      { kind: "compaction", options: { providerID: "google" } },
      { kind: "generate", options: { providerID: "google" } },
      { kind: "title", options: { providerID: "google" } },
    ])
    await cleanup()
    expect(f.hooks.every((hook) => hook.disposed)).toBe(true)
  })

  test("rewrites Antigravity system text but not other Google models", async () => {
    const f = fixture()
    const cleanup = await setupAntigravityGuard(f.ctx)
    const event = request()
    await f.hooks[0].callback(event)
    expect(event.system[0].text).toBe('Use tools["opencode"].session_move')
    const other = request("gemini-3-pro")
    await f.hooks[0].callback(other)
    expect(other.system[0].text).toBe("Use tools.opencode.session_move")
    await cleanup()
  })

  test("logs counts without prompt text when enabled", async () => {
    const dir = mkdtempSync(join(import.meta.dir, ".guard-log-"))
    const previous = process.env.ANTIGRAVITY_GUARD_LOG
    const f = fixture()
    const cleanup = await setupAntigravityGuard(f.ctx)
    try {
      const path = join(dir, "requests.jsonl")
      process.env.ANTIGRAVITY_GUARD_LOG = path
      const event = request()
      await f.hooks[0].callback(event)
      await f.hooks[0].callback(event)
      await f.hooks[0].callback(request("gemini-3-pro"))
      const lines = readFileSync(path, "utf8").trim().split("\n")
      expect(lines).toHaveLength(2)
      for (const [index, line] of lines.entries()) {
        const entry = JSON.parse(line)
        expect(entry).toEqual({
          at: expect.any(String),
          kind: "context",
          model: "google/antigravity-gemini-4-hydrogen-low",
          replaced: index === 0 ? 1 : 0,
        })
        expect(new Date(entry.at).toISOString()).toBe(entry.at)
        expect(line).not.toContain("session_move")
      }
    } finally {
      if (previous === undefined) delete process.env.ANTIGRAVITY_GUARD_LOG
      else process.env.ANTIGRAVITY_GUARD_LOG = previous
      await cleanup()
      rmSync(dir, { recursive: true, force: true })
    }
  })
})
