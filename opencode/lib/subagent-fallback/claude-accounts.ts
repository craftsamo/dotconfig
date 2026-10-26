import type { Subscription } from "./accounts"
import { longestSuffix, OAUTH_PROVIDER } from "./lanes"
import { METHODS, type ModelRef } from "./policy"

// Saved Claude subscription logins beside the active one. OpenCode resolves
// only an integration's active login, and the Claude login plugin rewrites
// requests for provider `anthropic` alone, so another login is reached through
// alias models of that provider: `claude-opus-5-5-main` (config
// `modelID: "claude-opus-5-5"`) runs on the login the `main` suffix names. Its
// requests leave with that login's token in place of the active one's.
export type ClaudeAccount = { suffix: string; label: string }

type Connection = {
  type: string
  id?: string
  label?: string
  method?: string
}
type Credential = { type: string; methodID?: string; access?: string }
export type ClaudeAccountsContext = {
  integration: {
    get(input: {
      integrationID: string
    }): Promise<{ data: { connections: readonly Connection[] } }>
    connection: {
      resolve(connection: Connection): Promise<Credential | undefined>
    }
  }
  session: {
    get(input: { sessionID: string }): Promise<{ model?: ModelRef }>
  }
}
export type RoutedRequest = {
  sessionID: string
  model: ModelRef
  kind: string
  request: Request
}

export class AccountError extends Error {
  constructor(reason: string) {
    super(`Claude account: ${reason}`)
  }
}

// The `claudeAccounts` option: model-ID suffix → saved login label. Nothing
// is dropped: an entry without a usable label stays, so its models fail
// instead of running on the active login. An option that is not a map throws
// (see AccountRouter.fromOption).
export function parseAccounts(option: unknown): ClaudeAccount[] {
  if (option === undefined) return []
  if (typeof option !== "object" || option === null || Array.isArray(option))
    throw new AccountError(
      "claudeAccounts must map model-ID suffixes to login labels",
    )
  return Object.entries(option)
    .filter(([suffix]) => suffix !== "")
    .map(([suffix, label]) => ({
      suffix,
      label: typeof label === "string" ? label.trim() : "",
    }))
}

// The account an alias model names; the longest matching suffix wins.
export function accountOf(
  model: ModelRef | undefined,
  accounts: readonly ClaudeAccount[],
): ClaudeAccount | undefined {
  if (model?.providerID !== OAUTH_PROVIDER) return undefined
  const suffix = longestSuffix(
    model.id,
    accounts.map((account) => account.suffix),
  )
  return accounts.find((account) => account.suffix === suffix)
}

// The saved login an account names, resolved (and refreshed when close to
// expiry) without making it the active one. The token stays in memory.
export async function login(
  ctx: ClaudeAccountsContext,
  account: ClaudeAccount,
): Promise<{ connectionID: string; access: string; methodID: string }> {
  if (account.label === "")
    throw new AccountError(
      `claudeAccounts gives the "${account.suffix}" models no login label`,
    )
  const { data } = await ctx.integration.get({ integrationID: OAUTH_PROVIDER })
  const matches = data.connections.filter(
    (c) =>
      c.type === "credential" &&
      c.method === "oauth" &&
      c.label === account.label &&
      typeof c.id === "string" &&
      c.id !== "",
  )
  if (matches.length === 0)
    throw new AccountError(
      `no saved Claude login is labelled "${account.label}"`,
    )
  if (matches.length > 1)
    throw new AccountError(
      `several saved Claude logins are labelled "${account.label}"`,
    )
  const credential = await ctx.integration.connection.resolve(matches[0])
  if (
    credential?.type !== "oauth" ||
    !METHODS[OAUTH_PROVIDER].includes(credential.methodID ?? "") ||
    typeof credential.access !== "string" ||
    credential.access === ""
  )
    throw new AccountError(
      `the login labelled "${account.label}" is not a Claude Pro/Max login`,
    )
  return {
    connectionID: matches[0].id!,
    access: credential.access,
    methodID: credential.methodID!,
  }
}

// A saved login as the subscription the launch selector and the transport
// guards check, like accounts.ts gives the active one.
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

// The beta flag the Claude login plugin adds to every request it rewrites;
// OpenCode's own Anthropic provider never sends it.
const OAUTH_BETA = "oauth-2025-04-20"
// Kinds whose model is the session's own (warming sends `generate`).
const OWN_MODEL: ReadonlySet<string> = new Set(["primary", "generate"])

// Puts the account's token on a request the Claude login plugin prepared.
// Side requests (compaction, a title on a Claude model) run on a model of
// their own, so they follow the account of the session's model: a session on
// another login never draws on the active one. A session without a stored
// model runs on the default one, so it follows the account of its last own
// request instead. Anything unexpected stops the request rather than sending
// it on the active login.
export class AccountRouter {
  private recent = new Map<string, ClaudeAccount | undefined>()
  constructor(
    readonly accounts: readonly ClaudeAccount[],
    // A malformed option: no alias can be told from a plain model, so every
    // Claude subscription request stops until it is fixed. Failing setup
    // instead would leave the aliases on the active login, since OpenCode
    // keeps going without a plugin whose setup threw.
    readonly broken?: AccountError,
    private max = 256,
  ) {}

  static fromOption(option: unknown): AccountRouter {
    try {
      return new AccountRouter(parseAccounts(option))
    } catch (error) {
      if (!(error instanceof AccountError)) throw error
      return new AccountRouter([], error)
    }
  }

  get active(): boolean {
    return this.accounts.length > 0 || this.broken !== undefined
  }

  async route(
    ctx: ClaudeAccountsContext,
    event: RoutedRequest,
    supported: boolean,
  ): Promise<ClaudeAccount | undefined> {
    if (this.broken && event.model.providerID === OAUTH_PROVIDER)
      throw this.broken
    if (this.accounts.length === 0) return undefined
    let account = accountOf(event.model, this.accounts)
    if (OWN_MODEL.has(event.kind)) this.remember(event.sessionID, account)
    if (event.model.providerID !== OAUTH_PROVIDER) return undefined
    if (!account && !OWN_MODEL.has(event.kind)) {
      const { model } = await ctx.session.get({ sessionID: event.sessionID })
      account = model
        ? accountOf(model, this.accounts)
        : this.recent.get(event.sessionID)
    }
    if (!account) return undefined
    if (!supported)
      throw new AccountError(
        "unsupported OpenCode version; requests on another login stopped",
      )
    const request = event.request
    let url: URL
    try {
      url = new URL(request.url)
    } catch {
      throw new AccountError("invalid request URL")
    }
    if (url.protocol !== "https:" || url.hostname !== "api.anthropic.com")
      throw new AccountError("not an Anthropic API request")
    const betas = (request.headers.get("anthropic-beta") ?? "")
      .split(",")
      .map((beta) => beta.trim())
    if (
      !request.headers.get("authorization")?.startsWith("Bearer ") ||
      request.headers.has("x-api-key") ||
      !betas.includes(OAUTH_BETA)
    )
      throw new AccountError(
        "the Claude login plugin did not prepare this request",
      )
    const { access } = await login(ctx, account)
    // In place, never a new Request: the login plugin keys its response
    // rewrite (tool names restored) on this exact object.
    request.headers.set("authorization", `Bearer ${access}`)
    if (request.headers.get("authorization") !== `Bearer ${access}`)
      throw new AccountError("request headers cannot be changed")
    return account
  }

  private remember(sessionID: string, account: ClaudeAccount | undefined) {
    this.recent.delete(sessionID)
    this.recent.set(sessionID, account)
    while (this.recent.size > this.max)
      this.recent.delete(this.recent.keys().next().value as string)
  }
}
