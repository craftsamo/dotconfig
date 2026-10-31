import {
  ANTIGRAVITY_QUOTA_ID,
  ANTIGRAVITY_QUOTA_TOKEN,
  createAntigravityCollector,
  type IntegrationContext,
} from "../lib/credit-lanes/antigravity"
import { collect, loadLanes } from "../lib/credit-lanes/collect"
import {
  createHandler,
  DEFAULT_PORT,
  serve,
} from "../lib/credit-lanes/endpoint"

/**
 * Serves the Console credit lane balance and the Antigravity quota on
 * 127.0.0.1 for OpenCode Quota's custom remote providers (see
 * lib/credit-lanes and the README). Behind the lanes, a cached `opencode
 * stats` run and a read of Hermes' usage rows; behind Antigravity, the
 * active Google Antigravity OAuth connection's `fetchAvailableModels`.
 * Nothing here touches the history database.
 */
async function setup(ctx: IntegrationContext = {}) {
  const port = Number(process.env.CREDIT_LANES_PORT) || DEFAULT_PORT
  const handler = createHandler({
    collect: () => collect(),
    routes: {
      [ANTIGRAVITY_QUOTA_ID]: createAntigravityCollector(ctx),
    },
    // Quota sends the lane's own key (or Antigravity's local sentinel) as the
    // bearer token; answer only that.
    tokenFor: (provider) => {
      if (provider === ANTIGRAVITY_QUOTA_ID) return ANTIGRAVITY_QUOTA_TOKEN
      const name = loadLanes().find(
        (lane) => lane.provider === provider,
      )?.keyEnv
      return name ? process.env[name] || undefined : undefined
    },
  })
  const server = serve(handler, port)
  return () => server.dispose()
}

export default { id: "credit-lanes", setup }
