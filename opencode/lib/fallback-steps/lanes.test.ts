import { describe, expect, test } from "bun:test"
import { antigravityLimit, classify, type Decision } from "./lanes"

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

describe("Antigravity limits", () => {
  const error = (message: string) => ({ type: "provider.unknown", message })
  test("its plugin's two refusals give their wait", () => {
    expect(
      antigravityLimit(
        error(
          "Quota protection: All 1 account(s) are over 90% usage for gemini. Quota resets in 2h 30m. Add more accounts, wait for quota reset, or set soft_quota_threshold_percent: 100 to disable.",
        ),
      ),
    ).toBe(150 * 60_000)
    expect(
      antigravityLimit(
        error(
          "All 2 account(s) rate-limited for claude. Quota resets in 12m 5s. Add more accounts with `opencode auth login` or wait and retry.",
        ),
      ),
    ).toBe(12 * 60_000 + 5_000)
    for (const [wait, ms] of [
      ["500ms", 500],
      ["45s", 45_000],
      ["2h", 7_200_000],
    ] as const)
      expect(
        antigravityLimit(
          error(
            `All 1 account(s) rate-limited for gemini. Quota resets in ${wait}. Add more accounts.`,
          ),
        ),
      ).toBe(ms)
    expect(
      antigravityLimit(
        error(
          "Quota protection: All 1 account(s) are over 90% usage for gemini. Quota resets in unknown. Add more accounts.",
        ),
      ),
    ).toBeUndefined()
  })
  test("anything else is not one", () => {
    for (const message of [
      "socket hang up",
      "No Antigravity accounts available. Run `opencode auth login`.",
      "Your credit balance is too low to access the Anthropic API.",
    ])
      expect(antigravityLimit(error(message))).toBeNull()
  })
})
