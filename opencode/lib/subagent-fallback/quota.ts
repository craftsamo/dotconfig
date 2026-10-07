import type { BillingProof, QuotaProof, UsageProof } from "./policy"

type Rec = Record<string, unknown>
type Win = { percent: number; resetAt: number }

const KNOWN_NATIVE_IDS = new Set([
  "claude-opus-5-5",
  "claude-sonnet-5-5",
  "claude-haiku-4-5",
  "claude-fable-5-1",
])
const KNOWN_OPENAI_IDS = new Set(["gpt-6.1-sol", "gpt-6-luna"])

const unknownBilling = (now: number): BillingProof => ({
  state: "unknown",
  observedAt: now,
})

function decimal(v: unknown): number | undefined {
  if (typeof v !== "string" || !/^(0|[1-9][0-9]*)(\.[0-9]+)?$/.test(v))
    return undefined
  const n = Number(v)
  return Number.isFinite(n) && n >= 0 ? n : undefined
}

const unknownProof = (now: number): QuotaProof => ({
  state: "unknown",
  observedAt: now,
})

function isRecord(v: unknown): v is Rec {
  if (typeof v !== "object" || v === null || Array.isArray(v)) return false
  const proto = Object.getPrototypeOf(v)
  return proto === Object.prototype || proto === null
}

function own(r: Rec, key: string): unknown {
  return Object.prototype.hasOwnProperty.call(r, key) ? r[key] : undefined
}

function percent(v: unknown): number | undefined {
  return typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= 100
    ? v
    : undefined
}

function positiveInt(v: unknown): number | undefined {
  return typeof v === "number" &&
    Number.isFinite(v) &&
    Number.isInteger(v) &&
    v > 0
    ? v
    : undefined
}

function classify(
  wins: Win[],
  now: number,
  forceExhausted = false,
): QuotaProof {
  const hit = wins.filter((w) => w.percent >= 100)
  if (hit.length === 0 && !forceExhausted)
    return { state: "available", observedAt: now }
  const pool = hit.length > 0 ? hit : wins
  return {
    state: "exhausted",
    observedAt: now,
    resetAt: Math.max(...pool.map((w) => w.resetAt)),
  }
}

function anthropicWindow(v: unknown, now: number): Win | undefined {
  if (!isRecord(v)) return undefined
  const p = percent(own(v, "utilization"))
  const raw = own(v, "resets_at")
  if (p === undefined || typeof raw !== "string") return undefined
  const resetAt = Date.parse(raw)
  if (!Number.isFinite(resetAt) || resetAt <= now) return undefined
  return { percent: p, resetAt }
}

export function parseAnthropicQuota(
  data: unknown,
  now: number,
  modelID: string,
): QuotaProof {
  if (!isRecord(data)) return unknownProof(now)

  const wins: Win[] = []
  for (const key of ["five_hour", "seven_day"]) {
    const w = anthropicWindow(own(data, key), now)
    if (!w) return unknownProof(now)
    wins.push(w)
  }

  const scoped = modelID.startsWith("claude-sonnet")
    ? "seven_day_sonnet"
    : modelID.startsWith("claude-opus")
      ? "seven_day_opus"
      : undefined
  if (scoped) {
    const raw = own(data, scoped)
    if (raw !== undefined && raw !== null) {
      const w = anthropicWindow(raw, now)
      if (!w) return unknownProof(now)
      wins.push(w)
    }
  }

  let opaque = false
  const limits = own(data, "limits")
  if (limits !== undefined && limits !== null) {
    if (!Array.isArray(limits)) opaque = true
    else
      for (const entry of limits) {
        const w = anthropicLimitWindow(entry, now)
        if (!w) {
          opaque = true
          continue
        }
        if (w.shared || (w.id !== undefined && w.id === modelID)) wins.push(w)
        else if (
          (w.id === undefined || !KNOWN_NATIVE_IDS.has(w.id)) &&
          w.percent >= 100
        )
          opaque = true
      }
  }

  if (opaque && !wins.some((w) => w.percent >= 100)) return unknownProof(now)
  return classify(wins, now)
}

function anthropicLimitWindow(
  v: unknown,
  now: number,
): (Win & { shared: boolean; id?: string }) | undefined {
  if (!isRecord(v)) return undefined
  const kind = own(v, "kind")
  if (kind !== "session" && kind !== "weekly_all" && kind !== "weekly_scoped")
    return undefined
  const w = anthropicWindow(
    { utilization: own(v, "percent"), resets_at: own(v, "resets_at") },
    now,
  )
  if (!w) return undefined
  const scope = own(v, "scope")
  if (kind !== "weekly_scoped") {
    if (!Object.prototype.hasOwnProperty.call(v, "scope") || scope !== null)
      return undefined
    return { ...w, shared: true }
  }
  if (!isRecord(scope)) return undefined
  const model = own(scope, "model")
  if (!isRecord(model)) return undefined
  const id = own(model, "id")
  if (id !== undefined && id !== null && typeof id !== "string")
    return undefined
  return {
    ...w,
    shared: false,
    id: id === null || id === "" ? undefined : id,
  }
}

export function parseAnthropicBilling(
  data: unknown,
  now: number,
): BillingProof {
  if (!isRecord(data)) return unknownBilling(now)
  const extra = own(data, "extra_usage")
  if (!isRecord(extra)) return unknownBilling(now)
  const enabled = own(extra, "is_enabled")
  if (enabled === false) return { state: "subscription_only", observedAt: now }
  if (enabled !== true) return unknownBilling(now)
  const u = own(extra, "utilization")
  const limit = own(extra, "monthly_limit")
  const used = own(extra, "used_credits")
  const fin = (v: unknown): v is number =>
    typeof v === "number" && Number.isFinite(v)
  if (!fin(u) || !fin(limit) || !fin(used) || limit <= 0 || used < 0 || u < 0)
    return unknownBilling(now)
  if (u >= 100 || used >= limit) return { state: "paid_risk", observedAt: now }
  return { state: "credits_available", observedAt: now }
}

export function inspectAnthropicUsage(
  data: unknown,
  now: number,
  modelID: string,
): UsageProof {
  return {
    quota: parseAnthropicQuota(data, now, modelID),
    billing: parseAnthropicBilling(data, now),
  }
}

function openaiWindow(v: unknown, now: number): Win | undefined {
  if (!isRecord(v)) return undefined
  const p = percent(own(v, "used_percent"))
  if (
    p === undefined ||
    positiveInt(own(v, "limit_window_seconds")) === undefined
  )
    return undefined
  const at = own(v, "reset_at")
  const after = own(v, "reset_after_seconds")
  let resetAt: number
  if (at !== undefined && at !== null) {
    if (typeof at !== "number" || !Number.isFinite(at)) return undefined
    resetAt = at * 1000
  } else {
    const s = positiveInt(after)
    if (s === undefined) return undefined
    resetAt = now + s * 1000
  }
  if (!Number.isFinite(resetAt) || !(resetAt > now)) return undefined
  return { percent: p, resetAt }
}

function rateStatus(rate: unknown, now: number): QuotaProof | undefined {
  if (!isRecord(rate)) return undefined
  const allowed = own(rate, "allowed")
  const reached = own(rate, "limit_reached")
  if (typeof allowed !== "boolean" || typeof reached !== "boolean")
    return undefined

  const primary = openaiWindow(own(rate, "primary_window"), now)
  if (!primary) return undefined
  const wins = [primary]
  const sec = own(rate, "secondary_window")
  if (sec !== undefined && sec !== null) {
    const w = openaiWindow(sec, now)
    if (!w) return undefined
    wins.push(w)
  }

  if (allowed === false && reached === true) return classify(wins, now, true)
  if (
    allowed === true &&
    reached === false &&
    wins.every((w) => w.percent < 100)
  )
    return { state: "available", observedAt: now }
  return unknownProof(now)
}

function spendFields(r: Rec, now: number): boolean {
  for (const key of ["used_percent", "remaining_percent"]) {
    const v = own(r, key)
    if (v === undefined || v === null) continue
    if (typeof v !== "number" || !Number.isInteger(v) || v < 0 || v > 100)
      return false
  }
  const after = own(r, "reset_after_seconds")
  if (after !== undefined && after !== null && positiveInt(after) === undefined)
    return false
  const at = own(r, "reset_at")
  if (at !== undefined && at !== null) {
    if (typeof at !== "number" || !Number.isFinite(at)) return false
    const ms = at * 1000
    if (!Number.isFinite(ms) || !(ms > now)) return false
  }
  return true
}

// True only when the spend_control shape is valid and not reached.
function spendOk(spend: unknown, now: number): boolean {
  if (spend === undefined || spend === null) return true
  if (!isRecord(spend)) return false
  if (own(spend, "reached") !== false) return false
  if (!spendFields(spend, now)) return false
  const lim = own(spend, "individual_limit")
  if (lim === undefined || lim === null) return true
  if (!isRecord(lim)) return false
  for (const key of ["limit", "used", "remaining"]) {
    const v = own(lim, key)
    if (v === undefined || v === null) continue
    if (decimal(v) === undefined) return false
  }
  return spendFields(lim, now)
}

export function parseOpenAIQuota(
  data: unknown,
  now: number,
  modelID = "gpt-6.1-sol",
): QuotaProof {
  if (!isRecord(data)) return unknownProof(now)
  if (own(data, "plan_type") !== "plus") return unknownProof(now)
  if (!spendOk(own(data, "spend_control"), now)) return unknownProof(now)

  const primary = rateStatus(own(data, "rate_limit"), now)
  if (!primary) return unknownProof(now)

  const statuses: QuotaProof[] = [primary]
  let opaque = false
  const extras = own(data, "additional_rate_limits")
  if (extras !== undefined && extras !== null) {
    if (!Array.isArray(extras)) opaque = true
    else
      for (const entry of extras) {
        if (
          !isRecord(entry) ||
          typeof own(entry, "limit_name") !== "string" ||
          typeof own(entry, "metered_feature") !== "string"
        ) {
          opaque = true
          continue
        }
        const slug = own(entry, "normal_model_slug")
        if (slug !== undefined && slug !== null && typeof slug !== "string") {
          opaque = true
          continue
        }
        const st = rateStatus(own(entry, "rate_limit"), now)
        if (!st) {
          opaque = true
          continue
        }
        if (slug === modelID) statuses.push(st)
        else if (typeof slug !== "string" || !KNOWN_OPENAI_IDS.has(slug))
          opaque = true
      }
  }

  const exhausted = statuses.filter((s) => s.state === "exhausted")
  if (exhausted.length > 0)
    return {
      state: "exhausted",
      observedAt: now,
      resetAt: Math.max(...exhausted.map((s) => s.resetAt as number)),
    }
  if (opaque || statuses.some((s) => s.state !== "available"))
    return unknownProof(now)
  return { state: "available", observedAt: now }
}

export function parseOpenAIBilling(data: unknown, now: number): BillingProof {
  if (!isRecord(data) || own(data, "plan_type") !== "plus")
    return unknownBilling(now)
  const credits = own(data, "credits")
  if (!isRecord(credits)) return unknownBilling(now)
  const has = own(credits, "has_credits")
  const unlimited = own(credits, "unlimited")
  if (typeof has !== "boolean" || typeof unlimited !== "boolean")
    return unknownBilling(now)
  if (unlimited) return unknownBilling(now)
  const balance = own(credits, "balance")
  if (has) {
    const n = decimal(balance)
    if (n === undefined) return unknownBilling(now)
    return {
      state: n > 0 ? "credits_available" : "paid_risk",
      observedAt: now,
    }
  }
  if (balance === undefined || balance === null)
    return { state: "subscription_only", observedAt: now }
  const n = decimal(balance)
  if (n === undefined || n > 0) return unknownBilling(now)
  return { state: "subscription_only", observedAt: now }
}

export function inspectOpenAIUsage(
  data: unknown,
  now: number,
  modelID = "gpt-6.1-sol",
): UsageProof {
  return {
    quota: parseOpenAIQuota(data, now, modelID),
    billing: parseOpenAIBilling(data, now),
  }
}
