// Usage: bun opencode/lib/credit-lanes/status.ts
//          the estimate for each lane
//        bun opencode/lib/credit-lanes/status.ts checkpoint <lane> <balance>
//          the balance the Console shows now, e.g. `checkpoint main 135.79`
//        bun opencode/lib/credit-lanes/status.ts grant <lane> <amount> <expires> [granted]
//          a grant the Console lists (dates YYYY-MM-DD; amount 0 removes it)
import {
  collect,
  loadConfig,
  recordCheckpoint,
  recordGrant,
  resolveLane,
} from "./collect"
import { format, ymd } from "./core"

const DATE = /^\d{4}-\d{2}-\d{2}$/

function amount(text: string | undefined): number {
  const value = Number(text?.replace(/^\$/, ""))
  if (text === undefined || !Number.isFinite(value))
    throw new Error(`not an amount: ${text ?? "(missing)"}`)
  return value
}

function date(text: string | undefined): string {
  if (!text || !DATE.test(text)) throw new Error(`not a date: ${text ?? "(missing)"}`)
  return text
}

try {
  const config = loadConfig()
  const [command, ...args] = process.argv.slice(2)
  if (command === "checkpoint") {
    const lane = resolveLane(config, args[0] ?? "")
    await recordCheckpoint(lane.provider, amount(args[1]), "console")
  } else if (command === "grant") {
    const lane = resolveLane(config, args[0] ?? "")
    await recordGrant(
      lane.provider,
      amount(args[1]),
      date(args[2]),
      args[3] ? date(args[3]) : ymd(new Date()),
    )
  } else if (command !== undefined) {
    throw new Error(`unknown command "${command}"; checkpoint or grant`)
  }
  console.log(format(await collect(), config.hermes?.order))
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error))
  process.exit(1)
}
