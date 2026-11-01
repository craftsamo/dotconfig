import { describe, expect, test } from "bun:test"
import { join } from "node:path"
import {
  judgedDecision,
  nativeDecision,
  OWN_WAIT_ATTEMPTS,
  recordNative,
} from "./native-retry"
import { setupRecorder } from "./retry-recorder"

const limit = () => ({ type: "provider.rate-limit", status: 429, message: "x" })

describe("OpenCode's own retry decision", () => {
  test("the recorder keeps it through a later rewrite and changes nothing", async () => {
    const hooks: Array<(event: any) => Promise<void>> = []
    const dispose = await setupRecorder({
      session: {
        hook: async (_name, callback) => {
          hooks.push(callback)
          return { dispose: async () => void hooks.splice(0) }
        },
      },
    })
    const event: any = {
      sessionID: "ses_x",
      error: limit(),
      decision: { retry: true, delay: 2_000 },
    }
    for (const hook of hooks) await hook(event)
    expect(event.decision).toEqual({ retry: true, delay: 2_000 })
    event.decision = { retry: true, delay: 18_000_000 }
    expect(nativeDecision(event)).toEqual({ retry: true, delay: 2_000 })
    // Another event, even with the same error, has no record of its own.
    const next = { ...event }
    expect(nativeDecision(next)).toBe(next.decision)
    await dispose()
    expect(hooks).toHaveLength(0)
  })
  test("is a copy, not the decision object a later hook may edit", () => {
    const decision = { retry: true as const, delay: 2_000 }
    const event = { error: limit(), decision }
    recordNative(event)
    decision.delay = 18_000_000
    expect(nativeDecision(event)).toEqual({ retry: true, delay: 2_000 })
  })
  test("without a record the current decision stands", () => {
    const event = { error: limit(), decision: { retry: false as const } }
    expect(nativeDecision(event)).toBe(event.decision)
  })
  test("opencode.jsonc lists the recorder right before Quota, and the preflight after it", async () => {
    const config = Bun.JSONC.parse(
      await Bun.file(join(import.meta.dir, "../../opencode.jsonc")).text(),
    ) as { plugins: (string | { package: string })[] }
    const names = config.plugins.map((p) =>
      typeof p === "string" ? p : p.package,
    )
    const quota = names.findIndex((n) =>
      n.startsWith("@slkiser/opencode-quota@"),
    )
    expect(quota).toBeGreaterThan(0)
    expect(names[quota - 1]).toBe("./lib/subagent-fallback/retry-recorder")
    expect(names.at(-1)).toBe("./lib/subagent-fallback")
  })
  test("a limit is judged by OpenCode's own retry in the first attempts only", () => {
    const judged = (own: any, attempt?: number) => {
      const event: any = { error: limit(), decision: own, attempt }
      recordNative(event)
      event.decision = { retry: true, delay: 18_000_000 }
      return judgedDecision(event)
    }
    const short = { retry: true, delay: 2_000 }
    const stretched = { retry: true, delay: 18_000_000 }
    expect(judged(short)).toEqual(short)
    expect(judged(short, OWN_WAIT_ATTEMPTS)).toEqual(short)
    expect(judged(short, OWN_WAIT_ATTEMPTS + 1)).toEqual(stretched)
    expect(judged({ retry: false })).toEqual(stretched)
  })
})
