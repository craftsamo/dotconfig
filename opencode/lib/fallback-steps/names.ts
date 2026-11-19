import { OAUTH_PROVIDER } from "../subagent-fallback/lanes"

// How the subscription providers a step can run on are named in a reason.
export const LOGIN_NAMES: Readonly<Record<string, string>> = {
  [OAUTH_PROVIDER]: "Claude",
  openai: "ChatGPT",
  xai: "xAI",
}
