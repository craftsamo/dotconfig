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

function scanLine(file: string, line: number, content: string, out: Finding[]): void {
  for (const { rule, re } of SECRET_RULES) {
    const m = content.match(re)
    if (m) out.push({ file, line, rule, redacted: redact(m[0]), source: "builtin" })
  }
  const looksEnv = /\.env(\.|$)/.test(file)
  for (const tok of content.match(/[A-Za-z0-9+/=_\-]{20,}/g) ?? []) {
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
    "Scan a diff for secrets before committing. Scans the staged diff by default (or the worktree, or a commit range). Uses built-in rules (known key prefixes, private-key blocks, secret-looking assignments, high-entropy tokens, .env values) and delegates to gitleaks when installed. Secret values are always redacted. Returns { pass, findings }. Read-only.",
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
    "Trace a change to its origin: commit -> PR -> Issue. Give a `sha`, or `file` + `lines` (e.g. \"10,20\") to blame the commit first. Returns the commit, the pull requests that introduced it (via the GitHub commits/{sha}/pulls API), and the Issues those PRs close, plus link-ready refs (bare short SHA, #PR, #Issue). Read-only; does not run bisect. Local/unpushed commits return no PRs.",
  args: {
    sha: tool.schema.string().optional().describe("Commit SHA to trace. If omitted, provide file + lines."),
    file: tool.schema.string().optional().describe("File to blame when no sha is given."),
    lines: tool.schema.string().optional().describe('Line range for blame, e.g. "10,20" or "10,+5".'),
    repo: tool.schema.string().optional().describe('"owner/repo". Defaults to the current repository.'),
  },
  async execute(args, context) {
    const cwd = context.worktree
    let sha = args.sha?.trim()
    let blameNote: string | undefined
    if (!sha) {
      if (!args.file || !args.lines) throw new Error('Provide `sha`, or `file` + `lines` (e.g. "10,20").')
      const blame = await runGit(["blame", "-w", "-C", "-L", args.lines, "--porcelain", "--", args.file], cwd)
      sha = blame.split("\n")[0]?.split(" ")[0]
      if (!sha || !/^[0-9a-f]{7,40}$/.test(sha)) throw new Error("Could not determine a commit from blame.")
      blameNote = `from blame ${args.file}:${args.lines}`
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
    return JSON.stringify({ commit, blameNote, repo: full, pulls, issues, links }, null, 2)
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

export const related_scan = tool({
  description:
    "Scan the current branch for Issues and PRs to link when opening a PR. Reads the branch's commit messages and name for issue references, finds an existing open PR for the branch, and runs targeted keyword searches for related Issues/PRs and a stacked base PR. Read-only; local refs plus targeted gh queries (no file-overlap deep scan). Explicit refs are high-confidence; search hits are candidates to confirm, never fabricate.",
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

    let stackedBasePR: any = null
    if (base !== defBranch) {
      try {
        stackedBasePR = (await runGhJson(["pr", "list", "--head", base, "--state", "all", "--json", "number,title", "--jq", ".[0]"], cwd)) ?? null
      } catch {
        // none
      }
    }

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
        stackedBasePR,
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
    const subjects = (await runGit(["log", "--no-merges", `-${limit}`, "--pretty=%s"], cwd)).split("\n").filter(Boolean)
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
