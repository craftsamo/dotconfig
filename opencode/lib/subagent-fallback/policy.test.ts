import { describe, expect, test } from "bun:test"
import {
  ROUTES,
  QUOTA_MAX_AGE_MS,
  REASON_CATALOG,
  REASON_SOURCE_ACCOUNT,
  REASON_TARGET_ACCOUNT,
  decideLaunch,
  freshState,
  modelsEqual,
  routeForLaunch,
  type AccountProof,
  type CatalogModel,
  type ModelRef,
  type QuotaProof,
} from "./policy"

const NOW = 1_710_000_000_000
const quota = (state: QuotaProof["state"]): QuotaProof => ({
  state,
  observedAt: NOW,
})
const account = (providerID: string): AccountProof => ({
  providerID,
  connectionID: "fixture",
  methodID: providerID === "anthropic" ? "claude-max" : "chatgpt-browser",
  type: "oauth",
})
const entry = (m: ModelRef): CatalogModel => ({
  ...m,
  enabled: true,
  status: "active",
  capabilities: { tools: true },
  variants: m.variant ? [{ id: m.variant }] : [],
  limit: { context: 200_000, output: 32_000 },
})
const base = (route = ROUTES.worker) => ({
  route,
  source: {
    account: account(route.primary.providerID) as AccountProof | undefined,
    quota: quota("available"),
  },
  target: {
    account: account(route.alternate.providerID) as AccountProof | undefined,
    quota: quota("available"),
  } as { account: AccountProof | undefined; quota: QuotaProof } | undefined,
  catalog: [entry(route.primary), entry(route.alternate)],
  now: NOW,
})

describe("launch preference", () => {
  test("all roles preserve primary and variant, selecting only their pinned alternate", () => {
    expect(Object.keys(ROUTES)).toHaveLength(12)
    for (const [agent, route] of Object.entries(ROUTES)) {
      expect(routeForLaunch({ agent }, route.primary)).toBe(route)
      const input = base(route)
      expect(decideLaunch(input)).toEqual({
        kind: "default",
        model: route.primary,
      })
      input.source.quota = quota("exhausted")
      expect(decideLaunch(input)).toEqual({
        kind: "fallback",
        model: route.alternate,
      })
    }
  })
  test("unknown source leaves the default even if alternate has quota", () => {
    const input = base()
    input.source.quota = quota("unknown")
    expect(decideLaunch(input)).toEqual({
      kind: "default",
      model: input.route.primary,
    })
  })
  test("exhausted source prefers an alternate whose data is unknown or stale", () => {
    for (const quotaProof of [
      quota("unknown"),
      {
        ...quota("available"),
        observedAt: NOW - QUOTA_MAX_AGE_MS - 1,
      },
    ]) {
      const input = base()
      input.source.quota = quota("exhausted")
      input.target = { account: account("openai"), quota: quotaProof }
      expect(decideLaunch(input)).toEqual({
        kind: "fallback",
        model: input.route.alternate,
      })
    }
  })
  test("exhausted source without a usable alternate account keeps the default", () => {
    for (const target of [
      undefined,
      { account: undefined, quota: quota("unknown") },
    ]) {
      const input = base()
      input.source.quota = quota("exhausted")
      input.target = target
      expect(decideLaunch(input)).toEqual({
        kind: "default",
        model: input.route.primary,
      })
    }
  })
  test("an exhausted window stays reliable until its reset, however old", () => {
    const old = NOW - 10 * QUOTA_MAX_AGE_MS
    const input = base()
    input.source.quota = {
      state: "exhausted",
      observedAt: old,
      resetAt: NOW + 1000,
    }
    expect(decideLaunch(input).kind).toBe("fallback")
    input.target!.quota = {
      state: "exhausted",
      observedAt: old,
      resetAt: NOW + 1000,
    }
    expect(decideLaunch(input).kind).toBe("credits")
    // Past its reset, or without a reset time, old data proves nothing.
    for (const resetAt of [NOW, undefined]) {
      input.source.quota = { state: "exhausted", observedAt: old, resetAt }
      expect(decideLaunch(input).kind).toBe("default")
    }
  })
  test("both exhausted tries the usual provider, without any balance inference", () => {
    const input = base()
    input.source.quota = quota("exhausted")
    input.target!.quota = quota("exhausted")
    expect(decideLaunch(input)).toEqual({
      kind: "credits",
      model: input.route.primary,
    })
  })
  test("unapproved native accounts cannot be selected", () => {
    for (const change of [
      undefined,
      { ...account("anthropic"), connectionID: "" },
      { ...account("anthropic"), methodID: "api" },
      account("openai"),
      { ...account("anthropic"), type: "api" },
    ]) {
      const input = base()
      input.source.account = change as any
      expect(decideLaunch(input)).toEqual({
        kind: "stop",
        reason: REASON_SOURCE_ACCOUNT,
      })
    }
    const input = base()
    input.source.quota = quota("exhausted")
    input.target!.account = undefined
    expect(decideLaunch(input)).toEqual({
      kind: "stop",
      reason: REASON_TARGET_ACCOUNT,
    })
  })
  test("catalog status, tools, variants and limits remain required", () => {
    for (const alternate of [false, true])
      for (const change of [
        { enabled: false },
        { status: "deprecated" },
        { capabilities: { tools: false } },
        { variants: [] },
        { limit: { context: 0, output: 1 } },
        { limit: { context: 1, output: 1 } },
        { limit: { context: 200_000, input: -1, output: 1 } },
      ]) {
        const input = base()
        if (alternate) input.source.quota = quota("exhausted")
        input.catalog[alternate ? 1 : 0] = {
          ...input.catalog[alternate ? 1 : 0],
          ...change,
        }
        expect(decideLaunch(input)).toEqual({
          kind: "stop",
          reason: REASON_CATALOG,
        })
      }
  })
  test("explicit models, continuations, unknown roles and changed defaults bypass selection", () => {
    for (const input of [
      { agent: "worker", model: "explicit" },
      { agent: "worker", sessionID: "ses_1" },
      { agent: "unknown" },
      { agent: "__proto__" },
      {},
    ])
      expect(routeForLaunch(input, ROUTES.worker.primary)).toBeUndefined()
    expect(
      routeForLaunch(
        { agent: "worker" },
        { ...ROUTES.worker.primary, variant: "high" },
      ),
    ).toBeUndefined()
    expect(routeForLaunch({ agent: "worker" }, undefined)).toBeUndefined()
    expect(
      modelsEqual(ROUTES.worker.primary, {
        ...ROUTES.worker.primary,
        variant: "high",
      }),
    ).toBe(false)
  })
  test("stale/future/reset data is unknown, but fresh 0% needs no reset proof", () => {
    expect(freshState(quota("exhausted"), NOW)).toBe("exhausted")
    expect(
      freshState(
        { ...quota("available"), observedAt: NOW - QUOTA_MAX_AGE_MS },
        NOW,
      ),
    ).toBe("available")
    for (const q of [
      { ...quota("available"), observedAt: NOW - QUOTA_MAX_AGE_MS - 1 },
      { ...quota("available"), observedAt: NOW + 1 },
      { ...quota("available"), observedAt: NaN },
      { ...quota("exhausted"), resetAt: NOW },
      quota("unknown"),
    ])
      expect(freshState(q, NOW)).toBeUndefined()
  })
})
