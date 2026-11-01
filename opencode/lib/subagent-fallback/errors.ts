// Every refusal of this plugin carries this prefix; the retry hook stops a
// protected child on it instead of retrying.
export const FAIL_PREFIX = "Subagent preflight:"

// A declaration, not an arrow: TypeScript narrows after a call only then.
export function fail(reason: string): never {
  throw new Error(`${FAIL_PREFIX} ${reason}`)
}
