import { describe, expect, test } from "bun:test"
import {
  inspectAnthropicUsage,
  inspectOpenAIUsage,
  parseAnthropicBilling,
  parseAnthropicQuota,
  parseOpenAIBilling,
  parseOpenAIQuota,
} from "./quota"

const NOW = Date.parse("2026-01-01T00:00:00Z")
const H1 = "2026-01-01T01:00:00Z"
const H2 = "2026-01-01T02:00:00Z"
const PAST = "2025-12-31T23:00:00Z"
const T1 = Date.parse(H1)
const T2 = Date.parse(H2)
const UNKNOWN = { state: "unknown", observedAt: NOW }

const win = (utilization: unknown, resets_at: unknown = H1) => ({
  utilization,
  resets_at,
})
const anth = (over: Record<string, unknown> = {}) => ({
  five_hour: win(10),
  seven_day: win(20),
  ...over,
})

describe("parseAnthropicQuota", () => {
  test("available without resetAt", () => {
    expect(parseAnthropicQuota(anth(), NOW, "claude-haiku-4-5")).toEqual({
      state: "available",
      observedAt: NOW,
    })
  })

  test("malformed roots are unknown", () => {
    for (const bad of [null, undefined, 1, "x", [], [anth()]]) {
      expect(parseAnthropicQuota(bad, NOW, "claude-haiku-4-5")).toEqual(UNKNOWN)
    }
  })

  test("missing weekly or five-hour window is unknown", () => {
    expect(parseAnthropicQuota({ five_hour: win(10) }, NOW, "m")).toEqual(
      UNKNOWN,
    )
    expect(parseAnthropicQuota({ seven_day: win(10) }, NOW, "m")).toEqual(
      UNKNOWN,
    )
    expect(parseAnthropicQuota(anth({ seven_day: null }), NOW, "m")).toEqual(
      UNKNOWN,
    )
  })

  test("nonfinite / out-of-range / non-number percent is unknown", () => {
    for (const bad of [NaN, Infinity, -Infinity, -1, 100.5, 101, "50", null]) {
      expect(
        parseAnthropicQuota(anth({ five_hour: win(bad) }), NOW, "m"),
      ).toEqual(UNKNOWN)
    }
  })

  test("stale, equal-to-now, or invalid reset is unknown", () => {
    expect(
      parseAnthropicQuota(anth({ five_hour: win(10, PAST) }), NOW, "m"),
    ).toEqual(UNKNOWN)
    expect(
      parseAnthropicQuota(
        anth({ five_hour: win(10, "2026-01-01T00:00:00Z") }),
        NOW,
        "m",
      ),
    ).toEqual(UNKNOWN)
    expect(
      parseAnthropicQuota(anth({ five_hour: win(10, "nope") }), NOW, "m"),
    ).toEqual(UNKNOWN)
    expect(
      parseAnthropicQuota(anth({ five_hour: win(10, 12345) }), NOW, "m"),
    ).toEqual(UNKNOWN)
  })

  test("exhausted at 100 uses max reset of exhausted windows", () => {
    const r = parseAnthropicQuota(
      anth({ five_hour: win(100, H1), seven_day: win(100, H2) }),
      NOW,
      "m",
    )
    expect(r).toEqual({ state: "exhausted", observedAt: NOW, resetAt: T2 })
  })

  test("only exhausted windows contribute to resetAt", () => {
    const r = parseAnthropicQuota(
      anth({ five_hour: win(100, H1), seven_day: win(50, H2) }),
      NOW,
      "m",
    )
    expect(r).toEqual({ state: "exhausted", observedAt: NOW, resetAt: T1 })
  })

  test("extra_usage does not gate quota", () => {
    for (const eu of [
      undefined,
      null,
      "x",
      { is_enabled: true },
      { is_enabled: false },
      {},
    ]) {
      expect(
        parseAnthropicQuota(anth({ extra_usage: eu }), NOW, "m").state,
      ).toBe("available")
    }
    expect(
      parseAnthropicQuota(
        anth({ five_hour: win(100), extra_usage: { is_enabled: true } }),
        NOW,
        "m",
      ).state,
    ).toBe("exhausted")
  })

  const lim = (id: unknown, percent: unknown = 50, extra = {}) => ({
    kind: "weekly_scoped",
    percent,
    resets_at: H1,
    scope: { model: { id, display_name: "Fable" } },
    ...extra,
  })

  test("limits: absent/null/empty ok; non-array or malformed unknown", () => {
    for (const ok of [undefined, null, []]) {
      expect(parseAnthropicQuota(anth({ limits: ok }), NOW, "m").state).toBe(
        "available",
      )
    }
    expect(
      parseAnthropicQuota(anth({ limits: [{ model: "x" }] }), NOW, "m"),
    ).toEqual(UNKNOWN)
    expect(parseAnthropicQuota(anth({ limits: {} }), NOW, "m")).toEqual(UNKNOWN)
  })

  test("limits: shared exhaustion verified regardless of opaque entries", () => {
    expect(
      parseAnthropicQuota(anth({ five_hour: win(100), limits: [1] }), NOW, "m")
        .state,
    ).toBe("exhausted")
    expect(
      parseAnthropicQuota(
        anth({ seven_day: win(100), limits: [lim(null)] }),
        NOW,
        "m",
      ).state,
    ).toBe("exhausted")
  })

  test("limits: exact native id scope applies or is excluded", () => {
    const sel = "claude-sonnet-5-5"
    expect(
      parseAnthropicQuota(anth({ limits: [lim(sel, 100)] }), NOW, sel).state,
    ).toBe("exhausted")
    expect(
      parseAnthropicQuota(
        anth({ limits: [lim("claude-opus-5-5", 100)] }),
        NOW,
        sel,
      ).state,
    ).toBe("available")
  })

  const SEL = "claude-sonnet-5-5"
  const q = (limits: unknown[], model = SEL) =>
    parseAnthropicQuota(anth({ limits }), NOW, model)

  test("limits: opaque ids below 100 are available", () => {
    for (const id of [null, undefined, "", "mystery"]) {
      for (const p of [0, 50, 99.99]) {
        expect(q([lim(id, p)]).state).toBe("available")
      }
    }
    for (const m of [
      "claude-sonnet-5-5",
      "claude-opus-5-5",
      "claude-haiku-4-5",
    ]) {
      expect(q([lim(null, 50)], m).state).toBe("available")
    }
  })

  test("limits: opaque ids at 100 are unknown, never exhausted", () => {
    for (const id of [null, undefined, "", "mystery"]) {
      expect(q([lim(id, 100)])).toEqual(UNKNOWN)
    }
    expect(q([lim(null, 50), lim("mystery", 100)])).toEqual(UNKNOWN)
    expect(q([lim(null, 50), lim(undefined, 50)]).state).toBe("available")
  })

  test("limits: known different id at 100 ignored; selected/shared exhaustion wins", () => {
    expect(q([lim("claude-opus-5-5", 100)]).state).toBe("available")
    expect(q([lim(SEL, 100), lim(null, 50)]).state).toBe("exhausted")
    expect(q([lim(SEL, 100), lim(null, 100)]).state).toBe("exhausted")
    expect(
      parseAnthropicQuota(
        anth({ five_hour: win(100), limits: [lim(null, 100)] }),
        NOW,
        SEL,
      ).state,
    ).toBe("exhausted")
  })

  test("limits: malformed entries stay unknown even below 100", () => {
    expect(q([lim(5, 50)])).toEqual(UNKNOWN)
    expect(q([lim(null, "50")])).toEqual(UNKNOWN)
    expect(q([lim(null, 101)])).toEqual(UNKNOWN)
    expect(q([lim(null, 50, { resets_at: "2000-01-01T00:00:00Z" })])).toEqual(
      UNKNOWN,
    )
    expect(q([lim(null, 50, { scope: "x" })])).toEqual(UNKNOWN)
    expect(q([lim(null, 50, { scope: { model: "x" } })])).toEqual(UNKNOWN)
  })

  test("limits: opaque 100 keeps quota unknown with billing independent", () => {
    expect(
      inspectAnthropicUsage(
        anth({
          limits: [lim(null, 100)],
          extra_usage: {
            is_enabled: true,
            monthly_limit: 100,
            used_credits: 1,
            utilization: 1,
          },
        }),
        NOW,
        "claude-sonnet-5-5",
      ),
    ).toEqual({
      quota: UNKNOWN,
      billing: { state: "credits_available", observedAt: NOW },
    })
  })

  test("limits: is_active is ignored", () => {
    expect(
      parseAnthropicQuota(
        anth({ limits: [lim("claude-sonnet-5-5", 100, { is_active: false })] }),
        NOW,
        "claude-sonnet-5-5",
      ).state,
    ).toBe("exhausted")
  })

  const shared = (kind: string, percent: unknown, resets_at: unknown = H1) => ({
    kind,
    percent,
    resets_at,
    scope: null,
    is_active: true,
  })
  const REAL = (over: unknown[] = []) => [
    shared("session", 10),
    shared("weekly_all", 20),
    lim(null, 50),
    ...over,
  ]

  test("limits: real shape below 100 is available for all models", () => {
    for (const m of [
      "claude-sonnet-5-5",
      "claude-opus-5-5",
      "claude-haiku-4-5",
    ])
      expect(
        parseAnthropicQuota(
          anth({ five_hour: win(10), seven_day: win(20), limits: REAL() }),
          NOW,
          m,
        ).state,
      ).toBe("available")
  })

  test("limits: shared session/weekly_all at 100 exhaust even with root below 100", () => {
    for (const kind of ["session", "weekly_all"])
      for (const m of ["claude-sonnet-5-5", "claude-haiku-4-5"])
        expect(q([shared(kind, 100)], m)).toEqual({
          state: "exhausted",
          observedAt: NOW,
          resetAt: T1,
        })
    expect(
      q([shared("session", 100, H1), shared("weekly_all", 100, H2)]),
    ).toEqual({ state: "exhausted", observedAt: NOW, resetAt: T2 })
  })

  test("limits: shared 100 dominates opaque 100; known other 100 ignored", () => {
    expect(q([lim(null, 100), shared("weekly_all", 100)]).state).toBe(
      "exhausted",
    )
    expect(q([...REAL(), lim("claude-opus-5-5", 100)]).state).toBe("available")
  })

  test("limits: shared with missing/wrong scope or malformed fields is unknown", () => {
    const { scope: _s, ...noScope } = shared("session", 10)
    expect(q([noScope])).toEqual(UNKNOWN)
    expect(q([{ ...shared("weekly_all", 10), scope: {} }])).toEqual(UNKNOWN)
    expect(q([shared("session", "10")])).toEqual(UNKNOWN)
    expect(q([shared("session", 10, PAST)])).toEqual(UNKNOWN)
    expect(q([shared("session", 10, 5)])).toEqual(UNKNOWN)
    expect(q([shared("mystery", 10)])).toEqual(UNKNOWN)
    expect(q([shared("session", 10), shared("mystery", 10)])).toEqual(UNKNOWN)
  })

  test("limits: is_active is ignored for shared kinds", () => {
    expect(q([{ ...shared("weekly_all", 100), is_active: false }]).state).toBe(
      "exhausted",
    )
    expect(
      q([{ ...shared("session", 10), is_active: false }, lim(SEL, 50)]).state,
    ).toBe("available")
  })

  test("limits: selected flat 100 still overrides lower shared entries", () => {
    expect(
      parseAnthropicQuota(
        anth({ seven_day_sonnet: win(100, H2), limits: REAL() }),
        NOW,
        SEL,
      ),
    ).toEqual({ state: "exhausted", observedAt: NOW, resetAt: T2 })
  })

  test("selected per-model window is chosen for sonnet and opus", () => {
    const s = anth({ seven_day_sonnet: win(100, H2) })
    expect(parseAnthropicQuota(s, NOW, "claude-sonnet-5-5")).toEqual({
      state: "exhausted",
      observedAt: NOW,
      resetAt: T2,
    })
    const o = anth({ seven_day_opus: win(100, H2) })
    expect(parseAnthropicQuota(o, NOW, "claude-opus-5-5")).toEqual({
      state: "exhausted",
      observedAt: NOW,
      resetAt: T2,
    })
  })

  test("non-selected per-model window is ignored, even if exhausted or malformed", () => {
    const s = anth({
      seven_day_sonnet: win(100, H2),
      seven_day_opus: "garbage",
    })
    expect(parseAnthropicQuota(s, NOW, "claude-haiku-4-5").state).toBe(
      "available",
    )
    expect(parseAnthropicQuota(s, NOW, "claude-opus-5-5").state).toBe("unknown")
    expect(
      parseAnthropicQuota(
        anth({ seven_day_opus: win(100) }),
        NOW,
        "claude-sonnet-5-5",
      ).state,
    ).toBe("available")
  })

  test("selected per-model window: null/missing ok, malformed unknown", () => {
    expect(
      parseAnthropicQuota(
        anth({ seven_day_sonnet: null }),
        NOW,
        "claude-sonnet-5-5",
      ).state,
    ).toBe("available")
    expect(parseAnthropicQuota(anth(), NOW, "claude-opus-5-5").state).toBe(
      "available",
    )
    expect(
      parseAnthropicQuota(
        anth({ seven_day_sonnet: win(NaN) }),
        NOW,
        "claude-sonnet-5-5",
      ),
    ).toEqual(UNKNOWN)
    expect(
      parseAnthropicQuota(
        anth({ seven_day_sonnet: { utilization: 5 } }),
        NOW,
        "claude-sonnet-5-5",
      ),
    ).toEqual(UNKNOWN)
  })

  test("malformed selected scope trumps exhausted shared window", () => {
    const d = anth({ five_hour: win(100), seven_day_sonnet: win(-5) })
    expect(parseAnthropicQuota(d, NOW, "claude-sonnet-5-5")).toEqual(UNKNOWN)
  })

  test("canonical keys only: camelCase / aliased keys are not read", () => {
    expect(
      parseAnthropicQuota({ fiveHour: win(10), sevenDay: win(10) }, NOW, "m"),
    ).toEqual(UNKNOWN)
    expect(
      parseAnthropicQuota(
        { five_hour: { utilization: 10, resetsAt: H1 }, seven_day: win(10) },
        NOW,
        "m",
      ),
    ).toEqual(UNKNOWN)
    const inherited = Object.create({ five_hour: win(10), seven_day: win(10) })
    expect(parseAnthropicQuota(inherited, NOW, "m")).toEqual(UNKNOWN)
  })

  test("does not mutate input", () => {
    const d = anth({
      five_hour: win(100, H2),
      seven_day_sonnet: win(5),
      limits: [],
    })
    const copy = JSON.parse(JSON.stringify(d))
    Object.freeze(d)
    parseAnthropicQuota(d, NOW, "claude-sonnet-5-5")
    expect(d).toEqual(copy)
  })
})

const NOW_S = NOW / 1000
const owin = (used_percent: unknown, extra: Record<string, unknown> = {}) => ({
  used_percent,
  limit_window_seconds: 18000,
  reset_at: NOW_S + 3600,
  ...extra,
})
const oai = (
  rate: Record<string, unknown> = {},
  root: Record<string, unknown> = {},
) => ({
  plan_type: "plus",
  rate_limit: {
    allowed: true,
    limit_reached: false,
    primary_window: owin(10),
    ...rate,
  },
  ...root,
})

const EX = { allowed: false, limit_reached: true }

describe("parseOpenAIQuota", () => {
  test("available without resetAt", () => {
    expect(parseOpenAIQuota(oai(), NOW)).toEqual({
      state: "available",
      observedAt: NOW,
    })
  })

  test("malformed roots are unknown", () => {
    for (const bad of [null, undefined, 1, "x", [], [oai()]]) {
      expect(parseOpenAIQuota(bad, NOW)).toEqual(UNKNOWN)
    }
    expect(parseOpenAIQuota({ plan_type: "plus" }, NOW)).toEqual(UNKNOWN)
    expect(
      parseOpenAIQuota({ plan_type: "plus", rate_limit: [] }, NOW),
    ).toEqual(UNKNOWN)
  })

  test("plan other than plus is unknown", () => {
    for (const p of ["free", "pro", "Plus", "team", undefined, null, 1]) {
      expect(parseOpenAIQuota(oai({}, { plan_type: p }), NOW)).toEqual(UNKNOWN)
    }
  })

  test("invalid flags are unknown", () => {
    expect(parseOpenAIQuota(oai({ allowed: "true" }), NOW)).toEqual(UNKNOWN)
    expect(parseOpenAIQuota(oai({ limit_reached: 0 }), NOW)).toEqual(UNKNOWN)
    expect(parseOpenAIQuota(oai({ allowed: undefined }), NOW)).toEqual(UNKNOWN)
    expect(parseOpenAIQuota(oai({ limit_reached: null }), NOW)).toEqual(UNKNOWN)
  })

  test("nonfinite / out-of-range percent is unknown", () => {
    for (const bad of [NaN, Infinity, -1, 100.1, "5", null, undefined]) {
      expect(parseOpenAIQuota(oai({ primary_window: owin(bad) }), NOW)).toEqual(
        UNKNOWN,
      )
    }
  })

  test("invalid limit_window_seconds is unknown", () => {
    for (const bad of [0, -1, 1.5, NaN, Infinity, "18000", undefined]) {
      expect(
        parseOpenAIQuota(
          oai({ primary_window: owin(10, { limit_window_seconds: bad }) }),
          NOW,
        ),
      ).toEqual(UNKNOWN)
    }
  })

  test("stale reset_at is unknown", () => {
    expect(
      parseOpenAIQuota(
        oai({ primary_window: owin(10, { reset_at: NOW_S }) }),
        NOW,
      ),
    ).toEqual(UNKNOWN)
    expect(
      parseOpenAIQuota(
        oai({ primary_window: owin(10, { reset_at: NOW_S - 5 }) }),
        NOW,
      ),
    ).toEqual(UNKNOWN)
  })

  test("reset_after_seconds fallback when reset_at missing", () => {
    const w = {
      used_percent: 100,
      limit_window_seconds: 18000,
      reset_after_seconds: 600,
    }
    expect(parseOpenAIQuota(oai({ ...EX, primary_window: w }), NOW)).toEqual({
      state: "exhausted",
      observedAt: NOW,
      resetAt: NOW + 600_000,
    })
  })

  test("invalid reset_at does not fall back to reset_after_seconds", () => {
    const w = owin(10, { reset_at: NOW_S - 5, reset_after_seconds: 600 })
    expect(parseOpenAIQuota(oai({ primary_window: w }), NOW)).toEqual(UNKNOWN)
    const bad = owin(10, { reset_at: "soon", reset_after_seconds: 600 })
    expect(parseOpenAIQuota(oai({ primary_window: bad }), NOW)).toEqual(UNKNOWN)
  })

  test("reset multiplication overflow to Infinity is unknown", () => {
    for (const w of [
      owin(10, { reset_at: 1e308 }),
      owin(100, { reset_at: 1e308 }),
      {
        used_percent: 10,
        limit_window_seconds: 18000,
        reset_after_seconds: 1e308,
      },
    ]) {
      expect(parseOpenAIQuota(oai({ primary_window: w }), NOW)).toEqual(UNKNOWN)
    }
  })

  test("reset_at preferred over reset_after_seconds", () => {
    const w = owin(100, { reset_at: NOW_S + 100, reset_after_seconds: 9999 })
    expect(parseOpenAIQuota(oai({ ...EX, primary_window: w }), NOW)).toEqual({
      state: "exhausted",
      observedAt: NOW,
      resetAt: NOW + 100_000,
    })
  })

  test("invalid reset_after_seconds is unknown", () => {
    for (const bad of [0, -1, 1.5, NaN, "60", undefined]) {
      const w = {
        used_percent: 10,
        limit_window_seconds: 18000,
        reset_after_seconds: bad,
      }
      expect(parseOpenAIQuota(oai({ primary_window: w }), NOW)).toEqual(UNKNOWN)
    }
  })

  test("secondary window: missing/null ok, malformed unknown", () => {
    expect(parseOpenAIQuota(oai({ secondary_window: null }), NOW).state).toBe(
      "available",
    )
    expect(
      parseOpenAIQuota(oai({ secondary_window: owin(20) }), NOW).state,
    ).toBe("available")
    expect(parseOpenAIQuota(oai({ secondary_window: owin(NaN) }), NOW)).toEqual(
      UNKNOWN,
    )
    expect(
      parseOpenAIQuota(
        oai({ primary_window: owin(100), secondary_window: "x" }),
        NOW,
      ),
    ).toEqual(UNKNOWN)
  })

  test("resetAt is max of exhausted rate windows", () => {
    const r = parseOpenAIQuota(
      oai({
        ...EX,
        primary_window: owin(100, { reset_at: NOW_S + 100 }),
        secondary_window: owin(100, { reset_at: NOW_S + 7200 }),
      }),
      NOW,
    )
    expect(r).toEqual({
      state: "exhausted",
      observedAt: NOW,
      resetAt: NOW + 7_200_000,
    })
  })

  test("non-exhausted window does not contribute when another is exhausted", () => {
    const r = parseOpenAIQuota(
      oai({
        ...EX,
        primary_window: owin(100, { reset_at: NOW_S + 100 }),
        secondary_window: owin(50, { reset_at: NOW_S + 7200 }),
      }),
      NOW,
    )
    expect(r).toEqual({
      state: "exhausted",
      observedAt: NOW,
      resetAt: NOW + 100_000,
    })
  })

  test("flags declaring exhaustion bound resetAt by max of all windows", () => {
    const rate = {
      primary_window: owin(10, { reset_at: NOW_S + 100 }),
      secondary_window: owin(20, { reset_at: NOW_S + 7200 }),
    }
    const expected = {
      state: "exhausted",
      observedAt: NOW,
      resetAt: NOW + 7_200_000,
    }
    expect(
      parseOpenAIQuota(
        oai({ ...rate, allowed: false, limit_reached: true }),
        NOW,
      ),
    ).toEqual(expected)
    expect(parseOpenAIQuota(oai({ ...rate, allowed: false }), NOW)).toEqual(
      UNKNOWN,
    )
    expect(
      parseOpenAIQuota(oai({ ...rate, limit_reached: true }), NOW),
    ).toEqual(UNKNOWN)
  })

  test("additional_rate_limits: absent/null/empty ok, nonempty or malformed unknown", () => {
    for (const ok of [undefined, null, []]) {
      expect(
        parseOpenAIQuota(oai({}, { additional_rate_limits: ok }), NOW).state,
      ).toBe("available")
    }
    expect(
      parseOpenAIQuota(
        oai({}, { additional_rate_limits: [{ name: "x" }] }),
        NOW,
      ),
    ).toEqual(UNKNOWN)
    expect(
      parseOpenAIQuota(oai({}, { additional_rate_limits: {} }), NOW),
    ).toEqual(UNKNOWN)
  })

  test("spend_control: recognized not-reached available; reached/malformed unknown", () => {
    for (const ok of [
      null,
      undefined,
      { reached: false },
      { reached: false, individual_limit: null },
      {
        reached: false,
        individual_limit: {
          limit: "10",
          used: "1.5",
          remaining: "8.5",
          used_percent: 15,
          remaining_percent: 85,
          reset_after_seconds: 60,
          reset_at: NOW_S + 60,
        },
      },
    ]) {
      expect(parseOpenAIQuota(oai({}, { spend_control: ok }), NOW).state).toBe(
        "available",
      )
    }
    for (const bad of [
      {},
      { reached: true },
      { reached: "no" },
      "x",
      { reached: false, individual_limit: { limit: 10 } },
      { reached: false, individual_limit: { used_percent: 1.5 } },
      { reached: false, individual_limit: { reset_at: NOW_S - 1 } },
    ]) {
      expect(parseOpenAIQuota(oai({}, { spend_control: bad }), NOW)).toEqual(
        UNKNOWN,
      )
    }
  })

  const extraRl = (slug: unknown, rate: Record<string, unknown> = {}) => ({
    limit_name: "n",
    metered_feature: "f",
    normal_model_slug: slug,
    rate_limit: {
      allowed: true,
      limit_reached: false,
      primary_window: owin(10),
      ...rate,
    },
  })

  test("additional_rate_limits: selected included, other known ignored, opaque unknown", () => {
    const ex = { allowed: false, limit_reached: true }
    expect(
      parseOpenAIQuota(
        oai({}, { additional_rate_limits: [extraRl("gpt-6.1-sol", ex)] }),
        NOW,
      ).state,
    ).toBe("exhausted")
    expect(
      parseOpenAIQuota(
        oai({}, { additional_rate_limits: [extraRl("gpt-6-luna", ex)] }),
        NOW,
      ).state,
    ).toBe("available")
    for (const s of [null, undefined, "mystery"]) {
      expect(
        parseOpenAIQuota(
          oai({}, { additional_rate_limits: [extraRl(s)] }),
          NOW,
        ),
      ).toEqual(UNKNOWN)
    }
    expect(
      parseOpenAIQuota(
        oai(
          { allowed: false, limit_reached: true },
          { additional_rate_limits: [extraRl(null)] },
        ),
        NOW,
      ).state,
    ).toBe("exhausted")
  })

  test("backend flag combinations; percent alone is not authority", () => {
    const full = { primary_window: owin(100) }
    expect(parseOpenAIQuota(oai(full), NOW)).toEqual(UNKNOWN)
    expect(
      parseOpenAIQuota(
        oai({ ...full, allowed: false, limit_reached: true }),
        NOW,
      ).state,
    ).toBe("exhausted")
    expect(
      parseOpenAIQuota(
        oai({ allowed: false, limit_reached: true, primary_window: owin(5) }),
        NOW,
      ).state,
    ).toBe("exhausted")
    expect(
      parseOpenAIQuota(
        oai({
          allowed: false,
          limit_reached: false,
          primary_window: owin(100),
        }),
        NOW,
      ),
    ).toEqual(UNKNOWN)
    expect(
      parseOpenAIQuota(
        oai({ allowed: true, limit_reached: true, primary_window: owin(5) }),
        NOW,
      ),
    ).toEqual(UNKNOWN)
  })

  test("credits are ignored and cannot turn exhausted into available", () => {
    const credits = { has_credits: true, unlimited: true, balance: "100" }
    expect(parseOpenAIQuota(oai({}, { credits }), NOW)).toEqual({
      state: "available",
      observedAt: NOW,
    })
    expect(
      parseOpenAIQuota(
        oai({ ...EX, primary_window: owin(100) }, { credits }),
        NOW,
      ).state,
    ).toBe("exhausted")
    expect(
      parseOpenAIQuota(
        oai({ allowed: false, limit_reached: true }, { credits }),
        NOW,
      ).state,
    ).toBe("exhausted")
    expect(parseOpenAIQuota(oai({}, { credits: "garbage" }), NOW).state).toBe(
      "available",
    )
  })

  test("output carries no source data", () => {
    const r = parseOpenAIQuota(
      oai({ ...EX, primary_window: owin(100) }, { user_id: "fake-user" }),
      NOW,
    )
    expect(Object.keys(r).sort()).toEqual(["observedAt", "resetAt", "state"])
  })

  test("does not mutate input", () => {
    const d = oai(
      { secondary_window: owin(20) },
      { additional_rate_limits: [], credits: { balance: "1" } },
    )
    const copy = JSON.parse(JSON.stringify(d))
    Object.freeze(d)
    parseOpenAIQuota(d, NOW)
    expect(d).toEqual(copy)
  })
})

const bill = (state: string) => ({ state, observedAt: NOW })
const eu = (over: Record<string, unknown> = {}) => ({
  extra_usage: {
    is_enabled: true,
    monthly_limit: 100,
    used_credits: 10,
    utilization: 10,
    ...over,
  },
})

describe("parseAnthropicBilling", () => {
  test("disabled is subscription_only", () => {
    expect(
      parseAnthropicBilling({ extra_usage: { is_enabled: false } }, NOW),
    ).toEqual(bill("subscription_only"))
  })
  test("enabled with bounded fields is credits_available", () => {
    expect(parseAnthropicBilling(eu(), NOW)).toEqual(bill("credits_available"))
  })
  test("enabled and at/over limit is paid_risk", () => {
    expect(parseAnthropicBilling(eu({ utilization: 100 }), NOW)).toEqual(
      bill("paid_risk"),
    )
    expect(parseAnthropicBilling(eu({ used_credits: 100 }), NOW)).toEqual(
      bill("paid_risk"),
    )
  })
  test("missing or malformed is unknown", () => {
    for (const bad of [
      null,
      {},
      { extra_usage: null },
      { extra_usage: { is_enabled: "yes" } },
      { extra_usage: { is_enabled: true } },
      eu({ monthly_limit: 0 }),
      eu({ monthly_limit: null }),
      eu({ used_credits: -1 }),
      eu({ used_credits: NaN }),
      eu({ utilization: "5" }),
      eu({ utilization: -1 }),
    ]) {
      expect(parseAnthropicBilling(bad, NOW)).toEqual(bill("unknown"))
    }
  })
})

describe("parseOpenAIBilling", () => {
  const b = (credits: unknown) => ({ plan_type: "plus", credits })
  test("has_credits with positive balance is credits_available", () => {
    expect(
      parseOpenAIBilling(
        b({ has_credits: true, unlimited: false, balance: "5.25" }),
        NOW,
      ),
    ).toEqual(bill("credits_available"))
  })
  test("has_credits with zero balance is paid_risk", () => {
    expect(
      parseOpenAIBilling(
        b({ has_credits: true, unlimited: false, balance: "0" }),
        NOW,
      ),
    ).toEqual(bill("paid_risk"))
  })
  test("has_credits with missing/malformed balance is unknown", () => {
    for (const balance of [undefined, null, 5, "-1", "1e3", "x"]) {
      expect(
        parseOpenAIBilling(
          b({ has_credits: true, unlimited: false, balance }),
          NOW,
        ),
      ).toEqual(bill("unknown"))
    }
  })
  test("unlimited is unknown", () => {
    for (const has of [true, false]) {
      expect(
        parseOpenAIBilling(
          b({ has_credits: has, unlimited: true, balance: "5" }),
          NOW,
        ),
      ).toEqual(bill("unknown"))
    }
  })
  test("no credits: zero/absent subscription_only; positive/malformed unknown", () => {
    for (const balance of [undefined, null, "0", "0.00"]) {
      expect(
        parseOpenAIBilling(
          b({ has_credits: false, unlimited: false, balance }),
          NOW,
        ),
      ).toEqual(bill("subscription_only"))
    }
    for (const balance of ["5", 0, "x"]) {
      expect(
        parseOpenAIBilling(
          b({ has_credits: false, unlimited: false, balance }),
          NOW,
        ),
      ).toEqual(bill("unknown"))
    }
  })
  test("malformed roots are unknown", () => {
    for (const bad of [
      null,
      {},
      { plan_type: "free" },
      b("x"),
      b({ has_credits: true }),
    ]) {
      expect(parseOpenAIBilling(bad, NOW)).toEqual(bill("unknown"))
    }
  })
})

describe("inspect wrappers", () => {
  test("OpenAI quota and billing are independent", () => {
    const d = oai(
      {},
      { credits: { has_credits: true, unlimited: false, balance: "3" } },
    )
    expect(inspectOpenAIUsage(d, NOW)).toEqual({
      quota: { state: "available", observedAt: NOW },
      billing: bill("credits_available"),
    })
    expect(inspectOpenAIUsage(d, NOW, "gpt-6.1-sol")).toEqual(
      inspectOpenAIUsage(d, NOW),
    )
  })
  test("Anthropic exhausted quota with credits available", () => {
    expect(
      inspectAnthropicUsage(anth({ five_hour: win(100), ...eu() }), NOW, "m"),
    ).toEqual({
      quota: { state: "exhausted", observedAt: NOW, resetAt: T1 },
      billing: bill("credits_available"),
    })
  })
})
