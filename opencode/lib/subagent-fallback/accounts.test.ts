import { describe, expect, test } from "bun:test"
import { subscription, type AccountsContext } from "./accounts"

function fixture(providerID = "anthropic") {
  const state = {
    provider: {
      package: `@opencode/ai/providers/${providerID}`,
      integrationID: providerID,
    },
    connection: { type: "credential", id: "fixture", method: "oauth" } as any,
    credential: {
      type: "oauth",
      access: "fixture-token",
      methodID: providerID === "anthropic" ? "claude-max" : "chatgpt-browser",
      metadata: { accountID: "fixture-account" },
    } as any,
    resolves: 0,
  }
  const ctx: AccountsContext = {
    provider: { get: async () => ({ data: state.provider }) },
    integration: {
      connection: {
        active: async () => state.connection,
        resolve: async () => {
          state.resolves++
          return state.credential
        },
      },
    },
  }
  return { state, ctx }
}

describe("native subscription identity", () => {
  test("accepts Claude Max and both ChatGPT login methods", async () => {
    for (const [provider, method] of [
      ["anthropic", "claude-max"],
      ["openai", "chatgpt-browser"],
      ["openai", "chatgpt-headless"],
    ]) {
      const { ctx, state } = fixture(provider)
      state.credential.methodID = method
      const auth = await subscription(ctx, provider)
      expect(auth?.proof).toEqual({
        connectionID: "fixture",
        providerID: provider,
        methodID: method,
        type: "oauth",
      })
      expect(auth?.access).toBe("fixture-token")
    }
  })
  test("rejects unknown providers, nonnative packages and redirected integrations", async () => {
    const { ctx, state } = fixture()
    expect(await subscription(ctx, "other")).toBeUndefined()
    state.provider.package = "third-party"
    expect(await subscription(ctx, "anthropic")).toBeUndefined()
    state.provider.package = "@opencode/ai/providers/anthropic"
    state.provider.integrationID = "other"
    expect(await subscription(ctx, "anthropic")).toBeUndefined()
    expect(state.resolves).toBe(0)
  })
  test("rejects env/API/absent connections before resolving", async () => {
    for (const connection of [
      undefined,
      { type: "env", id: "fixture", method: "oauth" },
      { type: "credential", id: "fixture", method: "api" },
      { type: "credential", method: "oauth" },
    ]) {
      const { ctx, state } = fixture()
      state.connection = connection
      expect(await subscription(ctx, "anthropic")).toBeUndefined()
      expect(state.resolves).toBe(0)
    }
  })
  test("rejects missing access, wrong credential type or login method", async () => {
    for (const change of [
      { access: undefined },
      { type: "api" },
      { methodID: "console-api" },
      { methodID: undefined },
    ]) {
      const { ctx, state } = fixture()
      Object.assign(state.credential, change)
      expect(await subscription(ctx, "anthropic")).toBeUndefined()
    }
  })
  test("ChatGPT requires a nonempty native account ID", async () => {
    for (const metadata of [
      undefined,
      {},
      { accountID: "" },
      { accountID: 1 },
    ]) {
      const { ctx, state } = fixture("openai")
      state.credential.metadata = metadata
      expect(await subscription(ctx, "openai")).toBeUndefined()
    }
  })
})
