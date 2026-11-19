import { STEPS_RPC } from "@craftsamo/opencode-model-fallback/rpc"
import { AccountRouter } from "../claude-logins/accounts"
import { EmptyLanes } from "../subagent-fallback/empty-lanes"
import { readOptions } from "../subagent-fallback/options"
import { defaultDeps, type StepsDeps } from "./deps"
import type { StepsContext } from "./runtime"
import { createUsable } from "./usable"

// Answers the model fallback's questions (@craftsamo/opencode-model-fallback)
// with what only dotconfig knows: Quota, the credit lanes' balance estimate
// and the saved Claude logins.
export async function setupFallbackSteps(
  ctx: StepsContext,
  deps: StepsDeps = defaultDeps,
): Promise<() => Promise<void>> {
  const { creditLanes, claudeAccounts } = readOptions(ctx.options)
  // A malformed `claudeAccounts` is kept, not thrown: its Claude steps are
  // refused instead of running on the active login.
  const accounts = AccountRouter.fromOption(claudeAccounts)
  const empty = new EmptyLanes()
  if (creditLanes.length > 0)
    empty.restore(deps.saved?.load() ?? {}, deps.now())
  const keep = () => {
    deps.saved?.save({ cooldowns: {}, ...empty.saved(deps.now()) })
  }
  const registration = await ctx.rpc.register(STEPS_RPC, {
    usable: createUsable(ctx, {
      deps,
      creditLanes,
      claudeAccounts: accounts,
      empty,
      keep,
    }),
    limit: async () => ({ limit: false }),
  })
  return () => registration.dispose()
}

export default { id: "dotconfig.fallback-steps", setup: setupFallbackSteps }
