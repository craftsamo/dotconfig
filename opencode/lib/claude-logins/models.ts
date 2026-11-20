// Copies of what lib/subagent-fallback (lanes.ts, policy.ts) holds, so this
// plugin outlives it; keep them equal until that directory is deleted.
export type ModelRef = {
  id: string
  providerID: string
  variant?: string
}

// Mirrors OAUTH_PROVIDER in lib/subagent-fallback/lanes.ts.
export const OAUTH_PROVIDER = "anthropic"

// Mirrors METHODS.anthropic in lib/subagent-fallback/policy.ts: the OAuth
// method the Claude login plugin registers. An API key never qualifies.
export const CLAUDE_METHODS: readonly string[] = ["claude-max"]

// The login suffix a model ID ends in; the longest one wins. Mirrors
// longestSuffix in lib/subagent-fallback/lanes.ts.
export function longestSuffix(
  id: string,
  suffixes: readonly string[],
): string | undefined {
  let found: string | undefined
  for (const suffix of suffixes)
    if (
      id.length > suffix.length + 1 &&
      id.endsWith(`-${suffix}`) &&
      (found === undefined || suffix.length > found.length)
    )
      found = suffix
  return found
}
