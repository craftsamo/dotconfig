import { rmSync } from "fs"
import { tmpdir } from "os"
import { join } from "path"

/**
 * Child-process helpers shared by the custom tools.
 *
 * Programs run through Bun.spawn with an explicit environment rather than
 * Bun.$: Bun.$ looks programs up on the PATH the process started with, while
 * Bun.spawn honors the PATH it is given. That lets a caller pass a reduced
 * environment, and lets tests put fakes on PATH.
 */

export type ExecOptions = {
  cwd?: string
  /** Full environment for the child. Defaults to the current process.env. */
  env?: Record<string, string | undefined>
  /** Text written to the child's stdin; otherwise stdin is closed. */
  stdin?: string
}

export type ExecResult = { ok: boolean; code: number; stdout: string; stderr: string }

export async function exec(argv: string[], options: ExecOptions = {}): Promise<ExecResult> {
  const child = Bun.spawn(argv, {
    cwd: options.cwd,
    env: options.env ?? process.env,
    stdin: options.stdin === undefined ? "ignore" : new Blob([options.stdin]),
    stdout: "pipe",
    stderr: "pipe",
  })
  const [stdout, stderr, code] = await Promise.all([
    new Response(child.stdout).text(),
    new Response(child.stderr).text(),
    child.exited,
  ])
  return { ok: code === 0, code, stdout, stderr }
}

/** Runs a program and returns its stdout; a non-zero exit throws with stderr (or stdout). */
export async function run(argv: string[], options: ExecOptions = {}): Promise<string> {
  const res = await exec(argv, options)
  if (!res.ok) {
    const err = res.stderr.trim() || res.stdout.trim()
    throw new Error(`${argv.join(" ")} failed (exit ${res.code}):\n${err}`)
  }
  return res.stdout
}

export const runGit = (argv: string[], cwd?: string) => run(["git", ...argv], { cwd })

export async function tryGit(argv: string[], cwd?: string): Promise<{ ok: boolean; stdout: string; code: number }> {
  const { ok, stdout, code } = await exec(["git", ...argv], { cwd })
  return { ok, stdout, code }
}

export const runGh = (argv: string[], cwd?: string) => run(["gh", ...argv], { cwd })

/** `gh` output parsed as JSON; empty output is null. */
export async function runGhJson(argv: string[], cwd?: string): Promise<any> {
  const out = (await runGh(argv, cwd)).trim()
  return out ? JSON.parse(out) : null
}

/** Whether a program is on PATH. */
export const which = (name: string) => Bun.which(name, { PATH: process.env.PATH }) !== null

/** Writes `content` to a fresh file under TMPDIR, hands its path to `fn`, and removes it afterwards. */
export async function withTempFile<T>(prefix: string, extension: string, content: string, fn: (path: string) => Promise<T>): Promise<T> {
  const path = join(process.env.TMPDIR ?? tmpdir(), `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}${extension}`)
  await Bun.write(path, content)
  try {
    return await fn(path)
  } finally {
    rmSync(path, { force: true })
  }
}

export const json = (value: unknown) => JSON.stringify(value, null, 2)
