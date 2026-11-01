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
  // How Quota 6 names this login's rows, its export having no connection ID:
  // the login's label when no other login of the integration carries it, and
  // whether it is the integration's only subscription login.
  label?: string
  sole?: boolean
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

// Quota checks a provider when something asks (the TUI's sidebar, /quota, a
// model turn, a limit), at most every providers.checking.minIntervalMs (two
// minutes here, five by default). This allows the default and a missed check.
export const QUOTA_MAX_AGE_MS = 6 * 60_000

// No step of a role's route could launch at all, whatever Quota says.
export const REASON_NO_STEP =
  "No step of the route has an approved subscription OAuth connection and a catalog model with the required status, tools, variant, and limits."
// Every step that could launch is a group Antigravity's plugin would refuse.
export const REASON_ALL_SPENT =
  "Every included quota the route can use is exhausted, and its Antigravity groups are refused by their plugin until they reset; no last resort is left."

const m = (providerID: string, id: string, variant?: string): ModelRef =>
  variant === undefined ? { id, providerID } : { id, providerID, variant }

const opus = (variant: string) => m("anthropic", "claude-opus-5-5", variant)
const sonnet = (variant: string) => m("anthropic", "claude-sonnet-5-5", variant)
const haiku = (variant: string) => m("anthropic", "claude-haiku-5-5", variant)
const sol = (variant: string) => m("openai", "gpt-6.1-sol", variant)
const luna = (variant: string) => m("openai", "gpt-6-luna", variant)
// The xAI subscription's weekly pool; retrieval is the work that fits it.
const grok = (variant: string) => m("xai", "grok-4.7", variant)
// Fast mode: the same model with priority processing, 2.5x the included
// usage. Only for explore-spark, a short lookup the parent waits for.
const lunaFast = (variant: string) => m("openai", "gpt-6-luna-fast", variant)

export const ROUTES: Readonly<Record<string, Route>> = Object.freeze(
  Object.fromEntries(
    Object.entries({
      "explore-max": { primary: sol("xhigh"), alternate: opus("xhigh") },
      "explore-high": { primary: sol("high"), alternate: sonnet("high") },
      "explore-medium": { primary: sol("medium"), alternate: sonnet("medium") },
      reviewer: { primary: sonnet("medium"), alternate: sol("medium") },
      worker: { primary: sonnet("low"), alternate: sol("low") },
      "worker-deep": { primary: sonnet("high"), alternate: sol("high") },
      "explore-spark": { primary: lunaFast("low"), alternate: haiku("low") },
      "explore-small": { primary: luna("low"), alternate: haiku("low") },
      verifier: { primary: luna("low"), alternate: haiku("low") },
      debugger: { primary: sol("high"), alternate: opus("high") },
      "reviewer-deep": { primary: sol("high"), alternate: opus("high") },
      "searcher-deep": { primary: grok("medium"), alternate: sol("medium") },
      searcher: { primary: grok("low"), alternate: sol("low") },
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

// A route model on a saved Claude login: its alias.
export const aliasOf = (
  model: ModelRef,
  login: string | undefined,
): ModelRef =>
  login === undefined ? model : { ...model, id: `${model.id}-${login}` }

// The native subscription logins, by the OAuth method each provider's
// built-in plugin registers. An API key never qualifies. Google's is the
// Antigravity plugin's login (ANTIGRAVITY_PROVIDER).
export const METHODS: Readonly<Record<string, readonly string[]>> = {
  anthropic: ["claude-max"],
  openai: ["chatgpt-browser", "chatgpt-headless"],
  xai: ["device"],
  google: ["antigravity"],
}

// Antigravity runs through its plugin's own fetch, not a transport this
// plugin checks: its launches carry no subscription marker, as a lane's.
export const ANTIGRAVITY_PROVIDER = "google"

export function approved(
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

// Providers whose catalog publishes one budget for input and output (the
// output limit equals the context) instead of reserving the output.
const SHARED_BUDGET = new Set(["xai"])

// Tokens a first request may carry: the context less the reserved output, or
// the whole context on a shared budget.
export function inputCapacity(limit: CatalogModel["limit"]): number {
  if (limit.output > limit.context) return 0
  const reserved =
    limit.output === limit.context ? limit.context : limit.context - limit.output
  return Math.min(limit.input ?? Infinity, reserved)
}

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
  if (limit.context === limit.output) return SHARED_BUDGET.has(model.providerID)
  return limit.context > limit.output
}

// How a launch weighs one subscription place of a step: a launch, a launch
// only as the last resort (Quota knows its window spent), or none (no
// approved login, or no usable catalog entry). Missing or stale data is no
// reason to pass a place over.
export function weigh(input: {
  model: ModelRef
  account: AccountProof | undefined
  quota: QuotaProof
  catalog: CatalogModel[]
  now: number
}): "launch" | "spent" | "unusable" {
  const { model, account, quota, catalog, now } = input
  if (!approved(account, model.providerID)) return "unusable"
  if (!catalogOk(catalog, model)) return "unusable"
  return freshState(quota, now) === "exhausted" ? "spent" : "launch"
}
