import { createHash } from "node:crypto"
import {
  subscription,
  type AccountsContext,
  type Subscription,
} from "./accounts"
import {
  dependencies,
  exportPath,
  loadQuotaExport,
  readQuota,
  type Dependencies,
} from "./quota"
import {
  classify,
  DEFAULT_COOLDOWN_MS,
  Episodes,
  EPISODE_TTL_MS,
  Lanes,
  launchLane,
  nextModel,
  OAUTH_PROVIDER,
  SIDE_AGENTS,
  type Role,
} from "./lanes"
import {
  decideLaunch,
  modelsEqual,
  routeForLaunch,
  ROUTES,
  type CatalogModel,
  type ModelRef,
} from "./policy"

// V2.0.23 structural API, like plugins/custom-tools.ts: no SDK dependency.
type Registration = { dispose(): Promise<void> }
type Session = {
  id: string
  parentID?: string
  agent?: string
  model?: ModelRef
  metadata?: Record<string, unknown>
  location: { directory: string }
}
type Kind = "primary" | "title" | "compaction" | "generate"
type Scope = { sessionID: string; model: ModelRef; kind: Kind }
type ContextEvent = {
  sessionID: string
  model: ModelRef
  system: unknown[]
  messages: unknown[]
  tools?: unknown
  options: unknown
}
type Hooks = {
  context: ContextEvent
  compaction: ContextEvent
  generate: ContextEvent
  "http.request": Scope & { request: Request }
  "experimental.ws.handshake": Scope & {
    url: string
    headers: Record<string, string>
  }
  "experimental.ws.send": Scope & { frame: string }
  retry: {
    sessionID: string
    agent?: string
    model: ModelRef
    attempt?: number
    error: {
      type: string
      status?: number
      message: string
      response?: { body?: string }
    }
    decision: { retry: false } | { retry: true; delay: number }
  }
}
type ToolContext = {
  sessionID: string
  id: string
  signal: AbortSignal
  progress(update: Record<string, unknown>): Promise<void>
}
type Result = {
  output?: unknown
  content?: string | readonly unknown[]
  metadata?: Record<string, unknown>
}
type Executor = (
  input: Record<string, unknown>,
  context: ToolContext,
) => Promise<Result>
export type RuntimeContext = AccountsContext & {
  app: { version: string }
  options: Record<string, unknown>
  agent: {
    get(input: {
      agentID: string
      location: { directory: string }
    }): Promise<{ data: { model?: ModelRef } }>
  }
  model: {
    list(input: {
      location: { directory: string }
    }): Promise<{ data: CatalogModel[] }>
  }
  session: {
    get(input: { sessionID: string }): Promise<Session>
    update(input: {
      sessionID: string
      metadata: Record<string, unknown>
    }): Promise<unknown>
    switchModel(input: { sessionID: string; model: ModelRef }): Promise<void>
    hook<N extends keyof Hooks>(
      name: N,
      callback: (event: Hooks[N]) => Promise<void>,
    ): Promise<Registration>
  }
  tool: {
    transform(
      callback: (editor: {
        get(id: string): unknown
        update(
          id: string,
          callback: (tool: { execute: Executor }) => void,
        ): void
      }) => void,
    ): Promise<Registration>
  }
}

export const METADATA_KEY = "dotconfig.subagent-preflight"
export const SUPPORTED_VERSION = "2.0.23"
// Conservative text-only ceiling. This is not a cross-provider tokenizer.
export const MAX_CONTEXT_BYTES = 160_000
type Marker = {
  version: 1
  childID: string
  parentID: string
  agent: string
  model: ModelRef
  connectionID: string
  fallback: boolean
  launchChecked?: boolean
  wireChecked?: boolean
}
const selector = (m: ModelRef) =>
  `${m.providerID}/${m.id}${m.variant ? `#${m.variant}` : ""}`
const fail = (reason: string): never => {
  throw new Error(`Subagent preflight: ${reason}`)
}
const record = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)
const signature = (auth: Subscription) =>
  createHash("sha256")
    .update(
      JSON.stringify([auth.proof.connectionID, auth.access, auth.accountID]),
    )
    .digest("hex")
const exchangeKey = (e: Scope) =>
  `${e.sessionID}/${e.kind}/${selector(e.model)}`

function parseMarker(session: Session): Marker | undefined {
  const raw = session.metadata?.[METADATA_KEY]
  if (raw === undefined) return undefined
  // Metadata is inherited by nested children; only this exact child is protected.
  if (
    record(raw) &&
    typeof raw.childID === "string" &&
    raw.childID.startsWith("ses_") &&
    raw.childID !== session.id
  )
    return undefined
  if (
    !record(raw) ||
    raw.version !== 1 ||
    raw.parentID !== session.parentID ||
    raw.agent !== session.agent ||
    typeof raw.connectionID !== "string" ||
    !raw.connectionID ||
    typeof raw.fallback !== "boolean" ||
    (raw.launchChecked !== undefined &&
      typeof raw.launchChecked !== "boolean") ||
    (raw.wireChecked !== undefined && typeof raw.wireChecked !== "boolean") ||
    !record(raw.model) ||
    typeof raw.model.id !== "string" ||
    typeof raw.model.providerID !== "string" ||
    (raw.model.variant !== undefined && typeof raw.model.variant !== "string")
  )
    fail("invalid persisted child policy")
  if (typeof raw.agent !== "string" || !Object.hasOwn(ROUTES, raw.agent))
    fail("unapproved child role")
  const marker = raw as unknown as Marker
  const route = ROUTES[marker.agent]
  if (
    !modelsEqual(
      marker.model,
      marker.fallback ? route.alternate : route.primary,
    )
  )
    fail("invalid persisted model selection")
  return marker
}

function textOnly(messages: unknown[]): boolean {
  return messages.every(
    (message) =>
      record(message) &&
      Array.isArray(message.content) &&
      message.content.every(
        (part) =>
          record(part) && part.type === "text" && typeof part.text === "string",
      ),
  )
}

function transportURL(
  url: string,
  providerID: string,
  kind: Kind,
  websocket: boolean,
): void {
  let target: URL
  try {
    target = new URL(url)
  } catch {
    return fail("invalid transport URL")
  }
  if (target.username || target.password || target.port || target.hash)
    fail("unapproved transport URL")
  if (providerID === "openai") {
    const paths =
      kind === "compaction"
        ? [
            "/backend-api/codex/responses",
            "/backend-api/codex/responses/compact",
          ]
        : ["/backend-api/codex/responses"]
    if (
      target.hostname !== "chatgpt.com" ||
      target.protocol !== (websocket ? "wss:" : "https:") ||
      target.search ||
      !paths.includes(target.pathname)
    )
      fail("not a ChatGPT subscription route")
  } else {
    if (
      websocket ||
      target.hostname !== "api.anthropic.com" ||
      target.protocol !== "https:" ||
      !["/v1/messages", "/v1/messages/count_tokens"].includes(
        target.pathname,
      ) ||
      (target.search !== "" && target.search !== "?beta=true")
    )
      fail("not an approved Anthropic OAuth route")
  }
}

export async function setupPreflight(
  ctx: RuntimeContext,
  deps: Dependencies = dependencies,
): Promise<() => Promise<void>> {
  const registrations: Registration[] = []
  const quotaPath =
    typeof ctx.options.quotaExportPath === "string"
      ? ctx.options.quotaExportPath
      : exportPath()
  const handshakes = new Map<string, string>()
  const enabled = ctx.options.enabled === true
  // Console credit lanes (see lanes.ts). An empty list turns the whole
  // feature off, in-flight moves included.
  const lanes = new Lanes(
    Array.isArray(ctx.options.creditLanes)
      ? ctx.options.creditLanes.filter(
          (id): id is string =>
            typeof id === "string" && id !== "" && id !== OAUTH_PROVIDER,
        )
      : [],
    typeof ctx.options.creditCooldownMs === "number" &&
    ctx.options.creditCooldownMs > 0
      ? ctx.options.creditCooldownMs
      : DEFAULT_COOLDOWN_MS,
    deps.now,
  )
  const episodes = new Episodes(EPISODE_TTL_MS, deps.now)
  const primaryFallback = ctx.options.primaryFallback !== false
  const protectedChild = async (sessionID: string) => {
    const session = await ctx.session.get({ sessionID })
    const marker = parseMarker(session)
    return marker ? { session, marker } : undefined
  }
  const authorize = async (event: Scope) => {
    const child = await protectedChild(event.sessionID)
    if (!child) return undefined
    if (ctx.app.version !== SUPPORTED_VERSION)
      fail("unsupported OpenCode version; protected child stopped")
    const { session, marker } = child
    if (!session.model || !modelsEqual(session.model, marker.model))
      fail("child model changed after launch")
    if (event.kind === "primary" && !modelsEqual(event.model, marker.model))
      fail("unexpected primary model")
    if (
      event.kind === "primary" &&
      marker.fallback &&
      marker.launchChecked !== true
    )
      fail("alternate launch context was not checked")
    const approvedModel = Object.values(ROUTES).some((r) =>
      [r.primary, r.alternate].some(
        (m) =>
          m.id === event.model.id && m.providerID === event.model.providerID,
      ),
    )
    if (!approvedModel) fail("unapproved auxiliary model")
    let auth: Subscription | undefined
    try {
      auth = await subscription(ctx, event.model.providerID)
    } catch {
      return fail("subscription credentials unavailable")
    }
    if (
      !auth ||
      (event.model.providerID === marker.model.providerID &&
        auth.proof.connectionID !== marker.connectionID)
    )
      fail("subscription account changed or unavailable")
    // Launch preferences are not an in-flight billing gate. Keep identity and
    // transport protection, without fetching/rechecking usage or credit balances.
    return auth
  }
  const guardContext = async (event: ContextEvent) => {
    const child = await protectedChild(event.sessionID)
    if (!child?.marker.fallback || child.marker.launchChecked === true) return
    // Check only the first request's full text context. Later native compaction
    // is not a mechanism for making an oversized launch fit the alternate.
    if (!textOnly(event.messages))
      fail("alternate launch requires text-only context")
    let bytes: number
    try {
      bytes = Buffer.byteLength(
        JSON.stringify(
          {
            system: event.system,
            messages: event.messages,
            tools: event.tools,
            options: event.options,
          },
          (_key, value) => {
            if (["function", "symbol", "bigint"].includes(typeof value))
              fail("alternate context contains unmeasurable values")
            return value
          },
        ),
      )
    } catch {
      return fail("alternate context cannot be measured")
    }
    if (bytes > MAX_CONTEXT_BYTES)
      fail("alternate launch context exceeds the conservative text limit")
    // Require catalog headroom as well as the byte ceiling. No history
    // conversion or compaction is used to make this first request fit.
    const catalog = (await ctx.model.list({ location: child.session.location }))
      .data
    const model = catalog.find(
      (m) =>
        m.id === child.marker.model.id &&
        m.providerID === child.marker.model.providerID,
    )
    if (
      !model ||
      bytes + 32_768 >
        Math.min(
          model.limit.input ?? Infinity,
          model.limit.context - model.limit.output,
        )
    )
      fail("alternate catalog lacks conservative context headroom")
    await ctx.session.update({
      sessionID: child.session.id,
      metadata: {
        ...child.session.metadata,
        [METADATA_KEY]: { ...child.marker, launchChecked: true },
      },
    })
  }
  const guardWireSize = async (event: Scope, read: () => Promise<string>) => {
    const child = await protectedChild(event.sessionID)
    if (
      !child?.marker.fallback ||
      child.marker.wireChecked === true ||
      event.kind !== "primary"
    )
      return
    let bytes: number
    try {
      bytes = Buffer.byteLength(await read())
    } catch {
      return fail("alternate wire context cannot be measured")
    }
    const catalog = (await ctx.model.list({ location: child.session.location }))
      .data
    const model = catalog.find(
      (m) =>
        m.id === child.marker.model.id &&
        m.providerID === child.marker.model.providerID,
    )
    const capacity = model
      ? Math.min(
          model.limit.input ?? Infinity,
          model.limit.context - model.limit.output,
        )
      : NaN
    if (
      !Number.isFinite(capacity) ||
      bytes > MAX_CONTEXT_BYTES ||
      bytes + 32_768 > capacity
    )
      fail("alternate wire context exceeds conservative headroom")
    // Later trusted context hooks can add global instructions. Measure the
    // actual serialized HTTP body / WS frame before its first transmission too.
    await ctx.session.update({
      sessionID: child.session.id,
      metadata: {
        ...child.session.metadata,
        [METADATA_KEY]: { ...child.marker, wireChecked: true },
      },
    })
  }
  const cleanup = async () => {
    for (const registration of registrations.reverse())
      await registration.dispose()
    handshakes.clear()
  }
  try {
    registrations.push(await ctx.session.hook("context", guardContext))
    registrations.push(
      await ctx.session.hook("http.request", async (event) => {
        const auth = await authorize(event)
        if (!auth) return
        transportURL(
          event.request.url,
          event.model.providerID,
          event.kind,
          false,
        )
        if (event.request.method !== "POST") fail("unapproved HTTP method")
        // Native OpenAI Requests default to follow; prohibit redirecting a
        // validated OAuth request to an unvalidated endpoint.
        if (event.request.redirect !== "error")
          event.request = new Request(event.request, { redirect: "error" })
        const headers = event.request.headers
        if (
          headers.get("authorization") !== `Bearer ${auth.access}` ||
          headers.has("x-api-key")
        )
          fail("wire authentication is not the approved OAuth credential")
        if (
          event.model.providerID === "openai" &&
          headers.get("chatgpt-account-id") !== auth.accountID
        )
          fail("wire subscription account mismatch")
        await guardWireSize(event, () => event.request.clone().text())
      }),
    )
    registrations.push(
      await ctx.session.hook("experimental.ws.handshake", async (event) => {
        const auth = await authorize(event)
        if (!auth) return
        transportURL(event.url, event.model.providerID, event.kind, true)
        const headers = new Headers(event.headers)
        if (
          headers.get("authorization") !== `Bearer ${auth.access}` ||
          headers.has("x-api-key") ||
          headers.get("chatgpt-account-id") !== auth.accountID
        )
          fail("WebSocket subscription identity mismatch")
        handshakes.set(exchangeKey(event), signature(auth))
      }),
    )
    registrations.push(
      await ctx.session.hook("experimental.ws.send", async (event) => {
        const auth = await authorize(event)
        if (!auth) return
        if (handshakes.get(exchangeKey(event)) !== signature(auth))
          fail("WebSocket exchange lacks a current approved handshake")
        await guardWireSize(event, async () => event.frame)
      }),
    )
    // Do not switch a running child. Override quota's long reset wait only for
    // children admitted by this plugin; root and ordinary sessions are untouched.
    registrations.push(
      await ctx.session.hook("retry", async (event) => {
        if (!(await protectedChild(event.sessionID))) return
        if (
          event.error.type === "provider.quota" ||
          event.error.message.startsWith("Subagent preflight:") ||
          ((event.error.type === "provider.rate-limit" ||
            event.error.status === 429) &&
            event.decision.retry &&
            event.decision.delay > 10_000)
        )
          event.decision = { retry: false }
      }),
    )
    // Console credit lanes. An empty balance fails before anything is
    // generated, and so does a bad key or a window limit, so moving the session
    // to the next provider and repeating the same step has no side effects.
    // Protected children keep their own guards above.
    registrations.push(
      await ctx.session.hook("retry", async (event) => {
        if (lanes.ids.length === 0 || !event.model) return
        const provider = event.model.providerID
        const onLane = lanes.has(provider)
        if (!onLane && provider !== OAUTH_PROVIDER) return
        const failure = classify(event.error, event.decision)
        if (!failure) return
        // A subscription failure matters only as a window limit; a lane
        // failure is any of the three.
        if (!onLane && failure !== "quota") return
        try {
          if (await protectedChild(event.sessionID)) return
          const session = await ctx.session.get({ sessionID: event.sessionID })
          const role: Role = session.parentID ? "subagent" : "primary"
          const agent = event.agent ?? session.agent
          // Side requests (compaction, titles) run on a model of their own;
          // moving the session for one would swap the model it works on.
          if (typeof agent === "string" && SIDE_AGENTS.has(agent)) return
          if (
            session.model &&
            (session.model.providerID !== provider ||
              session.model.id !== event.model.id)
          )
            return
          const eligible =
            typeof agent === "string" &&
            Object.hasOwn(ROUTES, agent) &&
            ROUTES[agent].primary.providerID === OAUTH_PROVIDER
          // A window limit lasts as long as its wait; an empty balance or a
          // bad key lasts until someone fixes it, so those take the cooldown.
          if (onLane)
            lanes.mark(
              provider,
              failure === "quota" && event.decision.retry
                ? event.decision.delay
                : undefined,
            )
          // The subscription's limit is moved off only for the roles that opt
          // in: Claude specialists, and the primary when primaryFallback is on.
          if (!onLane && (role === "primary" ? !primaryFallback : !eligible))
            return
          const tried = episodes.record(event.sessionID, provider)
          const catalog = (await ctx.model.list({ location: session.location }))
            .data
          const target = nextModel({
            current: event.model,
            role,
            lanes,
            tried,
            catalog,
          })
          if (target) {
            await ctx.session.switchModel({
              sessionID: event.sessionID,
              model: target,
            })
            event.decision = { retry: true, delay: 0 }
            return
          }
          // Nothing left to move to. A specialist must not sit out a long
          // reset: stop so the parent relaunches it and the usual preflight
          // can pick the other vendor.
          if (!onLane && role === "subagent") event.decision = { retry: false }
        } catch {
          // Leave the native decision untouched.
        }
      }),
    )
    registrations.push(
      await ctx.tool.transform((editor) => {
        if (!editor.get("subagent"))
          fail("builtin subagent executor unavailable")
        editor.update("subagent", (tool) => {
          const original = tool.execute
          tool.execute = async (input, context) => {
            // Outcome is historical, not a busy flag. There is no atomic
            // idle-and-release API, so protection stays with this exact child.
            if (typeof input.sessionID === "string") {
              const existing = await ctx.session.get({
                sessionID: input.sessionID,
              })
              const policy = parseMarker(existing)
              if (
                policy &&
                existing.parentID === context.sessionID &&
                (input.agent !== policy.agent ||
                  (input.model !== undefined &&
                    input.model !== selector(policy.model)))
              )
                fail(
                  "protected continuations keep their role and model; use a new child for a different explicit selection",
                )
              return original(input, context)
            }
            if (
              !enabled ||
              input.model !== undefined ||
              typeof input.agent !== "string" ||
              !Object.hasOwn(ROUTES, input.agent)
            )
              return original(input, context)
            if (ctx.app.version !== SUPPORTED_VERSION)
              fail(
                "unsupported OpenCode version; use an explicit model or disable new selection",
              )
            const parent = await ctx.session.get({
              sessionID: context.sessionID,
            })
            const agent = (
              await ctx.agent.get({
                agentID: input.agent,
                location: parent.location,
              })
            ).data
            const route = routeForLaunch(input, agent.model)
            if (!route) return original(input, context)
            // Credits first: a lane not known empty takes the launch, with no
            // subscription marker (its guards are for OAuth requests). When
            // every lane is empty, the usual preflight below decides.
            if (lanes.ids.length > 0) {
              const lane = launchLane(
                route,
                lanes,
                (await ctx.model.list({ location: parent.location })).data,
              )
              if (lane) {
                context.signal.throwIfAborted()
                const result = await original(
                  { ...input, model: selector(lane) },
                  context,
                )
                const notice = `[Subagent preflight: ${input.agent} ${selector(route.primary)} → ${selector(lane)}; a Console credit lane is tried before the subscription.]`
                return {
                  ...result,
                  metadata: {
                    ...result.metadata,
                    preflight: {
                      funding: "console-credit",
                      from: selector(route.primary),
                      to: selector(lane),
                    },
                  },
                  content:
                    typeof result.content === "string"
                      ? `${notice}\n${result.content}`
                      : [
                          { type: "text", text: notice },
                          ...(result.content ?? []),
                        ],
                }
              }
            }
            context.signal.throwIfAborted()
            const snapshot = await loadQuotaExport(deps, quotaPath)
            context.signal.throwIfAborted()
            const probe = async (model: ModelRef) => {
              let auth: Subscription | undefined
              try {
                auth = await subscription(ctx, model.providerID)
              } catch {}
              return {
                account: auth?.proof,
                quota: readQuota(snapshot, auth?.proof, deps.now()),
              }
            }
            const source = await probe(route.primary)
            const target =
              source.quota.state === "exhausted"
                ? await probe(route.alternate)
                : undefined
            const catalog = (
              await ctx.model.list({ location: parent.location })
            ).data
            const decision = decideLaunch({
              route,
              source,
              target,
              catalog,
              now: deps.now(),
            })
            if (decision.kind === "stop") fail(decision.reason)
            if (
              decision.kind === "credits" &&
              ctx.options.creditsLastResort !== true
            )
              fail(
                "both included quotas are exhausted; last-resort credits are disabled",
              )
            const alternate = !modelsEqual(decision.model, route.primary)
            const account = alternate ? target!.account! : source.account!
            const launch = alternate
              ? { ...input, model: selector(decision.model) }
              : input
            context.signal.throwIfAborted()
            let childID: string | undefined
            const result = await original(launch, {
              ...context,
              progress: async (update) => {
                if (
                  !childID &&
                  (typeof update.sessionID !== "string" ||
                    !update.sessionID.startsWith("ses_"))
                )
                  fail("missing builtin pre-launch child identity")
                if (
                  childID &&
                  update.sessionID !== undefined &&
                  childID !== update.sessionID
                )
                  fail("builtin child identity changed")
                if (!childID) {
                  context.signal.throwIfAborted()
                  const child = await ctx.session.get({
                    sessionID: update.sessionID as string,
                  })
                  if (
                    child.parentID !== context.sessionID ||
                    child.agent !== input.agent ||
                    !child.model ||
                    !modelsEqual(child.model, decision.model)
                  )
                    fail("builtin child launch policy mismatch")
                  const active = await subscription(
                    ctx,
                    decision.model.providerID,
                  ).catch(() => undefined)
                  if (
                    !active ||
                    active.proof.connectionID !== account.connectionID
                  )
                    fail("subscription account changed before launch")
                  const marker: Marker = {
                    version: 1,
                    childID: child.id,
                    parentID: context.sessionID,
                    agent: input.agent as string,
                    model: decision.model,
                    connectionID: account.connectionID,
                    fallback: alternate,
                  }
                  await ctx.session.update({
                    sessionID: child.id,
                    metadata: { ...child.metadata, [METADATA_KEY]: marker },
                  })
                  childID = child.id
                }
                await context.progress(update)
              },
            })
            if (!childID) fail("builtin did not await pre-launch registration")
            if (decision.kind === "default") return result
            const notice =
              decision.kind === "credits"
                ? `[Subagent preflight: ${input.agent} ${selector(decision.model)}; Quota reports both included quotas at 0%, trying the default with provider-managed credits as last resort. No credit purchase or running-session switch.]`
                : `[Subagent preflight: ${input.agent} ${selector(route.primary)} → ${selector(decision.model)}; Quota reports the default's included quota empty and the alternate not empty. No running-session switch.]`
            return {
              ...result,
              metadata: {
                ...result.metadata,
                preflight: {
                  funding:
                    decision.kind === "credits" ? "provider" : "included",
                  from: selector(route.primary),
                  to: selector(decision.model),
                },
              },
              content:
                typeof result.content === "string"
                  ? `${notice}\n${result.content}`
                  : [{ type: "text", text: notice }, ...(result.content ?? [])],
            }
          }
        })
      }),
    )
    return cleanup
  } catch (error) {
    await cleanup()
    throw error
  }
}

export default { id: "dotconfig.subagent-preflight", setup: setupPreflight }
