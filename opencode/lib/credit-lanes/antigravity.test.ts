import { describe, expect, test } from "bun:test"
import {
  ANTIGRAVITY_DEFAULT_PROJECT_ID,
  ANTIGRAVITY_ENDPOINT,
  ANTIGRAVITY_MANIFEST_URL,
  classifyFamily,
  createAntigravityCollector,
  hubUserAgent,
  parseManifestVersion,
  parseRefreshParts,
  summarizeAvailableModels,
  toAntigravityQuotaV1,
  type IntegrationContext,
} from "./antigravity"

const NOW = new Date("2026-10-31T08:00:00.000Z")

describe("parseRefreshParts", () => {
  test("splits refresh token, project id and managed project id", () => {
    expect(parseRefreshParts("tok|proj|mproj")).toEqual({
      refreshToken: "tok",
      projectId: "proj",
      managedProjectId: "mproj",
    })
    expect(parseRefreshParts("tok||mproj")).toEqual({
      refreshToken: "tok",
      managedProjectId: "mproj",
    })
    expect(parseRefreshParts(undefined)).toEqual({ refreshToken: "" })
  })
})

describe("parseManifestVersion & hubUserAgent", () => {
  test("accepts strict versions at or above 2.23.0 and builds the Hub User-Agent", () => {
    expect(parseManifestVersion("version: 2.24.0\nfiles:\n")).toBe("2.24.0")
    expect(parseManifestVersion("version: '2.23.1' # comment")).toBe("2.23.1")
    expect(parseManifestVersion("version: 2.22.9")).toBeUndefined()
    expect(parseManifestVersion("version: 2.24.0-beta.1")).toBeUndefined()
    expect(hubUserAgent("2.24.0")).toBe(
      "antigravity/hub/2.24.0 (aidev_client; os_type=darwin; arch=arm64; cl=1000335682)",
    )
    expect(hubUserAgent("2.25.0")).toBe(
      "antigravity/hub/2.25.0 (aidev_client; os_type=darwin; arch=arm64)",
    )
  })
})

describe("classifyFamily & summarizeAvailableModels", () => {
  test("classifies Gemini Pro, Gemini Flash and Claude while ignoring image and disabled models", () => {
    expect(classifyFamily("gemini-4-argon-high", "Gemini 4 Argon")).toBe(
      "gemini-pro",
    )
    expect(classifyFamily("gemini-3.8-flash-medium", "Gemini 3.8 Flash")).toBe(
      "gemini-flash",
    )
    expect(classifyFamily("claude-sonnet-4-6", "Claude Sonnet 4.6")).toBe(
      "claude",
    )
    expect(classifyFamily("gemini-3-pro-image")).toBeUndefined()
    expect(classifyFamily("gemini-3-flash-disabled")).toBeUndefined()
    expect(classifyFamily("gpt-oss-120b-medium")).toBeUndefined()
  })

  test("aggregates selectable models by family in Pro → Flash → Claude order, taking the lowest fraction", () => {
    const payload = {
      agentModelSorts: [
        {
          groups: [
            {
              modelIds: [
                "gemini-4-argon-high",
                "gemini-3.8-flash-medium",
                "claude-sonnet-4-6",
                "claude-opus-4-6-thinking",
              ],
            },
          ],
        },
      ],
      tieredModelIds: {
        flash: ["gemini-3.8-flash-high"],
      },
      models: {
        "gemini-4-argon-high": {
          displayName: "Gemini 4 Argon (High)",
          quotaInfo: {
            remainingFraction: 0.824,
            resetTime: "2026-10-31T12:00:00Z",
          },
        },
        "gemini-3.8-flash-medium": {
          displayName: "Gemini 3.8 Flash (Medium)",
          quotaInfo: {
            remainingFraction: 1,
            resetTime: "2026-10-31T13:00:00Z",
          },
        },
        "gemini-3.8-flash-high": {
          displayName: "Gemini 3.8 Flash (High)",
          quotaInfo: {
            remainingFraction: 0.65,
            resetTime: "2026-10-31T11:30:00Z",
          },
        },
        "claude-sonnet-4-6": {
          displayName: "Claude Sonnet 4.6",
          quotaInfo: {
            remainingFraction: 0.4,
            resetTime: "2026-11-01T00:00:00Z",
          },
        },
        "claude-opus-4-6-thinking": {
          displayName: "Claude Opus 4.6",
          // Missing remainingFraction means 0% in protobuf JSON.
          quotaInfo: {
            resetTime: "2026-11-01T00:00:00Z",
          },
        },
        "unselectable-gemini-pro": {
          displayName: "Gemini Obsolete",
          quotaInfo: {
            remainingFraction: 0,
            resetTime: "2026-10-31T09:00:00Z",
          },
        },
      },
    }

    const groups = summarizeAvailableModels(payload)
    expect(groups).toEqual([
      {
        family: "gemini-pro",
        name: "Gemini Pro",
        label: "Pro:",
        percentRemaining: 82,
        resetTimeIso: "2026-10-31T12:00:00.000Z",
      },
      {
        family: "gemini-flash",
        name: "Gemini Flash",
        label: "Flash:",
        percentRemaining: 65,
        resetTimeIso: "2026-10-31T11:30:00.000Z",
      },
      {
        family: "claude",
        name: "Claude",
        label: "Claude:",
        percentRemaining: 0,
        resetTimeIso: "2026-11-01T00:00:00.000Z",
      },
    ])

    const v1 = toAntigravityQuotaV1(groups, NOW)
    expect(v1.version).toBe("quota-v1")
    expect(v1.entries).toEqual([
      {
        kind: "percent",
        name: "Gemini Pro",
        resultType: "quota",
        percentRemaining: 82,
        label: "Pro:",
        resetTimeIso: "2026-10-31T12:00:00.000Z",
        observedAtIso: "2026-10-31T08:00:00.000Z",
      },
      {
        kind: "percent",
        name: "Gemini Flash",
        resultType: "quota",
        percentRemaining: 65,
        label: "Flash:",
        resetTimeIso: "2026-10-31T11:30:00.000Z",
        observedAtIso: "2026-10-31T08:00:00.000Z",
      },
      {
        kind: "percent",
        name: "Claude",
        resultType: "quota",
        percentRemaining: 0,
        label: "Claude:",
        resetTimeIso: "2026-11-01T00:00:00.000Z",
        observedAtIso: "2026-10-31T08:00:00.000Z",
      },
    ])
  })
})

describe("createAntigravityCollector", () => {
  const makeCtx = (
    credential?: {
      type: string
      methodID?: string
      access?: string
      refresh?: string
    },
  ): IntegrationContext => ({
    integration: {
      connection: {
        active: async (id) =>
          id === "google" && credential
            ? { type: "credential", id: "conn-1", method: "oauth" }
            : undefined,
        resolve: async () => credential,
      },
    },
  })

  test("returns undefined when no Antigravity OAuth connection is active", async () => {
    const collect = createAntigravityCollector(makeCtx(undefined))
    expect(await collect()).toBeUndefined()

    const otherMethod = createAntigravityCollector(
      makeCtx({ type: "oauth", methodID: "gemini-cli", access: "tok" }),
    )
    expect(await otherMethod()).toBeUndefined()
  })

  test("falls back to listed saved OAuth connections when active() is unset", async () => {
    const collect = createAntigravityCollector(
      {
        integration: {
          get: async () => ({
            data: {
              connections: [
                { type: "credential", id: "conn-saved", method: "oauth" },
              ],
            },
          }),
          connection: {
            active: async () => undefined,
            resolve: async () => ({
              type: "oauth",
              methodID: "antigravity",
              access: "access-saved",
              refresh: "refresh-saved||proj-saved",
            }),
          },
        },
      },
      {
        now: () => NOW,
        readAccounts: async () => [],
        fetch: (async (input: RequestInfo | URL) => {
          const url = String(input)
          if (url === `${ANTIGRAVITY_ENDPOINT}/v1internal:fetchAvailableModels`) {
            return new Response(
              JSON.stringify({
                models: {
                  "gemini-4-argon-high": {
                    quotaInfo: { remainingFraction: 0.9 },
                  },
                },
              }),
              { status: 200 },
            )
          }
          return new Response("", { status: 500 })
        }) as typeof globalThis.fetch,
      },
    )
    const res = await collect()
    expect(res?.entries[0]).toMatchObject({
      name: "Gemini Pro",
      percentRemaining: 90,
    })
  })

  test("uses packed managedProjectId when present and fetches quota", async () => {
    const calls: Array<{ url: string; body?: string; ua?: string | null }> = []
    const collect = createAntigravityCollector(
      makeCtx({
        type: "oauth",
        methodID: "antigravity",
        access: "access-1",
        refresh: "refresh-1||managed-proj-1",
      }),
      {
        now: () => NOW,
        readAccounts: async () => [],
        fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
          const url = String(input)
          const headers = new Headers(init?.headers)
          calls.push({
            url,
            body: typeof init?.body === "string" ? init.body : undefined,
            ua: headers.get("user-agent"),
          })
          if (url === ANTIGRAVITY_MANIFEST_URL) {
            return new Response("version: 2.24.0\n", { status: 200 })
          }
          if (url === `${ANTIGRAVITY_ENDPOINT}/v1internal:fetchAvailableModels`) {
            return new Response(
              JSON.stringify({
                models: {
                  "gemini-4-argon-high": {
                    displayName: "Gemini 4 Argon",
                    quotaInfo: {
                      remainingFraction: 0.75,
                      resetTime: "2026-10-31T12:00:00Z",
                    },
                  },
                },
              }),
              { status: 200, headers: { "content-type": "application/json" } },
            )
          }
          return new Response("not found", { status: 404 })
        }) as typeof globalThis.fetch,
      },
    )

    const result = await collect()
    expect(result?.version).toBe("quota-v1")
    expect(result?.entries).toHaveLength(1)
    expect(result?.entries[0]).toMatchObject({
      kind: "percent",
      name: "Gemini Pro",
      percentRemaining: 75,
    })
    expect(calls.map((c) => c.url)).toEqual([
      ANTIGRAVITY_MANIFEST_URL,
      `${ANTIGRAVITY_ENDPOINT}/v1internal:fetchAvailableModels`,
    ])
    expect(calls[1].body).toBe(JSON.stringify({ project: "managed-proj-1" }))
  })

  test("discovers project via loadCodeAssist when not in refresh parts or stored accounts, falling back to default", async () => {
    const bodies: string[] = []
    const collect = createAntigravityCollector(
      makeCtx({
        type: "oauth",
        methodID: "antigravity",
        access: "access-2",
        refresh: "refresh-2",
      }),
      {
        now: () => NOW,
        readAccounts: async () => [],
        fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
          const url = String(input)
          if (typeof init?.body === "string") bodies.push(init.body)
          if (url === ANTIGRAVITY_MANIFEST_URL)
            return new Response("", { status: 500 })
          if (url === `${ANTIGRAVITY_ENDPOINT}/v1internal:loadCodeAssist`) {
            return new Response(
              JSON.stringify({
                cloudaicompanionProject: { id: "discovered-proj" },
              }),
              { status: 200 },
            )
          }
          if (url === `${ANTIGRAVITY_ENDPOINT}/v1internal:fetchAvailableModels`) {
            return new Response(
              JSON.stringify({
                models: {
                  "claude-sonnet-4-6": {
                    quotaInfo: { remainingFraction: 0.5 },
                  },
                },
              }),
              { status: 200 },
            )
          }
          return new Response("", { status: 404 })
        }) as typeof globalThis.fetch,
      },
    )

    const res = await collect()
    expect(res?.entries[0]).toMatchObject({
      name: "Claude",
      percentRemaining: 50,
    })
    expect(bodies).toContain(JSON.stringify({ project: "discovered-proj" }))

    // Default project fallback when loadCodeAssist fails
    let lastBody = ""
    const fallbackCollect = createAntigravityCollector(
      makeCtx({
        type: "oauth",
        methodID: "antigravity",
        access: "access-3",
        refresh: "refresh-3",
      }),
      {
        now: () => NOW,
        readAccounts: async () => [],
        fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
          const url = String(input)
          if (url === `${ANTIGRAVITY_ENDPOINT}/v1internal:fetchAvailableModels`) {
            lastBody = String(init?.body ?? "")
            return new Response(
              JSON.stringify({
                models: {
                  "gemini-3.8-flash-medium": {
                    quotaInfo: { remainingFraction: 0.9 },
                  },
                },
              }),
              { status: 200 },
            )
          }
          return new Response("", { status: 500 })
        }) as typeof globalThis.fetch,
      },
    )
    await fallbackCollect()
    expect(lastBody).toBe(
      JSON.stringify({ project: ANTIGRAVITY_DEFAULT_PROJECT_ID }),
    )
  })
})
