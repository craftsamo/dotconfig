import { existsSync, lstatSync, mkdirSync, realpathSync } from "fs"
import { homedir, tmpdir } from "os"
import { delimiter, dirname, isAbsolute, join, relative, resolve, sep } from "path"
import { tool, type ToolContext } from "./define"

/**
 * Rendered web UI checks.
 *
 * `check` drives ../web-ui-check/web-ui-check.mjs in a Node child process
 * (Playwright is not reliable inside the Bun plugin host): it loads the given
 * pages per viewport and color scheme, measures what a machine can (horizontal
 * overflow, axe WCAG violations, focus visibility, console and page errors,
 * broken images), takes full-page screenshots and, with a baseline directory,
 * writes one baseline | current | diff image per page. It never judges how a
 * page looks.
 *
 * Safety: the tool runs without OpenCode's permission rules, so it decides
 * everything itself: it writes only into the Hermes run's output directory (a
 * `.agent/<job>` draft) or OpenCode's temporary directory, never the worktree;
 * it reads a baseline only from under ~/Workspaces; it loads only local or
 * private-network pages; and the Node child gets a minimal environment, never
 * the service's secrets.
 */

const SCRIPT = join(import.meta.dir, "..", "web-ui-check", "web-ui-check.mjs")
const TIMEOUT_MS = 10 * 60 * 1000
const KILL_GRACE_MS = 10 * 1000
const ENV_NAMES = ["PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "PLAYWRIGHT_BROWSERS_PATH"]

/** The directory under the OS temporary directory that OpenCode already uses as scratch. */
export function scratchRoot(): string {
  return join(tmpdir(), "opencode", "ui-check")
}

function real(path: string): string {
  // Resolve symlinks through the nearest existing ancestor, so a path that does
  // not exist yet is judged by where it would actually land. A dangling symlink
  // on the way is refused: mkdir would follow it somewhere unchecked.
  let current = resolve(path)
  const rest: string[] = []
  while (!existsSync(current)) {
    let dangling = false
    try {
      dangling = lstatSync(current).isSymbolicLink()
    } catch {}
    if (dangling) throw new Error(`Refusing a dangling symlink: ${current}`)
    const parent = dirname(current)
    if (parent === current) break
    rest.unshift(current.slice(parent.length + 1))
    current = parent
  }
  return join(realpathSync.native(current), ...rest)
}

function inside(child: string, parent: string): boolean {
  const rel = relative(parent.toLowerCase(), child.toLowerCase())
  return rel === "" || (rel !== ".." && !rel.startsWith(".." + sep) && !isAbsolute(rel))
}

/**
 * The output directory for one check: under the Hermes run's output directory
 * (`<dir>/ui-check/<timestamp>`) when the session has one, else a fresh scratch
 * directory. Throws unless it lands inside a `.agent/<job>` draft or the scratch
 * root, outside the worktree (compared case-insensitively, as macOS volumes are).
 */
export function resolveOut(input: { hermesOutput?: string; worktree: string; sessionID?: string; now?: Date }): string {
  const stamp = (input.now ?? new Date()).toISOString().replace(/[:.]/g, "-")
  const chosen = input.hermesOutput
    ? join(input.hermesOutput, "ui-check", stamp)
    : join(scratchRoot(), `${input.sessionID ?? "session"}-${stamp}`)
  if (!isAbsolute(chosen) || /[*?]/.test(chosen)) {
    throw new Error(`The run's output directory must be an absolute path without wildcards: ${chosen}`)
  }
  const target = real(chosen)
  if (inside(target, real(input.worktree))) {
    throw new Error(`The output directory must lie outside the worktree: ${target}`)
  }
  const parts = target.split(sep)
  const draft = parts.indexOf(".agent")
  const inDraft = draft > 0 && draft < parts.length - 2
  if (!inDraft && !inside(target, real(scratchRoot()))) {
    throw new Error(`The output directory must lie inside a .agent/<job> draft or ${scratchRoot()}: ${target}`)
  }
  return target
}

/** The baseline directory: an existing directory under ~/Workspaces, read only. */
export function resolveBaseline(value: string, home = process.env.HOME || homedir()): string {
  const expanded = value.startsWith("~/") ? join(home, value.slice(2)) : value
  if (!isAbsolute(expanded)) throw new Error("baseline must be an absolute path (or start with ~/)")
  if (!existsSync(expanded)) throw new Error(`baseline directory does not exist: ${expanded} (no approved baseline yet)`)
  const target = real(expanded)
  if (!inside(target, real(join(home, "Workspaces")))) {
    throw new Error(`baseline must lie under ~/Workspaces: ${target}`)
  }
  return target
}

const LOCAL_HOSTS = /^(localhost|.*\.localhost|.*\.local|127(\.\d+){3}|10(\.\d+){3}|192\.168(\.\d+){2}|172\.(1[6-9]|2\d|3[01])(\.\d+){2}|\[::1\])$/i

/** Only pages a local or private-network development server serves. */
export function checkUrl(value: string): string {
  let url: URL
  try {
    url = new URL(value)
  } catch {
    throw new Error(`Not a URL: ${value}`)
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") throw new Error(`Only http(s) pages: ${value}`)
  if (!LOCAL_HOSTS.test(url.hostname)) {
    throw new Error(`Only local or private-network pages (a running development build): ${value}`)
  }
  return url.toString()
}

/** A Node binary that is not one of the ~/.config/bin secret shims. */
export function findNode(path = process.env.PATH ?? "", home = process.env.HOME ?? ""): string {
  const shims = home ? resolve(home, ".config", "bin") : ""
  const entries = path.split(delimiter).filter((entry) => entry && resolve(entry) !== shims)
  const found = Bun.which("node", { PATH: entries.join(delimiter) })
  if (!found) throw new Error("No node binary on PATH outside the secret shims")
  return found
}

async function run(node: string, argv: string[]): Promise<{ code: number; out: string }> {
  const env: Record<string, string> = {}
  for (const name of ENV_NAMES) if (process.env[name]) env[name] = process.env[name] as string
  const child = Bun.spawn([node, SCRIPT, ...argv], { stdout: "pipe", stderr: "pipe", env })
  let timedOut = false
  const term = setTimeout(() => {
    timedOut = true
    child.kill("SIGTERM")
  }, TIMEOUT_MS)
  const hard = setTimeout(() => child.kill("SIGKILL"), TIMEOUT_MS + KILL_GRACE_MS)
  try {
    const [stdout, stderr] = await Promise.all([new Response(child.stdout).text(), new Response(child.stderr).text()])
    const code = await child.exited
    const out = (stdout + stderr).trim()
    return timedOut ? { code: 2, out: `${out}\nTimed out after ${TIMEOUT_MS / 60000} minutes`.trim() } : { code, out }
  } finally {
    clearTimeout(term)
    clearTimeout(hard)
  }
}

const CAPTURE_EXIT: Record<number, string> = {
  0: "no mechanical failures",
  1: "mechanical failures found",
  2: "the check could not run (not a pass)",
}
const COMPARE_EXIT: Record<number, string> = {
  0: "every pair compared",
  1: "some pairs could not be compared",
  2: "comparison could not run (a missing baseline means none is approved yet)",
}

export const check = tool({
  description:
    "Check a running web UI after a change that alters what pages render. Loads each page per viewport " +
    "(default 1440x900 and 375x812) and color scheme, reports horizontal overflow, axe WCAG violations, " +
    "focus stops without a visible indicator, console and page errors and broken images, and saves " +
    "full-page screenshots. With `baseline` (a directory of approved screenshots), it also writes one " +
    "baseline | current | diff image per page. Measures only; it never judges the look. Results go to " +
    "the Hermes run's output directory when there is one, else a scratch directory; read the summary, " +
    "and open a screenshot only to locate a failure.",
  args: {
    pages: tool.schema
      .array(
        tool.schema.object({
          name: tool.schema.string().describe("Short page name used in file names, e.g. home"),
          url: tool.schema.string().describe("Local http(s) URL served by this worktree's running build"),
        }),
      )
      .min(1)
      .describe("Pages the change affects"),
    viewports: tool.schema
      .array(tool.schema.string().regex(/^\d{2,5}x\d{2,5}$/))
      .optional()
      .describe("WIDTHxHEIGHT list; defaults to 1440x900 and 375x812, or the project's own breakpoints"),
    scheme: tool.schema.enum(["light", "dark", "both"]).optional().describe("Color scheme(s); default light"),
    wait_for: tool.schema.string().optional().describe("CSS selector to wait for on client-rendered pages"),
    ignore_console: tool.schema.string().optional().describe("Regex of a known third-party console error to ignore"),
    baseline: tool.schema
      .string()
      .optional()
      .describe("Directory of approved screenshots under ~/Workspaces to compare against (read only)"),
  },
  async execute(args, context: ToolContext) {
    const pages = args.pages.map((page) => ({ name: page.name, url: checkUrl(page.url) }))
    const baseline = args.baseline ? resolveBaseline(args.baseline) : undefined
    const hermes = (await context.sessionMetadata?.())?.hermes as { output_dir?: unknown } | undefined
    const hermesOutput = typeof hermes?.output_dir === "string" ? hermes.output_dir : undefined
    const out = resolveOut({ hermesOutput, worktree: context.worktree, sessionID: context.sessionID })
    mkdirSync(out, { recursive: true })
    if (real(out) !== out) throw new Error(`The output directory moved while it was created: ${out}`)
    const node = findNode()

    const capture = ["capture", "--out", out]
    for (const page of pages) capture.push("--page", `${page.name}=${page.url}`)
    for (const viewport of args.viewports ?? []) capture.push("--viewport", viewport)
    if (args.scheme) capture.push("--scheme", args.scheme)
    if (args.wait_for) capture.push("--wait-for", args.wait_for)
    if (args.ignore_console) capture.push("--ignore-console", args.ignore_console)
    const captured = await run(node, capture)
    const where = hermesOutput ? "the Hermes run's output directory" : "OpenCode's scratch directory (no Hermes output directory)"
    const lines = [`Output: ${out} (${where})`, `Capture: ${CAPTURE_EXIT[captured.code] ?? `exit ${captured.code}`}`,
      captured.out]

    if (baseline && captured.code !== 2) {
      const compareOut = join(out, "compare")
      const compared = await run(node, ["compare", "--baseline", baseline, "--current", join(out, "screens"),
        "--out", compareOut])
      lines.push("", `Compare: ${COMPARE_EXIT[compared.code] ?? `exit ${compared.code}`}`, compared.out)
      if (compared.code !== 2) lines.push(`Comparison images: ${compareOut}`)
    }
    lines.push("", `Screenshots: ${join(out, "screens")}`, `Report: ${join(out, "report.json")}`)
    return lines.join("\n")
  },
})
