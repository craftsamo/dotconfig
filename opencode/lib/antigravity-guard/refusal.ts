import { antigravityLimit } from "../fallback-steps/lanes"

export type RefusalInput = {
  type?: string
  status?: number
  message: string
  body?: string
}
export type Refusal = "tos" | "refused"

/**
 * The signature filter's fake 429s and retry loops have led to ToS
 * suspensions; do not treat these refusals as quota retries (#622 / #629).
 */
export function antigravityRefusal(error: RefusalInput): Refusal | null {
  if (
    antigravityLimit({
      type: error.type ?? "",
      status: error.status,
      message: error.message,
    }) !== null
  )
    return null
  const text = `${error.message}\n${error.body ?? ""}`
  if (/TOS_VIOLATION|violation of Terms of Service/i.test(text)) return "tos"
  if (
    error.status === 403 ||
    /SUBSCRIPTION_REQUIRED|PERMISSION_DENIED/.test(text)
  )
    return "refused"
  if (
    (error.status === 429 || /RESOURCE_EXHAUSTED/.test(text)) &&
    !/quota_?metric|quotaMetric|RetryInfo|retryDelay/i.test(text)
  )
    return "refused"
  return null
}
