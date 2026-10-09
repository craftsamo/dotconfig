// Usage: bun opencode/lib/credit-lanes/status.ts
import { readFileSync } from "node:fs"
import {
  format,
  statsDays,
  summarize,
  type Lane,
  type StatsModel,
} from "./core"

const { lanes } = JSON.parse(
  readFileSync(new URL("./lanes.json", import.meta.url), "utf8"),
) as { lanes: Lane[] }

const now = new Date()
const cache = new Map<number, StatsModel[]>()

async function stats(days: number): Promise<StatsModel[]> {
  const hit = cache.get(days)
  if (hit) return hit
  const proc = Bun.spawn(
    ["opencode", "stats", "--days", String(days), "--full", "--json"],
    {
      stdout: "pipe",
      stderr: "pipe",
    },
  )
  const [out, code] = await Promise.all([
    new Response(proc.stdout).text(),
    proc.exited,
  ])
  if (code !== 0) throw new Error(`opencode stats failed (exit ${code})`)
  const models = (JSON.parse(out) as { models?: StatsModel[] }).models ?? []
  cache.set(days, models)
  return models
}

try {
  const summaries = []
  for (const lane of lanes)
    summaries.push(
      summarize(lane, await stats(statsDays(lane.grantedOn, now)), now),
    )
  console.log(format(summaries))
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error))
  process.exit(1)
}
