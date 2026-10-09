import { localDate, type Summary } from "./core"

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

export function toQuotaV1(s: Summary, now: Date) {
  const observedAtIso = now.toISOString()
  const entries: QuotaEntry[] = [
    {
      kind: "percent",
      name: "Credit",
      resultType: "budget",
      // The envelope rejects more than 100; overspend may go below zero.
      percentRemaining: Math.min(100, s.percentLeft),
      label: "Left:",
      right: `${usd(s.remaining)}/${usd(s.lane.amount)}`,
      ...(s.expired
        ? {}
        : { resetTimeIso: localDate(s.lane.expiresOn).toISOString() }),
      observedAtIso,
    },
    {
      kind: "value",
      name: "Pace",
      resultType: "usage",
      label: "Pace:",
      value: s.expired
        ? "expired, update lanes.json"
        : s.unusedAtPace > 0
          ? `${usd(s.pacePerDay)}/day, needs ${usd(s.neededPerDay)} (~${usd(s.unusedAtPace)} unused)`
          : `${usd(s.pacePerDay)}/day, needs ${usd(s.neededPerDay)}`,
      observedAtIso,
    },
  ]
  return { version: "quota-v1" as const, entries }
}
