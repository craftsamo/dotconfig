import type {
  LIMITED_EVENT,
  LIMITS_RPC,
  LimitedEvent,
  STEPS_RPC,
  StepsHandlers,
} from "@craftsamo/opencode-model-fallback/rpc"
import type {
  AccountsContext,
  IdentityContext,
} from "./accounts"

type Registration = { dispose(): Promise<void> }

export type RuntimeContext = {
  // Another plugin's RPC methods, by its definition (quota-refresh.ts).
  rpc?: (definition: {
    id: string
    methods: Record<string, object>
    events: Record<string, object>
  }) => Record<string, ((input: unknown) => Promise<unknown>) | undefined>
}

/**
 * V2 structural API with no SDK dependency.
 * The fallback's `limited` events come in OpenCode's envelope, the payload
 * under `data`.
 */
type LimitsClient = {
  events: {
    on(
      name: typeof LIMITED_EVENT,
      handler: (envelope: { data?: LimitedEvent }) => unknown,
    ): () => void
  }
}
type StepsRegistry = {
  register(
    definition: typeof STEPS_RPC,
    handlers: StepsHandlers,
  ): Promise<Registration>
}

// `rpc` registers the handlers, hears the fallback's events and asks another
// plugin's RPC (Quota's refresh, quota-refresh.ts).
export type StepsContext = AccountsContext &
  IdentityContext & {
    options: Record<string, unknown>
    rpc: ((definition: typeof LIMITS_RPC) => LimitsClient) &
      NonNullable<RuntimeContext["rpc"]> &
      StepsRegistry
  }
