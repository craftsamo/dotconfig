import { DEFAULT_COOLDOWN_MS, OAUTH_PROVIDER } from "./lanes"
import { exportPath } from "./quota"

// The plugin's options in opencode.jsonc, read once at setup.
export type PreflightOptions = {
  // New launches are selected; false keeps the guards of launched children.
  enabled: boolean
  quotaExportPath: string
  // Console credit lanes in spending order. Empty turns them off.
  creditLanes: string[]
  creditCooldownMs: number
  creditsLastResort: boolean
  primaryFallback: boolean
  pinModels: boolean
  // Parsed by AccountRouter.fromOption, which keeps a malformed one.
  claudeAccounts: unknown
}

export function readOptions(
  options: Record<string, unknown>,
): PreflightOptions {
  return {
    enabled: options.enabled === true,
    quotaExportPath:
      typeof options.quotaExportPath === "string"
        ? options.quotaExportPath
        : exportPath(),
    creditLanes: Array.isArray(options.creditLanes)
      ? options.creditLanes.filter(
          (id): id is string =>
            typeof id === "string" && id !== "" && id !== OAUTH_PROVIDER,
        )
      : [],
    creditCooldownMs:
      typeof options.creditCooldownMs === "number" &&
      options.creditCooldownMs > 0
        ? options.creditCooldownMs
        : DEFAULT_COOLDOWN_MS,
    creditsLastResort: options.creditsLastResort === true,
    primaryFallback: options.primaryFallback !== false,
    pinModels: options.pinModels === true,
    claudeAccounts: options.claudeAccounts,
  }
}
