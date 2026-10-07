import { describe, expect, test } from "bun:test"
import type { AccountsContext } from "./accounts"
import { diagnoseQuota, explainAnthropic, explainOpenAI } from "./diagnostics"

const NOW = 1_710_000_000_000
const iso = (ms: number) => new Date(NOW + ms).toISOString()
const URLS = {
  anthropic: "https://api.anthropic.com/api/oauth/usage",
  openai: "https://chatgpt.com/backend-api/wham/usage",
}
const FAKES = ["fixture-access", "fixture-account", "fixture-connection"]

const anthropicBody = (over: Record<string, unknown> = {}) => ({
  five_hour: { utilization: 10, resets_at: iso(3_600_000) },
  seven_day: { utilization: 20, resets_at: iso(86_400_000) },
  extra_usage: { is_enabled: false },
  limits: [],
  ...over,
})
const openaiBody = (exhausted = false, over: Record<string, unknown> = {}) => ({
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
  ...over,
})

function makeCtx(valid = true): AccountsContext {
  const make = (providerID: string, methodID: string) => {
    const connection = {
      type: "credential",
      id: "fixture-connection",
      method: "oauth",
    }
    return { providerID, connection, methodID }
  }
  const byProvider: Record<string, ReturnType<typeof make>> = {
    anthropic: make("anthropic", "claude-max"),
    openai: make("openai", "chatgpt-browser"),
  }
  return {
    provider: {
      get: async ({ providerID }) => ({
        data: {
          package: `@opencode/ai/providers/${providerID}`,
          integrationID: providerID,
        },
      }),
    },
    integration: {
      connection: {
        active: async (providerID) =>
          valid ? byProvider[providerID].connection : undefined,
        resolve: async (connection) => {
          const hit = Object.values(byProvider).find(
            (p) => p.connection === connection,
          )!
          return {
            type: "oauth",
            methodID: hit.methodID,
            access: "fixture-access",
            metadata: { accountID: "fixture-account" },
          }
        },
      },
    },
  }
}

function makeDeps(respond: () => Response | Promise<Response>, now = NOW) {
  const calls: { url: string; init: RequestInit }[] = []
  const deps = {
    now: () => now,
    fetch: (async (url: string, init: RequestInit) => {
      calls.push({ url: String(url), init })
      return respond()
    }) as unknown as typeof fetch,
  }
  return { deps, calls }
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status })
const leaks = (r: unknown) => {
  const s = JSON.stringify(r)
  return FAKES.some((f) => s.includes(f))
}

describe("diagnoseQuota accepted proofs", () => {
  test("anthropic available", async () => {
    const { deps, calls } = makeDeps(() => json(anthropicBody()))
    const r = await diagnoseQuota(makeCtx(), "anthropic", deps)
    expect(r).toEqual({
      outcome: "proof_accepted",
      status: 200,
      state: "available",
      billingState: "subscription_only",
      limitShapes: [],
    })
    expect(calls).toHaveLength(1)
    expect(calls[0].url).toBe(URLS.anthropic)
    expect(calls[0].init.method).toBe("GET")
    expect(calls[0].init.redirect).toBe("error")
    expect(calls[0].init.signal instanceof AbortSignal).toBe(true)
    const h = new Headers(calls[0].init.headers)
    expect(h.get("authorization") === "Bearer fixture-access").toBe(true)
    expect(h.get("anthropic-beta")).toBe("oauth-2025-04-20")
    expect(leaks(r)).toBe(false)
  })

  test("anthropic exhausted", async () => {
    const { deps } = makeDeps(() =>
      json(
        anthropicBody({
          five_hour: { utilization: 100, resets_at: iso(3_600_000) },
        }),
      ),
    )
    const r = await diagnoseQuota(makeCtx(), "anthropic", deps)
    expect(r).toEqual({
      outcome: "proof_accepted",
      status: 200,
      state: "exhausted",
      billingState: "subscription_only",
      limitShapes: [],
    })
    expect(leaks(r)).toBe(false)
  })

  test("openai available", async () => {
    const { deps, calls } = makeDeps(() => json(openaiBody()))
    const r = await diagnoseQuota(makeCtx(), "openai", deps)
    expect(r).toEqual({
      outcome: "proof_accepted",
      status: 200,
      state: "available",
      billingState: "subscription_only",
    })
    expect(calls).toHaveLength(1)
    expect(calls[0].url).toBe(URLS.openai)
    expect(calls[0].init.redirect).toBe("error")
    const h = new Headers(calls[0].init.headers)
    expect(h.get("chatgpt-account-id") === "fixture-account").toBe(true)
    expect(leaks(r)).toBe(false)
  })

  test("openai exhausted", async () => {
    const { deps } = makeDeps(() => json(openaiBody(true)))
    const r = await diagnoseQuota(makeCtx(), "openai", deps)
    expect(r).toEqual({
      outcome: "proof_accepted",
      status: 200,
      state: "exhausted",
      billingState: "subscription_only",
    })
  })

  test("available quota with credits_available is accepted with one GET and no purchase request", async () => {
    const a = makeDeps(() =>
      json(
        anthropicBody({
          extra_usage: {
            is_enabled: true,
            utilization: 10,
            monthly_limit: 100,
            used_credits: 10,
          },
        }),
      ),
    )
    expect(await diagnoseQuota(makeCtx(), "anthropic", a.deps)).toEqual({
      outcome: "proof_accepted",
      status: 200,
      state: "available",
      billingState: "credits_available",
      limitShapes: [],
    })
    const o = makeDeps(() =>
      json(
        openaiBody(false, {
          credits: { has_credits: true, unlimited: false, balance: "10" },
        }),
      ),
    )
    expect(await diagnoseQuota(makeCtx(), "openai", o.deps)).toEqual({
      outcome: "proof_accepted",
      status: 200,
      state: "available",
      billingState: "credits_available",
    })
    for (const { calls } of [a, o]) {
      expect(calls).toHaveLength(1)
      expect(calls[0].init.method).toBe("GET")
      expect(calls[0].init.body === undefined).toBe(true)
    }
  })

  test("extra_usage enabled without bounded credit fields is no longer a quota reject", async () => {
    const { deps } = makeDeps(() =>
      json(anthropicBody({ extra_usage: { is_enabled: true } })),
    )
    expect(await diagnoseQuota(makeCtx(), "anthropic", deps)).toEqual({
      outcome: "proof_accepted",
      status: 200,
      state: "available",
      billingState: "unknown",
      limitShapes: [],
    })
  })

  test("missing credits info leaves billing unknown but quota accepted", async () => {
    const o = makeDeps(() => json(openaiBody(false, { credits: undefined })))
    expect(await diagnoseQuota(makeCtx(), "openai", o.deps)).toEqual({
      outcome: "proof_accepted",
      status: 200,
      state: "available",
      billingState: "unknown",
    })
    const a = makeDeps(() => json(anthropicBody({ extra_usage: undefined })))
    expect(await diagnoseQuota(makeCtx(), "anthropic", a.deps)).toEqual({
      outcome: "proof_accepted",
      status: 200,
      state: "available",
      billingState: "unknown",
      limitShapes: [],
    })
  })

  test("a recognized openai spend_control is accepted as subscription_only", async () => {
    const { deps } = makeDeps(() =>
      json(
        openaiBody(false, {
          spend_control: { reached: false, individual_limit: null },
        }),
      ),
    )
    expect(await diagnoseQuota(makeCtx(), "openai", deps)).toEqual({
      outcome: "proof_accepted",
      status: 200,
      state: "available",
      billingState: "subscription_only",
    })
  })
})

describe("diagnoseQuota failures", () => {
  for (const status of [401, 403, 429, 500]) {
    test(`http ${status} does not read body`, async () => {
      let touched = false
      const { deps, calls } = makeDeps(() => {
        const res = new Response("secret-body", { status })
        res.json = async () => {
          touched = true
          return {}
        }
        res.text = async () => {
          touched = true
          return ""
        }
        return res
      })
      const r = await diagnoseQuota(makeCtx(), "anthropic", deps)
      expect(r).toEqual({ outcome: "http_error", status })
      expect(touched).toBe(false)
      expect(calls).toHaveLength(1)
    })
  }

  test("timeout, redirect and network errors return only enums", async () => {
    const cases: [unknown, string][] = [
      [
        Object.assign(new Error("Bearer fixture-access"), {
          name: "TimeoutError",
        }),
        "timeout",
      ],
      [new TypeError("redirect fixture-access"), "transport_or_redirect_error"],
      [new Error("ECONNRESET fixture-account"), "transport_or_redirect_error"],
    ]
    for (const [err, outcome] of cases) {
      const { deps, calls } = makeDeps(() => {
        throw err
      })
      const r = await diagnoseQuota(makeCtx(), "openai", deps)
      expect(r).toEqual({ outcome } as any)
      expect(calls).toHaveLength(1)
      expect(leaks(r)).toBe(false)
    }
  })

  test("bad JSON", async () => {
    const { deps } = makeDeps(() => new Response("not json fixture-access"))
    const r = await diagnoseQuota(makeCtx(), "anthropic", deps)
    expect(r).toEqual({ outcome: "json_decode_error", status: 200 })
    expect(leaks(r)).toBe(false)
  })

  test("invalid account performs no fetch", async () => {
    const { deps, calls } = makeDeps(() => json({}))
    const r = await diagnoseQuota(makeCtx(false), "anthropic", deps)
    expect(r).toEqual({ outcome: "account_unavailable" })
    expect(calls).toHaveLength(0)
  })

  test("account getter throw is account_unavailable", async () => {
    const ctx = makeCtx()
    ctx.provider.get = async () => {
      throw new Error("fixture-access")
    }
    const { deps, calls } = makeDeps(() => json({}))
    const r = await diagnoseQuota(ctx, "openai", deps)
    expect(r).toEqual({ outcome: "account_unavailable" })
    expect(calls).toHaveLength(0)
  })
})

describe("diagnoseQuota parser rejects", () => {
  const reject = async (
    provider: "anthropic" | "openai",
    body: unknown,
  ): Promise<string[]> => {
    const { deps, calls } = makeDeps(() => json(body))
    const r = await diagnoseQuota(makeCtx(), provider, deps)
    expect(r.outcome).toBe("parser_reject")
    expect(r.status).toBe(200)
    expect(calls).toHaveLength(1)
    expect(leaks(r)).toBe(false)
    return r.reasons!
  }

  test("anthropic missing window", async () => {
    expect(
      await reject("anthropic", anthropicBody({ seven_day: undefined })),
    ).toEqual(["seven_day_window_missing"])
  })

  test("anthropic nullable and invalid resets", async () => {
    expect(
      await reject(
        "anthropic",
        anthropicBody({
          five_hour: { utilization: 10, resets_at: null },
          seven_day: { utilization: 20, resets_at: iso(-1000) },
        }),
      ),
    ).toEqual(["five_hour_reset_null", "seven_day_reset_not_future"])
  })

  test("anthropic non-array limits are unsupported", async () => {
    expect(await reject("anthropic", anthropicBody({ limits: {} }))).toEqual([
      "limits_unsupported",
    ])
  })

  test("anthropic opaque limits scope is model_scope_unverified with known billing", async () => {
    const wild = {
      kind: "weekly_scoped",
      percent: 100,
      resets_at: iso(3_600_000),
      scope: { model: { id: "fixture-wild-model" } },
    }
    const { deps, calls } = makeDeps(() =>
      json(anthropicBody({ limits: [wild] })),
    )
    const r = await diagnoseQuota(makeCtx(), "anthropic", deps)
    expect(r.outcome).toBe("parser_reject")
    expect(r.reasons).toEqual([
      "model_scope_unverified",
      "scoped_window_exhaustion_unverified",
    ])
    expect(r.billingState).toBe("subscription_only")
    expect(calls).toHaveLength(1)
    expect(JSON.stringify(r).includes("fixture-wild-model")).toBe(false)
    expect(leaks(r)).toBe(false)
  })

  test("anthropic malformed scoped windows yield fixed unique codes", () => {
    const good = {
      kind: "weekly_scoped",
      percent: 50,
      resets_at: iso(3_600_000),
      scope: { model: { id: null } },
    }
    const explain = (entry: unknown) =>
      explainAnthropic(anthropicBody({ limits: [entry] }), NOW)
    expect(explain(good)).toEqual(["model_scope_unverified"])
    expect(explain("fixture-raw")).toEqual([
      "model_scope_unverified",
      "scoped_window_shape_invalid",
    ])
    expect(explain({ ...good, kind: "other" })).toEqual([
      "model_scope_unverified",
      "scoped_window_shape_invalid",
    ])
    expect(explain({ ...good, percent: Number.NaN })).toEqual([
      "model_scope_unverified",
      "scoped_window_percent_invalid",
    ])
    expect(explain({ ...good, resets_at: null })).toEqual([
      "model_scope_unverified",
      "scoped_window_reset_null",
    ])
    expect(explain({ ...good, resets_at: undefined })).toEqual([
      "model_scope_unverified",
      "scoped_window_reset_missing",
    ])
    expect(explain({ ...good, resets_at: 5 })).toEqual([
      "model_scope_unverified",
      "scoped_window_reset_wrong_type",
    ])
    expect(explain({ ...good, resets_at: "fixture-bad" })).toEqual([
      "model_scope_unverified",
      "scoped_window_reset_unparseable",
    ])
    expect(explain({ ...good, resets_at: iso(-1000) })).toEqual([
      "model_scope_unverified",
      "scoped_window_reset_not_future",
    ])
    expect(explain({ ...good, scope: { model: { id: 7 } } })).toEqual([
      "model_scope_unverified",
      "scoped_window_scope_invalid",
    ])
    expect(explain({ ...good, scope: "fixture-scope" })).toEqual([
      "model_scope_unverified",
      "scoped_window_scope_invalid",
    ])
    expect(
      explainAnthropic(
        anthropicBody({
          limits: [
            { ...good, percent: 100 },
            { ...good, percent: 100, scope: { model: { id: "" } } },
          ],
        }),
        NOW,
      ),
    ).toEqual(["model_scope_unverified", "scoped_window_exhaustion_unverified"])
  })

  test("anthropic real-shape limits are accepted with kind and type-only snapshot", async () => {
    const mk = (kind: string, scope: unknown) => ({
      kind,
      percent: 10,
      resets_at: iso(3_600_000),
      scope,
      is_active: true,
    })
    const limits = [
      mk("session", null),
      mk("weekly_all", null),
      mk("weekly_scoped", { model: { id: null } }),
    ]
    const { deps, calls } = makeDeps(() => json(anthropicBody({ limits })))
    const r = await diagnoseQuota(makeCtx(), "anthropic", deps)
    const fields = {
      kind: "string",
      percent: "number",
      resets_at: "string",
      scope: "null",
      is_active: "boolean",
    }
    expect(r).toEqual({
      outcome: "proof_accepted",
      status: 200,
      state: "available",
      billingState: "subscription_only",
      limitShapes: [
        { kind: "session", fields },
        { kind: "weekly_all", fields },
        {
          kind: "weekly_scoped",
          fields: { ...fields, scope: "object" },
        },
      ],
    })
    expect(calls).toHaveLength(1)
    expect(leaks(r)).toBe(false)
  })

  test("anthropic shared kinds: scope_invalid when scope not null; 100 not unverified", () => {
    const shared = (kind: string, scope: unknown, percent = 10) => ({
      kind,
      percent,
      resets_at: iso(3_600_000),
      scope,
    })
    const explain = (entry: unknown) =>
      explainAnthropic(anthropicBody({ limits: [entry] }), NOW)
    expect(explain(shared("session", {}))).toEqual([
      "model_scope_unverified",
      "scoped_window_scope_invalid",
    ])
    expect(explain(shared("weekly_all", undefined))).toEqual([
      "model_scope_unverified",
      "scoped_window_scope_invalid",
    ])
    expect(explain(shared("session", null, 100))).toEqual([
      "model_scope_unverified",
    ])
    expect(explain(shared("weekly_all", null, 100))).toEqual([
      "model_scope_unverified",
    ])
    expect(
      explain({ ...shared("session", null), percent: Number.NaN }),
    ).toEqual(["model_scope_unverified", "scoped_window_percent_invalid"])
  })

  test("anthropic opaque below-100 scope is accepted as available", async () => {
    const opaque = {
      kind: "weekly_scoped",
      percent: 50,
      resets_at: iso(3_600_000),
      scope: { model: { id: null, display_name: "fixture-label" } },
    }
    const { deps, calls } = makeDeps(() =>
      json(anthropicBody({ limits: [opaque] })),
    )
    const r = await diagnoseQuota(makeCtx(), "anthropic", deps)
    expect(r).toEqual({
      outcome: "proof_accepted",
      status: 200,
      state: "available",
      billingState: "subscription_only",
      limitShapes: [
        {
          kind: "weekly_scoped",
          fields: {
            kind: "string",
            percent: "number",
            resets_at: "string",
            scope: "object",
          },
        },
      ],
    })
    expect(calls).toHaveLength(1)
    expect(JSON.stringify(r).includes("fixture-label")).toBe(false)
    expect(leaks(r)).toBe(false)
  })

  test("limitShapes projection is safe and bounded", async () => {
    const shapes = async (
      provider: "anthropic" | "openai",
      limits: unknown,
    ) => {
      const { deps } = makeDeps(() =>
        json(
          provider === "anthropic"
            ? anthropicBody({ limits })
            : openaiBody(false, { limits }),
        ),
      )
      return (await diagnoseQuota(makeCtx(), provider, deps)).limitShapes
    }
    const base = { percent: 1, resets_at: iso(1000), scope: {} }
    expect(
      await shapes("anthropic", [
        { ...base, kind: "weekly_shared" },
        { ...base, kind: "adversarial_token" },
        { ...base, kind: "Fixture-Upper" },
        { ...base, kind: "xk_qzjwvbnmpyhdgtfr_aeiou" },
        { ...base, kind: 5 },
        { percent: null, extra_secret_root: 1, usage: [] },
        "fixture-raw",
        null,
      ]),
    ).toEqual([
      {
        kind: "weekly_shared",
        fields: {
          kind: "string",
          percent: "number",
          resets_at: "string",
          scope: "object",
        },
      },
      { kind: "<redacted>", fields: expect.any(Object) },
      { kind: "<redacted>", fields: expect.any(Object) },
      { kind: "<redacted>", fields: expect.any(Object) },
      { kind: "<invalid>", fields: expect.any(Object) },
      { kind: "<missing>", fields: { percent: "null", usage: "array" } },
      { kind: "<non_object>", fields: {} },
      { kind: "<non_object>", fields: {} },
    ])
    const many = Array.from({ length: 30 }, () => ({
      ...base,
      kind: "five_hour",
    }))
    expect(await shapes("anthropic", many)).toHaveLength(20)
    expect(await shapes("openai", many)).toBeUndefined()
  })

  test("anthropic reasons carry no extra-credit reason fields", async () => {
    const reasons = await reject(
      "anthropic",
      anthropicBody({
        seven_day: undefined,
        extra_usage: { is_enabled: true, monthly_limit: 100 },
      }),
    )
    expect(reasons).toEqual(["seven_day_window_missing"])
  })

  test("anthropic selected model window invalid", async () => {
    expect(
      await reject(
        "anthropic",
        anthropicBody({
          seven_day_sonnet: { utilization: "x", resets_at: iso(1000) },
        }),
      ),
    ).toEqual(["selected_model_window_invalid"])
  })

  test("anthropic non-object", async () => {
    expect(await reject("anthropic", [])).toEqual(["usage_not_object"])
  })

  test("openai plan other never echoes plan", async () => {
    const reasons = await reject(
      "openai",
      openaiBody(false, { plan_type: "wild-plan-name" }),
    )
    expect(reasons).toEqual(["plan_not_plus"])
    expect(JSON.stringify(reasons).includes("wild-plan-name")).toBe(false)
  })

  test("openai additional limits and spend control", async () => {
    expect(
      await reject(
        "openai",
        openaiBody(false, {
          additional_rate_limits: [{ wild: 1 }],
          spend_control: { wild: 2 },
        }),
      ),
    ).toEqual(["additional_limits_unsupported", "spend_control_unverified"])
  })

  test("openai malformed spend_control is spend_control_unverified", async () => {
    expect(
      await reject("openai", openaiBody(false, { spend_control: {} })),
    ).toEqual(["spend_control_unverified"])
  })

  test("openai allowed with a full window is unknown, not exhausted", async () => {
    const body = openaiBody()
    ;(body.rate_limit as any).primary_window.used_percent = 100
    expect(await reject("openai", body)).toEqual(["unsupported_response"])
  })

  test("openai rate limit missing and bad primary", async () => {
    expect(await reject("openai", { plan_type: "plus" })).toEqual([
      "rate_limit_missing",
    ])
    const body = openaiBody()
    ;(body.rate_limit as any).primary_window = { used_percent: 500 }
    expect(await reject("openai", body)).toEqual([
      "primary_window_percent_invalid",
      "primary_window_reset_invalid",
      "primary_window_duration_invalid",
    ])
  })

  test("openai flags inconsistent and secondary invalid", async () => {
    const a = openaiBody()
    ;(a.rate_limit as any).limit_reached = true
    ;(a.rate_limit as any).allowed = true
    expect(await reject("openai", a)).toEqual(["rate_limit_flags_inconsistent"])
    const b = openaiBody()
    ;(b.rate_limit as any).secondary_window = { used_percent: "x" }
    expect(await reject("openai", b)).toEqual(["secondary_window_invalid"])
  })
})

describe("explain functions", () => {
  test("never echo wild field names or values", () => {
    const wild = { "fixture-access": "fixture-account", extra: { x: 1 } }
    const a = explainAnthropic(wild, NOW)
    const o = explainOpenAI(wild, NOW)
    expect(JSON.stringify([a, o]).includes("fixture")).toBe(false)
    expect(a).toEqual(["five_hour_window_missing", "seven_day_window_missing"])
    expect(o).toContain("plan_not_plus")
  })

  test("fallback when nothing enumerated matches", () => {
    expect(explainAnthropic(anthropicBody(), NOW)).toEqual([
      "unsupported_response",
    ])
    expect(explainOpenAI(openaiBody(), NOW)).toEqual(["unsupported_response"])
  })

  test("enabled extra usage alone, with fine quota windows, falls back to unsupported_response", () => {
    expect(
      explainAnthropic(
        anthropicBody({ extra_usage: { is_enabled: true } }),
        NOW,
      ),
    ).toEqual(["unsupported_response"])
  })

  test("throwing getters yield fallback", () => {
    const evil = new Proxy(
      {},
      {
        getPrototypeOf() {
          throw new Error("fixture-access")
        },
      },
    )
    expect(explainAnthropic(evil, NOW)).toEqual(["unsupported_response"])
    expect(explainOpenAI(evil, NOW)).toEqual(["unsupported_response"])
  })
})
