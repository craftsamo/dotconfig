import { tool, type Plugin } from "@opencode-ai/plugin"

type Role = "explore-small" | "explore-high" | "worker" | "reviewer"
type Budget = "small" | "medium" | "high" | "max"
type ProviderChoice = "auto" | "openai" | "anthropic"

type ModelProfile = {
  providerID: "openai" | "anthropic"
  modelID: string
  options: Record<string, unknown>
}

type QuotaSignal = {
  openai: "available" | "exhausted" | "unknown"
  detail: string
}

const DEFAULT_BUDGET: Record<Role, Budget> = {
  "explore-small": "small",
  "explore-high": "high",
  worker: "medium",
  reviewer: "high",
}

const PROFILES: Record<"openai" | "anthropic", Record<Budget, ModelProfile>> = {
  openai: {
    small: { providerID: "openai", modelID: "gpt-5.4-mini", options: {} },
    medium: { providerID: "openai", modelID: "gpt-5.5", options: { reasoningEffort: "medium" } },
    high: { providerID: "openai", modelID: "gpt-5.5", options: { reasoningEffort: "high" } },
    max: { providerID: "openai", modelID: "gpt-5.5", options: { reasoningEffort: "xhigh" } },
  },
  anthropic: {
    small: { providerID: "anthropic", modelID: "claude-haiku-4-5", options: {} },
    medium: { providerID: "anthropic", modelID: "claude-sonnet-5", options: { reasoningEffort: "medium" } },
    high: { providerID: "anthropic", modelID: "claude-sonnet-5", options: { reasoningEffort: "high" } },
    max: { providerID: "anthropic", modelID: "claude-sonnet-5", options: { reasoningEffort: "max" } },
  },
}

function unwrap<T>(result: any): T {
  if (result && typeof result === "object" && "error" in result && result.error) {
    throw new Error(formatUnknownError(result.error))
  }
  if (result && typeof result === "object" && "data" in result) return result.data as T
  return result as T
}

function formatUnknownError(error: unknown): string {
  if (!error) return "unknown error"
  if (error instanceof Error) return error.message
  if (typeof error === "string") return error
  try {
    return JSON.stringify(error)
  } catch {
    return String(error)
  }
}

function assistantError(reply: any): string | undefined {
  const error = reply?.info?.error
  if (!error) return undefined
  const name = String(error.name ?? "AssistantError")
  const data = error.data ? `: ${formatUnknownError(error.data)}` : ""
  return `${name}${data}`
}

function textFromParts(parts: any[]): string {
  return parts
    .filter((part) => part?.type === "text" && typeof part.text === "string")
    .map((part) => part.text.trim())
    .filter(Boolean)
    .join("\n\n")
}

function isFallbackError(error: unknown): boolean {
  const msg = formatUnknownError(error).toLowerCase()
  return /quota|rate.?limit|too many requests|429|overloaded|capacity|temporar|timeout|providerauth|auth|unsupported.*reasoning|invalid.*reasoning/.test(msg)
}

function shortTitle(role: Role, description: string | undefined): string {
  const base = (description?.trim() || role).replace(/\s+/g, " ")
  return base.length <= 80 ? base : `${base.slice(0, 77)}...`
}

export const DelegatePlugin: Plugin = async ({ client, $ }) => {
  const sessionProfiles = new Map<string, ModelProfile>()
  let quotaCache: { time: number; signal: QuotaSignal } | undefined

  async function openaiQuota(): Promise<QuotaSignal> {
    const now = Date.now()
    if (quotaCache && now - quotaCache.time < 60_000) return quotaCache.signal

    const result = await $`npx -y @slkiser/opencode-quota show --json`.nothrow().quiet()
    if (result.exitCode !== 0) {
      const detail = result.stderr.toString().trim() || result.stdout.toString().trim() || `exit ${result.exitCode}`
      quotaCache = { time: now, signal: { openai: "unknown", detail } }
      return quotaCache.signal
    }

    try {
      const parsed = JSON.parse(result.stdout.toString())
      const openai = parsed?.providers?.openai
      if (openai?.status !== "ok") {
        quotaCache = { time: now, signal: { openai: "exhausted", detail: `OpenAI quota status: ${openai?.status ?? "missing"}` } }
        return quotaCache.signal
      }
      const entries = Array.isArray(openai.entries) ? openai.entries : []
      const exhausted = entries.some((entry: any) => !entry?.unlimited && Number(entry?.percentRemaining ?? 0) <= 0)
      const min = entries.reduce((acc: number, entry: any) => Math.min(acc, Number(entry?.percentRemaining ?? 100)), 100)
      quotaCache = {
        time: now,
        signal: { openai: exhausted ? "exhausted" : "available", detail: `OpenAI quota min remaining: ${min}%` },
      }
      return quotaCache.signal
    } catch (error) {
      quotaCache = { time: now, signal: { openai: "unknown", detail: `quota JSON parse failed: ${formatUnknownError(error)}` } }
      return quotaCache.signal
    }
  }

  async function providerOrder(choice: ProviderChoice): Promise<{ providers: Array<"openai" | "anthropic">; quota: QuotaSignal }> {
    const quota = await openaiQuota()
    if (choice === "openai") return { providers: ["openai", "anthropic"], quota }
    if (choice === "anthropic") {
      return { providers: quota.openai === "available" ? ["anthropic", "openai"] : ["anthropic"], quota }
    }
    return { providers: quota.openai === "exhausted" ? ["anthropic"] : ["openai", "anthropic"], quota }
  }

  async function runAttempt(args: { role: Role; budget: Budget; prompt: string; description?: string }, profile: ModelProfile, parentSessionID: string, directory: string | undefined) {
    const created = unwrap<any>(
      await client.session.create({
        body: { parentID: parentSessionID, title: shortTitle(args.role, args.description) },
        query: directory ? { directory } : undefined,
      } as any),
    )
    sessionProfiles.set(created.id, profile)
    try {
      const reply = unwrap<any>(
        await client.session.prompt({
          path: { id: created.id },
          query: directory ? { directory } : undefined,
          body: {
            agent: args.role,
            model: { providerID: profile.providerID, modelID: profile.modelID },
            system: `Delegated by the parent session. Budget tier: ${args.budget}.`,
            parts: [{ type: "text", text: args.prompt }],
          },
        } as any),
      )
      const error = assistantError(reply)
      if (error) throw new Error(error)
      return { sessionID: created.id, text: textFromParts(reply.parts ?? []), reply }
    } finally {
      sessionProfiles.delete(created.id)
    }
  }

  return {
    "chat.params": async (input, output) => {
      const profile = sessionProfiles.get(input.sessionID)
      if (!profile) return
      Object.assign(output.options, profile.options)
    },
    tool: {
      delegate: tool({
        description:
          "Run a specialized subagent through a quota-aware model router. Use this instead of the built-in task tool for explore-small, explore-high, worker, and reviewer delegation. It chooses OpenAI or Claude from the requested budget tier, applies provider options, and retries on quota/rate-limit style failures.",
        args: {
          role: tool.schema
            .enum(["explore-small", "explore-high", "worker", "reviewer"])
            .describe("Specialized agent role to run."),
          budget: tool.schema
            .enum(["auto", "small", "medium", "high", "max"])
            .optional()
            .describe('Compute budget. Use "auto" unless there is a concrete reason to force a tier.'),
          provider: tool.schema
            .enum(["auto", "openai", "anthropic"])
            .optional()
            .describe('Provider preference. Use "auto" by default; fallback still applies on quota/rate-limit failures.'),
          description: tool.schema.string().optional().describe("Short child-session title / task description."),
          prompt: tool.schema.string().describe("Full task prompt for the delegated agent."),
        },
        async execute(args, context) {
          const role = args.role as Role
          if (context.agent === "plan" && role === "worker") {
            throw new Error("Plan agent cannot delegate to worker because worker may edit files. Switch to Build first.")
          }

          const budget = args.budget === "auto" || !args.budget ? DEFAULT_BUDGET[role] : (args.budget as Budget)
          const choice = (args.provider ?? "auto") as ProviderChoice
          const { providers, quota } = await providerOrder(choice)
          const attempts: Array<{ provider: string; model: string; sessionID?: string; error?: string }> = []

          for (const provider of providers) {
            const profile = PROFILES[provider][budget]
            try {
              const result = await runAttempt(
                { role, budget, prompt: args.prompt, description: args.description },
                profile,
                context.sessionID,
                context.directory,
              )
              attempts.push({ provider, model: profile.modelID, sessionID: result.sessionID })
              return JSON.stringify(
                {
                  role,
                  budget,
                  provider,
                  model: profile.modelID,
                  options: profile.options,
                  childSessionID: result.sessionID,
                  quota: quota.detail,
                  attempts,
                  output: result.text,
                },
                null,
                2,
              )
            } catch (error) {
              attempts.push({ provider, model: profile.modelID, error: formatUnknownError(error) })
              if (!isFallbackError(error) || provider === providers[providers.length - 1]) throw error
            }
          }

          throw new Error(`delegate failed without running an attempt: ${JSON.stringify(attempts)}`)
        },
      }),
    },
  }
}
