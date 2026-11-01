import { METHODS, type AccountProof } from "./policy"

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
export type IdentityContext = {
  integration: {
    get(input: { integrationID: string }): Promise<{
      data: {
        connections: readonly {
          type: string
          id?: string
          label?: string
          method?: string
        }[]
      }
    }>
  }
}

// Quota 6 exports no connection ID: it names a login's rows after the login's
// label. Adds the label when it names this login alone, and whether this is
// the integration's only subscription login. Never throws; without either,
// the login's rows in a Quota 6 export stay unmatched.
export async function identify(
  ctx: IdentityContext,
  proof: AccountProof,
): Promise<AccountProof> {
  let connections: unknown
  try {
    connections = (
      await ctx.integration.get({ integrationID: proof.providerID })
    ).data.connections
  } catch {
    return proof
  }
  if (!Array.isArray(connections)) return proof
  const logins = connections.filter(
    (c) =>
      c?.type === "credential" &&
      c.method === "oauth" &&
      typeof c.id === "string" &&
      c.id !== "",
  )
  const own = logins.find((c) => c.id === proof.connectionID)
  if (!own) return proof
  const labelOf = (c: { label?: unknown }) =>
    typeof c.label === "string" ? c.label.trim() : ""
  const label = labelOf(own)
  const named =
    label !== "" && logins.filter((c) => labelOf(c) === label).length === 1
  return {
    ...proof,
    ...(named ? { label } : {}),
    ...(logins.length === 1 ? { sole: true } : {}),
  }
}

// Access tokens stay in memory. Never include them (or provider response bodies)
// in errors, metadata, logs, snapshots, or test failure diagnostics.
export async function subscription(
  ctx: AccountsContext,
  providerID: string,
): Promise<Subscription | undefined> {
  if (!Object.hasOwn(METHODS, providerID)) return undefined
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
  if (!METHODS[providerID].includes(methodID ?? "")) return undefined
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
