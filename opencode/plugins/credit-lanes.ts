import { collect, loadLanes } from "../lib/credit-lanes/collect"
import {
  createHandler,
  DEFAULT_PORT,
  serve,
} from "../lib/credit-lanes/endpoint"

/**
 * Serves the Console credit lane balance on 127.0.0.1 for OpenCode Quota's
 * custom remote provider (see lib/credit-lanes and the README). Read-only, a
 * cached `opencode stats` run behind it; nothing here touches the history
 * database.
 */
async function setup() {
  const port = Number(process.env.CREDIT_LANES_PORT) || DEFAULT_PORT
  const handler = createHandler({
    collect: () => collect(),
    // Quota sends the lane's own key as the bearer token; answer only that.
    tokenFor: (provider) => {
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
