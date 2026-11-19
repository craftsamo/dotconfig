import { AccountRouter } from "./accounts"
import { supported, type RuntimeContext } from "./runtime"

export type { RuntimeContext }

// Routes requests on alias models to the saved Claude login their suffix
// names (accounts.ts). Listed right after the Claude login plugin, whose
// rewrite it builds on, and before any plugin that checks the final request.
export async function setup(ctx: RuntimeContext): Promise<() => Promise<void>> {
  const router = AccountRouter.fromOption(ctx.options.claudeAccounts)
  if (!router.active) return async () => {}
  const registration = await ctx.session.hook("http.request", async (event) => {
    await router.route(ctx, event, supported(ctx.app.version))
  })
  return () => registration.dispose()
}

export default { id: "dotconfig.claude-logins", setup }
