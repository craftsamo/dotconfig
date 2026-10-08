import { readFileSync } from "fs"
import { homedir } from "os"
import { z } from "zod"
import { isToolSpec, type OAuthAccess, type ToolContext, type ToolSpec } from "../lib/custom-tools/define"
import * as git from "../lib/custom-tools/git"
import * as githubProject from "../lib/custom-tools/github_project"
import * as webUi from "../lib/custom-tools/web_ui"
import * as x from "../lib/custom-tools/x"

/**
 * Registers the custom tools under ../lib/custom-tools for both OpenCode V1
 * (`server()`, 1.18.29+ object entrypoint) and OpenCode V2 (`setup()`).
 *
 * Tool IDs keep the old `tools/<file>.ts` naming (`<file>_<export>`, e.g.
 * git_secret_scan, github_project_item_add, x_search), so the per-tool
 * permission keys in opencode.jsonc and the skills that call them are
 * unchanged. Do not reintroduce a `tools/` directory: V1 would register the
 * same IDs twice, and V2 no longer loads it.
 *
 * Imports stay free of @opencode-ai/plugin and @opencode/plugin; both
 * entrypoint helpers are identity functions, and Zod v4 schemas are accepted
 * by V1 (tool args) and V2 (Standard Schema input).
 */

const modules: Record<string, Record<string, unknown>> = {
  git,
  github_project: githubProject,
  web_ui: webUi,
  x,
}

function collect(): Array<[string, ToolSpec]> {
  const out: Array<[string, ToolSpec]> = []
  for (const [namespace, mod] of Object.entries(modules)) {
    for (const [name, value] of Object.entries(mod)) {
      if (isToolSpec(value)) out.push([`${namespace}_${name}`, value])
    }
  }
  return out
}

// ---------------------------------------------------------------- V1 ----

const V1_AUTH_PATH = `${homedir()}/.local/share/opencode/auth.json`

async function v1OAuthAccess(integrationID: string): Promise<OAuthAccess | undefined> {
  const auth = JSON.parse(readFileSync(V1_AUTH_PATH, "utf8"))
  const entry = auth?.[integrationID]
  if (entry?.type !== "oauth" || typeof entry.access !== "string") return undefined
  return { access: entry.access, expires: typeof entry.expires === "number" ? entry.expires : undefined }
}

async function server() {
  const tool: Record<string, unknown> = {}
  for (const [id, spec] of collect()) {
    tool[id] = {
      description: spec.description,
      args: spec.args,
      execute: (args: any, context: { worktree: string; sessionID?: string }) =>
        spec.execute(args, { worktree: context.worktree, oauthAccess: v1OAuthAccess, sessionID: context.sessionID }),
    }
  }
  return { tool }
}

// ---------------------------------------------------------------- V2 ----

// Minimal structural view of the @opencode/plugin 2.0.x Promise context used
// here; kept local so this file has no dependency on the V2 package.
type V2Context = {
  location: { directory: string }
  session: {
    get(input: { sessionID: string }): Promise<{ location?: { directory?: string }; metadata?: Record<string, unknown> }>
  }
  integration: {
    connection: {
      active(integrationID: string): Promise<unknown | undefined>
      resolve(connection: unknown): Promise<{ type: string; access?: string; expires?: number } | undefined>
    }
  }
  tool: {
    transform(callback: (editor: { add(tool: Record<string, unknown>): void }) => void): Promise<unknown>
  }
}

async function gitToplevel(directory: string): Promise<string> {
  const res = await Bun.$`git rev-parse --show-toplevel`.cwd(directory).nothrow().quiet()
  const top = res.stdout.toString().trim()
  return res.exitCode === 0 && top ? top : directory
}

async function setup(ctx: V2Context) {
  // V2 tool contexts carry no directory; resolve it from the calling session.
  // Fail closed instead of falling back to ctx.location: the shared server
  // hosts many projects, and the git tools stage changes in that directory.
  const worktreeFor = async (sessionID: string) => {
    let directory: string | undefined
    try {
      directory = (await ctx.session.get({ sessionID })).location?.directory
    } catch {}
    if (!directory) throw new Error(`Could not resolve the working directory of session ${sessionID}.`)
    return gitToplevel(directory)
  }

  const oauthAccess = async (integrationID: string): Promise<OAuthAccess | undefined> => {
    const connection = await ctx.integration.connection.active(integrationID)
    if (!connection) return undefined
    const credential = await ctx.integration.connection.resolve(connection)
    if (credential?.type !== "oauth" || typeof credential.access !== "string") return undefined
    return { access: credential.access, expires: credential.expires }
  }

  const tools = collect()
  await ctx.tool.transform((editor) => {
    for (const [id, spec] of tools) {
      editor.add({
        name: id,
        description: spec.description,
        input: z.object(spec.args),
        async execute(input: any, context: { sessionID: string }) {
          const toolContext: ToolContext = {
            worktree: await worktreeFor(context.sessionID),
            oauthAccess,
            sessionID: context.sessionID,
            sessionMetadata: async () => {
              try {
                return (await ctx.session.get({ sessionID: context.sessionID })).metadata
              } catch {
                return undefined
              }
            },
          }
          return { content: await spec.execute(input, toolContext) }
        },
      })
    }
  })
}

export default { id: "custom-tools", server, setup }
