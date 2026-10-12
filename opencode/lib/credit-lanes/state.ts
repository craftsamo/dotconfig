import { randomUUID } from "node:crypto"
import {
  closeSync,
  mkdirSync,
  openSync,
  readFileSync,
  renameSync,
  statSync,
  unlinkSync,
  writeFileSync,
  writeSync,
} from "node:fs"
import { homedir } from "node:os"
import { dirname, join } from "node:path"
import type { LaneState } from "./core"

// What changes as the lanes are used: the known grants and each lane's latest
// checkpoint. Kept out of the repository, beside OpenCode's own state.
// `revision` counts writes: a writer whose readings began before the last
// write must not write over it with older figures.
export type State = {
  version: 1
  revision: number
  lanes: Record<string, LaneState>
}

export function statePath(
  env: NodeJS.ProcessEnv = process.env,
  home = homedir(),
): string {
  return (
    env.CREDIT_LANES_STATE ||
    join(env.XDG_STATE_HOME || join(home, ".local", "state"), "opencode", "credit-lanes.json")
  )
}

export function readState(path = statePath()): State {
  let text: string
  try {
    text = readFileSync(path, "utf8")
  } catch {
    return { version: 1, revision: 0, lanes: {} }
  }
  const state = JSON.parse(text) as Partial<State>
  return { version: 1, revision: state.revision ?? 0, lanes: state.lanes ?? {} }
}

// Atomic, so a reader never sees half a file.
export function writeState(state: State, path = statePath()): void {
  mkdirSync(dirname(path), { recursive: true })
  const tmp = `${path}.${process.pid}.tmp`
  writeFileSync(tmp, `${JSON.stringify(state, null, 2)}\n`)
  renameSync(tmp, path)
}

// A lock names its holder (`<pid> <token>`). One whose process is gone is taken
// over; one that names no holder (a writer killed between creating and
// writing it) only after this long.
export const STALE_LOCK_MS = 120_000
export const LOCK_WAIT_MS = 15_000

const alive = (pid: number) => {
  try {
    process.kill(pid, 0)
    return true
  } catch (error) {
    return (error as NodeJS.ErrnoException).code === "EPERM"
  }
}

const read = (path: string) => {
  try {
    return readFileSync(path, "utf8")
  } catch {
    return undefined
  }
}

function abandoned(lock: string, holder: string | undefined): boolean {
  const pid = Number(holder?.split(" ")[0])
  if (pid > 0) return !alive(pid)
  try {
    return Date.now() - statSync(lock).mtimeMs > STALE_LOCK_MS
  } catch {
    return false
  }
}

// A guard held only for the moment of a takeover.
export const STALE_GUARD_MS = 10_000

// Removes an abandoned lock, one process at a time: under the guard, the lock
// is removed only if it still names the holder judged gone and is still
// abandoned, so a lock another process has taken meanwhile is never touched. Whoever then creates the lock
// first holds it.
function reclaim(lock: string, holder: string | undefined) {
  const guard = `${lock}.reclaim`
  try {
    closeSync(openSync(guard, "wx"))
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error
    try {
      if (Date.now() - statSync(guard).mtimeMs > STALE_GUARD_MS)
        unlinkSync(guard)
    } catch {}
    return
  }
  try {
    // Judged again under the guard: an empty lock created meanwhile is the
    // same content but young.
    const current = read(lock)
    if (current !== undefined && current === holder && abandoned(lock, current))
      unlinkSync(lock)
  } catch {
  } finally {
    try {
      unlinkSync(guard)
    } catch {}
  }
}

// Read, change and write the state under an exclusive lock: the Quota
// endpoint, the CLI and the retry hook all write it, and an update made while
// another was in flight would otherwise be lost. Written only when `fn`
// changed it, and never if `fn` throws.
export async function updateState<T>(
  fn: (state: State) => Promise<T> | T,
  path = statePath(),
): Promise<T> {
  const lock = `${path}.lock`
  const token = randomUUID()
  const mine = `${process.pid} ${token}`
  mkdirSync(dirname(path), { recursive: true })
  const deadline = Date.now() + LOCK_WAIT_MS
  for (;;) {
    try {
      const fd = openSync(lock, "wx")
      try {
        writeSync(fd, mine)
      } finally {
        closeSync(fd)
      }
      break
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error
    }
    const holder = read(lock)
    if (abandoned(lock, holder)) {
      reclaim(lock, holder)
      await new Promise((resolve) => setTimeout(resolve, 10))
      continue
    }
    if (Date.now() > deadline)
      throw new Error(`credit lane state is locked: ${lock}`)
    await new Promise((resolve) => setTimeout(resolve, 50))
  }
  try {
    const state = readState(path)
    const before = JSON.stringify(state)
    const result = await fn(state)
    if (JSON.stringify(state) !== before) {
      state.revision += 1
      writeState(state, path)
    }
    return result
  } finally {
    // Only our own lock: never one another process holds.
    if (read(lock) === mine)
      try {
        unlinkSync(lock)
      } catch {}
  }
}
