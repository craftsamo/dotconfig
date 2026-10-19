/**
 * The reader of a PR title, body, commit subject or branch name has the
 * repository and GitHub and nothing else: not the plan the work came from,
 * not the tools that built it, not the machine it ran on. Text written at
 * the end of a long run tends to carry that working context along. These
 * checks catch its most frequent shapes so the preview can show them before
 * anything is published; they are tripwires, not a definition of the rule
 * (git-pullrequest's <Audience> is), and a clean pass proves nothing.
 */

export type AudienceFinding = { rule: string; match: string; hint: string }

type Rule = { rule: string; re: RegExp; hint: string }

const RULES: Rule[] = [
  {
    rule: "plan-label",
    re: /\b[Pp]hase[-_ ]?\d+(?:\.\d+)?\b|\b[Ss]tep\s*\d+\.\d+\b|フェーズ\s*\d+|段\s*[A-Z]\b|\d+\s*層目|\b[Ll]ayer\s+\d+\s+of\s+\d+\b/g,
    hint: "A plan label names where the work was planned, not what it does; a layer's place in a stack is its base and the linked PRs.",
  },
  {
    rule: "working-record",
    re: /決定\s*#\s*\d+|\bdecisions?\s*#\s*\d+|\b(?:decisions|progress)\.md\b/gi,
    hint: "A decision-log or task-record number means nothing to the repository's reader: restate the decision, or link the Issue that holds it.",
  },
  {
    rule: "tooling",
    re: /\bgit_[a-z_]+\b|\bgh_pr_[a-z_]+\b|\bOpenCode\b|\bHermes\b/g,
    hint: "Say what was checked, not what checked it: the agents, tools and harness that built the work are not part of the repository (unless the repository is about them).",
  },
  {
    rule: "build-machine",
    re: /\/Users\/[^\s)）」]+|\/home\/[^\s)）」]+|(?:^|[\s(（「`])~\/[^\s)）」`]*/g,
    hint: "A local path or the machine's state belongs to this run, not to the repository.",
  },
  {
    rule: "organisation",
    re: /\bbilling\s+(?:is|was|has been)?\s*(?:suspended|disabled|paused|stopped|off)\b|\bout of credits\b|支払い(?:の)?停止|課金(?:の)?停止/gi,
    hint: "Billing, plan and account state live outside the repository; a check that did not run is reported without that reason.",
  },
]

const MATCH_MAX = 60

/** Every tripwire a text trips, each once, with the first text it matched. */
export function audienceFindings(text: string): AudienceFinding[] {
  const out: AudienceFinding[] = []
  for (const { rule, re, hint } of RULES) {
    re.lastIndex = 0
    const m = re.exec(text)
    if (!m) continue
    const match = m[0].trim().slice(0, MATCH_MAX)
    out.push({ rule, match, hint })
  }
  return out
}
