import { afterAll, describe, expect, test } from "bun:test"
import { execFileSync } from "node:child_process"
import { mkdirSync, mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { expandHome, hermesDatabases, hermesSince, readHermes } from "./hermes"

const root = mkdtempSync(join(tmpdir(), "credit-lanes-hermes-"))
afterAll(() => rmSync(root, { recursive: true, force: true }))

const SCHEMA = `CREATE TABLE session_model_usage (
  session_id TEXT NOT NULL, model TEXT NOT NULL,
  billing_provider TEXT NOT NULL DEFAULT '', billing_base_url TEXT NOT NULL DEFAULT '',
  billing_mode TEXT NOT NULL DEFAULT '', task TEXT NOT NULL DEFAULT '',
  estimated_cost_usd REAL NOT NULL DEFAULT 0, actual_cost_usd REAL NOT NULL DEFAULT 0);`

const db = (path: string, sql: string) => {
  mkdirSync(join(path, ".."), { recursive: true })
  execFileSync("sqlite3", [path, sql])
}

db(
  join(root, "state.db"),
  `${SCHEMA} INSERT INTO session_model_usage VALUES
    ('s1', 'claude-opus-5-5', 'anthropic', '', '', '', 1.5, 0),
    ('s2', 'claude-opus-5-5', 'anthropic-oauth', '', '', '', 9, 0);`,
)
db(
  join(root, "profiles", "writer", "state.db"),
  `${SCHEMA} INSERT INTO session_model_usage VALUES
    ('s1', 'claude-sonnet-5-5', 'anthropic', '', '', '', 2, 3),
    ('s1', 'claude-sonnet-5-5', 'anthropic', '', '', 'vision', 0.25, 0);`,
)
// A profile that has never run.
db(join(root, "profiles", "fresh", "state.db"), "CREATE TABLE other (x);")

describe("readHermes", () => {
  test("reads every profile's Console lane rows, the actual cost when known", async () => {
    expect(hermesDatabases(root).map((d) => d.name)).toEqual([
      "default",
      "fresh",
      "writer",
    ])
    expect(await readHermes(root)).toEqual({
      "default\ts1\tclaude-opus-5-5\t\t\t": 1.5,
      "writer\ts1\tclaude-sonnet-5-5\t\t\t": 3,
      "writer\ts1\tclaude-sonnet-5-5\t\t\tvision": 0.25,
    })
  })
  test("a missing root has no usage", async () => {
    expect(await readHermes(join(root, "nope"))).toEqual({})
  })
  test("an unreadable database fails the whole read", async () => {
    const broken = mkdtempSync(join(tmpdir(), "credit-lanes-broken-"))
    db(join(broken, "state.db"), "CREATE TABLE session_model_usage (x);")
    await expect(readHermes(broken)).rejects.toBeDefined()
    rmSync(broken, { recursive: true, force: true })
  })
})

describe("hermesSince", () => {
  test("sums each row's growth; a new row counts whole, a shrunk or gone one not at all", () => {
    expect(hermesSince({ a: 5, b: 2, c: 1 }, { a: 3, c: 4, d: 9 })).toBe(4)
  })
})

describe("expandHome", () => {
  test("expands a leading ~ only", () => {
    expect(expandHome("~/.hermes", "/home/x")).toBe("/home/x/.hermes")
    expect(expandHome("/a/~/b", "/home/x")).toBe("/a/~/b")
  })
})
