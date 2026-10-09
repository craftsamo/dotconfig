import { describe, expect, test } from "bun:test"
import {
  classify,
  DEFAULT_COOLDOWN_MS,
  Episodes,
  Lanes,
  launchLane,
  nextModel,
  OAUTH_PROVIDER,
  retarget,
  type Decision,
} from "./lanes"
import { ROUTES, type CatalogModel, type ModelRef } from "./policy"

const MAIN = "anthropic-credit-main"
const SUB = "anthropic-credit-sub"
const SONNET = ROUTES.worker.primary
const entry = (m: ModelRef, variants: string[]): CatalogModel => ({
  id: m.id,
  providerID: m.providerID,
  enabled: true,
  status: "active",
  capabilities: { tools: true },
  variants: variants.map((id) => ({ id })),
  limit: { context: 400_000, output: 32_000 },
})
const catalog = (providers = [OAUTH_PROVIDER, MAIN, SUB]) =>
  providers.map((p) => entry({ ...SONNET, providerID: p }, ["low", "high"]))
const none: Decision = { retry: false }

describe("classify", () => {
  test("an empty balance is recognised by its text, not by the status alone", () => {
    const credit = {
      type: "provider.invalid-request",
      status: 400,
      message: "Your credit balance is too low to access the Anthropic API.",
    }
    expect(classify(credit, none)).toBe("credit")
    expect(
      classify(
        {
          ...credit,
          message: "x",
          response: { body: "credit balance is too low" },
        },
        none,
      ),
    ).toBe("credit")
    expect(
      classify({ ...credit, message: "bad max_tokens" }, none),
    ).toBeUndefined()
  })
  test("bad keys are auth failures", () => {
    expect(classify({ type: "provider.auth", message: "x" }, none)).toBe("auth")
    expect(classify({ type: "x", status: 401, message: "x" }, none)).toBe(
      "auth",
    )
    expect(classify({ type: "x", status: 403, message: "x" }, none)).toBe(
      "auth",
    )
  })
  test("only a long wait makes a rate limit a window limit", () => {
    const limit = { type: "provider.rate-limit", status: 429, message: "x" }
    expect(classify(limit, { retry: true, delay: 900_000 })).toBe("quota")
    expect(classify(limit, { retry: true, delay: 5_000 })).toBeUndefined()
    expect(classify(limit, none)).toBeUndefined()
    expect(classify({ type: "provider.quota", message: "x" }, none)).toBe(
      "quota",
    )
  })
})

describe("Lanes and Episodes", () => {
  test("a marked lane is blocked until its cooldown ends, then probed again", () => {
    let now = 1000
    const lanes = new Lanes([MAIN, SUB], 60_000, () => now)
    expect(lanes.blocked(MAIN)).toBe(false)
    lanes.mark(MAIN)
    expect(lanes.blocked(MAIN)).toBe(true)
    expect(lanes.blocked(SUB)).toBe(false)
    now += 60_000
    expect(lanes.blocked(MAIN)).toBe(false)
  })
  test("a mark can be shorter than the cooldown but never longer", () => {
    let now = 0
    const lanes = new Lanes([MAIN, SUB], 60_000, () => now)
    lanes.mark(MAIN, 5_000)
    lanes.mark(SUB, 9_999_999)
    now += 5_001
    expect(lanes.blocked(MAIN)).toBe(false)
    expect(lanes.blocked(SUB)).toBe(true)
    now += 55_000
    expect(lanes.blocked(SUB)).toBe(false)
    lanes.mark(MAIN, Number.NaN)
    expect(lanes.blocked(MAIN)).toBe(true)
  })
  test("only configured lanes can be marked", () => {
    const lanes = new Lanes([MAIN], DEFAULT_COOLDOWN_MS, () => 0)
    lanes.mark(OAUTH_PROVIDER)
    expect(lanes.blocked(OAUTH_PROVIDER)).toBe(false)
  })
  test("an episode remembers providers, forgets after its window and stays bounded", () => {
    let now = 0
    const episodes = new Episodes(1000, () => now, 2)
    episodes.record("a", "p1")
    expect([...episodes.record("a", "p2")]).toEqual(["p1", "p2"])
    now += 1001
    expect([...episodes.record("a", "p3")]).toEqual(["p3"])
    episodes.record("b", "p")
    episodes.record("c", "p")
    expect([...episodes.record("a", "q")]).toEqual(["q"])
  })
})

describe("choosing a model", () => {
  test("retarget keeps the variant when the target has it and drops it otherwise", () => {
    expect(retarget(SONNET, MAIN, catalog())).toEqual({
      ...SONNET,
      providerID: MAIN,
    })
    expect(
      retarget({ ...SONNET, variant: "default" }, MAIN, catalog()),
    ).toEqual({
      id: SONNET.id,
      providerID: MAIN,
    })
    expect(retarget(SONNET, "elsewhere", catalog())).toBeUndefined()
  })
  test("subagents prefer lanes and primaries prefer the subscription", () => {
    const lanes = new Lanes([MAIN, SUB], DEFAULT_COOLDOWN_MS, () => 0)
    const base = { current: SONNET, lanes, catalog: catalog() }
    expect(
      nextModel({ ...base, role: "subagent", tried: new Set() })?.providerID,
    ).toBe(MAIN)
    expect(
      nextModel({ ...base, role: "primary", tried: new Set() })?.providerID,
    ).toBe(OAUTH_PROVIDER)
    expect(
      nextModel({ ...base, role: "primary", tried: new Set([OAUTH_PROVIDER]) })
        ?.providerID,
    ).toBe(MAIN)
  })
  test("a session already on a lane keeps the subscription for last", () => {
    const lanes = new Lanes([MAIN, SUB], DEFAULT_COOLDOWN_MS, () => 0)
    const base = {
      lanes,
      role: "primary" as const,
      catalog: catalog(),
    }
    const onMain = { ...SONNET, providerID: MAIN }
    expect(
      nextModel({ ...base, current: onMain, tried: new Set([MAIN]) })
        ?.providerID,
    ).toBe(SUB)
    expect(
      nextModel({ ...base, current: onMain, tried: new Set([MAIN, SUB]) })
        ?.providerID,
    ).toBe(OAUTH_PROVIDER)
  })
  test("tried, blocked and uncatalogued providers are skipped; none left gives undefined", () => {
    const lanes = new Lanes([MAIN, SUB], DEFAULT_COOLDOWN_MS, () => 0)
    lanes.mark(MAIN)
    const base = { current: SONNET, lanes, role: "subagent" as const }
    expect(
      nextModel({ ...base, tried: new Set(), catalog: catalog() })?.providerID,
    ).toBe(SUB)
    expect(
      nextModel({
        ...base,
        tried: new Set([SUB]),
        catalog: catalog([OAUTH_PROVIDER, MAIN, SUB]),
      })?.providerID,
    ).toBe(OAUTH_PROVIDER)
    expect(
      nextModel({
        ...base,
        tried: new Set([SUB, OAUTH_PROVIDER]),
        catalog: catalog(),
      }),
    ).toBeUndefined()
    expect(
      nextModel({
        ...base,
        tried: new Set(),
        catalog: catalog([OAUTH_PROVIDER]),
      })?.providerID,
    ).toBe(OAUTH_PROVIDER)
  })
  test("a launch needs the role's own variant on the lane", () => {
    const lanes = new Lanes([MAIN, SUB], DEFAULT_COOLDOWN_MS, () => 0)
    expect(launchLane(ROUTES.worker, lanes, catalog())).toEqual({
      ...SONNET,
      providerID: MAIN,
    })
    const noLow = [MAIN, SUB].map((p) =>
      entry({ ...SONNET, providerID: p }, ["high"]),
    )
    expect(launchLane(ROUTES.worker, lanes, noLow)).toBeUndefined()
  })
  test("roles whose primary is not the subscription never launch on a lane", () => {
    const lanes = new Lanes([MAIN], DEFAULT_COOLDOWN_MS, () => 0)
    expect(launchLane(ROUTES.verifier, lanes, catalog())).toBeUndefined()
  })
})
