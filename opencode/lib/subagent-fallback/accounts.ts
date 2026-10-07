import { createHash } from "node:crypto"
import type { AccountProof, ModelRef, QuotaProof, UsageProof } from "./policy"
import { inspectAnthropicUsage, inspectOpenAIUsage } from "./quota"

export type Connection = { type: string; id?: string; method?: string }
export type OAuth = {
  type: string
  methodID?: string
  access?: string
  expires?: number
  metadata?: Record<string, unknown>
}
export type AccountsContext = {
  provider: {
    get(input: {
      providerID: string
    }): Promise<{ data: { package: string; integrationID?: string } }>
  }
  integration: {
    connection: {
      active(providerID: string): Promise<Connection | undefined>
      resolve(connection: Connection): Promise<OAuth | undefined>
    }
  }
}
export type Subscription = {
  proof: AccountProof
  access: string
  accountID?: string
}

// Access tokens stay in memory. Never include them (or provider response bodies)
// in errors, metadata, logs, snapshots, or test failure diagnostics.
export async function subscription(
  ctx: AccountsContext,
  providerID: string,
): Promise<Subscription | undefined> {
  if (providerID !== "anthropic" && providerID !== "openai") return undefined
  const provider = (await ctx.provider.get({ providerID })).data
  if (provider.package !== `@opencode/ai/providers/${providerID}`)
    return undefined
  if ((provider.integrationID ?? providerID) !== providerID) return undefined
  const connection = await ctx.integration.connection.active(providerID)
  if (
    connection?.type !== "credential" ||
    connection.method !== "oauth" ||
    !connection.id
  )
    return undefined
  const credential = await ctx.integration.connection.resolve(connection)
  if (credential?.type !== "oauth" || !credential.access) return undefined
  const methodID = credential.methodID
  if (
    providerID === "anthropic"
      ? methodID !== "claude-max"
      : !["chatgpt-browser", "chatgpt-headless"].includes(methodID ?? "")
  )
    return undefined
  const accountID = credential.metadata?.accountID
  if (providerID === "openai" && (typeof accountID !== "string" || !accountID))
    return undefined
  return {
    proof: {
      connectionID: connection.id,
      providerID,
      methodID: methodID!,
      type: "oauth",
    },
    access: credential.access,
    ...(typeof accountID === "string" ? { accountID } : {}),
  }
}

export type Dependencies = { fetch: typeof fetch; now: () => number }
const URLS = {
  anthropic: "https://api.anthropic.com/api/oauth/usage",
  openai: "https://chatgpt.com/backend-api/wham/usage",
} as const
const MODEL_IDS = {
  anthropic: ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5"],
  openai: ["gpt-6.1-sol", "gpt-6-luna"],
} as const

export class QuotaReader {
  private cache = new Map<
    string,
    { until: number; pending: Promise<Record<string, UsageProof>> }
  >()
  constructor(private deps: Dependencies) {}

  async read(
    auth: Subscription,
    model: ModelRef,
    signal: AbortSignal,
  ): Promise<QuotaProof> {
    return (await this.inspect(auth, model, signal)).quota
  }

  async inspect(
    auth: Subscription,
    model: ModelRef,
    signal: AbortSignal,
  ): Promise<UsageProof> {
    const unknown = (): UsageProof => ({
      quota: { state: "unknown", observedAt: this.deps.now() },
      billing: { state: "unknown", observedAt: this.deps.now() },
    })
    const providerID = auth.proof.providerID as keyof typeof URLS
    if (!Object.hasOwn(URLS, providerID) || model.providerID !== providerID)
      return unknown()
    // Identity-bound, process-local cache; no token, account ID or quota files.
    const key = `${providerID}/${auth.proof.connectionID}/${createHash("sha256")
      .update(JSON.stringify([auth.access, auth.accountID]))
      .digest("hex")}`
    const now = this.deps.now()
    for (const [id, entry] of this.cache)
      if (entry.until <= now) this.cache.delete(id)
    let entry = this.cache.get(key)
    if (!entry) {
      const pending = this.query(auth, providerID)
      entry = { until: now + 15_000, pending }
      this.cache.set(key, entry)
      const current = entry
      void pending.then((proofs) => {
        if (
          Object.values(proofs).some(
            (proof) =>
              proof.quota.state === "unknown" ||
              proof.billing.state === "unknown",
          )
        )
          current.until = this.deps.now() + 1_000
      })
    }
    // Shared probes have their own bounded timeout: cancelling one caller must
    // not cancel another caller's probe. Callers still stop before child creation.
    signal.throwIfAborted()
    let abort: (() => void) | undefined
    const cancelled = new Promise<never>((_, reject) => {
      abort = () =>
        reject(new DOMException("Preflight cancelled", "AbortError"))
      signal.addEventListener("abort", abort, { once: true })
    })
    let proofs: Record<string, UsageProof>
    try {
      proofs = await Promise.race([entry.pending, cancelled])
    } finally {
      if (abort) signal.removeEventListener("abort", abort)
    }
    return proofs[model.id] ?? unknown()
  }

  private async query(
    auth: Subscription,
    providerID: keyof typeof URLS,
  ): Promise<Record<string, UsageProof>> {
    const unknown = () =>
      Object.fromEntries(
        MODEL_IDS[providerID].map((id) => [
          id,
          {
            quota: { state: "unknown" as const, observedAt: this.deps.now() },
            billing: { state: "unknown" as const, observedAt: this.deps.now() },
          },
        ]),
      )
    try {
      const headers = new Headers({ authorization: `Bearer ${auth.access}` })
      if (providerID === "anthropic")
        headers.set("anthropic-beta", "oauth-2025-04-20")
      else headers.set("chatgpt-account-id", auth.accountID!)
      const response = await this.deps.fetch(URLS[providerID], {
        method: "GET",
        headers,
        redirect: "error",
        signal: AbortSignal.timeout(5_000),
      })
      if (!response.ok) return unknown() // 429 alone is not pool exhaustion.
      const data: unknown = await response.json()
      const now = this.deps.now()
      return Object.fromEntries(
        MODEL_IDS[providerID].map((id) => [
          id,
          providerID === "anthropic"
            ? inspectAnthropicUsage(data, now, id)
            : inspectOpenAIUsage(data, now, id),
        ]),
      )
    } catch {
      return unknown()
    }
  }
}
