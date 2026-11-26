import { appendFileSync } from "node:fs"
import { ANTIGRAVITY_PROVIDER } from "../fallback-steps/policy"
import { isAntigravity, neutralizeSystem, type SystemPart } from "./signature"

type Registration = { dispose(): Promise<void> }
type RequestEvent = {
  readonly sessionID: string
  readonly model: { providerID: string; id: string; variant?: string }
  system: SystemPart[]
}
type GuardContext = {
  session: {
    hook(
      name: "context" | "compaction" | "generate" | "title",
      callback: (event: RequestEvent) => void | Promise<void>,
      options?: { providerID?: string },
    ): Promise<Registration>
  }
}

const REQUEST_KINDS = ["context", "compaction", "generate", "title"] as const

/** Avoid Google's fake quota refusal for Code Mode system prompts (#622). */
export async function setupAntigravityGuard(
  ctx: GuardContext,
): Promise<() => Promise<void>> {
  const registrations: Registration[] = []
  for (const kind of REQUEST_KINDS) {
    const registration = await ctx.session.hook(
      kind,
      (event) => {
        if (!isAntigravity(event.model)) return
        const replaced = neutralizeSystem(event.system)
        const path = process.env.ANTIGRAVITY_GUARD_LOG
        if (!path) return
        try {
          appendFileSync(
            path,
            JSON.stringify({
              at: new Date().toISOString(),
              kind,
              model: `${event.model.providerID}/${event.model.id}`,
              replaced,
            }) + "\n",
          )
        } catch {}
      },
      { providerID: ANTIGRAVITY_PROVIDER },
    )
    registrations.push(registration)
  }
  return async () => {
    await Promise.all(registrations.map((registration) => registration.dispose()))
  }
}

export default { id: "dotconfig.antigravity-guard", setup: setupAntigravityGuard }
