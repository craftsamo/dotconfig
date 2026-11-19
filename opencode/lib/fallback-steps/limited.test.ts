import { describe, expect, test } from "bun:test"
import {
  emptyLane,
  HOUR_MS,
  LANE,
  LANE_AT,
  LOGINS,
  NOW,
  RESET,
  setup,
  UNTIL,
  USABLE,
  useTempDir,
} from "./fixture"

useTempDir()

const accounts = { claudeAccounts: { main: "Main", sub: "Sub" } }
const held = (name: string, until = UNTIL) => ({
  usable: false,
  reason: `${name} hit a limit until ${until}`,
})
const MAIN = held('Claude login "Main"')
const SUB = held('Claude login "Sub"')
const LANE_UNTIL = new Date(LANE_AT + HOUR_MS).toISOString()
const LANES = {
  readLanes: () => ({ lanes: [LANE], state: { [LANE.provider]: emptyLane } }),
}

describe("a window a limit spent", () => {
  test("a limit on one model of a Claude login passes over its other models until its end", async () => {
    const f = await setup(accounts)
    await f.limited("anthropic/claude-x-sub#high")
    expect(await f.ask("anthropic/claude-y-sub")).toEqual(SUB)
    expect(await f.ask("anthropic/claude-y-main")).toEqual(USABLE)
    f.clock.now = RESET - 1
    expect((await f.ask("anthropic/claude-y-sub")).usable).toBe(false)
    f.clock.now = RESET
    expect(await f.ask("anthropic/claude-y-sub")).toEqual(USABLE)
  })
  test("the plain model shares the account of the active login with its alias, and no other", async () => {
    const f = await setup(accounts)
    await f.limited("anthropic/claude-opus-5-5")
    expect(await f.ask("anthropic/claude-haiku-5-5")).toEqual(MAIN)
    expect(await f.ask("anthropic/claude-opus-5-5-main")).toEqual(MAIN)
    expect(await f.ask("anthropic/claude-opus-5-5-sub")).toEqual(USABLE)
    const other = await setup(accounts)
    await other.limited("anthropic/claude-opus-5-5-main")
    expect((await other.ask("anthropic/claude-opus-5-5")).usable).toBe(false)
  })
  test("an active login without a label is a window of its own", async () => {
    const logins = {
      ...LOGINS,
      anthropic: [{ id: "main-id", methodID: "claude-max" }],
    }
    const f = await setup({}, {}, { logins })
    await f.limited("anthropic/claude-opus-5-5")
    expect(await f.ask("anthropic/claude-haiku-5-5")).toEqual(
      held("the active Claude login"),
    )
  })
  test("a limit on a lane passes over its other models, not other lanes' or other providers'", async () => {
    const team = "anthropic-credit-team"
    const f = await setup({ creditLanes: [LANE.provider, team] }, {}, LANES)
    f.clock.now = LANE_AT + 60_000
    await f.limited(`${LANE.provider}/claude-opus-5-5#high`, LANE_UNTIL)
    expect(await f.ask(`${LANE.provider}/claude-haiku-5-5`)).toEqual(
      held(`credit lane ${LANE.provider}`, LANE_UNTIL),
    )
    expect(await f.ask(`${team}/claude-haiku-5-5`)).toEqual(USABLE)
    expect(await f.ask("openrouter/some-model")).toEqual(USABLE)
  })
  test("ChatGPT, xAI and Antigravity's groups are windows too", async () => {
    const f = await setup()
    await f.limited("openai/gpt-6.1-sol#high")
    await f.limited("xai/grok-4.7")
    await f.limited("google/antigravity-gemini-4-argon-high")
    expect(await f.ask("openai/gpt-6-luna")).toEqual(
      held("the active ChatGPT login"),
    )
    expect(await f.ask("xai/grok-5")).toEqual(held("the active xAI login"))
    expect(await f.ask("google/antigravity-gemini-4-hydrogen-low")).toEqual(
      held("Antigravity Gemini Pro"),
    )
    const flash = "google/antigravity-gemini-3.8-flash-low"
    expect(await f.ask(flash)).toEqual(USABLE)
  })
  test("an event on a model that shares no window holds nothing", async () => {
    const f = await setup()
    await f.limited("openrouter/some-model")
    await f.limited("nonsense")
    await f.limited("google/antigravity-gpt-oss-120b-medium")
    for (const step of [
      "openrouter/other-model",
      "google/antigravity-gpt-oss-120b-medium",
      "anthropic/claude-opus-5-5",
      "openai/gpt-6.1-sol",
    ])
      expect(await f.ask(step)).toEqual(USABLE)
  })
  test("an event off the schema, or ending in the past, is ignored", async () => {
    const f = await setup()
    const data = (extra: Record<string, unknown>) => ({
      data: { model: "openai/gpt-6.1-sol", until: UNTIL, ...extra },
    })
    await f.emit({})
    await f.emit(undefined)
    await f.emit(data({ until: "garbage" }))
    await f.emit(data({ until: 5 }))
    await f.emit(data({ until: undefined }))
    await f.emit(data({ model: undefined }))
    await f.emit(data({ until: new Date(NOW - 1).toISOString() }))
    expect(await f.ask("openai/gpt-6-luna")).toEqual(USABLE)
  })
  test("an active login that cannot be looked up is the unlabelled one", async () => {
    const f = await setup()
    f.ctx.provider.get = async () => {
      throw new Error("provider lookup failed")
    }
    await f.limited("anthropic/claude-opus-5-5")
    expect(await f.ask("anthropic/claude-haiku-5-5")).toEqual(
      held("the active Claude login"),
    )
  })
  test("stops hearing events once disposed", async () => {
    const f = await setup()
    await f.cleanup()
    await f.limited("openai/gpt-6.1-sol")
    expect(await f.ask("openai/gpt-6-luna")).toEqual(USABLE)
  })
})
