import { execFile } from "node:child_process"
import { existsSync, readdirSync } from "node:fs"
import { homedir } from "node:os"
import { join } from "node:path"

// Hermes' cost on the Console credit lanes, per usage row (session, model,
// mode, task) across every profile. `billing_provider = 'anthropic'` is the
// Console API key lane; the subscription is `anthropic-oauth`. A row is a
// running total, so spend since a checkpoint is each row's growth.
export type HermesUsage = Record<string, number>

const QUERY =
  "SELECT session_id, model, billing_mode, billing_base_url, task, " +
  "CASE WHEN actual_cost_usd > 0 THEN actual_cost_usd ELSE estimated_cost_usd END AS cost " +
  "FROM session_model_usage WHERE billing_provider = 'anthropic'"

type Row = {
  session_id: string
  model: string
  billing_mode: string
  billing_base_url: string
  task: string
  cost: number
}

export function expandHome(path: string, home = homedir()): string {
  return path === "~" || path.startsWith("~/") ? join(home, path.slice(1)) : path
}

export function hermesDatabases(root: string): { name: string; path: string }[] {
  const found: { name: string; path: string }[] = []
  const own = join(root, "state.db")
  if (existsSync(own)) found.push({ name: "default", path: own })
  const profiles = join(root, "profiles")
  if (existsSync(profiles))
    for (const name of readdirSync(profiles).sort()) {
      const path = join(profiles, name, "state.db")
      if (existsSync(path)) found.push({ name, path })
    }
  return found
}

const query = (path: string) =>
  new Promise<Row[]>((resolve, reject) =>
    execFile(
      "sqlite3",
      ["-readonly", "-json", "-cmd", ".timeout 3000", path, QUERY],
      { maxBuffer: 16 * 1024 * 1024, timeout: 10_000 },
      (error, stdout, stderr) => {
        // A profile that has never run has no usage table yet.
        if (error && /no such table/i.test(String(stderr))) return resolve([])
        if (error) return reject(error)
        try {
          resolve(stdout.trim() ? (JSON.parse(stdout) as Row[]) : [])
        } catch (cause) {
          reject(cause)
        }
      },
    ),
  )

// Rejects if any profile cannot be read: a snapshot missing one would count
// that profile's whole history as new spend later.
export async function readHermes(root: string): Promise<HermesUsage> {
  const usage: HermesUsage = {}
  for (const db of hermesDatabases(root))
    for (const row of await query(db.path))
      usage[
        [db.name, row.session_id, row.model, row.billing_mode, row.billing_base_url, row.task].join("\t")
      ] = Number(row.cost) || 0
  return usage
}

export function hermesSince(current: HermesUsage, base: HermesUsage): number {
  let sum = 0
  for (const [key, cost] of Object.entries(current))
    sum += Math.max(0, cost - (base[key] ?? 0))
  return sum
}
