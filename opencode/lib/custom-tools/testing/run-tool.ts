/**
 * Runs one custom tool in a child process and prints `{ ok, out | error }` as
 * JSON. Tests use it for tools that call `gh`, so a fake `gh` on PATH stays
 * confined to that child instead of the whole test process.
 *
 * Input (env TOOL_INPUT): { module, name, args, cwd }. Only the named module
 * is imported: every tool call is one child, and its start-up time is paid
 * on each gh-backed test.
 */

const loaders: Record<string, () => Promise<Record<string, any>>> = {
  gh: () => import("../gh"),
  gh_issue: () => import("../gh_issue"),
  gh_project: () => import("../gh_project"),
  git: () => import("../git"),
}

const input = JSON.parse(process.env.TOOL_INPUT ?? "{}")
try {
  const spec = (await loaders[input.module]?.())?.[input.name]
  if (!spec) throw new Error(`unknown tool ${input.module}.${input.name}`)
  const out = await spec.execute(input.args ?? {}, { worktree: input.cwd, oauthAccess: async () => undefined })
  process.stdout.write(JSON.stringify({ ok: true, out: JSON.parse(out) }))
} catch (error) {
  process.stdout.write(JSON.stringify({ ok: false, error: (error as Error).message }))
}
