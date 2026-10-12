// Estimates how much of each Console credit grant is left. Anthropic has no
// balance API, so a checkpoint (a balance read in the Console, or an empty
// balance a request reported) is carried forward with the spend since: OpenCode's
// own cost accounting (`opencode stats`) and Hermes' estimate on the same orgs.

export type Lane = {
  provider: string
  label: string
  // Credit granted each billing cycle, in USD. Changes only with the plan.
  amount: number
  // Day of the month the plan renews: a grant arrives and expires on it. A day
  // a short month lacks falls on that month's last day.
  renewalDay: number
  // Env var holding the lane's API key. OpenCode Quota sends it as the bearer
  // token to the local endpoint, which only answers a request carrying it.
  keyEnv?: string
}
export type StatsModel = {
  model: { providerID: string; id: string; variant?: string }
  cost: number
}

// console: listed in the Console. projected: the current cycle's grant, assumed
// when none is known. inferred: the spend outran every known grant, so one
// must have arrived.
export type GrantSource = "console" | "projected" | "inferred"
export type Grant = {
  amount: number
  // A date (local midnight) or an ISO time.
  granted: string
  expires: string
  source: GrantSource
}
// rolled: the estimate carried forward when another lane got a checkpoint or a
// grant expired. none: no checkpoint yet, so the cycle's grants count as full
// at its start.
export type CheckpointSource = "console" | "empty" | "rolled" | "none"
export type Checkpoint = {
  at: string
  balance: number
  source: CheckpointSource
  // `opencode stats` counts whole local days, so OpenCode's spend since `at` is
  // its cost from `opencodeFrom` (a date) less `opencodeBase`, the cost that
  // same window showed at `at`.
  opencodeFrom: string
  opencodeBase: number
  // Hermes' cost per usage row at `at`. Absent: Hermes is not counted.
  hermes?: Record<string, number>
}
export type LaneState = { grants: Grant[]; checkpoint?: Checkpoint }

export type GrantLeft = Grant & { left: number; expired: boolean }
export type Ledger = {
  grants: GrantLeft[]
  // Console balance beyond the known grants. Kept apart; never expires.
  unattributed: number
  // Spend beyond everything known.
  overspent: number
  // What spend could still draw, grants expired since the checkpoint included.
  available: number
  // Left on grants that have not expired, less any overspend.
  remaining: number
  // Left on grants that expired since the checkpoint.
  lapsed: number
}
export type Summary = {
  lane: Lane
  checkpoint: Checkpoint
  grants: GrantLeft[]
  spent: { opencode: number; hermes: number }
  // The `opencode stats` window the OpenCode spend came from, and its cost.
  opencodeWindow?: { from: string; total: number }
  hermesCounted: boolean
  remaining: number
  unattributed: number
  lapsed: number
  // Granted on the grants that still hold something (all live ones if none do).
  total: number
  percentLeft: number
  elapsedDays: number
  pacePerDay: number
  nextExpiry?: Date
  neededPerDay: number
  unusedAtPace: number
  // When the nearest grant with something left expires, else the next renewal.
  resetAt: Date
  nextGrant: Date
  byModel: { id: string; cost: number }[]
}

const DAY = 86_400_000
// OpenCode's pace is its spend over this many days, today included.
export const PACE_DAYS = 7

export function localDate(date: string): Date {
  const [y, m, d] = date.split("-").map(Number)
  return new Date(y, m - 1, d)
}

export function when(value: string): Date {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? localDate(value) : new Date(value)
}

export function ymd(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

// The billing cycle containing `now`, from local midnight of a renewal day to
// the next one. The time of day of a renewal is not known.
export function cycleOf(
  renewalDay: number,
  now: Date,
): { start: Date; end: Date } {
  const on = (year: number, month: number) =>
    new Date(
      year,
      month,
      Math.min(renewalDay, new Date(year, month + 1, 0).getDate()),
    )
  let start = on(now.getFullYear(), now.getMonth())
  if (start.getTime() > now.getTime())
    start = on(now.getFullYear(), now.getMonth() - 1)
  return { start, end: on(start.getFullYear(), start.getMonth() + 1) }
}

// `opencode stats --days N` counts from local midnight: N <= 1 is today, and a
// larger N includes today, so a start day's midnight needs one more day.
export function statsDays(from: Date, now: Date): number {
  const between = Math.round(
    (startOfDay(now).getTime() - startOfDay(from).getTime()) / DAY,
  )
  return Math.max(1, between + 1)
}

const sameDay = (a: Date, b: Date) => ymd(a) === ymd(b)

// The known grants, plus the current cycle's when none expires at its end.
export function grantsFor(lane: Lane, state: LaneState, now: Date): Grant[] {
  const { start, end } = cycleOf(lane.renewalDay, now)
  if (state.grants.some((g) => sameDay(when(g.expires), end)))
    return state.grants
  return [
    ...state.grants,
    {
      amount: lane.amount,
      granted: ymd(start),
      expires: ymd(end),
      source: "projected",
    },
  ]
}

export function checkpointFor(
  lane: Lane,
  state: LaneState,
  grants: Grant[],
  now: Date,
): Checkpoint {
  if (state.checkpoint) return state.checkpoint
  const { start } = cycleOf(lane.renewalDay, now)
  const full = grants
    .filter((g) => when(g.granted) <= start && when(g.expires) > start)
    .reduce((sum, g) => sum + g.amount, 0)
  return {
    at: start.toISOString(),
    balance: full,
    source: "none",
    opencodeFrom: ymd(start),
    opencodeBase: 0,
  }
}

// The checkpoint's balance sits on the grants held then, latest expiry first
// (spend takes the nearest expiry first); a grant that arrives later is full.
// Spend since is then taken nearest expiry first, grants that have expired
// since included: it is not known when within the window it was spent.
export function ledger(
  grants: Grant[],
  at: Date,
  balance: number,
  spent: number,
  now: Date,
): Ledger {
  const pool: GrantLeft[] = grants
    .filter((g) => when(g.expires) > at && when(g.granted) <= now)
    .sort(
      (a, b) =>
        when(a.expires).getTime() - when(b.expires).getTime() ||
        when(a.granted).getTime() - when(b.granted).getTime(),
    )
    .map((g) => ({ ...g, left: 0, expired: when(g.expires) <= now }))
  let rest = balance
  for (const g of [...pool].reverse()) {
    if (when(g.granted) > at) {
      g.left = g.amount
      continue
    }
    g.left = Math.min(g.amount, Math.max(0, rest))
    rest -= g.left
  }
  let unattributed = Math.max(0, rest)
  let due = spent + Math.max(0, -rest)
  for (const g of pool) {
    const take = Math.min(g.left, due)
    g.left -= take
    due -= take
  }
  const take = Math.min(unattributed, due)
  unattributed -= take
  due -= take
  const sum = (list: GrantLeft[]) => list.reduce((s, g) => s + g.left, 0)
  return {
    grants: pool,
    unattributed,
    overspent: due,
    available: sum(pool) + unattributed - due,
    remaining: sum(pool.filter((g) => !g.expired)) + unattributed - due,
    lapsed: sum(pool.filter((g) => g.expired)),
  }
}

// Hermes draws its lanes in a fixed order and moves on only when one is empty.
// Each lane sees Hermes' spend since its own checkpoint (`windows`); a lane
// takes what fits in its room, and what it cannot take is the latest part of
// that spend, so the next lane gets it, up to its own window.
export function allocateHermes(
  order: string[],
  windows: Record<string, number>,
  rooms: Record<string, number>,
): Record<string, number> {
  const charged: Record<string, number> = {}
  let incoming: number | undefined
  for (const id of order) {
    if (!Object.hasOwn(windows, id)) continue
    incoming =
      incoming === undefined ? windows[id] : Math.min(incoming, windows[id])
    const take = Math.min(incoming, Math.max(0, rooms[id] ?? 0))
    charged[id] = take
    incoming -= take
  }
  return charged
}

// The renewal whose grant is not known yet.
export function nextGrantAt(lane: Lane, grants: Grant[], now: Date): Date {
  let at = cycleOf(lane.renewalDay, now).end
  for (let i = 0; i < 12; i++) {
    const end = cycleOf(lane.renewalDay, at).end
    if (!grants.some((g) => sameDay(when(g.expires), end))) break
    at = end
  }
  return at
}

export function summarize(
  lane: Lane,
  input: {
    grants: Grant[]
    checkpoint: Checkpoint
    opencode: number
    // OpenCode's recent daily spend on the lane: a checkpoint can be minutes
    // old, too short a window for a pace.
    opencodePerDay: number
    opencodeWindow?: { from: string; total: number }
    hermes: number
    hermesCounted: boolean
    byModel: { id: string; cost: number }[]
  },
  now: Date,
): Summary {
  const { grants, checkpoint } = input
  const at = when(checkpoint.at)
  const spent = input.opencode + input.hermes
  const book = ledger(grants, at, checkpoint.balance, spent, now)
  const live = book.grants.filter((g) => !g.expired)
  const holding = live.filter((g) => g.left > 0)
  const total =
    (holding.length ? holding : live).reduce((s, g) => s + g.amount, 0) ||
    lane.amount
  const elapsedDays = Math.max(0, (now.getTime() - at.getTime()) / DAY)
  const pacePerDay =
    input.opencodePerDay + input.hermes / Math.max(elapsedDays, 1)
  const daysTo = (date: string) =>
    Math.max(0, (when(date).getTime() - now.getTime()) / DAY)
  const nearest = holding[0]
  // At the current pace, each grant gets what is spent before it expires,
  // after the grants that expire sooner.
  let used = 0
  let unusedAtPace = 0
  for (const g of holding) {
    const take = Math.min(g.left, Math.max(0, pacePerDay * daysTo(g.expires) - used))
    used += take
    unusedAtPace += g.left - take
  }
  const nextGrant = nextGrantAt(lane, grants, now)
  return {
    lane,
    checkpoint,
    grants: book.grants,
    spent: { opencode: input.opencode, hermes: input.hermes },
    opencodeWindow: input.opencodeWindow,
    hermesCounted: input.hermesCounted,
    remaining: book.remaining,
    unattributed: book.unattributed,
    lapsed: book.lapsed,
    total,
    percentLeft: (book.remaining / total) * 100,
    elapsedDays,
    pacePerDay,
    nextExpiry: nearest ? when(nearest.expires) : undefined,
    neededPerDay:
      nearest && daysTo(nearest.expires) > 0
        ? nearest.left / daysTo(nearest.expires)
        : 0,
    unusedAtPace,
    resetAt: nearest ? when(nearest.expires) : cycleOf(lane.renewalDay, now).end,
    nextGrant,
    byModel: input.byModel,
  }
}

const usd = (n: number) => (n < 0 ? `-$${(-n).toFixed(2)}` : `$${n.toFixed(2)}`)
const stamp = (date: Date) =>
  `${ymd(date)} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`

const BASIS: Record<CheckpointSource, string> = {
  console: "Console balance",
  empty: "empty balance reported",
  rolled: "estimate carried forward",
  none: "no checkpoint, grants taken as full",
}

export function format(summaries: Summary[], hermesOrder: string[] = []): string {
  const lines: string[] = []
  for (const s of summaries) {
    const { lane } = s
    lines.push(
      `${lane.label} (${lane.provider}): ${usd(s.remaining)} left of ${usd(s.total)} (${Math.round(s.percentLeft)}%), renews on day ${lane.renewalDay}`,
    )
    for (const g of s.grants)
      lines.push(
        `  grant     ${usd(g.left)} of ${usd(g.amount)}, ${g.expired ? "expired" : "expires"} ${ymd(when(g.expires))} (${g.source})`,
      )
    if (s.unattributed > 0)
      lines.push(`  grant     ${usd(s.unattributed)} beyond the known grants`)
    lines.push(`  next      ${usd(lane.amount)} expected ${ymd(s.nextGrant)}`)
    const cp = s.checkpoint
    lines.push(
      `  basis     ${BASIS[cp.source]} ${usd(cp.balance)} at ${stamp(when(cp.at))}`,
    )
    lines.push(
      `  since     OpenCode ${usd(s.spent.opencode)}, Hermes ${s.hermesCounted ? usd(s.spent.hermes) : "not counted"}`,
    )
    lines.push(
      `  pace      ${usd(s.pacePerDay)}/day lately` +
        (s.nextExpiry
          ? `, ${usd(s.neededPerDay)}/day needed by ${ymd(s.nextExpiry)}`
          : ""),
    )
    lines.push(`  at pace   ${usd(s.unusedAtPace)} would expire unused`)
    if (s.byModel.length)
      lines.push(
        `  by model  ${s.byModel
          .slice(0, 4)
          .map((m) => `${m.id} ${usd(m.cost)}`)
          .join(", ")} (OpenCode, last ${PACE_DAYS} days)`,
      )
    lines.push("")
  }
  const labels = hermesOrder
    .map((id) => summaries.find((s) => s.lane.provider === id)?.lane.label)
    .filter(Boolean)
  lines.push(
    "Spend after a checkpoint is OpenCode's own cost accounting plus Hermes' estimate" +
      (labels.length ? `, which draws ${labels.join(" then ")}.` : "."),
    "A grant expires at local midnight. Record a Console balance with",
    "  bun ~/.config/opencode/lib/credit-lanes/status.ts checkpoint <lane> <balance>",
  )
  return lines.join("\n")
}
