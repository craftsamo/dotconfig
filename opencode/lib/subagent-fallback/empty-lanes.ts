import { loadConfig } from "../credit-lanes/collect"
import {
  cycleOf,
  when,
  ymd,
  type Lane,
  type LaneState,
} from "../credit-lanes/core"
import { readState } from "../credit-lanes/state"

// What the credit-lane estimate (lib/credit-lanes) knows of each lane: its
// renewal day, and its known grants and latest checkpoint.
export type LaneBook = { lanes: Lane[]; state: Record<string, LaneState> }

export function readLaneBook(): LaneBook | undefined {
  try {
    const lanes = loadConfig().lanes
    const state = readState().lanes
    if (!Array.isArray(lanes) || typeof state !== "object" || state === null)
      return undefined
    return { lanes, state }
  } catch {
    return undefined
  }
}

// Empty below this, as /credits rounds it.
const EMPTY_USD = 0.005
// A lane known empty is still tried this often: a grant can arrive off its
// schedule (a plan change, a top-up), and only a request tells.
export const EMPTY_PROBE_MS = 24 * 3_600_000
// A try that has not failed this long after it was made shows the lane holds
// something: a failed one records an empty checkpoint within seconds.
export const TRY_SETTLED_MS = 10 * 60_000
// Tries kept across a restart: one that showed money stands for a cycle.
const KEEP_MS = 35 * 86_400_000
const DAY = 86_400_000

const dateOnly = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value)

// Until when a lane holds nothing: its checkpoint balance was $0 (an empty
// balance a request reported, a Console reading, or the estimate carried
// forward) and no money can have arrived since. Spend only lowers a balance,
// so this needs no spend figures: money comes with the first known grant
// after the checkpoint, or the next renewal. Neither has a known time of
// day: a grant listed by its date alone counts from that whole day, and a
// checkpoint on a renewal day holds only to its end. Undefined when the lane
// may hold something.
export function emptyUntil(
  lane: Lane,
  ls: LaneState | undefined,
  now: number,
): number | undefined {
  const checkpoint = ls?.checkpoint
  if (!checkpoint || !(checkpoint.balance < EMPTY_USD)) return undefined
  const at = when(checkpoint.at).getTime()
  if (!Number.isFinite(at) || at > now) return undefined
  const day = ymd(new Date(at))
  const { start, end } = cycleOf(lane.renewalDay, new Date(at))
  const renewal =
    ymd(start) === day
      ? Math.min(end.getTime(), start.getTime() + DAY)
      : end.getTime()
  const grants = (Array.isArray(ls!.grants) ? ls!.grants : []).flatMap((g) => {
    const t = when(String(g.granted)).getTime()
    if (!Number.isFinite(t)) return []
    if (dateOnly(String(g.granted))) return ymd(new Date(t)) >= day ? [t] : []
    return t > at ? [t] : []
  })
  const funded = Math.min(renewal, ...grants)
  return now < funded ? funded : undefined
}

// The lanes known empty that are passed over now, and those whose daily try
// is due. A lane's last try is the later of one made here and its own empty
// checkpoint (what a failed try records). A try that has settled without a
// newer reading of $0 (an empty balance, or the Console) shows money: the
// lane is not known empty then, whatever the estimate carries forward.
export class EmptyLanes {
  private probed = new Map<string, number>()
  // When a lane last refused a request for its balance. Kept here, since the
  // lane's empty checkpoint does not last: the next lane's checkpoint carries
  // every other lane forward, and that one reads as an estimate.
  private refusals = new Map<string, number>()

  scan(
    book: LaneBook | undefined,
    now: number,
  ): { skip: ReadonlySet<string>; due: ReadonlySet<string> } {
    const skip = new Set<string>()
    const due = new Set<string>()
    for (const lane of Array.isArray(book?.lanes) ? book!.lanes : []) {
      // A lane its state does not describe is passed over by nothing.
      try {
        const ls = book!.state[lane.provider]
        if (emptyUntil(lane, ls, now) === undefined) continue
        const checkpoint = ls!.checkpoint!
        const at = when(checkpoint.at).getTime()
        const probed = this.probed.get(lane.provider)
        const refused = this.refusals.get(lane.provider) ?? -Infinity
        const reading =
          checkpoint.source === "empty" || checkpoint.source === "console"
        if (
          probed !== undefined &&
          now - probed >= TRY_SETTLED_MS &&
          !(reading && at > probed) &&
          // A refusal in the same instant as the try is that try's.
          !(refused >= probed)
        )
          continue
        const own = checkpoint.source === "empty" ? at : -Infinity
        const last = Math.max(probed ?? -Infinity, own, refused)
        if (now - last < EMPTY_PROBE_MS) skip.add(lane.provider)
        else due.add(lane.provider)
      } catch {}
    }
    return { skip, due }
  }

  // A known-empty lane taken for its daily try: the next one waits a day,
  // unless this one shows money.
  tried(provider: string, now: number): void {
    this.probed.set(provider, now)
  }

  // A lane refused a request for its balance (a failed try, or any request).
  refused(provider: string, now: number): void {
    this.refusals.set(provider, now)
  }

  // The tries and refusals worth keeping across a restart.
  saved(now: number): {
    probed: Record<string, number>
    refused: Record<string, number>
  } {
    const recent = (times: Map<string, number>) =>
      Object.fromEntries(
        [...times].filter(([, at]) => at <= now && now - at < KEEP_MS),
      )
    return { probed: recent(this.probed), refused: recent(this.refusals) }
  }
  restore(
    saved: {
      probed?: Record<string, number>
      refused?: Record<string, number>
    },
    now: number,
  ): void {
    const take = (
      from: Record<string, number> | undefined,
      into: Map<string, number>,
    ) => {
      for (const [provider, at] of Object.entries(from ?? {}))
        if (at <= now && now - at < KEEP_MS) into.set(provider, at)
    }
    take(saved.probed, this.probed)
    take(saved.refused, this.refusals)
  }
}
