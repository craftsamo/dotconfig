import {
  LIMITED_EVENT,
  LIMITS_RPC,
} from "@craftsamo/opencode-model-fallback/rpc"
import type { ClaudeAccount } from "../claude-logins/accounts"
import { OAUTH_PROVIDER } from "../claude-logins/models"
import { activeLogin } from "./active"
import type { StepsDeps } from "./deps"
import type { StepsContext } from "./runtime"
import { parseStep } from "./step"
import { windowOf, type Windows } from "./windows"

// Holds the window of every model the fallback announces a limit on, until
// the end the limit gave. Returns the unsubscribe. A handler that throws ends
// its subscription, and an event off the schema holds nothing, so nothing
// escapes. Without RPC events there is no subscription.
export function holdLimits(
  ctx: StepsContext,
  state: {
    deps: StepsDeps
    creditLanes: readonly string[]
    accounts: readonly ClaudeAccount[]
    windows: Windows
  },
): () => void {
  const { deps, creditLanes, accounts, windows } = state
  try {
    return ctx.rpc(LIMITS_RPC).events.on(LIMITED_EVENT, async (envelope) => {
      try {
        const { model: step, until: end } = envelope.data ?? {}
        const until = typeof end === "string" ? Date.parse(end) : NaN
        const model = typeof step === "string" ? parseStep(step) : undefined
        if (!model || !Number.isFinite(until)) return
        const window = await windowOf(model, {
          creditLanes,
          accounts,
          activeLabel: async () =>
            (await activeLogin(ctx, OAUTH_PROVIDER).catch(() => undefined))
              ?.proof.label,
        })
        if (window) windows.hold(window.key, until, deps.now())
      } catch {}
    })
  } catch {
    return () => {}
  }
}
