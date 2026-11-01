import { QUOTA_MAX_AGE_MS } from "./policy"
import { loadQuotaExport, type Dependencies } from "./quota"
import type { RuntimeContext } from "./runtime"

// OpenCode Quota checks its providers only when something asks (its TUI
// sidebar, /quota, a model turn, a limit), so with no TUI open its export
// goes stale and a launch falls back to the default route. A launch whose
// providers' rows are stale asks Quota itself to check them, through the
// RPC its TUI uses, and reads the export again once it is rewritten.
//
// Not a public interface: the id and the refresh input are those of
// @slkiser/opencode-quota 6.0.0 (dist/rpc.js); re-check them with a bump.
// A call needs only the id and the method names; Quota validates the
// input. Anything that fails leaves the launch on the export it read.
export const QUOTA_RPC = {
  id: "slkiser.opencode-quota",
  methods: { refresh: {} },
  events: {},
} as const

// The longest a launch waits for Quota's check (about a second when the
// providers answer); a check still running goes on for the next launch.
export const REFRESH_WAIT_MS = 5_000
// Quota writes the export just after its check answers.
export const REWRITE_POLLS = 10
export const REWRITE_POLL_MS = 100

// A timer that never keeps the process alive.
const wait = (ms: number) =>
  new Promise<void>((resolve) => {
    const timer = setTimeout(resolve, ms) as { unref?: () => void }
    timer.unref?.()
  })

const record = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v)

// Whether the export's part for one of these providers is missing or older
// than the launch selector trusts. A provider Quota reports unavailable
// (not set up) is not: a check cannot change that.
export function staleFor(
  snapshot: unknown,
  providerIDs: readonly string[],
  now: number,
): boolean {
  if (!record(snapshot) || !record(snapshot.providers)) return true
  const providers = snapshot.providers
  return providerIDs.some((id) => {
    const part = providers[id]
    if (record(part) && part.status === "unavailable") return false
    return (
      !record(part) ||
      typeof part.fetchedAt !== "number" ||
      !Number.isFinite(part.fetchedAt) ||
      now - part.fetchedAt * 1000 > QUOTA_MAX_AGE_MS
    )
  })
}

// After asking for a set of providers, a launch asks again no sooner than
// this: rows a check left stale (a provider Quota writes no part for, one
// that keeps failing) would otherwise cost every launch the wait.
export const ASK_AGAIN_MS = 60_000

// One per launcher. Launches that find the same providers stale share one
// check, and wait on it no longer than REFRESH_WAIT_MS or their own abort.
export class QuotaRefresher {
  private asked = new Map<string, number>()
  private running = new Map<string, Promise<boolean>>()

  async fresh(
    ctx: Pick<RuntimeContext, "rpc">,
    deps: Dependencies,
    path: string,
    snapshot: unknown,
    providerIDs: readonly string[],
    signal?: AbortSignal,
  ): Promise<unknown> {
    if (signal?.aborted || !staleFor(snapshot, providerIDs, deps.now()))
      return snapshot
    const ids = [...new Set(providerIDs)].sort()
    const key = ids.join(",")
    let check = this.running.get(key)
    if (!check) {
      const now = deps.now()
      if (now - (this.asked.get(key) ?? -Infinity) < ASK_AGAIN_MS)
        return snapshot
      let quota: ReturnType<NonNullable<RuntimeContext["rpc"]>> | undefined
      try {
        quota = ctx.rpc?.(QUOTA_RPC)
      } catch {}
      if (typeof quota?.refresh !== "function") return snapshot
      this.asked.set(key, now)
      const client = quota
      check = (async () => {
        await client.refresh!({ reason: "poll", providerIds: ids })
        return true
      })()
        .catch(() => false)
        .finally(() => this.running.delete(key))
      this.running.set(key, check)
    }
    const sleep = deps.sleep ?? wait
    const stop = new Promise<false>((resolve) =>
      signal?.addEventListener("abort", () => resolve(false), { once: true }),
    )
    const answered = await Promise.race([
      check,
      sleep(REFRESH_WAIT_MS).then(() => false as const),
      stop,
    ])
    if (!answered) return snapshot
    let latest = snapshot
    for (let poll = 0; poll <= REWRITE_POLLS && !signal?.aborted; poll++) {
      if (poll > 0) await sleep(REWRITE_POLL_MS)
      const next = await loadQuotaExport(deps, path)
      if (next !== undefined) latest = next
      if (!staleFor(latest, ids, deps.now())) break
    }
    return latest
  }
}
