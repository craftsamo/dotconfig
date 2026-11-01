import { join } from "path"
import { tool } from "../define"
import { exec, tryGit, withTempFile } from "../exec"
import { COMMITLINT_CONFIGS, fileExists } from "./shared"

export type Violation = { rule: string; severity: "error" | "warning"; message: string }

const EMOJI_RE = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{1F1E6}-\u{1F1FF}\uFE0F]/u
// East Asian Wide and Fullwidth ranges: a terminal and `git log` give each two columns.
const WIDE_RE =
  /[\u{1100}-\u{115F}\u{231A}\u{231B}\u{23E9}-\u{23EC}\u{23F0}\u{23F3}\u{25FD}\u{25FE}\u{2614}\u{2615}\u{2648}-\u{2653}\u{267F}\u{2693}\u{26A1}\u{26AA}\u{26AB}\u{26BD}\u{26BE}\u{26C4}\u{26C5}\u{26CE}\u{26D4}\u{26EA}\u{26F2}\u{26F3}\u{26F5}\u{26FA}\u{26FD}\u{2705}\u{270A}\u{270B}\u{2728}\u{274C}\u{274E}\u{2753}-\u{2755}\u{2757}\u{2795}-\u{2797}\u{27B0}\u{27BF}\u{2B1B}\u{2B1C}\u{2B50}\u{2B55}\u{2E80}-\u{303E}\u{3041}-\u{33FF}\u{3400}-\u{4DBF}\u{4E00}-\u{9FFF}\u{A000}-\u{A4CF}\u{AC00}-\u{D7A3}\u{F900}-\u{FAFF}\u{FE30}-\u{FE4F}\u{FF00}-\u{FF60}\u{FFE0}-\u{FFE6}\u{1F300}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{1F900}-\u{1F9FF}\u{1FA70}-\u{1FAFF}\u{20000}-\u{3FFFD}]/u
// Combining marks, zero-width joiners and variation selectors take no column.
const ZERO_WIDTH_RE = /[\u{0300}-\u{036F}\u{200B}-\u{200D}\u{FE00}-\u{FE0F}\u{20D0}-\u{20FF}]/u

/** Columns the text takes in a terminal: wide and fullwidth characters count two. */
export function displayWidth(text: string): number {
  let width = 0
  for (const ch of text) width += ZERO_WIDTH_RE.test(ch) ? 0 : WIDE_RE.test(ch) ? 2 : 1
  return width
}

export function lintMessage(message: string, allowTrailers: boolean, subjectMax: number): Violation[] {
  const v: Violation[] = []
  const lines = message.replace(/\r\n/g, "\n").split("\n")
  const subject = lines[0] ?? ""
  const subjectWidth = displayWidth(subject)
  if (subjectWidth > subjectMax)
    v.push({ rule: "subject-hard-max", severity: "error", message: `Subject is ${subjectWidth} columns; hard limit ${subjectMax}.` })
  else if (subjectWidth > 50) v.push({ rule: "subject-target", severity: "warning", message: `Subject is ${subjectWidth} columns; aim for <= 50.` })
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
    if (displayWidth(l) > 72 && !/^\s*(https?:\/\/|[-*]\s|\d+\.\s|\|)/.test(l))
      v.push({ rule: "body-wrap", severity: "warning", message: `Body line ${i + 1} is ${displayWidth(l)} columns; wrap near 72.` })
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
    "Validate a candidate commit message before committing. Checks subject length in terminal columns, wide characters counting two (<=50 target, <=72 hard), conventional `type(scope): summary` structure, the blank line before the body, body wrap (~72), emoji, attribution/generated trailers, and file-path/line-number noise. If the repo has a local commitlint binary it is also run and its violations merged (authoritative); `commitlint` reports ran / not-installed / not-configured, and a commit-msg hook that runs a missing commitlint is an error. Lint the exact text that will be committed — rewrapping it afterwards defeats the check. Read-only. Returns { pass, commitlint, hook, errors, warnings }.",
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
