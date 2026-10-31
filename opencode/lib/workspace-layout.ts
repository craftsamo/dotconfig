/**
 * The Workspaces layout (root and areas), read by the same rules as Hermes'
 * plugins/_shared/workspace_layout.py: ~/.config/workspaces/layout.json
 * ($XDG_CONFIG_HOME respected, WORKSPACES_LAYOUT names another file), the
 * public defaults without it, WORKSPACES_ROOT over either root. An unreadable
 * or invalid file throws: the root bounds what a tool may read, so it is never
 * guessed. Contract: hermes/docs/workspace-layout.md.
 */
import { lstatSync, readFileSync } from "fs"
import { homedir } from "os"
import { isAbsolute, join, normalize, resolve } from "path"

export type Area = { name: string; role: "projects" | "personal"; sensitive: boolean }
export type Layout = { root: string; areas: Area[]; source: string | null }

const ROLES = ["projects", "personal"]
const KEYS = ["root", "areas"]
const AREA_KEYS = ["name", "role", "sensitive"]
export const DEFAULT = {
  root: "~/Workspaces",
  areas: [
    { name: "Projects", role: "projects", sensitive: false },
    { name: "Personal", role: "personal", sensitive: true },
  ],
}

type Env = Record<string, string | undefined>

function expand(path: string, home: string): string {
  return path === "~" ? home : path.startsWith("~/") ? join(home, path.slice(2)) : path
}

export function configPath(env: Env = process.env, home = env.HOME || homedir()): string {
  if (env.WORKSPACES_LAYOUT) return expand(env.WORKSPACES_LAYOUT, home)
  const base = env.XDG_CONFIG_HOME ? expand(env.XDG_CONFIG_HOME, home) : join(home, ".config")
  return join(base, "workspaces", "layout.json")
}

function lexists(path: string): boolean {
  try {
    lstatSync(path)
    return true
  } catch {
    return false
  }
}

function parse(data: unknown, source: string | null, home: string): Layout {
  const fail = (message: string): never => {
    throw new Error(`${source ?? "defaults"}: ${message}`)
  }
  if (typeof data !== "object" || data === null || Array.isArray(data)) fail("the layout must be a JSON object")
  const obj = data as Record<string, unknown>
  const unknown = Object.keys(obj).filter((k) => !KEYS.includes(k)).sort()
  if (unknown.length) fail(`unknown key(s) ${unknown.join(", ")} (allowed: ${KEYS.join(", ")})`)
  const root = "root" in obj ? obj.root : DEFAULT.root
  if (typeof root !== "string" || !root.trim()) fail("root must be a non-empty path")
  const rootPath = normalize(expand(root as string, home))
  if (!isAbsolute(rootPath)) fail(`root must be absolute or start with ~: ${JSON.stringify(root)}`)
  const rawAreas = "areas" in obj ? obj.areas : DEFAULT.areas
  if (!Array.isArray(rawAreas) || rawAreas.length === 0) fail("areas must be a non-empty list")
  const areas: Area[] = []
  const seen = new Set<string>()
  ;(rawAreas as unknown[]).forEach((item, i) => {
    if (typeof item !== "object" || item === null || Array.isArray(item)) fail(`areas[${i}] must be an object`)
    const a = item as Record<string, unknown>
    const extra = Object.keys(a).filter((k) => !AREA_KEYS.includes(k)).sort()
    if (extra.length) fail(`areas[${i}]: unknown key(s) ${extra.join(", ")} (allowed: ${AREA_KEYS.join(", ")})`)
    const { name, role } = a
    const sensitive = "sensitive" in a ? a.sensitive : false
    if (typeof name !== "string" || !name || name.startsWith(".") || /[\/\\]/.test(name) || name !== name.trim()) {
      fail(`areas[${i}].name must be a plain folder name not starting with '.': ${JSON.stringify(name)}`)
    }
    const folded = (name as string).toLowerCase()
    if (seen.has(folded)) fail(`area ${JSON.stringify(name)} is listed twice`)
    seen.add(folded)
    if (typeof role !== "string" || !ROLES.includes(role)) fail(`areas[${i}].role must be one of ${ROLES.join(", ")}`)
    if (typeof sensitive !== "boolean") fail(`areas[${i}].sensitive must be true or false`)
    areas.push({ name: name as string, role: role as Area["role"], sensitive: sensitive as boolean })
  })
  if (areas.filter((a) => a.role === "projects").length !== 1) fail("exactly one area must have role projects")
  return { root: rootPath, areas, source }
}

/** The layout in force: the file if there is one (a dangling link counts as unreadable), else the defaults. */
export function loadLayout(env: Env = process.env, home = env.HOME || homedir()): Layout {
  const path = configPath(env, home)
  let layout: Layout
  if (lexists(path)) {
    let data: unknown
    try {
      data = JSON.parse(readFileSync(path, "utf8"))
    } catch (err) {
      throw new Error(`${path}: cannot read the layout (${(err as Error).message})`)
    }
    layout = parse(data, path, home)
  } else {
    layout = parse(DEFAULT, null, home)
  }
  if (env.WORKSPACES_ROOT) {
    // A relative override is taken from the working directory, as Hermes' scanners take it.
    layout = { ...layout, root: resolve(expand(env.WORKSPACES_ROOT, home)) }
  }
  return layout
}
