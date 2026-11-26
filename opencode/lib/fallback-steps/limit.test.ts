import { describe, expect, test } from "bun:test"
import { readFile } from "node:fs/promises"
import {
  ANTIGRAVITY_MAX_WAIT_MS,
  ANTIGRAVITY_TOS_WAIT_MS,
  KEY_REFUSED_WAIT_MS,
} from "./limit"
import { LANE, savedFile, setup, useTempDir } from "./fixture"

useTempDir()

const options = { creditLanes: [LANE.provider] }
const LANE_MODEL = `${LANE.provider}/claude-opus-5-5#high`
const LOW_BALANCE = {
  type: "provider.unknown",
  status: 400,
  message: "Your credit balance is too low to access the Anthropic API.",
}
const NO_LIMIT = { limit: false }
const flush = () => new Promise((resolve) => setTimeout(resolve, 0))

describe("a credit lane's empty balance", () => {
  test("is a limit with the package's own cooldown", async () => {
    const f = await setup(options)
    expect(await f.limit(LANE_MODEL, LOW_BALANCE)).toEqual({
      limit: true,
      reason: "its credit balance is too low",
    })
  })
  test("is read from the body when the message does not say it", async () => {
    const f = await setup(options)
    const answer = await f.limit(LANE_MODEL, {
      type: "provider.unknown",
      status: 400,
      message: "Bad Request",
      body: '{"error":{"message":"Your credit balance is too low"}}',
    })
    expect(answer.limit).toBe(true)
  })
  test("records an empty checkpoint at most once a minute per lane, and saves the refusal", async () => {
    const checkpoints: string[] = []
    const f = await setup(
      options,
      {},
      { creditEmpty: async (provider) => void checkpoints.push(provider) },
    )
    await f.limit(LANE_MODEL, LOW_BALANCE)
    await f.limit(LANE_MODEL, LOW_BALANCE)
    await flush()
    expect(checkpoints).toEqual([LANE.provider])
    f.clock.now += 61_000
    await f.limit(LANE_MODEL, LOW_BALANCE)
    await flush()
    expect(checkpoints).toEqual([LANE.provider, LANE.provider])
    expect(JSON.parse(await readFile(savedFile(), "utf8")).refused).toEqual({
      [LANE.provider]: f.clock.now,
    })
  })
  test("a failing checkpoint does not stop the answer", async () => {
    const f = await setup(
      options,
      {},
      {
        creditEmpty: async () => {
          throw new Error("no state")
        },
      },
    )
    expect((await f.limit(LANE_MODEL, LOW_BALANCE)).limit).toBe(true)
  })
  test("needs the lane to be configured, status 400 and the text", async () => {
    const off = await setup()
    expect(await off.limit(LANE_MODEL, LOW_BALANCE)).toEqual({ limit: false })
    const f = await setup(options)
    expect(
      await f.limit(LANE_MODEL, { ...LOW_BALANCE, status: 429 }),
    ).toEqual({ limit: false })
    expect(
      await f.limit(LANE_MODEL, {
        type: "provider.unknown",
        status: 400,
        message: "Invalid request",
      }),
    ).toEqual({ limit: false })
  })
})

describe("a credit lane's refused key", () => {
  test.each([
    { type: "provider.unknown", status: 401, message: "invalid x-api-key" },
    { type: "provider.unknown", status: 403, message: "forbidden" },
    { type: "provider.auth", message: "expired" },
  ])("%j is a limit for a quarter of an hour", async (error) => {
    const f = await setup(options)
    expect(await f.limit(LANE_MODEL, error)).toEqual({
      limit: true,
      wait_ms: KEY_REFUSED_WAIT_MS,
      reason: "its key was refused",
    })
    expect(KEY_REFUSED_WAIT_MS).toBe(15 * 60_000)
  })
  test("a model that is no lane's is not a limit", async () => {
    const f = await setup(options)
    expect(
      await f.limit("anthropic/claude-opus-5-5", {
        type: "provider.unknown",
        status: 401,
        message: "unauthorized",
      }),
    ).toEqual({ limit: false })
  })
})

describe("Antigravity's own refusal", () => {
  const model = "google/antigravity-claude-opus-5-5-high"
  const error = (message: string) => ({ type: "provider.unknown", message })
  const quota = (wait: number) => ({
    limit: true,
    wait_ms: wait,
    reason: "Antigravity quota protection",
  })
  test("without a reset time lasts an hour", async () => {
    const f = await setup()
    expect(
      await f.limit(
        model,
        error(
          "Quota protection: All 1 account(s) are over 90% usage for claude.",
        ),
      ),
    ).toEqual(quota(ANTIGRAVITY_MAX_WAIT_MS))
  })
  test("lasts as long as it says, no longer than an hour", async () => {
    const f = await setup()
    expect(
      await f.limit(
        model,
        error(
          "Quota protection: All 1 account(s) are over 90% usage for gemini. Quota resets in 2h 30m.",
        ),
      ),
    ).toEqual(quota(ANTIGRAVITY_MAX_WAIT_MS))
    expect(
      await f.limit(
        model,
        error(
          "All 1 account(s) rate-limited for claude. Quota resets in 12m 5s.",
        ),
      ),
    ).toEqual(quota(725_000))
  })
  test("another error of the provider is not a limit", async () => {
    const f = await setup()
    expect(await f.limit(model, error("Internal error"))).toEqual({
      limit: false,
    })
  })
  test("holds a forbidden request for an hour", async () => {
    const f = await setup()
    expect(
      await f.limit(model, { ...error("Forbidden"), status: 403 }),
    ).toEqual({
      limit: true,
      wait_ms: ANTIGRAVITY_MAX_WAIT_MS,
      reason: "Antigravity refused the request",
    })
  })
  test("holds a ToS suspension for a day", async () => {
    const f = await setup()
    expect(
      await f.limit(model, {
        ...error(
          "This service has been disabled in this account for violation of Terms of Service",
        ),
        status: 403,
      }),
    ).toEqual({
      limit: true,
      wait_ms: ANTIGRAVITY_TOS_WAIT_MS,
      reason: "Antigravity suspended the account (Terms of Service)",
    })
    expect(ANTIGRAVITY_TOS_WAIT_MS).toBe(24 * 60 * 60_000)
  })
  test("holds a bare resource-exhausted response for an hour", async () => {
    const f = await setup()
    expect(
      await f.limit(model, {
        ...error("Resource has been exhausted (e.g. check quota)."),
        status: 429,
        body: '{"error":{"code":429,"status":"RESOURCE_EXHAUSTED"}}',
      }),
    ).toEqual({
      limit: true,
      wait_ms: ANTIGRAVITY_MAX_WAIT_MS,
      reason: "Antigravity refused the request",
    })
  })
  test("does not hold another provider's forbidden request", async () => {
    const f = await setup(options)
    expect(
      await f.limit("anthropic/claude-opus-5-5", {
        ...error("Forbidden"),
        status: 403,
      }),
    ).toEqual(NO_LIMIT)
  })
})

describe("failures", () => {
  test("anything else, a text that is no step and a throw are no limit", async () => {
    const f = await setup(options)
    const other = { type: "provider.unknown", message: "m" }
    expect(await f.limit("openai/gpt-6.1-sol", other)).toEqual(NO_LIMIT)
    expect(await f.limit("nonsense", LOW_BALANCE)).toEqual(NO_LIMIT)
    expect(await f.limit(LANE_MODEL, undefined as any)).toEqual(NO_LIMIT)
  })
})
