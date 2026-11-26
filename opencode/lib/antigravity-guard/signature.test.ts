import { describe, expect, test } from "bun:test"
import {
  isAntigravity,
  neutralizeSystem,
  neutralizeText,
  type SystemPart,
} from "./signature"

describe("system signature", () => {
  test("rewrites the signature and counts it", () => {
    expect(neutralizeText("Use tools.opencode.session_move")).toEqual({
      text: 'Use tools["opencode"].session_move',
      count: 1,
    })
  })

  test("rewrites every occurrence", () => {
    expect(neutralizeText("tools.opencode.a tools.opencode.b")).toEqual({
      text: 'tools["opencode"].a tools["opencode"].b',
      count: 2,
    })
  })

  test("is idempotent", () => {
    const first = neutralizeText("tools.opencode.session_move")
    expect(neutralizeText(first.text)).toEqual({ text: first.text, count: 0 })
  })

  test("leaves text without the needle unchanged", () => {
    const text = "Use another tool"
    expect(neutralizeText(text)).toEqual({ text, count: 0 })
  })

  test("mutates only text parts, preserving metadata and other fields", () => {
    const metadata = { text: "tools.opencode.metadata" }
    const other = { type: "image", text: "tools.opencode.image" }
    const missing = { type: "text", metadata }
    const system: SystemPart[] = [
      { type: "text", text: "tools.opencode.a", metadata },
      other,
      missing,
      { type: "text", text: "tools.opencode.b tools.opencode.c" },
    ]
    const first = system[0]
    expect(neutralizeSystem(system)).toBe(3)
    expect(system[0]).toBe(first)
    expect(system[0].text).toBe('tools["opencode"].a')
    expect(system[0].metadata).toBe(metadata)
    expect(metadata).toEqual({ text: "tools.opencode.metadata" })
    expect(system[1]).toBe(other)
    expect(other.text).toBe("tools.opencode.image")
    expect(system[2]).toBe(missing)
    expect(system[2].text).toBeUndefined()
    expect(system[3].text).toBe('tools["opencode"].b tools["opencode"].c')
  })
})

describe("Antigravity models", () => {
  test.each([
    ["google", "antigravity-gemini-4-hydrogen-low", true],
    ["google", "gemini-3-pro", false],
    ["anthropic", "antigravity-x", false],
  ] as const)("%s/%s matches: %s", (providerID, id, expected) => {
    expect(isAntigravity({ providerID, id })).toBe(expected)
  })
})
