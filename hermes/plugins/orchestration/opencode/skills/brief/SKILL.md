---
name: brief
description: "Use before writing any message to an OpenCode run (a plan, build, review, debug or design turn): how to commission it as a client in plain prose, what goes in and what stays out, paths, markup, and what to ask for. Driving the run is opencode:drive."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [opencode, opencode_run, engineering, coding-agent, brief]
---

# Briefing an OpenCode run

The engineering entries (`plan-engineering`, `execute-engineering`,
`qa-engineering`) own what to ask for, when the user's approval is needed and
how a result is accepted. This skill owns the message you send to a run;
starting, continuing and reading runs is `opencode:drive`, and what a run
pauses on is `opencode:answer`. Never call raw `opencode` commands or the
OpenCode API from the terminal, and never substitute another coding agent to
get around these tools.

OpenCode is the developer: it investigates, plans, implements, tests, reviews
and commits with its own agents and skills, and the technical calls are its
own. You are the client who commissions it, not a go-between: brief it as you
would a capable colleague, in the user's language and in plain prose. Say what
is wanted and why, what this turn should hand back, and what is already
settled (point at the job's decision log for the detail). People read these
messages in OpenCode too, so a message is a few short paragraphs: no headings,
no labelled blocks ("constraints:", "the person's words:"), and a list only
for things that are a list (claim numbers, repositories to compare).

- **The user's words** go inside your sentences where their wording carries
  the intent, in "…" in an English message (the user said "a weekly summary
  is enough", so …) and 「」 in a Japanese one
  (依頼者は「週に一度まとめて見られれば十分」と話していて、…), never as a
  block of quotes standing in for the requirement you draw from them. Quote
  exactly only what
  is itself specification (a label on a screen, a sentence that must appear);
  the decision log keeps the rest verbatim. Do not open by reporting who
  approved what: the tools record approval.
- **Markup.** OpenCode shows the message as typed, so Markdown appears as raw
  symbols. Use backticks, and nothing else, for paths, commands, identifiers,
  settings keys and branch names: they mark exactly what is literal. A fenced
  block (three backticks) only for several lines that must pass unchanged (an
  error output, wording that appears on a screen); anything longer than a
  screenful goes in a file you point at. No headings, bold, tables, link
  syntax, `>` quotes or other fences such as `'''`, and no fenced steps or
  command lists. `- ` or `1.` at a line start only for things that are a list.
- **Paths.** A file in the session's repository is relative to its root
  (`apps/web/src/app/page.tsx`): the session moves from the default checkout to
  its own worktree after a plan, and forks share that layout, so an absolute
  path inside the repository goes stale. Anything outside it (the decision log,
  a shared brief, another repository) is absolute. `@file`, `@agent` and
  `/command` are the TUI's own input: from Hermes they arrive as plain text.
- **Leave out** what the session already holds (its earlier turns, the plan it
  wrote), what its tools, ruleset and operating note already carry (prohibited
  commands, commit rules, push and merge limits, how to write commands, where
  the report goes), and how to do the work (commands, steps, file lists, retry
  counts, a report template): spelling those out narrows the model and buys
  nothing. Name the outcome you need ("make clear where checked fact ends and
  inference begins"), not its layout. Never paste its global instructions or
  whole skill bodies into a prompt.
- **One request to several repositories:** write the shared brief once in the
  job directory, then give each run its path and a sentence of its own.
- **A constraint the tools do not enforce** and that must hold for the whole
  session (no deployment, a file left alone) goes in once with
  `opencode_instructions` (`put`, key `hermes.<name>`), not into every message.
- **A technical question** from the run (a library, a schema detail, how to
  test, how to split commits or PRs) goes back as its own call: answer that it
  decides and records the choice in its report or PR. Relay only what changes
  what people can do or see, what is stored, cost, or anything irreversible.

A build turn after the user changed the approved plan, not as a relay
("Approved by the user. The user's words: - "…" - "…" So … Constraints: - …
When done …") but as a brief:

```text
Go ahead with the build, with one change from the plan. The CSV export stays,
but the low-stock email alerts are out for now: the user said "let's see whether
people actually look at the stock page before we decide on emails", so drop
step 1.3 and leave alerts for a later Phase.

This turn covers the changes in the repository and the PR. The user sets up the
hosting side themselves, so list the outside steps they will need in the PR
description. When you are done, tell me the results of the checks you actually
ran and the PR URL. Earlier decisions are in
`/Users/me/Workspaces/Projects/Acme/.agent/20260301-inventory/decisions.md`.
```

The same brief for a user who writes in Japanese:

```text
実装を進めてください。ただ、計画から一つ変更があります。
CSV の書き出しはそのまま残し、在庫が少なくなったときのメール通知は今回は見送ります。
依頼者は「在庫の画面をみんなが本当に見るか確かめてから、メールを送るか決めたい」と話していたので、
手順 1.3 は外し、通知は後の Phase に回してください。

今回の範囲は、リポジトリ内の変更と PR までです。
ホスティング側の設定は依頼者が自分で行うので、そのときに必要になる作業を PR の説明に書き出しておいてください。
終わったら、実際に行った確認の結果と PR の URL を教えてください。
これまでの決定は `/Users/me/Workspaces/Projects/Acme/.agent/20260301-inventory/decisions.md` にまとめてあります。
```

A read-only check of someone's claims, with the intent in your own words
where no remark of the user's carries it better:

```text
A migration proposal from another team makes several claims about this
repository, and the user wants them checked against the code before anyone
relies on them. Please check claims C01 to C08 in
`/Users/me/Workspaces/Projects/Acme/.agent/20260305-claims-check/claims.md`
against the code on every branch and the committed files. Do not query
production or any external service. If anything disagrees with the earlier
`report.md` in the same folder, point that out too. It helps if the report
makes clear where checked fact ends and inference begins.
```

## What to ask for

- Ask for outcomes, not methods: the checks' actual results, and a closer
  review in a plain sentence that names the area and why (no keyword triggers
  one) only where the person's stake is high (who can see what, stored data,
  money). Checkpoint commits, `web_ui_check` for a page
  change and how to test are the run's own practice.
- Permission rules match each command as written, and every unmatched one
  pauses the run for you. So never tell a run to write commands with a
  `NAME=value` prefix, a status wrapper (`…; exit "$status"`) or a launcher
  (`npx`, `mise exec`): name the target as the program's own option instead
  (`gh -R owner/repo …`, a script's flag). The operating note tells the run the
  same.
