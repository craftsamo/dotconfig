import { createHash } from "node:crypto"
import { gunzipSync, zstdDecompressSync } from "node:zlib"
import { subscription, type Subscription } from "./accounts"
import { fail } from "./errors"
import { OAUTH_PROVIDER } from "./lanes"
import { aliasOf, selector, withMarker, type Marker } from "./marker"
import { inputCapacity, modelsEqual, ROUTES } from "./policy"
import type { RouteTable } from "./routes"
import {
  supported,
  type ContextEvent,
  type Hooks,
  type Kind,
  type RuntimeContext,
  type Scope,
  type Session,
} from "./runtime"

// The guards of a protected child, the one this plugin launched: who its
// requests leave as, where they go, and whether an alternate's first
// request fits its model.

// Conservative text-only ceiling. This is not a cross-provider tokenizer.
export const MAX_CONTEXT_BYTES = 160_000
// Room a first request leaves in the alternate's input capacity.
const HEADROOM_BYTES = 32_768

export type Child = { session: Session; marker: Marker }

const record = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value)

function textOnly(messages: unknown[]): boolean {
  return messages.every(
    (message) =>
      record(message) &&
      Array.isArray(message.content) &&
      message.content.every(
        (part) =>
          record(part) && part.type === "text" && typeof part.text === "string",
      ),
  )
}

class WireTooLarge extends Error {}

// The size of the JSON a request carries. Since 2.0.28 provider requests can
// be zstd or gzip compressed (settings.encoding; zstd by default for ChatGPT
// sign-in), so the body is decoded first, never past the text ceiling. Any
// other encoding cannot be measured and stops the launch.
async function wireBytes(request: Request): Promise<number> {
  const body = new Uint8Array(await request.clone().arrayBuffer())
  const encoding = (request.headers.get("content-encoding") ?? "")
    .trim()
    .toLowerCase()
  if (encoding === "" || encoding === "identity") return body.byteLength
  const options = { maxOutputLength: MAX_CONTEXT_BYTES + 1 }
  try {
    if (encoding === "zstd") return zstdDecompressSync(body, options).byteLength
    if (encoding === "gzip") return gunzipSync(body, options).byteLength
  } catch (error) {
    if ((error as { code?: string }).code === "ERR_BUFFER_TOO_LARGE")
      throw new WireTooLarge()
    throw error
  }
  throw new Error(`unsupported content-encoding ${encoding}`)
}

function transportURL(
  url: string,
  providerID: string,
  kind: Kind,
  websocket: boolean,
): void {
  let target: URL
  try {
    target = new URL(url)
  } catch {
    return fail("invalid transport URL")
  }
  if (target.username || target.password || target.port || target.hash)
    fail("unapproved transport URL")
  if (providerID === "openai") {
    const paths =
      kind === "compaction"
        ? [
            "/backend-api/codex/responses",
            "/backend-api/codex/responses/compact",
          ]
        : ["/backend-api/codex/responses"]
    if (
      target.hostname !== "chatgpt.com" ||
      target.protocol !== (websocket ? "wss:" : "https:") ||
      target.search ||
      !paths.includes(target.pathname)
    )
      fail("not a ChatGPT subscription route")
  } else if (providerID === "xai") {
    // The built-in xAI provider defaults to the Responses WebSocket channel
    // and falls back to HTTP on the same path.
    if (
      target.hostname !== "api.x.ai" ||
      target.protocol !== (websocket ? "wss:" : "https:") ||
      target.search ||
      target.pathname !== "/v1/responses"
    )
      fail("not an approved xAI subscription route")
  } else if (providerID === "anthropic") {
    if (
      websocket ||
      target.hostname !== "api.anthropic.com" ||
      target.protocol !== "https:" ||
      !["/v1/messages", "/v1/messages/count_tokens"].includes(
        target.pathname,
      ) ||
      (target.search !== "" && target.search !== "?beta=true")
    )
      fail("not an approved Anthropic OAuth route")
  } else fail("no approved transport for this provider")
}

const signature = (auth: Subscription) =>
  createHash("sha256")
    .update(
      JSON.stringify([auth.proof.connectionID, auth.access, auth.accountID]),
    )
    .digest("hex")
const exchangeKey = (e: Scope) =>
  `${e.sessionID}/${e.kind}/${selector(e.model)}`

export function createGuards(
  ctx: RuntimeContext,
  deps: {
    protectedChild: (sessionID: string) => Promise<Child | undefined>
    loginOf: (suffix: string) => Promise<Subscription>
    // The routes in effect: their models are the ones a child may send.
    table: RouteTable
  },
) {
  const { protectedChild, loginOf, table } = deps
  const handshakes = new Map<string, string>()

  const authorize = async (event: Scope) => {
    const child = await protectedChild(event.sessionID)
    if (!child) return undefined
    if (!supported(ctx.app.version))
      fail("unsupported OpenCode version; protected child stopped")
    const { session, marker } = child
    if (!session.model || !modelsEqual(session.model, marker.model))
      fail("child model changed after launch")
    if (event.kind === "primary" && !modelsEqual(event.model, marker.model))
      fail("unexpected primary model")
    if (
      event.kind === "primary" &&
      marker.fallback &&
      marker.launchChecked !== true
    )
      fail("alternate launch context was not checked")
    // A child on a saved login runs its route model's alias, and its Claude
    // side requests leave on that login too (claude-accounts.ts).
    const bound =
      marker.login !== undefined && event.model.providerID === OAUTH_PROVIDER
    // The routes' models and the built-in ones, which children launched
    // before the routes changed may still run.
    const approvedModel = [
      ...Object.values(table).flatMap((steps) => steps.map((s) => s.model)),
      ...Object.values(ROUTES).flatMap((r) => [r.primary, r.alternate]),
    ].some((m) =>
      [m, ...(bound ? [aliasOf(m, marker.login)] : [])].some(
        (allowed) =>
          allowed.id === event.model.id &&
          allowed.providerID === event.model.providerID,
      ),
    )
    if (!approvedModel) fail("unapproved auxiliary model")
    let auth: Subscription | undefined
    try {
      auth = bound
        ? await loginOf(marker.login!)
        : await subscription(ctx, event.model.providerID)
    } catch {
      return fail("subscription credentials unavailable")
    }
    if (
      !auth ||
      (event.model.providerID === marker.model.providerID &&
        auth.proof.connectionID !== marker.connectionID)
    )
      fail("subscription account changed or unavailable")
    // Launch preferences are not an in-flight billing gate. Keep identity and
    // transport protection, without fetching/rechecking usage or credit balances.
    return auth
  }

  // The child's model as the catalog lists it now.
  const catalogModel = async (child: Child) =>
    (await ctx.model.list({ location: child.session.location })).data.find(
      (m) =>
        m.id === child.marker.model.id &&
        m.providerID === child.marker.model.providerID,
    )

  const context = async (event: ContextEvent) => {
    const child = await protectedChild(event.sessionID)
    if (!child?.marker.fallback || child.marker.launchChecked === true) return
    // Check only the first request's full text context. Later native compaction
    // is not a mechanism for making an oversized launch fit the alternate.
    if (!textOnly(event.messages))
      fail("alternate launch requires text-only context")
    let bytes: number
    try {
      bytes = Buffer.byteLength(
        JSON.stringify(
          {
            system: event.system,
            messages: event.messages,
            tools: event.tools,
            options: event.options,
          },
          (_key, value) => {
            if (["function", "symbol", "bigint"].includes(typeof value))
              fail("alternate context contains unmeasurable values")
            return value
          },
        ),
      )
    } catch {
      return fail("alternate context cannot be measured")
    }
    if (bytes > MAX_CONTEXT_BYTES)
      fail("alternate launch context exceeds the conservative text limit")
    // Require catalog headroom as well as the byte ceiling. No history
    // conversion or compaction is used to make this first request fit.
    const model = await catalogModel(child)
    if (!model || bytes + HEADROOM_BYTES > inputCapacity(model.limit))
      fail("alternate catalog lacks conservative context headroom")
    await ctx.session.update({
      sessionID: child.session.id,
      metadata: withMarker(child.session.metadata, {
        ...child.marker,
        launchChecked: true,
      }),
    })
  }

  const wireSize = async (event: Scope, read: () => Promise<number>) => {
    const child = await protectedChild(event.sessionID)
    if (
      !child?.marker.fallback ||
      child.marker.wireChecked === true ||
      event.kind !== "primary"
    )
      return
    let bytes: number
    try {
      bytes = await read()
    } catch (error) {
      if (error instanceof WireTooLarge)
        return fail("alternate wire context exceeds conservative headroom")
      return fail("alternate wire context cannot be measured")
    }
    const model = await catalogModel(child)
    const capacity = model ? inputCapacity(model.limit) : NaN
    if (
      !Number.isFinite(capacity) ||
      bytes > MAX_CONTEXT_BYTES ||
      bytes + HEADROOM_BYTES > capacity
    )
      fail("alternate wire context exceeds conservative headroom")
    // Later trusted context hooks can add global instructions. Measure the
    // actual serialized HTTP body / WS frame before its first transmission too.
    await ctx.session.update({
      sessionID: child.session.id,
      metadata: withMarker(child.session.metadata, {
        ...child.marker,
        wireChecked: true,
      }),
    })
  }

  const httpRequest = async (event: Hooks["http.request"]) => {
    const auth = await authorize(event)
    if (!auth) return
    transportURL(event.request.url, event.model.providerID, event.kind, false)
    if (event.request.method !== "POST") fail("unapproved HTTP method")
    // Native OpenAI Requests default to follow; prohibit redirecting a
    // validated OAuth request to an unvalidated endpoint.
    if (event.request.redirect !== "error")
      event.request = new Request(event.request, { redirect: "error" })
    const headers = event.request.headers
    if (
      headers.get("authorization") !== `Bearer ${auth.access}` ||
      headers.has("x-api-key")
    )
      fail("wire authentication is not the approved OAuth credential")
    if (
      event.model.providerID === "openai" &&
      headers.get("chatgpt-account-id") !== auth.accountID
    )
      fail("wire subscription account mismatch")
    await wireSize(event, () => wireBytes(event.request))
  }

  const wsHandshake = async (event: Hooks["experimental.ws.handshake"]) => {
    const auth = await authorize(event)
    if (!auth) return
    transportURL(event.url, event.model.providerID, event.kind, true)
    const headers = new Headers(event.headers)
    if (
      headers.get("authorization") !== `Bearer ${auth.access}` ||
      headers.has("x-api-key") ||
      (event.model.providerID === "openai" &&
        headers.get("chatgpt-account-id") !== auth.accountID)
    )
      fail("WebSocket subscription identity mismatch")
    handshakes.set(exchangeKey(event), signature(auth))
  }

  const wsSend = async (event: Hooks["experimental.ws.send"]) => {
    const auth = await authorize(event)
    if (!auth) return
    if (handshakes.get(exchangeKey(event)) !== signature(auth))
      fail("WebSocket exchange lacks a current approved handshake")
    await wireSize(event, async () => Buffer.byteLength(event.frame))
  }

  return {
    context,
    httpRequest,
    wsHandshake,
    wsSend,
    clear: () => handshakes.clear(),
  }
}
