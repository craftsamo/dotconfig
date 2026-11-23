import { accountOf, type ClaudeAccount } from "../claude-logins/accounts"
import { OAUTH_PROVIDER, type ModelRef } from "../claude-logins/models"
import { familyName } from "../credit-lanes/antigravity"
import { ANTIGRAVITY_PROVIDER } from "./policy"
import { antigravityFamily, groupKey } from "./quota"
import { LOGIN_NAMES } from "./names"

// A usage window several steps share: a credit lane (every model of it), a
// Claude login (its plain and alias models), a subscription provider, or an
// Antigravity group. The fallback package cools down only the model that hit
// a limit.
export type Window = { key: string; name: string }

export type WindowEnv = {
  creditLanes: readonly string[]
  accounts: readonly ClaudeAccount[]
  // The label of the active Claude login, when it has one.
  activeLabel: () => Promise<string | undefined>
}

const claudeLogin = (label: string): Window => ({
  key: `claude:${label}`,
  name: `Claude login "${label}"`,
})

// The window a model draws on; undefined for a model that shares none.
export async function windowOf(
  model: ModelRef,
  env: WindowEnv,
): Promise<Window | undefined> {
  const { providerID } = model
  if (env.creditLanes.includes(providerID))
    return { key: `lane:${providerID}`, name: `credit lane ${providerID}` }
  if (providerID === OAUTH_PROVIDER) {
    const account = accountOf(model, env.accounts)
    if (account)
      return account.label === "" ? undefined : claudeLogin(account.label)
    const label = await env.activeLabel()
    return label
      ? claudeLogin(label)
      : { key: "claude:active", name: "the active Claude login" }
  }
  if (Object.hasOwn(LOGIN_NAMES, providerID))
    return {
      key: providerID,
      name: `the active ${LOGIN_NAMES[providerID]} login`,
    }
  if (providerID === ANTIGRAVITY_PROVIDER) {
    const family = antigravityFamily(model)
    if (!family) return undefined
    return {
      key: groupKey(family),
      name: `Antigravity ${familyName(family)}`,
    }
  }
  return undefined
}

// Windows held spent until the end a limit gave, in memory only.
export class Windows {
  private until = new Map<string, number>()

  get empty(): boolean {
    return this.until.size === 0
  }

  // A later end wins; one already past holds nothing.
  hold(key: string, until: number, now: number): void {
    if (!Number.isFinite(until) || until <= now) return
    this.until.set(key, Math.max(until, this.until.get(key) ?? 0))
  }

  // The end of the hold on a window, or undefined once it is over.
  heldUntil(key: string, now: number): number | undefined {
    const until = this.until.get(key)
    if (until === undefined) return undefined
    if (until <= now) {
      this.until.delete(key)
      return undefined
    }
    return until
  }
}
