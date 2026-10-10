// Usage: bun opencode/lib/credit-lanes/status.ts
import { collect } from "./collect"
import { format } from "./core"

try {
  console.log(format(await collect()))
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error))
  process.exit(1)
}
