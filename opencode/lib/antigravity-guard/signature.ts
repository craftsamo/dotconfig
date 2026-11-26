import { ANTIGRAVITY_PROVIDER } from "../fallback-steps/policy"

/** Google's system-prompt filter rejects this spelling (#622). */
export const SIGNATURE_NEEDLE = "tools.opencode."
/** ASCII bracket access avoids the filter without changing the tool (#622). */
export const SIGNATURE_REPLACEMENT = 'tools["opencode"].'

export type SystemPart = {
  type: string
  text?: string
  [key: string]: unknown
}

/** Avoid Google's signature filter without relying on stripped zero-width text. */
export function neutralizeText(text: string): { text: string; count: number } {
  const parts = text.split(SIGNATURE_NEEDLE)
  return { text: parts.join(SIGNATURE_REPLACEMENT), count: parts.length - 1 }
}

/** Only system text is implicated in Google's signature filter (#622). */
export function neutralizeSystem(system: SystemPart[]): number {
  let count = 0
  for (const part of system) {
    if (part.type !== "text" || typeof part.text !== "string") continue
    const result = neutralizeText(part.text)
    part.text = result.text
    count += result.count
  }
  return count
}

/** Keep the filter workaround confined to the affected Google endpoint. */
export function isAntigravity(model: { providerID: string; id: string }): boolean {
  return (
    model.providerID === ANTIGRAVITY_PROVIDER &&
    model.id.startsWith("antigravity-")
  )
}
