import { describe, expect, test } from "bun:test"
import type { Lane, LaneState } from "../credit-lanes/core"
import {
  EMPTY_PROBE_MS,
  EmptyLanes,
  emptyUntil,
  TRY_SETTLED_MS,
} from "./empty-lanes"

const LANE: Lane = {
  provider: "anthropic-credit-main",
  label: "Main",
  amount: 200,
  renewalDay: 13,
}
const AT = new Date(2026, 9, 20, 12).getTime()
const RENEWAL = new Date(2026, 10, 13).getTime()
const state = (
  balance: number,
  source: "empty" | "console" | "rolled" = "empty",
  grants: LaneState["grants"] = [],
): LaneState => ({
  grants,
  checkpoint: {
    at: new Date(AT).toISOString(),
    balance,
    source,
    opencodeFrom: "2026-10-20",
    opencodeBase: 0,
  },
})

describe("emptyUntil", () => {
  test("a $0 checkpoint holds nothing until the next renewal, from any source", () => {
    for (const source of ["empty", "console", "rolled"] as const)
      expect(emptyUntil(LANE, state(0, source), AT + 1)).toBe(RENEWAL)
    expect(emptyUntil(LANE, state(0.004), AT + 1)).toBe(RENEWAL)
    expect(emptyUntil(LANE, state(0), RENEWAL)).toBeUndefined()
  })
  test("a grant after the checkpoint ends it at the grant", () => {
    const granted = new Date(AT + 3_600_000).toISOString()
    const ls = state(0, "empty", [
      { amount: 50, granted, expires: "2026-12-13", source: "console" },
      // Granted before the checkpoint: it is in the $0 already.
      {
        amount: 200,
        granted: "2026-10-13",
        expires: "2026-11-13",
        source: "console",
      },
    ])
    expect(emptyUntil(LANE, ls, AT + 60_000)).toBe(AT + 3_600_000)
    expect(emptyUntil(LANE, ls, AT + 3_600_000)).toBeUndefined()
  })
  test("a grant listed by its date alone counts from that whole day", () => {
    const sameDay = state(0, "empty", [
      {
        amount: 50,
        granted: "2026-10-20",
        expires: "2026-12-13",
        source: "console",
      },
    ])
    expect(emptyUntil(LANE, sameDay, AT + 60_000)).toBeUndefined()
    const dayBefore = state(0, "empty", [
      {
        amount: 50,
        granted: "2026-10-19",
        expires: "2026-12-13",
        source: "console",
      },
    ])
    expect(emptyUntil(LANE, dayBefore, AT + 60_000)).toBe(RENEWAL)
  })
  test("a checkpoint on a renewal day holds only to its end", () => {
    const onRenewal = new Date(2026, 10, 13, 9).getTime()
    const ls = {
      grants: [],
      checkpoint: {
        ...state(0).checkpoint!,
        at: new Date(onRenewal).toISOString(),
      },
    }
    expect(emptyUntil(LANE, ls, onRenewal + 60_000)).toBe(
      new Date(2026, 10, 14).getTime(),
    )
  })
  test("a balance, no checkpoint, or one from the future proves nothing", () => {
    expect(emptyUntil(LANE, state(12), AT + 1)).toBeUndefined()
    expect(emptyUntil(LANE, { grants: [] }, AT + 1)).toBeUndefined()
    expect(emptyUntil(LANE, undefined, AT + 1)).toBeUndefined()
    expect(emptyUntil(LANE, state(0), AT - 1)).toBeUndefined()
  })
})

describe("EmptyLanes", () => {
  const book = (ls: LaneState) => ({
    lanes: [LANE],
    state: { [LANE.provider]: ls },
  })
  test("an empty checkpoint counts as the lane's last try", () => {
    const lanes = new EmptyLanes()
    expect(lanes.scan(book(state(0)), AT + 1).skip).toEqual(
      new Set([LANE.provider]),
    )
    const later = lanes.scan(book(state(0)), AT + EMPTY_PROBE_MS)
    expect(later.skip.size).toBe(0)
    expect(later.due).toEqual(new Set([LANE.provider]))
    lanes.tried(LANE.provider, AT + EMPTY_PROBE_MS)
    expect(lanes.scan(book(state(0)), AT + EMPTY_PROBE_MS + 1).skip).toEqual(
      new Set([LANE.provider]),
    )
  })
  test("a try that settles without a newer reading of $0 shows money", () => {
    const lanes = new EmptyLanes()
    const tryAt = AT + EMPTY_PROBE_MS
    lanes.tried(LANE.provider, tryAt)
    const settled = tryAt + TRY_SETTLED_MS
    const none = lanes.scan(book(state(0)), settled)
    expect([none.skip.size, none.due.size]).toEqual([0, 0])
    // The estimate carrying $0 forward later does not undo that.
    const rolled = {
      ...state(0, "rolled"),
      checkpoint: {
        ...state(0, "rolled").checkpoint!,
        at: new Date(settled + 1).toISOString(),
      },
    }
    expect(lanes.scan(book(rolled), settled + 2).skip.size).toBe(0)
    // An empty balance reported after the try does.
    const failed = {
      ...state(0),
      checkpoint: {
        ...state(0).checkpoint!,
        at: new Date(tryAt + 5_000).toISOString(),
      },
    }
    expect(lanes.scan(book(failed), settled).skip).toEqual(
      new Set([LANE.provider]),
    )
  })
  test("a refusal holds the lane a day, whatever the checkpoint then says", () => {
    const lanes = new EmptyLanes()
    const rolled = state(0, "rolled")
    // A $0 carried forward is due at once; a refusal makes it wait a day.
    lanes.tried(LANE.provider, AT + 1)
    lanes.refused(LANE.provider, AT + 1)
    const later = AT + 1 + TRY_SETTLED_MS
    expect(lanes.scan(book(rolled), later).skip).toEqual(
      new Set([LANE.provider]),
    )
    expect(lanes.scan(book(rolled), AT + 1 + EMPTY_PROBE_MS).due).toEqual(
      new Set([LANE.provider]),
    )
    // A refusal without a try (any request) counts the same.
    const other = new EmptyLanes()
    other.refused(LANE.provider, AT + 1)
    expect(other.scan(book(rolled), AT + 2).skip).toEqual(
      new Set([LANE.provider]),
    )
  })
  test("a state it cannot read passes over nothing", () => {
    const lanes = new EmptyLanes()
    const broken: any = {
      lanes: [LANE],
      state: { [LANE.provider]: { checkpoint: 5 } },
    }
    expect(lanes.scan(broken, AT).skip.size).toBe(0)
    expect(lanes.scan({ lanes: "x" } as any, AT).skip.size).toBe(0)
    const noGrants: any = { grants: undefined, checkpoint: state(0).checkpoint }
    expect(lanes.scan(book(noGrants), AT + 1).skip).toEqual(
      new Set([LANE.provider]),
    )
  })
  test("a carried $0 is due at once; a lane holding something is neither", () => {
    const lanes = new EmptyLanes()
    expect(lanes.scan(book(state(0, "rolled")), AT + 1).due).toEqual(
      new Set([LANE.provider]),
    )
    const holding = lanes.scan(book(state(5)), AT + 1)
    expect([holding.skip.size, holding.due.size]).toEqual([0, 0])
    const none = lanes.scan(undefined, AT)
    expect([none.skip.size, none.due.size]).toEqual([0, 0])
  })
})
