import { OAUTH_PROVIDER } from "./models"

// The plugin's options in opencode.jsonc, read once at setup.
export type StepsOptions = {
  // Console credit lanes in spending order. Empty turns them off.
  creditLanes: string[]
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
  }
}
