import {
  subscription,
  type AccountsContext,
  type Dependencies,
} from "./accounts"
import { inspectAnthropicUsage, inspectOpenAIUsage } from "./quota"
import type { BillingProof } from "./policy"

export type Diagnostic = {
  outcome:
    | "account_unavailable"
    | "http_error"
    | "timeout"
    | "transport_or_redirect_error"
    | "json_decode_error"
    | "parser_reject"
    | "proof_accepted"
  status?: number
  reasons?: string[]
  state?: "available" | "exhausted"
  billingState?: BillingProof["state"]
  limitShapes?: { kind: string; fields: Record<string, string> }[]
}

type Rec = Record<string, unknown>

const SHAPE_FIELDS = [
  "kind",
  "type",
  "name",
  "percent",
  "utilization",
  "resets_at",
  "scope",
  "is_active",
  "period",
  "limit",
  "usage",
]
const SHAPE_MAX = 20
const KIND_FORBIDDEN =
  /secret|token|key|credential|password|auth|cookie|private|account|user|email/

const URLS = {
  anthropic: "https://api.anthropic.com/api/oauth/usage",
  openai: "https://chatgpt.com/backend-api/wham/usage",
} as const
const FALLBACK = "unsupported_response"

function isRecord(v: unknown): v is Rec {
  if (typeof v !== "object" || v === null || Array.isArray(v)) return false
  const proto = Object.getPrototypeOf(v)
  return proto === Object.prototype || proto === null
}

function own(r: Rec, key: string): unknown {
  return Object.prototype.hasOwnProperty.call(r, key) ? r[key] : undefined
}

function isPercent(v: unknown): boolean {
  return typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= 100
}

function isPositiveInt(v: unknown): boolean {
  return typeof v === "number" && Number.isInteger(v) && v > 0
}

function anthropicWindowCodes(
  v: unknown,
  now: number,
  prefix: string,
  missing: string,
): string[] {
  if (!isRecord(v)) return [missing]
  const codes: string[] = []
  if (!isPercent(own(v, "utilization")))
    codes.push(`${prefix}_utilization_invalid`)
  const raw = own(v, "resets_at")
  if (raw === undefined) codes.push(`${prefix}_reset_missing`)
  else if (raw === null) codes.push(`${prefix}_reset_null`)
  else if (typeof raw !== "string") codes.push(`${prefix}_reset_wrong_type`)
  else {
    const at = Date.parse(raw)
    if (!Number.isFinite(at)) codes.push(`${prefix}_reset_unparseable`)
    else if (at <= now) codes.push(`${prefix}_reset_not_future`)
  }
  return codes
}

const NATIVE_IDS = new Set([
  "claude-opus-5-5",
  "claude-sonnet-5-5",
  "claude-haiku-4-5",
  "claude-fable-5-1",
])

function scopedLimitCodes(entries: unknown[], now: number): string[] {
  const out = new Set<string>()
  for (const entry of entries) {
    const kind = isRecord(entry) ? own(entry, "kind") : undefined
    if (
      !isRecord(entry) ||
      (kind !== "session" && kind !== "weekly_all" && kind !== "weekly_scoped")
    ) {
      out.add("scoped_window_shape_invalid")
      continue
    }
    const shared = kind !== "weekly_scoped"
    let valid = true
    const pct = own(entry, "percent")
    if (!isPercent(pct)) {
      out.add("scoped_window_percent_invalid")
      valid = false
    }
    const raw = own(entry, "resets_at")
    if (raw === undefined) out.add("scoped_window_reset_missing")
    else if (raw === null) out.add("scoped_window_reset_null")
    else if (typeof raw !== "string") out.add("scoped_window_reset_wrong_type")
    else {
      const at = Date.parse(raw)
      if (!Number.isFinite(at)) out.add("scoped_window_reset_unparseable")
      else if (at <= now) out.add("scoped_window_reset_not_future")
    }
    if (
      raw === undefined ||
      raw === null ||
      typeof raw !== "string" ||
      !(Date.parse(raw) > now)
    )
      valid = false
    const scope = own(entry, "scope")
    if (shared) {
      if (scope !== null) out.add("scoped_window_scope_invalid")
      continue
    }
    const model = isRecord(scope) ? own(scope, "model") : undefined
    const id = isRecord(model) ? own(model, "id") : undefined
    if (
      !isRecord(scope) ||
      !isRecord(model) ||
      (id !== undefined && id !== null && typeof id !== "string")
    ) {
      out.add("scoped_window_scope_invalid")
      valid = false
    }
    if (
      valid &&
      (pct as number) >= 100 &&
      (typeof id !== "string" || id === "" || !NATIVE_IDS.has(id))
    )
      out.add("scoped_window_exhaustion_unverified")
  }
  return [...out]
}

export function explainAnthropic(data: unknown, now: number): string[] {
  try {
    if (!isRecord(data)) return ["usage_not_object"]
    const codes: string[] = []

    const limits = own(data, "limits")
    if (limits !== undefined && limits !== null) {
      if (!Array.isArray(limits)) codes.push("limits_unsupported")
      else if (limits.length > 0)
        codes.push("model_scope_unverified", ...scopedLimitCodes(limits, now))
    }

    codes.push(
      ...anthropicWindowCodes(
        own(data, "five_hour"),
        now,
        "five_hour",
        "five_hour_window_missing",
      ),
      ...anthropicWindowCodes(
        own(data, "seven_day"),
        now,
        "seven_day",
        "seven_day_window_missing",
      ),
    )

    // Diagnosed for the selected model scope only (claude-sonnet-5-5).
    const scoped = own(data, "seven_day_sonnet")
    if (scoped !== undefined && scoped !== null) {
      if (anthropicWindowCodes(scoped, now, "x", "x").length > 0)
        codes.push("selected_model_window_invalid")
    }

    return codes.length > 0 ? codes : [FALLBACK]
  } catch {
    return [FALLBACK]
  }
}

function openaiWindowCodes(v: unknown, now: number): string[] {
  const codes: string[] = []
  if (!isRecord(v)) return ["window_invalid"]
  if (!isPercent(own(v, "used_percent"))) codes.push("percent_invalid")
  if (!isPositiveInt(own(v, "limit_window_seconds")))
    codes.push("duration_invalid")
  const at = own(v, "reset_at")
  if (at !== undefined && at !== null) {
    if (typeof at !== "number" || !Number.isFinite(at) || !(at * 1000 > now))
      codes.push("reset_invalid")
  } else if (!isPositiveInt(own(v, "reset_after_seconds")))
    codes.push("reset_invalid")
  return codes
}

export function explainOpenAI(data: unknown, now: number): string[] {
  try {
    if (!isRecord(data)) return ["usage_not_object"]
    const codes: string[] = []

    if (own(data, "plan_type") !== "plus") codes.push("plan_not_plus")

    const extras = own(data, "additional_rate_limits")
    if (extras !== undefined && extras !== null) {
      if (!Array.isArray(extras) || extras.length > 0)
        codes.push("additional_limits_unsupported")
    }

    const spend = own(data, "spend_control")
    if (
      spend !== undefined &&
      spend !== null &&
      (!isRecord(spend) ||
        typeof own(spend, "reached") !== "boolean" ||
        own(spend, "reached") === true)
    )
      codes.push("spend_control_unverified")

    const rate = own(data, "rate_limit")
    if (!isRecord(rate)) {
      codes.push("rate_limit_missing")
      return codes
    }
    const allowed = own(rate, "allowed")
    const reached = own(rate, "limit_reached")
    const flagsValid =
      typeof allowed === "boolean" && typeof reached === "boolean"
    if (!flagsValid) codes.push("rate_limit_flags_invalid")

    const pw = own(rate, "primary_window")
    let anyExhausted = false
    let windowsOk = true
    if (!isRecord(pw)) {
      codes.push("primary_window_missing")
      windowsOk = false
    } else {
      const w = openaiWindowCodes(pw, now)
      if (w.includes("percent_invalid"))
        codes.push("primary_window_percent_invalid")
      if (w.includes("reset_invalid"))
        codes.push("primary_window_reset_invalid")
      if (w.includes("duration_invalid"))
        codes.push("primary_window_duration_invalid")
      if (w.length > 0) windowsOk = false
      else if ((own(pw, "used_percent") as number) >= 100) anyExhausted = true
    }

    const sec = own(rate, "secondary_window")
    if (sec !== undefined && sec !== null) {
      if (openaiWindowCodes(sec, now).length > 0) {
        codes.push("secondary_window_invalid")
        windowsOk = false
      } else if (isRecord(sec) && (own(sec, "used_percent") as number) >= 100)
        anyExhausted = true
    }

    if (flagsValid && windowsOk && !anyExhausted && allowed === reached)
      codes.push("rate_limit_flags_inconsistent")

    return codes.length > 0 ? codes : [FALLBACK]
  } catch {
    return [FALLBACK]
  }
}

function entropy(s: string): number {
  const counts = new Map<string, number>()
  for (const c of s) counts.set(c, (counts.get(c) ?? 0) + 1)
  let h = 0
  for (const n of counts.values()) {
    const p = n / s.length
    h -= p * Math.log2(p)
  }
  return h
}

function shapeKind(v: unknown): string {
  if (v === undefined) return "<missing>"
  if (typeof v !== "string") return "<invalid>"
  if (!/^[a-z_]{1,32}$/.test(v) || KIND_FORBIDDEN.test(v) || entropy(v) > 3.5)
    return "<redacted>"
  return v
}

function typeCode(v: unknown): string {
  if (v === null) return "null"
  if (Array.isArray(v)) return "array"
  switch (typeof v) {
    case "undefined":
      return "undefined"
    case "object":
      return "object"
    case "string":
      return "string"
    case "number":
      return "number"
    case "boolean":
      return "boolean"
    default:
      return "other"
  }
}

function anthropicLimitShapes(
  data: unknown,
): { kind: string; fields: Record<string, string> }[] | undefined {
  try {
    if (!isRecord(data)) return undefined
    const limits = own(data, "limits")
    if (!Array.isArray(limits)) return undefined
    return limits.slice(0, SHAPE_MAX).map((entry) => {
      if (!isRecord(entry)) return { kind: "<non_object>", fields: {} }
      return {
        kind: shapeKind(own(entry, "kind")),
        fields: Object.fromEntries(
          SHAPE_FIELDS.filter((f) =>
            Object.prototype.hasOwnProperty.call(entry, f),
          ).map((f) => [f, typeCode(entry[f])]),
        ),
      }
    })
  } catch {
    return undefined
  }
}

function safeStatus(response: Response): number | undefined {
  try {
    const s = response.status
    return typeof s === "number" && Number.isInteger(s) ? s : undefined
  } catch {
    return undefined
  }
}

export async function diagnoseQuota(
  ctx: AccountsContext,
  providerID: "anthropic" | "openai",
  deps: Dependencies,
): Promise<Diagnostic> {
  let auth: Awaited<ReturnType<typeof subscription>>
  try {
    auth = await subscription(ctx, providerID)
  } catch {
    return { outcome: "account_unavailable" }
  }
  if (!auth) return { outcome: "account_unavailable" }

  let response: Response
  try {
    const headers = new Headers({ authorization: `Bearer ${auth.access}` })
    if (providerID === "anthropic")
      headers.set("anthropic-beta", "oauth-2025-04-20")
    else headers.set("chatgpt-account-id", auth.accountID!)
    response = await deps.fetch(URLS[providerID], {
      method: "GET",
      headers,
      redirect: "error",
      signal: AbortSignal.timeout(5_000),
    })
  } catch (e) {
    let name: unknown
    try {
      name = (e as { name?: unknown } | undefined)?.name
    } catch {
      name = undefined
    }
    return {
      outcome:
        name === "TimeoutError" ? "timeout" : "transport_or_redirect_error",
    }
  }

  const status = safeStatus(response)
  const withStatus = status === undefined ? {} : { status }
  let ok = false
  try {
    ok = response.ok === true
  } catch {
    ok = false
  }
  if (!ok) return { outcome: "http_error", ...withStatus }

  let data: unknown
  try {
    data = await response.json()
  } catch {
    return { outcome: "json_decode_error", ...withStatus }
  }

  try {
    const now = deps.now()
    const proof =
      providerID === "anthropic"
        ? inspectAnthropicUsage(data, now, "claude-sonnet-5-5")
        : inspectOpenAIUsage(data, now, "gpt-6.1-sol")
    const limitShapes =
      providerID === "anthropic" ? anthropicLimitShapes(data) : undefined
    if (proof.quota.state === "available" || proof.quota.state === "exhausted")
      return {
        outcome: "proof_accepted",
        ...withStatus,
        state: proof.quota.state,
        billingState: proof.billing.state,
        ...(limitShapes ? { limitShapes } : {}),
      }
    return {
      outcome: "parser_reject",
      ...withStatus,
      billingState: proof.billing.state,
      ...(limitShapes ? { limitShapes } : {}),
      reasons:
        providerID === "anthropic"
          ? explainAnthropic(data, now)
          : explainOpenAI(data, now),
    }
  } catch {
    return { outcome: "parser_reject", ...withStatus, reasons: [FALLBACK] }
  }
}
