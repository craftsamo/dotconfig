import { describe, expect, test } from "bun:test"
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { exportPath, loadQuotaExport, readQuota, dependencies } from "./quota"
import { QUOTA_MAX_AGE_MS, type AccountProof } from "./policy"

const NOW = 1_710_000_000_000
const account: AccountProof = {
  connectionID: "fixture-claude",
  providerID: "anthropic",
  methodID: "claude-max",
  type: "oauth",
}
const row = (
  window: string,
  percentRemaining = 90,
  sourceId = account.connectionID,
) => ({
  name: `fixture ${window}`,
  window,
  percentRemaining,
  sourceId,
  resultType: "quota",
  acquisitionMethod: "remote_api",
  authority: "provider_reported",
  ownership: "maintained",
  renderType: "percent",
  resetAt: (NOW + 3_600_000) / 1000,
})
const provider = (entries = [row("5h"), row("Weekly")]) => ({
  status: "ok",
  fetchedAt: NOW / 1000,
  entries,
})
const snapshot = (p: unknown = provider()) => ({
  version: 2,
  exportedAt: NOW / 1000,
  fromCache: true,
  cacheAgeSeconds: 0,
  providers: { anthropic: p },
})
const state = (s: unknown) => readQuota(s, account, NOW).state

describe("Quota public JSON", () => {
  test("uses sourceId and percentage rows without credit/account entitlement evidence", () => {
    expect(state(snapshot())).toBe("available")
    expect(state(snapshot(provider([row("5h", 0), row("Weekly")])))).toBe(
      "exhausted",
    )
    expect(state(snapshot(provider([row("5h", 0.4), row("Weekly")])))).toBe(
      "available",
    )
    expect(state(snapshot(provider([row("5h", -1), row("Weekly")])))).toBe(
      "exhausted",
    )
  })
  test("accepts either primary or weekly exhaustion, including rounded 0%", () => {
    for (const window of ["5h", "Weekly"]) {
      expect(
        state(
          snapshot(
            provider([
              row("5h", window === "5h" ? 0 : 20),
              row("Weekly", window === "Weekly" ? 0 : 20),
            ]),
          ),
        ),
      ).toBe("exhausted")
    }
  })
  test("filters credit and code-review rows instead of treating them as chat quota", () => {
    expect(
      state(
        snapshot(
          provider([
            row("5h"),
            row("Weekly"),
            row("Monthly", 0),
            row("Code Review", 0),
          ]),
        ),
      ),
    ).toBe("available")
  })
  test("model-specific rows without a 5h/Weekly window are ignored", () => {
    const fable = (percentRemaining: number) =>
      ({
        ...row("Weekly", percentRemaining),
        window: null,
        name: "[Claude] Fable Weekly",
      }) as any
    expect(
      state(snapshot(provider([row("5h"), row("Weekly"), fable(0)]))),
    ).toBe("available")
    expect(state(snapshot(provider([fable(0)])))).toBe("unknown")
  })
  test("plans may report a single window: either one alone decides", () => {
    for (const window of ["5h", "Weekly"]) {
      expect(state(snapshot(provider([row(window)])))).toBe("available")
      expect(state(snapshot(provider([row(window, 0)])))).toBe("exhausted")
    }
  })
  test("real ChatGPT shape: Weekly 0% with no 5h row is exhausted", () => {
    const a = {
      ...account,
      providerID: "openai",
      connectionID: "fixture-chatgpt",
      methodID: "chatgpt-browser",
    }
    const s = {
      version: 2,
      providers: {
        openai: {
          ...provider([
            { ...row("Weekly", 0, a.connectionID), resultType: "rate_limit" },
          ]),
          status: "partial",
        },
      },
    }
    expect(readQuota(s, a, NOW).state).toBe("exhausted")
  })
  test("real xAI shape: one Weekly quota row decides the pool", () => {
    const a = {
      ...account,
      providerID: "xai",
      connectionID: "fixture-grok",
      methodID: "device",
    }
    const s = (percent: number) => ({
      version: 2,
      providers: { xai: provider([row("Weekly", percent, a.connectionID)]) },
    })
    expect(readQuota(s(79), a, NOW).state).toBe("available")
    expect(readQuota(s(0), a, NOW).state).toBe("exhausted")
  })
  test("never pools another login or accepts unbound rows", () => {
    expect(
      state(
        snapshot(
          provider([row("5h", 90, "other"), row("Weekly", 90, "other")]),
        ),
      ),
    ).toBe("unknown")
    expect(
      state(snapshot(provider([row("5h"), row("Weekly", 0, "other")]))),
    ).toBe("available")
    const entries = [row("5h"), row("Weekly"), row("5h", 0, "other")]
    expect(state(snapshot(provider(entries)))).toBe("available")
    expect(
      state(
        snapshot(
          provider(entries.map((r) => ({ ...r, sourceId: undefined })) as any),
        ),
      ),
    ).toBe("unknown")
  })
  test("partial provider results can use complete matching-login rows", () => {
    expect(
      state(
        snapshot({
          ...provider(),
          status: "partial",
          errors: [{ label: "other", message: "fixture" }],
        }),
      ),
    ).toBe("available")
  })
  test("freshness follows Quota's five-minute cache, with one-minute export grace", () => {
    expect(
      state(
        snapshot({ ...provider(), fetchedAt: (NOW - QUOTA_MAX_AGE_MS) / 1000 }),
      ),
    ).toBe("available")
    for (const fetchedAt of [
      (NOW - QUOTA_MAX_AGE_MS - 1) / 1000,
      (NOW + 1) / 1000,
      NaN,
    ])
      expect(state(snapshot({ ...provider(), fetchedAt }))).toBe("unknown")
    // Rewriting a stale export must not make its provider data fresh.
    expect(
      state({
        ...snapshot({ ...provider(), fetchedAt: 1 }),
        exportedAt: NOW / 1000,
      }),
    ).toBe("unknown")
  })
  test("an empty window with a future reset is exhausted however old the export", () => {
    const stale = (percent: number, resetMs: number) =>
      snapshot({
        ...provider([
          { ...row("Weekly", percent), resetAt: (NOW + resetMs) / 1000 },
        ]),
        fetchedAt: (NOW - 10 * QUOTA_MAX_AGE_MS) / 1000,
      })
    const proof = readQuota(stale(0, 3_600_000), account, NOW)
    expect(proof.state).toBe("exhausted")
    expect(proof.resetAt).toBe(NOW + 3_600_000)
    // The window may have reset since, and "available" always needs fresh data.
    expect(state(stale(0, -1))).toBe("unknown")
    expect(state(stale(50, 3_600_000))).toBe("unknown")
    // A window that has reset since is dropped; a still-empty one still counts.
    const mixed = snapshot({
      ...provider([
        { ...row("5h", 0), resetAt: (NOW - 1000) / 1000 },
        { ...row("Weekly", 0), resetAt: (NOW + 1000) / 1000 },
      ]),
      fetchedAt: (NOW - 10 * QUOTA_MAX_AGE_MS) / 1000,
    })
    expect(state(mixed)).toBe("exhausted")
  })
  test("fresh data whose window already reset is unknown", () => {
    expect(
      state(
        snapshot(
          provider([
            { ...row("5h", 0), resetAt: (NOW - 1000) / 1000 },
            row("Weekly"),
          ]),
        ),
      ),
    ).toBe("unknown")
  })
  test("malformed, missing, wrong version and unavailable data are unknown", () => {
    for (const s of [
      undefined,
      null,
      [],
      {},
      { version: 1 },
      snapshot(null),
      snapshot({ status: "error" }),
      snapshot(provider([])),
      snapshot(provider([row("Monthly"), row("Code Review")])),
    ])
      expect(state(s)).toBe("unknown")
    expect(readQuota(snapshot(), undefined, NOW).state).toBe("unknown")
  })
  test("invalid percentage/reset values do not prove exhaustion", () => {
    for (const change of [
      { percentRemaining: "0" },
      { percentRemaining: NaN },
      { percentRemaining: 101 },
      { resetAt: NOW / 1000 },
      { resetAt: "later" },
    ])
      expect(
        state(
          snapshot(
            provider([{ ...row("5h"), ...change } as any, row("Weekly")]),
          ),
        ),
      ).toBe("unknown")
  })
  test("rows that are not provider-reported percentage quota are never trusted", () => {
    for (const change of [
      { resultType: "balance" },
      { authority: "locally_derived" },
      { acquisitionMethod: "local_cli" },
      { renderType: "value" },
    ]) {
      expect(
        state(snapshot(provider([{ ...row("5h", 0), ...change } as any]))),
      ).toBe("unknown")
      // An untrusted row neither exhausts nor vouches for the provider.
      expect(
        state(
          snapshot(
            provider([{ ...row("5h", 0), ...change } as any, row("Weekly")]),
          ),
        ),
      ).toBe("available")
    }
  })
  test("fresh 0% works even when Quota supplies no reset", () => {
    expect(
      state(
        snapshot(
          provider([
            { ...row("5h", 0), resetAt: undefined } as any,
            row("Weekly"),
          ]),
        ),
      ),
    ).toBe("exhausted")
  })
  test("supports OpenAI with the same public schema", () => {
    const a = {
      ...account,
      providerID: "openai",
      connectionID: "fixture-chatgpt",
      methodID: "chatgpt-browser",
    }
    const s = {
      version: 2,
      providers: {
        openai: provider(
          [row("5h", 0, a.connectionID), row("Weekly", 90, a.connectionID)].map(
            (r) => ({ ...r, resultType: "rate_limit" }),
          ),
        ),
      },
    }
    expect(readQuota(s, a, NOW).state).toBe("exhausted")
  })
  test("default export path matches Quota's XDG location", () => {
    expect(exportPath({}, "/fixture")).toBe(
      "/fixture/.cache/opencode/quota-export.json",
    )
    expect(exportPath({ XDG_CACHE_HOME: "/cache" }, "/fixture")).toBe(
      "/cache/opencode/quota-export.json",
    )
  })
  test("loader reads JSON only and turns file/JSON errors into unknown data", async () => {
    let reads = 0
    const deps = {
      now: () => NOW,
      readExport: async (path: string) => {
        expect(path).toBe("/fixture/export.json")
        reads++
        return JSON.stringify(snapshot())
      },
    }
    expect(state(await loadQuotaExport(deps, "/fixture/export.json"))).toBe(
      "available",
    )
    expect(reads).toBe(1)
    for (const readExport of [
      async () => "not json",
      async () => {
        throw new Error("fixture")
      },
    ])
      expect(
        await loadQuotaExport({ ...deps, readExport }, "/fixture/export.json"),
      ).toBeUndefined()
  })
  test("an export version this reader does not know is unknown", () => {
    expect(state({ ...snapshot(), version: 4 })).toBe("unknown")
  })
  test("real file reader uses only an isolated synthetic export", async () => {
    const dir = await mkdtemp(join(tmpdir(), "quota-fixture-"))
    try {
      const path = join(dir, "quota-export.json")
      await writeFile(path, JSON.stringify(snapshot()))
      expect(state(await loadQuotaExport(dependencies, path))).toBe("available")
      expect(await readFile(path, "utf8")).toBe(JSON.stringify(snapshot()))
    } finally {
      await rm(dir, { recursive: true })
    }
  })
})

// Quota 6's export (v3): rows carry a stable id and the login's account text
// instead of a connection ID. Shapes follow its quota-export.ts.
describe("Quota 6 public JSON", () => {
  const work: AccountProof = { ...account, label: "Work" }
  const v3row = (
    id: string,
    window: string | undefined,
    percentRemaining = 90,
    // null: a login without account text.
    login: string | null = "Work",
  ) => ({
    id,
    name: `Claude${login ? ` (${login})` : ""} ${window ?? id}`,
    ...(login === null ? {} : { account: login }),
    resultType: "quota",
    acquisitionMethod: "remote_api",
    ownership: "maintained",
    authority: "provider_reported",
    ...(window === undefined ? {} : { window }),
    resetAt: (NOW + 3_600_000) / 1000,
    renderType: "percent",
    percentRemaining,
  })
  const claude = (login: string | null, fiveHour = 90, weekly = 90) => [
    v3row("anthropic.five_hour", "5h", fiveHour, login),
    v3row("anthropic.weekly", "Weekly", weekly, login),
  ]
  const v3 = (providers: Record<string, unknown>) => ({
    version: 3,
    exportedAt: NOW / 1000,
    fromCache: true,
    cacheAgeSeconds: 0,
    providers,
  })
  const read = (entries: unknown[], a: AccountProof = work, id = "anthropic") =>
    readQuota(v3({ [id]: provider(entries as any) }), a, NOW).state

  test("a labelled login reads only the rows of its own account", () => {
    const entries = [...claude("Work", 0), ...claude("Home")]
    expect(read(entries)).toBe("exhausted")
    expect(read(entries, { ...account, label: "Home" })).toBe("available")
    expect(read(claude("Work", 90, 0))).toBe("exhausted")
  })
  test("model-specific, extra-usage and code-review rows never decide", () => {
    const extra = [
      v3row("anthropic.weekly_fable", "Weekly", 0),
      v3row("anthropic.extra_usage", "Monthly", 0),
      v3row("openai.code_review", "Code Review", 0),
    ]
    expect(read([...claude("Work"), ...extra])).toBe("available")
    expect(read(extra)).toBe("unknown")
  })
  test("a login whose rows are missing proves nothing from another login's", () => {
    expect(read(claude("Home", 0))).toBe("unknown")
    expect(read(claude(null, 0))).toBe("unknown")
  })
  test("without a label only the integration's sole login owns the rows", () => {
    expect(read(claude(null, 0), account)).toBe("unknown")
    expect(read(claude(null, 0), { ...account, sole: true })).toBe("exhausted")
    expect(read(claude("Work", 0), { ...account, sole: true })).toBe(
      "exhausted",
    )
  })
  test("two rows for one window are logins Quota cannot tell apart", () => {
    const sole = { ...account, sole: true }
    expect(read([...claude(null), ...claude(null, 0)], sole)).toBe("unknown")
    // A label that is the prefix of another login's account text.
    expect(read([...claude("Work"), ...claude("Work (old)", 0)])).toBe(
      "unknown",
    )
  })
  test("ChatGPT rows carry the plan after the label", () => {
    const a = {
      ...account,
      providerID: "openai",
      connectionID: "fixture-chatgpt",
      methodID: "chatgpt-browser",
    }
    const rows = (login: string, fiveHour: number) => [
      v3row("openai.five_hour", "5h", fiveHour, login),
      v3row("openai.weekly", "Weekly", 90, login),
    ]
    expect(
      read(rows("Work (Plus)", 0), { ...a, label: "Work" }, "openai"),
    ).toBe("exhausted")
    expect(
      read(rows("Workshop (Plus)", 0), { ...a, label: "Work" }, "openai"),
    ).toBe("unknown")
    expect(read(rows("Plus", 0), { ...a, sole: true }, "openai")).toBe(
      "exhausted",
    )
  })
  test("xAI's weekly credits row decides its pool; a monthly one does not", () => {
    const a = {
      ...account,
      providerID: "xai",
      connectionID: "fixture-grok",
      methodID: "device",
      sole: true,
    }
    const credits = (window: string, percent: number) => [
      v3row("xai.credits", window, percent, "SuperGrok"),
    ]
    expect(read(credits("Weekly", 79), a, "xai")).toBe("available")
    expect(read(credits("Weekly", 0), a, "xai")).toBe("exhausted")
    expect(read(credits("Monthly", 0), a, "xai")).toBe("unknown")
  })
  test("Quota 5 rows bound by connection ID do not count in a v3 export", () => {
    expect(
      read([row("5h", 0), row("Weekly")], { ...account, sole: true }),
    ).toBe("unknown")
  })
  test("v3 keeps the freshness rules: an empty window holds until its reset", () => {
    const stale = (percent: number) =>
      readQuota(
        v3({
          anthropic: {
            ...provider(claude("Work", percent) as any),
            fetchedAt: (NOW - 10 * QUOTA_MAX_AGE_MS) / 1000,
          },
        }),
        work,
        NOW,
      )
    expect(stale(0)).toEqual({
      state: "exhausted",
      observedAt: NOW - 10 * QUOTA_MAX_AGE_MS,
      resetAt: NOW + 3_600_000,
    })
    expect(stale(50).state).toBe("unknown")
  })
})
