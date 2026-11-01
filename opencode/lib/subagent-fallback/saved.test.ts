import { describe, expect, test } from "bun:test"
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { EMPTY_PROBE_MS, EmptyLanes } from "./empty-lanes"
import { Cooldowns } from "./lanes"
import { fileStore, savedPath } from "./saved"

const NOW = 1_710_000_000_000

describe("saved preflight state", () => {
  test("lives beside OpenCode's other state", () => {
    expect(savedPath({ XDG_STATE_HOME: "/state" }, "/home/u")).toBe(
      "/state/opencode/subagent-preflight.json",
    )
    expect(savedPath({}, "/home/u")).toBe(
      "/home/u/.local/state/opencode/subagent-preflight.json",
    )
  })
  test("a file round-trips, and a missing or broken one reads as empty", async () => {
    const dir = await mkdtemp(join(tmpdir(), "preflight-saved-"))
    try {
      const path = join(dir, "nested", "saved.json")
      const store = fileStore(path)
      expect(store.load()).toEqual({ cooldowns: {}, probed: {} })
      store.save({ cooldowns: { a: NOW }, probed: { b: NOW - 1 } })
      expect(store.load()).toEqual({
        cooldowns: { a: NOW },
        probed: { b: NOW - 1 },
      })
      expect(JSON.parse(await readFile(path, "utf8")).version).toBe(1)
      await writeFile(
        path,
        '{"cooldowns": {"a": "soon", "b": 3}, "probed": []}',
      )
      expect(store.load()).toEqual({ cooldowns: { b: 3 }, probed: {} })
      await writeFile(path, "not json")
      expect(store.load()).toEqual({ cooldowns: {}, probed: {} })
    } finally {
      await rm(dir, { recursive: true, force: true })
    }
  })
  test("cooldowns come back only for their lanes, running, and no longer than one", () => {
    let now = NOW
    const before = new Cooldowns(["a", "b"], 3_600_000, () => now)
    before.mark("a", 60_000)
    before.mark("b")
    const saved = before.saved()
    now += 30_000
    const after = new Cooldowns(["a", "c"], 3_600_000, () => now)
    after.restore({ ...saved, c: now + 7_200_000, d: now + 1 })
    expect(after.blocked("a")).toBe(true)
    expect(after.blocked("c")).toBe(false)
    now += 31_000
    expect(after.blocked("a")).toBe(false)
    expect(after.saved()).toEqual({})
  })
  test("a lane's try comes back for a cycle, not from the future", () => {
    const old = NOW - 36 * 86_400_000
    const before = new EmptyLanes()
    before.tried("a", old)
    before.tried("b", NOW - EMPTY_PROBE_MS)
    expect(before.saved(NOW)).toEqual({ b: NOW - EMPTY_PROBE_MS })
    const after = new EmptyLanes()
    after.restore({ b: NOW - 60_000, c: NOW + 1, d: old }, NOW)
    expect(after.saved(NOW)).toEqual({ b: NOW - 60_000 })
  })
  test("a cooldown a restart should lift is not kept", () => {
    const lanes = new Cooldowns(["a", "b"], 3_600_000, () => NOW)
    lanes.mark("a", undefined, false)
    lanes.mark("b")
    expect(Object.keys(lanes.saved())).toEqual(["b"])
    lanes.mark("a")
    expect(Object.keys(lanes.saved()).sort()).toEqual(["a", "b"])
  })
})
