// Estimates how much of each Console credit grant is left, from OpenCode's own
// cost accounting (`opencode stats`). Anthropic has no balance API.

export type Lane = {
  provider: string
  label: string
  amount: number
  grantedOn: string
  expiresOn: string
}
export type StatsModel = {
  model: { providerID: string; id: string; variant?: string }
  cost: number
}
export type Summary = {
  lane: Lane
  spent: number
  remaining: number
  percentLeft: number
  elapsedDays: number
  daysLeft: number
  expired: boolean
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

// `opencode stats --days N` counts from local midnight: N <= 1 is today, and a
// larger N includes today, so the grant day's midnight needs one more day.
export function statsDays(grantedOn: string, now: Date): number {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const between = Math.round(
    (today.getTime() - localDate(grantedOn).getTime()) / DAY,
  )
  return Math.max(1, between + 1)
}

export function summarize(
  lane: Lane,
  models: StatsModel[],
  now: Date,
): Summary {
  const mine = models.filter((m) => m.model.providerID === lane.provider)
  const spent = mine.reduce((sum, m) => sum + m.cost, 0)
  const remaining = lane.amount - spent
  // Expiry is taken as the start of its date: the time of day is not shown.
  const elapsedDays = Math.max(
    0,
    (now.getTime() - localDate(lane.grantedOn).getTime()) / DAY,
  )
  const daysLeft = Math.max(
    0,
    (localDate(lane.expiresOn).getTime() - now.getTime()) / DAY,
  )
  const pacePerDay = spent / Math.max(elapsedDays, 0.5)
  const byId = new Map<string, number>()
  for (const m of mine)
    byId.set(m.model.id, (byId.get(m.model.id) ?? 0) + m.cost)
  return {
    lane,
    spent,
    remaining,
    percentLeft: (remaining / lane.amount) * 100,
    elapsedDays,
    daysLeft,
    expired: daysLeft === 0,
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
      `${lane.label} (${lane.provider}): ${lane.grantedOn} -> ${lane.expiresOn}`,
    )
    lines.push(
      `  spent     ${usd(s.spent)} of ${usd(lane.amount)}   ${usd(s.remaining)} left (${Math.round(s.percentLeft)}%)`,
    )
    if (s.expired) {
      lines.push("  expired   update lanes.json for the renewed grant")
    } else {
      lines.push(`  time      ${s.daysLeft.toFixed(1)} days left`)
      lines.push(
        `  pace      ${usd(s.pacePerDay)}/day so far, ${usd(s.neededPerDay)}/day needed to use it all`,
      )
      lines.push(`  at pace   ${usd(s.unusedAtPace)} would expire unused`)
    }
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
    "Only requests made through these keys by OpenCode count. Expiry is taken as the start of its date.",
  )
  return lines.join("\n")
}
