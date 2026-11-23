// lib/fallback-steps reads these from here.
export type ModelRef = {
  id: string
  providerID: string
  variant?: string
}

export const OAUTH_PROVIDER = "anthropic"

// The OAuth method the Claude login plugin registers. An API key never qualifies.
export const CLAUDE_METHODS: readonly string[] = ["claude-max"]

// The login suffix a model ID ends in; the longest one wins.
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
