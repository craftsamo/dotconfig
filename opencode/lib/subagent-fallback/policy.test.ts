import { describe, expect, test } from "bun:test"
import {
  ROUTES,
  REASON_CATALOG,
  REASON_SOURCE_ACCOUNT,
  REASON_SOURCE_BILLING,
  REASON_TARGET_ACCOUNT,
  REASON_TARGET_BILLING,
  REASON_CREDITS_UNAVAILABLE,
  REASON_CREDIT_QUOTA_UNKNOWN,
  REASON_TARGET_MISSING,
  REASON_TARGET_QUOTA,
  decideLaunch,
  modelsEqual,
  routeForLaunch,
  type AccountProof,
  type BillingProof,
  type CatalogModel,
  type ModelRef,
  type QuotaProof,
} from "./policy"

const NOW = 1_000_000

const fmt = (m: ModelRef) =>
  `${m.providerID}/${m.id}${m.variant ? "#" + m.variant : ""}`

const expected: Array<[string, string, string]> = [
  [
    "explore-max",
    "anthropic/claude-opus-5-5#xhigh",
    "openai/gpt-6.1-sol#xhigh",
  ],
  [
    "explore-high",
    "anthropic/claude-sonnet-5-5#high",
    "openai/gpt-6.1-sol#high",
  ],
  [
    "explore-medium",
    "anthropic/claude-sonnet-5-5#medium",
    "openai/gpt-6.1-sol#medium",
  ],
  [
    "reviewer",
    "anthropic/claude-sonnet-5-5#medium",
    "openai/gpt-6.1-sol#medium",
  ],
  ["worker", "anthropic/claude-sonnet-5-5#low", "openai/gpt-6.1-sol#low"],
  ["explore-spark", "anthropic/claude-haiku-4-5", "openai/gpt-6-luna#low"],
  ["explore-small", "openai/gpt-6-luna#low", "anthropic/claude-sonnet-5-5#low"],
  ["verifier", "openai/gpt-6-luna#low", "anthropic/claude-sonnet-5-5#low"],
  ["debugger", "openai/gpt-6.1-sol#high", "anthropic/claude-opus-5-5#high"],
  [
    "reviewer-deep",
    "openai/gpt-6.1-sol#high",
    "anthropic/claude-opus-5-5#high",
  ],
  [
    "searcher-deep",
    "openai/gpt-6.1-sol#medium",
    "anthropic/claude-sonnet-5-5#medium",
  ],
  ["searcher", "openai/gpt-6.1-sol#low", "anthropic/claude-sonnet-5-5#low"],
]

const acct = (
  providerID: string,
  methodID: string,
  over: Partial<AccountProof> = {},
): AccountProof => ({
  connectionID: "connection-a",
  providerID,
  methodID,
  type: "oauth",
  ...over,
})
const okAccount = (providerID: string) =>
  acct(
    providerID,
    providerID === "anthropic" ? "claude-max" : "chatgpt-browser",
  )

const avail = (over: Partial<QuotaProof> = {}): QuotaProof => ({
  state: "available",
  observedAt: NOW - 1000,
  ...over,
})
const exhausted = (over: Partial<QuotaProof> = {}): QuotaProof => ({
  state: "exhausted",
  observedAt: NOW - 1000,
  resetAt: NOW + 60_000,
  ...over,
})

const bill = (over: Partial<BillingProof> = {}): BillingProof => ({
  state: "subscription_only",
  observedAt: NOW - 1000,
  ...over,
})

const entry = (m: ModelRef): CatalogModel => ({
  id: m.id,
  providerID: m.providerID,
  enabled: true,
  status: "active",
  capabilities: { tools: true },
  variants: m.variant ? [{ id: m.variant }] : [],
  limit: { context: 200_000, input: 150_000, output: 32_000 },
})

const route = ROUTES["worker"]
const catalogAll = [entry(route.primary), entry(route.alternate)]

const base = () => ({
  route,
  source: {
    account: okAccount("anthropic") as AccountProof | undefined,
    quota: avail(),
    billing: bill() as BillingProof,
  },
  target: {
    account: okAccount("openai") as AccountProof | undefined,
    quota: avail(),
    billing: bill() as BillingProof,
  } as
    | {
        account: AccountProof | undefined
        quota: QuotaProof
        billing: BillingProof
      }
    | undefined,
  catalog: catalogAll,
  now: NOW,
})

describe("ROUTES", () => {
  test.each(expected)("%s route", (agent, primary, alternate) => {
    expect(Object.keys(ROUTES).length).toBe(12)
    expect(fmt(ROUTES[agent].primary)).toBe(primary)
    expect(fmt(ROUTES[agent].alternate)).toBe(alternate)
  })

  test("explore-spark primary omits variant", () => {
    expect("variant" in ROUTES["explore-spark"].primary).toBe(false)
  })
})

describe("modelsEqual", () => {
  test("compares variant exactly including undefined", () => {
    const a = { id: "x", providerID: "p" }
    expect(modelsEqual(a, { id: "x", providerID: "p" })).toBe(true)
    expect(modelsEqual(a, { id: "x", providerID: "p", variant: "low" })).toBe(
      false,
    )
    expect(
      modelsEqual({ ...a, variant: "low" }, { ...a, variant: "high" }),
    ).toBe(false)
    expect(modelsEqual(a, { id: "y", providerID: "p" })).toBe(false)
    expect(modelsEqual(a, { id: "x", providerID: "q" })).toBe(false)
  })
})

describe("routeForLaunch", () => {
  test.each(expected)(
    "%s resolves when configured matches primary",
    (agent) => {
      expect(routeForLaunch({ agent }, ROUTES[agent].primary)).toBe(
        ROUTES[agent],
      )
    },
  )

  test.each([
    ["unknown role", { agent: "nope" }],
    ["missing agent", {}],
    ["non-string agent", { agent: 5 }],
    ["prototype role", { agent: "toString" }],
    ["__proto__ role", { agent: "__proto__" }],
    ["constructor role", { agent: "constructor" }],
    [
      "manual model object",
      { agent: "worker", model: { id: "a", providerID: "b" } },
    ],
    ["manual empty model", { agent: "worker", model: "" }],
    ["manual null model", { agent: "worker", model: null }],
    ["sessionID continuation", { agent: "worker", sessionID: "ses_1" }],
    ["empty sessionID", { agent: "worker", sessionID: "" }],
    ["null sessionID", { agent: "worker", sessionID: null }],
  ])("undefined for %s", (_, input) => {
    expect(routeForLaunch(input, ROUTES["worker"].primary)).toBeUndefined()
  })

  test("undefined when parent default / configured missing", () => {
    expect(routeForLaunch({ agent: "worker" }, undefined)).toBeUndefined()
  })

  test.each([
    ["different id", { id: "other", providerID: "anthropic", variant: "low" }],
    [
      "different provider",
      { id: "claude-sonnet-5-5", providerID: "openai", variant: "low" },
    ],
    [
      "different variant",
      { id: "claude-sonnet-5-5", providerID: "anthropic", variant: "high" },
    ],
    ["missing variant", { id: "claude-sonnet-5-5", providerID: "anthropic" }],
  ])("undefined for changed configured model: %s", (_, configured) => {
    expect(routeForLaunch({ agent: "worker" }, configured)).toBeUndefined()
  })
})

describe("decideLaunch routes", () => {
  test.each(expected)(
    "%s defaults to exact primary and falls back to exact alternate",
    (agent) => {
      const r = ROUTES[agent]
      const catalog = [entry(r.primary), entry(r.alternate)]
      const pa = okAccount(r.primary.providerID)
      const aa = okAccount(r.alternate.providerID)
      expect(
        decideLaunch({
          route: r,
          source: { account: pa, quota: avail(), billing: bill() },
          target: undefined,
          catalog,
          now: NOW,
        }),
      ).toEqual({ kind: "default", model: r.primary })
      expect(
        decideLaunch({
          route: r,
          source: { account: pa, quota: exhausted(), billing: bill() },
          target: { account: aa, quota: avail(), billing: bill() },
          catalog,
          now: NOW,
        }),
      ).toEqual({ kind: "fallback", model: r.alternate })
    },
  )
})

describe("decideLaunch accounts", () => {
  test.each([
    ["missing account", undefined],
    ["wrong provider", acct("openai", "claude-max")],
    ["wrong method", acct("anthropic", "chatgpt-browser")],
    [
      "empty connectionID",
      acct("anthropic", "claude-max", { connectionID: "" }),
    ],
    ["non-oauth", acct("anthropic", "claude-max", { type: "api" as "oauth" })],
  ])("source %s stops", (_, account) => {
    const input = base()
    input.source.account = account
    expect(decideLaunch(input)).toEqual({
      kind: "stop",
      reason: REASON_SOURCE_ACCOUNT,
    })
  })

  test("openai headless method is approved", () => {
    const r = ROUTES["searcher"]
    expect(
      decideLaunch({
        route: r,
        source: {
          account: acct("openai", "chatgpt-headless"),
          quota: avail(),
          billing: bill(),
        },
        target: undefined,
        catalog: [entry(r.primary)],
        now: NOW,
      }).kind,
    ).toBe("default")
  })

  test.each([
    ["missing account", undefined],
    ["wrong provider", acct("anthropic", "chatgpt-browser")],
    ["wrong method", acct("openai", "api-key")],
    [
      "empty connectionID",
      acct("openai", "chatgpt-browser", { connectionID: "" }),
    ],
  ])("target %s stops", (_, account) => {
    const input = base()
    input.source.quota = exhausted()
    input.target = { account, quota: avail(), billing: bill() }
    expect(decideLaunch(input)).toEqual({
      kind: "stop",
      reason: REASON_TARGET_ACCOUNT,
    })
  })

  test("reasons never embed connection IDs", () => {
    const input = base()
    input.source.account = acct("anthropic", "bad", {
      connectionID: "connection-secretless",
    })
    const d = decideLaunch(input)
    expect(JSON.stringify(d)).not.toContain("connection-secretless")
  })
})

describe("decideLaunch quota", () => {
  test.each([
    ["unknown state", avail({ state: "unknown" })],
    ["stale", avail({ observedAt: NOW - 30_001 })],
    ["future", avail({ observedAt: NOW + 1 })],
    ["NaN observedAt", avail({ observedAt: Number.NaN })],
    ["exhausted without reset", exhausted({ resetAt: undefined })],
    ["exhausted reset in past", exhausted({ resetAt: NOW - 1 })],
    ["exhausted reset now", exhausted({ resetAt: NOW })],
    [
      "exhausted reset infinite",
      exhausted({ resetAt: Number.POSITIVE_INFINITY }),
    ],
  ])("source %s with no usable target defaults", (_, quota) => {
    const input = base()
    input.source.quota = quota
    input.target = undefined
    expect(decideLaunch(input)).toEqual({
      kind: "default",
      model: route.primary,
    })
  })

  test("source quota unknown with target available falls back", () => {
    const input = base()
    input.source.quota = avail({ state: "unknown" })
    expect(decideLaunch(input)).toEqual({
      kind: "fallback",
      model: route.alternate,
    })
  })

  test("source unknown with unknown target quota defaults", () => {
    const input = base()
    input.source.quota = avail({ state: "unknown" })
    input.target!.quota = avail({ state: "unknown" })
    expect(decideLaunch(input).kind).toBe("default")
  })

  test("source unknown with target billing invalid defaults", () => {
    const input = base()
    input.source.quota = avail({ state: "unknown" })
    input.target!.billing = bill({ state: "paid_risk" })
    expect(decideLaunch(input).kind).toBe("default")
  })

  test("source quota missing proof fields defaults", () => {
    const input = base()
    input.source.quota = { state: "unknown", observedAt: Number.NaN }
    input.target = undefined
    expect(decideLaunch(input).kind).toBe("default")
  })

  test("source expired exhausted with unusable target defaults", () => {
    const input = base()
    input.source.quota = exhausted({ resetAt: NOW - 1 })
    input.target = undefined
    expect(decideLaunch(input)).toEqual({
      kind: "default",
      model: route.primary,
    })
  })

  test("source quota unknown still requires valid catalog", () => {
    const input = base()
    input.source.quota = avail({ state: "unknown" })
    input.target = undefined
    input.catalog = [entry(route.alternate)]
    expect(decideLaunch(input)).toEqual({
      kind: "stop",
      reason: REASON_CATALOG,
    })
  })

  test("freshness boundaries are inclusive", () => {
    for (const observedAt of [NOW, NOW - 30_000]) {
      const input = base()
      input.source.quota = avail({ observedAt })
      expect(decideLaunch(input).kind).toBe("default")
    }
  })

  test("source available does not require target", () => {
    const input = base()
    input.target = undefined
    expect(decideLaunch(input)).toEqual({
      kind: "default",
      model: route.primary,
    })
  })

  test("source exhausted without target stops", () => {
    const input = base()
    input.source.quota = exhausted()
    input.target = undefined
    expect(decideLaunch(input)).toEqual({
      kind: "stop",
      reason: REASON_TARGET_MISSING,
    })
  })

  test.each([
    ["unknown", avail({ state: "unknown" })],
    ["stale", avail({ observedAt: NOW - 30_001 })],
    ["future", avail({ observedAt: NOW + 5 })],
    ["exhausted past reset", exhausted({ resetAt: NOW - 1 })],
  ])("target %s stops", (_, quota) => {
    const input = base()
    input.source.quota = exhausted()
    input.target = { account: okAccount("openai"), quota, billing: bill() }
    expect(decideLaunch(input)).toEqual({
      kind: "stop",
      reason: REASON_TARGET_QUOTA,
    })
  })

  test("both pools exhausted without credits stops", () => {
    const input = base()
    input.source.quota = exhausted()
    input.target = {
      account: okAccount("openai"),
      quota: exhausted(),
      billing: bill(),
    }
    expect(decideLaunch(input)).toEqual({
      kind: "stop",
      reason: REASON_CREDITS_UNAVAILABLE,
    })
  })
})

describe("decideLaunch credits", () => {
  const both = (sourceBilling: BillingProof, targetBilling: BillingProof) => {
    const input = base()
    input.source.quota = exhausted()
    input.source.billing = sourceBilling
    input.target = {
      account: okAccount("openai"),
      quota: exhausted(),
      billing: targetBilling,
    }
    return input
  }
  const credits = () => bill({ state: "credits_available" })

  test("source available with credits uses default", () => {
    const input = base()
    input.source.billing = credits()
    expect(decideLaunch(input)).toEqual({
      kind: "default",
      model: route.primary,
    })
  })

  test("primary available beats alternate credits", () => {
    const input = base()
    input.target!.billing = credits()
    expect(decideLaunch(input).kind).toBe("default")
  })

  test("alternate available with credits falls back when source unknown", () => {
    const input = base()
    input.source.quota = avail({ state: "unknown" })
    input.source.billing = credits()
    input.target!.billing = credits()
    expect(decideLaunch(input)).toEqual({
      kind: "fallback",
      model: route.alternate,
    })
  })

  test("both exhausted with source credits uses primary credits", () => {
    expect(decideLaunch(both(credits(), bill()))).toEqual({
      kind: "credits",
      model: route.primary,
    })
  })

  test("both exhausted with target credits uses alternate credits", () => {
    expect(decideLaunch(both(bill(), credits()))).toEqual({
      kind: "credits",
      model: route.alternate,
    })
  })

  test("both credits prefers source", () => {
    expect(decideLaunch(both(credits(), credits()))).toEqual({
      kind: "credits",
      model: route.primary,
    })
  })

  test("unknown target billing still allows source credits", () => {
    expect(decideLaunch(both(credits(), bill({ state: "unknown" })))).toEqual({
      kind: "credits",
      model: route.primary,
    })
  })

  test("target paid_risk or unknown billing is not credits", () => {
    for (const state of ["paid_risk", "unknown"] as const) {
      expect(decideLaunch(both(bill(), bill({ state })))).toEqual({
        kind: "stop",
        reason: REASON_CREDITS_UNAVAILABLE,
      })
    }
  })

  test("no credits when both exhausted stops", () => {
    expect(decideLaunch(both(bill(), bill()))).toEqual({
      kind: "stop",
      reason: REASON_CREDITS_UNAVAILABLE,
    })
  })

  test("source unknown quota with source credits stops", () => {
    const input = base()
    input.source.quota = avail({ state: "unknown" })
    input.source.billing = credits()
    input.target = undefined
    expect(decideLaunch(input)).toEqual({
      kind: "stop",
      reason: REASON_CREDIT_QUOTA_UNKNOWN,
    })
  })

  test("unknown or stale quota on either side blocks credits", () => {
    for (const q of [
      avail({ state: "unknown" }),
      avail({ observedAt: NOW - 30_001 }),
      exhausted({ resetAt: NOW - 1 }),
    ]) {
      const a = both(credits(), credits())
      a.target!.quota = q
      expect(decideLaunch(a).kind).toBe("stop")
      const b = both(credits(), credits())
      b.source.quota = q
      b.target!.quota = exhausted()
      expect(decideLaunch(b).kind).not.toBe("credits")
    }
  })

  test("credits with invalid catalog stops", () => {
    const input = both(credits(), bill())
    input.catalog = [entry(route.alternate)]
    expect(decideLaunch(input)).toEqual({
      kind: "stop",
      reason: REASON_CATALOG,
    })
  })

  test("credits_available is accepted as fresh billing; paid_risk is not", () => {
    const input = base()
    input.source.billing = bill({ state: "paid_risk" })
    expect(decideLaunch(input)).toEqual({
      kind: "stop",
      reason: REASON_SOURCE_BILLING,
    })
  })
})

describe("decideLaunch billing", () => {
  const bad: Array<[string, BillingProof | undefined]> = [
    ["unknown", bill({ state: "unknown" })],
    ["paid_risk", bill({ state: "paid_risk" })],
    ["missing", undefined],
    ["NaN observedAt", bill({ observedAt: Number.NaN })],
    ["future", bill({ observedAt: NOW + 1 })],
    ["stale", bill({ observedAt: NOW - 30_001 })],
  ]

  test.each(bad)("source billing %s stops before catalog", (_, billing) => {
    const input = base()
    input.source.billing = billing as BillingProof
    input.catalog = []
    expect(decideLaunch(input)).toEqual({
      kind: "stop",
      reason: REASON_SOURCE_BILLING,
    })
  })

  test.each(bad)("target billing %s stops before catalog", (_, billing) => {
    const input = base()
    input.source.quota = exhausted()
    input.target!.billing = billing as BillingProof
    input.catalog = []
    expect(decideLaunch(input)).toEqual({
      kind: "stop",
      reason: REASON_TARGET_BILLING,
    })
  })

  test("billing freshness boundaries are inclusive", () => {
    for (const observedAt of [NOW, NOW - 30_000]) {
      const input = base()
      input.source.billing = bill({ observedAt })
      expect(decideLaunch(input).kind).toBe("default")
      input.source.quota = exhausted()
      input.target!.billing = bill({ observedAt })
      expect(decideLaunch(input).kind).toBe("fallback")
    }
  })

  test("source paid_risk with quota available stops", () => {
    const input = base()
    input.source.billing = bill({ state: "paid_risk" })
    expect(decideLaunch(input)).toEqual({
      kind: "stop",
      reason: REASON_SOURCE_BILLING,
    })
  })

  test("source exhausted but target paid_risk stops", () => {
    const input = base()
    input.source.quota = exhausted()
    input.target!.billing = bill({ state: "paid_risk" })
    expect(decideLaunch(input)).toEqual({
      kind: "stop",
      reason: REASON_TARGET_BILLING,
    })
  })

  test("valid source billing with unknown quota defaults", () => {
    const input = base()
    input.source.quota = avail({ state: "unknown" })
    input.target = undefined
    expect(decideLaunch(input).kind).toBe("default")
  })
})

describe("decideLaunch catalog", () => {
  const variants: Array<
    [string, (c: CatalogModel) => CatalogModel | undefined]
  > = [
    ["missing", () => undefined],
    ["disabled", (c) => ({ ...c, enabled: false })],
    ["deprecated", (c) => ({ ...c, status: "deprecated" })],
    ["tools false", (c) => ({ ...c, capabilities: { tools: false } })],
    ["unsupported variant", (c) => ({ ...c, variants: [{ id: "other" }] })],
    ["zero context", (c) => ({ ...c, limit: { ...c.limit, context: 0 } })],
    [
      "NaN output",
      (c) => ({ ...c, limit: { ...c.limit, output: Number.NaN } }),
    ],
    ["negative input", (c) => ({ ...c, limit: { ...c.limit, input: -1 } })],
    [
      "context not above output",
      (c) => ({ ...c, limit: { ...c.limit, context: 32_000 } }),
    ],
    ["wrong provider", (c) => ({ ...c, providerID: "other" })],
    ["wrong id", (c) => ({ ...c, id: "other" })],
  ]

  test.each(variants)("primary %s stops", (_, mutate) => {
    const input = base()
    const changed = mutate(entry(route.primary))
    input.catalog = changed
      ? [changed, entry(route.alternate)]
      : [entry(route.alternate)]
    expect(decideLaunch(input)).toEqual({
      kind: "stop",
      reason: REASON_CATALOG,
    })
  })

  test.each(variants)("alternate %s stops", (_, mutate) => {
    const input = base()
    input.source.quota = exhausted()
    const changed = mutate(entry(route.alternate))
    input.catalog = changed
      ? [entry(route.primary), changed]
      : [entry(route.primary)]
    expect(decideLaunch(input)).toEqual({
      kind: "stop",
      reason: REASON_CATALOG,
    })
  })

  test("input limit may be omitted", () => {
    const input = base()
    const c = entry(route.primary)
    delete c.limit.input
    input.catalog = [c]
    expect(decideLaunch(input).kind).toBe("default")
  })

  test("variant-less primary needs no variant in catalog", () => {
    const r = ROUTES["explore-spark"]
    expect(
      decideLaunch({
        route: r,
        source: {
          account: okAccount("anthropic"),
          quota: avail(),
          billing: bill(),
        },
        target: undefined,
        catalog: [entry(r.primary)],
        now: NOW,
      }).kind,
    ).toBe("default")
  })
})
