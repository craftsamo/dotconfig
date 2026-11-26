import type {
  StepsLimitInput,
  StepsLimitOutput,
} from "@craftsamo/opencode-model-fallback/rpc"
import { antigravityRefusal } from "../antigravity-guard/refusal"
import type { EmptyLanes } from "./empty-lanes"
import {
  antigravityLimit,
  classify,
  type RetryError,
} from "./lanes"
import { ANTIGRAVITY_PROVIDER } from "./policy"
import type { StepsDeps } from "./deps"
import { parseStep } from "./step"

// A lane whose key was refused is passed over this long; the package cools an
// empty one for its own `cooldown_ms`.
export const KEY_REFUSED_WAIT_MS = 15 * 60_000
// Antigravity states how long its quota is protected; never pass it over
// longer than this, or for this long when it states none.
export const ANTIGRAVITY_MAX_WAIT_MS = 60 * 60_000
/** A ToS suspension needs an appeal; do not keep knocking. */
export const ANTIGRAVITY_TOS_WAIT_MS = 24 * 60 * 60_000
// Requests in flight report an empty balance together: one checkpoint a
// minute per lane.
const CHECKPOINT_EVERY_MS = 60_000

const NO_LIMIT: StepsLimitOutput = { limit: false }

/**
 * The package's own rule takes a quota error or a long rate limit for a
 * limit. What it asks here is the rest: a lane's empty balance or refused
 * key, and Antigravity's request refusals or quota protection of a spent group.
 */
export function createLimit(state: {
  deps: StepsDeps
  creditLanes: readonly string[]
  // Lanes the balance estimate knows are empty.
  empty: EmptyLanes
  // Saves the lanes' tries and refusals for a restart.
  keep: () => void
}): (input: StepsLimitInput) => Promise<StepsLimitOutput> {
  const { deps, creditLanes, empty, keep } = state
  const checkpoints = new Map<string, number>()

  // An empty balance is the one exact reading the balance estimate gets
  // without the Console (lib/credit-lanes).
  const creditEmpty = (provider: string) => {
    const now = deps.now()
    empty.refused(provider, now)
    keep()
    if (now - (checkpoints.get(provider) ?? -Infinity) < CHECKPOINT_EVERY_MS)
      return
    checkpoints.set(provider, now)
    void Promise.resolve()
      .then(() => deps.creditEmpty?.(provider))
      .catch(() => {})
  }

  return async ({ model: step, error }) => {
    try {
      const model = parseStep(step)
      if (!model) return NO_LIMIT
      const failure: RetryError = {
        type: error.type,
        status: error.status,
        message: error.message,
        ...(error.body === undefined ? {} : { response: { body: error.body } }),
      }
      if (creditLanes.includes(model.providerID)) {
        const kind = classify(failure, { retry: false })
        if (kind === "credit") {
          creditEmpty(model.providerID)
          return { limit: true, reason: "its credit balance is too low" }
        }
        if (kind === "auth")
          return {
            limit: true,
            wait_ms: KEY_REFUSED_WAIT_MS,
            reason: "its key was refused",
          }
        return NO_LIMIT
      }
      if (model.providerID === ANTIGRAVITY_PROVIDER) {
        const refusal = antigravityRefusal({
          type: error.type,
          status: error.status,
          message: error.message,
          body: error.body,
        })
        if (refusal === "tos")
          return {
            limit: true,
            wait_ms: ANTIGRAVITY_TOS_WAIT_MS,
            reason: "Antigravity suspended the account (Terms of Service)",
          }
        if (refusal === "refused")
          return {
            limit: true,
            wait_ms: ANTIGRAVITY_MAX_WAIT_MS,
            reason: "Antigravity refused the request",
          }
        const wait = antigravityLimit(failure)
        if (wait === null) return NO_LIMIT
        return {
          limit: true,
          wait_ms: Math.min(
            wait ?? ANTIGRAVITY_MAX_WAIT_MS,
            ANTIGRAVITY_MAX_WAIT_MS,
          ),
          reason: "Antigravity quota protection",
        }
      }
      return NO_LIMIT
    } catch {
      return NO_LIMIT
    }
  }
}
