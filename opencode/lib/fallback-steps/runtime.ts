import type {
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
// `rpc` is both what registers the handlers and what asks another plugin's
// RPC (Quota's refresh, subagent-fallback/quota-refresh.ts).
export type StepsContext = AccountsContext &
  ClaudeAccountsContext &
  IdentityContext & {
    options: Record<string, unknown>
    rpc: NonNullable<PreflightContext["rpc"]> & {
      register(
        definition: typeof STEPS_RPC,
        handlers: StepsHandlers,
      ): Promise<Registration>
    }
  }
