import { readFile } from "node:fs/promises"
import { homedir } from "node:os"
import { join } from "node:path"
import type { QuotaEntry } from "./quota"

export const ANTIGRAVITY_QUOTA_ID = "google-antigravity"
export const ANTIGRAVITY_QUOTA_TOKEN = "antigravity-quota"
export const ANTIGRAVITY_ENDPOINT =
  "https://daily-cloudcode-pa.googleapis.com"
export const ANTIGRAVITY_DEFAULT_PROJECT_ID = "rising-fact-p41fc"
export const ANTIGRAVITY_MANIFEST_URL =
  "https://antigravity-hub-auto-updater-974169037036.us-central1.run.app/manifest/latest-arm64-mac.yml"
export const ANTIGRAVITY_VERSION_FALLBACK = "2.24.0"
export const ANTIGRAVITY_HUB_CHANGELISTS: Readonly<Record<string, string>> = {
  "2.23.0": "998057262",
  "2.23.1": "998881661",
  "2.24.0": "1000335682",
}

const VERSION_FLOOR = [2, 23, 0] as const
const SEMVER_RE = /^(\d{1,6})\.(\d{1,6})\.(\d{1,6})$/
const ISO_RE =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/
const IMAGE_RE = /image|imagen/i

export type Family = "gemini-pro" | "gemini-flash" | "claude"

export type GroupSummary = {
  family: Family
  name: string
  label: string
  percentRemaining: number
  resetTimeIso?: string
}

const FAMILY_META: Readonly<
  Record<Family, { name: string; label: string; rank: number }>
> = {
  "gemini-pro": { name: "Gemini Pro", label: "Pro:", rank: 0 },
  "gemini-flash": { name: "Gemini Flash", label: "Flash:", rank: 1 },
  claude: { name: "Claude", label: "Claude:", rank: 2 },
}

export type Connection = { type: string; id?: string; method?: string }
export type OAuthCredential = {
  type: string
  methodID?: string
  access?: string
  refresh?: string
  expires?: number
  metadata?: Record<string, unknown>
}
export type IntegrationContext = {
  integration?: {
    connection?: {
      active(providerID: string): Promise<Connection | undefined>
      resolve(connection: Connection): Promise<OAuthCredential | undefined>
    }
  }
}

export type StoredAccount = {
  id?: string
  email?: string
  refreshToken?: string
  projectId?: string
  managedProjectId?: string
  enabled?: boolean
}

export function accountsPath(
  env: NodeJS.ProcessEnv = process.env,
  home = homedir(),
): string {
  const dir =
    env.OPENCODE_CONFIG_DIR ||
    join(env.XDG_CONFIG_HOME || join(home, ".config"), "opencode")
  return join(dir, "antigravity-accounts.json")
}

export function parseRefreshParts(refresh: string | undefined): {
  refreshToken: string
  projectId?: string
  managedProjectId?: string
} {
  const [refreshToken = "", projectId = "", managedProjectId = ""] = (
    refresh ?? ""
  ).split("|")
  return {
    refreshToken: refreshToken.trim(),
    ...(projectId.trim() ? { projectId: projectId.trim() } : {}),
    ...(managedProjectId.trim()
      ? { managedProjectId: managedProjectId.trim() }
      : {}),
  }
}

export function parseManifestVersion(text: string): string | undefined {
  for (const line of text.split(/\r?\n/).slice(0, 40)) {
    if (!line.startsWith("version:")) continue
    const raw = line
      .slice("version:".length)
      .split(/\s#/)[0]
      .trim()
      .replace(/^['"]|['"]$/g, "")
    const m = SEMVER_RE.exec(raw)
    if (!m) return undefined
    const parts = [Number(m[1]), Number(m[2]), Number(m[3])] as const
    for (let i = 0; i < 3; i++) {
      if (parts[i] > VERSION_FLOOR[i]) return raw
      if (parts[i] < VERSION_FLOOR[i]) return undefined
    }
    return raw
  }
  return undefined
}

export function hubUserAgent(version = ANTIGRAVITY_VERSION_FALLBACK): string {
  const cl = ANTIGRAVITY_HUB_CHANGELISTS[version]
  return `antigravity/hub/${version} (aidev_client; os_type=darwin; arch=arm64${cl ? `; cl=${cl}` : ""})`
}

export function classifyFamily(
  modelId: string,
  displayName?: string,
): Family | undefined {
  const lowerId = modelId.toLowerCase()
  if (
    IMAGE_RE.test(lowerId) ||
    lowerId.endsWith("-disabled") ||
    lowerId.endsWith("-tiered")
  )
    return undefined
  const combined = `${lowerId} ${(displayName ?? "").toLowerCase()}`
  if (combined.includes("claude")) return "claude"
  if (!combined.includes("gemini")) return undefined
  return lowerId.includes("flash") ? "gemini-flash" : "gemini-pro"
}

function normalizeFraction(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return 0
  return Math.min(1, Math.max(0, value))
}

function normalizeIso(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined
  const trimmed = value.trim()
  if (!ISO_RE.test(trimmed)) return undefined
  const ms = Date.parse(trimmed)
  return Number.isFinite(ms) ? new Date(ms).toISOString() : undefined
}

export function summarizeAvailableModels(payload: unknown): GroupSummary[] {
  if (!payload || typeof payload !== "object" || Array.isArray(payload))
    return []
  const root = payload as Record<string, unknown>
  const models = root.models
  if (!models || typeof models !== "object" || Array.isArray(models)) return []

  const visible: string[] = []
  if (Array.isArray(root.agentModelSorts)) {
    for (const sort of root.agentModelSorts) {
      if (!sort || typeof sort !== "object") continue
      const groups = (sort as Record<string, unknown>).groups
      if (!Array.isArray(groups)) continue
      for (const g of groups) {
        if (!g || typeof g !== "object") continue
        const ids = (g as Record<string, unknown>).modelIds
        if (!Array.isArray(ids)) continue
        for (const id of ids) if (typeof id === "string" && id) visible.push(id)
      }
    }
  }
  const selectable =
    visible.length > 0
      ? new Set<string>([
          ...visible,
          ...Object.values(
            (root.tieredModelIds &&
            typeof root.tieredModelIds === "object" &&
            !Array.isArray(root.tieredModelIds)
              ? (root.tieredModelIds as Record<string, unknown>)
              : {}) as Record<string, unknown>,
          ).flatMap((v) =>
            Array.isArray(v)
              ? v.filter((id): id is string => typeof id === "string")
              : [],
          ),
        ])
      : undefined

  const byFamily = new Map<
    Family,
    { fraction: number; resetTimeIso?: string }
  >()

  for (const [modelId, rawEntry] of Object.entries(
    models as Record<string, unknown>,
  )) {
    if (!rawEntry || typeof rawEntry !== "object" || Array.isArray(rawEntry))
      continue
    const entry = rawEntry as Record<string, unknown>
    if (entry.disabled === true) continue
    if (selectable && !selectable.has(modelId)) continue
    const family = classifyFamily(
      modelId,
      typeof entry.displayName === "string" ? entry.displayName : undefined,
    )
    if (!family) continue
    const quotaInfo = entry.quotaInfo
    if (!quotaInfo || typeof quotaInfo !== "object" || Array.isArray(quotaInfo))
      continue
    const q = quotaInfo as Record<string, unknown>
    const fraction = normalizeFraction(q.remainingFraction)
    const resetTimeIso = normalizeIso(q.resetTime)
    const existing = byFamily.get(family)
    if (!existing) {
      byFamily.set(family, { fraction, resetTimeIso })
      continue
    }
    if (fraction < existing.fraction) {
      byFamily.set(family, { fraction, resetTimeIso })
    } else if (
      fraction === existing.fraction &&
      resetTimeIso &&
      (!existing.resetTimeIso ||
        Date.parse(resetTimeIso) < Date.parse(existing.resetTimeIso))
    ) {
      byFamily.set(family, { fraction, resetTimeIso })
    }
  }

  return Array.from(byFamily.entries())
    .sort(([a], [b]) => FAMILY_META[a].rank - FAMILY_META[b].rank)
    .map(([family, { fraction, resetTimeIso }]) => ({
      family,
      name: FAMILY_META[family].name,
      label: FAMILY_META[family].label,
      percentRemaining: Math.round(fraction * 100),
      ...(resetTimeIso ? { resetTimeIso } : {}),
    }))
}

export function toAntigravityQuotaV1(groups: GroupSummary[], now: Date) {
  const observedAtIso = now.toISOString()
  const entries: QuotaEntry[] = groups.map((g) => ({
    kind: "percent",
    name: g.name,
    resultType: "quota",
    percentRemaining: Math.min(100, Math.max(0, g.percentRemaining)),
    label: g.label,
    ...(g.resetTimeIso ? { resetTimeIso: g.resetTimeIso } : {}),
    observedAtIso,
  }))
  return { version: "quota-v1" as const, entries }
}

async function readStoredAccounts(
  path = accountsPath(),
): Promise<StoredAccount[]> {
  try {
    const raw = JSON.parse(await readFile(path, "utf8")) as {
      accounts?: unknown
    }
    return Array.isArray(raw.accounts)
      ? (raw.accounts.filter(
          (a): a is StoredAccount =>
            typeof a === "object" && a !== null && !Array.isArray(a),
        ) as StoredAccount[])
      : []
  } catch {
    return []
  }
}

function extractProjectId(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object" || Array.isArray(payload))
    return undefined
  const raw = (payload as Record<string, unknown>).cloudaicompanionProject
  const id =
    typeof raw === "string"
      ? raw
      : raw && typeof raw === "object"
        ? (raw as Record<string, unknown>).id
        : undefined
  return typeof id === "string" && id.trim() ? id.trim() : undefined
}

export type AntigravityDeps = {
  fetch: typeof globalThis.fetch
  readAccounts: () => Promise<StoredAccount[]>
  now: () => Date
}

export function createAntigravityCollector(
  ctx: IntegrationContext,
  deps: Partial<AntigravityDeps> = {},
) {
  const fetchFn = deps.fetch ?? globalThis.fetch
  const readAccounts = deps.readAccounts ?? (() => readStoredAccounts())
  const now = deps.now ?? (() => new Date())

  let cachedVersion: string | undefined
  const projectByToken = new Map<string, string>()

  const getVersion = async (): Promise<string> => {
    if (cachedVersion) return cachedVersion
    try {
      const res = await fetchFn(ANTIGRAVITY_MANIFEST_URL, {
        method: "GET",
        headers: {
          "User-Agent": "electron-builder",
          "Cache-Control": "no-cache",
        },
        signal: AbortSignal.timeout(5_000),
      })
      if (res.ok) {
        const text = (await res.text()).slice(0, 4096)
        cachedVersion = parseManifestVersion(text)
      }
    } catch {
      // fall back to pinned release
    }
    cachedVersion ??= ANTIGRAVITY_VERSION_FALLBACK
    return cachedVersion
  }

  const resolveProject = async (
    access: string,
    refresh: string | undefined,
    userAgent: string,
  ): Promise<string> => {
    const parts = parseRefreshParts(refresh)
    if (parts.managedProjectId) return parts.managedProjectId
    if (parts.projectId) return parts.projectId

    const accounts = await readAccounts()
    const match = accounts.find(
      (a) => a.refreshToken && a.refreshToken === parts.refreshToken,
    )
    if (match?.managedProjectId) return match.managedProjectId
    if (match?.projectId) return match.projectId

    if (parts.refreshToken && projectByToken.has(parts.refreshToken)) {
      return projectByToken.get(parts.refreshToken)!
    }

    try {
      const res = await fetchFn(
        `${ANTIGRAVITY_ENDPOINT}/v1internal:loadCodeAssist`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${access}`,
            "Content-Type": "application/json",
            "User-Agent": userAgent,
          },
          body: JSON.stringify({ metadata: { ideType: "ANTIGRAVITY" } }),
          signal: AbortSignal.timeout(8_000),
        },
      )
      if (res.ok) {
        const discovered = extractProjectId(await res.json())
        if (discovered) {
          if (parts.refreshToken)
            projectByToken.set(parts.refreshToken, discovered)
          return discovered
        }
      }
    } catch {
      // fall back to default project id
    }
    return ANTIGRAVITY_DEFAULT_PROJECT_ID
  }

  return async (): Promise<
    { version: "quota-v1"; entries: QuotaEntry[] } | undefined
  > => {
    const connection = await ctx.integration?.connection?.active("google")
    if (connection?.type !== "credential" || connection.method !== "oauth")
      return undefined
    const credential = await ctx.integration?.connection?.resolve(connection)
    if (
      credential?.type !== "oauth" ||
      (credential.methodID !== "antigravity" &&
        credential.methodID !== "oauth") ||
      typeof credential.access !== "string" ||
      !credential.access
    )
      return undefined

    const userAgent = hubUserAgent(await getVersion())
    const project = await resolveProject(
      credential.access,
      credential.refresh,
      userAgent,
    )
    const res = await fetchFn(
      `${ANTIGRAVITY_ENDPOINT}/v1internal:fetchAvailableModels`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${credential.access}`,
          "Content-Type": "application/json",
          "User-Agent": userAgent,
        },
        body: JSON.stringify(project ? { project } : {}),
        signal: AbortSignal.timeout(8_000),
      },
    )
    if (!res.ok) throw new Error(`fetchAvailableModels HTTP ${res.status}`)
    const groups = summarizeAvailableModels(await res.json())
    if (groups.length === 0) throw new Error("no Antigravity quota groups")
    return toAntigravityQuotaV1(groups, now())
  }
}
