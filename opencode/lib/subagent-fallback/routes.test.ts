import { describe, expect, test } from "bun:test"
import { modelsEqual, ROUTES } from "./policy"
import {
  defaultSteps,
  modelAt,
  parsePlaces,
  parseStep,
  readRoutes,
  stepsForLaunch,
  stopOf,
  type Names,
} from "./routes"

const TEAM = "anthropic-credit-team"
const MAIN_LANE = "anthropic-credit-main"
const NAMES: Names = {
  lanes: [TEAM, MAIN_LANE],
  logins: ["main", "sub"],
  // A suffix with no label, and one that ends in another.
  suffixes: ["main", "sub", "spare", "fast-sub"],
}
const HAIKU = {
  providerID: "anthropic",
  id: "claude-haiku-5-5",
  variant: "low",
}

describe("route steps", () => {
  test("a step is a model as /models names it; its provider and alias say where it runs", () => {
    expect(parseStep("openai/gpt-6-luna#low", NAMES)).toEqual({
      step: {
        model: { providerID: "openai", id: "gpt-6-luna", variant: "low" },
        places: [{ kind: "active" }],
      },
      problems: [],
    })
    expect(parseStep(`${TEAM}/claude-haiku-5-5#low`, NAMES)).toEqual({
      step: { model: HAIKU, places: [{ kind: "lane", providerID: TEAM }] },
      problems: [],
    })
    expect(parseStep("anthropic/claude-haiku-5-5-sub#low", NAMES)).toEqual({
      step: { model: HAIKU, places: [{ kind: "login", suffix: "sub" }] },
      problems: [],
    })
    expect(parseStep(" anthropic/claude-haiku-5-5#low ", NAMES).step).toEqual({
      model: HAIKU,
      places: [{ kind: "active" }],
    })
    expect(parseStep("anthropic/claude-haiku-5-5", NAMES).step?.model).toEqual({
      providerID: "anthropic",
      id: "claude-haiku-5-5",
    })
    expect(parseStep("xai/grok-4.7#low", NAMES).step?.places).toEqual([
      { kind: "active" },
    ])
    expect(
      parseStep("google/antigravity-gemini-3.8-flash-low", NAMES).step,
    ).toEqual({
      model: { providerID: "google", id: "antigravity-gemini-3.8-flash-low" },
      places: [{ kind: "active" }],
    })
  })
  test("malformed steps and places it cannot use are ignored, each with its reason", () => {
    for (const [text, reason] of [
      [42, /must be a string/],
      ["claude-haiku-5-5", /is not a model/],
      ["anthropic/claude-haiku-5-5#low @ credit(team)", /is not a model/],
      ["anthropic/*", /is not a model/],
      ["anthropic/claude-haiku-5-5-spare", /no labelled Claude login "spare"/],
      [
        "anthropic/claude-haiku-5-5-fast-sub",
        /no labelled Claude login "fast-sub"/,
      ],
      ["anthropic-credit-sub/claude-haiku-5-5", /neither a credit lane/],
      ["mistral/large", /neither a credit lane/],
      ["google/antigravity-gpt-oss-120b-medium", /no Antigravity quota group/],
    ] as const) {
      const { step, problems } = parseStep(text, NAMES)
      expect(step).toBeUndefined()
      expect(problems.join("\n")).toMatch(reason)
    }
  })
  test("the primary's places are models left as *", () => {
    expect(
      parsePlaces(
        [
          "anthropic/*-main",
          "anthropic/*",
          `${TEAM}/*`,
          "anthropic/*-spare",
          "nowhere",
        ],
        NAMES,
      ),
    ).toEqual({
      places: [
        { kind: "login", suffix: "main" },
        { kind: "active" },
        { kind: "lane", providerID: TEAM },
      ],
      problems: [
        `primaryRoute: "anthropic/*-spare": no labelled Claude login "spare" in claudeAccounts`,
        `primaryRoute: "nowhere" is not a place ("provider/*" or "anthropic/*-<login>")`,
      ],
    })
    expect(parsePlaces([`${TEAM}/*-main`], NAMES).problems).toEqual([
      `primaryRoute: "${TEAM}/*-main": a credit lane runs no login's alias`,
    ])
    expect(parsePlaces(undefined, NAMES)).toEqual({ problems: [] })
    expect(parsePlaces("anthropic/*", NAMES).problems).toEqual([
      "primaryRoute must be a list of places",
    ])
  })
  test("a place runs the model as its alias or on its lane, and is the stop a session moves to", () => {
    expect(modelAt(HAIKU, { kind: "login", suffix: "main" })).toEqual({
      ...HAIKU,
      id: "claude-haiku-5-5-main",
    })
    expect(modelAt(HAIKU, { kind: "lane", providerID: "x" })).toEqual({
      ...HAIKU,
      providerID: "x",
    })
    expect(stopOf({ kind: "active" }).key).toBe("anthropic")
    expect(stopOf({ kind: "login", suffix: "main" }).key).toBe("anthropic#main")
    expect(stopOf({ kind: "lane", providerID: "x" }).key).toBe("x")
  })
})

describe("route table", () => {
  test("built in: a Claude model on the lanes, the active login, then the other logins", () => {
    const lane = (providerID: string) => ({ kind: "lane" as const, providerID })
    expect(defaultSteps(ROUTES.reviewer, NAMES)).toEqual([
      {
        model: ROUTES.reviewer.primary,
        places: [lane(TEAM), lane(MAIN_LANE)],
      },
      { model: ROUTES.reviewer.primary, places: [{ kind: "active" }] },
      {
        model: ROUTES.reviewer.primary,
        places: [
          { kind: "login", suffix: "main" },
          { kind: "login", suffix: "sub" },
        ],
      },
      { model: ROUTES.reviewer.alternate, places: [{ kind: "active" }] },
    ])
    expect(defaultSteps(ROUTES.verifier, { lanes: [], logins: [] })).toEqual([
      { model: ROUTES.verifier.primary, places: [{ kind: "active" }] },
      { model: ROUTES.verifier.alternate, places: [{ kind: "active" }] },
    ])
  })
  test("the option's roles replace the built-in ones; the rest stay", () => {
    const { table, problems, primary } = readRoutes(
      {
        routes: {
          verifier: [
            "openai/gpt-6-luna#low",
            "anthropic/claude-haiku-5-5-sub#low",
          ],
          worker: ["nope"],
          "explore-small": [],
          extra: ["xai/grok-4.7#low"],
          searcher: "xai/grok-4.7#low",
        },
        primaryRoute: ["anthropic/*-sub", `${TEAM}/*`],
      },
      NAMES,
    )
    expect(table.verifier.map((s) => s.places[0].kind)).toEqual([
      "active",
      "login",
    ])
    // Nothing readable keeps the built-in steps, with its problems; only an
    // empty list unroutes a role.
    expect(table.worker).toEqual(defaultSteps(ROUTES.worker, NAMES))
    expect(Object.hasOwn(table, "explore-small")).toBe(false)
    expect(table.extra).toHaveLength(1)
    // Not a list: the built-in steps stay, with a problem.
    expect(modelsEqual(table.searcher[0].model, ROUTES.searcher.primary)).toBe(
      true,
    )
    expect(table.reviewer).toEqual(defaultSteps(ROUTES.reviewer, NAMES))
    expect(Object.keys(problems).sort()).toEqual(["searcher", "worker"])
    expect(primary).toEqual([
      { kind: "login", suffix: "sub" },
      { kind: "lane", providerID: TEAM },
    ])
  })
  test("a malformed option leaves the built-in table and says so", () => {
    const { table, problems, primary } = readRoutes(
      { routes: ["x"], primaryRoute: 3 },
      NAMES,
    )
    expect(table.worker).toEqual(defaultSteps(ROUTES.worker, NAMES))
    expect(problems[""]).toHaveLength(2)
    expect(primary).toBeUndefined()
  })
  test("a primaryRoute with no readable place keeps the built-in order", () => {
    for (const primaryRoute of [[], ["anthropic/*-nope"]]) {
      const { primary, problems } = readRoutes({ primaryRoute }, NAMES)
      expect(primary).toBeUndefined()
      expect(problems[""]).toContain(
        "primaryRoute has no place; the built-in order applies",
      )
    }
  })
  test("the routes opencode.jsonc sets read whole, with no problem", async () => {
    const config = Bun.JSONC.parse(
      await Bun.file(new URL("../../opencode.jsonc", import.meta.url)).text(),
    ) as {
      plugins: (string | { package: string; options?: Record<string, any> })[]
    }
    const { options } = config.plugins.find(
      (p) => typeof p !== "string" && p.package === "./lib/subagent-fallback",
    ) as { options: Record<string, any> }
    const logins = Object.keys(options.claudeAccounts)
    const { table, problems } = readRoutes(options, {
      lanes: options.creditLanes,
      logins,
      suffixes: logins,
    })
    expect(problems).toEqual({})
    for (const [role, steps] of Object.entries(options.routes))
      expect(`${role}: ${table[role].length}`).toBe(
        `${role}: ${(steps as string[]).length}`,
      )
  })
  test("a new role with no readable step is not routed, and every launch says so", () => {
    const { table, problems } = readRoutes({ routes: { extra: ["x"] } }, NAMES)
    expect(Object.hasOwn(table, "extra")).toBe(false)
    expect(problems[""]).toEqual(["routes.extra has no step it can use"])
  })
  test("explicit models, continuations, unknown roles and changed defaults bypass selection", () => {
    const { table } = readRoutes({}, NAMES)
    const configured = ROUTES.worker.primary
    for (const input of [
      { agent: "worker", model: "explicit" },
      { agent: "worker", sessionID: "ses_1" },
      { agent: "unknown" },
      { agent: "__proto__" },
      {},
    ])
      expect(stepsForLaunch(input, configured, false, table)).toBeUndefined()
    expect(
      stepsForLaunch(
        { agent: "worker" },
        { ...configured, variant: "high" },
        false,
        table,
      ),
    ).toBeUndefined()
    expect(
      stepsForLaunch({ agent: "worker" }, undefined, false, table),
    ).toBeUndefined()
    expect(stepsForLaunch({ agent: "worker" }, configured, false, table)).toBe(
      table.worker,
    )
  })
  test("pin keeps a role's steps whatever model is configured, but never an explicit model, continuation or unknown role", () => {
    const { table } = readRoutes({}, NAMES)
    const changed = { providerID: "openai", id: "gpt-5.6-terra" }
    for (const configured of [changed, undefined, ROUTES.reviewer.primary])
      expect(
        stepsForLaunch({ agent: "reviewer" }, configured, true, table),
      ).toBe(table.reviewer)
    for (const input of [
      { agent: "reviewer", model: "explicit" },
      { agent: "reviewer", sessionID: "ses_1" },
      { agent: "unknown" },
      { agent: "__proto__" },
      {},
    ])
      expect(stepsForLaunch(input, changed, true, table)).toBeUndefined()
  })
})
