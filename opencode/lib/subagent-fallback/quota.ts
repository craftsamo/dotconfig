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
  if (now < observedAt || now - observedAt > QUOTA_MAX_AGE_MS) return unknown()
  const rows = provider.entries.filter(
    (row) =>
      record(row) &&
      row.sourceId === account.connectionID &&
      // Claude exports quota; ChatGPT exports the same windows as rate_limit.
      ["quota", "rate_limit"].includes(String(row.resultType)) &&
      row.authority === "provider_reported" &&
      row.acquisitionMethod === "remote_api" &&
      row.renderType === "percent" &&
      // Monthly usage credits and code-review-only limits aren't included chat quota.
      row.window !== "Monthly" &&
      row.window !== "Code Review",
  ) as Record<string, unknown>[]
  if (
    !["5h", "Weekly"].every((window) =>
      rows.some((row) => row.window === window),
    )
  )
    return unknown()
  if (
    rows.some(
      (row) =>
        !finite(row.percentRemaining) ||
        row.percentRemaining > 100 ||
        (row.resetAt !== undefined &&
          (!finite(row.resetAt) || row.resetAt * 1000 <= now)),
    )
  )
    return unknown()
  // Quota's published (possibly rounded) 0% is sufficient for launch preference.
  // Additional named quota rows apply conservatively to the provider, not a guessed model.
  const empty = rows.filter((row) => (row.percentRemaining as number) <= 0)
  return {
    state: empty.length ? "exhausted" : "available",
    observedAt,
    ...(empty.length && empty.every((row) => finite(row.resetAt))
      ? {
          resetAt: Math.max(
            ...empty.map((row) => (row.resetAt as number) * 1000),
          ),
        }
      : {}),
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
