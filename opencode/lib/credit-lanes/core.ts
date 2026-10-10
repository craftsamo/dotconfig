// Estimates how much of each Console credit grant is left, from OpenCode's own
// cost accounting (`opencode stats`). Anthropic has no balance API.

export type Lane = {
  provider: string
  label: string
  // Credit granted each billing cycle, in USD. Changes only with the plan.
  amount: number
  // Day of the month the plan renews: the grant arrives and the old one
  // expires. A day a short month lacks falls on that month's last day.
  renewalDay: number
  // When the lane began receiving its grant, for a first cycle that started
  // part way through. Older than the current cycle once it renews; then unused.
  since?: string
  // Env var holding the lane's API key. OpenCode Quota sends it as the bearer
  // token to the local endpoint, which only answers a request carrying it.
  keyEnv?: string
}
export type StatsModel = {
  model: { providerID: string; id: string; variant?: string }
  cost: number
}
export type Summary = {
  lane: Lane
  cycleStart: Date
  cycleEnd: Date
  trackedFrom: Date
  spent: number
  remaining: number
  percentLeft: number
  elapsedDays: number
  daysLeft: number
  pacePerDay: number
  neededPerDay: number
  unusedAtPace: number
  byModel: { id: string; cost: number }[]
}

const DAY = 86_400_000

export function localDate(date: string): Date {
  const [y, m, d] = date.split("-").map(Number)
  return new Date(y, m - 1, d)
}

export function ymd(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
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

// What this lane has been spending against: the current cycle, or since it
// began receiving the grant when that is later.
export function trackedFrom(lane: Lane, now: Date): Date {
  const { start } = cycleOf(lane.renewalDay, now)
  const since = lane.since ? localDate(lane.since) : undefined
  return since && since.getTime() > start.getTime() ? since : start
}

// `opencode stats --days N` counts from local midnight: N <= 1 is today, and a
// larger N includes today, so a start day's midnight needs one more day.
export function statsDays(from: Date, now: Date): number {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const between = Math.round((today.getTime() - from.getTime()) / DAY)
  return Math.max(1, between + 1)
}

export function summarize(
  lane: Lane,
  models: StatsModel[],
  now: Date,
): Summary {
  const { start: cycleStart, end: cycleEnd } = cycleOf(lane.renewalDay, now)
  const from = trackedFrom(lane, now)
  const mine = models.filter((m) => m.model.providerID === lane.provider)
  const spent = mine.reduce((sum, m) => sum + m.cost, 0)
  const remaining = lane.amount - spent
  const elapsedDays = Math.max(0, (now.getTime() - from.getTime()) / DAY)
  // Expiry is taken as the start of its date: the time of day is not known.
  const daysLeft = Math.max(0, (cycleEnd.getTime() - now.getTime()) / DAY)
  const pacePerDay = spent / Math.max(elapsedDays, 0.5)
  const byId = new Map<string, number>()
  for (const m of mine)
    byId.set(m.model.id, (byId.get(m.model.id) ?? 0) + m.cost)
  return {
    lane,
    cycleStart,
    cycleEnd,
    trackedFrom: from,
    spent,
    remaining,
    percentLeft: (remaining / lane.amount) * 100,
    elapsedDays,
    daysLeft,
    pacePerDay,
    neededPerDay: daysLeft > 0 ? Math.max(0, remaining) / daysLeft : 0,
    unusedAtPace: Math.max(0, remaining - pacePerDay * daysLeft),
    byModel: [...byId.entries()]
      .map(([id, cost]) => ({ id, cost }))
      .sort((a, b) => b.cost - a.cost),
  }
}

const usd = (n: number) => `$${n.toFixed(2)}`

export function format(summaries: Summary[]): string {
  const lines: string[] = []
  for (const s of summaries) {
    const { lane } = s
    lines.push(
      `${lane.label} (${lane.provider}): ${ymd(s.cycleStart)} -> ${ymd(s.cycleEnd)}, renews on day ${lane.renewalDay}`,
    )
    lines.push(
      `  spent     ${usd(s.spent)} of ${usd(lane.amount)}   ${usd(s.remaining)} left (${Math.round(s.percentLeft)}%)`,
    )
    lines.push(`  time      ${s.daysLeft.toFixed(1)} days left`)
    lines.push(
      `  pace      ${usd(s.pacePerDay)}/day so far, ${usd(s.neededPerDay)}/day needed to use it all`,
    )
    lines.push(`  at pace   ${usd(s.unusedAtPace)} would expire unused`)
    if (s.byModel.length)
      lines.push(
        `  by model  ${s.byModel
          .slice(0, 4)
          .map((m) => `${m.id} ${usd(m.cost)}`)
          .join(", ")}`,
      )
    lines.push("")
  }
  lines.push(
    "Spend is OpenCode's own cost accounting for each provider (Console differed by about 3% on 2026-10-09).",
    "Only requests made through these keys by OpenCode count. A cycle starts at local midnight of its renewal day.",
  )
  return lines.join("\n")
}
