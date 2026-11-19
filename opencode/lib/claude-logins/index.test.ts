import { describe, expect, test } from "bun:test"
import plugin, { setup } from "./index"
import type { ModelRef } from "./models"
import { SUPPORTED_VERSIONS, type RuntimeContext } from "./runtime"

const SONNET: ModelRef = { providerID: "anthropic", id: "claude-sonnet-5-5" }
const SONNET_SUB: ModelRef = { ...SONNET, id: "claude-sonnet-5-5-sub" }
const GPT: ModelRef = { providerID: "openai", id: "gpt-6.1-sol" }
const URL_MESSAGES = "https://api.anthropic.com/v1/messages?beta=true"

// As the Claude login plugin leaves it.
const prepared = () =>
  new Request(URL_MESSAGES, {
    method: "POST",
    headers: {
      authorization: "Bearer fixture-anthropic",
      "anthropic-beta": "oauth-2025-04-20",
    },
    body: "{}",
  })

function fixture(options: Record<string, unknown> = {}) {
  const env = {
    version: SUPPORTED_VERSIONS[0],
    hooks: [] as ((event: any) => Promise<void>)[],
    registered: 0,
    disposed: 0,
  }
  const ctx: RuntimeContext = {
    app: {
      get version() {
        return env.version
      },
    },
    options,
    integration: {
      get: async () => ({
        data: {
          connections: [
            {
              type: "credential",
              id: "fixture-sub",
              label: "Sub OAuth",
              method: "oauth",
            },
          ],
        },
      }),
      connection: {
        resolve: async () => ({
          type: "oauth",
          methodID: "claude-max",
          access: "fixture-anthropic-sub",
        }),
      },
    },
    session: {
      get: async () => ({ model: SONNET_SUB }),
      hook: async (_name, callback) => {
        env.registered++
        env.hooks.push(callback)
        return {
          dispose: async () => {
            env.disposed++
          },
        }
      },
    },
  }
  const fire = async (model: ModelRef, request = prepared()) => {
    const event = { sessionID: "ses_fixture", model, kind: "primary", request }
    for (const hook of env.hooks) await hook(event)
    return event
  }
  return { env, ctx, fire }
}
const bearer = (request: Request) => request.headers.get("authorization")

describe("claude-logins plugin", () => {
  test("has its own id", () => {
    expect(plugin.id).toBe("dotconfig.claude-logins")
    expect(plugin.setup).toBe(setup)
  })
  test("an alias request leaves with the named login's token on the same Request", async () => {
    const { ctx, fire } = fixture({ claudeAccounts: { sub: "Sub OAuth" } })
    await setup(ctx)
    const request = prepared()
    const event = await fire(SONNET_SUB, request)
    expect(event.request).toBe(request)
    expect(bearer(request)).toBe("Bearer fixture-anthropic-sub")
  })
  test("the active login's requests and other providers are unchanged", async () => {
    const { ctx, fire } = fixture({ claudeAccounts: { sub: "Sub OAuth" } })
    await setup(ctx)
    for (const model of [SONNET, GPT]) {
      const event = await fire(model)
      expect(bearer(event.request)).toBe("Bearer fixture-anthropic")
    }
  })
  test("without the option no hook is added; with it exactly one, disposed on cleanup", async () => {
    const plain = fixture()
    await setup(plain.ctx)
    expect(plain.env.registered).toBe(0)
    const routed = fixture({ claudeAccounts: { sub: "Sub OAuth" } })
    const cleanup = await setup(routed.ctx)
    expect(routed.env.registered).toBe(1)
    await cleanup()
    expect(routed.env.disposed).toBe(1)
  })
  test("an option that is not a map stops every Claude subscription request", async () => {
    const { ctx, fire } = fixture({ claudeAccounts: "sub" })
    await setup(ctx)
    for (const model of [SONNET, SONNET_SUB])
      await expect(fire(model)).rejects.toThrow(
        "Claude account: claudeAccounts must map",
      )
    const event = await fire(GPT)
    expect(bearer(event.request)).toBe("Bearer fixture-anthropic")
  })
  test("an unchecked OpenCode release stops an alias request", async () => {
    const { env, ctx, fire } = fixture({ claudeAccounts: { sub: "Sub OAuth" } })
    await setup(ctx)
    env.version = "0.0.0"
    await expect(fire(SONNET_SUB)).rejects.toThrow(
      "Claude account: unsupported OpenCode version",
    )
  })
})
