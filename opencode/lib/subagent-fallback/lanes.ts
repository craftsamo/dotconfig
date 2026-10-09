import {
  catalogOk,
  type CatalogModel,
  type ModelRef,
  type Route,
} from "./policy"

// Console credit lanes: API-key providers that spend the monthly credits a Max
// plan grants. They sit beside the subscription (OAuth) provider.
//   subagents: lanes first, then the subscription (then the usual preflight)
//   primary:   the subscription first, then lanes; on a lane, the other lanes
//              first and the subscription last
export const OAUTH_PROVIDER = "anthropic"
export const DEFAULT_COOLDOWN_MS = 60 * 60_000
// Moves of one session within this window never revisit a provider.
export const EPISODE_TTL_MS = 5 * 60_000
// Same threshold as the retry override for protected children.
export const LONG_WAIT_MS = 10_000
// Agents whose requests run on a model of their own, not the session's.
export const SIDE_AGENTS: ReadonlySet<string> = new Set([
  "compaction",
  "title",
  "summary",
])

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
export type Role = "subagent" | "primary"

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

// A lane that failed is skipped for a while. There is no balance API, so the
// first request after the cooldown is the probe: an empty lane fails fast
// (before any generation) and is marked again.
export class Lanes {
  private until = new Map<string, number>()
  constructor(
    readonly ids: readonly string[],
    private cooldownMs: number,
    private now: () => number,
  ) {}
  has(id: string): boolean {
    return this.ids.includes(id)
  }
  // forMs shortens the block (a window limit that says when it resets); it
  // never exceeds the cooldown.
  mark(id: string, forMs?: number): void {
    if (!this.has(id)) return
    const ms =
      forMs !== undefined && Number.isFinite(forMs) && forMs > 0
        ? Math.min(forMs, this.cooldownMs)
        : this.cooldownMs
    this.until.set(id, this.now() + ms)
  }
  blocked(id: string): boolean {
    const until = this.until.get(id)
    if (until === undefined) return false
    if (until <= this.now()) {
      this.until.delete(id)
      return false
    }
    return true
  }
}

// Providers one session has already failed on recently, so a chain that
// cycles (subscription -> lane -> subscription) cannot loop.
export class Episodes {
  private map = new Map<string, { at: number; tried: Set<string> }>()
  constructor(
    private ttlMs: number,
    private now: () => number,
    private max = 256,
  ) {}
  record(sessionID: string, providerID: string): ReadonlySet<string> {
    const now = this.now()
    let entry = this.map.get(sessionID)
    if (!entry || now - entry.at > this.ttlMs)
      entry = { at: now, tried: new Set() }
    entry.at = now
    entry.tried.add(providerID)
    this.map.delete(sessionID)
    this.map.set(sessionID, entry)
    while (this.map.size > this.max)
      this.map.delete(this.map.keys().next().value as string)
    return entry.tried
  }
}

// The same model on another provider. A variant the target lacks (the
// "default" label, for one) is dropped rather than refusing the move.
export function retarget(
  model: ModelRef,
  providerID: string,
  catalog: CatalogModel[],
): ModelRef | undefined {
  if (model.variant !== undefined) {
    const same = { id: model.id, providerID, variant: model.variant }
    if (catalogOk(catalog, same)) return same
  }
  const bare = { id: model.id, providerID }
  return catalogOk(catalog, bare) ? bare : undefined
}

export function nextModel(input: {
  current: ModelRef
  role: Role
  lanes: Lanes
  tried: ReadonlySet<string>
  catalog: CatalogModel[]
}): ModelRef | undefined {
  const { current, role, lanes, tried, catalog } = input
  // Credits stay ahead of the subscription for a specialist, and for any
  // session already on a lane: the subscription is then the last stop. Only a
  // primary still on the subscription goes to the lanes after it.
  const chain =
    role === "subagent" || lanes.has(current.providerID)
      ? [...lanes.ids, OAUTH_PROVIDER]
      : [OAUTH_PROVIDER, ...lanes.ids]
  for (const id of chain) {
    if (tried.has(id) || lanes.blocked(id)) continue
    const target = retarget(current, id, catalog)
    if (target) return target
  }
  return undefined
}

// The first lane that is not known empty, for a new launch. The role's own
// variant must exist on the lane: a launch never changes it silently.
export function launchLane(
  route: Route,
  lanes: Lanes,
  catalog: CatalogModel[],
): ModelRef | undefined {
  if (route.primary.providerID !== OAUTH_PROVIDER) return undefined
  for (const id of lanes.ids) {
    if (lanes.blocked(id)) continue
    const model = { ...route.primary, providerID: id }
    if (catalogOk(catalog, model)) return model
  }
  return undefined
}
