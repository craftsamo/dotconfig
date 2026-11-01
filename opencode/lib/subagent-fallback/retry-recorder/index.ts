import { recordNative } from "../native-retry"
import type { Hooks, Registration } from "../runtime"

// Listed in opencode.jsonc before OpenCode Quota, whose retry hook may
// rewrite the wait: records OpenCode's own retry decision for the
// subagent preflight (../native-retry.ts). Changes nothing.
export type RecorderContext = {
  session: {
    hook(
      name: "retry",
      callback: (event: Hooks["retry"]) => Promise<void>,
    ): Promise<Registration>
  }
}

export async function setupRecorder(
  ctx: RecorderContext,
): Promise<() => Promise<void>> {
  const registration = await ctx.session.hook("retry", async (event) => {
    recordNative(event)
  })
  return () => registration.dispose()
}

export default {
  id: "dotconfig.subagent-preflight.retry-recorder",
  setup: setupRecorder,
}
