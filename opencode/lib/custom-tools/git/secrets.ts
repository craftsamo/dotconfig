import { tool } from "../define"
import { exec, runGit, which } from "../exec"

export type Finding = { file: string; line: number; rule: string; redacted: string; source: "builtin" | "gitleaks" }

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

export function scanDiff(diff: string): Finding[] {
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

export function dedupe(list: Finding[]): Finding[] {
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

async function runGitleaks(target: string, range: string | undefined, cwd?: string): Promise<Finding[]> {
  const common = ["--redact", "--report-format", "json", "--report-path", "/dev/stdout", "--no-banner"]
  const argv =
    target === "range"
      ? ["detect", ...common, ...(range ? ["--log-opts", range] : [])]
      : ["protect", ...common, ...(target === "staged" ? ["--staged"] : [])]
  const out = (await exec(["gitleaks", ...argv], { cwd })).stdout.trim()
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
    if (which("gitleaks")) {
      gitleaksRan = true
      gitleaks = await runGitleaks(target, args.range, cwd)
    }
    const findings = dedupe([...builtin, ...gitleaks])
    return JSON.stringify({ pass: findings.length === 0, target, gitleaksRan, count: findings.length, findings }, null, 2)
  },
})
