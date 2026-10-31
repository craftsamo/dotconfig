import { afterAll, beforeAll, describe, expect, test } from "bun:test"
import { spawnSync } from "child_process"
import { mkdirSync, mkdtempSync, realpathSync, rmSync, symlinkSync, writeFileSync } from "fs"
import { tmpdir } from "os"
import { join, resolve } from "path"
import { DEFAULT, configPath, loadLayout } from "./workspace-layout"

const PYTHON_READER = resolve(import.meta.dir, "../../hermes/plugins/_shared/workspace_layout.py")
let root: string

beforeAll(() => {
  root = realpathSync(mkdtempSync(join(tmpdir(), "workspace-layout-")))
})
afterAll(() => rmSync(root, { recursive: true, force: true }))

let n = 0
function home(layout?: unknown): string {
  const h = join(root, `home-${n++}`)
  mkdirSync(join(h, ".config", "workspaces"), { recursive: true })
  if (layout !== undefined) {
    writeFileSync(join(h, ".config", "workspaces", "layout.json"), typeof layout === "string" ? layout : JSON.stringify(layout))
  }
  return h
}

describe("loadLayout", () => {
  test("without a file the public defaults apply", () => {
    const h = home()
    const layout = loadLayout({ HOME: h }, h)
    expect(layout.root).toBe(join(h, "Workspaces"))
    expect(layout.areas.map((a) => a.name)).toEqual(["Projects", "Personal"])
    expect(layout.source).toBeNull()
  })

  test("a file sets the root and areas; WORKSPACES_ROOT overrides the root", () => {
    const h = home({ root: "~/Work", areas: [{ name: "Clients", role: "projects" }] })
    expect(loadLayout({ HOME: h }, h)).toEqual({
      root: join(h, "Work"),
      areas: [{ name: "Clients", role: "projects", sensitive: false }],
      source: join(h, ".config", "workspaces", "layout.json"),
    })
    expect(loadLayout({ HOME: h, WORKSPACES_ROOT: "/srv/ws" }, h).root).toBe("/srv/ws")
  })

  test("XDG_CONFIG_HOME and WORKSPACES_LAYOUT name the file", () => {
    const h = home()
    const xdg = join(h, "xdg")
    mkdirSync(join(xdg, "workspaces"), { recursive: true })
    writeFileSync(join(xdg, "workspaces", "layout.json"), JSON.stringify({ root: "/x" }))
    expect(loadLayout({ HOME: h, XDG_CONFIG_HOME: xdg }, h).root).toBe("/x")
    writeFileSync(join(h, "other.json"), JSON.stringify({ root: "/y" }))
    expect(configPath({ HOME: h, WORKSPACES_LAYOUT: join(h, "other.json") }, h)).toBe(join(h, "other.json"))
    expect(loadLayout({ HOME: h, WORKSPACES_LAYOUT: join(h, "other.json") }, h).root).toBe("/y")
  })

  test.each([
    ["{not json", /cannot read/],
    [{ root: "relative" }, /absolute/],
    [{ areas: [] }, /non-empty list/],
    [{ areas: [{ name: "A", role: "personal" }] }, /exactly one area/],
    [{ areas: [{ name: "A", role: "projects" }, { name: "a", role: "personal" }] }, /listed twice/],
    [{ areas: [{ name: ".x", role: "projects" }] }, /plain folder name/],
    [{ areas: [{ name: "A", role: "work" }] }, /role must be/],
    [{ areas: [{ name: "A", role: "projects", sensitive: "yes" }] }, /true or false/],
    [{ rooot: "/x" }, /unknown key/],
  ])("an invalid file is refused: %p", (layout, message) => {
    const h = home(layout)
    expect(() => loadLayout({ HOME: h }, h)).toThrow(message)
  })

  test("a layout link to a missing file is refused, not ignored", () => {
    const h = home()
    symlinkSync(join(h, "gone.json"), join(h, ".config", "workspaces", "layout.json"))
    expect(() => loadLayout({ HOME: h }, h)).toThrow(/cannot read/)
  })
})

describe("parity with Hermes' reader", () => {
  const python = spawnSync("python3", ["--version"]).status === 0
  const cases: unknown[] = [
    undefined,
    { root: "~/Work" },
    { areas: [{ name: "Clients", role: "projects" }, { name: "Home", role: "personal", sensitive: true }] },
    DEFAULT,
  ]
  test.skipIf(!python).each(cases.map((c, i) => [i, c]))("case %i resolves the same root and areas", (_i, layout) => {
    const h = home(layout)
    const env = { HOME: h, PATH: process.env.PATH ?? "/usr/bin:/bin" }
    const out = spawnSync("python3", [PYTHON_READER], { env, encoding: "utf8" })
    expect(out.status).toBe(0)
    const py = JSON.parse(out.stdout)
    const ts = loadLayout({ HOME: h }, h)
    expect(ts.root).toBe(py.root)
    expect(ts.areas).toEqual(py.areas)
  })
})
