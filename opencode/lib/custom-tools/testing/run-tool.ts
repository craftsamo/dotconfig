/**
 * Runs one custom tool in a child process and prints `{ ok, out | error }` as
 * JSON. Tests use it for tools that call `gh`, so a fake `gh` on PATH stays
 * confined to that child instead of the whole test process.
 *
 * Input (env TOOL_INPUT): { module, name, args, cwd }.
 */
import * as git from "../git"

const modules: Record<string, Record<string, any>> = { git }

const input = JSON.parse(process.env.TOOL_INPUT ?? "{}")
const spec = modules[input.module]?.[input.name]
try {
  if (!spec) throw new Error(`unknown tool ${input.module}.${input.name}`)
  const out = await spec.execute(input.args ?? {}, { worktree: input.cwd, oauthAccess: async () => undefined })
  process.stdout.write(JSON.stringify({ ok: true, out: JSON.parse(out) }))
} catch (error) {
  process.stdout.write(JSON.stringify({ ok: false, error: (error as Error).message }))
}
