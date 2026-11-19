import { expect, test } from "bun:test"
import type { ClaudeAccountsContext } from "../claude-logins/accounts"
import { loginSubscription } from "./claude-logins"

test("a saved login is the subscription its connection proves, without activating it", async () => {
  const resolved: string[] = []
  const ctx: ClaudeAccountsContext = {
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
        resolve: async (connection) => {
          resolved.push(connection.id!)
          return {
            type: "oauth",
            methodID: "claude-max",
            access: "fixture-sub-access",
          }
        },
      },
    },
    session: { get: async () => ({}) },
  }
  expect(
    await loginSubscription(ctx, { suffix: "sub", label: "Sub OAuth" }),
  ).toEqual({
    proof: {
      connectionID: "fixture-sub",
      providerID: "anthropic",
      methodID: "claude-max",
      type: "oauth",
    },
    access: "fixture-sub-access",
  })
  expect(resolved).toEqual(["fixture-sub"])
})
