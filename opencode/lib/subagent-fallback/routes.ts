import {
  longestSuffix,
  loginStop,
  OAUTH_PROVIDER,
  providerStop,
  type Stop,
} from "./lanes"
import { antigravityFamily } from "./quota"
import {
  aliasOf,
  ANTIGRAVITY_PROVIDER,
  METHODS,
  modelsEqual,
  ROUTES,
  type ModelRef,
  type Route,
} from "./policy"

// Each routed role's steps, in the order a launch tries them. A step is a
// model as /models names it, "<provider>/<model>[#<variant>]"; where it runs
// follows from that:
//   anthropic-credit-team/claude-haiku-5-5   a credit lane (in creditLanes)
//   anthropic/claude-haiku-5-5-main          a saved Claude login, by its
//                                            claudeAccounts suffix
//   anthropic/claude-haiku-5-5, openai/...   the provider's active login
// The `primaryRoute` option lists places alone, the model left as "*", for
// the primary session's moves off a limit: "anthropic/*-main",
// "anthropic-credit-team/*", "anthropic/*".

export type Place =
  | { kind: "active" }
  | { kind: "login"; suffix: string }
  | { kind: "lane"; providerID: string }

export type Step = { model: ModelRef; places: readonly Place[] }

export type RouteTable = Readonly<Record<string, readonly Step[]>>

export type Routes = {
  table: RouteTable
  // Config problems, by role ("" for the whole option), so a launch can
  // name the steps it ignored.
  problems: Readonly<Record<string, readonly string[]>>
  // The primary session's places in order; undefined keeps the built-in
  // order (lanes.ts nextModel).
  primary: readonly Place[] | undefined
}

// What tells a step's place from its model.
export type Names = {
  // The credit lanes' provider IDs, in spending order.
  lanes: readonly string[]
  // The saved Claude logins with a label, by suffix, in order.
  logins: readonly string[]
  // Every configured login suffix, labelled or not (the logins without).
  suffixes?: readonly string[]
}

const ACTIVE: Place = { kind: "active" }

// The model a step runs at a place.
export function modelAt(model: ModelRef, place: Place): ModelRef {
  if (place.kind === "login") return aliasOf(model, place.suffix)
  if (place.kind === "lane") return { ...model, providerID: place.providerID }
  return model
}

// The place a session moves to, as lanes.ts names it.
export function stopOf(place: Place): Stop {
  if (place.kind === "login") return loginStop(place.suffix)
  if (place.kind === "lane") return providerStop(place.providerID)
  return providerStop(OAUTH_PROVIDER)
}

export const isLane = (place: Place) => place.kind === "lane"

const MODEL = /^([a-z0-9][a-z0-9-]*)\/([^\s#@/*]+)(?:#([^\s#@]+))?$/
const ANY_MODEL = /^([a-z0-9][a-z0-9-]*)\/\*(?:-([^\s#@/*]+))?$/

// The place a provider and a login suffix name, or why there is none.
function placeOf(
  providerID: string,
  suffix: string | undefined,
  names: Names,
): Place | string {
  if (names.lanes.includes(providerID))
    return suffix === undefined
      ? { kind: "lane", providerID }
      : `a credit lane runs no login's alias`
  if (providerID === OAUTH_PROVIDER) {
    if (suffix === undefined) return ACTIVE
    return names.logins.includes(suffix)
      ? { kind: "login", suffix }
      : `no labelled Claude login "${suffix}" in claudeAccounts`
  }
  if (suffix === undefined && Object.hasOwn(METHODS, providerID)) return ACTIVE
  return `${providerID} is neither a credit lane in creditLanes nor a subscription provider`
}

// One step, or why it is ignored.
export function parseStep(
  text: unknown,
  names: Names,
): { step?: Step; problems: string[] } {
  if (typeof text !== "string") return { problems: ["a step must be a string"] }
  const match = MODEL.exec(text.trim())
  if (!match)
    return { problems: [`"${text}" is not a model ("provider/model#variant")`] }
  const [, providerID, full, variant] = match
  // A Claude alias names its login by the longest configured suffix, as the
  // request router does; the step keeps the model it sends.
  const suffix =
    providerID === OAUTH_PROVIDER
      ? longestSuffix(full, names.suffixes ?? names.logins)
      : undefined
  const place = placeOf(providerID, suffix, names)
  if (typeof place === "string") return { problems: [`"${text}": ${place}`] }
  // Its quota group decides an Antigravity step, and holds a refusal.
  if (
    providerID === ANTIGRAVITY_PROVIDER &&
    !antigravityFamily({ id: full, providerID })
  )
    return {
      problems: [
        `"${text}": in no Antigravity quota group (Gemini Pro, Gemini Flash, Claude)`,
      ],
    }
  const id = suffix === undefined ? full : full.slice(0, -(suffix.length + 1))
  const base = place.kind === "lane" ? OAUTH_PROVIDER : providerID
  const model: ModelRef =
    variant === undefined
      ? { id, providerID: base }
      : { id, providerID: base, variant }
  return { step: { model, places: [place] }, problems: [] }
}

// The places of `primaryRoute`: "<provider>/*", or "anthropic/*-<login>".
export function parsePlaces(
  value: unknown,
  names: Names,
): { places?: Place[]; problems: string[] } {
  if (value === undefined) return { problems: [] }
  if (!Array.isArray(value))
    return { problems: ["primaryRoute must be a list of places"] }
  const places: Place[] = []
  const problems: string[] = []
  for (const text of value) {
    const match = typeof text === "string" ? ANY_MODEL.exec(text.trim()) : null
    if (!match) {
      problems.push(
        `primaryRoute: ${JSON.stringify(text)} is not a place ("provider/*" or "anthropic/*-<login>")`,
      )
      continue
    }
    const place = placeOf(match[1], match[2], names)
    if (typeof place === "string")
      problems.push(`primaryRoute: "${text}": ${place}`)
    else places.push(place)
  }
  return { places, problems }
}

// A role's built-in steps, from its two-model route: a Claude model on the
// lanes, then the active login, then the other saved logins; any other
// model on its active login.
export function defaultSteps(route: Route, names: Names): Step[] {
  const lanes: Place[] = names.lanes.map((providerID) => ({
    kind: "lane",
    providerID,
  }))
  const logins: Place[] = names.logins.map((suffix) => ({
    kind: "login",
    suffix,
  }))
  const on = (model: ModelRef): Step[] =>
    model.providerID === OAUTH_PROVIDER
      ? [
          ...(lanes.length > 0 ? [{ model, places: lanes }] : []),
          { model, places: [ACTIVE] },
          ...(logins.length > 0 ? [{ model, places: logins }] : []),
        ]
      : [{ model, places: [ACTIVE] }]
  return [...on(route.primary), ...on(route.alternate)]
}

// The table in effect: the `routes` option's roles over the built-in ones.
// A role listed with [] is not routed.
export function readRoutes(
  options: { routes?: unknown; primaryRoute?: unknown },
  names: Names,
): Routes {
  const table: Record<string, readonly Step[]> = {}
  const problems: Record<string, string[]> = {}
  const note = (role: string, list: string[]) => {
    if (list.length > 0) (problems[role] ??= []).push(...list)
  }
  for (const [role, route] of Object.entries(ROUTES))
    table[role] = defaultSteps(route, names)
  const option = options.routes
  if (option !== undefined) {
    if (typeof option !== "object" || option === null || Array.isArray(option))
      note("", ["routes must map roles to lists of steps"])
    else
      for (const [role, value] of Object.entries(option)) {
        if (!Array.isArray(value)) {
          note(role, [`routes.${role} must be a list of steps`])
          continue
        }
        const steps: Step[] = []
        for (const text of value) {
          const { step, problems: found } = parseStep(text, names)
          if (step) steps.push(step)
          note(
            role,
            found.map((p) => `routes.${role}: ${p}`),
          )
        }
        // An empty list unroutes the role; one with nothing readable keeps
        // the built-in steps, so its launches still name the problems.
        if (steps.length > 0) table[role] = steps
        else if (value.length === 0) delete table[role]
        else if (!Object.hasOwn(ROUTES, role))
          note("", [`routes.${role} has no step it can use`])
      }
  }
  const primary = parsePlaces(options.primaryRoute, names)
  note("", primary.problems)
  // Nothing readable keeps the built-in order rather than no move at all.
  const places = primary.places?.length ? primary.places : undefined
  if (primary.places && !places)
    note("", ["primaryRoute has no place; the built-in order applies"])
  return {
    table: Object.freeze(table),
    problems: Object.freeze(problems),
    primary: places,
  }
}

// The steps of a new launch the preflight selects. With pin, a role keeps
// its steps even when the agent definition in effect (a project's own agent
// file, say) names another model or none at all; without it, only when that
// model is the first step's.
export function stepsForLaunch(
  input: { agent?: unknown; model?: unknown; sessionID?: unknown },
  configured: ModelRef | undefined,
  pin: boolean,
  table: RouteTable,
): readonly Step[] | undefined {
  if (input.model !== undefined) return undefined
  if (input.sessionID !== undefined) return undefined
  if (typeof input.agent !== "string") return undefined
  if (!Object.hasOwn(table, input.agent)) return undefined
  const steps = table[input.agent]
  if (pin) return steps
  if (!configured || !modelsEqual(steps[0].model, configured)) return undefined
  return steps
}
