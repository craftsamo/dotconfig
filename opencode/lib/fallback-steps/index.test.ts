import { afterEach, beforeEach, describe, expect, test } from "bun:test"
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import type { Lane, LaneState } from "../credit-lanes/core"
import { EMPTY_PROBE_MS } from "../subagent-fallback/empty-lanes"
import { QUOTA_RPC } from "../subagent-fallback/quota-refresh"
import { fileStore } from "../subagent-fallback/saved"
import { statePath, type StepsDeps } from "./deps"
import plugin, { setupFallbackSteps } from "./index"

const NOW = 1_710_000_000_000
const HOUR_MS = 3_600_000
const RESET = NOW + HOUR_MS
const UNTIL = new Date(RESET).toISOString()
const USABLE = { usable: true }
const signal = new AbortController().signal
const never = () => new Promise<never>(() => {})

type Login = { id: string; label?: string; methodID: string }
const LOGINS: Record<string, Login[]> = {
  anthropic: [
    { id: "main-id", label: "Main", methodID: "claude-max" },
    { id: "sub-id", label: "Sub", methodID: "claude-max" },
  ],
  openai: [{ id: "chatgpt-id", methodID: "chatgpt-browser" }],
  xai: [{ id: "xai-id", methodID: "device" }],
  google: [{ id: "agy-id", methodID: "antigravity" }],
}
const ACTIVE: Record<string, string> = {
  anthropic: "main-id",
  openai: "chatgpt-id",
  xai: "xai-id",
  google: "agy-id",
}

// A Quota 6 row: its `account` is the login's label.
const row = (providerID: string, account: string, percentRemaining = 90) => ({
  id: providerID === "xai" ? "xai.credits" : `${providerID}.five_hour`,
  window: "5h",
  percentRemaining,
  account,
  resultType: "quota",
  acquisitionMethod: "remote_api",
  authority: "provider_reported",
  renderType: "percent",
  resetAt: RESET / 1000,
})
const part = (entries: unknown[], fetchedAt = NOW / 1000) => ({
  status: "ok",
  fetchedAt,
  entries,
})
const agyRow = (group: string, percentRemaining: number) => ({
  id: `quota-providers.custom.google-antigravity.${group}`,
  resultType: "quota",
  percentRemaining,
  resetAt: RESET / 1000,
})

const LANE: Lane = {
  provider: "anthropic-credit-main",
  label: "Main",
  amount: 200,
  renewalDay: 13,
}
const LANE_AT = new Date(2026, 9, 20, 12).getTime()
const emptyLane: LaneState = {
  grants: [],
  checkpoint: {
    at: new Date(LANE_AT).toISOString(),
    balance: 0,
    source: "empty",
    opencodeFrom: "2026-10-20",
    opencodeBase: 0,
  },
}

let dir: string
beforeEach(async () => {
  dir = await mkdtemp(join(tmpdir(), "fallback-steps-"))
})
afterEach(() => rm(dir, { recursive: true, force: true }))

async function setup(
  options: Record<string, unknown> = {},
  exported: Record<string, unknown> = {},
  extra: Partial<StepsDeps> & { logins?: Record<string, Login[]> } = {},
) {
  const { logins = LOGINS, ...overrides } = extra
  const exportFile = join(dir, "quota-export.json")
  await writeFile(
    exportFile,
    JSON.stringify({ version: 3, providers: exported }),
  )
  const clock = { now: NOW }
  const deps: StepsDeps = {
    now: () => clock.now,
    readExport: (path) => readFile(path, "utf8"),
    sleep: never,
    antigravityReserve: () => 10,
    saved: fileStore(join(dir, "state.json")),
    exportFile,
    ...overrides,
  }
  const calls = { refresh: [] as unknown[], disposed: false }
  const handlers: { usable: any; limit: any } = {} as any
  const ctx: any = {
    options,
    app: { version: "2.3.0" },
    session: { get: async () => ({}) },
    provider: {
      get: async ({ providerID }: { providerID: string }) => {
        if (!logins[providerID]) throw new Error("no provider")
        return { data: { package: `@opencode/ai/providers/${providerID}` } }
      },
    },
    integration: {
      get: async ({ integrationID }: { integrationID: string }) => ({
        data: {
          connections: (logins[integrationID] ?? []).map((l) => ({
            type: "credential",
            method: "oauth",
            ...l,
          })),
        },
      }),
      connection: {
        active: async (providerID: string) => {
          const id = ACTIVE[providerID]
          return logins[providerID]?.some((l) => l.id === id)
            ? { type: "credential", method: "oauth", id }
            : undefined
        },
        resolve: async ({ id }: { id: string }) => {
          const found = Object.values(logins)
            .flat()
            .find((l) => l.id === id)
          return found && {
            type: "oauth",
            methodID: found.methodID,
            access: `token-${id}`,
            metadata: { accountID: "account" },
          }
        },
      },
    },
    rpc: Object.assign(
      (definition: typeof QUOTA_RPC) => {
        expect(definition.id).toBe(QUOTA_RPC.id)
        return {
          refresh: async (input: unknown) => {
            calls.refresh.push(input)
            return never()
          },
        }
      },
      {
        register: async (_definition: unknown, registered: any) => {
          Object.assign(handlers, registered)
          return { dispose: async () => void (calls.disposed = true) }
        },
      },
    ),
  }
  const cleanup = await setupFallbackSteps(ctx, deps)
  const ask = (model: string) =>
    handlers.usable({ agent: "worker", model }, { signal })
  return { ask, calls, clock, cleanup, handlers, ctx, deps }
}

const fresh = (providerID: string, ...rows: unknown[]) => ({
  [providerID]: part(rows),
})

describe("registration", () => {
  test("registers both handlers, never calls a limit, and disposes", async () => {
    const f = await setup()
    expect(f.handlers.limit).toBeFunction()
    expect(
      await f.handlers.limit(
        { agent: "worker", model: "a/x", error: { type: "x", message: "m" } },
        { signal },
      ),
    ).toEqual({ limit: false })
    await f.cleanup()
    expect(f.calls.disposed).toBe(true)
  })
  test("the plugin is named for dotconfig and keeps its state beside the old one", () => {
    expect(plugin.id).toBe("dotconfig.fallback-steps")
    expect(statePath({ XDG_STATE_HOME: "/s" }, "/h")).toBe(
      "/s/opencode/fallback-steps.json",
    )
    expect(statePath({}, "/h")).toBe(
      "/h/.local/state/opencode/fallback-steps.json",
    )
  })
})

describe("Claude subscription", () => {
  test("the active login with quota left, or no data, is usable", async () => {
    const f = await setup({}, fresh("anthropic", row("anthropic", "Main")))
    expect(await f.ask("anthropic/claude-opus-5-5#high")).toEqual(USABLE)
    expect(f.calls.refresh).toEqual([])
    const unknown = await setup({}, {})
    expect(await unknown.ask("anthropic/claude-opus-5-5")).toEqual(USABLE)
  })
  test("an exhausted active login is refused, naming it and the reset", async () => {
    const f = await setup({}, fresh("anthropic", row("anthropic", "Main", 0)))
    expect(await f.ask("anthropic/claude-opus-5-5#high")).toEqual({
      usable: false,
      reason: `the active Claude login has no included quota left until ${UNTIL}`,
    })
  })
  test("an alias runs on its own saved login, never combined with the active one", async () => {
    const options = { claudeAccounts: { sub: "Sub" } }
    const exported = fresh(
      "anthropic",
      row("anthropic", "Main"),
      row("anthropic", "Sub", 0),
    )
    const f = await setup(options, exported)
    expect(await f.ask("anthropic/claude-opus-5-5-sub#high")).toEqual({
      usable: false,
      reason: `Claude login "Sub" has no included quota left until ${UNTIL}`,
    })
    expect(await f.ask("anthropic/claude-opus-5-5")).toEqual({ usable: true })
    const spentMain = await setup(
      options,
      fresh("anthropic", row("anthropic", "Main", 0), row("anthropic", "Sub")),
    )
    expect(await spentMain.ask("anthropic/claude-opus-5-5-sub")).toEqual({
      usable: true,
    })
  })
  test("an alias whose login is missing or has no label is refused with the account error", async () => {
    const gone = await setup({ claudeAccounts: { sub: "Gone" } })
    expect(await gone.ask("anthropic/claude-opus-5-5-sub")).toEqual({
      usable: false,
      reason: 'Claude account: no saved Claude login is labelled "Gone"',
    })
    const blank = await setup({ claudeAccounts: { sub: " " } })
    expect(await blank.ask("anthropic/claude-opus-5-5-sub")).toEqual({
      usable: false,
      reason:
        'Claude account: claudeAccounts gives the "sub" models no login label',
    })
  })
  test("the longest configured suffix claims the model", async () => {
    const f = await setup(
      { claudeAccounts: { sub: "Sub", "team-sub": "Gone" } },
      fresh("anthropic", row("anthropic", "Sub")),
    )
    const answer = await f.ask("anthropic/claude-opus-5-5-team-sub")
    expect(answer.reason).toContain('"Gone"')
  })
  test("a malformed claudeAccounts refuses every Claude subscription step", async () => {
    const f = await setup({ claudeAccounts: ["sub"] })
    const reason =
      "Claude account: claudeAccounts must map model-ID suffixes to login labels"
    expect(await f.ask("anthropic/claude-opus-5-5")).toEqual({
      usable: false,
      reason,
    })
    expect(await f.ask("anthropic/claude-opus-5-5-sub")).toEqual({
      usable: false,
      reason,
    })
    expect(await f.ask("openrouter/some-model")).toEqual({ usable: true })
  })
  test("no approved Claude login is refused", async () => {
    const f = await setup({}, {}, { logins: { ...LOGINS, anthropic: [] } })
    expect(await f.ask("anthropic/claude-opus-5-5")).toEqual({
      usable: false,
      reason: "no approved Claude login",
    })
  })
})

describe("ChatGPT and xAI subscriptions", () => {
  test.each([
    ["openai", "ChatGPT", "openai/gpt-6.1-sol#high"],
    ["xai", "xAI", "xai/grok-4.7#low"],
  ])("%s: spent is refused, with quota left usable, no login refused", async (providerID, name, step) => {
    const spent = await setup({}, fresh(providerID, row(providerID, "Acct", 0)))
    expect(await spent.ask(step)).toEqual({
      usable: false,
      reason: `the active ${name} login has no included quota left until ${UNTIL}`,
    })
    const left = await setup({}, fresh(providerID, row(providerID, "Acct")))
    expect(await left.ask(step)).toEqual({ usable: true })
    const logins = { ...LOGINS, [providerID]: [] }
    const none = await setup({}, {}, { logins })
    expect(await none.ask(step)).toEqual({
      usable: false,
      reason: `no approved ${name} login`,
    })
  })
})

describe("Antigravity", () => {
  const exported = {
    "quota-providers": part([
      agyRow("Claude", 0),
      agyRow("Gemini_Pro", 50),
      agyRow("Gemini_Flash", 5),
    ]),
  }
  test("a spent group is refused by family, a group with quota left is usable", async () => {
    const f = await setup({}, exported)
    expect(await f.ask("google/antigravity-claude-opus-5-5-high")).toEqual({
      usable: false,
      reason: `Antigravity Claude has no included quota left until ${UNTIL}`,
    })
    // 5% left is under the plugin's reserve.
    const flash = await f.ask("google/antigravity-gemini-3.8-flash-low")
    expect(flash.reason).toContain("Antigravity Gemini Flash")
    expect(await f.ask("google/antigravity-gemini-4-argon-high")).toEqual({
      usable: true,
    })
  })
  test("a reserve of 0 leaves a nearly spent group usable", async () => {
    const f = await setup({}, exported, { antigravityReserve: () => 0 })
    expect(await f.ask("google/antigravity-gemini-3.8-flash-low")).toEqual({
      usable: true,
    })
  })
  test("no approved login is refused; a model of no known family is usable", async () => {
    const f = await setup({}, exported, { logins: { ...LOGINS, google: [] } })
    expect(await f.ask("google/antigravity-gemini-4-argon-high")).toEqual({
      usable: false,
      reason: "no approved Antigravity login",
    })
    expect(await f.ask("google/antigravity-gpt-oss-120b-medium")).toEqual({
      usable: true,
    })
  })
})

describe("stale and unknown Quota data", () => {
  test("stale data never refuses; it asks Quota for one check without delaying the answer", async () => {
    const stale = {
      anthropic: part([row("anthropic", "Main")], NOW / 1000 - 3_600),
    }
    const f = await setup({}, stale)
    const started = Date.now()
    expect(await f.ask("anthropic/claude-opus-5-5")).toEqual({ usable: true })
    expect(await f.ask("anthropic/claude-opus-5-5")).toEqual({ usable: true })
    expect(Date.now() - started).toBeLessThan(1_000)
    expect(f.calls.refresh).toEqual([
      { reason: "poll", providerIds: ["anthropic"] },
    ])
  })
  test("a spent window stays spent however stale the export, until its reset", async () => {
    const old = {
      anthropic: part([row("anthropic", "Main", 0)], NOW / 1000 - 3_600),
    }
    const f = await setup({}, old)
    expect((await f.ask("anthropic/claude-opus-5-5")).usable).toBe(false)
  })
  test("an unreadable export is usable", async () => {
    const f = await setup({}, {}, { readExport: async () => "not json" })
    expect(await f.ask("anthropic/claude-opus-5-5")).toEqual({ usable: true })
    expect(await f.ask("google/antigravity-claude-opus-5-5-high")).toEqual({
      usable: true,
    })
  })
})

describe("credit lanes", () => {
  const options = { creditLanes: [LANE.provider] }
  const book = () => ({ lanes: [LANE], state: { [LANE.provider]: emptyLane } })
  const savedFile = () => join(dir, "state.json")

  test("a lane known empty is refused; other steps are untouched", async () => {
    const f = await setup(options, {}, { readLanes: book })
    f.clock.now = LANE_AT + 60_000
    expect((await f.ask(`${LANE.provider}/claude-opus-5-5`)).usable).toBe(false)
    expect(await f.ask("openrouter/some-model")).toEqual({ usable: true })
  })
  test("a lane with no estimate, or one not configured, is usable", async () => {
    const f = await setup(options, {}, { readLanes: () => undefined })
    expect(await f.ask(`${LANE.provider}/claude-opus-5-5`)).toEqual({
      usable: true,
    })
    const off = await setup({}, {}, { readLanes: book })
    off.clock.now = LANE_AT + 60_000
    expect(await off.ask(`${LANE.provider}/claude-opus-5-5`)).toEqual({
      usable: true,
    })
  })
  test("a lane due for its daily try passes once and the try is saved", async () => {
    const f = await setup(options, {}, { readLanes: book })
    f.clock.now = LANE_AT + EMPTY_PROBE_MS + 1_000
    const step = `${LANE.provider}/claude-opus-5-5#high`
    expect(await f.ask(step)).toEqual({ usable: true })
    expect((await f.ask(step)).usable).toBe(false)
    expect(JSON.parse(await readFile(savedFile(), "utf8")).probed).toEqual({
      [LANE.provider]: f.clock.now,
    })
  })
  test("a restart restores the saved try", async () => {
    const at = LANE_AT + EMPTY_PROBE_MS + 1_000
    await writeFile(
      savedFile(),
      JSON.stringify({ probed: { [LANE.provider]: at - 1_000 } }),
    )
    const f = await setup(options, {}, { readLanes: book, now: () => at })
    expect((await f.ask(`${LANE.provider}/claude-opus-5-5`)).usable).toBe(false)
  })
})

describe("failures", () => {
  test("an unknown provider or a text that is no step is usable", async () => {
    const f = await setup()
    expect(await f.ask("openrouter/some-model#high")).toEqual({ usable: true })
    expect(await f.ask("nonsense")).toEqual({ usable: true })
  })
  test("an internal failure never refuses", async () => {
    const f = await setup({}, fresh("openai", row("openai", "Acct", 0)))
    f.ctx.provider.get = async () => {
      throw new Error("provider lookup failed")
    }
    expect(await f.ask("openai/gpt-6.1-sol")).toEqual({ usable: true })
  })
})
