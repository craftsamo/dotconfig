/**
 * Runs one custom tool in a child process and prints `{ ok, out | error }` as
 * JSON. Tests use it for tools that call `gh`, so a fake `gh` on PATH stays
 * confined to that child instead of the whole test process.
 *
 * Input (env TOOL_INPUT): { module, name, args, cwd, gate? }. Only the named
 * module is imported: every tool call is one child, and its start-up time is
 * paid on each gh-backed test.
 *
 * `gate` shapes the permission context a GitHub write meets: absent, a
 * person's own session without a gate (nothing asserts); "record" offers a
 * gate that allows and records every assertion (reported as `asserted`);
 * "deny" offers one that refuses; "hermes" offers no gate but a session
 * bound to Hermes.
 */

const loaders: Record<string, () => Promise<Record<string, any>>> = {
  gh: () => import("../gh"),
  gh_issue: () => import("../gh_issue"),
  gh_project: () => import("../gh_project"),
  git: () => import("../git"),
}

const input = JSON.parse(process.env.TOOL_INPUT ?? "{}")
const asserted: unknown[] = []
const context: Record<string, unknown> = { worktree: input.cwd, oauthAccess: async () => undefined }
if (input.gate === "record") context.permission = { assert: async (request: unknown) => void asserted.push(request) }
if (input.gate === "deny") context.permission = { assert: async () => { throw new Error("permission denied by the session") } }
if (input.gate === "hermes") context.sessionMetadata = async () => ({ hermes: { owner: "x" } })
try {
  const spec = (await loaders[input.module]?.())?.[input.name]
  if (!spec) throw new Error(`unknown tool ${input.module}.${input.name}`)
  const out = await spec.execute(input.args ?? {}, context)
  process.stdout.write(JSON.stringify({ ok: true, out: JSON.parse(out), asserted }))
} catch (error) {
  process.stdout.write(JSON.stringify({ ok: false, error: (error as Error).message, asserted }))
}
