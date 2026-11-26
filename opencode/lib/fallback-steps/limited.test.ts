import { describe, expect, test } from "bun:test"
import {
  emptyLane,
  HOUR_MS,
  LANE,
  LANE_AT,
  NOW,
  RESET,
  setup,
  UNTIL,
  USABLE,
  useTempDir,
} from "./fixture"

useTempDir()

const held = (name: string, until = UNTIL) => ({
  usable: false,
  reason: `${name} hit a limit until ${until}`,
})
const LANE_UNTIL = new Date(LANE_AT + HOUR_MS).toISOString()
const LANES = {
  readLanes: () => ({ lanes: [LANE], state: { [LANE.provider]: emptyLane } }),
}

describe("a window a limit spent", () => {
  test("a limit on one model of a Claude login passes over its other models until its end", async () => {
    const f = await setup({ creditLanes: [LANE.provider] })
    await f.limited("anthropic/claude-opus-5-5#high")
    expect(await f.ask("anthropic/claude-haiku-5-5")).toEqual(
      held("the active Claude login"),
    )
    expect(await f.ask(`${LANE.provider}/claude-haiku-5-5`)).toEqual(USABLE)
    expect(await f.ask("openai/gpt-6.1-sol")).toEqual(USABLE)
    f.clock.now = RESET - 1
    expect((await f.ask("anthropic/claude-haiku-5-5")).usable).toBe(false)
    f.clock.now = RESET
    expect(await f.ask("anthropic/claude-haiku-5-5")).toEqual(USABLE)
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
  test("holding a window does not depend on looking up the active login", async () => {
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
