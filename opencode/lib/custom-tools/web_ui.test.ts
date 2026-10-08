import { afterAll, beforeAll, describe, expect, test } from "bun:test"
import { chmodSync, cpSync, existsSync, mkdirSync, mkdtempSync, readdirSync, realpathSync, rmSync, symlinkSync, writeFileSync } from "fs"
import { tmpdir } from "os"
import { join } from "path"
import { check, checkUrl, findNode, resolveBaseline, resolveOut, scratchRoot } from "./web_ui"

let root: string
let worktree: string
let job: string
let home: string

beforeAll(() => {
  root = realpathSync(mkdtempSync(join(tmpdir(), "web-ui-tool-")))
  worktree = join(root, "repo")
  home = join(root, "home")
  job = join(home, "Workspaces/Projects/G/.agent/20261008-job")
  mkdirSync(worktree, { recursive: true })
  mkdirSync(job, { recursive: true })
})

afterAll(() => rmSync(root, { recursive: true, force: true }))

const now = new Date("2026-10-08T12:00:00Z")
const STAMP = "2026-10-08T12-00-00-000Z"

describe("resolveOut", () => {
  test("uses the Hermes run's output directory when there is one", () => {
    expect(resolveOut({ hermesOutput: job, worktree, now })).toBe(join(job, "ui-check", STAMP))
  })

  test("falls back to OpenCode's scratch directory", () => {
    const out = resolveOut({ worktree, sessionID: "ses_1", now })
    expect(out).toBe(join(realpathSync.native(tmpdir()), "opencode", "ui-check", `ses_1-${STAMP}`))
    expect(scratchRoot()).toContain(join("opencode", "ui-check"))
  })

  test("refuses output directories outside a draft, inside the worktree or with wildcards", () => {
    const refused = [
      join(root, "elsewhere"),
      join(worktree, ".agent", "job"),
      join(worktree, "..x", ".agent", "job"),
      join(worktree.toUpperCase(), ".agent", "job"),
      join(home, "Workspaces/Projects/G"),
      "relative/.agent/job",
      join(job, "*"),
    ]
    for (const hermesOutput of refused) expect(() => resolveOut({ hermesOutput, worktree }), hermesOutput).toThrow()
  })

  test("judges symlinks by where they land and refuses dangling ones", () => {
    const link = join(home, "Workspaces/Projects/G/.agent/sneaky")
    symlinkSync(worktree, link)
    expect(() => resolveOut({ hermesOutput: link, worktree })).toThrow(/outside the worktree/)
    mkdirSync(join(root, "elsewhere-dir"))
    const escape = join(job, "escape")
    symlinkSync(join(root, "elsewhere-dir"), escape)
    expect(() => resolveOut({ hermesOutput: escape, worktree })).toThrow(/draft/)
    const dangling = join(job, "dangling")
    symlinkSync(join(worktree, "not-yet"), dangling)
    expect(() => resolveOut({ hermesOutput: dangling, worktree })).toThrow(/dangling/)
  })
})

describe("resolveBaseline", () => {
  test("accepts an existing directory under ~/Workspaces, with ~ expanded", () => {
    const baseline = join(home, "Workspaces/Projects/G/assets/ui-baseline/repo")
    mkdirSync(baseline, { recursive: true })
    expect(resolveBaseline("~/Workspaces/Projects/G/assets/ui-baseline/repo", home)).toBe(baseline)
  })

  test("refuses a missing, relative or outside directory", () => {
    expect(() => resolveBaseline(join(home, "Workspaces/none"), home)).toThrow(/no approved baseline yet/)
    expect(() => resolveBaseline("Workspaces/x", home)).toThrow(/absolute/)
    expect(() => resolveBaseline(root, home)).toThrow(/under ~\/Workspaces/)
  })
})

describe("checkUrl", () => {
  test("allows local and private-network development servers only", () => {
    for (const url of ["http://localhost:3000/", "http://127.0.0.1:5173/a", "http://app.localhost/", "http://192.168.1.5:8080/",
      "http://10.0.0.2/", "http://[::1]:3000/"]) {
      expect(() => checkUrl(url), url).not.toThrow()
    }
    for (const url of ["https://example.com/", "http://169.254.169.254/latest/meta-data/", "file:///etc/passwd", "nope"]) {
      expect(() => checkUrl(url), url).toThrow()
    }
  })
})

describe("findNode", () => {
  test("skips the ~/.config/bin secret shims", () => {
    const fakeHome = join(root, "node-home")
    const shims = join(fakeHome, ".config", "bin")
    const real = join(root, "real-bin")
    mkdirSync(shims, { recursive: true })
    mkdirSync(real, { recursive: true })
    for (const dir of [shims, real]) {
      writeFileSync(join(dir, "node"), "#!/bin/sh\n")
      chmodSync(join(dir, "node"), 0o755)
    }
    expect(findNode(`${shims}:${real}`, fakeHome)).toBe(join(real, "node"))
    expect(() => findNode(shims, fakeHome)).toThrow(/No node/)
  })
})

describe("check", () => {
  test("captures into the Hermes output directory and compares with a baseline", async () => {
    const server = Bun.serve({
      port: 0,
      fetch: () =>
        new Response(
          `<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width"><title>t</title>
          </head><body><main><h1>Hello</h1><a href="#x">link</a></main></body></html>`,
          { headers: { "content-type": "text/html" } },
        ),
    })
    const realHome = process.env.HOME
    const realBrowsers = process.env.PLAYWRIGHT_BROWSERS_PATH
    try {
      const context = {
        worktree,
        sessionID: "ses_test",
        oauthAccess: async () => undefined,
        sessionMetadata: async () => ({ hermes: { output_dir: job } }),
      }
      const page = { name: "home", url: `http://127.0.0.1:${server.port}/` }
      const first = await check.execute({ pages: [page], viewports: ["800x600"] }, context)
      expect(first).toContain("Capture: no mechanical failures")
      expect(first).toContain("the Hermes run's output directory")
      const [run] = readdirSync(join(job, "ui-check"))
      const baseline = join(home, "Workspaces/Projects/G/assets/ui-baseline/check")
      cpSync(join(job, "ui-check", run, "screens"), baseline, { recursive: true })

      // The baseline must lie under ~/Workspaces, so HOME points at the fixture; keep
      // Playwright's browsers where they were installed.
      process.env.PLAYWRIGHT_BROWSERS_PATH ??= join(realHome ?? "", "Library", "Caches", "ms-playwright")
      process.env.HOME = home
      const second = await check.execute({ pages: [page], viewports: ["800x600"], baseline }, context)
      expect(second).toContain("Compare: every pair compared")
      expect(second).toContain("home--800x600--light.png: changed 0.00%")
      const runs = readdirSync(join(job, "ui-check")).filter((name) => name !== run)
      expect(existsSync(join(job, "ui-check", runs[0], "compare", "home--800x600--light.png"))).toBe(true)

      await expect(check.execute({ pages: [{ name: "x", url: "https://example.com/" }] }, context)).rejects.toThrow(
        /local or private-network/,
      )
    } finally {
      process.env.HOME = realHome
      if (realBrowsers === undefined) delete process.env.PLAYWRIGHT_BROWSERS_PATH
      server.stop(true)
    }
  }, 120_000)
})
