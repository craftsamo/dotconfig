import { tool } from "../define"
import { runGh, runGhJson, runGit } from "../exec"
import { resolveRepo } from "./shared"

function parseIssueRefs(text: string): { closes: number[]; refs: number[] } {
  const closes = new Set<number>()
  const refs = new Set<number>()
  const closeRe = /\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)/gi
  let m: RegExpExecArray | null
  while ((m = closeRe.exec(text))) closes.add(parseInt(m[1], 10))
  const refRe = /(?<![\w/])#(\d+)\b/g
  while ((m = refRe.exec(text))) {
    const n = parseInt(m[1], 10)
    if (!closes.has(n)) refs.add(n)
  }
  return { closes: [...closes], refs: [...refs] }
}

// The Stacks API is versioned (`2026-03-10`). The default version currently
// serves the `stack` field too, so try unpinned first and only pin when that
// yields nothing — a null result is as much a miss as a failed call here.
const STACKS_API_VERSION = "2026-03-10"

async function ghApi(path: string, jq: string | undefined, cwd?: string): Promise<any> {
  const argv = ["api", path]
  if (jq) argv.push("--jq", jq)
  for (const attempt of [argv, [...argv, "-H", `X-GitHub-Api-Version: ${STACKS_API_VERSION}`]]) {
    try {
      const out = await runGhJson(attempt, cwd)
      if (out != null) return out
    } catch {
      // try the next form
    }
  }
  return null
}

/** Local stack tracking (`gh stack view --json`), which also covers layers that have no PR yet. */
async function localStack(head: string, cwd?: string): Promise<any> {
  let view: any = null
  try {
    view = await runGhJson(["stack", "view", "--json"], cwd)
  } catch {
    return null
  }
  // `gh stack view` always describes the checked-out branch's stack, so it is
  // only authoritative when the branch we are scanning is the checked-out one.
  if (!view?.branches?.length || (view.currentBranch && view.currentBranch !== head)) return null
  const layers = view.branches.map((b: any, i: number) => ({
    position: i + 1,
    number: b.pr?.number ?? null,
    head: b.name,
    state: b.pr?.state ?? null,
    merged: Boolean(b.isMerged),
    needsRebase: Boolean(b.needsRebase),
  }))
  const self = layers.findIndex((l: any) => l.head === head)
  if (self < 0) return null
  return {
    native: true,
    source: "local",
    trunk: view.trunk ?? null,
    position: self + 1,
    size: layers.length,
    below: self > 0 ? layers[self - 1] : null,
    above: self < layers.length - 1 ? layers[self + 1] : null,
    needsRebase: layers.some((l: any) => l.needsRebase),
    layers,
  }
}

/**
 * Describe the branch's position in a native GitHub stack.
 *
 * Local tracking is checked first because it also covers a layer that has just
 * been added and has no PR yet. Server membership is the fallback for a clone
 * without local tracking, and is only readable through the REST API — note that
 * `gh pr view --json stack` is NOT supported. Failing both, report the PR that
 * owns a non-default base branch (the pre-native notion of a stacked base).
 */
async function describeStack(opts: {
  repo: string
  prNumber: number | null
  head: string
  base: string
  defBranch: string
  cwd?: string
}): Promise<any> {
  const { repo, prNumber, head, base, defBranch, cwd } = opts

  const local = await localStack(head, cwd)
  if (local) return local

  if (prNumber) {
    const membership = await ghApi(`repos/${repo}/pulls/${prNumber}`, ".stack", cwd)
    if (membership?.number) {
      const detail = await ghApi(`repos/${repo}/stacks/${membership.number}`, undefined, cwd)
      const layers = (detail?.pull_requests ?? []).map((p: any, i: number) => ({
        position: i + 1,
        number: p.number,
        head: p.head?.ref ?? null,
        base: p.base?.ref ?? null,
        state: p.state ?? null,
        merged: Boolean(p.merged_at),
      }))
      // `position` is 1-based from the trunk and is authoritative; the listed
      // order is only a fallback for locating this PR among the layers.
      const self =
        typeof membership.position === "number" ? membership.position - 1 : layers.findIndex((l: any) => l.number === prNumber)
      return {
        native: true,
        source: "server",
        stackNumber: membership.number,
        trunk: membership.base?.ref ?? detail?.base?.ref ?? null,
        position: self >= 0 ? self + 1 : null,
        size: membership.size ?? layers.length,
        below: self > 0 ? layers[self - 1] : null,
        above: self >= 0 && self < layers.length - 1 ? layers[self + 1] : null,
        layers,
      }
    }
  }

  if (base !== defBranch) {
    let basePR: any = null
    try {
      basePR = (await runGhJson(["pr", "list", "--head", base, "--state", "all", "--json", "number,title", "--jq", ".[0]"], cwd)) ?? null
    } catch {
      // none
    }
    if (basePR) {
      return {
        native: false,
        trunk: null,
        basePR,
        note: `Branch targets non-default base "${base}" but is not in a native stack. Link it with \`gh stack link --base <trunk> …\` (never omit --base: it silently retargets to ${defBranch}).`,
      }
    }
  }

  return null
}

export const related_scan = tool({
  description:
    "Scan the current branch for Issues and PRs to link when opening a PR. Reads the branch's commit messages and name for issue references, finds an existing open PR for the branch, runs targeted keyword searches for related Issues/PRs, and reports native GitHub stack membership — trunk, position, size, the layers below and above, and whether the stack needs a rebase — including for a layer that has no PR yet. Read-only; local refs plus targeted gh queries (no file-overlap deep scan). Explicit refs are high-confidence; search hits are candidates to confirm, never fabricate.",
  args: {
    base: tool.schema.string().optional().describe("Base branch (defaults to the repo's default branch)."),
    head: tool.schema.string().optional().describe("Head branch (defaults to the current branch)."),
    keywords: tool.schema.string().optional().describe("Override the keyword query for the Issue/PR search."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const head = args.head?.trim() || (await runGit(["rev-parse", "--abbrev-ref", "HEAD"], cwd)).trim()
    let defBranch = "main"
    try {
      defBranch = (await runGh(["repo", "view", "--json", "defaultBranchRef", "--jq", ".defaultBranchRef.name"], cwd)).trim() || "main"
    } catch {
      // not resolvable; assume main
    }
    const base = args.base?.trim() || defBranch
    const { full } = await resolveRepo(undefined, cwd)

    let log = ""
    try {
      log = await runGit(["log", `${base}..${head}`, "--pretty=%s%n%b%n--"], cwd)
    } catch {
      // base/head not comparable
    }
    const { closes, refs } = parseIssueRefs(log)
    const bm = head.match(/(?:^|[/_-])(\d+)(?:[/_-]|$)/)
    if (bm) refs.push(parseInt(bm[1], 10))

    let existingPR: any = null
    try {
      existingPR = (await runGhJson(["pr", "list", "--head", head, "--state", "open", "--json", "number,title,url", "--jq", ".[0]"], cwd)) ?? null
    } catch {
      // none / not resolvable
    }

    const keywords = args.keywords?.trim() || head.replace(/[/_-]+/g, " ").replace(/\b\d+\b/g, "").trim()
    let issueCandidates: any[] = []
    let relatedPRs: any[] = []
    if (keywords) {
      try {
        issueCandidates = (await runGhJson(["issue", "list", "--state", "open", "--search", keywords, "--json", "number,title", "-L", "10"], cwd)) ?? []
      } catch {
        // search unavailable
      }
      try {
        relatedPRs = (await runGhJson(["pr", "list", "--state", "open", "--search", keywords, "--json", "number,title", "-L", "10"], cwd)) ?? []
      } catch {
        // search unavailable
      }
    }
    if (existingPR) relatedPRs = relatedPRs.filter((p: any) => p.number !== existingPR.number)

    const stack = await describeStack({ repo: full, prNumber: existingPR?.number ?? null, head, base, defBranch, cwd })

    return JSON.stringify(
      {
        base,
        head,
        repo: full,
        existingPR,
        closes: [...new Set(closes)].map((n) => ({ number: n, source: "commit" })),
        refs: [...new Set(refs)].map((n) => ({ number: n, source: "commit-or-branch" })),
        issueCandidates: issueCandidates.map((i: any) => ({ ...i, source: "search" })),
        relatedPRs: relatedPRs.map((p: any) => ({ ...p, source: "search" })),
        stack,
      },
      null,
      2,
    )
  },
})
