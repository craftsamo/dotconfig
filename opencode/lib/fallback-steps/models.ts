export type ModelRef = {
  id: string
  providerID: string
  variant?: string
}

export const OAUTH_PROVIDER = "anthropic"

/** The OAuth method the Claude login plugin registers. An API key never qualifies. */
export const CLAUDE_METHODS: readonly string[] = ["claude-max"]
