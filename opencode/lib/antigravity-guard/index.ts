import { appendFileSync } from "node:fs"
import type { Decision } from "../fallback-steps/lanes"
import { ANTIGRAVITY_PROVIDER } from "../fallback-steps/policy"
import { antigravityRefusal } from "./refusal"
import { isAntigravity, neutralizeSystem, type SystemPart } from "./signature"

type Registration = { dispose(): Promise<void> }
type RequestEvent = {
  readonly sessionID: string
  readonly model: { providerID: string; id: string; variant?: string }
  system: SystemPart[]
}
type RetryEvent = {
  readonly sessionID: string
  readonly agent: string
  readonly model: RequestEvent["model"]
  readonly error: { type: string; message: string; status?: number }
  readonly attempt: number
  decision: Decision
}
type GuardContext = {
  session: {
    hook(
      name: "retry",
      callback: (event: RetryEvent) => void | Promise<void>,
      options?: { providerID?: string },
    ): Promise<Registration>
    hook(
      name: "context" | "compaction" | "generate" | "title",
      callback: (event: RequestEvent) => void | Promise<void>,
      options?: { providerID?: string },
    ): Promise<Registration>
  }
}

const REQUEST_KINDS = ["context", "compaction", "generate", "title"] as const

function log(entry: Record<string, unknown>) {
  const path = process.env.ANTIGRAVITY_GUARD_LOG
  if (!path) return
  try {
    appendFileSync(
      path,
      JSON.stringify({ at: new Date().toISOString(), ...entry }) + "\n",
    )
  } catch {}
}

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
        log({
          kind,
          model: `${event.model.providerID}/${event.model.id}`,
          replaced,
        })
      },
      { providerID: ANTIGRAVITY_PROVIDER },
    )
    registrations.push(registration)
  }
  registrations.push(
    await ctx.session.hook(
      "retry",
      (event) => {
        if (!isAntigravity(event.model)) return
        const refusal = antigravityRefusal(event.error)
        if (!refusal) return
        event.decision = { retry: false }
        log({
          kind: "retry",
          model: `${event.model.providerID}/${event.model.id}`,
          refusal,
          status: event.error.status,
        })
      },
      { providerID: ANTIGRAVITY_PROVIDER },
    ),
  )
  return async () => {
    await Promise.all(registrations.map((registration) => registration.dispose()))
  }
}

export default { id: "dotconfig.antigravity-guard", setup: setupAntigravityGuard }
