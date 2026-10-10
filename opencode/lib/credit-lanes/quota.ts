import type { Summary } from "./core"

// OpenCode Quota's `quota-v1` envelope, for a custom remote provider.
export type QuotaEntry =
  | {
      kind: "percent"
      name: string
      resultType: "budget"
      percentRemaining: number
      label: string
      right: string
      resetTimeIso?: string
      observedAtIso: string
    }
  | {
      kind: "value"
      name: string
      resultType: "usage"
      label: string
      value: string
      observedAtIso: string
    }

const usd = (n: number) => `$${n.toFixed(2)}`
// Whole dollars: the sidebar is 36 columns wide.
const perDay = (n: number) => `$${Math.round(n)}/day`

// Quota's sidebar puts a value row on one line as label + value and gives the
// label what the value leaves of 15 columns (a value counts as at least 6). A
// value of 15 to 24 characters leaves it one, so "Pace:" showed as "P". Keep
// label + value within 15, so a label is never cut and the row stays on one line.
export const SIDEBAR_ROOM = 15
export const valueRoom = (label: string, value: string) =>
  label.length + Math.max(value.length, 6)

export function toQuotaV1(s: Summary, now: Date) {
  const observedAtIso = now.toISOString()
  const row = (name: string, label: string, value: string): QuotaEntry => ({
    kind: "value",
    name,
    resultType: "usage",
    label,
    value,
    observedAtIso,
  })
  const entries: QuotaEntry[] = [
    {
      kind: "percent",
      name: "Credit",
      resultType: "budget",
      // The envelope rejects more than 100; overspend may go below zero.
      percentRemaining: Math.min(100, s.percentLeft),
      label: "Left:",
      right: `${usd(s.remaining)}/${usd(s.lane.amount)}`,
      resetTimeIso: s.cycleEnd.toISOString(),
      observedAtIso,
    },
    row("Pace", "Pace:", perDay(s.pacePerDay)),
    row("Need", "Need:", perDay(s.neededPerDay)),
  ]
  // Said only when there is something to lose: it is the number to act on.
  if (s.unusedAtPace >= 0.5)
    entries.push(row("Unused", "Unused:", `~$${Math.round(s.unusedAtPace)}`))
  return { version: "quota-v1" as const, entries }
}
