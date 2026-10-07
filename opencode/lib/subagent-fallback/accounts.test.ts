import { describe, expect, test } from "bun:test"
import {
  QuotaReader,
  subscription,
  type AccountsContext,
  type Subscription,
} from "./accounts"

const NOW = 1_710_000_000_000
const USAGE_URLS = [
  "https://api.anthropic.com/api/oauth/usage",
  "https://chatgpt.com/backend-api/wham/usage",
]
const iso = (ms: number) => new Date(NOW + ms).toISOString()

const anthropicBody = (exhausted = false) => ({
  five_hour: { utilization: exhausted ? 100 : 10, resets_at: iso(3_600_000) },
  seven_day: { utilization: 20, resets_at: iso(86_400_000) },
  extra_usage: { is_enabled: false },
  limits: [],
})
const openaiBody = (exhausted = false) => ({
  plan_type: "plus",
  credits: { has_credits: false, unlimited: false, balance: "0" },
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
})

type Cred = {
  connection: any
  oauth: any
  pkg?: string
  integrationID?: string
}
function makeCtx(
  overrides: { anthropic?: Partial<Cred>; openai?: Partial<Cred> } = {},
) {
  const state: Record<string, Cred> = {
    anthropic: {
      connection: { type: "credential", id: "fixture-claude", method: "oauth" },
      oauth: {
        type: "oauth",
        methodID: "claude-max",
        access: "fixture-anthropic",
        metadata: { accountID: "fixture-account" },
      },
      ...overrides.anthropic,
    },
    openai: {
      connection: {
        type: "credential",
        id: "fixture-chatgpt",
        method: "oauth",
      },
      oauth: {
        type: "oauth",
        methodID: "chatgpt-browser",
        access: "fixture-openai",
        metadata: { accountID: "fixture-account" },
      },
      ...overrides.openai,
    },
  }
  const resolved: string[] = []
  const ctx: AccountsContext = {
    provider: {
      get: async ({ providerID }) => ({
        data: {
          package:
            state[providerID].pkg ?? `@opencode/ai/providers/${providerID}`,
          integrationID: state[providerID].integrationID ?? providerID,
        },
      }),
    },
    integration: {
      connection: {
        active: async (providerID) => state[providerID].connection,
        resolve: async (connection) => {
          resolved.push(connection.id ?? "")
          return Object.values(state).find((s) => s.connection === connection)
            ?.oauth
        },
      },
    },
  }
  return { ctx, state, resolved }
}

const makeCtxByConnection = makeCtx

const anthropicAuth: Subscription = {
  proof: {
    connectionID: "fixture-claude",
    providerID: "anthropic",
    methodID: "claude-max",
    type: "oauth",
  },
  access: "fixture-anthropic",
  accountID: "fixture-account",
}
const openaiAuth: Subscription = {
  proof: {
    connectionID: "fixture-chatgpt",
    providerID: "openai",
    methodID: "chatgpt-browser",
    type: "oauth",
  },
  access: "fixture-openai",
  accountID: "fixture-account",
}
const SONNET = {
  providerID: "anthropic",
  id: "claude-sonnet-5-5",
  variant: "low",
}
const SOL = { providerID: "openai", id: "gpt-6.1-sol", variant: "low" }

function makeReader(
  responder?: (url: string, call: number) => Response | Promise<Response>,
) {
  const clock = { now: NOW }
  const calls: Array<{ url: string; init: RequestInit }> = []
  const fetchFake = (async (input: any, init?: RequestInit) => {
    const url = String(input)
    calls.push({ url, init: init ?? {} })
    if (responder) return responder(url, calls.length)
    return Response.json(
      url.includes("anthropic") ? anthropicBody() : openaiBody(),
    )
  }) as unknown as typeof fetch
  const reader = new QuotaReader({ fetch: fetchFake, now: () => clock.now })
  return { reader, calls, clock }
}
const live = () => new AbortController().signal

describe("subscription", () => {
  test("accepts approved native OAuth connections", async () => {
    const { ctx } = makeCtxByConnection()
    const a = await subscription(ctx, "anthropic")
    const o = await subscription(ctx, "openai")
    expect(a?.proof).toEqual({
      connectionID: "fixture-claude",
      providerID: "anthropic",
      methodID: "claude-max",
      type: "oauth",
    })
    expect(a?.access === "fixture-anthropic").toBe(true)
    expect(o?.proof.connectionID).toBe("fixture-chatgpt")
    expect(o?.accountID === "fixture-account").toBe(true)
  })

  test("accepts both ChatGPT OAuth methods", async () => {
    for (const methodID of ["chatgpt-browser", "chatgpt-headless"]) {
      const { ctx } = makeCtxByConnection({
        openai: {
          oauth: {
            type: "oauth",
            methodID,
            access: "fixture-openai",
            metadata: { accountID: "fixture-account" },
          },
        },
      })
      expect((await subscription(ctx, "openai"))?.proof.methodID).toBe(methodID)
    }
  })

  test("rejects unsupported providers", async () => {
    const { ctx } = makeCtxByConnection()
    expect(await subscription(ctx, "google")).toBeUndefined()
  })

  test("rejects non-native provider package or integration", async () => {
    expect(
      await subscription(
        makeCtxByConnection({ anthropic: { pkg: "@ai-sdk/anthropic" } }).ctx,
        "anthropic",
      ),
    ).toBeUndefined()
    expect(
      await subscription(
        makeCtxByConnection({ openai: { integrationID: "other" } }).ctx,
        "openai",
      ),
    ).toBeUndefined()
  })

  test("rejects API-key, env and non-OAuth connections without resolving credentials", async () => {
    for (const connection of [
      { type: "env", id: "fixture-claude", method: "oauth" },
      { type: "credential", id: "fixture-claude", method: "api" },
      { type: "credential", method: "oauth" },
      undefined,
    ]) {
      const env = makeCtxByConnection({ anthropic: { connection } })
      expect(await subscription(env.ctx, "anthropic")).toBeUndefined()
      expect(env.resolved.length).toBe(0)
    }
  })

  test("rejects non-oauth credentials, missing access, and unapproved OAuth methods", async () => {
    const bad = [
      { type: "api", access: "fixture-anthropic", methodID: "claude-max" },
      { type: "oauth", methodID: "claude-max" },
      { type: "oauth", access: "fixture-anthropic", methodID: "console-api" },
      { type: "oauth", access: "fixture-anthropic" },
    ]
    for (const oauth of bad)
      expect(
        await subscription(
          makeCtxByConnection({ anthropic: { oauth } }).ctx,
          "anthropic",
        ),
      ).toBeUndefined()
    expect(
      await subscription(
        makeCtxByConnection({
          openai: {
            oauth: {
              type: "oauth",
              methodID: "claude-max",
              access: "fixture-openai",
              metadata: { accountID: "fixture-account" },
            },
          },
        }).ctx,
        "openai",
      ),
    ).toBeUndefined()
  })

  test("requires an OpenAI account ID", async () => {
    for (const metadata of [
      undefined,
      {},
      { accountID: "" },
      { accountID: 7 },
    ]) {
      const oauth = {
        type: "oauth",
        methodID: "chatgpt-browser",
        access: "fixture-openai",
        metadata,
      }
      expect(
        await subscription(
          makeCtxByConnection({ openai: { oauth } }).ctx,
          "openai",
        ),
      ).toBeUndefined()
    }
  })

  test("does not touch auth files, Keychain, or credential environment variables", async () => {
    const before = Object.keys(process.env).sort().join(",")
    const { ctx } = makeCtxByConnection()
    await subscription(ctx, "anthropic")
    expect(Object.keys(process.env).sort().join(",")).toBe(before)
  })
})

describe("QuotaReader", () => {
  test("only issues whitelisted GET requests with redirect error and OAuth headers", async () => {
    const { reader, calls } = makeReader()
    expect((await reader.read(anthropicAuth, SONNET, live())).state).toBe(
      "available",
    )
    expect((await reader.read(openaiAuth, SOL, live())).state).toBe("available")
    expect(calls.map((c) => c.url)).toEqual(USAGE_URLS)
    for (const call of calls) {
      expect(call.init.method).toBe("GET")
      expect(call.init.redirect).toBe("error")
      expect(call.init.body === undefined).toBe(true)
    }
    const a = new Headers(calls[0].init.headers)
    expect(a.get("authorization") === "Bearer fixture-anthropic").toBe(true)
    expect(a.get("anthropic-beta")).toBe("oauth-2025-04-20")
    expect(a.has("chatgpt-account-id")).toBe(false)
    const o = new Headers(calls[1].init.headers)
    expect(o.get("authorization") === "Bearer fixture-openai").toBe(true)
    expect(o.get("chatgpt-account-id") === "fixture-account").toBe(true)
    expect(o.has("anthropic-beta")).toBe(false)
  })

  test("reports exhaustion with a future reset", async () => {
    const { reader } = makeReader((url) =>
      Response.json(
        url.includes("anthropic") ? anthropicBody(true) : openaiBody(true),
      ),
    )
    const a = await reader.read(anthropicAuth, SONNET, live())
    expect(a.state).toBe("exhausted")
    expect(a.resetAt! > NOW).toBe(true)
    expect((await reader.read(openaiAuth, SOL, live())).state).toBe("exhausted")
  })

  test("repeated and concurrent callers for different models share one request", async () => {
    const { reader, calls } = makeReader()
    const [a, b] = await Promise.all([
      reader.read(anthropicAuth, SONNET, live()),
      reader.read(
        anthropicAuth,
        { providerID: "anthropic", id: "claude-opus-5-5" },
        live(),
      ),
    ])
    expect(a.state).toBe("available")
    expect(b.state).toBe("available")
    await reader.read(anthropicAuth, SONNET, live())
    expect(calls.length).toBe(1)
  })

  test("cache expires and changed account identity invalidates it", async () => {
    const { reader, calls, clock } = makeReader()
    await reader.read(anthropicAuth, SONNET, live())
    clock.now += 14_000
    await reader.read(anthropicAuth, SONNET, live())
    expect(calls.length).toBe(1)
    clock.now += 1_001
    await reader.read(anthropicAuth, SONNET, live())
    expect(calls.length).toBe(2)
    await reader.read(
      { ...anthropicAuth, access: "fixture-anthropic-2" },
      SONNET,
      live(),
    )
    expect(calls.length).toBe(3)
    await reader.read(
      { ...anthropicAuth, accountID: "fixture-account-2" },
      SONNET,
      live(),
    )
    expect(calls.length).toBe(4)
    await reader.read(
      {
        ...anthropicAuth,
        proof: { ...anthropicAuth.proof, connectionID: "fixture-claude-2" },
      },
      SONNET,
      live(),
    )
    expect(calls.length).toBe(5)
  })

  test("provider 429, 500 and malformed JSON become unknown, never exhausted", async () => {
    const responders: Array<() => Response> = [
      () => new Response("{}", { status: 429 }),
      () => new Response("{}", { status: 500 }),
      () => new Response("not json", { status: 200 }),
      () => Response.json({ unexpected: true }),
    ]
    for (const responder of responders) {
      const { reader } = makeReader(responder)
      const proof = await reader.read(anthropicAuth, SONNET, live())
      expect(proof.state).toBe("unknown")
      expect(proof.observedAt).toBe(NOW)
    }
  })

  test("unknown results use a short cache and are retried", async () => {
    let status = 500
    const { reader, calls, clock } = makeReader((url) =>
      status === 500
        ? new Response("{}", { status })
        : Response.json(anthropicBody()),
    )
    expect((await reader.read(anthropicAuth, SONNET, live())).state).toBe(
      "unknown",
    )
    await reader.read(anthropicAuth, SONNET, live())
    expect(calls.length).toBe(1)
    status = 200
    clock.now += 1_001
    expect((await reader.read(anthropicAuth, SONNET, live())).state).toBe(
      "available",
    )
    expect(calls.length).toBe(2)
  })

  test("fetch throws are suppressed and do not leak token or account fields", async () => {
    const { reader } = makeReader(() => {
      throw new Error("boom fixture-anthropic fixture-account")
    })
    const proof = await reader.read(anthropicAuth, SONNET, live())
    expect(proof.state).toBe("unknown")
    expect(Object.keys(proof).sort()).toEqual(["observedAt", "state"])
    const text = JSON.stringify(proof)
    expect(
      text.includes("fixture-anthropic") || text.includes("fixture-account"),
    ).toBe(false)
  })

  test("API response errors and echoed fields do not leak into quota", async () => {
    const { reader } = makeReader(() =>
      Response.json({
        ...anthropicBody(),
        access_token: "fixture-anthropic",
        account_id: "fixture-account",
      }),
    )
    const proof = await reader.read(anthropicAuth, SONNET, live())
    const text = JSON.stringify(proof)
    expect(
      text.includes("fixture-anthropic") || text.includes("fixture-account"),
    ).toBe(false)
    const bad = makeReader(
      () => new Response("fixture-anthropic fixture-account", { status: 401 }),
    )
    const unknown = JSON.stringify(
      await bad.reader.read(anthropicAuth, SONNET, live()),
    )
    expect(
      unknown.includes("fixture-anthropic") ||
        unknown.includes("fixture-account"),
    ).toBe(false)
  })

  test("unsupported models and provider mismatches are unknown", async () => {
    const { reader, calls } = makeReader()
    expect(
      (
        await reader.read(
          anthropicAuth,
          { providerID: "anthropic", id: "claude-unknown-9" },
          live(),
        )
      ).state,
    ).toBe("unknown")
    expect((await reader.read(anthropicAuth, SOL, live())).state).toBe(
      "unknown",
    )
    expect(
      (
        await reader.read(
          {
            ...anthropicAuth,
            proof: { ...anthropicAuth.proof, providerID: "google" },
          },
          SONNET,
          live(),
        )
      ).state,
    ).toBe("unknown")
    expect(calls.every((c) => USAGE_URLS.includes(c.url))).toBe(true)
  })

  const anthropicCredits = (over: Record<string, unknown> = {}) => ({
    ...anthropicBody(),
    extra_usage: {
      is_enabled: true,
      utilization: 10,
      monthly_limit: 100,
      used_credits: 10,
      ...over,
    },
  })
  const openaiCredits = (over: Record<string, unknown> = {}) => ({
    ...openaiBody(),
    credits: { has_credits: true, unlimited: false, balance: "10", ...over },
  })

  test("credit and paid fields do not affect the quota parse (read)", async () => {
    const a = makeReader(() => Response.json(anthropicCredits()))
    expect((await a.reader.read(anthropicAuth, SONNET, live())).state).toBe(
      "available",
    )
    const o = makeReader(() => Response.json(openaiCredits()))
    expect((await o.reader.read(openaiAuth, SOL, live())).state).toBe(
      "available",
    )
    const ax = makeReader(() =>
      Response.json({
        ...anthropicBody(true),
        extra_usage: anthropicCredits().extra_usage,
      }),
    )
    expect((await ax.reader.read(anthropicAuth, SONNET, live())).state).toBe(
      "exhausted",
    )
    const ox = makeReader(() =>
      Response.json({ ...openaiBody(true), credits: openaiCredits().credits }),
    )
    expect((await ox.reader.read(openaiAuth, SOL, live())).state).toBe(
      "exhausted",
    )
  })

  test("inspect returns independent quota and billing proofs", async () => {
    const cases: Array<[string, any, string, string]> = [
      ["anthropic", anthropicBody(), "available", "subscription_only"],
      ["anthropic", anthropicCredits(), "available", "credits_available"],
      [
        "anthropic",
        anthropicCredits({ used_credits: 100 }),
        "available",
        "paid_risk",
      ],
      [
        "anthropic",
        { ...anthropicBody(), extra_usage: undefined },
        "available",
        "unknown",
      ],
      [
        "anthropic",
        { ...anthropicBody(true), extra_usage: { is_enabled: false } },
        "exhausted",
        "subscription_only",
      ],
      ["openai", openaiBody(), "available", "subscription_only"],
      ["openai", openaiCredits(), "available", "credits_available"],
      ["openai", openaiCredits({ balance: "0" }), "available", "paid_risk"],
      [
        "openai",
        { ...openaiBody(), credits: undefined },
        "available",
        "unknown",
      ],
      [
        "openai",
        { ...openaiBody(), rate_limit: undefined },
        "unknown",
        "subscription_only",
      ],
      [
        "openai",
        {
          ...anthropicBody(),
          five_hour: undefined,
          extra_usage: { is_enabled: false },
        },
        "unknown",
        "unknown",
      ],
    ]
    for (const [provider, body, quota, billing] of cases) {
      const { reader } = makeReader(() => Response.json(body))
      const auth = provider === "anthropic" ? anthropicAuth : openaiAuth
      const model = provider === "anthropic" ? SONNET : SOL
      const usage = await reader.inspect(auth, model, live())
      expect(usage.quota.state).toBe(quota)
      expect(usage.billing.state).toBe(billing)
      expect((await reader.read(auth, model, live())).state).toBe(quota)
    }
  })

  test("inspect failures leave both proofs unknown", async () => {
    const { reader } = makeReader(() => new Response("{}", { status: 500 }))
    const usage = await reader.inspect(anthropicAuth, SONNET, live())
    expect(usage.quota.state).toBe("unknown")
    expect(usage.billing.state).toBe("unknown")
    expect(usage.billing.observedAt).toBe(NOW)
  })

  test("inspect and read treat opaque scope below 100 as available, at 100 as unknown", async () => {
    const scoped = (percent: number) => ({
      ...anthropicBody(),
      limits: [
        {
          kind: "weekly_scoped",
          percent,
          resets_at: iso(3_600_000),
          scope: { model: { id: null, display_name: "fixture-label" } },
        },
      ],
    })
    for (const [percent, quota] of [
      [50, "available"],
      [100, "unknown"],
    ] as const) {
      const { reader, calls } = makeReader(() => Response.json(scoped(percent)))
      const usage = await reader.inspect(anthropicAuth, SONNET, live())
      expect(usage.quota.state).toBe(quota)
      expect(usage.billing.state).toBe("subscription_only")
      expect((await reader.read(anthropicAuth, SONNET, live())).state).toBe(
        quota,
      )
      expect(calls.length).toBe(1)
    }
  })

  test("inspect and read use one GET for real-shape shared limits", async () => {
    const entry = (kind: string, percent: number, scope: unknown) => ({
      kind,
      percent,
      resets_at: iso(3_600_000),
      scope,
      is_active: true,
    })
    const body = (sessionPercent: number) => ({
      ...anthropicCredits(),
      limits: [
        entry("session", sessionPercent, null),
        entry("weekly_all", 20, null),
        entry("weekly_scoped", 50, { model: { id: null } }),
      ],
    })
    for (const [percent, quota] of [
      [10, "available"],
      [100, "exhausted"],
    ] as const) {
      const { reader, calls } = makeReader(() => Response.json(body(percent)))
      const usage = await reader.inspect(anthropicAuth, SONNET, live())
      expect(usage.quota.state).toBe(quota)
      expect(usage.billing.state).toBe("credits_available")
      expect((await reader.read(anthropicAuth, SONNET, live())).state).toBe(
        quota,
      )
      expect(calls.length).toBe(1)
    }
  })

  test("read and inspect share a single GET", async () => {
    const { reader, calls } = makeReader(() =>
      Response.json(anthropicCredits()),
    )
    const [quota, usage] = await Promise.all([
      reader.read(anthropicAuth, SONNET, live()),
      reader.inspect(anthropicAuth, SONNET, live()),
    ])
    expect(quota.state).toBe("available")
    expect(usage.billing.state).toBe("credits_available")
    expect(calls.length).toBe(1)
    expect(USAGE_URLS.includes(calls[0].url)).toBe(true)
    expect(calls[0].init.method).toBe("GET")
  })

  test("price metadata never infers a paid route; billing carries only state and timestamps", async () => {
    const body = anthropicCredits()
    const priced = {
      ...body,
      extra_usage: {
        ...body.extra_usage,
        price_per_credit: "0.01",
        currency: "USD",
      },
      pricing: { per_credit: "0.01" },
    }
    const { reader } = makeReader(() => Response.json(priced))
    const usage = await reader.inspect(anthropicAuth, SONNET, live())
    expect(usage.billing.state).toBe("credits_available")
    expect(
      Object.keys(usage.billing).every((k) =>
        ["state", "observedAt", "reason"].includes(k),
      ),
    ).toBe(true)
    expect(JSON.stringify(usage).includes("0.01")).toBe(false)
    const o = makeReader(() =>
      Response.json({ ...openaiCredits(), pricing: { per_credit: "0.01" } }),
    )
    const ousage = await o.reader.inspect(openaiAuth, SOL, live())
    expect(ousage.billing.state).toBe("credits_available")
    expect(JSON.stringify(ousage).includes("0.01")).toBe(false)
  })

  test("an already-aborted caller is rejected", async () => {
    const { reader } = makeReader()
    const controller = new AbortController()
    controller.abort()
    await expect(
      reader.read(anthropicAuth, SONNET, controller.signal),
    ).rejects.toThrow()
  })

  test("cancelling one caller does not cancel another sharing the probe", async () => {
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    const { reader, calls } = makeReader(async () => {
      await gate
      return Response.json(anthropicBody())
    })
    const a = new AbortController()
    const b = new AbortController()
    const first = reader.read(anthropicAuth, SONNET, a.signal)
    const second = reader.read(anthropicAuth, SONNET, b.signal)
    const firstResult = first.then(
      () => "resolved",
      (e: Error) => e.name,
    )
    a.abort()
    release()
    expect(await firstResult).toBe("AbortError")
    expect((await second).state).toBe("available")
    expect(calls.length).toBe(1)
  })
})
