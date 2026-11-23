import { describe, expect, test } from "bun:test"
import { QUOTA_MAX_AGE_MS } from "./policy"
import type { Dependencies } from "./quota"
import {
  ASK_AGAIN_MS,
  QUOTA_RPC,
  QuotaRefresher,
  REWRITE_POLLS,
  staleFor,
} from "./quota-refresh"

const NOW = 1_710_000_000_000
const part = (ageMs: number, status = "ok") => ({
  status,
  fetchedAt: (NOW - ageMs) / 1000,
  entries: [],
})
const exportOf = (providers: Record<string, unknown>) => ({
  version: 3,
  providers,
})

describe("staleFor", () => {
  test("a missing or old part is stale; a fresh or unavailable one is not", () => {
    const ids = ["anthropic", "openai"]
    expect(staleFor(undefined, ids, NOW)).toBe(true)
    expect(staleFor(exportOf({ anthropic: part(0) }), ids, NOW)).toBe(true)
    expect(
      staleFor(
        exportOf({ anthropic: part(0), openai: part(QUOTA_MAX_AGE_MS + 1) }),
        ids,
        NOW,
      ),
    ).toBe(true)
    expect(
      staleFor(
        exportOf({
          anthropic: part(QUOTA_MAX_AGE_MS),
          openai: { status: "unavailable" },
        }),
        ids,
        NOW,
      ),
    ).toBe(false)
  })
})

describe("QuotaRefresher", () => {
  const stale = exportOf({ anthropic: part(20 * 60_000) })
  const fresh = exportOf({ anthropic: part(0) })
  // Polls and the wait for a check pass at once unless `slow` holds the wait.
  const deps = (reads: unknown[], clock = { now: NOW }, slow = false) => {
    let n = 0
    const d: Dependencies & { count: () => number } = {
      now: () => clock.now,
      readExport: async () =>
        JSON.stringify(reads[Math.min(n++, reads.length - 1)]),
      sleep: (ms) =>
        ms < 1_000 || !slow ? Promise.resolve() : new Promise<void>(() => {}),
      count: () => n,
    }
    return d
  }
  // A check that answers at once.
  const answering = (calls: unknown[] = []) => ({
    rpc: (definition: typeof QUOTA_RPC) => ({
      refresh: async (input: unknown) => {
        calls.push([definition.id, input])
        return {}
      },
    }),
  })
  test("asks Quota for the stale providers and reads until the export is rewritten", async () => {
    const calls: unknown[] = []
    const both = exportOf({ anthropic: part(0), openai: part(0) })
    const d = deps([stale, stale, both], undefined, true)
    const r = new QuotaRefresher()
    expect(
      await r.fresh(answering(calls) as any, d, "/x", stale, [
        "openai",
        "anthropic",
        "anthropic",
      ]),
    ).toEqual(both)
    expect(calls).toEqual([
      [
        "slkiser.opencode-quota",
        { reason: "poll", providerIds: ["anthropic", "openai"] },
      ],
    ])
    expect(d.count()).toBe(3)
  })
  test("gives up on the rewrite after its polls, with the latest export read", async () => {
    const d = deps([stale], undefined, true)
    const r = new QuotaRefresher()
    expect(
      await r.fresh(answering() as any, d, "/x", undefined, ["anthropic"]),
    ).toEqual(stale)
    expect(d.count()).toBe(REWRITE_POLLS + 1)
  })
  test("a check that does not answer in time keeps what it read", async () => {
    const d = deps([fresh])
    const r = new QuotaRefresher()
    const never = { rpc: () => ({ refresh: () => new Promise(() => {}) }) }
    expect(await r.fresh(never as any, d, "/x", stale, ["anthropic"])).toBe(
      stale,
    )
    expect(d.count()).toBe(0)
  })
  test("an aborted launch stops waiting at once", async () => {
    const d = deps([fresh], undefined, true)
    const r = new QuotaRefresher()
    const never = { rpc: () => ({ refresh: () => new Promise(() => {}) }) }
    const controller = new AbortController()
    const pending = r.fresh(
      never as any,
      d,
      "/x",
      stale,
      ["anthropic"],
      controller.signal,
    )
    controller.abort()
    expect(await pending).toBe(stale)
    controller.abort()
    expect(
      await r.fresh(
        answering() as any,
        d,
        "/x",
        stale,
        ["openai"],
        controller.signal,
      ),
    ).toBe(stale)
    expect(d.count()).toBe(0)
  })
  test("launches share a running check, and ask again only after a minute", async () => {
    const calls: unknown[] = []
    let answer!: () => void
    const ctx = {
      rpc: () => ({
        refresh: (input: unknown) => {
          calls.push(input)
          return new Promise<void>((resolve) => (answer = resolve))
        },
      }),
    }
    const clock = { now: NOW }
    const d = deps([stale], clock, true)
    const r = new QuotaRefresher()
    const first = r.fresh(ctx as any, d, "/x", stale, ["anthropic"])
    const second = r.fresh(ctx as any, d, "/x", stale, ["anthropic"])
    answer()
    await Promise.all([first, second])
    expect(calls).toHaveLength(1)
    // The check left the rows stale: no new ask within the minute.
    await r.fresh(ctx as any, d, "/x", stale, ["anthropic"])
    expect(calls).toHaveLength(1)
    clock.now += ASK_AGAIN_MS
    const third = r.fresh(ctx as any, d, "/x", stale, ["anthropic"])
    answer()
    await third
    expect(calls).toHaveLength(2)
  })
  test("keeps what it has without an RPC, on a failure, or when nothing is stale", async () => {
    const d = deps([fresh], undefined, true)
    for (const ctx of [
      {},
      { rpc: () => ({}) },
      {
        rpc: () => {
          throw new Error("no such rpc")
        },
      },
      { rpc: () => ({ refresh: async () => Promise.reject(new Error("x")) }) },
    ])
      expect(
        await new QuotaRefresher().fresh(ctx as any, d, "/x", stale, [
          "anthropic",
        ]),
      ).toBe(stale)
    expect(
      await new QuotaRefresher().fresh(answering() as any, d, "/x", fresh, [
        "anthropic",
      ]),
    ).toBe(fresh)
    expect(d.count()).toBe(0)
  })
})
