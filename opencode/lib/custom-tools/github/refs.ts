/**
 * Parsers for the ways a person names GitHub things in a tool argument:
 * an issue as `12`, `#12`, `owner/repo#12` or its URL; a repository as
 * `owner/repo` or its URL; a project as a number, `owner/N`, a title, or its
 * `/orgs/<o>/projects/N` / `/users/<u>/projects/N` URL.
 */

export type IssueRef = { repo?: string; number: number }
export type ProjectRef = { owner?: string; number?: number; title?: string }

export function parseIssueRef(ref: string, defaultRepo?: string): IssueRef {
  const s = ref.trim()
  let m = s.match(/^https?:\/\/[^/]+\/([^/]+\/[^/]+)\/(?:issues|pull)\/(\d+)(?:[/?#].*)?$/)
  if (m) return { repo: m[1], number: parseInt(m[2], 10) }
  m = s.match(/^([^/\s#]+\/[^/\s#]+)#(\d+)$/)
  if (m) return { repo: m[1], number: parseInt(m[2], 10) }
  m = s.match(/^#?(\d+)$/)
  if (m) return { repo: defaultRepo, number: parseInt(m[1], 10) }
  throw new Error(`Not an issue reference: "${ref}". Use a number, #N, owner/repo#N or an issue URL.`)
}

export function parseRepoRef(ref: string): string {
  const s = ref.trim().replace(/\.git$/, "")
  const m = s.match(/^(?:https?:\/\/[^/]+\/|git@[^:]+:)?([^/\s]+)\/([^/\s]+)\/?$/)
  if (!m) throw new Error(`Not a repository reference: "${ref}". Use owner/repo or a GitHub URL.`)
  return `${m[1]}/${m[2]}`
}

export function parseProjectRef(ref: string | undefined, owner?: string): ProjectRef {
  const s = (ref ?? "").trim()
  if (!s) return { owner }
  let m = s.match(/^https?:\/\/[^/]+\/(?:orgs|users)\/([^/]+)\/projects\/(\d+)(?:[/?#].*)?$/)
  if (m) return { owner: m[1], number: parseInt(m[2], 10) }
  m = s.match(/^([^/\s]+)\/(\d+)$/)
  if (m) return { owner: m[1], number: parseInt(m[2], 10) }
  if (/^\d+$/.test(s)) return { owner, number: parseInt(s, 10) }
  return { owner, title: s }
}

/** Case-insensitive name match, the rule every field / option / type lookup follows. */
export const sameName = (a: unknown, b: unknown) => String(a ?? "").trim().toLowerCase() === String(b ?? "").trim().toLowerCase()
