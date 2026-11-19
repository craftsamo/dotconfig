import { afterEach, beforeEach, expect } from "bun:test"
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import type { Lane, LaneState } from "../credit-lanes/core"
import { QUOTA_RPC } from "../subagent-fallback/quota-refresh"
import { fileStore } from "../subagent-fallback/saved"
import type { StepsDeps } from "./deps"
import { setupFallbackSteps } from "./index"

// What the plugin's tests share: a fake plugin context (logins, RPC, events),
// Quota export rows, and a temp dir for the export and the state file.
export const NOW = 1_710_000_000_000
export const HOUR_MS = 3_600_000
export const RESET = NOW + HOUR_MS
export const UNTIL = new Date(RESET).toISOString()
export const USABLE = { usable: true }
export const signal = new AbortController().signal
export const never = () => new Promise<never>(() => {})

export type Login = { id: string; label?: string; methodID: string }
export const LOGINS: Record<string, Login[]> = {
  anthropic: [
    { id: "main-id", label: "Main", methodID: "claude-max" },
    { id: "sub-id", label: "Sub", methodID: "claude-max" },
  ],
  openai: [{ id: "chatgpt-id", methodID: "chatgpt-browser" }],
  xai: [{ id: "xai-id", methodID: "device" }],
  google: [{ id: "agy-id", methodID: "antigravity" }],
}
const ACTIVE: Record<string, string> = {
  anthropic: "main-id",
  openai: "chatgpt-id",
  xai: "xai-id",
  google: "agy-id",
}

// A Quota 6 row: its `account` is the login's label.
export const row = (
  providerID: string,
  account: string,
  percentRemaining = 90,
) => ({
  id: providerID === "xai" ? "xai.credits" : `${providerID}.five_hour`,
  window: "5h",
  percentRemaining,
  account,
  resultType: "quota",
  acquisitionMethod: "remote_api",
  authority: "provider_reported",
  renderType: "percent",
  resetAt: RESET / 1000,
})
export const part = (entries: unknown[], fetchedAt = NOW / 1000) => ({
  status: "ok",
  fetchedAt,
  entries,
})
export const agyRow = (group: string, percentRemaining: number) => ({
  id: `quota-providers.custom.google-antigravity.${group}`,
  resultType: "quota",
  percentRemaining,
  resetAt: RESET / 1000,
})
export const fresh = (providerID: string, ...rows: unknown[]) => ({
  [providerID]: part(rows),
})

export const LANE: Lane = {
  provider: "anthropic-credit-main",
  label: "Main",
  amount: 200,
  renewalDay: 13,
}
export const LANE_AT = new Date(2026, 9, 20, 12).getTime()
export const emptyLane: LaneState = {
  grants: [],
  checkpoint: {
    at: new Date(LANE_AT).toISOString(),
    balance: 0,
    source: "empty",
    opencodeFrom: "2026-10-20",
    opencodeBase: 0,
  },
}

let dir: string
/** Registers the hooks that give each test a fresh temp dir. */
export function useTempDir() {
  beforeEach(async () => {
    dir = await mkdtemp(join(tmpdir(), "fallback-steps-"))
  })
  afterEach(() => rm(dir, { recursive: true, force: true }))
}
export const savedFile = () => join(dir, "state.json")

export async function setup(
  options: Record<string, unknown> = {},
  exported: Record<string, unknown> = {},
  extra: Partial<StepsDeps> & { logins?: Record<string, Login[]> } = {},
) {
  const { logins = LOGINS, ...overrides } = extra
  const exportFile = join(dir, "quota-export.json")
  await writeFile(
    exportFile,
    JSON.stringify({ version: 3, providers: exported }),
  )
  const clock = { now: NOW }
  const deps: StepsDeps = {
    now: () => clock.now,
    readExport: (path) => readFile(path, "utf8"),
    sleep: never,
    antigravityReserve: () => 10,
    saved: fileStore(savedFile()),
    exportFile,
    ...overrides,
  }
  const calls = { refresh: [] as unknown[], disposed: false }
  const listeners = new Set<(envelope: unknown) => unknown>()
  const handlers: { usable: any; limit: any } = {} as any
  const ctx: any = {
    options,
    app: { version: "2.3.0" },
    session: { get: async () => ({}) },
    provider: {
      get: async ({ providerID }: { providerID: string }) => {
        if (!logins[providerID]) throw new Error("no provider")
        return { data: { package: `@opencode/ai/providers/${providerID}` } }
      },
    },
    integration: {
      get: async ({ integrationID }: { integrationID: string }) => ({
        data: {
          connections: (logins[integrationID] ?? []).map((l) => ({
            type: "credential",
            method: "oauth",
            ...l,
          })),
        },
      }),
      connection: {
        active: async (providerID: string) => {
          const id = ACTIVE[providerID]
          return logins[providerID]?.some((l) => l.id === id)
            ? { type: "credential", method: "oauth", id }
            : undefined
        },
        resolve: async ({ id }: { id: string }) => {
          const found = Object.values(logins)
            .flat()
            .find((l) => l.id === id)
          return (
            found && {
              type: "oauth",
              methodID: found.methodID,
              access: `token-${id}`,
              metadata: { accountID: "account" },
            }
          )
        },
      },
    },
    rpc: Object.assign(
      (definition: { id: string }) => {
        if (definition.id === QUOTA_RPC.id)
          return {
            refresh: async (input: unknown) => {
              calls.refresh.push(input)
              return never()
            },
          }
        return {
          events: {
            on(name: string, handler: (envelope: unknown) => unknown) {
              expect(name).toBe("limited")
              listeners.add(handler)
              return () => listeners.delete(handler)
            },
          },
        }
      },
      {
        register: async (_definition: unknown, registered: any) => {
          Object.assign(handlers, registered)
          return { dispose: async () => void (calls.disposed = true) }
        },
      },
    ),
  }
  const cleanup = await setupFallbackSteps(ctx, deps)
  const ask = (model: string) =>
    handlers.usable({ agent: "worker", model }, { signal })
  const limit = (
    model: string,
    error: Record<string, unknown>,
    extra: Record<string, unknown> = {},
  ) => handlers.limit({ agent: "worker", model, error, ...extra }, { signal })
  // Delivers an event as OpenCode does, and waits for the handlers.
  const emit = (envelope: unknown) =>
    Promise.all([...listeners].map((handler) => handler(envelope)))
  const limited = (model: string, until: string = UNTIL) =>
    emit({
      data: {
        session_id: "ses_1",
        agent: "worker",
        model,
        kind: "quota",
        until,
      },
    })
  return {
    ask,
    limit,
    emit,
    limited,
    listeners,
    calls,
    clock,
    cleanup,
    handlers,
    ctx,
    deps,
  }
}
