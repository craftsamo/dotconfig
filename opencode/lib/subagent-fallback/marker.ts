import { fail } from "./errors"
import { OAUTH_PROVIDER } from "./lanes"
import { modelsEqual, ROUTES, type ModelRef } from "./policy"

// The policy a launched child carries in its session metadata. Its guards
// apply only to the exact child it names.
export const METADATA_KEY = "dotconfig.subagent-preflight"

export type Marker = {
  version: 1
  childID: string
  parentID: string
  agent: string
  model: ModelRef
  connectionID: string
  fallback: boolean
  // The suffix of the saved Claude login the child runs on, through the
  // alias of its model; absent on the active login.
  login?: string
  launchChecked?: boolean
  wireChecked?: boolean
}

export type MarkedSession = {
  id: string
  parentID?: string
  agent?: string
  metadata?: Record<string, unknown>
}

// A route model on a saved login: its alias.
export const aliasOf = (
  model: ModelRef,
  login: string | undefined,
): ModelRef =>
  login === undefined ? model : { ...model, id: `${model.id}-${login}` }

export const selector = (m: ModelRef) =>
  `${m.providerID}/${m.id}${m.variant ? `#${m.variant}` : ""}`

const record = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

// The session's metadata with `marker` in place of any it had.
export const withMarker = (
  metadata: Record<string, unknown> | undefined,
  marker: Marker,
): Record<string, unknown> => ({ ...metadata, [METADATA_KEY]: marker })

export function parseMarker(session: MarkedSession): Marker | undefined {
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
    (raw.login !== undefined &&
      (typeof raw.login !== "string" || !raw.login)) ||
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
  const expected = marker.fallback ? route.alternate : route.primary
  if (
    (marker.login !== undefined && expected.providerID !== OAUTH_PROVIDER) ||
    !modelsEqual(marker.model, aliasOf(expected, marker.login))
  )
    fail("invalid persisted model selection")
  return marker
}
