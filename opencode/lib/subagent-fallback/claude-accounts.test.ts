import { describe, expect, test } from "bun:test"
import {
  AccountError,
  AccountRouter,
  accountOf,
  login,
  loginSubscription,
  parseAccounts,
  type ClaudeAccountsContext,
  type RoutedRequest,
} from "./claude-accounts"
import type { ModelRef } from "./policy"

const SUB = { suffix: "sub", label: "Sub OAuth" }
const ACCOUNTS = [SUB]
const OPUS: ModelRef = { providerID: "anthropic", id: "claude-opus-5-5" }
const OPUS_SUB: ModelRef = {
  providerID: "anthropic",
  id: "claude-opus-5-5-sub",
  variant: "high",
}
const HAIKU: ModelRef = { providerID: "anthropic", id: "claude-haiku-5-5" }
const URL_MESSAGES = "https://api.anthropic.com/v1/messages?beta=true"
// What the Claude login plugin leaves on a request it rewrote.
const PREPARED = {
  authorization: "Bearer fixture-main-access",
  "anthropic-beta": "oauth-2025-04-20,interleaved-thinking-2025-05-14",
}

function fixture() {
  const env = {
    connections: [
      {
        type: "credential",
        id: "fixture-main",
        label: "Main OAuth",
        method: "oauth",
      },
      {
        type: "credential",
        id: "fixture-sub",
        label: "Sub OAuth",
        method: "oauth",
      },
      { type: "env", name: "ANTHROPIC_API_KEY" },
    ] as Record<string, string>[],
    credentials: {
      "fixture-main": {
        type: "oauth",
        methodID: "claude-max",
        access: "fixture-main-access",
      },
      "fixture-sub": {
        type: "oauth",
        methodID: "claude-max",
        access: "fixture-sub-access",
      },
    } as Record<string, { type: string; methodID?: string; access?: string }>,
    sessionModel: OPUS_SUB as ModelRef | undefined,
    gets: 0,
    resolved: [] as string[],
  }
  const ctx: ClaudeAccountsContext = {
    integration: {
      get: async ({ integrationID }) => {
        env.gets++
        expect(integrationID).toBe("anthropic")
        return { data: { connections: env.connections } }
      },
      connection: {
        resolve: async (connection) => {
          env.resolved.push(connection.id!)
          return env.credentials[connection.id!]
        },
      },
    },
    session: { get: async () => ({ model: env.sessionModel }) },
  }
  return { env, ctx }
}
const request = (
  url = URL_MESSAGES,
  headers: Record<string, string> = PREPARED,
) =>
  new Request(url, {
    method: "POST",
    headers: { "content-type": "application/json", ...headers },
    body: '{"model":"claude-opus-5-5"}',
    redirect: "error",
  })
const event = (
  model: ModelRef = OPUS_SUB,
  kind = "primary",
  req = request(),
): RoutedRequest => ({ sessionID: "ses_fixture", model, kind, request: req })
const route = (
  ctx: ClaudeAccountsContext,
  e: RoutedRequest,
  router = new AccountRouter(ACCOUNTS),
  supported = true,
) => router.route(ctx, e, supported)
const bearer = (e: RoutedRequest) => e.request.headers.get("authorization")

describe("claudeAccounts option", () => {
  test("keeps every entry; one without a usable label keeps an empty one", () => {
    expect(
      parseAccounts({
        sub: "Sub OAuth",
        team2: " Team OAuth ",
        blank: " ",
        number: 7,
        "": "ignored",
      }),
    ).toEqual([
      { suffix: "sub", label: "Sub OAuth" },
      { suffix: "team2", label: "Team OAuth" },
      { suffix: "blank", label: "" },
      { suffix: "number", label: "" },
    ])
    expect(parseAccounts(undefined)).toEqual([])
    expect(parseAccounts({})).toEqual([])
  })
  test("an option that is not a map is refused", () => {
    for (const option of [null, "sub", ["sub"], 7])
      expect(() => parseAccounts(option)).toThrow(AccountError)
  })
  test("a router for a malformed option stops every Claude subscription request", async () => {
    expect(AccountRouter.fromOption(undefined).active).toBe(false)
    expect(AccountRouter.fromOption({ sub: "Sub OAuth" }).active).toBe(true)
    const router = AccountRouter.fromOption("sub")
    expect(router.active).toBe(true)
    for (const model of [OPUS, OPUS_SUB, HAIKU]) {
      const { env, ctx } = fixture()
      const e = event(model)
      await expect(route(ctx, e, router)).rejects.toThrow(
        "claudeAccounts must map",
      )
      expect(env.resolved).toEqual([])
      expect(bearer(e)).toBe("Bearer fixture-main-access")
    }
    const { ctx } = fixture()
    expect(
      await route(
        ctx,
        event({ providerID: "openai", id: "gpt-6.1-sol" }),
        router,
      ),
    ).toBeUndefined()
  })
  test("an alias of provider anthropic names its account; the longest suffix wins", () => {
    expect(accountOf(OPUS_SUB, ACCOUNTS)).toBe(SUB)
    expect(accountOf(OPUS, ACCOUNTS)).toBeUndefined()
    expect(
      accountOf(
        { providerID: "anthropic-credit-sub", id: "claude-opus-5-5-sub" },
        ACCOUNTS,
      ),
    ).toBeUndefined()
    expect(
      accountOf({ providerID: "anthropic", id: "-sub" }, ACCOUNTS),
    ).toBeUndefined()
    expect(accountOf(undefined, ACCOUNTS)).toBeUndefined()
    const b = { suffix: "b", label: "B" }
    expect(accountOf(OPUS_SUB, [b, SUB])).toBe(SUB)
  })
})

describe("saved login", () => {
  test("resolves the labelled login without activating it", async () => {
    const { env, ctx } = fixture()
    expect(await login(ctx, SUB)).toEqual({
      connectionID: "fixture-sub",
      access: "fixture-sub-access",
      methodID: "claude-max",
    })
    expect(env.resolved).toEqual(["fixture-sub"])
    expect(await loginSubscription(ctx, SUB)).toEqual({
      proof: {
        connectionID: "fixture-sub",
        providerID: "anthropic",
        methodID: "claude-max",
        type: "oauth",
      },
      access: "fixture-sub-access",
    })
  })
  test("a missing label, login, duplicate or non-subscription login is refused", async () => {
    const unlabelled = fixture()
    await expect(
      login(unlabelled.ctx, { suffix: "sub", label: "" }),
    ).rejects.toThrow('gives the "sub" models no login label')
    expect(unlabelled.env.gets).toBe(0)
    const missing = fixture()
    missing.env.connections = missing.env.connections.filter(
      (c) => c.label !== "Sub OAuth",
    )
    await expect(login(missing.ctx, SUB)).rejects.toThrow(
      'no saved Claude login is labelled "Sub OAuth"',
    )
    const twice = fixture()
    twice.env.connections.push({
      type: "credential",
      id: "fixture-sub-2",
      label: "Sub OAuth",
      method: "oauth",
    })
    await expect(login(twice.ctx, SUB)).rejects.toThrow("several saved")
    const key = fixture()
    key.env.connections[1].method = "key"
    await expect(login(key.ctx, SUB)).rejects.toThrow("no saved")
    for (const credential of [
      undefined,
      { type: "key", access: "x" },
      { type: "oauth", methodID: "console", access: "x" },
      { type: "oauth", methodID: "claude-max", access: "" },
    ]) {
      const f = fixture()
      f.env.credentials["fixture-sub"] = credential as any
      await expect(login(f.ctx, SUB)).rejects.toThrow(
        "not a Claude Pro/Max login",
      )
    }
  })
})

describe("request routing", () => {
  test("an alias request carries the named login's token on the same Request", async () => {
    const { ctx } = fixture()
    const e = event()
    const original = e.request
    expect(await route(ctx, e)).toBe(SUB)
    expect(e.request).toBe(original)
    expect(bearer(e)).toBe("Bearer fixture-sub-access")
    expect(await e.request.text()).toBe('{"model":"claude-opus-5-5"}')
  })
  test("the active login's models, other providers and an empty option are left alone", async () => {
    for (const [model, accounts] of [
      [OPUS, ACCOUNTS],
      [{ providerID: "openai", id: "gpt-6.1-sol-sub" }, ACCOUNTS],
      [OPUS_SUB, []],
    ] as const) {
      const { env, ctx } = fixture()
      env.sessionModel = OPUS
      const e = event(model)
      expect(await route(ctx, e, new AccountRouter(accounts))).toBeUndefined()
      expect(bearer(e)).toBe("Bearer fixture-main-access")
      expect(env.gets).toBe(0)
    }
  })
  test("side requests follow the session's account; the session's own requests follow their model", async () => {
    for (const kind of ["compaction", "title"]) {
      const { ctx } = fixture()
      const e = event(HAIKU, kind)
      expect(await route(ctx, e)).toBe(SUB)
      expect(bearer(e)).toBe("Bearer fixture-sub-access")
    }
    for (const kind of ["primary", "generate"]) {
      const { ctx } = fixture()
      expect(await route(ctx, event(OPUS, kind))).toBeUndefined()
    }
    const mainSession = fixture()
    mainSession.env.sessionModel = OPUS
    expect(
      await route(mainSession.ctx, event(HAIKU, "compaction")),
    ).toBeUndefined()
  })
  test("a session on the default model follows the account of its last own request", async () => {
    const { env, ctx } = fixture()
    env.sessionModel = undefined
    const router = new AccountRouter(ACCOUNTS)
    expect(await route(ctx, event(HAIKU, "compaction"), router)).toBeUndefined()
    await route(ctx, event(OPUS_SUB, "primary"), router)
    const side = event(HAIKU, "compaction")
    expect(await route(ctx, side, router)).toBe(SUB)
    expect(bearer(side)).toBe("Bearer fixture-sub-access")
    await route(ctx, event(OPUS, "generate"), router)
    expect(await route(ctx, event(HAIKU, "compaction"), router)).toBeUndefined()
    await route(ctx, event(OPUS_SUB, "primary"), router)
    await route(
      ctx,
      event({ providerID: "openai", id: "gpt-6.1-sol" }, "primary"),
      router,
    )
    expect(await route(ctx, event(HAIKU, "compaction"), router)).toBeUndefined()
  })
  test("a request the login plugin did not prepare, or another host, stops before any token is read", async () => {
    const { authorization } = PREPARED
    for (const req of [
      request("https://example.com/v1/messages"),
      request("http://api.anthropic.com/v1/messages"),
      request(URL_MESSAGES, {}),
      request(URL_MESSAGES, { ...PREPARED, authorization: "Basic x" }),
      request(URL_MESSAGES, { authorization }),
      request(URL_MESSAGES, { ...PREPARED, "x-api-key": "fixture-key" }),
    ]) {
      const { env, ctx } = fixture()
      const e = event(OPUS_SUB, "primary", req)
      const before = bearer(e)
      await expect(route(ctx, e)).rejects.toBeInstanceOf(AccountError)
      expect(env.resolved).toEqual([])
      expect(bearer(e)).toBe(before)
    }
  })
  test("a missing login, an unlabelled entry or an unchecked OpenCode release stops the request", async () => {
    const missing = fixture()
    missing.env.connections = []
    const e = event()
    await expect(route(missing.ctx, e)).rejects.toThrow(
      "Claude account: no saved",
    )
    expect(bearer(e)).toBe("Bearer fixture-main-access")
    const unlabelled = fixture()
    await expect(
      route(
        unlabelled.ctx,
        event(),
        new AccountRouter(parseAccounts({ sub: 7 })),
      ),
    ).rejects.toThrow("no login label")
    const old = fixture()
    await expect(
      route(old.ctx, event(), new AccountRouter(ACCOUNTS), false),
    ).rejects.toThrow("unsupported OpenCode version")
    expect(old.env.resolved).toEqual([])
  })
})
