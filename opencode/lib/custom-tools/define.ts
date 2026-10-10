import { z } from "zod"

/**
 * Runtime-neutral tool definition shared by the OpenCode V1 and V2 adapters in
 * ../../plugins/custom-tools.ts. Tool modules stay free of @opencode-ai/plugin
 * and @opencode/plugin so the same code runs under both plugin APIs.
 *
 * `tool()` is an identity helper with the same shape as V1's
 * `@opencode-ai/plugin` helper, and `tool.schema` is Zod v4, which V1 and
 * V2 (Standard Schema) both accept.
 */

export type OAuthAccess = { access: string; expires?: number }

export type ToolContext = {
  /** Git worktree root of the calling session (falls back to its directory). */
  worktree: string
  /**
   * Reads the stored OAuth access token of an OpenCode provider integration
   * (V1: auth.json, V2: the integration credential store). Never log the value.
   */
  oauthAccess(integrationID: string): Promise<OAuthAccess | undefined>
  /** The calling session's id, when the runtime provides one. */
  sessionID?: string
  /** Aborts when the session stops the call (V2 `signal`, V1 `abort`). */
  signal?: AbortSignal
  /** The calling session's metadata (V2 only; Hermes keeps its binding under `hermes`). */
  sessionMetadata?(): Promise<Record<string, unknown> | undefined>
  /** OpenCode's worktree operations for the calling session's project (V2 only). */
  worktrees?: {
    create(input: { name?: string; branch?: string }): Promise<{ directory: string }>
    remove(input: { directory: string; force: boolean }): Promise<void>
    list(): Promise<{ directory: string; strategy?: string }[]>
  }
}

export type ToolSpec<Args extends z.ZodRawShape = z.ZodRawShape> = {
  description: string
  args: Args
  execute(args: z.infer<z.ZodObject<Args>>, context: ToolContext): Promise<string>
}

export function tool<Args extends z.ZodRawShape>(input: ToolSpec<Args>): ToolSpec<Args> {
  return input
}
tool.schema = z

export function isToolSpec(value: unknown): value is ToolSpec {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as ToolSpec).description === "string" &&
    typeof (value as ToolSpec).args === "object" &&
    typeof (value as ToolSpec).execute === "function"
  )
}
