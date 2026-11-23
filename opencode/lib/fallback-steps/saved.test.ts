import { describe, expect, test } from "bun:test"
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { EMPTY_PROBE_MS, EmptyLanes } from "./empty-lanes"
import { fileStore } from "./saved"

const NOW = 1_710_000_000_000

describe("saved preflight state", () => {
  test("a file round-trips, and a missing or broken one reads as empty", async () => {
    const dir = await mkdtemp(join(tmpdir(), "preflight-saved-"))
    try {
      const path = join(dir, "nested", "saved.json")
      const store = fileStore(path)
      const none = { cooldowns: {}, probed: {}, refused: {} }
      expect(store.load()).toEqual(none)
      store.save({
        cooldowns: { a: NOW },
        probed: { b: NOW - 1 },
        refused: { c: NOW - 2 },
      })
      expect(store.load()).toEqual({
        cooldowns: { a: NOW },
        probed: { b: NOW - 1 },
        refused: { c: NOW - 2 },
      })
      expect(JSON.parse(await readFile(path, "utf8")).version).toBe(1)
      // A file from before refusals were kept, and one with bad values.
      await writeFile(
        path,
        '{"cooldowns": {"a": "soon", "b": 3}, "probed": []}',
      )
      expect(store.load()).toEqual({ ...none, cooldowns: { b: 3 } })
      await writeFile(path, "not json")
      expect(store.load()).toEqual(none)
    } finally {
      await rm(dir, { recursive: true, force: true })
    }
  })
  test("a lane's tries and refusals come back for a cycle, not from the future", () => {
    const old = NOW - 36 * 86_400_000
    const before = new EmptyLanes()
    before.tried("a", old)
    before.tried("b", NOW - EMPTY_PROBE_MS)
    before.refused("c", NOW - 1)
    before.refused("d", old)
    expect(before.saved(NOW)).toEqual({
      probed: { b: NOW - EMPTY_PROBE_MS },
      refused: { c: NOW - 1 },
    })
    const after = new EmptyLanes()
    after.restore(
      {
        probed: { b: NOW - 60_000, c: NOW + 1, d: old },
        refused: { e: NOW - 5 },
      },
      NOW,
    )
    expect(after.saved(NOW)).toEqual({
      probed: { b: NOW - 60_000 },
      refused: { e: NOW - 5 },
    })
    // A file from before refusals were kept.
    const older = new EmptyLanes()
    older.restore({ probed: { b: NOW - 1 } }, NOW)
    expect(older.saved(NOW)).toEqual({ probed: { b: NOW - 1 }, refused: {} })
  })
})
