import { loadConfig } from "../credit-lanes/collect"
import { cycleOf, when, type Lane, type LaneState } from "../credit-lanes/core"
import { readState } from "../credit-lanes/state"

// What the credit-lane estimate (lib/credit-lanes) knows of each lane: its
// renewal day, and its known grants and latest checkpoint.
export type LaneBook = { lanes: Lane[]; state: Record<string, LaneState> }

export function readLaneBook(): LaneBook | undefined {
  try {
    return { lanes: loadConfig().lanes, state: readState().lanes }
  } catch {
    return undefined
  }
}

// Empty below this, as /credits rounds it.
const EMPTY_USD = 0.005
// A lane known empty is still tried this often: a grant can arrive off its
// schedule (a plan change, a top-up), and only a request tells.
export const EMPTY_PROBE_MS = 24 * 3_600_000

// Until when a lane holds nothing: its checkpoint balance was $0 (an empty
// balance a request reported, a Console reading, or the estimate carried
// forward) and no money can have arrived since. Spend only lowers a balance,
// so this needs no spend figures: money comes with the first known grant
// after the checkpoint, or the next renewal. Undefined when it may hold
// something.
export function emptyUntil(
  lane: Lane,
  ls: LaneState | undefined,
  now: number,
): number | undefined {
  const checkpoint = ls?.checkpoint
  if (!checkpoint || !(checkpoint.balance < EMPTY_USD)) return undefined
  const at = when(checkpoint.at).getTime()
  if (!Number.isFinite(at) || at > now) return undefined
  const funded = Math.min(
    cycleOf(lane.renewalDay, new Date(at)).end.getTime(),
    ...ls!.grants
      .map((g) => when(g.granted).getTime())
      .filter((t) => Number.isFinite(t) && t > at),
  )
  return now < funded ? funded : undefined
}

// The lanes known empty that are passed over now, and those whose daily try
// is due. A lane's last try is the later of one made here and its own empty
// checkpoint (what a failed try records).
export class EmptyLanes {
  private probed = new Map<string, number>()

  scan(
    book: LaneBook | undefined,
    now: number,
  ): { skip: ReadonlySet<string>; due: ReadonlySet<string> } {
    const skip = new Set<string>()
    const due = new Set<string>()
    for (const lane of book?.lanes ?? []) {
      const ls = book!.state[lane.provider]
      if (emptyUntil(lane, ls, now) === undefined) continue
      const own =
        ls!.checkpoint!.source === "empty"
          ? when(ls!.checkpoint!.at).getTime()
          : -Infinity
      const last = Math.max(this.probed.get(lane.provider) ?? -Infinity, own)
      if (now - last < EMPTY_PROBE_MS) skip.add(lane.provider)
      else due.add(lane.provider)
    }
    return { skip, due }
  }

  // A known-empty lane taken for its daily try: the next one waits a day.
  tried(provider: string, now: number): void {
    this.probed.set(provider, now)
  }
}
