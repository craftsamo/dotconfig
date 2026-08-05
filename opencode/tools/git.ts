import { tool } from "@opencode-ai/plugin"

/**
 * Git workflow toolset.
 *
 * Deterministic, read/index-only mechanics that the git-commit and
 * git-pullrequest skills delegate to. The conventions (when/how to commit or
 * open a PR) live in those skills; the mechanics live here.
 *
 * Safety: these tools run git/gh internally via Bun.$, which does NOT pass
 * through the shell permission gates, so they are deliberately limited to read
 * and index operations. They never commit, push, or merge — those stay as
 * gated commands the agent issues directly.
 */

async function runGit(argv: string[], cwd?: string): Promise<string> {
  let p = Bun.$`git ${argv}`
  if (cwd) p = p.cwd(cwd)
  const res = await p.nothrow().quiet()
  if (res.exitCode !== 0) {
    const err = res.stderr.toString().trim() || res.stdout.toString().trim()
    throw new Error(`git ${argv.join(" ")} failed (exit ${res.exitCode}):\n${err}`)
  }
  return res.stdout.toString()
}

async function tryGit(argv: string[], cwd?: string): Promise<{ ok: boolean; stdout: string; code: number }> {
  let p = Bun.$`git ${argv}`
  if (cwd) p = p.cwd(cwd)
  const res = await p.nothrow().quiet()
  return { ok: res.exitCode === 0, stdout: res.stdout.toString(), code: res.exitCode ?? -1 }
}

// ---- secret scanning ------------------------------------------------------

type Finding = { file: string; line: number; rule: string; redacted: string; source: "builtin" | "gitleaks" }

const SECRET_RULES: { rule: string; re: RegExp }[] = [
  { rule: "aws-access-key-id", re: /\bAKIA[0-9A-Z]{16}\b/ },
  { rule: "github-pat", re: /\bghp_[A-Za-z0-9]{36,}\b/ },
  { rule: "github-fine-grained-pat", re: /\bgithub_pat_[A-Za-z0-9_]{22,}\b/ },
  { rule: "github-oauth-token", re: /\bgh[osur]_[A-Za-z0-9]{30,}\b/ },
  { rule: "slack-token", re: /\bxox[baprs]-[A-Za-z0-9-]{10,}\b/ },
  { rule: "google-api-key", re: /\bAIza[0-9A-Za-z_\-]{35}\b/ },
  { rule: "private-key-block", re: /-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----/ },
  {
    rule: "secret-assignment",
    re: /\b(?:password|passwd|secret|token|api[_-]?key|access[_-]?key|client[_-]?secret|private[_-]?key)\b\s*[:=]\s*['"]?[A-Za-z0-9+/=_\-]{12,}/i,
  },
]

function shannonEntropy(s: string): number {
  if (!s) return 0
  const freq: Record<string, number> = {}
  for (const ch of s) freq[ch] = (freq[ch] ?? 0) + 1
  let e = 0
  for (const k in freq) {
    const p = freq[k] / s.length
    e -= p * Math.log2(p)
  }
  return e
}

function redact(secret: string): string {
  const s = secret.trim()
  if (s.length <= 8) return `*** [${s.length} chars]`
  return `${s.slice(0, 3)}...${s.slice(-3)} [${s.length} chars]`
}

// Files whose bulk is integrity hashes / generated blobs — exempt from the
// entropy heuristic only; the explicit SECRET_RULES still apply everywhere.
const HASH_MANIFEST_RE =
  /(^|\/)(package-lock\.json|npm-shrinkwrap\.json|pnpm-lock\.yaml|bun\.lockb|go\.sum|packages\.lock\.json|gradle\.lockfile)$|\.(lock|min\.js|min\.css|map|svg)$/i
// Integrity-hash tokens (npm `sha512-...` style) are checksums, not secrets.
const HASH_TOKEN_RE = /^(sha\d+|blake2b|blake3|md5)-/i

function scanLine(file: string, line: number, content: string, out: Finding[]): void {
  for (const { rule, re } of SECRET_RULES) {
    const m = content.match(re)
    if (m) out.push({ file, line, rule, redacted: redact(m[0]), source: "builtin" })
  }
  if (HASH_MANIFEST_RE.test(file)) return
  const looksEnv = /\.env(\.|$)/.test(file)
  for (const tok of content.match(/[A-Za-z0-9+/=_\-]{20,}/g) ?? []) {
    if (HASH_TOKEN_RE.test(tok)) continue
    const ent = shannonEntropy(tok)
    if ((ent >= 4.0 && tok.length >= 24) || (looksEnv && tok.length >= 16 && ent >= 3.0)) {
      out.push({ file, line, rule: "high-entropy", redacted: redact(tok), source: "builtin" })
    }
  }
}

function scanDiff(diff: string): Finding[] {
  const out: Finding[] = []
  let file = ""
  let newLine = 0
  for (const raw of diff.split("\n")) {
    if (raw.startsWith("diff --git")) {
      file = ""
      continue
    }
    if (raw.startsWith("+++ ")) {
      const m = raw.match(/^\+\+\+ b\/(.*)$/)
      file = m ? m[1] : raw.slice(4).replace(/^b\//, "")
      continue
    }
    if (raw.startsWith("--- ")) continue
    const hm = raw.match(/^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@/)
    if (hm) {
      newLine = parseInt(hm[1], 10)
      continue
    }
    if (raw.startsWith("+")) {
      scanLine(file, newLine, raw.slice(1), out)
      newLine++
      continue
    }
    if (raw.startsWith("-")) continue
    if (raw.startsWith(" ")) newLine++
  }
  return out
}

function dedupe(list: Finding[]): Finding[] {
  const seen = new Set<string>()
  const out: Finding[] = []
  for (const f of list) {
    const k = `${f.file}:${f.line}:${f.rule}:${f.redacted}`
    if (!seen.has(k)) {
      seen.add(k)
      out.push(f)
    }
  }
  return out
}

async function hasGitleaks(): Promise<boolean> {
  const res = await Bun.$`which gitleaks`.nothrow().quiet()
  return res.exitCode === 0
}

async function runGitleaks(target: string, range: string | undefined, cwd?: string): Promise<Finding[]> {
  const common = ["--redact", "--report-format", "json", "--report-path", "/dev/stdout", "--no-banner"]
  const argv =
    target === "range"
      ? ["detect", ...common, ...(range ? ["--log-opts", range] : [])]
      : ["protect", ...common, ...(target === "staged" ? ["--staged"] : [])]
  let p = Bun.$`gitleaks ${argv}`
  if (cwd) p = p.cwd(cwd)
  const res = await p.nothrow().quiet()
  const out = res.stdout.toString().trim()
  if (!out) return []
  try {
    const parsed = JSON.parse(out)
    return (Array.isArray(parsed) ? parsed : []).map((f: any) => ({
      file: String(f.File ?? ""),
      line: Number(f.StartLine ?? 0),
      rule: String(f.RuleID ?? "gitleaks"),
      redacted: String(f.Secret ?? f.Match ?? "").slice(0, 16),
      source: "gitleaks" as const,
    }))
  } catch {
    return []
  }
}

export const secret_scan = tool({
  description:
    "Scan a diff for secrets before committing. Scans the staged diff by default (or the worktree, or a commit range). Uses built-in rules (known key prefixes, private-key blocks, secret-looking assignments, high-entropy tokens, .env values) and delegates to gitleaks when installed; lockfiles and integrity hashes are exempt from the entropy heuristic to avoid false positives. Secret values are always redacted. Returns { pass, findings }. Read-only.",
  args: {
    target: tool.schema
      .enum(["staged", "worktree", "range"])
      .optional()
      .describe('What to scan: "staged" (default) = git diff --cached, "worktree" = unstaged, "range" = a commit range.'),
    range: tool.schema.string().optional().describe('Commit range when target is "range", e.g. "main..HEAD".'),
    paths: tool.schema.array(tool.schema.string()).optional().describe("Optional path filter."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const target = args.target ?? "staged"
    const diffArgs = ["diff", "--no-color", "--unified=0"]
    if (target === "staged") diffArgs.push("--cached")
    else if (target === "range") {
      if (!args.range) throw new Error('target "range" requires `range`, e.g. "main..HEAD".')
      diffArgs.push(args.range)
    }
    if (args.paths?.length) diffArgs.push("--", ...args.paths)
    const diff = await runGit(diffArgs, cwd)
    const builtin = scanDiff(diff)
    let gitleaksRan = false
    let gitleaks: Finding[] = []
    if (await hasGitleaks()) {
      gitleaksRan = true
      gitleaks = await runGitleaks(target, args.range, cwd)
    }
    const findings = dedupe([...builtin, ...gitleaks])
    return JSON.stringify({ pass: findings.length === 0, target, gitleaksRan, count: findings.length, findings }, null, 2)
  },
})

// ---- hunk staging ---------------------------------------------------------

type Hunk = {
  id: number
  file: string
  header: string
  preamble: string
  body: string
  added: number
  removed: number
  binary: boolean
}

function parseHunks(diff: string): Hunk[] {
  const hunks: Hunk[] = []
  const lines = diff.split("\n")
  let id = 0
  let i = 0
  while (i < lines.length) {
    if (!lines[i].startsWith("diff --git")) {
      i++
      continue
    }
    const fm = lines[i].match(/^diff --git a\/(.*) b\/(.*)$/)
    const file = fm ? fm[2] : ""
    const preambleLines = [lines[i]]
    i++
    let binary = false
    while (i < lines.length && !lines[i].startsWith("@@") && !lines[i].startsWith("diff --git")) {
      if (lines[i].startsWith("Binary files")) binary = true
      preambleLines.push(lines[i])
      i++
    }
    const preamble = preambleLines.join("\n")
    if (binary) {
      hunks.push({ id: ++id, file, header: "(binary)", preamble, body: "", added: 0, removed: 0, binary: true })
      continue
    }
    while (i < lines.length && lines[i].startsWith("@@")) {
      const bodyLines = [lines[i]]
      const header = lines[i]
      i++
      let added = 0
      let removed = 0
      while (i < lines.length && !lines[i].startsWith("@@") && !lines[i].startsWith("diff --git")) {
        if (lines[i].startsWith("+")) added++
        else if (lines[i].startsWith("-")) removed++
        bodyLines.push(lines[i])
        i++
      }
      // Drop the split artifact of the diff's trailing newline: kept, it
      // becomes an empty "context" line that --recount counts and git apply
      // then rejects ("patch does not apply") on the file's last hunk.
      while (bodyLines.length && bodyLines[bodyLines.length - 1] === "") bodyLines.pop()
      hunks.push({ id: ++id, file, header, preamble, body: bodyLines.join("\n"), added, removed, binary: false })
    }
  }
  return hunks
}

function buildPatch(selected: Hunk[]): string {
  const byFile = new Map<string, { preamble: string; bodies: string[] }>()
  for (const h of selected) {
    const cur = byFile.get(h.preamble) ?? { preamble: h.preamble, bodies: [] }
    cur.bodies.push(h.body)
    byFile.set(h.preamble, cur)
  }
  const parts: string[] = []
  for (const { preamble, bodies } of byFile.values()) {
    parts.push(preamble, ...bodies)
  }
  return parts.join("\n") + "\n"
}

export const stage_hunks = tool({
  description:
    "List and stage individual diff hunks deterministically — a reliable replacement for `git add -p`. Call with no selection (or list:true) to enumerate the unstaged hunks with stable ids; call with `hunks` (ids) and/or `include`/`exclude` (regex on hunk text) to stage exactly those via `git apply --cached`. Set denySecrets to refuse staging hunks that contain secrets. Operates on the index only (reversible); never commits. Returns the chosen hunks and the resulting staged stat.",
  args: {
    paths: tool.schema.array(tool.schema.string()).optional().describe("Limit to these files (default: all unstaged changes)."),
    list: tool.schema.boolean().optional().describe("List hunks without staging. Implied when no selection is given."),
    hunks: tool.schema.array(tool.schema.number()).optional().describe("Hunk ids to stage (from the list output)."),
    include: tool.schema.string().optional().describe("Stage only hunks whose text matches this regex."),
    exclude: tool.schema.string().optional().describe("Never stage hunks whose text matches this regex."),
    denySecrets: tool.schema.boolean().optional().describe("Scan selected hunks for secrets and refuse to stage if any are found."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const diffArgs = ["diff", "--no-color"]
    if (args.paths?.length) diffArgs.push("--", ...args.paths)
    const hunks = parseHunks(await runGit(diffArgs, cwd))

    if (args.list || (!args.hunks?.length && !args.include)) {
      return JSON.stringify(
        {
          mode: "list",
          count: hunks.length,
          hunks: hunks.map((h) => ({
            id: h.id,
            file: h.file,
            header: h.header,
            added: h.added,
            removed: h.removed,
            binary: h.binary,
            preview: h.body.split("\n").slice(0, 8),
          })),
        },
        null,
        2,
      )
    }

    let selected = hunks.filter((h) => !h.binary)
    if (args.hunks?.length) {
      const set = new Set(args.hunks)
      selected = selected.filter((h) => set.has(h.id))
    }
    if (args.include) {
      const re = new RegExp(args.include)
      selected = selected.filter((h) => re.test(h.body))
    }
    if (args.exclude) {
      const re = new RegExp(args.exclude)
      selected = selected.filter((h) => !re.test(h.body))
    }
    if (!selected.length) throw new Error("No hunks matched the selection.")

    if (args.denySecrets) {
      const findings = dedupe(scanDiff(buildPatch(selected)))
      if (findings.length) {
        return JSON.stringify({ mode: "blocked", reason: "secret findings in selected hunks", findings }, null, 2)
      }
    }

    const tmp = `${Bun.env.TMPDIR ?? "/tmp"}/opencode-stage-${Date.now()}-${Math.random().toString(36).slice(2)}.patch`
    await Bun.write(tmp, buildPatch(selected))
    try {
      await runGit(["apply", "--cached", "--recount", "--whitespace=nowarn", tmp], cwd)
    } finally {
      await Bun.$`rm -f ${tmp}`.nothrow().quiet()
    }
    const staged = await runGit(["diff", "--cached", "--stat"], cwd)
    return JSON.stringify({ mode: "staged", stagedHunkIds: selected.map((h) => h.id), staged: staged.trim() }, null, 2)
  },
})

// ---- gh helpers + provenance ----------------------------------------------

async function runGh(argv: string[], cwd?: string): Promise<string> {
  let p = Bun.$`gh ${argv}`
  if (cwd) p = p.cwd(cwd)
  const res = await p.nothrow().quiet()
  if (res.exitCode !== 0) {
    const err = res.stderr.toString().trim() || res.stdout.toString().trim()
    throw new Error(`gh ${argv.join(" ")} failed (exit ${res.exitCode}):\n${err}`)
  }
  return res.stdout.toString()
}

async function runGhJson(argv: string[], cwd?: string): Promise<any> {
  const out = (await runGh(argv, cwd)).trim()
  return out ? JSON.parse(out) : null
}

async function resolveRepo(repo: string | undefined, cwd?: string): Promise<{ full: string }> {
  const r = (repo ?? "").trim()
  if (r.includes("/")) return { full: r }
  const full = (await runGh(["repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"], cwd)).trim()
  return { full }
}

export const provenance = tool({
  description:
    "Trace a change to its origin: commit -> PR -> Issue. Anchor with a `sha`, with `file` + `lines` (blame), or with `token`/`regex` to pickaxe the commit that introduced a string (anchored on the oldest hit — the introducer; the newest hit is reported alongside). Returns the commit, the pull requests that introduced it (via the GitHub commits/{sha}/pulls API), and the Issues those PRs close, plus link-ready refs (bare short SHA, #PR, #Issue). Read-only; does not run bisect. Local/unpushed commits return no PRs.",
  args: {
    sha: tool.schema.string().optional().describe("Commit SHA to trace. If omitted, provide file + lines, or token/regex."),
    file: tool.schema.string().optional().describe("File to blame (with lines) or to scope a token/regex search."),
    lines: tool.schema.string().optional().describe('Line range for blame, e.g. "10,20" or "10,+5".'),
    token: tool.schema.string().optional().describe("Find the commit that introduced this exact string (pickaxe, git log -S)."),
    regex: tool.schema.string().optional().describe("Find the commit that introduced a match of this regex (git log -G)."),
    repo: tool.schema.string().optional().describe('"owner/repo". Defaults to the current repository.'),
  },
  async execute(args, context) {
    const cwd = context.worktree
    let sha = args.sha?.trim()
    let locatedBy: string | undefined
    let pickaxe: { hits: number; newest?: string; oldest?: string } | undefined
    if (!sha) {
      if (args.file && args.lines) {
        const blame = await runGit(["blame", "-w", "-C", "-L", args.lines, "--porcelain", "--", args.file], cwd)
        sha = blame.split("\n")[0]?.split(" ")[0]
        locatedBy = `blame ${args.file}:${args.lines}`
      } else if (args.token || args.regex) {
        const pick = args.token ? ["-S", args.token] : ["-G", args.regex as string]
        const argv = ["log", ...pick, "--format=%H"]
        if (args.file) argv.push("--", args.file)
        // Oldest hit = the commit that introduced the string; newer hits are
        // later edits or removals of it.
        const hits = (await runGit(argv, cwd)).split("\n").map((s) => s.trim()).filter(Boolean)
        sha = hits[hits.length - 1]
        pickaxe = { hits: hits.length, newest: hits[0]?.slice(0, 8), oldest: sha?.slice(0, 8) }
        locatedBy = `${args.token ? `pickaxe -S "${args.token}"` : `pickaxe -G "${args.regex}"`} (oldest of ${hits.length} hit(s))`
      } else {
        throw new Error("Provide `sha`, `file` + `lines`, or `token`/`regex`.")
      }
      if (!sha || !/^[0-9a-f]{7,40}$/.test(sha)) throw new Error("Could not locate a commit from the given anchor.")
    }
    const { full } = await resolveRepo(args.repo, cwd)
    const meta = (await runGit(["show", "-s", "--format=%H%n%s%n%an%n%aI", sha], cwd)).split("\n")
    const commit = { sha: meta[0] ?? sha, subject: meta[1] ?? "", author: meta[2] ?? "", date: meta[3] ?? "" }
    let pulls: any[] = []
    try {
      pulls = (await runGhJson(["api", `repos/${full}/commits/${sha}/pulls`, "--jq", "[.[]|{number,title,state}]"], cwd)) ?? []
    } catch {
      pulls = []
    }
    const issues: any[] = []
    for (const pr of pulls) {
      try {
        const v = await runGhJson(
          ["pr", "view", String(pr.number), "--json", "closingIssuesReferences", "--jq", "[.closingIssuesReferences[]?|{number,title}]"],
          cwd,
        )
        for (const is of v ?? []) issues.push({ ...is, viaPR: pr.number })
      } catch {
        // PR not resolvable; skip
      }
    }
    const links = {
      commit: commit.sha.slice(0, 8),
      prs: pulls.map((p: any) => `#${p.number}`),
      issues: issues.map((i: any) => `#${i.number}`),
    }
    return JSON.stringify({ commit, locatedBy, pickaxe, repo: full, pulls, issues, links }, null, 2)
  },
})

// ---- related-work scanning ------------------------------------------------

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

// ---- history digest (convention signals) ----------------------------------

async function fileExists(cwd: string, rel: string): Promise<boolean> {
  try {
    return await Bun.file(`${cwd}/${rel}`).exists()
  } catch {
    return false
  }
}

export const history_digest = tool({
  description:
    "Gather signals for inferring a repository's commit and PR conventions: recent commit subjects with conventional-commit type/scope frequencies, presence of commitlint / .gitmessage / commitizen / CONTRIBUTING config, recent merged PR titles, and whether a PR template exists. Read-only — the inference itself stays a judgment step in the skills.",
  args: {
    limit: tool.schema.number().optional().describe("How many recent non-merge commits to sample (default 30)."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const limit = args.limit ?? 30
    // Tolerate an unborn HEAD (no commits yet): report an empty sample.
    const logRes = await tryGit(["log", "--no-merges", `-${limit}`, "--pretty=%s"], cwd)
    const subjects = logRes.ok ? logRes.stdout.split("\n").filter(Boolean) : []
    const typeFrequency: Record<string, number> = {}
    const scopes = new Set<string>()
    let conventional = 0
    for (const s of subjects) {
      const m = s.match(/^(\w+)(?:\(([^)]+)\))?!?:\s/)
      if (m) {
        conventional++
        typeFrequency[m[1]] = (typeFrequency[m[1]] ?? 0) + 1
        if (m[2]) scopes.add(m[2])
      }
    }
    const configCandidates = [
      "commitlint.config.js",
      "commitlint.config.cjs",
      "commitlint.config.mjs",
      "commitlint.config.ts",
      ".commitlintrc",
      ".commitlintrc.json",
      ".commitlintrc.js",
      ".commitlintrc.yml",
      ".commitlintrc.yaml",
      ".gitmessage",
      ".czrc",
      ".cz.json",
      "cz.config.js",
      "CONTRIBUTING.md",
      ".github/CONTRIBUTING.md",
    ]
    const commitConfigFiles: string[] = []
    for (const c of configCandidates) if (await fileExists(cwd, c)) commitConfigFiles.push(c)

    const prTemplateCandidates = [
      ".github/PULL_REQUEST_TEMPLATE.md",
      ".github/pull_request_template.md",
      "PULL_REQUEST_TEMPLATE.md",
      "docs/PULL_REQUEST_TEMPLATE.md",
    ]
    let prTemplate: string | null = null
    for (const c of prTemplateCandidates)
      if (await fileExists(cwd, c)) {
        prTemplate = c
        break
      }

    let prTitles: string[] = []
    try {
      prTitles = (await runGhJson(["pr", "list", "--state", "merged", "--limit", "15", "--json", "title", "--jq", "[.[].title]"], cwd)) ?? []
    } catch {
      // gh unavailable / no network
    }

    return JSON.stringify(
      {
        commitSampleSize: subjects.length,
        conventionalRatio: subjects.length ? +(conventional / subjects.length).toFixed(2) : 0,
        typeFrequency,
        scopes: [...scopes],
        commitConfigFiles,
        commitSubjects: subjects.slice(0, 15),
        prTitles,
        prTemplate,
      },
      null,
      2,
    )
  },
})

// ---- amend safety ---------------------------------------------------------

export const amend_check = tool({
  description:
    "Classify whether a commit can be safely amended or fixed up in place (local and unpushed) or must be corrected with a new linked-fix commit (already published). Checks whether the commit is HEAD, is in the branch's upstream, and is on any remote branch. Read-only; never rewrites history. Returns a recommendation of amend / fixup / linked-fix.",
  args: {
    sha: tool.schema.string().optional().describe("Commit to check. Defaults to HEAD."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const ref = args.sha?.trim() || "HEAD"
    const sha = (await runGit(["rev-parse", ref], cwd)).trim()
    const head = (await runGit(["rev-parse", "HEAD"], cwd)).trim()
    const isHead = sha === head

    let hasUpstream = false
    let inUpstream = false
    const up = await tryGit(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd)
    if (up.ok) {
      hasUpstream = true
      inUpstream = (await tryGit(["merge-base", "--is-ancestor", sha, "@{u}"], cwd)).ok
    }

    const rb = await tryGit(["branch", "-r", "--contains", sha], cwd)
    const remoteBranches = rb.ok ? rb.stdout.split("\n").map((s) => s.trim()).filter(Boolean) : []
    const pushed = inUpstream || remoteBranches.length > 0

    let recommendation: "amend" | "fixup" | "linked-fix"
    let reason: string
    if (pushed) {
      recommendation = "linked-fix"
      reason = "Commit is already published; do not rewrite it. Make a new commit that links it."
    } else if (isHead) {
      recommendation = "amend"
      reason = "Commit is local, unpushed, and is HEAD; `git commit --amend` is safe."
    } else {
      recommendation = "fixup"
      reason = "Commit is local and unpushed but not HEAD; use `git commit --fixup` + `git rebase --autosquash`."
    }

    return JSON.stringify({ sha, ref, isHead, hasUpstream, inUpstream, remoteBranches, pushed, recommendation, reason }, null, 2)
  },
})

// ---- commit message lint --------------------------------------------------

type Violation = { rule: string; severity: "error" | "warning"; message: string }

const EMOJI_RE = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{1F1E6}-\u{1F1FF}\uFE0F]/u

function lintMessage(message: string, allowTrailers: boolean, subjectMax: number): Violation[] {
  const v: Violation[] = []
  const lines = message.replace(/\r\n/g, "\n").split("\n")
  const subject = lines[0] ?? ""
  if (subject.length > subjectMax)
    v.push({ rule: "subject-hard-max", severity: "error", message: `Subject is ${subject.length} chars; hard limit ${subjectMax}.` })
  else if (subject.length > 50) v.push({ rule: "subject-target", severity: "warning", message: `Subject is ${subject.length} chars; aim for <= 50.` })
  if (subject !== subject.trim()) v.push({ rule: "subject-whitespace", severity: "warning", message: "Subject has leading or trailing whitespace." })
  if (/\.$/.test(subject.trim())) v.push({ rule: "subject-period", severity: "warning", message: "Subject ends with a period." })
  if (!/^[a-z]+(\([^)]+\))?!?: .+/.test(subject) && !/^(Merge|Revert)\b/.test(subject))
    v.push({ rule: "conventional", severity: "warning", message: "Subject is not `type(scope): summary`." })
  if (lines.length > 1 && lines[1].trim() !== "")
    v.push({ rule: "blank-line", severity: "error", message: "Missing blank line between subject and body." })
  let inFence = false
  for (let i = 2; i < lines.length; i++) {
    const l = lines[i]
    if (/^\s*(```|~~~)/.test(l)) {
      inFence = !inFence
      continue
    }
    if (inFence) continue
    if (l.length > 72 && !/^\s*(https?:\/\/|[-*]\s|\d+\.\s|\|)/.test(l))
      v.push({ rule: "body-wrap", severity: "warning", message: `Body line ${i + 1} is ${l.length} chars; wrap near 72.` })
  }
  if (EMOJI_RE.test(message)) v.push({ rule: "emoji", severity: "warning", message: "Message contains emoji." })
  if (!allowTrailers && (/^(co-authored-by|signed-off-by|generated[ -]?by):/im.test(message) || /generated with /i.test(message)))
    v.push({ rule: "trailer", severity: "warning", message: "Message contains an attribution or generated trailer." })
  const body = lines.slice(2).join("\n")
  const paths = body.match(/(?:^|\s)(?:[\w.-]+\/){2,}[\w.-]+\.\w+/g) ?? []
  if (paths.length)
    v.push({ rule: "path-enumeration", severity: "warning", message: `Body has multi-segment path(s): ${paths.slice(0, 3).map((s) => s.trim()).join(", ")}.` })
  if (/\b(?:line\s+\d+|L\d+)\b/i.test(body) || /\.\w+:\d{1,5}\b/.test(body))
    v.push({ rule: "line-numbers", severity: "warning", message: "Body references line numbers." })
  return v
}

export const commit_lint = tool({
  description:
    "Validate a candidate commit message before committing. Checks subject length (<=50 target, <=72 hard), conventional `type(scope): summary` structure, the blank line before the body, body wrap (~72), emoji, attribution/generated trailers, and file-path/line-number noise. If the repo has a local commitlint binary it is also run and its violations merged (authoritative). Read-only. Returns { pass, errors, warnings }.",
  args: {
    message: tool.schema.string().describe("The full candidate commit message (subject, blank line, body)."),
    allowTrailers: tool.schema.boolean().optional().describe("Permit attribution/generated trailers (default false)."),
    subjectMax: tool.schema.number().optional().describe("Hard subject length limit (default 72)."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const violations = lintMessage(args.message, args.allowTrailers ?? false, args.subjectMax ?? 72)
    let commitlintRan = false
    if (await fileExists(cwd, "node_modules/.bin/commitlint")) {
      commitlintRan = true
      const tmp = `${Bun.env.TMPDIR ?? "/tmp"}/opencode-commitmsg-${Date.now()}-${Math.random().toString(36).slice(2)}.txt`
      await Bun.write(tmp, args.message)
      try {
        const res = await Bun.$`${cwd}/node_modules/.bin/commitlint --edit ${tmp} --no-color`.cwd(cwd).nothrow().quiet()
        if (res.exitCode !== 0) {
          const out = `${res.stdout.toString()}\n${res.stderr.toString()}`.trim()
          violations.push({ rule: "commitlint", severity: "error", message: out || "commitlint reported problems." })
        }
      } finally {
        await Bun.$`rm -f ${tmp}`.nothrow().quiet()
      }
    }
    const errors = violations.filter((x) => x.severity === "error")
    const warnings = violations.filter((x) => x.severity === "warning")
    return JSON.stringify({ pass: errors.length === 0, commitlintRan, errors, warnings }, null, 2)
  },
})
