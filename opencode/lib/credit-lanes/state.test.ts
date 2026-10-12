import { afterAll, describe, expect, test } from "bun:test"
import { existsSync, mkdtempSync, rmSync, utimesSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { readState, statePath, updateState, STALE_LOCK_MS } from "./state"

const dir = mkdtempSync(join(tmpdir(), "credit-lanes-state-"))
afterAll(() => rmSync(dir, { recursive: true, force: true }))
const grant = { amount: 1, granted: "2026-10-01", expires: "2026-11-01", source: "console" as const }

describe("state", () => {
  test("lives beside OpenCode's state unless overridden", () => {
    expect(statePath({}, "/home/x")).toBe("/home/x/.local/state/opencode/credit-lanes.json")
    expect(statePath({ XDG_STATE_HOME: "/s" }, "/home/x")).toBe("/s/opencode/credit-lanes.json")
    expect(statePath({ CREDIT_LANES_STATE: "/f.json" }, "/home/x")).toBe("/f.json")
  })
  test("a missing file is an empty state", () => {
    expect(readState(join(dir, "none.json"))).toEqual({ version: 1, revision: 0, lanes: {} })
  })
  test("each write counts a revision", async () => {
    const path = join(dir, "revision.json")
    await updateState((state) => {
      state.lanes.a = { grants: [] }
    }, path)
    await updateState(() => {}, path)
    await updateState((state) => {
      state.lanes.b = { grants: [] }
    }, path)
    expect(readState(path).revision).toBe(2)
  })
  test("concurrent updates are applied one after another, none lost", async () => {
    const path = join(dir, "concurrent.json")
    await Promise.all(
      ["a", "b", "c"].map((id) =>
        updateState(async (state) => {
          await new Promise((r) => setTimeout(r, 20))
          state.lanes[id] = { grants: [grant] }
        }, path),
      ),
    )
    expect(Object.keys(readState(path).lanes).sort()).toEqual(["a", "b", "c"])
    expect(existsSync(`${path}.lock`)).toBe(false)
  })
  test("nothing is written when unchanged or on an error, and the lock is released", async () => {
    const path = join(dir, "unchanged.json")
    await updateState(() => {}, path)
    expect(existsSync(path)).toBe(false)
    await expect(
      updateState((state) => {
        state.lanes.x = { grants: [] }
        throw new Error("boom")
      }, path),
    ).rejects.toThrow("boom")
    expect(existsSync(path)).toBe(false)
    expect(existsSync(`${path}.lock`)).toBe(false)
  })
  test("a lock whose process is gone is taken over", async () => {
    const path = join(dir, "dead.json")
    writeFileSync(`${path}.lock`, "999999999 gone")
    await updateState((state) => {
      state.lanes.x = { grants: [] }
    }, path)
    expect(readState(path).lanes.x).toEqual({ grants: [] })
    expect(existsSync(`${path}.lock`)).toBe(false)
  })
  test("a lock naming no holder is taken over only once it is old", async () => {
    const path = join(dir, "stale.json")
    writeFileSync(`${path}.lock`, "")
    const old = (Date.now() - STALE_LOCK_MS - 1000) / 1000
    utimesSync(`${path}.lock`, old, old)
    await updateState((state) => {
      state.lanes.x = { grants: [] }
    }, path)
    expect(readState(path).lanes.x).toEqual({ grants: [] })
  })
  test("a holder never removes a lock that is no longer its own", async () => {
    const path = join(dir, "foreign.json")
    await updateState(() => {
      // Another process took the lock over (it judged ours abandoned).
      writeFileSync(`${path}.lock`, `${process.pid} someone-else`)
    }, path)
    expect(existsSync(`${path}.lock`)).toBe(true)
    rmSync(`${path}.lock`)
  })
})
