import { homedir } from "node:os"
import { join } from "node:path"
import { fileStore } from "./saved"
import {
  dependencies,
  exportPath,
  type Dependencies,
} from "./quota"

// What the plugin reads and keeps, injectable for tests. `saved` holds the
// lanes' daily tries; `exportFile` is Quota's JSON export.
export type StepsDeps = Dependencies & { exportFile: string }

// Beside the credit-lane state.
export function statePath(
  env: Readonly<Record<string, string | undefined>> = process.env,
  home = homedir(),
): string {
  return join(
    env.XDG_STATE_HOME || join(home, ".local", "state"),
    "opencode",
    "fallback-steps.json",
  )
}

export const defaultDeps: StepsDeps = {
  ...dependencies,
  saved: fileStore(statePath()),
  exportFile: exportPath(),
}
