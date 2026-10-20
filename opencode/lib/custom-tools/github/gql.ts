import { exec } from "../exec"

/**
 * GraphQL over `gh api graphql`, the one transport the GitHub tools share.
 *
 * Variables travel as `-f` (string) / `-F` (typed: number, boolean, null)
 * flags, so a query, its variables and the fake `gh` of the tests all meet on
 * argv. Composite values (lists, input objects) are inlined into the query
 * text with `lit()` instead; GitHub accepts a JSON string as a GraphQL string
 * literal, and enum values stay bare.
 */

export type Vars = Record<string, string | number | boolean | null | undefined>

export class GraphQLError extends Error {
  constructor(
    message: string,
    public readonly errors: unknown[],
    public readonly data: unknown,
  ) {
    super(message)
  }
}

function varFlags(vars: Vars): string[] {
  const out: string[] = []
  for (const [k, v] of Object.entries(vars)) {
    if (v === undefined) continue
    if (typeof v === "string") out.push("-f", `${k}=${v}`)
    else out.push("-F", `${k}=${v === null ? "null" : String(v)}`)
  }
  return out
}

/** Runs one query or mutation and returns its `data`; GraphQL errors throw with the error list. */
export async function graphql<T = any>(query: string, vars: Vars = {}, cwd?: string): Promise<T> {
  const argv = ["gh", "api", "graphql", "-f", `query=${query}`, ...varFlags(vars)]
  const res = await exec(argv, { cwd })
  let parsed: any = null
  const text = res.stdout.trim()
  if (text) {
    try {
      parsed = JSON.parse(text)
    } catch {
      parsed = null
    }
  }
  const errors: unknown[] = Array.isArray(parsed?.errors) ? parsed.errors : []
  if (!res.ok || errors.length) {
    const detail = errors.length
      ? errors.map((e: any) => (typeof e?.message === "string" ? e.message : JSON.stringify(e))).join("; ")
      : res.stderr.trim() || res.stdout.trim()
    throw new GraphQLError(`gh api graphql failed (exit ${res.code}): ${detail}`, errors, parsed?.data ?? null)
  }
  return (parsed?.data ?? null) as T
}

export type Page<T> = { nodes: T[]; pageInfo?: { hasNextPage?: boolean; endCursor?: string | null } }

/**
 * Walks a connection whose query declares `$after: String` and passes it as
 * `after: $after`. `pick` returns the connection from one page's data. Stops
 * at `limit` nodes (default 500) so a runaway board cannot pull everything.
 */
export async function paginate<T>(
  query: string,
  vars: Vars,
  pick: (data: any) => Page<T> | null | undefined,
  options: { limit?: number; cwd?: string } = {},
): Promise<T[]> {
  const limit = options.limit ?? 500
  const out: T[] = []
  let after: string | null = null
  for (;;) {
    const data = await graphql(query, { ...vars, after: after ?? null }, options.cwd)
    const page = pick(data)
    if (!page) break
    out.push(...(page.nodes ?? []))
    if (out.length >= limit) return out.slice(0, limit)
    if (!page.pageInfo?.hasNextPage || !page.pageInfo.endCursor) break
    after = page.pageInfo.endCursor
  }
  return out
}

/** A GraphQL string literal (JSON escaping is valid GraphQL). */
export const lit = (s: string): string => JSON.stringify(s ?? "")
