import type { ClaudeAccountsContext, RoutedRequest } from "./accounts"

// V2 structural API (see SUPPORTED_VERSIONS), like
// lib/subagent-fallback/runtime.ts: no SDK dependency.
export type Registration = { dispose(): Promise<void> }
export type RuntimeContext = ClaudeAccountsContext & {
  app: { version: string }
  options: Record<string, unknown>
  session: {
    hook(
      name: "http.request",
      callback: (event: RoutedRequest) => Promise<void>,
    ): Promise<Registration>
  }
}

// Releases whose http.request hook contract was checked against the upstream
// source. Same list as lib/subagent-fallback/runtime.ts; both move together
// until that directory is deleted.
export const SUPPORTED_VERSIONS: readonly string[] = ["2.1.2", "2.3.0"]
export const supported = (version: string) =>
  SUPPORTED_VERSIONS.includes(version)
