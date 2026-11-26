import { expect, test } from "bun:test"

type Options = Record<string, any>
type Entry = string | { package: string; options?: Options }
type Config = {
  plugins: Entry[]
  agents?: Record<string, { model?: string }>
  providers?: Record<string, unknown>
}

const FALLBACK_PACKAGE = "@craftsamo/opencode-model-fallback"
const QUOTA_PACKAGE = "@slkiser/opencode-quota@"
const STEPS = "./lib/fallback-steps"
const STEP_FORMAT = /^([^/#\s]+)\/([^#\s]+)(#\S+)?$/
const BUILT_IN_PROVIDERS = ["anthropic", "openai", "xai", "google"]

const nameOf = (entry: Entry) =>
  typeof entry === "string" ? entry : entry.package
const withoutVariant = (model: string) => model.split("#")[0]

const config = Bun.JSONC.parse(
  await Bun.file(new URL("../../opencode.jsonc", import.meta.url)).text(),
) as Config
const names = config.plugins.map(nameOf)
const fallbackAt = names.findIndex((name) =>
  name.startsWith(`${FALLBACK_PACKAGE}@`),
)
const optionsAt = (index: number): Options => {
  const entry = config.plugins[index]
  return typeof entry === "string" ? {} : (entry.options ?? {})
}
const routes: Record<string, string[]> = optionsAt(fallbackAt).routes ?? {}

test("opencode.jsonc lists the model fallback last, after Quota, at the version package.json depends on", async () => {
  const pkg = JSON.parse(
    await Bun.file(new URL("../../package.json", import.meta.url)).text(),
  ) as { dependencies: Record<string, string> }
  const quota = names.findIndex((name) => name.startsWith(QUOTA_PACKAGE))
  expect(fallbackAt).toBeGreaterThanOrEqual(0)
  expect(quota).toBeGreaterThanOrEqual(0)
  expect(fallbackAt).toBeGreaterThan(quota)
  expect(fallbackAt).toBe(names.length - 1)
  expect(names[fallbackAt]).toBe(
    `${FALLBACK_PACKAGE}@${pkg.dependencies[FALLBACK_PACKAGE]}`,
  )
})

test("opencode.jsonc lists lib/fallback-steps with credit lanes only", () => {
  const at = names.indexOf(STEPS)
  expect(at).toBeGreaterThanOrEqual(0)
  expect(optionsAt(at).creditLanes).toBeDefined()
  expect(optionsAt(at).claudeAccounts).toBeUndefined()
})

test("every route step is provider/model[#variant] on a known provider", () => {
  const lanes: string[] = optionsAt(names.indexOf(STEPS)).creditLanes ?? []
  const known = new Set([
    ...lanes,
    ...Object.keys(config.providers ?? {}),
    ...BUILT_IN_PROVIDERS,
  ])
  expect(Object.keys(routes).length).toBeGreaterThan(0)
  for (const [role, steps] of Object.entries(routes))
    for (const step of steps) {
      const match = STEP_FORMAT.exec(step)
      expect(`${role}: ${step} ${match ? "ok" : "malformed"}`).toBe(
        `${role}: ${step} ok`,
      )
      const provider = match![1]
      expect(provider).not.toBe("anthropic-credit-sub")
      if (provider === "anthropic")
        expect(match![2]).not.toMatch(/-(sub|main)$/)
      expect(`${role}: ${provider} ${known.has(provider)}`).toBe(
        `${role}: ${provider} true`,
      )
    }
})

test("every routed role's agent names its route's first step as its model", async () => {
  for (const [role, steps] of Object.entries(routes)) {
    const first = steps[0]
    const file = Bun.file(new URL(`../../agents/${role}.md`, import.meta.url))
    const named = (await file.exists())
      ? (await file.text()).match(/^model:\s*(\S+)\s*$/m)?.[1]
      : config.agents?.[role]?.model
    // A step without a variant stands for every variant.
    const model = first.includes("#") ? named : named && withoutVariant(named)
    expect(`${role}: ${model}`).toBe(`${role}: ${first}`)
  }
})

test("opencode.jsonc declares the logged-in providers, so Quota writes no provider entry", () => {
  expect((config as Record<string, unknown>).provider).toBeUndefined()
  for (const provider of ["anthropic", "openai", "xai"])
    expect(Object.keys(config.providers ?? {})).toContain(provider)
})

test("no plugin entry loads an obsolete local plugin", () => {
  expect(names.filter((name) => name.includes("subagent-fallback"))).toEqual([])
  expect(names).not.toContain("./lib/claude-logins")
})
