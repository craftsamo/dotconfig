import { mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs"
import { homedir } from "node:os"
import { dirname, join } from "node:path"

// What the preflight keeps across restarts, in epoch ms: when each lane's
// cooldown ends, when a lane known empty had its daily try, and when a lane
// last refused a request for its balance. Beside the credit-lane state;
// nothing here is a secret. Without it a restart forgets them and costs a
// rejected request per lane.
export type Saved = {
  cooldowns: Record<string, number>
  probed: Record<string, number>
  refused: Record<string, number>
}
export type SavedStore = {
  load(): Saved
  save(saved: Saved): void
}

export function savedPath(
  env: Readonly<Record<string, string | undefined>> = process.env,
  home = homedir(),
): string {
  return join(
    env.XDG_STATE_HOME || join(home, ".local", "state"),
    "opencode",
    "subagent-preflight.json",
  )
}

const times = (value: unknown): Record<string, number> =>
  typeof value === "object" && value !== null && !Array.isArray(value)
    ? Object.fromEntries(
        Object.entries(value).filter(
          (entry): entry is [string, number] =>
            typeof entry[1] === "number" && Number.isFinite(entry[1]),
        ),
      )
    : {}

// A file that cannot be read or written leaves the preflight as it was
// without one: it only ever saves rejected requests.
export function fileStore(path = savedPath()): SavedStore {
  return {
    load() {
      try {
        const raw = JSON.parse(readFileSync(path, "utf8")) as Partial<Saved>
        return {
          cooldowns: times(raw.cooldowns),
          probed: times(raw.probed),
          refused: times(raw.refused),
        }
      } catch {
        return { cooldowns: {}, probed: {}, refused: {} }
      }
    },
    save(saved) {
      try {
        mkdirSync(dirname(path), { recursive: true })
        const tmp = `${path}.${process.pid}.tmp`
        writeFileSync(
          tmp,
          `${JSON.stringify({ version: 1, ...saved }, null, 2)}\n`,
        )
        renameSync(tmp, path)
      } catch {}
    },
  }
}
