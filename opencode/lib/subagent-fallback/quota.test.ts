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
