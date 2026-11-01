import type { AccountsContext } from "./accounts"
import type { ClaudeAccountsContext } from "./claude-accounts"
import type { CatalogModel, ModelRef } from "./policy"

// V2 structural API (see SUPPORTED_VERSIONS), like plugins/custom-tools.ts:
// no SDK dependency.
export type Registration = { dispose(): Promise<void> }
export type Session = {
  id: string
  parentID?: string
  agent?: string
  model?: ModelRef
  metadata?: Record<string, unknown>
  location: { directory: string }
}
export type Kind = "primary" | "title" | "compaction" | "generate"
export type Scope = { sessionID: string; model: ModelRef; kind: Kind }
export type ContextEvent = {
  sessionID: string
  model: ModelRef
  system: unknown[]
  messages: unknown[]
  tools?: unknown
  options: unknown
}
export type Hooks = {
  context: ContextEvent
  compaction: ContextEvent
  generate: ContextEvent
  "http.request": Scope & { request: Request }
  "experimental.ws.handshake": Scope & {
    url: string
    headers: Record<string, string>
  }
  "experimental.ws.send": Scope & { frame: string }
  retry: {
    sessionID: string
    agent?: string
    model: ModelRef
    attempt?: number
    error: {
      type: string
      status?: number
      message: string
      response?: { body?: string }
    }
    decision: { retry: false } | { retry: true; delay: number }
  }
}
export type ToolContext = {
  sessionID: string
  id: string
  signal: AbortSignal
  progress(update: Record<string, unknown>): Promise<void>
}
export type Result = {
  output?: unknown
  content?: string | readonly unknown[]
  metadata?: Record<string, unknown>
}
export type Executor = (
  input: Record<string, unknown>,
  context: ToolContext,
) => Promise<Result>
// The Claude login router reads less of a session than this plugin does;
// its narrower `session.get` would win the intersection.
type LoginContext = AccountsContext & Omit<ClaudeAccountsContext, "session">
export type RuntimeContext = LoginContext & {
  app: { version: string }
  options: Record<string, unknown>
  agent: {
    get(input: {
      agentID: string
      location: { directory: string }
    }): Promise<{ data: { model?: ModelRef } }>
  }
  model: {
    list(input: {
      location: { directory: string }
    }): Promise<{ data: CatalogModel[] }>
  }
  session: {
    get(input: { sessionID: string }): Promise<Session>
    update(input: {
      sessionID: string
      metadata: Record<string, unknown>
    }): Promise<unknown>
    switchModel(input: { sessionID: string; model: ModelRef }): Promise<void>
    hook<N extends keyof Hooks>(
      name: N,
      callback: (event: Hooks[N]) => Promise<void>,
    ): Promise<Registration>
  }
  tool: {
    transform(
      callback: (editor: {
        get(id: string): unknown
        update(
          id: string,
          callback: (tool: { execute: Executor }) => void,
        ): void
      }) => void,
    ): Promise<Registration>
  }
}

// Releases whose hook and subagent-tool contracts were checked against the
// upstream source. Add a release only after re-checking them.
export const SUPPORTED_VERSIONS: readonly string[] = ["2.1.2"]
export const supported = (version: string) =>
  SUPPORTED_VERSIONS.includes(version)
