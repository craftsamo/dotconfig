import { createServer, type Server } from "node:http"
import type { AddressInfo } from "node:net"
import type { Summary } from "./core"
import { toQuotaV1, type QuotaEntry } from "./quota"

export const DEFAULT_PORT = 47631
export const CACHE_MS = 30_000

export type Reply = { status: number; body: unknown }
export type QuotaV1Envelope = { version: "quota-v1"; entries: QuotaEntry[] }

function cachedCall<T>(
  run: () => Promise<T>,
  now: () => Date,
): () => Promise<T> {
  let cached: { at: number; value: T } | undefined
  let inflight: Promise<T> | undefined
  return async () => {
    if (cached && now().getTime() - cached.at < CACHE_MS) return cached.value
    inflight ??= run()
      .then((value) => {
        if (value !== undefined) cached = { at: now().getTime(), value }
        return value
      })
      .finally(() => {
        inflight = undefined
      })
    return inflight
  }
}

// Serves one lane per path (`/<provider id>`) as an OpenCode Quota `quota-v1`
// envelope. Collection is cached and shared between concurrent requests so a
// busy UI cannot fan out into many `opencode stats` or quota runs.
export function createHandler(options: {
  collect: () => Promise<Summary[]>
  now?: () => Date
  // The bearer token a lane's request must carry, if any.
  tokenFor?: (provider: string) => string | undefined
  // Extra quota-v1 routes served on the same loopback port (e.g. Antigravity).
  routes?: Record<string, () => Promise<QuotaV1Envelope | undefined>>
}) {
  const now = options.now ?? (() => new Date())
  const summaries = cachedCall(options.collect, now)
  const extraRoutes = Object.fromEntries(
    Object.entries(options.routes ?? {}).map(([key, fn]) => [
      key,
      cachedCall(fn, now),
    ]),
  )

  return async (
    method: string | undefined,
    path: string | undefined,
    authorization: string | undefined,
  ): Promise<Reply> => {
    if (method !== "GET")
      return { status: 405, body: { error: "method not allowed" } }
    const provider = decodeURIComponent((path ?? "").split("?", 1)[0]).replace(
      /^\/+/,
      "",
    )
    const token = options.tokenFor?.(provider)
    if (token && authorization !== `Bearer ${token}`)
      return { status: 401, body: { error: "unauthorized" } }
    const customRoute = extraRoutes[provider]
    if (customRoute) {
      try {
        const body = await customRoute()
        if (!body) return { status: 404, body: { error: "unknown lane" } }
        return { status: 200, body }
      } catch {
        return { status: 503, body: { error: "unavailable" } }
      }
    }
    try {
      const found = (await summaries()).find(
        (s) => s.lane.provider === provider,
      )
      if (!found) return { status: 404, body: { error: "unknown lane" } }
      return { status: 200, body: toQuotaV1(found, now()) }
    } catch {
      return { status: 503, body: { error: "unavailable" } }
    }
  }
}

// The plugin can be loaded once per location, and only one instance can own the
// port. The others keep trying, so the endpoint comes back if its owner is
// unloaded.
export function serve(
  handler: ReturnType<typeof createHandler>,
  port: number,
  retryMs = 30_000,
): { dispose(): Promise<void> } {
  let owned: { close(): Promise<void> } | undefined
  let closed = false
  let busy = false
  const attempt = async () => {
    if (closed || owned || busy) return
    busy = true
    try {
      const server = await listen(handler, port)
      if (closed) await server?.close()
      else owned = server
    } finally {
      busy = false
    }
  }
  void attempt()
  const timer = setInterval(() => void attempt(), retryMs)
  timer.unref?.()
  return {
    async dispose() {
      closed = true
      clearInterval(timer)
      await owned?.close()
      owned = undefined
    },
  }
}

// Loopback only. Resolves to undefined when the port is taken (another service
// or a standalone run already serves it), which is not an error.
export function listen(
  handler: ReturnType<typeof createHandler>,
  port: number,
): Promise<{ port: number; close(): Promise<void> } | undefined> {
  return new Promise((resolve) => {
    const server: Server = createServer((req, res) => {
      handler(req.method, req.url, req.headers.authorization)
        .then(({ status, body }) => {
          const text = JSON.stringify(body)
          res.writeHead(status, {
            "content-type": "application/json",
            "content-length": Buffer.byteLength(text),
          })
          res.end(text)
        })
        .catch(() => {
          res.writeHead(500).end()
        })
    })
    server.once("error", () => resolve(undefined))
    server.listen(port, "127.0.0.1", () => {
      resolve({
        port: (server.address() as AddressInfo).port,
        close: () => new Promise<void>((done) => server.close(() => done())),
      })
    })
    server.unref()
  })
}
