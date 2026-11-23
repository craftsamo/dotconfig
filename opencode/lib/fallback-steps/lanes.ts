// Rate-limit retries above this wait count as quota limits.
export const LONG_WAIT_MS = 10_000

export type RetryError = {
  type: string
  status?: number
  message: string
  response?: { body?: string }
}
export type Decision = { retry: false } | { retry: true; delay: number }
// credit: the org's balance is empty. auth: the key is invalid or expired.
// quota: a window limit, i.e. a rate limit that asks for a long wait.
export type Failure = "credit" | "auth" | "quota"

export function classify(
  error: RetryError,
  decision: Decision,
): Failure | undefined {
  // The Anthropic API reports an empty balance as a plain 400, so only the
  // text tells it from any other invalid request.
  const text = `${error.message}\n${error.response?.body ?? ""}`
  if (error.status === 400 && /credit balance is too low/i.test(text))
    return "credit"
  if (
    error.type === "provider.auth" ||
    error.status === 401 ||
    error.status === 403
  )
    return "auth"
  if (error.type === "provider.quota") return "quota"
  if (
    (error.type === "provider.rate-limit" || error.status === 429) &&
    decision.retry &&
    decision.delay > LONG_WAIT_MS
  )
    return "quota"
  return undefined
}

// Antigravity's plugin turns a spent group into a plain error of its own
// (OpenCode sees provider.unknown, no status), after waiting out any limit
// of up to five minutes: its quota protection ("Quota protection: All 1
// account(s) are over 90% usage for gemini. Quota resets in 2h 30m.") or
// every account rate-limited ("All 1 account(s) rate-limited for claude.
// Quota resets in 12m 5s."). The wait it gives, in ms (undefined when it
// gives none), or null when the error is not one of these.
export function antigravityLimit(error: RetryError): number | undefined | null {
  const text = error.message
  if (
    !/^Quota protection: All \d+ account\(s\) are over/.test(text) &&
    !/^All \d+ account\(s\) rate-limited for /.test(text)
  )
    return null
  const wait = /Quota resets in ((?:\d+(?:ms|h|m|s)\s*)+)\./.exec(text)?.[1]
  if (!wait) return undefined
  const unit: Record<string, number> = {
    ms: 1,
    s: 1000,
    m: 60_000,
    h: 3_600_000,
  }
  let ms = 0
  for (const [, n, u] of wait.matchAll(/(\d+)(ms|h|m|s)/g))
    ms += Number(n) * unit[u]
  return ms > 0 ? ms : undefined
}
