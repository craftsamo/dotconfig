import { OAUTH_PROVIDER } from "../claude-logins/models"

// The plugin's options in opencode.jsonc, read once at setup.
export type StepsOptions = {
  // Console credit lanes in spending order. Empty turns them off.
  creditLanes: string[]
  // Parsed by AccountRouter.fromOption, which keeps a malformed one.
  claudeAccounts: unknown
}

export function readOptions(
  options: Record<string, unknown>,
): StepsOptions {
  return {
    creditLanes: Array.isArray(options.creditLanes)
      ? options.creditLanes.filter(
          (id): id is string =>
            typeof id === "string" && id !== "" && id !== OAUTH_PROVIDER,
        )
      : [],
    claudeAccounts: options.claudeAccounts,
  }
}
