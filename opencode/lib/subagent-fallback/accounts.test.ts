import { describe, expect, test } from "bun:test"
import {
  identify,
  subscription,
  type AccountsContext,
  type IdentityContext,
} from "./accounts"
import type { AccountProof } from "./policy"

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
  test("accepts Claude Max, both ChatGPT login methods and the xAI device login", async () => {
    for (const [provider, method] of [
      ["anthropic", "claude-max"],
      ["openai", "chatgpt-browser"],
      ["openai", "chatgpt-headless"],
      ["xai", "device"],
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
  test("xAI needs no account metadata, but only its device login qualifies", async () => {
    const { ctx, state } = fixture("xai")
    state.credential.methodID = "device"
    state.credential.metadata = undefined
    const auth = await subscription(ctx, "xai")
    expect(auth?.proof.methodID).toBe("device")
    expect(auth?.accountID).toBeUndefined()
    for (const methodID of ["browser", "api", "claude-max", undefined]) {
      state.credential.methodID = methodID
      expect(await subscription(ctx, "xai")).toBeUndefined()
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

describe("login identity for Quota 6 rows", () => {
  const proof: AccountProof = {
    connectionID: "fixture-a",
    providerID: "anthropic",
    methodID: "claude-max",
    type: "oauth",
  }
  const login = (id: string, label?: string, method = "oauth") => ({
    type: "credential",
    id,
    method,
    ...(label === undefined ? {} : { label }),
  })
  const ctx = (connections: unknown): IdentityContext => ({
    integration: {
      get: async ({ integrationID }) => {
        expect(integrationID).toBe("anthropic")
        return { data: { connections: connections as any } }
      },
    },
  })

  test("a label only this login carries names it", async () => {
    expect(
      await identify(
        ctx([login("fixture-a", " Work "), login("fixture-b", "Home")]),
        proof,
      ),
    ).toEqual({ ...proof, label: "Work" })
  })
  test("the only subscription login is sole, labelled or not", async () => {
    expect(
      await identify(
        ctx([login("fixture-a"), login("fixture-key", "Key", "api")]),
        proof,
      ),
    ).toEqual({ ...proof, sole: true })
    expect(await identify(ctx([login("fixture-a", "Work")]), proof)).toEqual({
      ...proof,
      label: "Work",
      sole: true,
    })
  })
  test("a shared, blank or missing label names nothing", async () => {
    for (const connections of [
      [login("fixture-a", "Work"), login("fixture-b", "Work ")],
      [login("fixture-a", "  "), login("fixture-b", "Home")],
      [login("fixture-a"), login("fixture-b")],
    ])
      expect(await identify(ctx(connections), proof)).toEqual(proof)
  })
  test("an unlisted login or an unreadable integration adds nothing", async () => {
    expect(await identify(ctx([login("fixture-b", "Work")]), proof)).toEqual(
      proof,
    )
    expect(await identify(ctx(undefined), proof)).toEqual(proof)
    const failing: IdentityContext = {
      integration: {
        get: async () => {
          throw new Error("fixture")
        },
      },
    }
    expect(await identify(failing, proof)).toEqual(proof)
  })
})
