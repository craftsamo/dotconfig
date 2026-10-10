import { tool } from "../define"
import { exec, withTempFile } from "../exec"
import { fileExists } from "./shared"

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
      const res = await withTempFile("opencode-commitmsg", ".txt", args.message, (file) =>
        exec([`${cwd}/node_modules/.bin/commitlint`, "--edit", file, "--no-color"], { cwd }),
      )
      if (!res.ok) {
        const out = `${res.stdout}\n${res.stderr}`.trim()
        violations.push({ rule: "commitlint", severity: "error", message: out || "commitlint reported problems." })
      }
    }
    const errors = violations.filter((x) => x.severity === "error")
    const warnings = violations.filter((x) => x.severity === "warning")
    return JSON.stringify({ pass: errors.length === 0, commitlintRan, errors, warnings }, null, 2)
  },
})
