import type { ClaudeAccountsContext, RoutedRequest } from "./accounts"

// V2 structural API (see SUPPORTED_VERSIONS), with no SDK dependency.
// lib/fallback-steps imports these types.
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
// source.
export const SUPPORTED_VERSIONS: readonly string[] = ["2.1.2", "2.3.0"]
export const supported = (version: string) =>
  SUPPORTED_VERSIONS.includes(version)
