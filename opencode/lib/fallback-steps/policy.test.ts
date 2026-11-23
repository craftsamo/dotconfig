import { describe, expect, test } from "bun:test"
import { QUOTA_MAX_AGE_MS, freshState, type QuotaProof } from "./policy"

const NOW = 1_710_000_000_000
const quota = (state: QuotaProof["state"]): QuotaProof => ({
  state,
  observedAt: NOW,
})

describe("freshState", () => {
  test("stale/future/reset data is unknown, but fresh 0% needs no reset proof", () => {
    expect(freshState(quota("exhausted"), NOW)).toBe("exhausted")
    expect(
      freshState(
        { ...quota("available"), observedAt: NOW - QUOTA_MAX_AGE_MS },
        NOW,
      ),
    ).toBe("available")
    for (const q of [
      { ...quota("available"), observedAt: NOW - QUOTA_MAX_AGE_MS - 1 },
      { ...quota("available"), observedAt: NOW + 1 },
      { ...quota("available"), observedAt: NaN },
      { ...quota("exhausted"), resetAt: NOW },
      quota("unknown"),
    ])
      expect(freshState(q, NOW)).toBeUndefined()
  })
})
