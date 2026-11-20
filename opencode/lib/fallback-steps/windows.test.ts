import { describe, expect, test } from "bun:test"
import { Windows, windowOf, type WindowEnv } from "./windows"

const accounts = [
  { suffix: "sub", label: "Sub OAuth" },
  { suffix: "blank", label: "" },
]
const env = (label: string | undefined = "Main OAuth"): WindowEnv => ({
  creditLanes: ["lane-a"],
  accounts,
  activeLabel: async () => label,
})
const of = (providerID: string, id: string, label?: string) =>
  windowOf({ providerID, id }, label === undefined ? env() : env(label))

describe("windowOf", () => {
  test("every model of a lane shares the lane", async () => {
    const lane = { key: "lane:lane-a", name: "credit lane lane-a" }
    expect(await of("lane-a", "claude-opus-5-5")).toEqual(lane)
    expect(await of("lane-a", "claude-haiku-5-5")).toEqual(lane)
  })
  test("a Claude login's models share it, the active login by its label", async () => {
    const sub = { key: "claude:Sub OAuth", name: 'Claude login "Sub OAuth"' }
    expect(await of("anthropic", "claude-opus-5-5-sub")).toEqual(sub)
    expect(await of("anthropic", "claude-haiku-5-5-sub")).toEqual(sub)
    expect(await of("anthropic", "claude-opus-5-5")).toEqual({
      key: "claude:Main OAuth",
      name: 'Claude login "Main OAuth"',
    })
  })
  test("the active login without a label is its own window", async () => {
    expect(await of("anthropic", "claude-opus-5-5", "")).toEqual({
      key: "claude:active",
      name: "the active Claude login",
    })
  })
  test("an alias without a login label has no window", async () => {
    expect(await of("anthropic", "claude-opus-5-5-blank")).toBeUndefined()
  })
  test("ChatGPT and xAI are one window each", async () => {
    expect(await of("openai", "gpt-6.1-sol")).toEqual({
      key: "openai",
      name: "the active ChatGPT login",
    })
    expect(await of("xai", "grok-4.7")).toEqual({
      key: "xai",
      name: "the active xAI login",
    })
  })
  test("Antigravity's models share their group", async () => {
    const pro = { key: "google#gemini-pro", name: "Antigravity Gemini Pro" }
    expect(await of("google", "antigravity-gemini-4-argon-high")).toEqual(pro)
    expect(await of("google", "antigravity-gemini-4-hydrogen-low")).toEqual(pro)
    expect(await of("google", "antigravity-claude-opus-5-5-high")).toEqual({
      key: "google#claude",
      name: "Antigravity Claude",
    })
    const oss = await of("google", "antigravity-gpt-oss-120b-medium")
    expect(oss).toBeUndefined()
  })
  test("anything else shares nothing", async () => {
    expect(await of("openrouter", "some-model")).toBeUndefined()
    expect(await of("constructor", "x")).toBeUndefined()
  })
})

describe("Windows", () => {
  test("holds a window until its end, then lets go", () => {
    const windows = new Windows()
    expect(windows.empty).toBe(true)
    windows.hold("a", 2_000, 1_000)
    expect(windows.empty).toBe(false)
    expect(windows.heldUntil("a", 1_999)).toBe(2_000)
    expect(windows.heldUntil("a", 2_000)).toBeUndefined()
    expect(windows.empty).toBe(true)
  })
  test("a later end wins and an earlier one does not shorten it", () => {
    const windows = new Windows()
    windows.hold("a", 3_000, 1_000)
    windows.hold("a", 2_000, 1_000)
    expect(windows.heldUntil("a", 1_000)).toBe(3_000)
    windows.hold("a", 5_000, 1_000)
    expect(windows.heldUntil("a", 1_000)).toBe(5_000)
  })
  test("an end already past, or not a time, holds nothing", () => {
    const windows = new Windows()
    windows.hold("a", 1_000, 1_000)
    windows.hold("b", Number.NaN, 1_000)
    expect(windows.empty).toBe(true)
    expect(windows.heldUntil("a", 0)).toBeUndefined()
  })
})
