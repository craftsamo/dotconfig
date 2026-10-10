import { describe, expect, test } from "bun:test"
import {
  cycleOf,
  format,
  statsDays,
  summarize,
  trackedFrom,
  ymd,
  type Lane,
  type StatsModel,
} from "./core"

const MAIN: Lane = {
  provider: "anthropic-credit-main",
  label: "Main",
  amount: 200,
  renewalDay: 13,
  since: "2026-10-09",
}
const model = (providerID: string, id: string, cost: number): StatsModel => ({
  model: { providerID, id },
  cost,
})
// Noon on the second day of a four-day first cycle.
const NOW = new Date(2026, 9, 10, 12, 0, 0)
const span = (day: number, now: Date) => {
  const { start, end } = cycleOf(day, now)
  return `${ymd(start)} ${ymd(end)}`
}

describe("cycleOf", () => {
  test("runs from the latest renewal day to the next", () => {
    expect(span(13, new Date(2026, 9, 10))).toBe("2026-09-13 2026-10-13")
    expect(span(13, new Date(2026, 9, 20))).toBe("2026-10-13 2026-11-13")
  })
  test("a renewal day starts the new cycle at its local midnight", () => {
    expect(span(13, new Date(2026, 9, 13, 0, 0, 0))).toBe(
      "2026-10-13 2026-11-13",
    )
    expect(span(13, new Date(2026, 9, 12, 23, 59, 59))).toBe(
      "2026-09-13 2026-10-13",
    )
  })
  test("crosses year boundaries both ways", () => {
    expect(span(20, new Date(2026, 11, 25))).toBe("2026-12-20 2027-01-20")
    expect(span(20, new Date(2027, 0, 5))).toBe("2026-12-20 2027-01-20")
  })
  test("a day a short month lacks falls on its last day", () => {
    expect(span(31, new Date(2026, 1, 10))).toBe("2026-01-31 2026-02-28")
    expect(span(31, new Date(2026, 2, 5))).toBe("2026-02-28 2026-03-31")
    expect(span(30, new Date(2028, 1, 29, 12))).toBe("2028-02-29 2028-03-30")
  })
})

describe("trackedFrom and statsDays", () => {
  test("a later `since` starts a first cycle part way, an older one is ignored", () => {
    expect(ymd(trackedFrom(MAIN, NOW))).toBe("2026-10-09")
    expect(ymd(trackedFrom(MAIN, new Date(2026, 10, 1)))).toBe("2026-10-13")
    expect(ymd(trackedFrom({ ...MAIN, since: undefined }, NOW))).toBe(
      "2026-09-13",
    )
  })
  test("counts days from local midnight, today included", () => {
    const from = new Date(2026, 9, 9)
    expect(statsDays(from, new Date(2026, 9, 9, 15))).toBe(1)
    expect(statsDays(from, new Date(2026, 9, 10, 1))).toBe(2)
    expect(statsDays(from, new Date(2026, 9, 13, 23))).toBe(5)
  })
  test("never goes below one day", () => {
    expect(statsDays(new Date(2026, 9, 20), new Date(2026, 9, 9))).toBe(1)
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
    expect(ymd(s.cycleEnd)).toBe("2026-10-13")
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
  test("after the renewal day the next cycle starts on its own", () => {
    const s = summarize(MAIN, [], new Date(2026, 9, 14))
    expect(`${ymd(s.cycleStart)} ${ymd(s.cycleEnd)}`).toBe(
      "2026-10-13 2026-11-13",
    )
    expect(ymd(s.trackedFrom)).toBe("2026-10-13")
    expect(s.daysLeft).toBeGreaterThan(29)
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
      "Main (anthropic-credit-main): 2026-09-13 -> 2026-10-13, renews on day 13",
    )
    expect(text).toContain("$50.00 of $200.00")
    expect(text).toContain("$150.00 left (75%)")
    expect(text).toContain("claude-sonnet-5-5 $50.00")
    expect(text).toContain("about 3%")
  })
})
