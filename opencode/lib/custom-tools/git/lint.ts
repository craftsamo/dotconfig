import { join } from "path"
import { tool } from "../define"
import { exec, tryGit, withTempFile } from "../exec"
import { COMMITLINT_CONFIGS, fileExists } from "./shared"

export type Violation = { rule: string; severity: "error" | "warning"; message: string }

const EMOJI_RE = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{1F1E6}-\u{1F1FF}\uFE0F]/u

export function lintMessage(message: string, allowTrailers: boolean, subjectMax: number): Violation[] {
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

/** The first line of the repository's commit-msg hook that runs commitlint, if any. */
async function commitlintHook(cwd: string): Promise<string | null> {
  const hooks = await tryGit(["rev-parse", "--path-format=absolute", "--git-path", "hooks/commit-msg"], cwd)
  // husky points core.hooksPath at a generated .husky/_, which may be missing
  // in a fresh worktree; the hook it runs is .husky/commit-msg.
  const candidates = [hooks.ok ? hooks.stdout.trim() : "", join(cwd, ".husky", "commit-msg")].filter(Boolean)
  for (const path of candidates) {
    let text = ""
    try {
      text = await Bun.file(path).text()
    } catch {
      continue
    }
    const line = text.split("\n").find((l) => /commitlint/.test(l) && !/^\s*#/.test(l))
    if (line) return line.trim()
  }
  return null
}

async function commitlintConfigured(cwd: string): Promise<boolean> {
  for (const name of COMMITLINT_CONFIGS) if (await fileExists(cwd, name)) return true
  try {
    return "commitlint" in (await Bun.file(join(cwd, "package.json")).json())
  } catch {
    return false
  }
}

export type CommitlintStatus = "ran" | "not-installed" | "not-configured"

/**
 * Runs the repository's own commitlint on `messageFile`. When it is not
 * installed, a commit-msg hook that runs it makes that an error (the commit
 * would fail there), a configuration alone a warning.
 */
export async function commitlint(
  messageFile: string,
  cwd: string,
): Promise<{ status: CommitlintStatus; hook: string | null; violations: Violation[] }> {
  const hook = await commitlintHook(cwd)
  if (await fileExists(cwd, "node_modules/.bin/commitlint")) {
    const res = await exec([`${cwd}/node_modules/.bin/commitlint`, "--edit", messageFile, "--no-color"], { cwd })
    if (res.ok) return { status: "ran", hook, violations: [] }
    const out = `${res.stdout}\n${res.stderr}`.trim()
    return { status: "ran", hook, violations: [{ rule: "commitlint", severity: "error", message: out || "commitlint reported problems." }] }
  }
  if (hook)
    return {
      status: "not-installed",
      hook,
      violations: [
        {
          rule: "commitlint-not-installed",
          severity: "error",
          message: `The commit-msg hook runs commitlint (\`${hook}\`), but it is not installed here; install the dependencies first, or the hook rejects the commit.`,
        },
      ],
    }
  if (await commitlintConfigured(cwd))
    return {
      status: "not-installed",
      hook,
      violations: [
        { rule: "commitlint-not-installed", severity: "warning", message: "A commitlint configuration exists but commitlint is not installed, so only the built-in rules ran." },
      ],
    }
  return { status: "not-configured", hook, violations: [] }
}

export const commit_lint = tool({
  description:
    "Validate a candidate commit message before committing. Checks subject length (<=50 target, <=72 hard), conventional `type(scope): summary` structure, the blank line before the body, body wrap (~72), emoji, attribution/generated trailers, and file-path/line-number noise. If the repo has a local commitlint binary it is also run and its violations merged (authoritative); `commitlint` reports ran / not-installed / not-configured, and a commit-msg hook that runs a missing commitlint is an error. Lint the exact text that will be committed — rewrapping it afterwards defeats the check. Read-only. Returns { pass, commitlint, hook, errors, warnings }.",
  args: {
    message: tool.schema.string().describe("The full candidate commit message (subject, blank line, body)."),
    allowTrailers: tool.schema.boolean().optional().describe("Permit attribution/generated trailers (default false)."),
    subjectMax: tool.schema.number().optional().describe("Hard subject length limit (default 72)."),
  },
  async execute(args, context) {
    const cwd = context.worktree
    const violations = lintMessage(args.message, args.allowTrailers ?? false, args.subjectMax ?? 72)
    const checked = await withTempFile("opencode-commitmsg", ".txt", args.message, (file) => commitlint(file, cwd))
    violations.push(...checked.violations)
    const errors = violations.filter((x) => x.severity === "error")
    const warnings = violations.filter((x) => x.severity === "warning")
    return JSON.stringify(
      { pass: errors.length === 0, commitlintRan: checked.status === "ran", commitlint: checked.status, hook: checked.hook, errors, warnings },
      null,
      2,
    )
  },
})
