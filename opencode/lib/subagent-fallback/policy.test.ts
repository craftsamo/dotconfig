import { describe, expect, test } from "bun:test"
import {
  ROUTES,
  QUOTA_MAX_AGE_MS,
  freshState,
  inputCapacity,
  weigh,
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
  methodID:
    { anthropic: "claude-max", xai: "device" }[providerID] ?? "chatgpt-browser",
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
const base = (model: ModelRef = ROUTES.worker.primary) => ({
  model,
  account: account(model.providerID) as AccountProof | undefined,
  quota: quota("available"),
  catalog: [entry(model)],
  now: NOW,
})

describe("weighing a place", () => {
  test("every route model launches while its quota is not known spent", () => {
    expect(Object.keys(ROUTES)).toHaveLength(12)
    for (const route of Object.values(ROUTES))
      for (const model of [route.primary, route.alternate]) {
        const input = base(model)
        expect(weigh(input)).toBe("launch")
        input.quota = quota("unknown")
        expect(weigh(input)).toBe("launch")
        input.quota = quota("exhausted")
        expect(weigh(input)).toBe("spent")
      }
  })
  test("stale data is no reason to pass a place over", () => {
    const input = base()
    input.quota = {
      ...quota("available"),
      observedAt: NOW - QUOTA_MAX_AGE_MS - 1,
    }
    expect(weigh(input)).toBe("launch")
  })
  test("an exhausted window stays reliable until its reset, however old", () => {
    const old = NOW - 10 * QUOTA_MAX_AGE_MS
    const input = base()
    input.quota = { state: "exhausted", observedAt: old, resetAt: NOW + 1000 }
    expect(weigh(input)).toBe("spent")
    // Past its reset, or without a reset time, old data proves nothing.
    for (const resetAt of [NOW, undefined]) {
      input.quota = { state: "exhausted", observedAt: old, resetAt }
      expect(weigh(input)).toBe("launch")
    }
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
      input.account = change as any
      expect(weigh(input)).toBe("unusable")
    }
  })
  test("catalog status, tools, variants and limits remain required", () => {
    for (const change of [
      { enabled: false },
      { status: "deprecated" },
      { capabilities: { tools: false } },
      { variants: [] },
      { limit: { context: 0, output: 1 } },
      { limit: { context: 1, output: 2 } },
      { limit: { context: 200_000, input: -1, output: 1 } },
    ]) {
      const input = base()
      input.catalog[0] = { ...input.catalog[0], ...change }
      expect(weigh(input)).toBe("unusable")
    }
  })
  test("a shared input/output budget, as xAI publishes, is the whole context; a reserved output is subtracted", () => {
    const shared = { context: 500_000, output: 500_000 }
    expect(inputCapacity(shared)).toBe(500_000)
    expect(inputCapacity({ context: 200_000, output: 32_000 })).toBe(168_000)
    expect(inputCapacity({ ...shared, input: 100_000 })).toBe(100_000)
    expect(inputCapacity({ context: 1, output: 2 })).toBe(0)
    const input = base(ROUTES.searcher.primary)
    input.catalog[0] = { ...input.catalog[0], limit: shared }
    expect(weigh(input)).toBe("launch")
    // Only xAI publishes that shape; elsewhere it is a broken entry.
    for (const model of [ROUTES.worker.primary, ROUTES.verifier.primary]) {
      const other = base(model)
      other.catalog[0] = { ...other.catalog[0], limit: shared }
      expect(weigh(other)).toBe("unusable")
    }
  })
  test("every routed role's global agent file names its route's primary", async () => {
    // ROUTES and the agent files name the same models; a drift between them
    // would go unnoticed at launch.
    for (const [role, route] of Object.entries(ROUTES)) {
      const file = new URL(`../../agents/${role}.md`, import.meta.url)
      const text = await Bun.file(file).text()
      const line = text.match(/^model:\s*(\S+)\s*$/m)?.[1]
      const p = route.primary
      expect(`${role}: ${line}`).toBe(
        `${role}: ${p.providerID}/${p.id}${p.variant ? `#${p.variant}` : ""}`,
      )
    }
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
