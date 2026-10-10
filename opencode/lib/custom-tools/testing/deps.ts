import { createRequire } from "module"

// The custom tools import zod from opencode/node_modules, which is gitignored:
// a fresh task worktree has none until ./worktree-setup.sh links it. Test
// files that reach the tools load them through `load` and run their suites
// under `describe.skipIf(skip)`, so a missing package skips with this reason
// instead of failing the whole file at import.
const REQUIRED = ["zod"]
const require = createRequire(import.meta.url)

export const missing = REQUIRED.filter((name) => {
  try {
    require.resolve(name)
    return false
  } catch {
    return true
  }
})
export const skip = missing.length > 0
if (skip) {
  console.warn(
    `skipping custom-tool suites: opencode/node_modules lacks ${missing.join(", ")}; ` +
      "run ./worktree-setup.sh in a task worktree or ./install.sh --deps",
  )
}

export function load<T>(importer: () => Promise<T>): Promise<T> {
  return skip ? Promise.resolve({} as T) : importer()
}
