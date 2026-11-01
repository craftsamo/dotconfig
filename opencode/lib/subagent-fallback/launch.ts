import { identify, subscription, type Subscription } from "./accounts"
import { fail } from "./errors"
import type { EmptyLanes } from "./empty-lanes"
import {
  launchLane,
  loginStop,
  passingOver,
  stopFor,
  type Cooldowns,
} from "./lanes"
import { parseMarker, selector, withMarker, type Marker } from "./marker"
import type { PreflightOptions } from "./options"
import {
  modelsEqual,
  REASON_NO_STEP,
  weigh,
  type AccountProof,
  type ModelRef,
  type QuotaProof,
} from "./policy"
import {
  loadQuotaExport,
  readQuota,
  SpentWindows,
  type Dependencies,
} from "./quota"
import { QuotaRefresher } from "./quota-refresh"
import {
  isLane,
  modelAt,
  stepsForLaunch,
  type Routes,
  type Step,
} from "./routes"
import {
  supported,
  type Executor,
  type Result,
  type RuntimeContext,
} from "./runtime"

// The builtin subagent tool's launch of a routed role: the first step of its
// route (routes.ts) that can take it, by what Quota, the lanes' balance
// estimate and the protected children report.

const withNotices = (
  result: Result,
  notices: string[],
  metadata: Record<string, unknown>,
): Result => {
  if (notices.length === 0 && Object.keys(metadata).length === 0) return result
  const text = notices.join("\n")
  return {
    ...result,
    metadata: { ...result.metadata, ...metadata },
    content:
      notices.length === 0
        ? result.content
        : typeof result.content === "string"
          ? `${text}\n${result.content}`
          : [{ type: "text", text }, ...(result.content ?? [])],
  }
}

const WHY_LANE = "a Console credit lane is tried before the subscription."
const WHY_LANE_SPENT =
  "Quota reports the default's included quota empty; a Console credit lane is tried before the subscription."
const WHY_LOGIN =
  "Quota reports an earlier Claude login's included quota empty and the next saved login not empty. No running-session switch."
const WHY_ALTERNATE =
  "Quota reports the default's included quota empty and the alternate not empty. No running-session switch."
const WHY_UNUSABLE =
  "an earlier step of the route has no approved login or usable catalog model. No running-session switch."
const WHY_LANES =
  "every credit lane of the route is known empty or cooling down. No running-session switch."
const WHY_FIRST =
  "the route's first step runs there. No running-session switch."
const WHY_LAST_RESORT =
  "Quota reports every included quota the route can use at 0%, trying the first of them with provider-managed credits as last resort. No credit purchase or running-session switch."

// A subscription place of a step, with what its login and Quota say.
type Candidate = {
  step: Step
  model: ModelRef
  login?: string
  account: AccountProof | undefined
  quota: QuotaProof
}

export function createLauncher(
  ctx: RuntimeContext,
  state: {
    deps: Dependencies
    options: PreflightOptions
    routes: Routes
    lanes: Cooldowns
    // Lanes the balance estimate knows are empty.
    empty: EmptyLanes
    // Saves the lane cooldowns and daily tries for a restart.
    keep: () => void
    // Notes a child launched on a lane.
    launchedOnLane: (sessionID: string) => void
    // Window limits protected children hit.
    limited: Cooldowns
    suffixes: readonly string[]
    loginOf: (suffix: string) => Promise<Subscription>
  },
): (original: Executor) => Executor {
  const { deps, options, routes, lanes, empty, keep, launchedOnLane } = state
  const { limited, suffixes, loginOf } = state
  const spent = new SpentWindows()
  const refresher = new QuotaRefresher()
  return (original) => async (input, context) => {
    // Outcome is historical, not a busy flag. There is no atomic
    // idle-and-release API, so protection stays with this exact child.
    if (typeof input.sessionID === "string") {
      const existing = await ctx.session.get({
        sessionID: input.sessionID,
      })
      const policy = parseMarker(existing, routes.table)
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
      !Object.hasOwn(routes.table, input.agent)
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
    const steps = stepsForLaunch(
      input,
      agent.model,
      options.pinModels,
      routes.table,
    )
    if (!steps) return original(input, context)
    const first = steps[0].model
    // pinModels: a project's agent file can name another model for a
    // role. Launch the role on its route anyway, the model made
    // explicit, and say so; its prompt and permissions stay. Steps the
    // config could not read are named too.
    const pinned = !agent.model || !modelsEqual(agent.model, first)
    const ignored = [
      ...(routes.problems[""] ?? []),
      ...(routes.problems[input.agent] ?? []),
    ]
    const pin = {
      notices: [
        ...(pinned
          ? [
              `[Model pin: ${input.agent} ${agent.model ? selector(agent.model) : "(no model)"} → ${selector(first)}; the agent definition in effect is replaced by the dotconfig route.]`,
            ]
          : []),
        ...(ignored.length > 0
          ? [`[Subagent preflight: config ignored: ${ignored.join("; ")}]`]
          : []),
      ],
      metadata: pinned
        ? {
            pin: {
              from: agent.model ? selector(agent.model) : null,
              to: selector(first),
            },
          }
        : {},
    }
    const catalog = (await ctx.model.list({ location: parent.location })).data
    // A launch on a lane carries no subscription marker (its guards
    // are for OAuth requests). Its child is noted, so a limit on the
    // subscription it may fall back to moves or stops it (index.ts).
    const onLane = async (lane: ModelRef, why: string) => {
      context.signal.throwIfAborted()
      const result = await original(
        { ...input, model: selector(lane) },
        {
          ...context,
          progress: async (update) => {
            if (
              typeof update.sessionID === "string" &&
              update.sessionID.startsWith("ses_")
            )
              launchedOnLane(update.sessionID)
            await context.progress(update)
          },
        },
      )
      return withNotices(
        result,
        [
          ...pin.notices,
          `[Subagent preflight: ${input.agent} ${selector(first)} → ${selector(lane)}; ${why}]`,
        ],
        {
          ...pin.metadata,
          preflight: {
            funding: "console-credit",
            from: selector(first),
            to: selector(lane),
          },
        },
      )
    }
    // A step's first lane past the cooldowns and the lanes known empty. A
    // known-empty lane taken for its daily try is noted, so the next
    // launches pass it over again.
    const pickLane = (model: ModelRef, ids: readonly string[]) => {
      const now = deps.now()
      const { skip, due } = empty.scan(deps.readLanes?.(), now)
      const view = passingOver(lanes, skip)
      const lane = launchLane(
        model,
        { ids, blocked: (id) => !lanes.has(id) || view.blocked(id) },
        catalog,
      )
      if (lane && due.has(lane.providerID)) {
        empty.tried(lane.providerID, now)
        keep()
      }
      return lane
    }
    // The export, read once the first subscription step is weighed. Stale
    // rows for the route's providers: Quota is asked to check them first
    // (quota-refresh.ts), since no TUI may be asking it to.
    const providers = [
      ...new Set(
        steps
          .filter((step) => !step.places.some(isLane))
          .map((step) => step.model.providerID),
      ),
    ]
    let snapshot: Promise<unknown> | undefined
    const exported = () =>
      (snapshot ??= (async () =>
        refresher.fresh(
          ctx,
          deps,
          options.quotaExportPath,
          await loadQuotaExport(deps, options.quotaExportPath),
          providers,
          context.signal,
        ))())
    const probe = async (
      step: Step,
      login: string | undefined,
    ): Promise<Candidate> => {
      const model = modelAt(
        step.model,
        login === undefined
          ? { kind: "active" }
          : { kind: "login", suffix: login },
      )
      let auth: Subscription | undefined
      try {
        auth =
          login === undefined
            ? await subscription(ctx, model.providerID)
            : await loginOf(login)
        if (auth) auth = { ...auth, proof: await identify(ctx, auth.proof) }
      } catch {}
      const read = await exported()
      context.signal.throwIfAborted()
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
        : spent.recall(
            auth?.proof,
            readQuota(read, auth?.proof, deps.now()),
            deps.now(),
          )
      return { step, model, login, account: auth?.proof, quota }
    }

    // The steps in order: a lane step launches on its first lane not known
    // empty; a subscription step on its first place Quota does not know
    // spent. A spent place is kept as the last resort.
    let passed: "none" | "unusable" | "spent" = "none"
    let lanesPassed = false
    let lastResort: Candidate | undefined
    let chosen: Candidate | undefined
    scan: for (const step of steps) {
      const laneIDs = step.places
        .filter((place) => place.kind === "lane")
        .map((place) => place.providerID)
      if (laneIDs.length > 0) {
        const lane = pickLane(step.model, laneIDs)
        if (lane)
          return onLane(lane, passed === "spent" ? WHY_LANE_SPENT : WHY_LANE)
        lanesPassed = true
        continue
      }
      for (const place of step.places) {
        const login = place.kind === "login" ? place.suffix : undefined
        // The router picks a login by the longest suffix: an alias a
        // longer configured suffix claims would run elsewhere.
        if (
          login !== undefined &&
          stopFor(modelAt(step.model, place), suffixes).key !==
            loginStop(login).key
        )
          continue
        context.signal.throwIfAborted()
        const candidate = await probe(step, login)
        const weight = weigh({ ...candidate, catalog, now: deps.now() })
        if (weight === "launch") {
          chosen = candidate
          break scan
        }
        if (weight === "spent") {
          passed = "spent"
          lastResort ??= candidate
        } else if (passed === "none") passed = "unusable"
      }
    }
    const resort = !chosen
    if (!chosen) {
      if (!lastResort) fail(REASON_NO_STEP)
      if (!options.creditsLastResort)
        fail(
          "every included quota of the route is exhausted; last-resort credits are disabled",
        )
      chosen = lastResort
    }
    const { model, login, account } = chosen
    const alternate = !modelsEqual(chosen.step.model, first)
    const launch =
      pinned || !modelsEqual(model, first)
        ? { ...input, model: selector(model) }
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
            !modelsEqual(child.model, model)
          )
            fail("builtin child launch policy mismatch")
          const current = await (
            login === undefined
              ? subscription(ctx, model.providerID)
              : loginOf(login)
          ).catch(() => undefined)
          if (!current || current.proof.connectionID !== account!.connectionID)
            fail("subscription account changed before launch")
          const marker: Marker = {
            version: 1,
            childID: child.id,
            parentID: context.sessionID,
            agent: input.agent as string,
            model,
            connectionID: account!.connectionID,
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
    if (!resort && modelsEqual(model, first) && passed === "none")
      return withNotices(result, pin.notices, pin.metadata)
    const notice = resort
      ? `[Subagent preflight: ${input.agent} ${selector(model)}; ${WHY_LAST_RESORT}]`
      : `[Subagent preflight: ${input.agent} ${selector(first)} → ${selector(model)}; ${
          passed === "spent"
            ? alternate
              ? WHY_ALTERNATE
              : WHY_LOGIN
            : passed === "unusable"
              ? WHY_UNUSABLE
              : lanesPassed
                ? WHY_LANES
                : WHY_FIRST
        }]`
    return withNotices(result, [...pin.notices, notice], {
      ...pin.metadata,
      preflight: {
        funding: resort ? "provider" : "included",
        from: selector(first),
        to: selector(model),
      },
    })
  }
}
