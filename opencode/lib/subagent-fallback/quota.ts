import { readFileSync } from "node:fs"
import { readFile } from "node:fs/promises"
import { homedir } from "node:os"
import { join } from "node:path"
import {
  ANTIGRAVITY_QUOTA_ID,
  classifyFamily,
  familyName,
  type Family,
} from "../credit-lanes/antigravity"
import { recordCheckpoint } from "../credit-lanes/collect"
import { readLaneBook, type LaneBook } from "./empty-lanes"
import { fileStore, type SavedStore } from "./saved"
import {
  QUOTA_MAX_AGE_MS,
  type AccountProof,
  type ModelRef,
  type QuotaProof,
} from "./policy"

export type Dependencies = {
  readExport: (path: string) => Promise<string>
  now: () => number
  // A lane reported an empty balance: a checkpoint for the balance estimate
  // (lib/credit-lanes).
  creditEmpty?: (provider: string) => Promise<void>
  // The balance estimate's lanes and state, to pass over lanes known empty.
  // Without it no lane is.
  readLanes?: () => LaneBook | undefined
  // Lane cooldowns and daily tries kept across restarts. Without it they
  // last as long as the process.
  saved?: SavedStore
  // Waits that long; a timer by default.
  sleep?: (ms: number) => Promise<void>
  // The percent left at which an Antigravity group is spent (10 without).
  antigravityReserve?: () => number
}

export const dependencies: Dependencies = {
  readExport: (path) => readFile(path, "utf8"),
  now: Date.now,
  antigravityReserve: () => antigravityReserve(),
  creditEmpty: (provider) => recordCheckpoint(provider, 0, "empty"),
  readLanes: readLaneBook,
  saved: fileStore(),
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
  // however old the export is (Quota checks only when something asks, so
  // with no TUI open it can stay unchanged for hours).
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

// Antigravity's quota groups, as the credit-lanes endpoint reports them to
// Quota's custom providers: one row per group (Gemini Pro, Gemini Flash,
// Claude), the model's family deciding which. Its plugin refuses a group
// once its use passes soft_quota_threshold_percent, so a group with no more
// than `reserve` percent left is spent too.
export function antigravityFamily(model: ModelRef): Family | undefined {
  return classifyFamily(model.id.replace(/^antigravity-/, ""))
}
// The place a limit on one group marks (index.ts `limited`).
export const ANTIGRAVITY_GROUPS: readonly Family[] = [
  "gemini-pro",
  "gemini-flash",
  "claude",
]
export const groupKey = (family: Family) => `google#${family}`
export function antigravityKey(model: ModelRef): string | undefined {
  const family = antigravityFamily(model)
  return family && groupKey(family)
}
export function readAntigravity(
  snapshot: unknown,
  model: ModelRef,
  now: number,
  reserve: number,
): QuotaProof {
  const unknown = (): QuotaProof => ({ state: "unknown", observedAt: now })
  const family = antigravityFamily(model)
  if (!family || !record(snapshot) || snapshot.version !== 3) return unknown()
  const part = record(snapshot.providers)
    ? snapshot.providers[CUSTOM_PROVIDERS]
    : undefined
  if (
    !record(part) ||
    !["ok", "partial"].includes(String(part.status)) ||
    !finite(part.fetchedAt) ||
    !Array.isArray(part.entries)
  )
    return unknown()
  const id = `${CUSTOM_PROVIDERS}.custom.${ANTIGRAVITY_QUOTA_ID}.${familyName(family).replace(/\s+/g, "_")}`
  const rows = part.entries.filter(
    (row): row is Row => record(row) && row.id === id,
  )
  if (rows.length !== 1) return unknown()
  const row = rows[0]
  const observedAt = part.fetchedAt * 1000
  if (
    now < observedAt ||
    !finite(row.percentRemaining) ||
    row.percentRemaining > 100 ||
    (row.resetAt !== undefined && !finite(row.resetAt))
  )
    return unknown()
  const spent = row.percentRemaining <= reserve
  const resetAt = finite(row.resetAt) ? row.resetAt * 1000 : undefined
  const pending = resetAt !== undefined && resetAt > now
  // As a window: spent until its reset at any age, anything else fresh.
  if (spent && pending) return { state: "exhausted", observedAt, resetAt }
  if (
    now - observedAt > QUOTA_MAX_AGE_MS ||
    (resetAt !== undefined && !pending)
  )
    return unknown()
  return { state: spent ? "exhausted" : "available", observedAt }
}

// Where Quota's export keeps its custom providers' rows.
export const CUSTOM_PROVIDERS = "quota-providers"

// The share Antigravity's plugin keeps back, from its user config, found as
// the plugin finds it: 100 less soft_quota_threshold_percent (1 to 100, 90
// by default). A project's own .opencode/antigravity.json is not read.
export function antigravityReserve(
  env: Readonly<Record<string, string | undefined>> = process.env,
  home = homedir(),
): number {
  const dir =
    env.OPENCODE_CONFIG_DIR ||
    join(env.XDG_CONFIG_HOME || join(home, ".config"), "opencode")
  try {
    const value = JSON.parse(
      readFileSync(join(dir, "antigravity.json"), "utf8"),
    )?.soft_quota_threshold_percent
    if (finite(value) && value >= 1 && value <= 100) return 100 - value
  } catch {}
  return 10
}

// Logins Quota reported spent, until the reset it gave. The export keeps
// only a provider's last check, and a failed check leaves no rows, so a
// login known spent would read as unknown again. A window cannot recover
// before its reset, so that reading stands until then when nothing newer is
// known; any other reading replaces it.
export class SpentWindows {
  private spent = new Map<string, QuotaProof>()
  recall(
    account: AccountProof | undefined,
    proof: QuotaProof,
    now: number,
  ): QuotaProof {
    if (!account) return proof
    const key = `${account.providerID}/${account.connectionID}`
    if (proof.state === "unknown") {
      const kept = this.spent.get(key)
      if (kept?.resetAt !== undefined && kept.resetAt > now) return kept
      this.spent.delete(key)
      return proof
    }
    if (proof.state === "exhausted" && proof.resetAt !== undefined)
      this.spent.set(key, proof)
    else this.spent.delete(key)
    return proof
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
