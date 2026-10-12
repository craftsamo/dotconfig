import { describe, expect, test } from "bun:test"
import {
  allocateHermes,
  checkpointFor,
  cycleOf,
  format,
  grantsFor,
  ledger,
  nextGrantAt,
  statsDays,
  summarize,
  ymd,
  type Checkpoint,
  type Grant,
  type Lane,
} from "./core"

const MAIN: Lane = {
  provider: "anthropic-credit-main",
  label: "Main",
  amount: 200,
  renewalDay: 13,
}
const grant = (
  expires: string,
  granted: string,
  amount = 200,
  source: Grant["source"] = "console",
): Grant => ({ amount, granted, expires, source })
// Main as the Console listed it: a first grant ending this cycle, and the next
// cycle's grant that arrived early.
const MAIN_GRANTS = [grant("2026-10-13", "2026-10-09"), grant("2026-11-13", "2026-10-10")]
const AT = new Date(2026, 9, 12, 15, 50)
const NOW = new Date(2026, 9, 12, 21, 50)
const span = (day: number, now: Date) => {
  const { start, end } = cycleOf(day, now)
  return `${ymd(start)} ${ymd(end)}`
}
const lefts = (l: ReturnType<typeof ledger>) =>
  l.grants.map((g) => [g.expires, Number(g.left.toFixed(2))])

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

describe("statsDays", () => {
  test("counts days from the start's local midnight, today included", () => {
    const from = new Date(2026, 9, 9, 15)
    expect(statsDays(from, new Date(2026, 9, 9, 16))).toBe(1)
    expect(statsDays(from, new Date(2026, 9, 10, 1))).toBe(2)
    expect(statsDays(from, new Date(2026, 9, 13, 23))).toBe(5)
  })
  test("never goes below one day", () => {
    expect(statsDays(new Date(2026, 9, 20), new Date(2026, 9, 9))).toBe(1)
  })
})

describe("grantsFor and checkpointFor", () => {
  test("projects the current cycle's grant only when none expires at its end", () => {
    const projected = grantsFor(MAIN, { grants: [] }, NOW)
    expect(projected).toEqual([
      grant("2026-10-13", "2026-09-13", 200, "projected"),
    ])
    expect(grantsFor(MAIN, { grants: MAIN_GRANTS }, NOW)).toBe(MAIN_GRANTS)
    // After the renewal, the 11-13 grant covers the new cycle.
    expect(
      grantsFor(MAIN, { grants: MAIN_GRANTS }, new Date(2026, 9, 20)),
    ).toBe(MAIN_GRANTS)
  })
  test("without a checkpoint, the cycle's grants count as full at its start", () => {
    const grants = grantsFor(MAIN, { grants: [] }, NOW)
    expect(checkpointFor(MAIN, { grants: [] }, grants, NOW)).toEqual({
      at: new Date(2026, 8, 13).toISOString(),
      balance: 200,
      source: "none",
      opencodeFrom: "2026-09-13",
      opencodeBase: 0,
    })
  })
})

describe("ledger", () => {
  test("puts the checkpoint's balance on the latest expiry and spends the nearest first", () => {
    const l = ledger(MAIN_GRANTS, AT, 135.79, 10, NOW)
    expect(lefts(l)).toEqual([
      ["2026-10-13", 0],
      ["2026-11-13", 125.79],
    ])
    expect(l.remaining).toBeCloseTo(125.79, 5)
  })
  test("spend after the checkpoint is charged to a grant that has expired since, the rest lapses", () => {
    const l = ledger(MAIN_GRANTS, AT, 250, 30, new Date(2026, 9, 14))
    expect(lefts(l)).toEqual([
      ["2026-10-13", 20],
      ["2026-11-13", 200],
    ])
    expect(l.lapsed).toBe(20)
    expect(l.remaining).toBe(200)
    expect(l.available).toBe(220)
  })
  test("a grant arriving after the checkpoint is full, and a debt is repaid first", () => {
    const grants = [grant("2026-10-29", "2026-10-09"), grant("2026-11-29", "2026-10-29", 200, "projected")]
    const at = new Date(2026, 9, 12)
    expect(ledger(grants, at, -0.06, 0, new Date(2026, 9, 20)).remaining).toBe(-0.06)
    const later = ledger(grants, at, -0.06, 10, new Date(2026, 9, 30))
    expect(later.remaining).toBeCloseTo(189.94, 5)
  })
  test("spend beyond everything known goes below zero", () => {
    const l = ledger(MAIN_GRANTS, AT, 20, 50, NOW)
    expect(l.overspent).toBe(30)
    expect(l.remaining).toBe(-30)
  })
  test("a balance above the known grants is kept apart and spent last", () => {
    const l = ledger([grant("2026-11-13", "2026-10-10")], AT, 250, 220, NOW)
    expect(l.unattributed).toBe(30)
    expect(l.remaining).toBe(30)
  })
  test("ignores grants that expired before the checkpoint or have not arrived", () => {
    const grants = [
      grant("2026-10-01", "2026-09-01"),
      ...MAIN_GRANTS,
      grant("2026-12-13", "2026-11-13", 200, "projected"),
    ]
    expect(ledger(grants, AT, 135.79, 0, NOW).grants.map((g) => g.expires)).toEqual([
      "2026-10-13",
      "2026-11-13",
    ])
  })
})

describe("allocateHermes", () => {
  const ORDER = ["sub", "main"]
  test("the first lane takes what fits, the rest moves on", () => {
    expect(allocateHermes(ORDER, { sub: 30, main: 30 }, { sub: 10, main: 100 })).toEqual({
      sub: 10,
      main: 20,
    })
  })
  test("the next lane takes no more than Hermes spent since its own checkpoint", () => {
    expect(allocateHermes(ORDER, { sub: 30, main: 5 }, { sub: 0, main: 100 })).toEqual({
      sub: 0,
      main: 5,
    })
  })
  test("a lane without a full room keeps what does not fit nowhere, and absent lanes are skipped", () => {
    expect(allocateHermes(ORDER, { main: 30 }, { main: 12 })).toEqual({ main: 12 })
    expect(allocateHermes(ORDER, { sub: 30, main: 30 }, { sub: -5, main: 0 })).toEqual({
      sub: 0,
      main: 0,
    })
  })
})

describe("summarize", () => {
  const checkpoint: Checkpoint = {
    at: AT.toISOString(),
    balance: 135.79,
    source: "console",
    opencodeFrom: "2026-10-12",
    opencodeBase: 0,
  }
  const run = (opencode: number, hermes: number, now = NOW, perDay = 0) =>
    summarize(
      MAIN,
      {
        grants: MAIN_GRANTS,
        checkpoint,
        opencode,
        opencodePerDay: perDay,
        hermes,
        hermesCounted: true,
        byModel: [],
      },
      now,
    )
  test("reports against the grants that still hold something", () => {
    const s = run(4, 1.79)
    expect(s.remaining).toBeCloseTo(130, 5)
    expect(s.total).toBe(200)
    expect(s.percentLeft).toBeCloseTo(65, 5)
    expect(ymd(s.resetAt)).toBe("2026-11-13")
    expect(ymd(s.nextExpiry!)).toBe("2026-11-13")
    expect(s.spent).toEqual({ opencode: 4, hermes: 1.79 })
  })
  test("pace, need and what would expire unused follow the nearest holding grant", () => {
    const now = new Date(2026, 9, 13, 15, 50)
    const s = run(1, 0, now, 1)
    expect(s.elapsedDays).toBeCloseTo(1, 5)
    expect(s.pacePerDay).toBeCloseTo(1, 5)
    const days = (new Date(2026, 10, 13).getTime() - now.getTime()) / 86_400_000
    expect(s.neededPerDay).toBeCloseTo(134.79 / days, 5)
    expect(s.unusedAtPace).toBeCloseTo(134.79 - days, 5)
    // A pace that uses it all loses nothing.
    expect(run(10, 0, now, 10).unusedAtPace).toBe(0)
  })
  test("the pace is OpenCode's recent rate plus Hermes' since the checkpoint, never over less than a day", () => {
    // Six hours after the checkpoint: Hermes' $3 counts as $3 a day.
    expect(run(0, 3, NOW, 20).pacePerDay).toBeCloseTo(23, 5)
    expect(run(0, 3, new Date(2026, 9, 14, 15, 50), 20).pacePerDay).toBeCloseTo(21.5, 5)
  })
  test("with nothing left the reset is the next renewal, and the total is what is live", () => {
    const s = run(500, 0)
    expect(s.remaining).toBeCloseTo(-364.21, 5)
    expect(s.total).toBe(400)
    expect(s.neededPerDay).toBe(0)
    expect(ymd(s.resetAt)).toBe("2026-10-13")
  })
  test("the next grant expected skips a cycle whose grant already arrived", () => {
    expect(ymd(nextGrantAt(MAIN, MAIN_GRANTS, NOW))).toBe("2026-11-13")
    expect(ymd(nextGrantAt(MAIN, [], NOW))).toBe("2026-10-13")
  })
})

describe("format", () => {
  test("shows each grant, the basis and the caveats", () => {
    const s = summarize(
      MAIN,
      {
        grants: MAIN_GRANTS,
        checkpoint: {
          at: AT.toISOString(),
          balance: 135.79,
          source: "console",
          opencodeFrom: "2026-10-12",
          opencodeBase: 0,
        },
        opencode: 5.79,
        opencodePerDay: 30,
        hermes: 0,
        hermesCounted: false,
        byModel: [{ id: "claude-sonnet-5-5", cost: 5.79 }],
      },
      NOW,
    )
    const text = format([s], ["anthropic-credit-sub", "anthropic-credit-main"])
    expect(text).toContain(
      "Main (anthropic-credit-main): $130.00 left of $200.00 (65%), renews on day 13",
    )
    expect(text).toContain("grant     $0.00 of $200.00, expires 2026-10-13 (console)")
    expect(text).toContain("grant     $130.00 of $200.00, expires 2026-11-13 (console)")
    expect(text).toContain("next      $200.00 expected 2026-11-13")
    expect(text).toContain("basis     Console balance $135.79 at 2026-10-12 15:50")
    expect(text).toContain("since     OpenCode $5.79, Hermes not counted")
    expect(text).toContain("pace      $30.00/day lately, $4.18/day needed by 2026-11-13")
    expect(text).toContain("claude-sonnet-5-5 $5.79 (OpenCode, last 7 days)")
    expect(text).toContain("which draws Main.")
  })
})
