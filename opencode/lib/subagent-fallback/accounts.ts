import type { AccountProof } from "./policy"

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
