import { describe, expect, test } from "bun:test"
import {
  collect,
  paceWindow,
  recordCheckpoint,
  recordGrant,
  resolveLane,
  type Config,
  type Sources,
} from "./collect"
import type { LaneState, StatsModel } from "./core"
import type { HermesUsage } from "./hermes"
import type { State } from "./state"

const MAIN = "anthropic-credit-main"
const SUB = "anthropic-credit-sub"
const CONFIG: Config = {
  lanes: [
    { provider: MAIN, label: "Main", amount: 200, renewalDay: 13 },
    { provider: SUB, label: "Sub", amount: 200, renewalDay: 29 },
  ],
  hermes: { root: "/fixture", order: [SUB, MAIN] },
}
const AT = new Date(2026, 9, 12, 15, 50)
const NOW = new Date(2026, 9, 12, 21, 50)
const LATER = new Date(2026, 9, 13, 9)

const fixture = (
  lanes: Record<string, LaneState>,
  options: {
    // Cost per provider for `stats --days N`.
    stats?: (days: number) => Record<string, number>
    hermes?: HermesUsage | undefined
    // The wall clock, read again after the stats runs.
    clock?: () => Date
    // Another writer's change, committed just before the first update takes
    // the lock.
    meanwhile?: (state: State) => void
  } = {},
) => {
  let meanwhile = options.meanwhile
  const env = {
    state: structuredClone({ version: 1, revision: 0, lanes }) as State,
    saves: 0,
    statsCalls: [] as number[],
  }
  const src: Sources = {
    clock: options.clock ?? (() => NOW),
    stats: async (days) => {
      env.statsCalls.push(days)
      return Object.entries(options.stats?.(days) ?? {}).map(
        ([providerID, cost]): StatsModel => ({
          model: { providerID, id: "claude-opus-5-5" },
          cost,
        }),
      )
    },
    hermes: async () => ("hermes" in options ? options.hermes : {}),
    load: () => structuredClone(env.state),
    update: async (fn) => {
      if (meanwhile) {
        meanwhile(env.state)
        env.state.revision++
        meanwhile = undefined
      }
      const state = structuredClone(env.state)
      const before = JSON.stringify(state)
      const result = await fn(state)
      if (JSON.stringify(state) !== before) {
        env.saves++
        state.revision++
        env.state = state
      }
      return result
    },
  }
  return { env, src }
}

// The Console reading this fix started from.
const CONSOLE: Record<string, LaneState> = {
  [MAIN]: {
    grants: [
      { amount: 200, granted: "2026-10-09", expires: "2026-10-13", source: "console" },
      { amount: 200, granted: "2026-10-10", expires: "2026-11-13", source: "console" },
    ],
    checkpoint: {
      at: AT.toISOString(),
      balance: 135.79,
      source: "console",
      opencodeFrom: "2026-10-12",
      opencodeBase: 40,
      hermes: { a: 10 },
    },
  },
  [SUB]: {
    grants: [
      { amount: 200, granted: "2026-10-09", expires: "2026-10-29", source: "console" },
    ],
    checkpoint: {
      at: AT.toISOString(),
      balance: 20,
      source: "console",
      opencodeFrom: "2026-10-12",
      opencodeBase: 0,
      hermes: { a: 10 },
    },
  },
}

describe("collect", () => {
  test("counts OpenCode since the checkpoint, and Hermes on Sub first, then Main", async () => {
    const { env, src } = fixture(CONSOLE, {
      stats: () => ({ [MAIN]: 45, [SUB]: 5 }),
      // Hermes spent $25 since: a grew by 20, b is new.
      hermes: { a: 30, b: 5 },
    })
    const [main, sub] = await collect(NOW, CONFIG, src)
    expect(sub.spent).toEqual({ opencode: 5, hermes: 15 })
    expect(sub.remaining).toBeCloseTo(0, 5)
    expect(main.spent).toEqual({ opencode: 5, hermes: 10 })
    expect(main.remaining).toBeCloseTo(120.79, 5)
    expect(main.hermesCounted).toBe(true)
    // Both checkpoints are today: one run serves both, one more for the pace.
    expect(env.statsCalls).toEqual([1, 7])
    // OpenCode's $45 over six full days and today's 21h50m, and Hermes' $10
    // since the checkpoint counted over a day.
    expect(main.pacePerDay).toBeCloseTo(45 / paceWindow(NOW) + 10, 5)
    expect(paceWindow(NOW)).toBeCloseTo(6 + (21 * 60 + 50) / 1440, 5)
    expect(env.saves).toBe(0)
  })
  test("Hermes is not counted when it cannot be read", async () => {
    const { src } = fixture(CONSOLE, { hermes: undefined })
    const [main, sub] = await collect(NOW, CONFIG, src)
    expect(main.hermesCounted).toBe(false)
    expect(sub.spent.hermes).toBe(0)
  })
  test("a lane without a checkpoint counts its cycle's grant as full from the cycle start", async () => {
    const { env, src } = fixture({}, { stats: () => ({ [MAIN]: 50 }) })
    const [main] = await collect(NOW, CONFIG, src)
    expect(main.checkpoint.source).toBe("none")
    expect(main.remaining).toBe(150)
    expect(main.hermesCounted).toBe(false)
    expect(env.statsCalls).toContain(30)
  })
  test("spend well beyond every known grant records the grant that must have arrived", async () => {
    const { env, src } = fixture(CONSOLE, {
      stats: () => ({ [SUB]: 60 }),
      hermes: { a: 10 },
    })
    const [, sub] = await collect(NOW, CONFIG, src)
    expect(env.state.lanes[SUB].grants.at(-1)).toEqual({
      amount: 200,
      granted: NOW.toISOString(),
      expires: "2026-11-29",
      source: "inferred",
    })
    expect(sub.remaining).toBeCloseTo(160, 5)
    // Inferred once: the next run finds it.
    await collect(NOW, CONFIG, src)
    expect(env.state.lanes[SUB].grants).toHaveLength(2)
  })
  test("a small overrun is taken as cost accounting running ahead, not a grant", async () => {
    const { env, src } = fixture(CONSOLE, { stats: () => ({ [SUB]: 24 }) })
    const [, sub] = await collect(NOW, CONFIG, src)
    expect(sub.remaining).toBeCloseTo(-4, 5)
    expect(env.saves).toBe(0)
  })
  const expiring = (options: { hermes?: HermesUsage; clock?: () => Date } = {}) =>
    fixture(CONSOLE, {
      stats: (days) => (days === 1 ? { [MAIN]: 3 } : { [MAIN]: 50 }),
      hermes: { a: 10, c: 1 },
      clock: () => LATER,
      ...options,
    })
  test("a grant expiring since the checkpoint carries every lane's balance forward", async () => {
    const { env, src } = expiring()
    const [main, sub] = await collect(LATER, CONFIG, src)
    expect(env.state.lanes[MAIN].checkpoint).toEqual({
      at: LATER.toISOString(),
      balance: 125.79,
      source: "rolled",
      // The same two-day run the $125.79 came from.
      opencodeFrom: "2026-10-12",
      opencodeBase: 50,
      hermes: { a: 10, c: 1 },
    })
    // Sub took Hermes' $1 and is re-based on the same baseline.
    expect(env.state.lanes[SUB].checkpoint).toMatchObject({
      balance: 19,
      source: "rolled",
      opencodeFrom: "2026-10-12",
      opencodeBase: 0,
      hermes: { a: 10, c: 1 },
    })
    expect(env.state.lanes[MAIN].grants.map((g) => g.expires)).toEqual(["2026-11-13"])
    expect(main.remaining).toBeCloseTo(125.79, 5)
    expect(main.grants.map((g) => g.expired)).toEqual([false])
    expect(sub.remaining).toBeCloseTo(19, 5)
    expect(env.saves).toBe(1)
  })
  test("nothing is carried forward while Hermes cannot be read", async () => {
    const { env, src } = expiring({ hermes: undefined })
    const [main] = await collect(LATER, CONFIG, src)
    expect(env.saves).toBe(0)
    expect(main.hermesCounted).toBe(false)
  })
  test("nothing is written over a write made after the reading began", async () => {
    // Sub's estimate is far below zero, which would infer a grant.
    const { env, src } = fixture(CONSOLE, {
      stats: () => ({ [SUB]: 60 }),
      meanwhile: (state) => {
        state.lanes[SUB].checkpoint!.balance = 80
      },
    })
    await collect(NOW, CONFIG, src)
    expect(env.saves).toBe(0)
    expect(env.state.lanes[SUB].checkpoint?.balance).toBe(80)
    expect(env.state.lanes[SUB].grants).toHaveLength(1)
  })
  test("nothing is written from a reading that crossed midnight", async () => {
    const { env, src } = expiring({ clock: () => new Date(2026, 9, 14, 0, 0, 1) })
    await collect(LATER, CONFIG, src)
    expect(env.saves).toBe(0)
  })
})

describe("recording", () => {
  test("a Console balance becomes the lane's checkpoint, the other lane's estimate is carried forward", async () => {
    const { env, src } = fixture(CONSOLE, {
      stats: () => ({ [MAIN]: 12 }),
      hermes: { a: 40 },
    })
    await recordCheckpoint(MAIN, 99.5, "console", CONFIG, src)
    expect(env.state.lanes[MAIN].checkpoint).toEqual({
      at: NOW.toISOString(),
      balance: 99.5,
      source: "console",
      opencodeFrom: "2026-10-12",
      opencodeBase: 12,
      hermes: { a: 40 },
    })
    // Hermes' $30 since: Sub's $20 first.
    expect(env.state.lanes[SUB].checkpoint).toEqual({
      at: NOW.toISOString(),
      balance: 0,
      source: "rolled",
      opencodeFrom: "2026-10-12",
      opencodeBase: 0,
      hermes: { a: 40 },
    })
  })
  test("a checkpoint on Sub keeps what Hermes had already spent on Main", async () => {
    const lanes = structuredClone(CONSOLE)
    lanes[MAIN].checkpoint = { ...lanes[MAIN].checkpoint!, balance: 100, opencodeBase: 0 }
    lanes[SUB].checkpoint = { ...lanes[SUB].checkpoint!, balance: 0 }
    const { src } = fixture(lanes, { hermes: { a: 40 } })
    expect((await collect(NOW, CONFIG, src))[0].remaining).toBeCloseTo(70, 5)
    await recordCheckpoint(SUB, 0, "empty", CONFIG, src)
    expect((await collect(NOW, CONFIG, src))[0].remaining).toBeCloseTo(70, 5)
  })
  test("a reading that crosses midnight is taken again", async () => {
    let reads = 0
    const { env, src } = fixture(CONSOLE, {
      clock: () => (reads++ === 0 ? new Date(2026, 9, 12, 23, 59, 59) : LATER),
    })
    await recordCheckpoint(MAIN, 50, "console", CONFIG, src)
    expect(env.state.lanes[MAIN].checkpoint?.at).toBe(LATER.toISOString())
    expect(reads).toBeGreaterThan(2)
  })
  test("a reading overtaken by another write is taken again, on top of it", async () => {
    const { env, src } = fixture(CONSOLE, {
      meanwhile: (state) => {
        state.lanes[SUB].checkpoint!.balance = 80
      },
    })
    await recordCheckpoint(MAIN, 50, "console", CONFIG, src)
    expect(env.saves).toBe(1)
    expect(env.state.lanes[MAIN].checkpoint).toMatchObject({ balance: 50, source: "console" })
    expect(env.state.lanes[SUB].checkpoint).toMatchObject({ balance: 80, source: "rolled" })
  })
  test("a carried estimate below zero is carried as zero, so it cannot infer a grant later", async () => {
    const lanes = structuredClone(CONSOLE)
    lanes[MAIN].checkpoint = { ...lanes[MAIN].checkpoint!, balance: 100 }
    // $109 spent since: -$9, within the 10% tolerance of that spend.
    const { env, src } = fixture(lanes, { stats: () => ({ [MAIN]: 149 }) })
    expect((await collect(NOW, CONFIG, src))[0].remaining).toBeCloseTo(-9, 5)
    await recordCheckpoint(SUB, 0, "empty", CONFIG, src)
    expect(env.state.lanes[MAIN].checkpoint?.balance).toBe(0)
    const saves = env.saves
    expect((await collect(NOW, CONFIG, src))[0].remaining).toBe(0)
    expect(env.saves).toBe(saves)
  })
  test("a checkpoint is refused while Hermes cannot be read", async () => {
    const { env, src } = fixture(CONSOLE, { hermes: undefined })
    await expect(recordCheckpoint(MAIN, 50, "console", CONFIG, src)).rejects.toThrow(
      "Hermes usage could not be read",
    )
    expect(env.saves).toBe(0)
  })
  test("an empty balance drops live inferred grants and expired ones", async () => {
    const lanes = structuredClone(CONSOLE)
    lanes[SUB].grants.push(
      { amount: 200, granted: NOW.toISOString(), expires: "2026-11-29", source: "inferred" },
      { amount: 200, granted: "2026-09-01", expires: "2026-10-01", source: "console" },
    )
    const { env, src } = fixture(lanes)
    await recordCheckpoint(SUB, 0, "empty", CONFIG, src)
    expect(env.state.lanes[SUB].grants.map((g) => g.expires)).toEqual(["2026-10-29"])
    expect(env.state.lanes[SUB].checkpoint?.source).toBe("empty")
  })
  test("a listed grant replaces any grant expiring the same day, and 0 removes it", async () => {
    const lanes = structuredClone(CONSOLE)
    lanes[SUB].grants.push({
      amount: 200,
      granted: NOW.toISOString(),
      expires: "2026-11-29",
      source: "inferred",
    })
    const { env, src } = fixture(lanes)
    await recordGrant(SUB, 200, "2026-11-29", "2026-10-27", CONFIG, src)
    expect(env.state.lanes[SUB].grants.at(-1)).toEqual({
      amount: 200,
      granted: "2026-10-27",
      expires: "2026-11-29",
      source: "console",
    })
    await recordGrant(SUB, 0, "2026-11-29", "2026-10-27", CONFIG, src)
    expect(env.state.lanes[SUB].grants).toHaveLength(1)
  })
  test("lanes resolve by label or provider, and an unknown one is refused", () => {
    expect(resolveLane(CONFIG, "main").provider).toBe(MAIN)
    expect(resolveLane(CONFIG, SUB).label).toBe("Sub")
    expect(() => resolveLane(CONFIG, "other")).toThrow("unknown lane")
  })
})
