export type ModelRef = {
  id: string
  providerID: string
  variant?: string
}

export type Route = {
  primary: ModelRef
  alternate: ModelRef
}

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
}

export type CatalogModel = {
  id: string
  providerID: string
  enabled: boolean
  status: string
  capabilities: { tools: boolean }
  variants: Array<{ id: string }>
  limit: { context: number; input?: number; output: number }
}

export type LaunchDecision =
  | { kind: "default" | "fallback" | "credits"; model: ModelRef }
  | { kind: "stop"; reason: string }

// Quota's default refresh is five minutes; allow the export's next UI refresh.
export const QUOTA_MAX_AGE_MS = 6 * 60_000

export const REASON_SOURCE_ACCOUNT =
  "The source provider account is missing or is not an approved subscription OAuth connection."
export const REASON_TARGET_ACCOUNT =
  "The alternate provider account is missing or is not an approved subscription OAuth connection."
export const REASON_CATALOG =
  "The selected model is not available in the catalog with the required status, tools, variant, and limits."

const m = (providerID: string, id: string, variant?: string): ModelRef =>
  variant === undefined ? { id, providerID } : { id, providerID, variant }

const opus = (variant: string) => m("anthropic", "claude-opus-5-5", variant)
const sonnet = (variant: string) => m("anthropic", "claude-sonnet-5-5", variant)
const haiku = (variant: string) => m("anthropic", "claude-haiku-5-5", variant)
const sol = (variant: string) => m("openai", "gpt-6.1-sol", variant)
const luna = (variant: string) => m("openai", "gpt-6-luna", variant)

export const ROUTES: Readonly<Record<string, Route>> = Object.freeze(
  Object.fromEntries(
    Object.entries({
      "explore-max": { primary: opus("xhigh"), alternate: sol("xhigh") },
      "explore-high": { primary: sonnet("high"), alternate: sol("high") },
      "explore-medium": { primary: sonnet("medium"), alternate: sol("medium") },
      reviewer: { primary: sonnet("medium"), alternate: sol("medium") },
      worker: { primary: sonnet("low"), alternate: sol("low") },
      "explore-spark": { primary: haiku("low"), alternate: luna("low") },
      "explore-small": { primary: luna("low"), alternate: haiku("low") },
      verifier: { primary: luna("low"), alternate: haiku("low") },
      debugger: { primary: sol("high"), alternate: opus("high") },
      "reviewer-deep": { primary: sol("high"), alternate: opus("high") },
      "searcher-deep": { primary: sol("medium"), alternate: sonnet("medium") },
      searcher: { primary: sol("low"), alternate: sonnet("low") },
    }).map(([agent, route]) => [
      agent,
      Object.freeze({
        primary: Object.freeze(route.primary),
        alternate: Object.freeze(route.alternate),
      }),
    ]),
  ),
)

export function modelsEqual(a: ModelRef, b: ModelRef): boolean {
  return (
    a.id === b.id && a.providerID === b.providerID && a.variant === b.variant
  )
}

// With pin, a role keeps its route even when the agent definition in effect
// (a project's own agent file, say) names another model or none at all.
export function routeForLaunch(
  input: { agent?: unknown; model?: unknown; sessionID?: unknown },
  configured: ModelRef | undefined,
  pin = false,
): Route | undefined {
  if (input.model !== undefined) return undefined
  if (input.sessionID !== undefined) return undefined
  if (typeof input.agent !== "string") return undefined
  if (!Object.hasOwn(ROUTES, input.agent)) return undefined
  const route = ROUTES[input.agent]
  if (pin) return route
  if (!configured) return undefined
  if (!modelsEqual(route.primary, configured)) return undefined
  return route
}

const METHODS: Record<string, readonly string[]> = {
  anthropic: ["claude-max"],
  openai: ["chatgpt-browser", "chatgpt-headless"],
}

function approved(
  account: AccountProof | undefined,
  providerID: string,
): boolean {
  if (!account) return false
  if (account.providerID !== providerID) return false
  if (
    typeof account.connectionID !== "string" ||
    account.connectionID.length === 0
  )
    return false
  if (account.type !== "oauth") return false
  if (!Object.hasOwn(METHODS, providerID)) return false
  return METHODS[providerID].includes(account.methodID)
}

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

const positive = (n: unknown): boolean =>
  typeof n === "number" && Number.isFinite(n) && n > 0

export function catalogOk(catalog: CatalogModel[], model: ModelRef): boolean {
  const found = catalog.find(
    (item) => item.id === model.id && item.providerID === model.providerID,
  )
  if (!found) return false
  if (found.enabled !== true) return false
  if (found.status !== "active") return false
  if (found.capabilities?.tools !== true) return false
  if (
    model.variant !== undefined &&
    !found.variants.some((v) => v.id === model.variant)
  )
    return false
  const limit = found.limit
  if (!limit || !positive(limit.context) || !positive(limit.output))
    return false
  if (limit.input !== undefined && !positive(limit.input)) return false
  return limit.context > limit.output
}

export function decideLaunch(input: {
  route: Route
  source: {
    account: AccountProof | undefined
    quota: QuotaProof
  }
  target:
    | {
        account: AccountProof | undefined
        quota: QuotaProof
      }
    | undefined
  catalog: CatalogModel[]
  now: number
}): LaunchDecision {
  const { route, source, target, catalog, now } = input
  const stop = (reason: string): LaunchDecision => ({ kind: "stop", reason })

  if (!approved(source.account, route.primary.providerID))
    return stop(REASON_SOURCE_ACCOUNT)
  const sourceState = freshState(source.quota, now)
  if (sourceState !== "exhausted") {
    if (!catalogOk(catalog, route.primary)) return stop(REASON_CATALOG)
    return { kind: "default", model: route.primary }
  }

  const targetAccountOk =
    !!target && approved(target.account, route.alternate.providerID)
  const targetState = target ? freshState(target.quota, now) : undefined
  if (targetState === "exhausted") {
    // No independent credit balance check. Native OAuth/provider behavior
    // decides whether the usual model can proceed; this is an attempt, not
    // billing proof.
    if (!catalogOk(catalog, route.primary)) return stop(REASON_CATALOG)
    return { kind: "credits", model: route.primary }
  }
  // The source is known empty; an alternate that isn't known empty is the
  // better bet, even when its own data is missing or stale.
  if (!targetAccountOk) {
    if (targetState) return stop(REASON_TARGET_ACCOUNT)
    if (!catalogOk(catalog, route.primary)) return stop(REASON_CATALOG)
    return { kind: "default", model: route.primary }
  }
  if (!catalogOk(catalog, route.alternate)) return stop(REASON_CATALOG)
  return { kind: "fallback", model: route.alternate }
}
