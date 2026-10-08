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
const SONNET = ROUTES.worker.primary
const SOL = ROUTES.worker.alternate
const LUNA = ROUTES.verifier.primary
const sel = (m: ModelRef) =>
  `${m.providerID}/${m.id}${m.variant ? `#${m.variant}` : ""}`
const modelFrom = (s: string): ModelRef => {
  const [providerID, rest] = s.split("/")
  const [id, variant] = rest.split("#")
  return { providerID, id, ...(variant ? { variant } : {}) }
}
const catalog = (): CatalogModel[] => {
  const models = new Map<string, CatalogModel>()
  for (const route of Object.values(ROUTES))
    for (const m of [route.primary, route.alternate]) {
      const key = `${m.providerID}/${m.id}`
      const item = models.get(key) ?? {
        ...m,
        enabled: true,
        status: "active",
        capabilities: { tools: true },
        variants: [],
        limit: { context: 400_000, output: 32_000 },
      }
      if (m.variant && !item.variants.some((v) => v.id === m.variant))
        item.variants.push({ id: m.variant })
      models.set(key, item)
    }
  return [...models.values()]
}
type Session = {
  id: string
  parentID?: string
  agent?: string
  model?: ModelRef
  metadata?: Record<string, unknown>
  location: typeof LOCATION
}

async function fixture() {
  const env = {
    now: NOW,
    version: SUPPORTED_VERSION,
    reads: 0,
    fetchedAt: undefined as number | undefined,
    path: "",
    unavailable: false,
    quota: { anthropic: 90, openai: 90 } as Record<string, number | undefined>,
    connection: {
      anthropic: { type: "credential", id: "fixture-claude", method: "oauth" },
      openai: { type: "credential", id: "fixture-chatgpt", method: "oauth" },
    } as Record<string, any>,
    access: {
      anthropic: "fixture-anthropic",
      openai: "fixture-openai",
    } as Record<string, string>,
    childID: "ses_child",
    childParent: "ses_parent",
    childModel: undefined as ModelRef | undefined,
    progress: "normal" as "normal" | "noid" | "none" | "wrongid",
    failUpdate: false,
    hasTool: true,
    catalog: catalog(),
    updates: 0,
    registered: 0,
    disposed: 0,
    prompted: false,
    originals: [] as Record<string, any>[],
    agents: Object.fromEntries(
      Object.entries(ROUTES).map(([k, r]) => [k, r.primary]),
    ) as Record<string, ModelRef>,
    sessions: new Map<string, Session>([
      ["ses_parent", { id: "ses_parent", agent: "build", location: LOCATION }],
    ]),
  }
  const install = async (
    options: Record<string, unknown> = {
      enabled: true,
      creditsLastResort: true,
      quotaExportPath: "/fixture/quota-export.json",
    },
  ) => {
    const hooks: Record<string, ((e: any) => Promise<void>)[]> = {}
    const reg = () => {
      env.registered++
      return {
        dispose: async () => {
          env.disposed++
        },
      }
    }
    const tool = {
      execute: async (
        input: Record<string, any>,
        context: any,
      ): Promise<any> => {
        env.originals.push(input)
        const continuing = typeof input.sessionID === "string"
        const id = continuing ? input.sessionID : env.childID
        if (continuing) {
          if (env.sessions.get(id)?.parentID !== context.sessionID)
            throw new Error("native parent mismatch")
        } else
          env.sessions.set(id, {
            id,
            parentID: env.childParent,
            agent: input.agent,
            model:
              env.childModel ??
              (typeof input.model === "string"
                ? modelFrom(input.model)
                : env.agents[input.agent]),
            location: LOCATION,
            metadata: { keep: true },
          })
        if (env.progress !== "none")
          await context.progress(
            env.progress === "noid"
              ? { status: "running" }
              : {
                  sessionID: env.progress === "wrongid" ? "ses_other" : id,
                  status: "running",
                },
          )
        env.prompted = true
        return {
          output: {
            sessionID: id,
            status: input.background ? "running" : "completed",
          },
          content: "done",
          metadata: { sessionID: id },
        }
      },
    }
    const ctx: RuntimeContext = {
      app: {
        get version() {
          return env.version
        },
      },
      options,
      agent: {
        get: async ({ agentID }) => ({ data: { model: env.agents[agentID] } }),
      },
      model: { list: async () => ({ data: env.catalog }) },
      provider: {
        get: async ({ providerID }) => ({
          data: { package: `@opencode/ai/providers/${providerID}` },
        }),
      },
      integration: {
        connection: {
          active: async (id) => env.connection[id],
          resolve: async (c) => {
            const id = c.id === "fixture-claude" ? "anthropic" : "openai"
            return {
              type: "oauth",
              methodID: id === "anthropic" ? "claude-max" : "chatgpt-browser",
              access: env.access[id],
              metadata: { accountID: "fixture-account" },
            }
          },
        },
      },
      session: {
        get: async ({ sessionID }) => {
          const s = env.sessions.get(sessionID)
          if (!s) throw new Error("missing session")
          return s
        },
        update: async ({ sessionID, metadata }) => {
          if (env.failUpdate) throw new Error("update rejected")
          env.updates++
          env.sessions.get(sessionID)!.metadata = metadata
        },
        hook: async (name, cb) => {
          ;(hooks[name] ??= []).push(cb as any)
          return reg()
        },
      },
      tool: {
        transform: async (cb) => {
          cb({
            get: () => (env.hasTool ? tool : undefined),
            update: (_id, update) => update(tool),
          })
          return reg()
        },
      },
    }
    const cleanup = await setupPreflight(ctx, {
      now: () => env.now,
      readExport: async (path) => {
        env.reads++
        env.path = path
        if (env.unavailable) throw new Error("fixture export unavailable")
        return JSON.stringify({
          version: 2,
          providers: Object.fromEntries(
            Object.entries(env.quota).map(([id, percent]) => [
              id,
              {
                status: "ok",
                fetchedAt: (env.fetchedAt ?? env.now) / 1000,
                entries:
                  percent === undefined
                    ? []
                    : ["5h", "Weekly"].map((window) => ({
                        window,
                        sourceId:
                          id === "anthropic"
                            ? "fixture-claude"
                            : "fixture-chatgpt",
                        resultType: id === "openai" ? "rate_limit" : "quota",
                        authority: "provider_reported",
                        acquisitionMethod: "remote_api",
                        renderType: "percent",
                        percentRemaining: window === "5h" ? percent : 90,
                        resetAt: env.now / 1000 + 3600,
                      })),
              },
            ]),
          ),
        })
      },
    })
    return {
      cleanup,
      run: (
        input: Record<string, any> = {
          agent: "worker",
          prompt: "fixture",
          background: true,
        },
        signal = new AbortController().signal,
      ) =>
        tool.execute(input, {
          sessionID: "ses_parent",
          id: "fixture-call",
          signal,
          progress: async () => {
            if (env.failUpdate) throw new Error("update rejected")
            if (
              typeof input.sessionID !== "string" &&
              input.model === undefined &&
              Object.hasOwn(ROUTES, input.agent) &&
              env.agents[input.agent] === ROUTES[input.agent]?.primary &&
              options.enabled
            )
              expect(
                env.sessions.get(env.childID)?.metadata?.[METADATA_KEY],
              ).toBeDefined()
          },
        }),
      fire: async (name: string, event: any) => {
        for (const hook of hooks[name] ?? []) await hook(event)
        return event
      },
    }
  }
  return { env, install, inst: await install() }
}
type Inst = Awaited<ReturnType<typeof fixture>>["inst"]
const marker = (env: Awaited<ReturnType<typeof fixture>>["env"]) =>
  env.sessions.get("ses_child")?.metadata?.[METADATA_KEY] as any
const scope = (model = SONNET, kind = "primary", sessionID = "ses_child") => ({
  model,
  kind,
  sessionID,
})
const A_URL = "https://api.anthropic.com/v1/messages?beta=true"
const O_URL = "https://chatgpt.com/backend-api/codex/responses"
const WS_URL = "wss://chatgpt.com/backend-api/codex/responses"
const headers = (provider = "anthropic") => ({
  authorization: `Bearer fixture-${provider}`,
  ...(provider === "openai" ? { "chatgpt-account-id": "fixture-account" } : {}),
})
const post = (
  url = A_URL,
  h: Record<string, string> = headers(),
  body = "{}",
) => new Request(url, { method: "POST", headers: h, body })
const send = (inst: Inst, request = post(), model = SONNET, kind = "primary") =>
  inst.fire("http.request", { ...scope(model, kind), request })
const context = (size = 10, media = false) => ({
  ...scope(SOL),
  system: [],
  messages: [
    { content: [{ type: media ? "image" : "text", text: "x".repeat(size) }] },
  ],
  options: {},
})
const fallback = async () => {
  const f = await fixture()
  f.env.quota.anthropic = 0
  await f.inst.run()
  return f
}

describe("launch and persistence", () => {
  test("reads one public export per new launch and preserves default/background/structured output", async () => {
    const { env, inst } = await fixture()
    const input = { agent: "worker", prompt: "fixture", background: true }
    const result = await inst.run(input)
    expect(env.originals[0]).toBe(input)
    expect(env.reads).toBe(1)
    expect(env.path).toBe("/fixture/quota-export.json")
    expect(result.output).toEqual({ sessionID: "ses_child", status: "running" })
    expect(result.content).toBe("done")
    expect(marker(env).model).toEqual(SONNET)
    expect(env.sessions.get("ses_child")!.metadata!.keep).toBe(true)
  })
  test("0% source and available alternate injects only the pinned alternate", async () => {
    const f = await fallback()
    expect(f.env.originals[0]).toEqual({
      agent: "worker",
      prompt: "fixture",
      background: true,
      model: sel(SOL),
    })
    expect(marker(f.env).fallback).toBe(true)
    expect(f.env.reads).toBe(1)
  })
  test("missing file or source information keeps the default rather than stopping", async () => {
    for (const mode of ["missing-file", "source"]) {
      const { env, inst } = await fixture()
      if (mode === "missing-file") env.unavailable = true
      else env.quota.anthropic = undefined
      await inst.run()
      expect(env.originals[0].model).toBeUndefined()
      expect(marker(env).fallback).toBe(false)
    }
  })
  test("an empty default with unknown alternate data still prefers the alternate", async () => {
    const { env, inst } = await fixture()
    env.quota.anthropic = 0
    env.quota.openai = undefined
    await inst.run()
    expect(env.originals[0].model).toBe(sel(SOL))
    expect(marker(env).fallback).toBe(true)
  })
  test("a stale export keeps an empty window reliable until its reset", async () => {
    const { env, inst } = await fixture()
    env.quota.anthropic = 0
    // Observed an hour ago; its reset is still in the future.
    env.fetchedAt = env.now
    env.now += 60 * 60_000
    await inst.run()
    expect(env.originals[0].model).toBe(sel(SOL))
  })
  test("both 0% tries the default provider without claiming a credit balance", async () => {
    const { env, inst } = await fixture()
    env.quota.anthropic = env.quota.openai = 0
    const result = await inst.run()
    expect(env.originals[0].model).toBeUndefined()
    expect(result.metadata.preflight.funding).toBe("provider")
    expect(result.content).toContain("provider-managed credits")
    expect(result.content).not.toContain("authorized")
  })
  test("creditsLastResort=false still denies the both-empty launch", async () => {
    const { env, install } = await fixture()
    env.quota.anthropic = env.quota.openai = 0
    const inst = await install({ enabled: true, creditsLastResort: false })
    await expect(inst.run()).rejects.toThrow(/credits are disabled/)
    expect(env.originals).toHaveLength(0)
  })
  test("explicit model, unknown role, changed default and disabled selection bypass JSON", async () => {
    for (const mode of ["explicit", "unknown", "changed", "disabled"]) {
      const { env, inst, install } = await fixture()
      if (mode === "changed") env.agents.worker = { ...SONNET, variant: "high" }
      const active =
        mode === "disabled" ? await install({ enabled: false }) : inst
      const input = {
        agent: mode === "unknown" ? "not-a-role" : "worker",
        ...(mode === "explicit" ? { model: sel(SOL) } : {}),
      }
      await active.run(input)
      expect(env.originals[0]).toBe(input)
      expect(env.reads).toBe(0)
      expect(marker(env)).toBeUndefined()
    }
  })
  test("wrong child identity/model, failed marker and irregular progress cannot prompt", async () => {
    for (const mode of ["parent", "model", "noid", "wrongid", "update"]) {
      const { env, inst } = await fixture()
      if (mode === "parent") env.childParent = "ses_foreign"
      if (mode === "model") env.childModel = SOL
      if (mode === "noid" || mode === "wrongid") env.progress = mode
      if (mode === "update") env.failUpdate = true
      await expect(inst.run()).rejects.toThrow()
      expect(env.prompted).toBe(false)
    }
  })
  test("missing native pre-launch progress raises an invariant alarm", async () => {
    const { env, inst } = await fixture()
    env.progress = "none"
    await expect(inst.run()).rejects.toThrow(
      /did not await pre-launch registration/,
    )
  })
  test("cancelled launch and unsupported version stop before original", async () => {
    const { env, inst } = await fixture()
    const c = new AbortController()
    c.abort()
    await expect(inst.run({ agent: "worker" }, c.signal)).rejects.toThrow()
    env.version = "unsupported"
    await expect(inst.run()).rejects.toThrow(/unsupported OpenCode version/)
    expect(env.originals).toHaveLength(0)
    await inst.run({ agent: "worker", model: sel(SOL) })
    expect(env.originals).toHaveLength(1)
  })
  test("setup failure disposes all previously registered hooks", async () => {
    const { env, install } = await fixture()
    const before = env.registered
    env.hasTool = false
    await expect(install()).rejects.toThrow(
      /builtin subagent executor unavailable/,
    )
    expect(env.disposed).toBe(env.registered - before)
  })
  test("continuation preserves role/model with no JSON read even after completion or reload", async () => {
    const { env, inst, install } = await fixture()
    await inst.run({ agent: "worker" })
    const m = marker(env)
    // Old markers retain identity/context protection, not obsolete funding gates.
    Object.assign(m, { funding: "credits", allowUnknownQuota: false })
    await inst.cleanup()
    const again = await install({ enabled: false })
    env.unavailable = true
    await again.run({ agent: "worker", sessionID: "ses_child" })
    expect(env.reads).toBe(1)
    expect(marker(env)).toBe(m)
    for (const change of [
      { agent: "reviewer" },
      { agent: "worker", model: sel(SOL) },
    ])
      await expect(
        again.run({ sessionID: "ses_child", ...change }),
      ).rejects.toThrow(/protected continuations/)
    await send(again)
    expect(env.reads).toBe(1)
  })
  test("ordinary and foreign continuations leave parent checks to native tool", async () => {
    const { env, inst } = await fixture()
    env.sessions.set("ses_plain", {
      id: "ses_plain",
      parentID: "ses_parent",
      location: LOCATION,
    })
    await inst.run({ agent: "worker", sessionID: "ses_plain" })
    env.sessions.get("ses_plain")!.parentID = "ses_other"
    await expect(
      inst.run({ agent: "worker", sessionID: "ses_plain" }),
    ).rejects.toThrow(/native parent mismatch/)
    expect(env.reads).toBe(0)
  })
})

describe("HTTP/WS identity protection without quota rechecks", () => {
  test("quota exhaustion/errors mid-task do not read JSON or stop approved requests", async () => {
    const { env, inst } = await fixture()
    await inst.run()
    env.now += 24 * 3600_000
    env.unavailable = true
    env.quota.anthropic = 0
    for (const kind of ["primary", "title", "compaction", "generate"])
      await send(inst, post(), SONNET, kind)
    expect(env.reads).toBe(1)
    expect(env.originals).toHaveLength(1)
    expect(marker(env).model).toEqual(SONNET)
  })
  test("HTTP denies wrong routes, tokens, keys, method, redirect hosts and child models", async () => {
    const { env, inst } = await fixture()
    await inst.run()
    const bad = [
      post("https://api.openai.com/v1/responses"),
      post("https://evil.example/v1/messages"),
      post(A_URL, { authorization: "Bearer wrong" }),
      post(A_URL, { ...headers(), "x-api-key": "fixture" }),
      new Request(A_URL, { headers: headers() }),
      post("https://user:pass@api.anthropic.com/v1/messages"),
      post("https://api.anthropic.com/v1/messages?unexpected=true"),
    ]
    for (const request of bad)
      await expect(send(inst, request)).rejects.toThrow(/Subagent preflight/)
    const event = await send(inst)
    expect(event.request.redirect).toBe("error")
    env.sessions.get("ses_child")!.model = SOL
    await expect(send(inst)).rejects.toThrow(/model changed/)
  })
  test("changed account and unsupported version are still rejected", async () => {
    const { env, inst } = await fixture()
    await inst.run()
    env.connection.anthropic.id = "another-login"
    await expect(send(inst)).rejects.toThrow(/account changed|unavailable/)
    env.connection.anthropic.id = "fixture-claude"
    env.version = "unsupported"
    await expect(send(inst)).rejects.toThrow(/unsupported/)
  })
  test("root and inherited markers are outside child protection", async () => {
    const { env, inst } = await fixture()
    await inst.run()
    env.sessions.get("ses_parent")!.metadata = { [METADATA_KEY]: marker(env) }
    env.sessions.set("ses_nested", {
      id: "ses_nested",
      parentID: "ses_child",
      location: LOCATION,
      metadata: { [METADATA_KEY]: marker(env) },
    })
    for (const id of ["ses_parent", "ses_nested"])
      await inst.fire("http.request", {
        ...scope(SONNET, "primary", id),
        request: post("https://evil.example"),
      })
  })
  test("ChatGPT account headers, auxiliary routes and model allowlist stay guarded", async () => {
    const { inst } = await fixture()
    await inst.run({ agent: "verifier" })
    await send(inst, post(O_URL, headers("openai")), LUNA)
    await expect(
      send(
        inst,
        post(O_URL, { ...headers("openai"), "chatgpt-account-id": "wrong" }),
        LUNA,
      ),
    ).rejects.toThrow(/account mismatch/)
    await send(
      inst,
      post(`${O_URL}/compact`, headers("openai")),
      LUNA,
      "compaction",
    )
    await expect(
      send(inst, post(`${O_URL}/compact`, headers("openai")), LUNA, "title"),
    ).rejects.toThrow()
    await expect(
      send(
        inst,
        post(O_URL, headers("openai")),
        { ...LUNA, id: "unapproved" },
        "title",
      ),
    ).rejects.toThrow(/unapproved auxiliary/)
  })
  test("WebSocket requires approved handshake, identity, host and unchanged credential", async () => {
    const { env, inst } = await fixture()
    await inst.run({ agent: "verifier" })
    const frame = { ...scope(LUNA), frame: "{}" }
    await expect(inst.fire("experimental.ws.send", frame)).rejects.toThrow(
      /handshake/,
    )
    for (const item of [
      { url: "wss://evil.example", headers: headers("openai") },
      {
        url: WS_URL,
        headers: { ...headers("openai"), authorization: "wrong" },
      },
      {
        url: WS_URL,
        headers: { ...headers("openai"), "x-api-key": "fixture" },
      },
    ])
      await expect(
        inst.fire("experimental.ws.handshake", { ...scope(LUNA), ...item }),
      ).rejects.toThrow()
    await inst.fire("experimental.ws.handshake", {
      ...scope(LUNA),
      url: WS_URL,
      headers: headers("openai"),
    })
    env.unavailable = true
    env.quota.openai = 0
    await inst.fire("experimental.ws.send", frame)
    expect(env.reads).toBe(1)
    env.access.openai = "rotated"
    await expect(inst.fire("experimental.ws.send", frame)).rejects.toThrow(
      /handshake/,
    )
  })
  test("reload retains guards without requiring quota or billing data", async () => {
    const { env, inst, install } = await fixture()
    await inst.run()
    await inst.cleanup()
    env.unavailable = true
    const again = await install()
    await send(again)
    await expect(
      send(again, post(A_URL, { authorization: "wrong" })),
    ).rejects.toThrow()
    expect(env.reads).toBe(1)
  })
})

describe("alternate context and wire safeguards", () => {
  test("context must be text-only, measurable, within byte and catalog headroom", async () => {
    for (const mode of ["media", "bytes", "catalog", "tools"]) {
      const { env, inst } = await fallback()
      if (mode === "catalog")
        env.catalog = env.catalog.map((m) => ({
          ...m,
          limit: { ...m.limit, input: 32_000 },
        }))
      const e = context(
        mode === "bytes" ? MAX_CONTEXT_BYTES : 10,
        mode === "media",
      )
      if (mode === "tools")
        Object.assign(e, {
          tools: [{ description: "x".repeat(MAX_CONTEXT_BYTES) }],
        })
      await expect(inst.fire("context", e)).rejects.toThrow()
      expect(marker(env).launchChecked).toBeUndefined()
    }
  })
  test("primary transmission requires context check, then wire-size check exactly once", async () => {
    const { env, inst } = await fallback()
    await expect(
      send(inst, post(O_URL, headers("openai")), SOL),
    ).rejects.toThrow(/not checked/)
    await inst.fire("context", context())
    expect(marker(env).launchChecked).toBe(true)
    await expect(
      send(
        inst,
        post(O_URL, headers("openai"), "x".repeat(MAX_CONTEXT_BYTES + 1)),
        SOL,
      ),
    ).rejects.toThrow(/wire context/)
    expect(marker(env).wireChecked).toBeUndefined()
    await send(inst, post(O_URL, headers("openai")), SOL)
    expect(marker(env).wireChecked).toBe(true)
    const updates = env.updates
    await send(
      inst,
      post(O_URL, headers("openai"), "x".repeat(MAX_CONTEXT_BYTES + 1)),
      SOL,
    )
    await inst.fire("context", context(MAX_CONTEXT_BYTES + 1))
    expect(env.updates).toBe(updates)
  })
  test("WS wire frames also have launch headroom checks", async () => {
    const { env, inst } = await fallback()
    await inst.fire("context", context())
    await inst.fire("experimental.ws.handshake", {
      ...scope(SOL),
      url: WS_URL,
      headers: headers("openai"),
    })
    await expect(
      inst.fire("experimental.ws.send", {
        ...scope(SOL),
        frame: "x".repeat(MAX_CONTEXT_BYTES + 1),
      }),
    ).rejects.toThrow(/wire context/)
    await inst.fire("experimental.ws.send", { ...scope(SOL), frame: "{}" })
    expect(marker(env).wireChecked).toBe(true)
  })
  test("auxiliary requests skip wire size, and persisted checks survive reload", async () => {
    const { env, inst, install } = await fallback()
    await inst.fire("context", context())
    await send(
      inst,
      post(O_URL, headers("openai"), "x".repeat(MAX_CONTEXT_BYTES)),
      SOL,
      "title",
    )
    expect(marker(env).wireChecked).toBeUndefined()
    await send(inst, post(O_URL, headers("openai")), SOL)
    await inst.cleanup()
    const again = await install()
    await send(
      again,
      post(O_URL, headers("openai"), "x".repeat(MAX_CONTEXT_BYTES)),
      SOL,
    )
    expect(env.reads).toBe(1)
  })
})

test("quota/long retry is denied for protected children without resubmit/model switch", async () => {
  const { env, inst } = await fixture()
  await inst.run()
  for (const [type, delay, sessionID, expected] of [
    ["provider.quota", 1000, "ses_child", false],
    ["provider.rate-limit", 18_000_000, "ses_child", false],
    ["provider.rate-limit", 2000, "ses_child", true],
    ["provider.quota", 18_000_000, "ses_parent", true],
  ] as const) {
    const e = await inst.fire("retry", {
      sessionID,
      error: { type, message: "fixture" },
      decision: { retry: true, delay },
    })
    expect(e.decision.retry).toBe(expected)
  }
  expect(env.originals).toHaveLength(1)
  expect(env.reads).toBe(1)
})
