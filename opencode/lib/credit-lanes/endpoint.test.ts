import { describe, expect, test } from "bun:test"
import { CACHE_MS, createHandler, listen, serve } from "./endpoint"
import { summarize, type Lane, type Summary } from "./core"
import { toQuotaV1 } from "./quota"

const LANE: Lane = {
  provider: "anthropic-credit-main",
  label: "Main",
  amount: 200,
  renewalDay: 13,
  since: "2026-10-09",
}
const NOW = new Date(2026, 9, 10, 12)
const summary = (cost: number, now = NOW): Summary =>
  summarize(
    LANE,
    [{ model: { providerID: LANE.provider, id: "m" }, cost }],
    now,
  )

describe("toQuotaV1", () => {
  test("emits only what Quota accepts", () => {
    const body = toQuotaV1(summary(50), NOW)
    expect(body.version).toBe("quota-v1")
    const allowed = [
      "kind",
      "name",
      "resultType",
      "percentRemaining",
      "value",
      "label",
      "right",
      "resetTimeIso",
      "observedAtIso",
    ]
    for (const entry of body.entries) {
      for (const key of Object.keys(entry)) expect(allowed).toContain(key)
      expect(entry.name.length).toBeLessThanOrEqual(80)
    }
    const [percent, value] = body.entries as any[]
    expect(percent).toMatchObject({
      kind: "percent",
      resultType: "budget",
      percentRemaining: 75,
    })
    expect(percent.right).toBe("$150.00/$200.00")
    expect(percent.resetTimeIso).toBe(new Date(2026, 9, 13).toISOString())
    expect(value.kind).toBe("value")
    expect(value.value.length).toBeLessThanOrEqual(160)
    expect(value.percentRemaining).toBeUndefined()
  })
  test("never exceeds 100%, and the reset follows the cycle after a renewal", () => {
    expect(
      (toQuotaV1(summary(-5), NOW).entries[0] as any).percentRemaining,
    ).toBe(100)
    const later = new Date(2026, 9, 14)
    const next = toQuotaV1(summary(50, later), later)
    expect((next.entries[0] as any).resetTimeIso).toBe(
      new Date(2026, 10, 13).toISOString(),
    )
  })
})

describe("handler", () => {
  const make = (extra: Record<string, unknown> = {}) => {
    let runs = 0
    let clock = NOW.getTime()
    const handler = createHandler({
      collect: async () => {
        runs++
        return [summary(50)]
      },
      now: () => new Date(clock),
      ...extra,
    })
    return { handler, runs: () => runs, tick: (ms: number) => (clock += ms) }
  }
  test("serves a lane by path and rejects the rest", async () => {
    const { handler } = make()
    expect(
      (await handler("GET", "/anthropic-credit-main", undefined)).status,
    ).toBe(200)
    expect((await handler("GET", "/nope", undefined)).status).toBe(404)
    expect(
      (await handler("POST", "/anthropic-credit-main", undefined)).status,
    ).toBe(405)
  })
  test("shares one collection between concurrent requests and caches it", async () => {
    const { handler, runs, tick } = make()
    await Promise.all(
      [1, 2, 3].map(() => handler("GET", "/anthropic-credit-main", undefined)),
    )
    expect(runs()).toBe(1)
    tick(CACHE_MS - 1)
    await handler("GET", "/anthropic-credit-main", undefined)
    expect(runs()).toBe(1)
    tick(2)
    await handler("GET", "/anthropic-credit-main", undefined)
    expect(runs()).toBe(2)
  })
  test("a failed collection is a 503 and is retried on the next request", async () => {
    let fail = true
    const handler = createHandler({
      collect: async () => {
        if (fail) throw new Error("stats down")
        return [summary(50)]
      },
    })
    expect(
      (await handler("GET", "/anthropic-credit-main", undefined)).status,
    ).toBe(503)
    fail = false
    expect(
      (await handler("GET", "/anthropic-credit-main", undefined)).status,
    ).toBe(200)
  })
  test("checks the lane's own bearer token when it has one", async () => {
    const { handler } = make({
      tokenFor: (provider: string) =>
        provider === "anthropic-credit-main" ? "t" : undefined,
    })
    expect(
      (await handler("GET", "/anthropic-credit-main", undefined)).status,
    ).toBe(401)
    expect(
      (await handler("GET", "/anthropic-credit-main", "Bearer x")).status,
    ).toBe(401)
    expect(
      (await handler("GET", "/anthropic-credit-main", "Bearer t")).status,
    ).toBe(200)
  })
  test("a lane without a token is open, and an unknown lane is still 404", async () => {
    const { handler } = make({ tokenFor: () => undefined })
    expect(
      (await handler("GET", "/anthropic-credit-main", undefined)).status,
    ).toBe(200)
    expect((await handler("GET", "/nope", "Bearer t")).status).toBe(404)
  })
})

describe("listen", () => {
  test("serves JSON on loopback and shuts down", async () => {
    const handler = createHandler({ collect: async () => [summary(50)] })
    const server = await listen(handler, 0)
    expect(server).toBeDefined()
    const res = await fetch(
      `http://127.0.0.1:${server!.port}/anthropic-credit-main`,
    )
    expect(res.status).toBe(200)
    expect(res.headers.get("content-type")).toBe("application/json")
    expect(((await res.json()) as any).version).toBe("quota-v1")
    await server!.close()
  })
  test("a taken port is not an error", async () => {
    const handler = createHandler({ collect: async () => [] })
    const first = await listen(handler, 0)
    const second = await listen(handler, first!.port)
    expect(second).toBeUndefined()
    await first!.close()
  })
})

describe("serve", () => {
  const handler = createHandler({ collect: async () => [summary(50)] })
  const up = async (port: number) =>
    (
      await fetch(`http://127.0.0.1:${port}/anthropic-credit-main`).catch(
        () => undefined,
      )
    )?.status
  const until = async (check: () => Promise<boolean>) => {
    for (let i = 0; i < 100; i++) {
      if (await check()) return true
      await new Promise((r) => setTimeout(r, 20))
    }
    return false
  }
  test("takes over the port when its owner goes away", async () => {
    const probe = await listen(handler, 0)
    const port = probe!.port
    await probe!.close()
    const a = serve(handler, port, 30)
    expect(await until(async () => (await up(port)) === 200)).toBe(true)
    const b = serve(handler, port, 30)
    await a.dispose()
    expect(await until(async () => (await up(port)) === 200)).toBe(true)
    await b.dispose()
    expect(await until(async () => (await up(port)) === undefined)).toBe(true)
  })
})
