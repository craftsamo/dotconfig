import { describe, expect, test } from "bun:test"
import { mkdtempSync, readFileSync, rmSync } from "node:fs"
import { join } from "node:path"
import { setupAntigravityGuard } from "./index"

type GuardContext = Parameters<typeof setupAntigravityGuard>[0]
type Hook = GuardContext["session"]["hook"]
type RequestCallback = Parameters<Hook>[1]
type RequestEvent = Parameters<RequestCallback>[0]
type RetryArgs = Hook extends {
  (...args: infer First): unknown
  (...args: infer Last): unknown
} ? First : never
type RetryCallback = RetryArgs[1]
type RetryEvent = Parameters<RetryCallback>[0]

function fixture() {
  const requests: RequestCallback[] = []
  const retries: RetryCallback[] = []
  const hooks: {
    kind: Parameters<Hook>[0] | RetryArgs[0]
    options: Parameters<Hook>[2]
    disposed: boolean
  }[] = []
  const ctx: GuardContext = {
    session: {
      async hook(kind, callback, options) {
        if (kind === "retry") retries.push(callback as RetryCallback)
        else requests.push(callback as RequestCallback)
        const hook = { kind, options, disposed: false }
        hooks.push(hook)
        return {
          async dispose() {
            hook.disposed = true
          },
        }
      },
    },
  }
  return { ctx, hooks, requests, retries }
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
      { kind: "retry", options: { providerID: "google" } },
    ])
    await cleanup()
    expect(f.hooks.every((hook) => hook.disposed)).toBe(true)
  })

  test("rewrites Antigravity system text but not other Google models", async () => {
    const f = fixture()
    const cleanup = await setupAntigravityGuard(f.ctx)
    const event = request()
    await f.requests[0](event)
    expect(event.system[0].text).toBe('Use tools["opencode"].session_move')
    const other = request("gemini-3-pro")
    await f.requests[0](other)
    expect(other.system[0].text).toBe("Use tools.opencode.session_move")
    await cleanup()
  })

  test.each([
    ["antigravity-gemini-4-hydrogen-low", 403, { retry: false }],
    ["antigravity-gemini-4-hydrogen-low", 500, { retry: true, delay: 1000 }],
    ["gemini-3-pro", 403, { retry: true, delay: 1000 }],
  ] as const)("retry for %s with %s", async (id, status, expected) => {
    const f = fixture()
    const cleanup = await setupAntigravityGuard(f.ctx)
    const event: RetryEvent = {
      sessionID: "session",
      agent: "build",
      model: { providerID: "google", id },
      error: { type: "provider.unknown", message: "Error", status },
      attempt: 1,
      decision: { retry: true, delay: 1000 },
    }
    await f.retries[0](event)
    expect(event.decision).toEqual(expected)
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
      await f.requests[0](event)
      await f.requests[0](event)
      await f.requests[0](request("gemini-3-pro"))
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
      await f.retries[0]({
        sessionID: "session",
        agent: "build",
        model: event.model,
        error: { type: "provider.unknown", message: "Forbidden", status: 403 },
        attempt: 1,
        decision: { retry: true, delay: 1000 },
      })
      const retryLines = readFileSync(path, "utf8").trim().split("\n")
      expect(retryLines).toHaveLength(3)
      expect(JSON.parse(retryLines[2])).toEqual({
        at: expect.any(String),
        kind: "retry",
        model: "google/antigravity-gemini-4-hydrogen-low",
        refusal: "refused",
        status: 403,
      })
      expect(retryLines[2]).not.toContain("Forbidden")
    } finally {
      if (previous === undefined) delete process.env.ANTIGRAVITY_GUARD_LOG
      else process.env.ANTIGRAVITY_GUARD_LOG = previous
      await cleanup()
      rmSync(dir, { recursive: true, force: true })
    }
  })
})
