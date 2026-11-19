import type {
  LIMITED_EVENT,
  LIMITS_RPC,
  LimitedEvent,
  STEPS_RPC,
  StepsHandlers,
} from "@craftsamo/opencode-model-fallback/rpc"
import type { ClaudeAccountsContext } from "../claude-logins/accounts"
import type {
  AccountsContext,
  IdentityContext,
} from "../subagent-fallback/accounts"
import type {
  Registration,
  RuntimeContext as PreflightContext,
} from "../subagent-fallback/runtime"

// V2 structural API, like lib/claude-logins/runtime.ts: no SDK dependency.
// The fallback's `limited` events come in OpenCode's envelope, the payload
// under `data`.
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
// plugin's RPC (Quota's refresh, subagent-fallback/quota-refresh.ts).
export type StepsContext = AccountsContext &
  ClaudeAccountsContext &
  IdentityContext & {
    options: Record<string, unknown>
    rpc: ((definition: typeof LIMITS_RPC) => LimitsClient) &
      NonNullable<PreflightContext["rpc"]> &
      StepsRegistry
  }
