import type { ModelRef } from "../claude-logins/models"

// `provider/model#default` runs the model as it is: no variant of its own.
const NO_VARIANT = "default"

// A step as the fallback names it, `provider/model#variant`: the provider ends
// at the first `/` (a model ID may hold more), the variant starts at the last
// `#`. Undefined for text that names no provider or no model.
export function parseStep(step: string): ModelRef | undefined {
  const slash = step.indexOf("/")
  if (slash <= 0) return undefined
  const rest = step.slice(slash + 1)
  const hash = rest.lastIndexOf("#")
  const id = hash === -1 ? rest : rest.slice(0, hash)
  const variant = hash === -1 ? "" : rest.slice(hash + 1)
  if (id === "") return undefined
  return {
    providerID: step.slice(0, slash),
    id,
    ...(variant === "" || variant === NO_VARIANT ? {} : { variant }),
  }
}
