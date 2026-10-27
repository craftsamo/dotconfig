import type { ToolContext } from "../define"

/**
 * The gate every GitHub write passes before it runs. Custom tools call `gh`
 * in a child process, so the shell permission rules never see them; this is
 * where a session's ruleset gets its say.
 *
 * `action` is the tool id (`gh_issue_update`), so a ruleset keyed on tool
 * names decides it; `resources` are the GitHub targets (`owner/repo#N`,
 * `owner/N` for a board); `metadata` says what the write will change, so a
 * driver that answers requests for the session (Hermes) can judge it without
 * re-reading the arguments.
 *
 * A session driven by Hermes carries its binding under `metadata.hermes`.
 * On a runtime without the gate (V1) such a session gets no write at all:
 * the driver would never see the request.
 */
export async function assertWrite(context: ToolContext, action: string, resources: string[], metadata: Record<string, unknown>, message?: string): Promise<void> {
  if (context.permission) {
    await context.permission.assert({ action, resources, metadata, message })
    return
  }
  const meta = await context.sessionMetadata?.()
  if (meta && typeof meta === "object" && "hermes" in meta) {
    throw new Error(`${action}: this session is driven by Hermes and this runtime offers no permission gate for a GitHub write; refused.`)
  }
}
