import {
  login,
  type ClaudeAccount,
  type ClaudeAccountsContext,
} from "../claude-logins/accounts"
import type { Subscription } from "./accounts"
import { OAUTH_PROVIDER } from "../claude-logins/models"

// A saved login as the subscription checked for a step's usable answer,
// like accounts.ts gives the active one.
export async function loginSubscription(
  ctx: ClaudeAccountsContext,
  account: ClaudeAccount,
): Promise<Subscription> {
  const { connectionID, access, methodID } = await login(ctx, account)
  return {
    proof: {
      connectionID,
      providerID: OAUTH_PROVIDER,
      methodID,
      type: "oauth",
    },
    access,
  }
}
