import { describe, expect, test } from "bun:test"
import {
  MAX_CONTEXT_BYTES,
  METADATA_KEY,
  SUPPORTED_VERSION,
  setupPreflight,
  type RuntimeContext,
} from "./index"
import { ROUTES, type CatalogModel, type ModelRef } from "./policy"

const NOW = 1_710_000_000_000
const LOCATION = { directory: "/fixture" }
const iso = (ms: number) => new Date(NOW + ms).toISOString()
const sel = (m: ModelRef) =>
  `${m.providerID}/${m.id}${m.variant ? `#${m.variant}` : ""}`
const parse = (s: string): ModelRef => {
  const [providerID, rest] = [
    s.slice(0, s.indexOf("/")),
    s.slice(s.indexOf("/") + 1),
  ]
  const [id, variant] = rest.split("#")
  return variant ? { providerID, id, variant } : { providerID, id }
}

const SONNET_LOW: ModelRef = {
  providerID: "anthropic",
  id: "claude-sonnet-5-5",
  variant: "low",
}
const SOL_LOW: ModelRef = {
  providerID: "openai",
  id: "gpt-6.1-sol",
  variant: "low",
}
const LUNA_LOW: ModelRef = {
  providerID: "openai",
  id: "gpt-6-luna",
  variant: "low",
}

const catalog = (): CatalogModel[] => {
  const byKey = new Map<string, CatalogModel>()
  for (const route of Object.values(ROUTES)) {
    for (const m of [route.primary, route.alternate]) {
      const key = `${m.providerID}/${m.id}`
      const found = byKey.get(key) ?? {
        id: m.id,
        providerID: m.providerID,
        enabled: true,
        status: "active",
        capabilities: { tools: true },
        variants: [],
        limit: { context: 400_000, output: 32_000 },
      }
      if (m.variant && !found.variants.some((v) => v.id === m.variant))
        found.variants.push({ id: m.variant })
      byKey.set(key, found)
    }
  }
  return [...byKey.values()]
}

const anthropicBody = (
  exhausted: boolean,
  credits = false,
  unknown = false,
  resetMs = 3_600_000,
) => ({
  ...(unknown
    ? {}
    : {
        five_hour: {
          utilization: exhausted ? 100 : 10,
          resets_at: iso(resetMs),
        },
        seven_day: { utilization: 20, resets_at: iso(86_400_000) },
      }),
  extra_usage: credits
    ? {
        is_enabled: true,
        utilization: 10,
        monthly_limit: 100,
        used_credits: 10,
      }
    : { is_enabled: false },
  limits: [],
})
const openaiBody = (exhausted: boolean, credits = false, unknown = false) => ({
  plan_type: "plus",
  credits: credits
    ? { has_credits: true, unlimited: false, balance: "10" }
    : { has_credits: false, unlimited: false, balance: "0" },
  ...(unknown
    ? {}
    : {
        rate_limit: {
          allowed: !exhausted,
          limit_reached: exhausted,
          primary_window: {
            used_percent: exhausted ? 100 : 10,
            limit_window_seconds: 18_000,
            reset_after_seconds: 3_600,
          },
          secondary_window: {
            used_percent: 20,
            limit_window_seconds: 604_800,
            reset_after_seconds: 86_400,
          },
        },
      }),
})

type Session = {
  id: string
  parentID?: string
  agent?: string
  model?: ModelRef
  outcome?: "succeeded" | "failed" | "interrupted"
  metadata?: Record<string, unknown>
  location: { directory: string }
}
// "unknownquota": quota fields invalid but a valid billing block is present.
type Quota = "available" | "exhausted" | "bad" | "http500" | "unknownquota"

function makeEnv() {
  const env = {
    now: NOW,
    version: SUPPORTED_VERSION,
    childID: "ses_child",
    childParent: "ses_parent",
    progress: "normal" as "normal" | "none" | "noid" | "wrongid",
    childModelOverride: undefined as ModelRef | undefined,
    hasTool: true,
    inputLimit: undefined as number | undefined,
    failUpdate: false,
    resetMs: 3_600_000,
    credits: { anthropic: false, openai: false } as Record<string, boolean>,
    registered: 0,
    disposed: 0,
    updates: 0,
    fetchURLs: [] as string[],
    events: [] as string[],
    originals: [] as Array<{ input: Record<string, any>; context: any }>,
    sessions: new Map<string, Session>(),
    quota: { anthropic: "available", openai: "available" } as Record<
      string,
      Quota
    >,
    access: {
      anthropic: "fixture-anthropic",
      openai: "fixture-openai",
    } as Record<string, string>,
    connection: {
      anthropic: {
        type: "credential",
        id: "fixture-claude",
        method: "oauth",
      } as any,
      openai: {
        type: "credential",
        id: "fixture-chatgpt",
        method: "oauth",
      } as any,
    },
    agentModels: Object.fromEntries(
      Object.entries(ROUTES).map(([k, v]) => [k, v.primary]),
    ) as Record<string, ModelRef>,
  }
  env.sessions.set("ses_parent", {
    id: "ses_parent",
    agent: "build",
    location: LOCATION,
  })
  return env
}
type Env = ReturnType<typeof makeEnv>

const fakeFetch = (env: Env) =>
  (async (input: any) => {
    const url = String(input)
    env.fetchURLs.push(url)
    const provider = url.includes("anthropic")
      ? "anthropic"
      : url.includes("chatgpt")
        ? "openai"
        : undefined
    if (!provider) throw new Error("unexpected fetch")
    const mode = env.quota[provider]
    if (mode === "http500") return new Response("{}", { status: 500 })
    if (mode === "bad") return new Response("not json")
    const exhausted = mode === "exhausted"
    const unknown = mode === "unknownquota"
    const credits = env.credits[provider]
    return Response.json(
      provider === "anthropic"
        ? anthropicBody(exhausted, credits, unknown, env.resetMs)
        : openaiBody(exhausted, credits, unknown),
    )
  }) as unknown as typeof fetch

const original =
  (env: Env) => async (input: Record<string, any>, context: any) => {
    env.originals.push({ input, context })
    const continuing = typeof input.sessionID === "string"
    const id: string = continuing ? input.sessionID : env.childID
    if (!continuing) {
      const model =
        env.childModelOverride ??
        (typeof input.model === "string"
          ? parse(input.model)
          : env.agentModels[input.agent])
      env.sessions.set(id, {
        id,
        parentID: env.childParent,
        agent: input.agent,
        model,
        metadata: { keep: true },
        location: LOCATION,
      })
    }
    if (continuing) {
      // Native parent relationship is enforced before any mutation or progress.
      if (env.sessions.get(id)?.parentID !== context.sessionID)
        throw new Error("native parent mismatch")
      if (typeof input.model === "string")
        env.sessions.get(id)!.model = parse(input.model)
    }
    if (env.progress !== "none") {
      await context.progress(
        env.progress === "noid"
          ? { status: "running" }
          : {
              sessionID: env.progress === "wrongid" ? "ses_other" : id,
              status: "running",
            },
      )
    }
    env.events.push(
      `marker:${METADATA_KEY in (env.sessions.get(id)?.metadata ?? {})}`,
    )
    env.events.push("prompt")
    const status = input.background === true ? "running" : "completed"
    if (status === "completed") env.sessions.get(id)!.outcome = "succeeded"
    return {
      output: {
        sessionID: id,
        status,
        output: status === "running" ? "" : "done",
      },
      content: status === "running" ? "started" : "done",
      metadata: { sessionID: id, status },
    }
  }

async function install(
  env: Env,
  options: Record<string, unknown> = { enabled: true },
  rpc?: unknown,
) {
  const hooks: Record<string, Array<(e: any) => Promise<void>>> = {}
  const tool = { execute: original(env) as any }
  const reg = () => {
    env.registered++
    return {
      dispose: async () => {
        env.disposed++
      },
    }
  }
  const ctx = {
    app: {
      get version() {
        return env.version
      },
    },
    options,
    ...(rpc ? { rpc } : {}),
    agent: {
      get: async ({ agentID }: any) => ({
        data: { model: env.agentModels[agentID] },
      }),
    },
    model: {
      list: async () => ({
        data: catalog().map((m) =>
          env.inputLimit === undefined
            ? m
            : { ...m, limit: { ...m.limit, input: env.inputLimit } },
        ),
      }),
    },
    session: {
      get: async ({ sessionID }: any) => {
        const s = env.sessions.get(sessionID)
        if (!s) throw new Error("missing session")
        return s
      },
      update: async ({ sessionID, metadata }: any) => {
        env.updates++
        if (env.failUpdate) throw new Error("update rejected")
        env.sessions.get(sessionID)!.metadata = metadata
      },
      hook: async (name: string, cb: any) => {
        ;(hooks[name] ??= []).push(cb)
        return reg()
      },
    },
    tool: {
      transform: async (cb: any) => {
        cb({
          get: (id: string) =>
            id === "subagent" && env.hasTool ? {} : undefined,
          update: (_id: string, fn: any) => fn(tool),
        })
        return reg()
      },
    },
    provider: {
      get: async ({ providerID }: any) => ({
        data: {
          package: `@opencode/ai/providers/${providerID}`,
          integrationID: providerID,
        },
      }),
    },
    integration: {
      connection: {
        active: async (providerID: string) =>
          env.connection[providerID as "anthropic" | "openai"],
        resolve: async (connection: any) =>
          connection.id === "fixture-claude"
            ? {
                type: "oauth",
                methodID: "claude-max",
                access: env.access.anthropic,
                metadata: { accountID: "fixture-account" },
              }
            : {
                type: "oauth",
                methodID: "chatgpt-browser",
                access: env.access.openai,
                metadata: { accountID: "fixture-account" },
              },
      },
    },
  }
  const cleanup = await setupPreflight(ctx as unknown as RuntimeContext, {
    fetch: fakeFetch(env),
    now: () => env.now,
  })
  const fire = async <T>(name: string, event: T): Promise<T> => {
    for (const cb of hooks[name] ?? []) await cb(event)
    return event
  }
  const run = (
    input: Record<string, any>,
    signal: AbortSignal = new AbortController().signal,
  ) =>
    tool.execute(input, {
      sessionID: "ses_parent",
      id: "call_1",
      signal,
      progress: async (u: any) => {
        env.events.push(`progress:${u.sessionID}`)
      },
    })
  return { run, fire, cleanup }
}
type Inst = Awaited<ReturnType<typeof install>>

const setup = async (options?: Record<string, unknown>) => {
  const env = makeEnv()
  return { env, inst: await install(env, options) }
}
const launch = (
  inst: Inst,
  agent = "worker",
  extra: Record<string, unknown> = {},
) => inst.run({ agent, prompt: "p", background: true, ...extra })
const scope = (model: ModelRef, kind = "primary", sessionID = "ses_child") => ({
  sessionID,
  model,
  kind,
})
const text = (n: number) => [
  { role: "user", content: [{ type: "text", text: "x".repeat(n) }] },
]
const ctxEvent = (messages: unknown[]) => ({
  sessionID: "ses_child",
  model: SOL_LOW,
  system: [],
  messages,
  options: {},
})
const post = (url: string, headers: Record<string, string>) =>
  new Request(url, { method: "POST", headers })
const bearer = (token: string, extra: Record<string, string> = {}) => ({
  authorization: `Bearer ${token}`,
  ...extra,
})
const marker = (env: Env, id = "ses_child") =>
  env.sessions.get(id)?.metadata?.[METADATA_KEY] as any
const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages?beta=true"
const CODEX_URL = "https://chatgpt.com/backend-api/codex/responses"
const PRE = /Subagent preflight/

// An alternate (OpenAI sol) child admitted because Anthropic was exhausted.
async function fallbackChild() {
  const s = await setup()
  s.env.quota.anthropic = "exhausted"
  await launch(s.inst)
  s.env.quota.anthropic = "available"
  return s
}

describe("launch selection", () => {
  test("available source uses the exact default without mutating input", async () => {
    const { env, inst } = await setup()
    const input = { agent: "worker", prompt: "p" }
    const result = await inst.run(input)
    expect(input).toEqual({ agent: "worker", prompt: "p" })
    expect(env.originals.length).toBe(1)
    expect(env.originals[0].input).toEqual({ agent: "worker", prompt: "p" })
    expect(result).toEqual({
      output: { sessionID: "ses_child", status: "completed", output: "done" },
      content: "done",
      metadata: { sessionID: "ses_child", status: "completed" },
    })
    expect(marker(env).fallback).toBe(false)
    expect(marker(env).parentID).toBe("ses_parent")
  })

  test("exhausted source with available target injects the alternate once, preserving fields", async () => {
    const { env, inst } = await setup()
    env.quota.anthropic = "exhausted"
    const controller = new AbortController()
    const input = { agent: "worker", prompt: "p", background: false }
    await inst.run(input, controller.signal)
    expect(input).toEqual({ agent: "worker", prompt: "p", background: false })
    expect(env.originals.length).toBe(1)
    expect(env.originals[0].input).toEqual({
      agent: "worker",
      prompt: "p",
      background: false,
      model: sel(SOL_LOW),
    })
    expect(env.originals[0].context.signal === controller.signal).toBe(true)
    expect(marker(env).fallback).toBe(true)
    expect(marker(env).model).toEqual(SOL_LOW)
  })

  test("preserves background on fallback and retains the marker after the wrapper returns", async () => {
    const { env, inst } = await setup()
    env.quota.anthropic = "exhausted"
    const result = await launch(inst)
    expect(env.originals[0].input.background).toBe(true)
    expect(result.metadata.status).toBe("running")
    expect(marker(env).childID).toBe("ses_child")
    expect(marker(env).fallback).toBe(true)
  })

  test("foreground completion also retains the marker", async () => {
    const { env, inst } = await setup()
    await inst.run({ agent: "worker", prompt: "p" })
    expect(marker(env)).toBeDefined()
  })

  test("persists the marker before the child prompt starts", async () => {
    const { env, inst } = await setup()
    await inst.run({ agent: "worker", prompt: "p" })
    expect(env.events.indexOf("marker:true")).toBeGreaterThanOrEqual(0)
    expect(env.events.indexOf("marker:true")).toBeLessThan(
      env.events.indexOf("prompt"),
    )
    expect(env.updates).toBeGreaterThanOrEqual(1)
  })

  test("fallback adds notice content and metadata without changing structured output", async () => {
    const { env, inst } = await setup()
    env.quota.anthropic = "exhausted"
    const result = await inst.run({ agent: "worker", prompt: "p" })
    expect(result.output).toEqual({
      sessionID: "ses_child",
      status: "completed",
      output: "done",
    })
    expect(
      typeof result.content === "string" &&
        result.content.startsWith(
          `[Subagent preflight: worker ${sel(SONNET_LOW)} → ${sel(SOL_LOW)};`,
        ),
    ).toBe(true)
    expect(result.content.endsWith("\ndone")).toBe(true)
    expect(result.metadata).toEqual({
      sessionID: "ses_child",
      status: "completed",
      preflight: {
        funding: "included",
        from: sel(SONNET_LOW),
        to: sel(SOL_LOW),
      },
    })
  })

  test("stops before the original when billing is unknown (http failure or malformed JSON)", async () => {
    for (const mode of ["bad", "http500"] as const) {
      const { env, inst } = await setup()
      env.quota.anthropic = mode
      await expect(inst.run({ agent: "worker", prompt: "p" })).rejects.toThrow(
        PRE,
      )
      expect(env.originals.length).toBe(0)
    }
  })

  test("stops before the original when both pools are exhausted", async () => {
    const { env, inst } = await setup()
    env.quota.anthropic = "exhausted"
    env.quota.openai = "exhausted"
    await expect(inst.run({ agent: "worker", prompt: "p" })).rejects.toThrow(
      PRE,
    )
    expect(env.originals.length).toBe(0)
  })

  test("stops before the original for API-key or env accounts", async () => {
    for (const which of ["source", "target"] as const) {
      const { env, inst } = await setup()
      if (which === "source")
        env.connection.anthropic = {
          type: "env",
          id: "fixture-claude",
          method: "oauth",
        }
      else {
        env.quota.anthropic = "exhausted"
        env.connection.openai = {
          type: "credential",
          id: "fixture-chatgpt",
          method: "api",
        }
      }
      await expect(inst.run({ agent: "worker", prompt: "p" })).rejects.toThrow(
        PRE,
      )
      expect(env.originals.length).toBe(0)
    }
  })

  test("explicit model and sessionID pass through untouched", async () => {
    const { env, inst } = await setup()
    const input = { agent: "worker", model: sel(SOL_LOW), prompt: "p" }
    await inst.run(input)
    expect(env.originals[0].input).toBe(input)
    expect(env.fetchURLs.length).toBe(0)
    expect(
      env.sessions.get("ses_child")?.metadata?.[METADATA_KEY],
    ).toBeUndefined()
  })

  test("unknown role and changed configured model pass through", async () => {
    const { env, inst } = await setup()
    await inst.run({ agent: "not-a-role", prompt: "p" })
    env.agentModels.worker = {
      providerID: "anthropic",
      id: "claude-sonnet-5-5",
      variant: "high",
    }
    env.childID = "ses_two"
    await inst.run({ agent: "worker", prompt: "p" })
    expect(env.originals.length).toBe(2)
    expect(env.fetchURLs.length).toBe(0)
    expect(
      env.sessions.get("ses_two")?.metadata?.[METADATA_KEY],
    ).toBeUndefined()
  })

  test("rejects a child with the wrong parent before the prompt", async () => {
    const { env, inst } = await setup()
    env.childParent = "ses_somebody_else"
    await expect(inst.run({ agent: "worker", prompt: "p" })).rejects.toThrow(
      PRE,
    )
    expect(env.events.includes("prompt")).toBe(false)
    expect(marker(env)).toBeUndefined()
  })

  test("rejects a child whose actual model differs from the decision", async () => {
    const { env, inst } = await setup()
    env.childModelOverride = SOL_LOW
    await expect(inst.run({ agent: "worker", prompt: "p" })).rejects.toThrow(
      PRE,
    )
    expect(env.events.includes("prompt")).toBe(false)
  })

  test("rejects missing or unknown progress child identity before the prompt", async () => {
    for (const progress of ["noid", "wrongid"] as const) {
      const { env, inst } = await setup()
      env.progress = progress
      await expect(inst.run({ agent: "worker", prompt: "p" })).rejects.toThrow()
      expect(env.events.includes("prompt")).toBe(false)
    }
  })

  test("a builtin that never awaits pre-launch registration raises a late invariant alarm", async () => {
    // This cannot prevent the prompt: the version guard is what establishes
    // the trusted native behavior. The wrapper only alarms after the fact.
    const { env, inst } = await setup()
    env.progress = "none"
    await expect(inst.run({ agent: "worker", prompt: "p" })).rejects.toThrow(
      /did not await pre-launch registration/,
    )
    expect(env.events.includes("prompt")).toBe(true)
    expect(marker(env)).toBeUndefined()
  })

  test("cancellation before the original does not launch a child", async () => {
    const { env, inst } = await setup()
    const controller = new AbortController()
    controller.abort()
    await expect(
      inst.run({ agent: "worker", prompt: "p" }, controller.signal),
    ).rejects.toThrow()
    expect(env.originals.length).toBe(0)
    expect(env.sessions.has("ses_child")).toBe(false)
  })

  test("unsupported version stops automatic selection but explicit models pass", async () => {
    const { env, inst } = await setup()
    env.version = "2.0.24"
    await expect(inst.run({ agent: "worker", prompt: "p" })).rejects.toThrow(
      /unsupported OpenCode version/,
    )
    expect(env.originals.length).toBe(0)
    await inst.run({ agent: "worker", model: sel(SOL_LOW), prompt: "p" })
    expect(env.originals.length).toBe(1)
  })

  test("setup failure disposes registered hooks", async () => {
    const env = makeEnv()
    env.hasTool = false
    await expect(install(env)).rejects.toThrow(
      /builtin subagent executor unavailable/,
    )
    expect(env.registered).toBeGreaterThan(0)
    expect(env.disposed).toBe(env.registered)
  })
})

describe("options and persistence", () => {
  test("enabled=false stops new selection while existing marked children stay guarded", async () => {
    const env = makeEnv()
    const first = await install(env)
    await launch(first)
    await first.cleanup()
    const off = await install(env, { enabled: false })
    env.childID = "ses_new"
    const fetchesBefore = env.fetchURLs.length
    await off.run({ agent: "worker", prompt: "p" })
    expect(env.fetchURLs.length - fetchesBefore).toBe(0)
    expect(
      env.sessions.get("ses_new")?.metadata?.[METADATA_KEY],
    ).toBeUndefined()
    const bad = post(ANTHROPIC_URL, bearer("fixture-wrong"))
    await expect(
      off.fire("http.request", { ...scope(SONNET_LOW), request: bad }),
    ).rejects.toThrow(PRE)
  })

  test("a new setup rehydrates the guard from persisted metadata", async () => {
    const env = makeEnv()
    const first = await install(env)
    await launch(first)
    await first.cleanup()
    const second = await install(env)
    await expect(
      second.fire("http.request", {
        ...scope(SONNET_LOW),
        request: post(ANTHROPIC_URL, bearer("fixture-wrong")),
      }),
    ).rejects.toThrow(PRE)
    await second.fire("http.request", {
      ...scope(SONNET_LOW),
      request: post(ANTHROPIC_URL, bearer("fixture-anthropic")),
    })
  })

  test("an inherited marker does not protect the parent or nested ordinary sessions", async () => {
    const { env, inst } = await setup()
    await launch(inst)
    const inherited = { [METADATA_KEY]: marker(env) }
    env.sessions.get("ses_parent")!.metadata = inherited
    env.sessions.set("ses_nested", {
      id: "ses_nested",
      parentID: "ses_child",
      agent: "worker",
      model: SONNET_LOW,
      metadata: inherited,
      location: LOCATION,
    })
    for (const id of ["ses_parent", "ses_nested"]) {
      const request = post("https://api.openai.com/v1/responses", {})
      await inst.fire("http.request", {
        ...scope(SONNET_LOW, "primary", id),
        request,
      })
    }
  })

  test("root HTTP requests are untouched", async () => {
    const { env, inst } = await setup()
    const request = new Request("https://api.openai.com/v1/responses", {
      method: "GET",
    })
    await inst.fire("http.request", {
      ...scope(SOL_LOW, "primary", "ses_parent"),
      request,
    })
    await inst.fire("retry", {
      sessionID: "ses_parent",
      error: { type: "provider.quota", message: "x" },
      decision: { retry: true, delay: 1 },
    })
    expect(env.fetchURLs.length).toBe(0)
  })
})

describe("protected HTTP", () => {
  test("denies unapproved routes, credentials, accounts and methods", async () => {
    const { inst } = await setup()
    await launch(inst)
    const cases: Array<Request> = [
      post("https://api.openai.com/v1/responses", bearer("fixture-anthropic")),
      post("https://evil.example/v1/messages", bearer("fixture-anthropic")),
      post(ANTHROPIC_URL, bearer("fixture-wrong")),
      post(ANTHROPIC_URL, {
        ...bearer("fixture-anthropic"),
        "x-api-key": "fixture-key",
      }),
      new Request(ANTHROPIC_URL, {
        method: "GET",
        headers: bearer("fixture-anthropic"),
      }),
    ]
    for (const request of cases)
      await expect(
        inst.fire("http.request", { ...scope(SONNET_LOW), request }),
      ).rejects.toThrow(PRE)
  })

  test("denies a mismatched ChatGPT account and non-codex routes", async () => {
    const { env, inst } = await setup()
    await launch(inst, "verifier")
    const wrong = post(
      CODEX_URL,
      bearer("fixture-openai", { "chatgpt-account-id": "fixture-other" }),
    )
    await expect(
      inst.fire("http.request", { ...scope(LUNA_LOW), request: wrong }),
    ).rejects.toThrow(PRE)
    const route = post(
      "https://chatgpt.com/backend-api/other",
      bearer("fixture-openai", { "chatgpt-account-id": "fixture-account" }),
    )
    await expect(
      inst.fire("http.request", { ...scope(LUNA_LOW), request: route }),
    ).rejects.toThrow(PRE)
    expect(env.originals.length).toBe(1)
  })

  test("accepts approved Anthropic and ChatGPT codex requests and enforces redirect error", async () => {
    const a = await setup()
    await launch(a.inst)
    const anthropic = await a.inst.fire("http.request", {
      ...scope(SONNET_LOW),
      request: post(ANTHROPIC_URL, bearer("fixture-anthropic")),
    })
    expect(anthropic.request.redirect).toBe("error")
    expect(anthropic.request.method).toBe("POST")

    const o = await setup()
    await launch(o.inst, "verifier")
    const request = post(
      CODEX_URL,
      bearer("fixture-openai", { "chatgpt-account-id": "fixture-account" }),
    )
    expect(request.redirect).toBe("follow")
    const codex = await o.inst.fire("http.request", {
      ...scope(LUNA_LOW),
      request,
    })
    expect(codex.request.redirect).toBe("error")
    expect(codex.request.method).toBe("POST")
  })

  test("auxiliary requests are guarded: compact only for compaction, unapproved models denied", async () => {
    const { inst } = await setup()
    await launch(inst, "verifier")
    const headers = bearer("fixture-openai", {
      "chatgpt-account-id": "fixture-account",
    })
    const compact = "https://chatgpt.com/backend-api/codex/responses/compact"
    await inst.fire("http.request", {
      ...scope(LUNA_LOW, "compaction"),
      request: post(compact, headers),
    })
    await expect(
      inst.fire("http.request", {
        ...scope(LUNA_LOW, "title"),
        request: post(compact, headers),
      }),
    ).rejects.toThrow(PRE)
    await inst.fire("http.request", {
      ...scope(LUNA_LOW, "title"),
      request: post(CODEX_URL, headers),
    })
    const unapproved = { providerID: "openai", id: "gpt-unlisted" }
    await expect(
      inst.fire("http.request", {
        ...scope(unapproved, "title"),
        request: post(CODEX_URL, headers),
      }),
    ).rejects.toThrow(PRE)
  })

  test("a changed child model is rejected rather than switched", async () => {
    const { env, inst } = await setup()
    await launch(inst)
    env.sessions.get("ses_child")!.model = {
      providerID: "anthropic",
      id: "claude-sonnet-5-5",
      variant: "medium",
    }
    await expect(
      inst.fire("http.request", {
        ...scope(SONNET_LOW),
        request: post(ANTHROPIC_URL, bearer("fixture-anthropic")),
      }),
    ).rejects.toThrow(/model changed/)
  })

  test("an unsupported version stops protected children", async () => {
    const { env, inst } = await setup()
    await launch(inst)
    env.version = "2.0.24"
    await expect(
      inst.fire("http.request", {
        ...scope(SONNET_LOW),
        request: post(ANTHROPIC_URL, bearer("fixture-anthropic")),
      }),
    ).rejects.toThrow(/unsupported OpenCode version/)
  })

  test("an exhausted quota mid-task stops the child instead of switching", async () => {
    const { env, inst } = await setup()
    await launch(inst)
    env.now += 16_000
    env.quota.anthropic = "exhausted"
    await expect(
      inst.fire("http.request", {
        ...scope(SONNET_LOW),
        request: post(ANTHROPIC_URL, bearer("fixture-anthropic")),
      }),
    ).rejects.toThrow(PRE)
  })
})

describe("WebSocket", () => {
  const url = "wss://chatgpt.com/backend-api/codex/responses"
  const headers = {
    authorization: "Bearer fixture-openai",
    "chatgpt-account-id": "fixture-account",
  }
  const childSetup = async () => {
    const s = await setup()
    await launch(s.inst, "verifier")
    return s
  }

  test("an approved handshake followed by send succeeds", async () => {
    const { inst } = await childSetup()
    await inst.fire("experimental.ws.handshake", {
      ...scope(LUNA_LOW),
      url,
      headers,
    })
    await inst.fire("experimental.ws.send", { ...scope(LUNA_LOW), frame: "{}" })
  })

  test("send without a handshake is denied", async () => {
    const { inst } = await childSetup()
    await expect(
      inst.fire("experimental.ws.send", { ...scope(LUNA_LOW), frame: "{}" }),
    ).rejects.toThrow(PRE)
  })

  test("wrong identity or untrusted URL is denied at handshake, before any frame", async () => {
    const { inst } = await childSetup()
    const bad = [
      { url, headers: { ...headers, "chatgpt-account-id": "fixture-other" } },
      { url, headers: { ...headers, authorization: "Bearer fixture-wrong" } },
      { url, headers: { ...headers, "x-api-key": "fixture-key" } },
      { url: "wss://evil.example/backend-api/codex/responses", headers },
      { url: "ws://chatgpt.com/backend-api/codex/responses", headers },
    ]
    for (const item of bad)
      await expect(
        inst.fire("experimental.ws.handshake", { ...scope(LUNA_LOW), ...item }),
      ).rejects.toThrow(PRE)
    await expect(
      inst.fire("experimental.ws.send", { ...scope(LUNA_LOW), frame: "{}" }),
    ).rejects.toThrow(PRE)
  })

  test("an account change between handshake and send is rejected", async () => {
    const { env, inst } = await childSetup()
    await inst.fire("experimental.ws.handshake", {
      ...scope(LUNA_LOW),
      url,
      headers,
    })
    env.access.openai = "fixture-openai-rotated"
    await expect(
      inst.fire("experimental.ws.send", { ...scope(LUNA_LOW), frame: "{}" }),
    ).rejects.toThrow(PRE)
  })
})

describe("retry", () => {
  const event = (
    sessionID: string,
    type: string,
    delay: number,
    extra: Record<string, unknown> = {},
  ) => ({
    sessionID,
    error: { type, message: "limit", ...extra },
    decision: { retry: true, delay } as any,
  })

  test("protected quota and long rate-limit delays do not retry", async () => {
    const { inst } = await setup()
    await launch(inst)
    expect(
      (await inst.fire("retry", event("ses_child", "provider.quota", 1_000)))
        .decision,
    ).toEqual({ retry: false })
    expect(
      (
        await inst.fire(
          "retry",
          event("ses_child", "provider.rate-limit", 18_000_000),
        )
      ).decision,
    ).toEqual({ retry: false })
    expect(
      (await inst.fire("retry", event("ses_child", "x", 10, { status: 429 })))
        .decision,
    ).toEqual({ retry: true, delay: 10 })
    expect(
      (
        await inst.fire(
          "retry",
          event("ses_child", "x", 18_000_000, { status: 429 }),
        )
      ).decision,
    ).toEqual({ retry: false })
  })

  test("short transient rate limits keep native retry; root sessions are unchanged", async () => {
    const { inst } = await setup()
    await launch(inst)
    expect(
      (
        await inst.fire(
          "retry",
          event("ses_child", "provider.rate-limit", 2_000),
        )
      ).decision,
    ).toEqual({ retry: true, delay: 2_000 })
    expect(
      (
        await inst.fire(
          "retry",
          event("ses_parent", "provider.quota", 18_000_000),
        )
      ).decision,
    ).toEqual({ retry: true, delay: 18_000_000 })
  })
})

describe("alternate launch context", () => {
  test("a valid text context is accepted and persists launchChecked", async () => {
    const { env, inst } = await fallbackChild()
    await inst.fire("context", ctxEvent(text(10)))
    expect(marker(env).launchChecked).toBe(true)
    expect(marker(env).fallback).toBe(true)
    await inst.fire("http.request", {
      ...scope(SOL_LOW),
      request: post(
        CODEX_URL,
        bearer("fixture-openai", { "chatgpt-account-id": "fixture-account" }),
      ),
    })
  })

  test("a small initial context is rejected when the catalog input limit lacks headroom", async () => {
    const { env, inst } = await fallbackChild()
    env.inputLimit = 32_000
    const updates = env.updates
    await expect(inst.fire("context", ctxEvent(text(10)))).rejects.toThrow(
      /catalog lacks conservative context headroom/,
    )
    expect(marker(env).launchChecked).toBeUndefined()
    expect(env.updates).toBe(updates)
  })

  test("primary requests are denied until the launch context was checked", async () => {
    const { inst } = await fallbackChild()
    await expect(
      inst.fire("http.request", {
        ...scope(SOL_LOW),
        request: post(
          CODEX_URL,
          bearer("fixture-openai", { "chatgpt-account-id": "fixture-account" }),
        ),
      }),
    ).rejects.toThrow(/not checked/)
  })

  test("media or oversized initial contexts are rejected", async () => {
    const media = [
      {
        role: "user",
        content: [
          { type: "text", text: "hi" },
          { type: "image", data: "fixture" },
        ],
      },
    ]
    for (const messages of [media, text(MAX_CONTEXT_BYTES)]) {
      const { env, inst } = await fallbackChild()
      await expect(inst.fire("context", ctxEvent(messages))).rejects.toThrow(
        PRE,
      )
      expect(marker(env).launchChecked).toBeUndefined()
    }
  })

  test("after the first check, ordinary assistant and tool contexts need not be resized", async () => {
    const { env, inst } = await fallbackChild()
    await inst.fire("context", ctxEvent(text(10)))
    const updates = env.updates
    const later = [
      ...text(MAX_CONTEXT_BYTES),
      { role: "tool", content: [{ type: "tool-result", output: "x" }] },
    ]
    await inst.fire("context", ctxEvent(later))
    expect(env.updates).toBe(updates)
  })

  test("non-fallback children are not subject to the launch context check", async () => {
    const { inst } = await setup()
    await launch(inst)
    await inst.fire("context", {
      ...ctxEvent(text(MAX_CONTEXT_BYTES)),
      model: SONNET_LOW,
    })
  })
})

describe("continuations", () => {
  const OUTCOMES = [undefined, "succeeded", "failed", "interrupted"] as const
  const STICKY = /protected continuations keep their role and model/

  test("same-role same-model continuation passes the original once and keeps the marker, for any outcome", async () => {
    for (const outcome of OUTCOMES) {
      for (const model of [undefined, sel(SONNET_LOW)]) {
        const { env, inst } = await setup()
        await launch(inst)
        env.sessions.get("ses_child")!.outcome = outcome
        const updates = env.updates
        const fetches = env.fetchURLs.length
        const input = {
          sessionID: "ses_child",
          agent: "worker",
          prompt: "more",
          ...(model ? { model } : {}),
        }
        await inst.run(input)
        expect(env.originals.length).toBe(2)
        expect(env.originals[1].input).toBe(input)
        expect(marker(env)).toBeDefined()
        expect(marker(env).fallback).toBe(false)
        expect(env.updates).toBe(updates)
        expect(env.fetchURLs.length).toBe(fetches)
        expect(env.sessions.get("ses_child")?.model).toEqual(SONNET_LOW)
      }
    }
  })

  test("a different role or model is rejected before the original regardless of outcome", async () => {
    const changes: Array<Record<string, unknown>> = [
      { agent: "reviewer" },
      { agent: "worker", model: sel(SOL_LOW) },
      { agent: "worker", model: "anthropic/claude-sonnet-5-5#medium" },
      { agent: "reviewer", model: sel(SONNET_LOW) },
    ]
    for (const outcome of OUTCOMES) {
      for (const change of changes) {
        const { env, inst } = await setup()
        await launch(inst)
        env.sessions.get("ses_child")!.outcome = outcome
        const updates = env.updates
        await expect(
          inst.run({ sessionID: "ses_child", prompt: "more", ...change }),
        ).rejects.toThrow(STICKY)
        expect(env.originals.length).toBe(1)
        expect(env.sessions.get("ses_child")?.model).toEqual(SONNET_LOW)
        expect(marker(env)).toBeDefined()
        expect(env.updates).toBe(updates)
      }
    }
  })

  test("a historical succeeded outcome does not unblock a model override (outcome is not a busy flag)", async () => {
    const { env, inst } = await setup()
    await inst.run({ agent: "worker", prompt: "p" })
    // Fake builtin recorded outcome=succeeded for the completed first run; a
    // new run is conceptually in flight but the outcome stays historical.
    expect(env.sessions.get("ses_child")?.outcome).toBe("succeeded")
    await expect(
      inst.run({
        sessionID: "ses_child",
        agent: "worker",
        prompt: "more",
        model: sel(SOL_LOW),
      }),
    ).rejects.toThrow(STICKY)
    expect(env.originals.length).toBe(1)
    expect(marker(env)).toBeDefined()
  })

  test("a background running child keeps its marker on same-model continuation", async () => {
    const { env, inst } = await setup()
    await launch(inst)
    expect(env.sessions.get("ses_child")?.outcome).toBeUndefined()
    await inst.run({ sessionID: "ses_child", agent: "worker", prompt: "more" })
    expect(marker(env)).toBeDefined()
  })

  test("an unmarked existing child passes through to the native builtin unchanged", async () => {
    const { env, inst } = await setup()
    env.sessions.set("ses_plain", {
      id: "ses_plain",
      parentID: "ses_parent",
      agent: "worker",
      model: SONNET_LOW,
      metadata: { keep: true },
      location: LOCATION,
    })
    const input = {
      sessionID: "ses_plain",
      agent: "reviewer",
      model: sel(SOL_LOW),
      prompt: "more",
    }
    await inst.run(input)
    expect(env.originals.length).toBe(1)
    expect(env.originals[0].input).toBe(input)
    expect(env.events.includes("progress:ses_plain")).toBe(true)
    expect(env.sessions.get("ses_plain")?.metadata).toEqual({ keep: true })
    expect(env.updates).toBe(0)
    expect(env.fetchURLs.length).toBe(0)
  })

  test("a foreign existing child reaches the original and fails the native parent check without our effects", async () => {
    const { env, inst } = await setup()
    env.sessions.set("ses_foreign", {
      id: "ses_foreign",
      parentID: "ses_somebody_else",
      agent: "worker",
      model: SONNET_LOW,
      metadata: { keep: true },
      location: LOCATION,
    })
    await expect(
      inst.run({
        sessionID: "ses_foreign",
        agent: "reviewer",
        model: sel(SOL_LOW),
        prompt: "more",
      }),
    ).rejects.toThrow(/native parent mismatch/)
    expect(env.originals.length).toBe(1)
    expect(env.sessions.get("ses_foreign")?.model).toEqual(SONNET_LOW)
    expect(env.sessions.get("ses_foreign")?.metadata).toEqual({ keep: true })
    expect(env.updates).toBe(0)
  })

  test("a marked child owned by another parent is not guarded by us; native parent check fails", async () => {
    const { env, inst } = await setup()
    await launch(inst)
    const foreign = env.sessions.get("ses_child")!
    foreign.parentID = "ses_somebody_else"
    foreign.metadata = {
      keep: true,
      [METADATA_KEY]: { ...marker(env), parentID: "ses_somebody_else" },
    }
    const updates = env.updates
    await expect(
      inst.run({
        sessionID: "ses_child",
        agent: "reviewer",
        model: sel(SOL_LOW),
        prompt: "more",
      }),
    ).rejects.toThrow(/native parent mismatch/)
    expect(env.originals.length).toBe(2)
    expect(env.sessions.get("ses_child")?.model).toEqual(SONNET_LOW)
    expect(marker(env)).toBeDefined()
    expect(env.updates).toBe(updates)
  })

  test("progress irregularities on a protected continuation leave the marker and metadata untouched", async () => {
    for (const progress of ["wrongid", "none"] as const) {
      const { env, inst } = await setup()
      await launch(inst)
      env.sessions.get("ses_child")!.outcome = "succeeded"
      env.progress = progress
      const updates = env.updates
      await inst.run({
        sessionID: "ses_child",
        agent: "worker",
        prompt: "more",
      })
      expect(marker(env)).toBeDefined()
      expect(env.updates).toBe(updates)
    }
  })
})

describe("alternate wire size", () => {
  const WIRE = /wire context exceeds conservative headroom/
  const wsURL = "wss://chatgpt.com/backend-api/codex/responses"
  const openaiHeaders = bearer("fixture-openai", {
    "chatgpt-account-id": "fixture-account",
  })
  const bodyRequest = (body: string, url = CODEX_URL) =>
    new Request(url, { method: "POST", headers: openaiHeaders, body })
  const checkedChild = async () => {
    const s = await fallbackChild()
    await s.inst.fire("context", ctxEvent(text(10)))
    return s
  }
  const sendHTTP = (inst: Inst, request: Request, kind = "primary") =>
    inst.fire("http.request", { ...scope(SOL_LOW, kind), request })
  const handshake = (inst: Inst) =>
    inst.fire("experimental.ws.handshake", {
      ...scope(SOL_LOW),
      url: wsURL,
      headers: openaiHeaders,
    })
  const sendFrame = (inst: Inst, frame: string) =>
    inst.fire("experimental.ws.send", { ...scope(SOL_LOW), frame })

  test("an oversized HTTP body fails even when the initial context was small", async () => {
    const { env, inst } = await checkedChild()
    expect(marker(env).launchChecked).toBe(true)
    const updates = env.updates
    await expect(
      sendHTTP(inst, bodyRequest("x".repeat(MAX_CONTEXT_BYTES + 1))),
    ).rejects.toThrow(WIRE)
    expect(marker(env).wireChecked === undefined).toBe(true)
    expect(env.updates).toBe(updates)
  })

  test("an oversized WebSocket frame fails after a valid handshake and context", async () => {
    const { env, inst } = await checkedChild()
    await handshake(inst)
    await expect(
      sendFrame(inst, "x".repeat(MAX_CONTEXT_BYTES + 1)),
    ).rejects.toThrow(WIRE)
    expect(marker(env).wireChecked === undefined).toBe(true)
  })

  test("a small catalog input limit below body plus headroom fails the first wire body", async () => {
    const { env, inst } = await checkedChild()
    env.inputLimit = 32_000
    const updates = env.updates
    await expect(sendHTTP(inst, bodyRequest("{}"))).rejects.toThrow(WIRE)
    expect(marker(env).wireChecked === undefined).toBe(true)
    expect(env.updates).toBe(updates)
  })

  test("a valid HTTP body passes and persists wireChecked before the caller would send", async () => {
    const { env, inst } = await checkedChild()
    const updates = env.updates
    const event = await sendHTTP(
      inst,
      bodyRequest(JSON.stringify({ input: "ok" })),
    )
    expect(marker(env).wireChecked).toBe(true)
    expect(env.updates).toBe(updates + 1)
    expect(event.request.redirect).toBe("error")
    // Later native contexts may be oversized: no re-check, no new update.
    await sendHTTP(inst, bodyRequest("x".repeat(MAX_CONTEXT_BYTES + 1)))
    await inst.fire("context", ctxEvent(text(MAX_CONTEXT_BYTES + 1)))
    expect(env.updates).toBe(updates + 1)
  })

  test("a valid WebSocket frame passes and persists wireChecked", async () => {
    const { env, inst } = await checkedChild()
    await handshake(inst)
    const updates = env.updates
    await sendFrame(inst, JSON.stringify({ type: "response.create" }))
    expect(marker(env).wireChecked).toBe(true)
    expect(env.updates).toBe(updates + 1)
    await sendFrame(inst, "x".repeat(MAX_CONTEXT_BYTES + 1))
    expect(env.updates).toBe(updates + 1)
  })

  test("a reloaded setup retains wireChecked, skips only the size check, and keeps identity guards", async () => {
    const { env, inst } = await checkedChild()
    await sendHTTP(inst, bodyRequest("{}"))
    await inst.cleanup()
    const again = await install(env)
    expect(marker(env).wireChecked).toBe(true)
    const updates = env.updates
    await sendHTTP(again, bodyRequest("x".repeat(MAX_CONTEXT_BYTES + 1)))
    expect(env.updates).toBe(updates)
    await expect(
      sendHTTP(again, bodyRequest("{}", "https://api.openai.com/v1/responses")),
    ).rejects.toThrow(PRE)
    const wrong = new Request(CODEX_URL, {
      method: "POST",
      headers: bearer("fixture-wrong", {
        "chatgpt-account-id": "fixture-account",
      }),
      body: "{}",
    })
    await expect(sendHTTP(again, wrong)).rejects.toThrow(PRE)
  })

  test("an auxiliary request does not run the wire check or set wireChecked", async () => {
    const { env, inst } = await checkedChild()
    const updates = env.updates
    await sendHTTP(
      inst,
      bodyRequest("x".repeat(MAX_CONTEXT_BYTES + 1)),
      "title",
    )
    expect(marker(env).wireChecked === undefined).toBe(true)
    expect(env.updates).toBe(updates)
  })

  test("a first context whose tool schema overhead is oversized fails", async () => {
    const { env, inst } = await fallbackChild()
    const event = {
      ...ctxEvent(text(10)),
      tools: [{ name: "t", description: "x".repeat(MAX_CONTEXT_BYTES + 1) }],
    }
    await expect(inst.fire("context", event)).rejects.toThrow(
      /exceeds the conservative text limit/,
    )
    expect(marker(env).launchChecked === undefined).toBe(true)
  })
})

describe("funding priority and credits last resort", () => {
  const CREDITS = { enabled: true, creditsLastResort: true }
  const ANTHROPIC_REQ = () => post(ANTHROPIC_URL, bearer("fixture-anthropic"))
  const OPENAI_REQ = (body = "{}") =>
    new Request(CODEX_URL, {
      method: "POST",
      headers: bearer("fixture-openai", {
        "chatgpt-account-id": "fixture-account",
      }),
      body,
    })
  const bothExhausted = (env: Env, anthropic: boolean, openai: boolean) => {
    env.quota.anthropic = "exhausted"
    env.quota.openai = "exhausted"
    env.credits.anthropic = anthropic
    env.credits.openai = openai
  }
  const hitsOpenAI = (env: Env) =>
    env.fetchURLs.some((u) => u.includes("chatgpt"))
  const sendAnthropic = (inst: Inst) =>
    inst.fire("http.request", {
      ...scope(SONNET_LOW),
      request: ANTHROPIC_REQ(),
    })

  test("available primary with credits stays default and does not probe the target", async () => {
    const { env, inst } = await setup(CREDITS)
    env.credits.anthropic = true
    await inst.run({ agent: "worker", prompt: "p" })
    expect(env.originals[0].input).toEqual({ agent: "worker", prompt: "p" })
    expect(hitsOpenAI(env)).toBe(false)
    expect(marker(env).fallback).toBe(false)
    expect(marker(env).funding).toBe("included")
    expect(marker(env).allowUnknownQuota).toBe(true)
  })

  test("exhausted primary with an available target stays FALLBACK with included funding, not credits", async () => {
    const { env, inst } = await setup(CREDITS)
    env.quota.anthropic = "exhausted"
    env.credits.anthropic = true
    env.credits.openai = true
    const result = await inst.run({ agent: "worker", prompt: "p" })
    expect(env.originals.length).toBe(1)
    expect(env.originals[0].input.model).toBe(sel(SOL_LOW))
    expect(marker(env).fallback).toBe(true)
    expect(marker(env).funding).toBe("included")
    expect(marker(env).allowUnknownQuota).toBe(false)
    expect(result.metadata.preflight.funding).toBe("included")
  })

  test("both exhausted with primary credits runs the unmodified primary on credits", async () => {
    const { env, inst } = await setup(CREDITS)
    bothExhausted(env, true, false)
    const result = await inst.run({ agent: "worker", prompt: "p" })
    expect(env.originals.length).toBe(1)
    expect(env.originals[0].input).toEqual({ agent: "worker", prompt: "p" })
    expect(env.sessions.get("ses_child")?.model).toEqual(SONNET_LOW)
    expect(marker(env).fallback).toBe(false)
    expect(marker(env).funding).toBe("credits")
    expect(marker(env).allowUnknownQuota).toBe(false)
    expect(
      typeof result.content === "string" &&
        result.content.startsWith(
          `[Subagent preflight: worker ${sel(SONNET_LOW)}; both included quotas exhausted, existing credits authorized as last resort.`,
        ),
    ).toBe(true)
    expect(result.content.includes("No credit purchase")).toBe(true)
    expect(result.output).toEqual({
      sessionID: "ses_child",
      status: "completed",
      output: "done",
    })
    expect(result.metadata.preflight).toEqual({
      funding: "credits",
      from: sel(SONNET_LOW),
      to: sel(SONNET_LOW),
    })
  })

  test("both exhausted with credits only on the target injects the alternate on credits", async () => {
    const { env, inst } = await setup(CREDITS)
    bothExhausted(env, false, true)
    const result = await inst.run({ agent: "worker", prompt: "p" })
    expect(env.originals.length).toBe(1)
    expect(env.originals[0].input.model).toBe(sel(SOL_LOW))
    expect(marker(env).fallback).toBe(true)
    expect(marker(env).funding).toBe("credits")
    expect(marker(env).allowUnknownQuota).toBe(false)
    expect(result.metadata.preflight).toEqual({
      funding: "credits",
      from: sel(SONNET_LOW),
      to: sel(SOL_LOW),
    })
  })

  test("with creditsLastResort not true, both-exhausted credits stop before the builtin", async () => {
    for (const options of [
      { enabled: true },
      { enabled: true, creditsLastResort: false },
    ]) {
      const { env, inst } = await setup(options)
      bothExhausted(env, true, true)
      await expect(inst.run({ agent: "worker", prompt: "p" })).rejects.toThrow(
        /last-resort credits are disabled/,
      )
      expect(env.originals.length).toBe(0)
    }
  })

  test("an unknown pool can never spend credits", async () => {
    const a = await setup(CREDITS)
    a.env.quota.anthropic = "exhausted"
    a.env.credits.anthropic = true
    a.env.quota.openai = "unknownquota"
    a.env.credits.openai = true
    await expect(a.inst.run({ agent: "worker", prompt: "p" })).rejects.toThrow(
      PRE,
    )
    expect(a.env.originals.length).toBe(0)

    const b = await setup(CREDITS)
    b.env.quota.anthropic = "unknownquota"
    b.env.credits.anthropic = true
    b.env.quota.openai = "exhausted"
    b.env.credits.openai = true
    await expect(b.inst.run({ agent: "worker", prompt: "p" })).rejects.toThrow(
      /existing credits cannot be used yet/,
    )
    expect(b.env.originals.length).toBe(0)

    const c = await setup(CREDITS)
    bothExhausted(c.env, true, true)
    c.env.quota.openai = "http500"
    await expect(c.inst.run({ agent: "worker", prompt: "p" })).rejects.toThrow(
      PRE,
    )
    expect(c.env.originals.length).toBe(0)
  })

  test("API-key and env accounts never use credits", async () => {
    for (const provider of ["anthropic", "openai"] as const) {
      const { env, inst } = await setup(CREDITS)
      bothExhausted(env, true, true)
      env.connection[provider] = {
        type: "env",
        id: "fixture-env",
        method: "oauth",
      }
      await expect(inst.run({ agent: "worker", prompt: "p" })).rejects.toThrow(
        PRE,
      )
      expect(env.originals.length).toBe(0)
    }
  })

  test("unknown source and target quota with subscription-only billing keeps the default primary", async () => {
    const { env, inst } = await setup(CREDITS)
    env.quota.anthropic = "unknownquota"
    env.quota.openai = "unknownquota"
    const result = await inst.run({ agent: "worker", prompt: "p" })
    expect(env.originals[0].input).toEqual({ agent: "worker", prompt: "p" })
    expect(result.metadata).toEqual({
      sessionID: "ses_child",
      status: "completed",
    })
    expect(marker(env).fallback).toBe(false)
    expect(marker(env).funding).toBe("included")
    expect(marker(env).allowUnknownQuota).toBe(true)
    await sendAnthropic(inst)
  })

  test("unknown source with an available target falls back to the target, with or without source credits", async () => {
    for (const credits of [false, true]) {
      const { env, inst } = await setup(CREDITS)
      env.quota.anthropic = "unknownquota"
      env.credits.anthropic = credits
      await inst.run({ agent: "worker", prompt: "p" })
      expect(env.originals[0].input.model).toBe(sel(SOL_LOW))
      expect(marker(env).fallback).toBe(true)
      expect(marker(env).funding).toBe("included")
      expect(marker(env).allowUnknownQuota).toBe(false)
    }
  })

  test("a failed marker write for a credits launch still happens before the prompt", async () => {
    const { env, inst } = await setup(CREDITS)
    bothExhausted(env, true, false)
    env.failUpdate = true
    await expect(inst.run({ agent: "worker", prompt: "p" })).rejects.toThrow(
      /update rejected/,
    )
    expect(env.originals.length).toBe(1)
    expect(env.events.includes("prompt")).toBe(false)
  })

  test("an included-funded child stops when quota is exhausted even with positive credits", async () => {
    const { env, inst } = await setup(CREDITS)
    await launch(inst)
    env.now += 16_000
    env.quota.anthropic = "exhausted"
    env.credits.anthropic = true
    await expect(sendAnthropic(inst)).rejects.toThrow(
      /no mid-task switch to credits/,
    )
  })

  test("an available included quota accepts either credit state", async () => {
    for (const credits of [false, true]) {
      const { env, inst } = await setup(CREDITS)
      await launch(inst)
      env.now += 16_000
      env.credits.anthropic = credits
      await sendAnthropic(inst)
    }
  })

  test("unknown quota continues only for a default marker with subscription-only billing", async () => {
    const ok = await setup(CREDITS)
    await launch(ok.inst)
    ok.env.now += 16_000
    ok.env.quota.anthropic = "unknownquota"
    await sendAnthropic(ok.inst)

    const paid = await setup(CREDITS)
    await launch(paid.inst)
    paid.env.now += 16_000
    paid.env.quota.anthropic = "unknownquota"
    paid.env.credits.anthropic = true
    await expect(sendAnthropic(paid.inst)).rejects.toThrow(PRE)

    const alt = await fallbackChild()
    await alt.inst.fire("context", ctxEvent(text(10)))
    alt.env.now += 16_000
    alt.env.quota.openai = "unknownquota"
    await expect(
      alt.inst.fire("http.request", {
        ...scope(SOL_LOW),
        request: OPENAI_REQ(),
      }),
    ).rejects.toThrow(PRE)
  })

  test("a credits child runs with fresh credits and exhausted quota; transport guards still apply", async () => {
    const { env, inst } = await setup(CREDITS)
    bothExhausted(env, true, false)
    await launch(inst)
    await sendAnthropic(inst)
    await expect(
      inst.fire("http.request", {
        ...scope(SONNET_LOW),
        request: post(ANTHROPIC_URL, bearer("fixture-wrong")),
      }),
    ).rejects.toThrow(PRE)
    await expect(
      inst.fire("http.request", {
        ...scope(SONNET_LOW),
        request: post(
          "https://evil.example/v1/messages",
          bearer("fixture-anthropic"),
        ),
      }),
    ).rejects.toThrow(PRE)
  })

  test("an alternate credits child keeps the first-context and wire-size limits", async () => {
    const big = await setup(CREDITS)
    bothExhausted(big.env, false, true)
    await launch(big.inst)
    await expect(
      big.inst.fire("context", ctxEvent(text(MAX_CONTEXT_BYTES))),
    ).rejects.toThrow(PRE)

    const wire = await setup(CREDITS)
    bothExhausted(wire.env, false, true)
    await launch(wire.inst)
    await wire.inst.fire("context", ctxEvent(text(10)))
    await expect(
      wire.inst.fire("http.request", {
        ...scope(SOL_LOW),
        request: OPENAI_REQ("x".repeat(MAX_CONTEXT_BYTES + 1)),
      }),
    ).rejects.toThrow(/wire context exceeds conservative headroom/)
    expect(marker(wire.env).wireChecked === undefined).toBe(true)
    await wire.inst.fire("http.request", {
      ...scope(SOL_LOW),
      request: OPENAI_REQ("{}"),
    })
    expect(marker(wire.env).wireChecked).toBe(true)
  })

  test("a credits child with no credits remaining stops", async () => {
    const { env, inst } = await setup(CREDITS)
    bothExhausted(env, true, false)
    await launch(inst)
    env.now += 16_000
    env.credits.anthropic = false
    await expect(sendAnthropic(inst)).rejects.toThrow(
      /last-resort credits are no longer available/,
    )
  })

  test("a credits child may continue on fresh included quota after reset", async () => {
    const { env, inst } = await setup(CREDITS)
    bothExhausted(env, true, false)
    await launch(inst)
    env.now += 16_000
    env.credits.anthropic = false
    env.quota.anthropic = "available"
    await sendAnthropic(inst)
  })

  test("a credits child is stopped when the operator disables credits in a later setup", async () => {
    const env = makeEnv()
    const first = await install(env, CREDITS)
    bothExhausted(env, true, false)
    await launch(first)
    await first.cleanup()
    const off = await install(env, { enabled: true })
    await expect(sendAnthropic(off)).rejects.toThrow(/disabled by the operator/)
  })
})

describe("auxiliary funding guards and expired resets", () => {
  const CREDITS = { enabled: true, creditsLastResort: true }
  const NOSWITCH = /no mid-task switch to credits/
  const WS_URL = "wss://chatgpt.com/backend-api/codex/responses"
  const OPENAI_HEADERS = bearer("fixture-openai", {
    "chatgpt-account-id": "fixture-account",
  })
  const openaiReq = () =>
    new Request(CODEX_URL, {
      method: "POST",
      headers: OPENAI_HEADERS,
      body: "{}",
    })
  const anthropicReq = () => post(ANTHROPIC_URL, bearer("fixture-anthropic"))
  const snapshot = (env: Env) => {
    const s = env.sessions.get("ses_child")
    return JSON.stringify([s?.metadata, s?.model, s?.agent])
  }
  const creditsChild = async () => {
    const s = await setup(CREDITS)
    s.env.quota.anthropic = "exhausted"
    s.env.quota.openai = "exhausted"
    s.env.credits.anthropic = true
    await launch(s.inst)
    expect(marker(s.env).funding).toBe("credits")
    s.env.now += 16_000
    return s
  }

  test("a credits child rejects cross-provider aux with unknown quota even when credits are available (HTTP and WS)", async () => {
    const { env, inst } = await creditsChild()
    env.quota.openai = "unknownquota"
    env.credits.openai = true
    const before = snapshot(env)
    const updates = env.updates
    for (const kind of ["title", "generate"]) {
      await expect(
        inst.fire("http.request", {
          ...scope(SOL_LOW, kind),
          request: openaiReq(),
        }),
      ).rejects.toThrow(NOSWITCH)
      await expect(
        inst.fire("experimental.ws.handshake", {
          ...scope(SOL_LOW, kind),
          url: WS_URL,
          headers: OPENAI_HEADERS,
        }),
      ).rejects.toThrow(NOSWITCH)
      await expect(
        inst.fire("experimental.ws.send", {
          ...scope(SOL_LOW, kind),
          frame: "{}",
        }),
      ).rejects.toThrow(PRE)
    }
    expect(snapshot(env)).toBe(before)
    expect(env.updates).toBe(updates)
    expect(env.originals.length).toBe(1)
  })

  test("a credits child rejects cross-provider aux with exhausted quota and credits", async () => {
    const { env, inst } = await creditsChild()
    env.credits.openai = true
    await expect(
      inst.fire("http.request", {
        ...scope(SOL_LOW, "title"),
        request: openaiReq(),
      }),
    ).rejects.toThrow(NOSWITCH)
  })

  test("a credits child allows cross-provider aux with known available quota, marker unchanged", async () => {
    const { env, inst } = await creditsChild()
    env.quota.openai = "available"
    env.credits.openai = true
    const before = snapshot(env)
    const updates = env.updates
    for (const kind of ["title", "generate"]) {
      await inst.fire("http.request", {
        ...scope(SOL_LOW, kind),
        request: openaiReq(),
      })
      await inst.fire("experimental.ws.handshake", {
        ...scope(SOL_LOW, kind),
        url: WS_URL,
        headers: OPENAI_HEADERS,
      })
      await inst.fire("experimental.ws.send", {
        ...scope(SOL_LOW, kind),
        frame: "{}",
      })
    }
    expect(snapshot(env)).toBe(before)
    expect(env.updates).toBe(updates)
    expect(env.originals.length).toBe(1)
  })

  test("a default child with unknown quota allows only its own primary request", async () => {
    const { env, inst } = await setup()
    env.quota.anthropic = "unknownquota"
    env.quota.openai = "unknownquota"
    await launch(inst)
    expect(marker(env).allowUnknownQuota).toBe(true)
    expect(marker(env).funding).toBe("included")
    const before = snapshot(env)
    await inst.fire("http.request", {
      ...scope(SONNET_LOW),
      request: anthropicReq(),
    })
    const opus = {
      providerID: "anthropic",
      id: "claude-opus-5-5",
      variant: "high",
    }
    const rejected: Array<[ModelRef, string, () => Request]> = [
      [SOL_LOW, "title", openaiReq],
      [SOL_LOW, "generate", openaiReq],
      [opus, "title", anthropicReq],
      [opus, "primary", anthropicReq],
      [SONNET_LOW, "title", anthropicReq],
      [SONNET_LOW, "generate", anthropicReq],
    ]
    for (const [model, kind, request] of rejected)
      await expect(
        inst.fire("http.request", {
          ...scope(model, kind),
          request: request(),
        }),
      ).rejects.toThrow(PRE)
    expect(snapshot(env)).toBe(before)
    expect(env.originals.length).toBe(1)
  })

  test("WebSocket: only the primary binding may proceed on unknown quota; aux handshakes and frames are rejected", async () => {
    const { env, inst } = await setup()
    env.quota.anthropic = "unknownquota"
    env.quota.openai = "unknownquota"
    await launch(inst, "verifier")
    expect(marker(env).allowUnknownQuota).toBe(true)
    await inst.fire("experimental.ws.handshake", {
      ...scope(LUNA_LOW),
      url: WS_URL,
      headers: OPENAI_HEADERS,
    })
    await inst.fire("experimental.ws.send", { ...scope(LUNA_LOW), frame: "{}" })
    const auxModels: ModelRef[] = [LUNA_LOW, SOL_LOW, SONNET_LOW]
    for (const model of auxModels) {
      await expect(
        inst.fire("experimental.ws.handshake", {
          ...scope(model, "title"),
          url: WS_URL,
          headers: OPENAI_HEADERS,
        }),
      ).rejects.toThrow(PRE)
      await expect(
        inst.fire("experimental.ws.send", {
          ...scope(model, "title"),
          frame: "{}",
        }),
      ).rejects.toThrow(PRE)
    }
    await expect(
      inst.fire("experimental.ws.handshake", {
        ...scope(SOL_LOW),
        url: WS_URL,
        headers: OPENAI_HEADERS,
      }),
    ).rejects.toThrow(PRE)
  })

  test("an expired exhausted reset in a cached proof is unknown: default admission and transport agree", async () => {
    const { env, inst } = await setup()
    env.quota.anthropic = "exhausted"
    env.resetMs = 1_000
    env.quota.openai = "unknownquota"
    await expect(inst.run({ agent: "worker", prompt: "p" })).rejects.toThrow(
      PRE,
    )
    expect(env.originals.length).toBe(0)
    const anthropicReads = () =>
      env.fetchURLs.filter((u) => u.includes("anthropic")).length
    const cached = anthropicReads()
    env.now += 1_500
    await inst.run({ agent: "worker", prompt: "p" })
    expect(anthropicReads()).toBe(cached)
    expect(env.originals.length).toBe(1)
    expect(env.originals[0].input).toEqual({ agent: "worker", prompt: "p" })
    expect(marker(env).fallback).toBe(false)
    expect(marker(env).funding).toBe("included")
    expect(marker(env).allowUnknownQuota).toBe(true)
    await inst.fire("http.request", {
      ...scope(SONNET_LOW),
      request: anthropicReq(),
    })
    expect(anthropicReads()).toBe(cached)
    // Aux requests never get the unknown-quota exception.
    await expect(
      inst.fire("http.request", {
        ...scope(SONNET_LOW, "title"),
        request: anthropicReq(),
      }),
    ).rejects.toThrow(PRE)
  })
})

describe("marker write failure", () => {
  test("a rejected marker update fails after one original call, with no prompt and no protected child", async () => {
    const { env, inst } = await setup()
    env.failUpdate = true
    await expect(inst.run({ agent: "worker", prompt: "p" })).rejects.toThrow(
      /update rejected/,
    )
    expect(env.originals.length).toBe(1)
    expect(env.events.includes("prompt")).toBe(false)
    expect(marker(env)).toBeUndefined()
    expect(env.fetchURLs.every((u) => u.includes("usage"))).toBe(true)
  })
})

describe("parser diagnostic rpc", () => {
  const rpcSetup = async (options: Record<string, unknown>) => {
    const env = makeEnv()
    const seen: { definition?: any; handlers?: any } = {}
    let reads = 0
    for (const id of ["anthropic", "openai"] as const) {
      const value = env.connection[id]
      Object.defineProperty(env.connection, id, {
        get() {
          reads++
          return value
        },
      })
    }
    const inst = await install(env, options, {
      register: async (definition: any, handlers: any) => {
        seen.definition = definition
        seen.handlers = handlers
        return { dispose: async () => {} }
      },
    })
    env.fetchURLs.length = 0
    reads = 0
    return { env, inst, seen, reads: () => reads }
  }

  test("method shape is exported", async () => {
    const { seen } = await rpcSetup({ enabled: false })
    const m = seen.definition.methods.inspectParser
    expect(m.input.additionalProperties).toBe(false)
    expect(m.output.required).toEqual(["revision", "belowLimit", "atLimit"])
    expect(m.output.properties.revision.enum).toEqual([
      "anthropic-opaque-window-v2",
    ])
    expect(typeof seen.handlers.inspectParser).toBe("function")
  })

  test("disabled diagnostics reject without fetch or auth", async () => {
    const { env, seen, reads } = await rpcSetup({ enabled: false })
    await expect(seen.handlers.inspectParser({})).rejects.toThrow(
      /parser diagnostics are disabled/,
    )
    expect(env.fetchURLs).toEqual([])
    expect(reads()).toBe(0)
    expect(env.sessions.size).toBe(1)
  })

  test("enabled diagnostics are synthetic and API-free", async () => {
    const { env, seen, reads } = await rpcSetup({
      enabled: false,
      allowDiagnostics: true,
    })
    const expected = {
      revision: "anthropic-opaque-window-v2",
      belowLimit: "available",
      atLimit: "unknown",
    }
    expect(await seen.handlers.inspectParser({})).toEqual(expected)
    expect(await seen.handlers.inspectParser({})).toEqual(expected)
    expect(env.fetchURLs).toEqual([])
    expect(reads()).toBe(0)
    expect(env.sessions.size).toBe(1)
    await seen.handlers.inspectQuota({})
    await seen.handlers.inspectQuota({})
    expect(env.fetchURLs.filter((u) => u.includes("anthropic"))).toHaveLength(1)
    expect(env.fetchURLs.filter((u) => u.includes("chatgpt"))).toHaveLength(1)
  })
})

describe("anthropic quota diagnostic rpc", () => {
  const rpcSetup = async (
    options: Record<string, unknown>,
    openaiThrows = false,
  ) => {
    const env = makeEnv()
    const seen: { definition?: any; handlers?: any } = {}
    const reads = { anthropic: 0, openai: 0 }
    for (const id of ["anthropic", "openai"] as const) {
      const value = env.connection[id]
      Object.defineProperty(env.connection, id, {
        get() {
          reads[id]++
          if (id === "openai" && openaiThrows)
            throw new Error("openai must not be resolved")
          return value
        },
      })
    }
    const inst = await install(env, options, {
      register: async (definition: any, handlers: any) => {
        seen.definition = definition
        seen.handlers = handlers
        return { dispose: async () => {} }
      },
    })
    env.fetchURLs.length = 0
    reads.anthropic = 0
    reads.openai = 0
    return { env, inst, seen, reads }
  }
  const count = (env: { fetchURLs: string[] }, name: string) =>
    env.fetchURLs.filter((u) => u.includes(name)).length

  test("method shape is exported", async () => {
    const { seen } = await rpcSetup({ enabled: false })
    const m = seen.definition.methods.inspectAnthropicQuota
    expect(m.input.additionalProperties).toBe(false)
    expect(m.output).toBe(
      seen.definition.methods.inspectQuota.output.properties.anthropic,
    )
    expect(typeof seen.handlers.inspectAnthropicQuota).toBe("function")
  })

  test("disabled opt-in rejects without fetch, auth read or session updates", async () => {
    const { env, seen, reads } = await rpcSetup({ enabled: false })
    await expect(seen.handlers.inspectAnthropicQuota({})).rejects.toThrow(
      /usage diagnostics are disabled/,
    )
    expect(env.fetchURLs).toEqual([])
    expect(reads.anthropic + reads.openai).toBe(0)
    expect(env.sessions.size).toBe(1)
  })

  test("single-provider method issues one Anthropic GET, never touches OpenAI, and memoizes", async () => {
    const { env, seen, reads } = await rpcSetup(
      { enabled: false, allowDiagnostics: true },
      true,
    )
    await seen.handlers.inspectAnthropicQuota({})
    await seen.handlers.inspectAnthropicQuota({})
    expect(count(env, "anthropic")).toBe(1)
    expect(count(env, "chatgpt")).toBe(0)
    expect(reads.openai).toBe(0)
  })

  test("aggregate after single calls OpenAI once and Anthropic not again", async () => {
    const { env, seen } = await rpcSetup({
      enabled: false,
      allowDiagnostics: true,
    })
    await seen.handlers.inspectAnthropicQuota({})
    await seen.handlers.inspectQuota({})
    await seen.handlers.inspectQuota({})
    expect(count(env, "anthropic")).toBe(1)
    expect(count(env, "chatgpt")).toBe(1)
  })

  test("single after aggregate adds no further GET", async () => {
    const { env, seen } = await rpcSetup({
      enabled: false,
      allowDiagnostics: true,
    })
    await seen.handlers.inspectQuota({})
    await seen.handlers.inspectAnthropicQuota({})
    expect(count(env, "anthropic")).toBe(1)
    expect(count(env, "chatgpt")).toBe(1)
  })
})
