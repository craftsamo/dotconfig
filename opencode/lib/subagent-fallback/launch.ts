import { identify, subscription, type Subscription } from "./accounts"
import { fail } from "./errors"
import {
  launchLane,
  loginStop,
  OAUTH_PROVIDER,
  stopFor,
  type Lanes,
} from "./lanes"
import {
  aliasOf,
  parseMarker,
  selector,
  withMarker,
  type Marker,
} from "./marker"
import type { PreflightOptions } from "./options"
import {
  catalogOk,
  decideLaunch,
  freshState,
  modelsEqual,
  routeForLaunch,
  ROUTES,
  type ModelRef,
} from "./policy"
import { loadQuotaExport, readQuota, type Dependencies } from "./quota"
import {
  supported,
  type Executor,
  type Result,
  type RuntimeContext,
} from "./runtime"

// The builtin subagent tool's launch of a routed role: on a credit lane, on
// the role's primary or alternate subscription, or on another saved Claude
// login, by what Quota and the protected children report.

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

export function createLauncher(
  ctx: RuntimeContext,
  state: {
    deps: Dependencies
    options: PreflightOptions
    lanes: Lanes
    // Window limits protected children hit.
    limited: Lanes
    logins: readonly string[]
    suffixes: readonly string[]
    loginOf: (suffix: string) => Promise<Subscription>
  },
): (original: Executor) => Executor {
  const { deps, options, lanes, limited, logins, suffixes, loginOf } = state
  return (original) => async (input, context) => {
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
          (input.model !== undefined && input.model !== selector(policy.model)))
      )
        fail(
          "protected continuations keep their role and model; use a new child for a different explicit selection",
        )
      return original(input, context)
    }
    if (
      !options.enabled ||
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
    const route = routeForLaunch(input, agent.model, options.pinModels)
    if (!route) return original(input, context)
    // pinModels: a project's agent file can name another model for a
    // role. Launch the role on its route anyway, the model made
    // explicit, and say so; its prompt and permissions stay.
    const pinned = !agent.model || !modelsEqual(agent.model, route.primary)
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
    const catalog = (await ctx.model.list({ location: parent.location })).data
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
    const snapshot = await loadQuotaExport(deps, options.quotaExportPath)
    context.signal.throwIfAborted()
    const probeOn = async (model: ModelRef, login?: string) => {
      let auth: Subscription | undefined
      try {
        auth =
          login === undefined
            ? await subscription(ctx, model.providerID)
            : await loginOf(login)
        if (auth) auth = { ...auth, proof: await identify(ctx, auth.proof) }
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
        if (next.account && freshState(next.quota, deps.now()) !== "exhausted")
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
    if (decision.kind === "credits" && !options.creditsLastResort)
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
          if (!current || current.proof.connectionID !== account.connectionID)
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
      return pinned ? withNotices(result, pin.notices, pin.metadata) : result
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
}
