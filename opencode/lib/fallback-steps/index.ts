import { STEPS_RPC } from "@craftsamo/opencode-model-fallback/rpc"
import { EmptyLanes } from "./empty-lanes"
import { readOptions } from "./options"
import { defaultDeps, type StepsDeps } from "./deps"
import { createLimit } from "./limit"
import { holdLimits } from "./limited"
import type { StepsContext } from "./runtime"
import { createUsable } from "./usable"
import { Windows } from "./windows"

/**
 * Answers the model fallback's questions (@craftsamo/opencode-model-fallback)
 * with what only dotconfig knows: Quota, the credit lanes' balance estimate
 * and the active logins; and holds the windows its limits spend.
 */
export async function setupFallbackSteps(
  ctx: StepsContext,
  deps: StepsDeps = defaultDeps,
): Promise<() => Promise<void>> {
  const { creditLanes } = readOptions(ctx.options)
  const empty = new EmptyLanes()
  if (creditLanes.length > 0)
    empty.restore(deps.saved?.load() ?? {}, deps.now())
  const keep = () => {
    deps.saved?.save({ cooldowns: {}, ...empty.saved(deps.now()) })
  }
  const windows = new Windows()
  const registration = await ctx.rpc.register(STEPS_RPC, {
    usable: createUsable(ctx, {
      deps,
      creditLanes,
      empty,
      keep,
      windows,
    }),
    limit: createLimit({ deps, creditLanes, empty, keep }),
  })
  const unsubscribe = holdLimits(ctx, {
    deps,
    creditLanes,
    windows,
  })
  return async () => {
    unsubscribe()
    await registration.dispose()
  }
}

export default { id: "dotconfig.fallback-steps", setup: setupFallbackSteps }
