import { AccountRouter, loginSubscription } from "./claude-accounts"
import { EmptyLanes } from "./empty-lanes"
import { FAIL_PREFIX, fail } from "./errors"
import { createGuards } from "./guards"
import {
  antigravityLimit,
  classify,
  DEFAULT_COOLDOWN_MS,
  Episodes,
  EPISODE_TTL_MS,
  Cooldowns,
  LONG_WAIT_MS,
  loginStop,
  nextModel,
  OAUTH_PROVIDER,
  passingOver,
  SIDE_AGENTS,
  stopFor,
  type Decision,
  type Role,
  type Stop,
} from "./lanes"
import { judgedDecision } from "./native-retry"
import { createLauncher } from "./launch"
import { METADATA_KEY, parseMarker } from "./marker"
import { readOptions } from "./options"
import { ANTIGRAVITY_PROVIDER, type ModelRef } from "./policy"
import { readRoutes, stopOf } from "./routes"
import {
  ANTIGRAVITY_GROUPS,
  antigravityKey,
  dependencies,
  groupKey,
  type Dependencies,
} from "./quota"
import { supported, type Registration, type RuntimeContext } from "./runtime"

export { METADATA_KEY }
export { MAX_CONTEXT_BYTES } from "./guards"
export { SUPPORTED_VERSIONS } from "./runtime"
export type { RuntimeContext }

export async function setupPreflight(
  ctx: RuntimeContext,
  deps: Dependencies = dependencies,
): Promise<() => Promise<void>> {
  const registrations: Registration[] = []
  const options = readOptions(ctx.options)
  // Console credit lanes (see lanes.ts). An empty list turns the whole
  // feature off, in-flight moves included.
  const lanes = new Cooldowns(
    options.creditLanes,
    options.creditCooldownMs,
    deps.now,
  )
  const episodes = new Episodes(EPISODE_TTL_MS, deps.now)
  // Lanes the balance estimate knows are empty: passed over until money can
  // have arrived, but for one try a day (empty-lanes.ts).
  const empty = new EmptyLanes()
  // Both survive a restart (saved.ts), so it costs no rejected request.
  if (lanes.ids.length > 0) {
    const saved = deps.saved?.load()
    if (saved) {
      lanes.restore(saved.cooldowns)
      empty.restore(saved, deps.now())
    }
  }
  const keep = () => {
    if (lanes.ids.length > 0)
      deps.saved?.save({
        cooldowns: lanes.saved(),
        ...empty.saved(deps.now()),
      })
  }
  // Specialists launched on a lane (launch.ts): unmarked, so a window limit
  // on the subscription they fall back to moves or stops them like a Claude
  // specialist, whatever their role's primary. Bounded, newest kept.
  const laneLaunched = new Set<string>()
  const launchedOnLane = (sessionID: string) => {
    laneLaunched.delete(sessionID)
    laneLaunched.add(sessionID)
    while (laneLaunched.size > 256)
      laneLaunched.delete(laneLaunched.values().next().value as string)
  }
  // Other saved Claude logins, reached by alias model (claude-accounts.ts).
  // Independent of `enabled`: an alias must never fall back to the active
  // login. Every configured suffix decides which login a model runs on; only
  // the labelled ones are places to move or launch.
  const claudeAccounts = AccountRouter.fromOption(options.claudeAccounts)
  const suffixes = claudeAccounts.accounts.map((account) => account.suffix)
  const logins = claudeAccounts.accounts
    .filter((account) => account.label !== "")
    .map((account) => account.suffix)
  const loginOf = (suffix: string) => {
    const account = claudeAccounts.accounts.find((a) => a.suffix === suffix)
    if (!account) throw new Error("no such Claude login")
    return loginSubscription(ctx, account)
  }
  // Each routed role's steps, and the primary's places (routes.ts).
  const routes = readRoutes(options, {
    lanes: options.creditLanes,
    logins,
    suffixes,
  })
  // The stops a specialist on `model` moves through, in its route's order:
  // the places of the role's steps that run the same model. None (a model
  // the route does not name) keeps the built-in order.
  const chainFor = (agent: string, model: ModelRef): Stop[] | undefined => {
    const from = stopFor(model, suffixes)
    const id = from.suffix
      ? model.id.slice(0, -(from.suffix.length + 1))
      : model.id
    const stops = (
      Object.hasOwn(routes.table, agent) ? routes.table[agent] : []
    )
      .filter(
        (step) =>
          step.model.providerID === OAUTH_PROVIDER && step.model.id === id,
      )
      .flatMap((step) => step.places.map(stopOf))
    return stops.length > 0 ? stops : undefined
  }
  // Subscription window limits protected children hit, kept for the wait
  // asked: the Quota export is rewritten only at Quota's next check, so the
  // parent's relaunch would otherwise bounce back to the same window. Each
  // Claude login is its own window, and each Antigravity group its own.
  const limited = new Cooldowns(
    [
      OAUTH_PROVIDER,
      ...logins.map((login) => loginStop(login).key),
      "openai",
      "xai",
      ...ANTIGRAVITY_GROUPS.map(groupKey),
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
  const protectedChild = async (sessionID: string) => {
    const session = await ctx.session.get({ sessionID })
    const marker = parseMarker(session, routes.table)
    return marker ? { session, marker } : undefined
  }
  const guards = createGuards(ctx, {
    protectedChild,
    loginOf,
    table: routes.table,
  })
  const launcher = createLauncher(ctx, {
    deps,
    options,
    routes,
    lanes,
    empty,
    keep,
    launchedOnLane,
    limited,
    suffixes,
    loginOf,
  })
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
        // A window limit by OpenCode's own decision (native-retry.ts): a
        // wait Quota stretched for an unrelated used-up row is not one.
        const own = judgedDecision(event)
        const rateLimit =
          event.error.type === "provider.rate-limit" ||
          event.error.status === 429
        const long = (d: Decision) => d.retry && d.delay > LONG_WAIT_MS
        if (event.error.type === "provider.quota" || (rateLimit && long(own))) {
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
          return
        }
        // A short limit with a stretched wait: retry as OpenCode would.
        if (rateLimit && long(event.decision)) event.decision = own
      }),
    )
    // An Antigravity group its plugin refused: any session's word, kept for
    // the wait it gave, so the next launch passes the group over before
    // Quota's export shows it spent. The session itself ends, as natively.
    registrations.push(
      await ctx.session.hook("retry", async (event) => {
        if (event.model?.providerID !== ANTIGRAVITY_PROVIDER) return
        const wait = antigravityLimit(event.error)
        if (wait === null) return
        const key = antigravityKey(event.model)
        if (key) limited.mark(key, wait)
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
        // Classified by OpenCode's own decision (native-retry.ts). A short
        // limit whose wait another plugin stretched is no failure: the
        // session stays and retries as OpenCode would have.
        const own = judgedDecision(event)
        const failure = classify(event.error, own)
        const stretched =
          !failure && classify(event.error, event.decision) === "quota"
        if (!failure && !stretched) return
        if (onLane && failure === "credit") {
          noteEmpty(provider)
          empty.refused(provider, deps.now())
          keep()
        }
        // A subscription failure matters only as a window limit; a lane
        // failure is any of the three.
        if (!onLane && failure !== undefined && failure !== "quota") return
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
          // A specialist launched on a lane runs a Claude model whatever its
          // role's primary, and carries no marker to stop it on a limit.
          const eligible =
            typeof agent === "string" &&
            Object.hasOwn(routes.table, agent) &&
            (routes.table[agent][0].model.providerID === OAUTH_PROVIDER ||
              laneLaunched.has(event.sessionID))
          // The subscription's limit is moved off only for the roles that opt
          // in: Claude specialists (and any launched on a lane), and the
          // primary when primaryFallback is on.
          const moves =
            onLane || (role === "primary" ? options.primaryFallback : eligible)
          if (stretched) {
            if (moves) event.decision = own
            return
          }
          // A window limit lasts as long as its wait; an empty balance or a
          // bad key lasts until someone fixes it, so those take the cooldown.
          // A bad key is fixed with a restart, which must not bring it back.
          if (onLane) {
            lanes.mark(
              provider,
              failure === "quota" && event.decision.retry
                ? event.decision.delay
                : undefined,
              failure !== "auth",
            )
            keep()
          }
          if (!moves) return
          const tried = episodes.record(
            event.sessionID,
            stopFor(event.model, suffixes).key,
          )
          const catalog = (await ctx.model.list({ location: session.location }))
            .data
          const now = deps.now()
          const { skip, due } = empty.scan(deps.readLanes?.(), now)
          const target = nextModel({
            current: event.model,
            role,
            lanes: passingOver(lanes, skip),
            logins,
            suffixes,
            tried,
            catalog,
            chain:
              role === "primary"
                ? routes.primary?.map(stopOf)
                : chainFor(agent as string, event.model),
          })
          if (target) {
            await ctx.session.switchModel({
              sessionID: event.sessionID,
              model: target,
            })
            // Noted once the session is on it: a failed switch tries nothing.
            if (due.has(target.providerID)) {
              empty.tried(target.providerID, now)
              keep()
            }
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
          tool.execute = launcher(tool.execute)
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
