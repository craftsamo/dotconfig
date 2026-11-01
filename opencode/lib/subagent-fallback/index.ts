import { identify, subscription, type Subscription } from "./accounts"
import { AccountRouter, loginSubscription } from "./claude-accounts"
import { FAIL_PREFIX, fail } from "./errors"
import { createGuards } from "./guards"
import {
  aliasOf,
  METADATA_KEY,
  parseMarker,
  selector,
  withMarker,
  type Marker,
} from "./marker"
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
  loginStop,
  nextModel,
  OAUTH_PROVIDER,
  SIDE_AGENTS,
  stopFor,
  type Role,
} from "./lanes"
import {
  catalogOk,
  decideLaunch,
  freshState,
  modelsEqual,
  routeForLaunch,
  ROUTES,
  type ModelRef,
} from "./policy"
import {
  supported,
  type Registration,
  type Result,
  type RuntimeContext,
} from "./runtime"

export { METADATA_KEY }
export { MAX_CONTEXT_BYTES } from "./guards"
export { SUPPORTED_VERSIONS } from "./runtime"
export type { RuntimeContext }

const withNotices = (
  result: Result,
  notices: string[],
  metadata: Record<string, unknown>,
): Result => {
  const text = notices.join("\n")
  return {
    ...result,
    metadata: { ...result.metadata, ...metadata },
    content:
      typeof result.content === "string"
        ? `${text}\n${result.content}`
        : [{ type: "text", text }, ...(result.content ?? [])],
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
  // Other saved Claude logins, reached by alias model (claude-accounts.ts).
  // Independent of `enabled`: an alias must never fall back to the active
  // login. Every configured suffix decides which login a model runs on; only
  // the labelled ones are places to move or launch.
  const claudeAccounts = AccountRouter.fromOption(ctx.options.claudeAccounts)
  const suffixes = claudeAccounts.accounts.map((account) => account.suffix)
  const logins = claudeAccounts.accounts
    .filter((account) => account.label !== "")
    .map((account) => account.suffix)
  const loginOf = (suffix: string) => {
    const account = claudeAccounts.accounts.find((a) => a.suffix === suffix)
    if (!account) throw new Error("no such Claude login")
    return loginSubscription(ctx, account)
  }
  // Subscription window limits protected children hit, kept for the wait
  // asked: the Quota export is rewritten on the TUI's own schedule, so the
  // parent's relaunch would otherwise bounce back to the same window. Each
  // Claude login is its own window.
  const limited = new Lanes(
    [
      OAUTH_PROVIDER,
      ...logins.map((login) => loginStop(login).key),
      "openai",
      "xai",
    ],
    DEFAULT_COOLDOWN_MS,
    deps.now,
  )
  // An empty balance is the one exact reading the balance estimate gets
  // without the Console. Requests in flight report it together, so at most
  // once a minute per lane.
  const emptied = new Map<string, number>()
  const noteEmpty = (provider: string) => {
    const at = deps.now()
    if (at - (emptied.get(provider) ?? -Infinity) < 60_000) return
    emptied.set(provider, at)
    void deps.creditEmpty?.(provider).catch(() => {})
  }
  const primaryFallback = ctx.options.primaryFallback !== false
  const pinModels = ctx.options.pinModels === true
  const protectedChild = async (sessionID: string) => {
    const session = await ctx.session.get({ sessionID })
    const marker = parseMarker(session)
    return marker ? { session, marker } : undefined
  }
  const guards = createGuards(ctx, { protectedChild, loginOf })
  const cleanup = async () => {
    for (const registration of registrations.reverse())
      await registration.dispose()
    guards.clear()
  }
  try {
    // Before the transport guard, so the guard sees the token a request
    // leaves with.
    if (claudeAccounts.active)
      registrations.push(
        await ctx.session.hook("http.request", async (event) => {
          await claudeAccounts.route(ctx, event, supported(ctx.app.version))
        }),
      )
    registrations.push(await ctx.session.hook("context", guards.context))
    registrations.push(
      await ctx.session.hook("http.request", guards.httpRequest),
    )
    registrations.push(
      await ctx.session.hook("experimental.ws.handshake", guards.wsHandshake),
    )
    registrations.push(
      await ctx.session.hook("experimental.ws.send", guards.wsSend),
    )
    // Do not switch a running child. Override quota's long reset wait only for
    // children admitted by this plugin; root and ordinary sessions are untouched.
    registrations.push(
      await ctx.session.hook("retry", async (event) => {
        const child = await protectedChild(event.sessionID)
        if (!child) return
        if (event.error.message.startsWith(FAIL_PREFIX)) {
          event.decision = { retry: false }
          return
        }
        if (
          event.error.type === "provider.quota" ||
          ((event.error.type === "provider.rate-limit" ||
            event.error.status === 429) &&
            event.decision.retry &&
            event.decision.delay > 10_000)
        ) {
          // A bound child's Claude requests all leave on its login, a side
          // request on a plain model too, so the limit is that login's.
          if (event.model)
            limited.mark(
              child.marker.login !== undefined &&
                event.model.providerID === OAUTH_PROVIDER
                ? loginStop(child.marker.login).key
                : stopFor(event.model, suffixes).key,
              event.decision.retry ? event.decision.delay : undefined,
            )
          event.decision = { retry: false }
        }
      }),
    )
    // Console credit lanes and other Claude logins. An empty balance fails
    // before anything is generated, and so does a bad key or a window limit,
    // so moving the session to the next stop and repeating the same step has
    // no side effects. Protected children keep their own guards above.
    registrations.push(
      await ctx.session.hook("retry", async (event) => {
        if ((lanes.ids.length === 0 && logins.length === 0) || !event.model)
          return
        const provider = event.model.providerID
        const onLane = lanes.has(provider)
        if (!onLane && provider !== OAUTH_PROVIDER) return
        const failure = classify(event.error, event.decision)
        if (!failure) return
        if (onLane && failure === "credit") noteEmpty(provider)
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
          const tried = episodes.record(
            event.sessionID,
            stopFor(event.model, suffixes).key,
          )
          const catalog = (await ctx.model.list({ location: session.location }))
            .data
          const target = nextModel({
            current: event.model,
            role,
            lanes,
            logins,
            suffixes,
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
            if (!supported(ctx.app.version))
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
            const route = routeForLaunch(input, agent.model, pinModels)
            if (!route) return original(input, context)
            // pinModels: a project's agent file can name another model for a
            // role. Launch the role on its route anyway, the model made
            // explicit, and say so; its prompt and permissions stay.
            const pinned =
              !agent.model || !modelsEqual(agent.model, route.primary)
            const pin = pinned
              ? {
                  notices: [
                    `[Model pin: ${input.agent} ${agent.model ? selector(agent.model) : "(no model)"} → ${selector(route.primary)}; the agent definition in effect is replaced by the dotconfig route.]`,
                  ],
                  metadata: {
                    pin: {
                      from: agent.model ? selector(agent.model) : null,
                      to: selector(route.primary),
                    },
                  },
                }
              : { notices: [], metadata: {} }
            const catalog = (
              await ctx.model.list({ location: parent.location })
            ).data
            // A launch on a lane carries no subscription marker (its guards
            // are for OAuth requests).
            const onLane = async (lane: ModelRef, why: string) => {
              context.signal.throwIfAborted()
              const result = await original(
                { ...input, model: selector(lane) },
                context,
              )
              return withNotices(
                result,
                [
                  ...pin.notices,
                  `[Subagent preflight: ${input.agent} ${selector(route.primary)} → ${selector(lane)}; ${why}]`,
                ],
                {
                  ...pin.metadata,
                  preflight: {
                    funding: "console-credit",
                    from: selector(route.primary),
                    to: selector(lane),
                  },
                },
              )
            }
            // Credits first for a Claude role: a lane not known empty takes
            // the launch. When every lane is empty, the usual preflight below
            // decides.
            if (lanes.ids.length > 0) {
              const lane = launchLane(route.primary, lanes, catalog)
              if (lane)
                return onLane(
                  lane,
                  "a Console credit lane is tried before the subscription.",
                )
            }
            context.signal.throwIfAborted()
            const snapshot = await loadQuotaExport(deps, quotaPath)
            context.signal.throwIfAborted()
            const probeOn = async (model: ModelRef, login?: string) => {
              let auth: Subscription | undefined
              try {
                auth =
                  login === undefined
                    ? await subscription(ctx, model.providerID)
                    : await loginOf(login)
                if (auth)
                  auth = { ...auth, proof: await identify(ctx, auth.proof) }
              } catch {}
              // A window limit a protected child hit is the provider's own
              // word and outranks an export that has not caught up yet.
              const quota = limited.blocked(
                login === undefined ? model.providerID : loginStop(login).key,
              )
                ? {
                    state: "exhausted" as const,
                    observedAt: deps.now(),
                    reason: "window limit observed on a protected child",
                  }
                : readQuota(snapshot, auth?.proof, deps.now())
              return {
                account: auth?.proof,
                quota,
                model: aliasOf(model, login),
                login,
              }
            }
            // A Claude model takes the active login unless Quota knows it is
            // spent; then the other saved logins in order, the first not
            // known spent, as the retry chain reaches them last. With every
            // login spent the active one is what the decision below weighs.
            const probe = async (model: ModelRef) => {
              const active = await probeOn(model)
              if (
                model.providerID !== OAUTH_PROVIDER ||
                freshState(active.quota, deps.now()) !== "exhausted"
              )
                return active
              for (const login of logins) {
                const alias = aliasOf(model, login)
                // The router picks a login by the longest suffix: an alias a
                // longer configured suffix claims would run elsewhere.
                if (
                  !catalogOk(catalog, alias) ||
                  stopFor(alias, suffixes).key !== loginStop(login).key
                )
                  continue
                const next = await probeOn(model, login)
                if (
                  next.account &&
                  freshState(next.quota, deps.now()) !== "exhausted"
                )
                  return next
              }
              return active
            }
            const source = await probe(route.primary)
            // A ChatGPT role whose window is spent goes to its Claude
            // alternate the way a Claude role starts: credits before the
            // subscription. With every lane empty, the usual preflight
            // launches the alternate on the subscription.
            if (
              lanes.ids.length > 0 &&
              route.primary.providerID !== OAUTH_PROVIDER &&
              freshState(source.quota, deps.now()) === "exhausted"
            ) {
              const lane = launchLane(route.alternate, lanes, catalog)
              if (lane)
                return onLane(
                  lane,
                  "Quota reports the default's included quota empty; a Console credit lane is tried before the subscription.",
                )
            }
            const target =
              source.quota.state === "exhausted"
                ? await probe(route.alternate)
                : undefined
            // The decision weighs the models on the logins the probes chose.
            const decision = decideLaunch({
              route: {
                primary: source.model,
                alternate: target?.model ?? route.alternate,
              },
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
            const alternate = decision.kind === "fallback"
            const chosen = alternate ? target! : source
            const account = chosen.account!
            const login = chosen.login
            const launch =
              pinned || !modelsEqual(decision.model, route.primary)
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
                  const current = await (
                    login === undefined
                      ? subscription(ctx, decision.model.providerID)
                      : loginOf(login)
                  ).catch(() => undefined)
                  if (
                    !current ||
                    current.proof.connectionID !== account.connectionID
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
                    ...(login === undefined ? {} : { login }),
                  }
                  await ctx.session.update({
                    sessionID: child.id,
                    metadata: withMarker(child.metadata, marker),
                  })
                  childID = child.id
                }
                await context.progress(update)
              },
            })
            if (!childID) fail("builtin did not await pre-launch registration")
            if (decision.kind === "default" && login === undefined)
              return pinned
                ? withNotices(result, pin.notices, pin.metadata)
                : result
            const notice =
              decision.kind === "credits"
                ? `[Subagent preflight: ${input.agent} ${selector(decision.model)}; Quota reports both included quotas at 0%, trying the default with provider-managed credits as last resort. No credit purchase or running-session switch.]`
                : decision.kind === "default"
                  ? `[Subagent preflight: ${input.agent} ${selector(route.primary)} → ${selector(decision.model)}; Quota reports the active Claude login's included quota empty and the next saved login not empty. No running-session switch.]`
                  : `[Subagent preflight: ${input.agent} ${selector(route.primary)} → ${selector(decision.model)}; Quota reports the default's included quota empty and the alternate not empty. No running-session switch.]`
            return withNotices(result, [...pin.notices, notice], {
              ...pin.metadata,
              preflight: {
                funding: decision.kind === "credits" ? "provider" : "included",
                from: selector(route.primary),
                to: selector(decision.model),
              },
            })
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
