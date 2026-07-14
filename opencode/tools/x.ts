import { tool } from "@opencode-ai/plugin"
import { readFileSync } from "fs"
import { homedir } from "os"

/**
 * X (Twitter) live search via xAI's server-side x_search agent tool.
 *
 * Calls POST https://api.x.ai/v1/responses with the x_search tool; xAI runs
 * the search loop server-side and returns a synthesized answer with
 * citations. Legacy Live Search (search_parameters) is deprecated (410) —
 * this is the current mechanism.
 *
 * Auth: XAI_API_KEY env when present (official, metered: ~$5/1k calls),
 * otherwise the xAI OAuth access token from opencode's auth store
 * (subscription tier — UNOFFICIAL path; may start returning 403 at any
 * time). The token is read fresh per call and never included in output or
 * error messages.
 */

const AUTH_PATH = `${homedir()}/.local/share/opencode/auth.json`
const API_URL = "https://api.x.ai/v1/responses"

function resolveAuth(): { token: string; source: "api-key" | "oauth" } {
  const key = process.env["XAI_API_KEY"]
  if (key) return { token: key, source: "api-key" }
  let auth: any
  try {
    auth = JSON.parse(readFileSync(AUTH_PATH, "utf8"))
  } catch {
    throw new Error("No XAI_API_KEY set and opencode auth store is unreadable.")
  }
  const xai = auth?.xai
  if (xai?.type !== "oauth" || !xai.access) {
    throw new Error("No XAI_API_KEY set and no xAI OAuth credential found. Run `opencode auth login` for xAI, or set XAI_API_KEY.")
  }
  if (typeof xai.expires === "number" && xai.expires < Date.now()) {
    throw new Error(
      "The stored xAI OAuth token is expired. Any call to an xai/* model (e.g. the searcher subagent) refreshes it; retry after that, or set XAI_API_KEY.",
    )
  }
  return { token: xai.access, source: "oauth" }
}

export const search = tool({
  description:
    "Search X (Twitter) posts via xAI's server-side x_search tool: real-time sentiment, developer reactions, announcements, and posts from specific handles. Returns a synthesized answer with cited posts. Uses the Grok subscription tier. Never put secrets, private code, or internal identifiers in the query.",
  args: {
    query: tool.schema.string().describe("What to find out, in natural language. Include timeframe/topic context."),
    allowedHandles: tool.schema
      .array(tool.schema.string())
      .optional()
      .describe("Restrict search to these X handles (without @, max 20). Mutually exclusive with excludedHandles."),
    excludedHandles: tool.schema.array(tool.schema.string()).optional().describe("Exclude these X handles (without @, max 20)."),
    fromDate: tool.schema.string().optional().describe("Only posts on/after this date, YYYY-MM-DD."),
    toDate: tool.schema.string().optional().describe("Only posts on/before this date, YYYY-MM-DD."),
    enableImageUnderstanding: tool.schema.boolean().optional().describe("Analyze images in posts (extra tokens)."),
    enableVideoUnderstanding: tool.schema.boolean().optional().describe("Analyze videos in posts (extra tokens)."),
    model: tool.schema
      .enum(["grok-4.3", "grok-4.5"])
      .optional()
      .describe("Model that drives the search loop. Default grok-4.3 (fast); use grok-4.5 for hard synthesis."),
  },
  async execute(args) {
    if (args.allowedHandles?.length && args.excludedHandles?.length) {
      throw new Error("allowedHandles and excludedHandles are mutually exclusive.")
    }
    const { token, source } = resolveAuth()

    const xSearch: Record<string, unknown> = { type: "x_search" }
    if (args.allowedHandles?.length) xSearch["allowed_x_handles"] = args.allowedHandles.map((h) => h.replace(/^@/, ""))
    if (args.excludedHandles?.length) xSearch["excluded_x_handles"] = args.excludedHandles.map((h) => h.replace(/^@/, ""))
    if (args.fromDate) xSearch["from_date"] = args.fromDate
    if (args.toDate) xSearch["to_date"] = args.toDate
    if (args.enableImageUnderstanding) xSearch["enable_image_understanding"] = true
    if (args.enableVideoUnderstanding) xSearch["enable_video_understanding"] = true

    const res = await fetch(API_URL, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: args.model ?? "grok-4.3",
        input: [{ role: "user", content: args.query }],
        tools: [xSearch],
      }),
    })

    if (!res.ok) {
      const body = (await res.text()).slice(0, 400)
      if (res.status === 401) {
        throw new Error(
          `xAI API returned 401 (auth source: ${source}). The OAuth token may be stale — any xai/* model call refreshes it; retry afterwards. Body: ${body}`,
        )
      }
      if (res.status === 403) {
        throw new Error(
          `xAI API returned 403 (auth source: ${source}). The subscription OAuth path may have been closed for API access; switch to XAI_API_KEY (metered) or stop using x_search. Body: ${body}`,
        )
      }
      if (res.status === 429) {
        throw new Error(`xAI API returned 429 (rate limited / quota exhausted, auth source: ${source}). Retry later. Body: ${body}`)
      }
      throw new Error(`xAI API error ${res.status} (auth source: ${source}): ${body}`)
    }

    const json: any = await res.json()
    const output: any[] = json.output ?? []
    const text = output
      .filter((o) => o.type === "message")
      .flatMap((o) => (Array.isArray(o.content) ? o.content : []))
      .map((c) => c.text ?? "")
      .join("\n")
      .trim()

    // Collect citations from message content annotations and citations field.
    const citations = new Set<string>()
    for (const o of output) {
      if (o.type !== "message" || !Array.isArray(o.content)) continue
      for (const c of o.content) {
        for (const a of c.annotations ?? []) {
          const url = a.url ?? a.uri
          if (typeof url === "string") citations.add(url)
        }
      }
    }
    for (const u of json.citations ?? []) if (typeof u === "string") citations.add(u)

    const usage = json.usage ?? {}
    const toolCalls = usage.server_side_tool_usage_details?.x_search_calls ?? usage.num_server_side_tools_used ?? "?"

    const parts = [text || "(no answer text returned)"]
    if (citations.size) parts.push(`\nSources:\n${[...citations].map((u) => `- ${u}`).join("\n")}`)
    parts.push(`\n(x_search calls: ${toolCalls}, model: ${args.model ?? "grok-4.3"}, auth: ${source})`)
    return parts.join("\n")
  },
})
