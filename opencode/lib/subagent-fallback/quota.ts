import { readFile } from "node:fs/promises"
import { homedir } from "node:os"
import { join } from "node:path"
import { QUOTA_MAX_AGE_MS, type AccountProof, type QuotaProof } from "./policy"

export type Dependencies = {
  readExport: (path: string) => Promise<string>
  now: () => number
}

export const dependencies: Dependencies = {
  readExport: (path) => readFile(path, "utf8"),
  now: Date.now,
}

export function exportPath(
  env: Pick<NodeJS.ProcessEnv, "XDG_CACHE_HOME"> = process.env,
  home = homedir(),
): string {
  return join(
    env.XDG_CACHE_HOME?.trim() || join(home, ".cache"),
    "opencode",
    "quota-export.json",
  )
}

const record = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v)
const finite = (v: unknown): v is number =>
  typeof v === "number" && Number.isFinite(v)

// Consume Quota 5.0.1's public v2 JSON, not provider responses or human text.
// sourceId is the OpenCode credential connection ID; never combine logins.
export function readQuota(
  snapshot: unknown,
  account: AccountProof | undefined,
  now: number,
): QuotaProof {
  const unknown = (): QuotaProof => ({ state: "unknown", observedAt: now })
  if (
    !account ||
    !record(snapshot) ||
    snapshot.version !== 2 ||
    !record(snapshot.providers)
  )
    return unknown()
  const provider = snapshot.providers[account.providerID]
  if (
    !record(provider) ||
    !["ok", "partial"].includes(String(provider.status)) ||
    !finite(provider.fetchedAt) ||
    !Array.isArray(provider.entries)
  )
    return unknown()
  const observedAt = provider.fetchedAt * 1000
  if (now < observedAt) return unknown()
  const fresh = now - observedAt <= QUOTA_MAX_AGE_MS
  const rows = provider.entries.filter(
    (row) =>
      record(row) &&
      row.sourceId === account.connectionID &&
      // Claude exports quota; ChatGPT exports the same windows as rate_limit.
      ["quota", "rate_limit"].includes(String(row.resultType)) &&
      row.authority === "provider_reported" &&
      row.acquisitionMethod === "remote_api" &&
      row.renderType === "percent" &&
      // Only the 5h and weekly windows decide launch preference. Plans differ
      // (ChatGPT may lack 5h), and model-specific, monthly credit and
      // code-review rows aren't shared chat quota.
      (row.window === "5h" || row.window === "Weekly"),
  ) as Record<string, unknown>[]
  if (!rows.length) return unknown()
  if (
    rows.some(
      (row) =>
        !finite(row.percentRemaining) ||
        row.percentRemaining > 100 ||
        (row.resetAt !== undefined && !finite(row.resetAt)),
    )
  )
    return unknown()
  const empty = (row: Record<string, unknown>) =>
    (row.percentRemaining as number) <= 0
  const pending = (row: Record<string, unknown>) =>
    finite(row.resetAt) && row.resetAt * 1000 > now
  // Either window at (rounded) 0% means the provider is exhausted; credits
  // may already be spent behind the scenes, so prefer the other provider.
  // A window cannot recover before its reset, so an empty row stays reliable
  // however old the export is (Quota refreshes only while the TUI is open).
  const exhausted = rows.filter((row) => empty(row) && pending(row))
  if (exhausted.length)
    return {
      state: "exhausted",
      observedAt,
      resetAt: Math.max(
        ...exhausted.map((row) => (row.resetAt as number) * 1000),
      ),
    }
  // Everything else (available, or an empty row without a reset time) needs
  // fresh data whose windows haven't reset since it was observed.
  if (!fresh || rows.some((row) => row.resetAt !== undefined && !pending(row)))
    return unknown()
  return {
    state: rows.some(empty) ? "exhausted" : "available",
    observedAt,
  }
}

export async function loadQuotaExport(
  deps: Dependencies,
  path: string,
): Promise<unknown> {
  try {
    return JSON.parse(await deps.readExport(path))
  } catch {
    // Unavailable Quota data keeps native defaults; it does not prove exhaustion.
    return undefined
  }
}
