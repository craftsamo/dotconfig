import { readFile } from "node:fs/promises"
import { homedir } from "node:os"
import { join } from "node:path"
import { recordCheckpoint } from "../credit-lanes/collect"
import { QUOTA_MAX_AGE_MS, type AccountProof, type QuotaProof } from "./policy"

export type Dependencies = {
  readExport: (path: string) => Promise<string>
  now: () => number
  // A lane reported an empty balance: a checkpoint for the balance estimate
  // (lib/credit-lanes).
  creditEmpty?: (provider: string) => Promise<void>
}

export const dependencies: Dependencies = {
  readExport: (path) => readFile(path, "utf8"),
  now: Date.now,
  creditEmpty: (provider) => recordCheckpoint(provider, 0, "empty"),
}

export function exportPath(
  env: Readonly<Record<string, string | undefined>> = process.env,
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

type Row = Record<string, unknown>

// A provider-reported percentage of a 5h or weekly window. Only those decide
// launch preference: plans differ (ChatGPT may lack 5h; xAI has only the
// weekly pool), and monthly credit and code-review rows aren't shared chat
// quota. Claude and xAI report quota; ChatGPT reported rate_limit in Quota 5.
const chatWindow = (row: unknown): row is Row =>
  record(row) &&
  ["quota", "rate_limit"].includes(String(row.resultType)) &&
  row.authority === "provider_reported" &&
  row.acquisitionMethod === "remote_api" &&
  row.renderType === "percent" &&
  (row.window === "5h" || row.window === "Weekly")

// Quota 5 (v2): sourceId is the OpenCode credential connection ID.
const v2Rows = (entries: unknown[], account: AccountProof): Row[] =>
  entries.filter(
    (row): row is Row =>
      chatWindow(row) && row.sourceId === account.connectionID,
  )

// The rows Quota 6 keeps per window, by id. A Claude model-specific window
// (Fable) is weekly too, so the window alone no longer singles them out.
const V3_IDS: Readonly<Record<string, readonly string[]>> = {
  anthropic: ["anthropic.five_hour", "anthropic.weekly"],
  openai: ["openai.five_hour", "openai.weekly"],
  xai: ["xai.credits"],
}

// Quota 6 (v3) exports no connection ID: a row's `account` is the login's
// label (with a plan after it in parentheses, as ChatGPT has), or nothing for
// a login without one. The integration's only login owns every row; another
// needs a label no other login has. Two rows for one window are two logins
// Quota cannot tell apart, which proves nothing.
function v3Rows(entries: unknown[], account: AccountProof): Row[] {
  const ids = V3_IDS[account.providerID] ?? []
  const windows = entries.filter(
    (row): row is Row => chatWindow(row) && ids.includes(String(row.id)),
  )
  const label = account.label
  const own = account.sole
    ? windows
    : label
      ? windows.filter(
          (row) =>
            typeof row.account === "string" &&
            (row.account === label || row.account.startsWith(`${label} (`)),
        )
      : []
  return new Set(own.map((row) => row.id)).size === own.length ? own : []
}

// Consume Quota's public JSON (v2 from Quota 5, v3 from Quota 6), not
// provider responses or human text. Never combine logins.
export function readQuota(
  snapshot: unknown,
  account: AccountProof | undefined,
  now: number,
): QuotaProof {
  const unknown = (): QuotaProof => ({ state: "unknown", observedAt: now })
  if (
    !account ||
    !record(snapshot) ||
    (snapshot.version !== 2 && snapshot.version !== 3) ||
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
  const rows =
    snapshot.version === 2
      ? v2Rows(provider.entries, account)
      : v3Rows(provider.entries, account)
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
