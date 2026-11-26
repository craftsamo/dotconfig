import { describe, expect, test } from "bun:test"
import { antigravityRefusal, type RefusalInput } from "./refusal"

describe("Antigravity refusals", () => {
  test("leaves the plugin's quota protection to fallback-steps", () => {
    expect(
      antigravityRefusal({
        status: 429,
        message: "Quota protection: All 1 account(s) are over 90% usage for gemini. Quota resets in 2h 30m.",
      }),
    ).toBeNull()
    expect(
      antigravityRefusal({
        status: 429,
        message: "All 1 account(s) rate-limited for claude.",
      }),
    ).toBeNull()
  })

  test.each([
    {
      status: 403,
      message: "This service has been disabled in this account for violation of Terms of Service",
    },
    { message: "Forbidden", body: '{"reason":"TOS_VIOLATION"}' },
  ])("recognizes ToS suspensions: %j", (error) => {
    expect(antigravityRefusal(error)).toBe("tos")
  })

  test.each([
    { status: 403, message: "Forbidden" },
    { message: "Forbidden", body: '{"reason":"SUBSCRIPTION_REQUIRED"}' },
    { message: "PERMISSION_DENIED" },
    {
      status: 429,
      message: "Resource has been exhausted (e.g. check quota).",
      body: '{"error":{"code":429,"message":"Resource has been exhausted (e.g. check quota).","status":"RESOURCE_EXHAUSTED"}}',
    },
    { message: "RESOURCE_EXHAUSTED" },
  ])("recognizes refusals without quota details: %j", (error) => {
    expect(antigravityRefusal(error)).toBe("refused")
  })

  test.each(["quota_metric", "quotaMetric", "RetryInfo", "retryDelay"])(
    "preserves quota retries with %s",
    (detail) => {
      const error: RefusalInput = {
        status: 429,
        message: "RESOURCE_EXHAUSTED",
        body: JSON.stringify({ [detail]: "quota detail" }),
      }
      expect(antigravityRefusal(error)).toBeNull()
    },
  )

  test("leaves other errors alone", () => {
    expect(antigravityRefusal({ status: 500, message: "Internal error" })).toBeNull()
  })
})
