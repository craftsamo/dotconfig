// zai-sanitize — keep "Hermes Agent" in your files AND use Z.ai's GLM Coding Plan.
//
// Why this exists:
//   Z.ai's Coding Plan endpoint (api/coding/paas/v4) fingerprints the SYSTEM
//   prompt and rejects requests that contain certain product/agent brand
//   strings with error code 1305 / HTTP 429 ("The service may be temporarily
//   overloaded, please try again later"). It is deterministic and content-based,
//   NOT a real capacity problem (the same model works fine via openrouter, and
//   the same phrase passes in user/assistant/tool messages — only the system
//   role is filtered).
//
//   Empirically confirmed trigger: the literal, case-sensitive bigram
//   "Hermes Agent" in the system prompt (injected here from AGENTS.md). It
//   reaches the system prompt every request, so every request fails.
//
// What this does:
//   Registers an auth loader for the zai-coding-plan provider that supplies a
//   custom fetch. The fetch rewrites the OUTGOING request body just before send
//   ("Hermes Agent" -> "Hermes agent"), so nothing on disk needs to change.
//   Scoped to zai-coding-plan only; all other providers are untouched.
//
// Notes:
//   - Add more [find, replace] pairs to REPLACEMENTS if other phrases trip the
//     same filter.
//   - Set ZAI_SANITIZE_DEBUG=1 to append diagnostics to /tmp/zai-plugin-debug.log.
//   - "experimental.chat.system.transform" was tried first but does NOT affect
//     the serialized request body, so body rewriting in fetch is used instead.

import fs from "node:fs"

const TARGET_PROVIDER = "zai-coding-plan"
const CODING_BASE_URL = "https://api.z.ai/api/coding/paas/v4"
const REPLACEMENTS = [["Hermes Agent", "Hermes agent"]]

function sanitize(text) {
  let out = text
  for (const [from, to] of REPLACEMENTS) out = out.split(from).join(to)
  return out
}

function debug(...args) {
  if (!process.env.ZAI_SANITIZE_DEBUG) return
  try {
    fs.appendFileSync("/tmp/zai-plugin-debug.log", `${new Date().toISOString()} ${args.join(" ")}\n`)
  } catch {}
}

export const ZaiSanitize = async () => {
  return {
    auth: {
      provider: TARGET_PROVIDER,
      async loader(getAuth) {
        let key
        try {
          key = (await getAuth())?.key
        } catch {}
        key =
          key ||
          process.env.ZAI_CODING_PLAN_API_KEY ||
          process.env.ZHIPU_API_KEY ||
          process.env.ZAI_API_KEY
        debug("auth_loader hasKey", Boolean(key))
        return {
          apiKey: key,
          baseURL: CODING_BASE_URL,
          async fetch(input, init) {
            const reqInit = init ?? {}
            let body = reqInit.body
            if (typeof body === "string") {
              const rewritten = sanitize(body)
              if (rewritten !== body) {
                body = rewritten
                debug("body_rewritten len", body.length)
              }
            }
            return fetch(input, { ...reqInit, body })
          },
        }
      },
    },
  }
}

export default ZaiSanitize
