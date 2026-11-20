import {
  identify,
  subscription,
  type Subscription,
} from "../subagent-fallback/accounts"
import type { StepsContext } from "./runtime"

// The provider's active subscription login, its proof named after the login
// when Quota can tell it (accounts.ts `identify`).
export async function activeLogin(
  ctx: StepsContext,
  providerID: string,
): Promise<Subscription | undefined> {
  const auth = await subscription(ctx, providerID)
  return auth && { ...auth, proof: await identify(ctx, auth.proof) }
}
