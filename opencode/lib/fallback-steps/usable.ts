import type {
  StepsUsableInput,
  StepsUsableOutput,
} from "@craftsamo/opencode-model-fallback/rpc"
import type { ModelRef } from "./models"
import { familyName } from "../credit-lanes/antigravity"
import { subscription, type Subscription } from "./accounts"
import type { EmptyLanes } from "./empty-lanes"
import {
  ANTIGRAVITY_PROVIDER,
  freshState,
  type QuotaProof,
} from "./policy"
import {
  antigravityFamily,
  antigravityKey,
  antigravityReserve,
  CUSTOM_PROVIDERS,
  loadQuotaExport,
  readAntigravity,
  readQuota,
  SpentWindows,
} from "./quota"
import { QuotaRefresher } from "./quota-refresh"
import type { StepsDeps } from "./deps"
import type { StepsContext } from "./runtime"
import { activeLogin } from "./active"
import { LOGIN_NAMES } from "./names"
import { parseStep } from "./step"
import { windowOf, type Windows } from "./windows"

// An answer never waits for Quota's check; this long it does, for a check that
// answers at once.
export const REFRESH_GRACE_MS = 25

const refused = (reason: string): StepsUsableOutput => ({
  usable: false,
  reason,
})

const spentReason = (
  who: string,
  quota: QuotaProof,
  now: number,
): string | undefined => {
  if (freshState(quota, now) !== "exhausted") return undefined
  const until =
    quota.resetAt === undefined
      ? ""
      : ` until ${new Date(quota.resetAt).toISOString()}`
  return `${who} has no included quota left${until}`
}

// The active login of a provider, looked up once for a question.
type ActiveLogin = (providerID: string) => Promise<Subscription | undefined>

// The decision on one step: the first reason to pass it over
// (a window a limit held spent, credit lane known empty,
// subscription or Antigravity group spent or without an approved login),
// else usable. What the fallback package covers itself (the route walk, the
// catalog, cooldowns) is not here.
export function createUsable(
  ctx: StepsContext,
  state: {
    deps: StepsDeps
    creditLanes: readonly string[]
    // Lanes the balance estimate knows are empty, tried once a day.
    empty: EmptyLanes
    // Saves the daily tries for a restart.
    keep: () => void
    // Windows the `limited` events hold spent (limited.ts).
    windows: Windows
  },
): (input: StepsUsableInput) => Promise<StepsUsableOutput> {
  const { deps, creditLanes, empty, keep, windows } = state
  const spent = new SpentWindows()
  const refresher = new QuotaRefresher()

  // The package launches or moves on the first step not refused, so a lane
  // passed for its daily try is tried.
  const laneReason = (provider: string): string | undefined => {
    const now = deps.now()
    const { skip, due } = empty.scan(deps.readLanes?.(), now)
    if (skip.has(provider))
      return "its credit balance is known empty; it is tried once a day"
    if (due.has(provider)) {
      empty.tried(provider, now)
      keep()
    }
    return undefined
  }

  // The export as it stands. Rows stale for the provider ask Quota to check
  // them, in the background: the answer waits a moment for a check that
  // answers at once, never for one that does not.
  const exported = async (providerID: string): Promise<unknown> => {
    const read = await loadQuotaExport(deps, deps.exportFile)
    const providers = [
      providerID === ANTIGRAVITY_PROVIDER ? CUSTOM_PROVIDERS : providerID,
    ]
    let timer: ReturnType<typeof setTimeout> | undefined
    const grace = new Promise<unknown>((resolve) => {
      timer = setTimeout(resolve, REFRESH_GRACE_MS, read)
    })
    const checked = refresher
      .fresh(ctx, deps, deps.exportFile, read, providers)
      .catch(() => read)
    try {
      return await Promise.race([checked, grace])
    } finally {
      clearTimeout(timer)
    }
  }

  const subscriptionReason = async (
    model: ModelRef,
    active: ActiveLogin,
  ): Promise<string | undefined> => {
    const name = LOGIN_NAMES[model.providerID]
    const auth = await active(model.providerID)
    if (!auth) return `no approved ${name} login`
    const { proof } = auth
    const now = deps.now()
    const quota = spent.recall(
      proof,
      readQuota(await exported(model.providerID), proof, now),
      now,
    )
    return spentReason(
      `the active ${name} login`,
      quota,
      now,
    )
  }

  const antigravityReason = async (
    model: ModelRef,
  ): Promise<string | undefined> => {
    const family = antigravityFamily(model)
    if (!family) return undefined
    const auth = await subscription(ctx, ANTIGRAVITY_PROVIDER)
    if (!auth) return "no approved Antigravity login"
    // Antigravity's quota is per group of models, not per login.
    const proof = {
      ...auth.proof,
      connectionID: `${auth.proof.connectionID}#${antigravityKey(model)}`,
    }
    const now = deps.now()
    const quota = spent.recall(
      proof,
      readAntigravity(
        await exported(ANTIGRAVITY_PROVIDER),
        model,
        now,
        (deps.antigravityReserve ?? antigravityReserve)(),
      ),
      now,
    )
    return spentReason(`Antigravity ${familyName(family)}`, quota, now)
  }

  // A window a limit held spent comes before anything Quota or the lanes'
  // estimate know of it.
  const heldReason = async (
    model: ModelRef,
  ): Promise<string | undefined> => {
    if (windows.empty) return undefined
    const window = await windowOf(model, {
      creditLanes,
    })
    const until = window && windows.heldUntil(window.key, deps.now())
    return until === undefined
      ? undefined
      : `${window!.name} hit a limit until ${new Date(until).toISOString()}`
  }

  const reasonFor = async (
    model: ModelRef,
    active: ActiveLogin,
  ): Promise<string | undefined> => {
    const held = await heldReason(model)
    if (held) return held
    if (creditLanes.includes(model.providerID))
      return laneReason(model.providerID)
    if (model.providerID === ANTIGRAVITY_PROVIDER)
      return antigravityReason(model)
    if (Object.hasOwn(LOGIN_NAMES, model.providerID))
      return subscriptionReason(model, active)
    return undefined
  }

  // Never breaks a launch: only an explicit reason refuses a step.
  return async ({ model: step }) => {
    try {
      const model = parseStep(step)
      const logins = new Map<string, Promise<Subscription | undefined>>()
      const active: ActiveLogin = (providerID) => {
        if (!logins.has(providerID))
          logins.set(providerID, activeLogin(ctx, providerID))
        return logins.get(providerID)!
      }
      const reason = model && (await reasonFor(model, active))
      return reason ? refused(reason) : { usable: true }
    } catch {
      return { usable: true }
    }
  }
}
