import { describe, expect, test } from "bun:test"
import {
  format,
  statsDays,
  summarize,
  type Lane,
  type StatsModel,
} from "./core"

const MAIN: Lane = {
  provider: "anthropic-credit-main",
  label: "Main",
  amount: 200,
  grantedOn: "2026-10-09",
  expiresOn: "2026-10-13",
}
const model = (providerID: string, id: string, cost: number): StatsModel => ({
  model: { providerID, id },
  cost,
})
// Noon on the second day of a four-day grant.
const NOW = new Date(2026, 9, 10, 12, 0, 0)

describe("statsDays", () => {
  test("starts from the grant day's midnight", () => {
    expect(statsDays("2026-10-09", new Date(2026, 9, 9, 15))).toBe(1)
    expect(statsDays("2026-10-09", new Date(2026, 9, 10, 1))).toBe(2)
    expect(statsDays("2026-10-09", new Date(2026, 9, 13, 23))).toBe(5)
  })
  test("never goes below one day", () => {
    expect(statsDays("2026-10-20", new Date(2026, 9, 9))).toBe(1)
  })
})

describe("summarize", () => {
  const models = [
    model("anthropic-credit-main", "claude-sonnet-5-5", 30),
    model("anthropic-credit-main", "claude-opus-5-5", 20),
    model("anthropic-credit-sub", "claude-sonnet-5-5", 99),
    model("anthropic", "claude-opus-5-5", 500),
  ]
  test("counts only the lane's own provider", () => {
    const s = summarize(MAIN, models, NOW)
    expect(s.spent).toBe(50)
    expect(s.remaining).toBe(150)
    expect(s.percentLeft).toBe(75)
    expect(s.byModel.map((m) => m.id)).toEqual([
      "claude-sonnet-5-5",
      "claude-opus-5-5",
    ])
  })
  test("derives the pace and what would expire unused", () => {
    const s = summarize(MAIN, models, NOW)
    expect(s.elapsedDays).toBeCloseTo(1.5, 5)
    expect(s.daysLeft).toBeCloseTo(2.5, 5)
    expect(s.pacePerDay).toBeCloseTo(50 / 1.5, 5)
    expect(s.neededPerDay).toBeCloseTo(150 / 2.5, 5)
    expect(s.unusedAtPace).toBeCloseTo(150 - (50 / 1.5) * 2.5, 5)
  })
  test("a pace that would exhaust the grant leaves nothing unused", () => {
    const s = summarize(MAIN, [model("anthropic-credit-main", "x", 190)], NOW)
    expect(s.unusedAtPace).toBe(0)
  })
  test("overspend never reports negative needs", () => {
    const s = summarize(MAIN, [model("anthropic-credit-main", "x", 250)], NOW)
    expect(s.remaining).toBe(-50)
    expect(s.neededPerDay).toBe(0)
  })
  test("a lane past its expiry is reported as expired", () => {
    const s = summarize(MAIN, models, new Date(2026, 9, 14))
    expect(s.expired).toBe(true)
    expect(s.neededPerDay).toBe(0)
  })
  test("a very young grant does not blow up the pace", () => {
    const s = summarize(
      MAIN,
      [model("anthropic-credit-main", "x", 10)],
      new Date(2026, 9, 9, 1),
    )
    expect(s.pacePerDay).toBe(20)
  })
})

describe("format", () => {
  test("shows each lane and the caveats", () => {
    const text = format([
      summarize(
        MAIN,
        [model("anthropic-credit-main", "claude-sonnet-5-5", 50)],
        NOW,
      ),
    ])
    expect(text).toContain(
      "Main (anthropic-credit-main): 2026-10-09 -> 2026-10-13",
    )
    expect(text).toContain("$50.00 of $200.00")
    expect(text).toContain("$150.00 left (75%)")
    expect(text).toContain("claude-sonnet-5-5 $50.00")
    expect(text).toContain("about 3%")
  })
  test("an expired lane asks for the new grant instead of a pace", () => {
    const text = format([summarize(MAIN, [], new Date(2026, 9, 14))])
    expect(text).toContain("expired")
    expect(text).not.toContain("per day")
  })
})
