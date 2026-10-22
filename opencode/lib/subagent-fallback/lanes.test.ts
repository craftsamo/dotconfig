import { describe, expect, test } from "bun:test"
import {
  classify,
  DEFAULT_COOLDOWN_MS,
  Episodes,
  Lanes,
  launchLane,
  loginStop,
  longestSuffix,
  nextModel,
  OAUTH_PROVIDER,
  providerStop,
  retarget,
  stopFor,
  type Decision,
} from "./lanes"
import { ROUTES, type CatalogModel, type ModelRef } from "./policy"

const MAIN = "anthropic-credit-main"
const SUB = "anthropic-credit-sub"
const SONNET = ROUTES.worker.primary
const SONNET_SUB = { ...SONNET, id: `${SONNET.id}-sub` }
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
    expect(retarget(SONNET, providerStop(MAIN), catalog())).toEqual({
      ...SONNET,
      providerID: MAIN,
    })
    expect(
      retarget(
        { ...SONNET, variant: "default" },
        providerStop(MAIN),
        catalog(),
      ),
    ).toEqual({
      id: SONNET.id,
      providerID: MAIN,
    })
    expect(
      retarget(SONNET, providerStop("elsewhere"), catalog()),
    ).toBeUndefined()
  })
  test("retarget moves between a provider and another login's alias models", () => {
    const withLogin = [...catalog(), entry(SONNET_SUB, ["low"])]
    expect(retarget(SONNET, loginStop("sub"), withLogin)).toEqual(SONNET_SUB)
    expect(
      retarget(SONNET_SUB, providerStop(MAIN), withLogin, loginStop("sub")),
    ).toEqual({ ...SONNET, providerID: MAIN })
    expect(
      retarget(
        { ...SONNET, providerID: MAIN },
        providerStop(OAUTH_PROVIDER),
        withLogin,
      ),
    ).toEqual(SONNET)
    expect(retarget(SONNET, loginStop("sub"), catalog())).toBeUndefined()
  })
  test("other saved logins come after the lanes and the active login", () => {
    const lanes = new Lanes([MAIN, SUB], DEFAULT_COOLDOWN_MS, () => 0)
    const withLogin = [...catalog(), entry(SONNET_SUB, ["low"])]
    const base = { lanes, catalog: withLogin, logins: ["sub"] }
    expect(
      nextModel({
        ...base,
        current: SONNET,
        role: "primary",
        tried: new Set([OAUTH_PROVIDER, MAIN, SUB]),
      }),
    ).toEqual(SONNET_SUB)
    expect(
      nextModel({
        ...base,
        current: SONNET,
        role: "primary",
        tried: new Set([OAUTH_PROVIDER]),
      })?.providerID,
    ).toBe(MAIN)
    expect(
      nextModel({
        ...base,
        current: { ...SONNET, providerID: SUB },
        role: "subagent",
        tried: new Set([MAIN, SUB, OAUTH_PROVIDER]),
      }),
    ).toEqual(SONNET_SUB)
    // A session on that login goes to the lanes, then the active login.
    const fromLogin = {
      ...base,
      current: SONNET_SUB,
      role: "primary" as const,
    }
    expect(
      nextModel({ ...fromLogin, tried: new Set([loginStop("sub").key]) }),
    ).toEqual({ ...SONNET, providerID: MAIN })
    expect(
      nextModel({
        ...fromLogin,
        tried: new Set([loginStop("sub").key, MAIN, SUB]),
      }),
    ).toEqual(SONNET)
    expect(
      nextModel({
        ...fromLogin,
        tried: new Set([loginStop("sub").key, MAIN, SUB, OAUTH_PROVIDER]),
      }),
    ).toBeUndefined()
  })
  test("a model runs on the login of its longest suffix", () => {
    const suffixes = ["sub", "fast-sub"]
    expect(longestSuffix("claude-opus-5-5-fast-sub", suffixes)).toBe(
      "fast-sub",
    )
    expect(longestSuffix("claude-opus-5-5-sub", suffixes)).toBe("sub")
    expect(longestSuffix("-sub", suffixes)).toBeUndefined()
    expect(stopFor(SONNET_SUB, suffixes)).toEqual(loginStop("sub"))
    expect(stopFor(SONNET, suffixes)).toEqual(providerStop(OAUTH_PROVIDER))
    expect(stopFor({ ...SONNET_SUB, providerID: MAIN }, suffixes)).toEqual(
      providerStop(MAIN),
    )
  })
  test("a move never lands on a model another login's suffix claims", () => {
    const lanes = new Lanes([], DEFAULT_COOLDOWN_MS, () => 0)
    const FAST = { ...SONNET, id: `${SONNET.id}-fast` }
    const FAST_SUB = { ...SONNET, id: `${SONNET.id}-fast-sub` }
    const SUB_ONLY = { ...SONNET, id: `${SONNET.id}-sub` }
    const models = [FAST, FAST_SUB, SUB_ONLY].map((m) => entry(m, ["low"]))
    // Only `sub` is usable; `fast-sub` is configured but has no label.
    const base = {
      lanes,
      role: "primary" as const,
      catalog: models,
      logins: ["sub"],
      suffixes: ["sub", "fast-sub"],
    }
    expect(
      nextModel({ ...base, current: FAST, tried: new Set([OAUTH_PROVIDER]) }),
    ).toBeUndefined()
    // An active-login candidate a suffix claims is no active-login stop.
    expect(
      nextModel({
        ...base,
        current: { ...SUB_ONLY, providerID: MAIN },
        catalog: [entry(SUB_ONLY, ["low"])],
        logins: [],
        suffixes: ["sub"],
        tried: new Set([MAIN]),
      }),
    ).toBeUndefined()
    expect(
      nextModel({
        ...base,
        current: { ...SUB_ONLY, providerID: MAIN },
        catalog: [entry(SUB_ONLY, ["low"])],
        logins: [],
        suffixes: [],
        tried: new Set([MAIN]),
      }),
    ).toEqual(SUB_ONLY)
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
  test("a launch needs the model's own variant on the lane", () => {
    const lanes = new Lanes([MAIN, SUB], DEFAULT_COOLDOWN_MS, () => 0)
    expect(launchLane(ROUTES.worker.primary, lanes, catalog())).toEqual({
      ...SONNET,
      providerID: MAIN,
    })
    const noLow = [MAIN, SUB].map((p) =>
      entry({ ...SONNET, providerID: p }, ["high"]),
    )
    expect(launchLane(ROUTES.worker.primary, lanes, noLow)).toBeUndefined()
  })
  test("a model that is not on the subscription never launches on a lane, its Claude alternate can", () => {
    const lanes = new Lanes([MAIN], DEFAULT_COOLDOWN_MS, () => 0)
    expect(launchLane(ROUTES.verifier.primary, lanes, catalog())).toBeUndefined()
    expect(launchLane(ROUTES.searcher.primary, lanes, catalog())).toBeUndefined()
    expect(launchLane(ROUTES.searcher.alternate, lanes, catalog())).toBeUndefined()
    expect(
      launchLane(ROUTES["explore-high"].alternate, lanes, catalog()),
    ).toEqual({
      ...ROUTES["explore-high"].alternate,
      providerID: MAIN,
    })
  })
})
