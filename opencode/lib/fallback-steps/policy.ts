import { CLAUDE_METHODS } from "../claude-logins/models"

export type QuotaProof = {
  state: "available" | "exhausted" | "unknown"
  observedAt: number
  resetAt?: number
  reason?: string
}

export type AccountProof = {
  connectionID: string
  providerID: string
  methodID: string
  type: "oauth"
  // How Quota 6 names this login's rows, its export having no connection ID:
  // the login's label when no other login of the integration carries it, and
  // whether it is the integration's only subscription login.
  label?: string
  sole?: boolean
}

// Quota checks a provider when something asks (the TUI's sidebar, /quota, a
// model turn, a limit), at most every providers.checking.minIntervalMs (two
// minutes here, five by default). This allows the default and a missed check.
export const QUOTA_MAX_AGE_MS = 6 * 60_000

// The native subscription logins, by the OAuth method each provider's
// built-in plugin registers. An API key never qualifies. Google's is the
// Antigravity plugin's login (ANTIGRAVITY_PROVIDER).
export const METHODS: Readonly<Record<string, readonly string[]>> = {
  anthropic: CLAUDE_METHODS,
  openai: ["chatgpt-browser", "chatgpt-headless"],
  xai: ["device"],
  google: ["antigravity"],
}

export const ANTIGRAVITY_PROVIDER = "google"

export function freshState(
  quota: QuotaProof,
  now: number,
): "available" | "exhausted" | undefined {
  if (!Number.isFinite(quota.observedAt) || !Number.isFinite(now))
    return undefined
  const age = now - quota.observedAt
  if (age < 0) return undefined
  if (quota.state === "exhausted") {
    // A window can't recover before its reset, however old the observation.
    if (quota.resetAt !== undefined)
      return Number.isFinite(quota.resetAt) && quota.resetAt > now
        ? "exhausted"
        : undefined
    return age <= QUOTA_MAX_AGE_MS ? "exhausted" : undefined
  }
  if (age > QUOTA_MAX_AGE_MS) return undefined
  if (quota.state === "available") return "available"
  return undefined
}
