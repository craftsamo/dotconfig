import type { Decision } from "./lanes"

// OpenCode's own retry decision, from before another plugin's retry hook
// rewrote it. OpenCode Quota's waitForQuotaReset sets the wait to the reset
// of any used-up row of the model's provider (another Claude login, a
// model-specific weekly window, a credit lane's estimate), so a rate limit
// OpenCode would retry in seconds can arrive here asking for hours. The
// recorder plugin (retry-recorder/), listed before Quota, keeps the decision
// it saw; the hooks here read it back. Shared through the global symbol
// registry, so separate module instances of the two plugins meet.
const KEY = Symbol.for("dotconfig.subagent-preflight.native-retry")

type Event = { decision: Decision }

const store = (): WeakMap<object, Decision> => {
  const g = globalThis as { [KEY]?: WeakMap<object, Decision> }
  return (g[KEY] ??= new WeakMap())
}

// Keyed by the event object every retry hook edits in turn. A host that gave
// each hook a copy would leave nothing to find: the current decision stands.
export function recordNative(event: Event): void {
  store().set(event, { ...event.decision })
}

// The decision OpenCode made, or the current one when nothing was recorded
// (no recorder, or it ran after another rewrite): then this plugin behaves
// as it did before it read the native decision.
export function nativeDecision(event: Event): Decision {
  return store().get(event) ?? event.decision
}

// Retries of one request judged by OpenCode's own wait. Past them the wait
// as it stands counts: a real window limit OpenCode retries quickly (no
// retry-after, a text Quota's error parser does not know) still ends up
// treated as one instead of retrying the spent window for good.
export const OWN_WAIT_ATTEMPTS = 3

// The decision a limit is judged by. OpenCode's own while it is a retry and
// the request is in its first attempts; otherwise the current one, as before
// the recorder: an own {retry: false} is OpenCode giving up, and a wait
// another plugin put on that is no short limit.
export function judgedDecision(event: Event & { attempt?: number }): Decision {
  const own = nativeDecision(event)
  return own.retry && (event.attempt ?? 1) <= OWN_WAIT_ATTEMPTS
    ? own
    : event.decision
}
