import { expect, test } from "bun:test"

type Entry = string | { package: string; options?: Record<string, unknown> }

const LOGIN_PLUGIN = "@ex-machina/opencode-anthropic-auth@"
const NAME = (entry: Entry) =>
  typeof entry === "string" ? entry : entry.package

test("opencode.jsonc lists lib/claude-logins after the login plugin and with the same accounts as fallback-steps", async () => {
  const config = Bun.JSONC.parse(
    await Bun.file(new URL("../../opencode.jsonc", import.meta.url)).text(),
  ) as { plugins: Entry[] }
  const names = config.plugins.map(NAME)
  const login = names.findIndex((name) => name.startsWith(LOGIN_PLUGIN))
  const logins = names.indexOf("./lib/claude-logins")
  const steps = names.indexOf("./lib/fallback-steps")
  expect(login).toBeGreaterThanOrEqual(0)
  expect(logins).toBeGreaterThan(login)
  expect(steps).toBeGreaterThanOrEqual(0)
  const accounts = (entry: Entry) =>
    typeof entry === "string" ? undefined : entry.options?.claudeAccounts
  expect(accounts(config.plugins[logins])).toBeDefined()
  expect(accounts(config.plugins[logins])).toEqual(
    accounts(config.plugins[steps]),
  )
})
