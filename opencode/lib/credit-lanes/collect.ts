import { execFile } from "node:child_process"
import { readFileSync } from "node:fs"
import {
  statsDays,
  summarize,
  type Lane,
  type StatsModel,
  type Summary,
} from "./core"

export function loadLanes(): Lane[] {
  const file = new URL("./lanes.json", import.meta.url)
  return (JSON.parse(readFileSync(file, "utf8")) as { lanes: Lane[] }).lanes
}

export type RunStats = (days: number) => Promise<StatsModel[]>

// `opencode stats` asks the running service for an aggregate, which takes about
// a second. Never read the history database from here: it is tens of GB.
export const runStats: RunStats = (days) =>
  new Promise((resolve, reject) =>
    execFile(
      process.env.OPENCODE_BIN || "opencode",
      ["stats", "--days", String(days), "--full", "--json"],
      { maxBuffer: 64 * 1024 * 1024, timeout: 30_000 },
      (error, stdout) => {
        if (error) return reject(error)
        try {
          resolve(
            (JSON.parse(stdout) as { models?: StatsModel[] }).models ?? [],
          )
        } catch (cause) {
          reject(cause)
        }
      },
    ),
  )

export async function collect(
  now = new Date(),
  lanes = loadLanes(),
  run: RunStats = runStats,
): Promise<Summary[]> {
  const cache = new Map<number, StatsModel[]>()
  const summaries: Summary[] = []
  for (const lane of lanes) {
    const days = statsDays(lane.grantedOn, now)
    if (!cache.has(days)) cache.set(days, await run(days))
    summaries.push(summarize(lane, cache.get(days)!, now))
  }
  return summaries
}
