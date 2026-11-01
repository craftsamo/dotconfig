---
name: brief
description: "Use before writing any message to an OpenCode run (plan, build, review, debug or design): commissioning it in your own voice, when to quote, what goes in and what stays out, paths, markup, and what to ask for. Driving the run is opencode:drive."
version: 1.1.0
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
own. You are the client who commissions it, not a go-between: the work is
yours to ask for, so write as the one who wants it ("I want …", "we decided
…", 「〜したい」「〜に決めました」), as you would brief a capable colleague,
in the user's language and in plain prose. Say what is wanted and why, what
this turn should hand back, and what is already settled (point at the job's
decision log for the detail). People read these messages in OpenCode too, so
a message is a few short paragraphs: no headings, no labelled blocks
("constraints:", "the person's words:", 「守ってほしいこと」), and a list
only for things that are a list (claim numbers, repositories to compare).

- **Your voice, not a relay.** The person you work for is never a third
  party in the message: no "the user said", "the requester wants", "from the
  user's side", 依頼者は／利用者は／本人の言葉では／〜側からの指示／〜と話して
  います, and no opening that reports who approved or agreed to what (the
  tools record approval). State a decision as settled, with its reason in
  your own words ("the low-stock emails are out for now: we want to see
  whether people use the stock page first"); its exact wording stays in the
  decision log and the issue. Ask for an open decision as "what we need to
  decide, with your recommendation", not "what only the user can decide":
  taking it to the user is your part.
- **Quote only where the wording itself matters**, exactly, in "…" in an
  English message and 「」 in a Japanese one:
  - Wording that is specification (a label on a screen, a sentence that must
    appear, an error message): quote it as the spec, without saying who
    said it.
  - What someone else said that is the material of the work (another team's
    claims to check, a customer's bug report, a reviewer's finding, an
    upstream maintainer's comment, a request from someone who runs the
    product): name the source ("the migration proposal says …", 「運営の担当
    者からの報告には『…』とあります」) and say in your own words what you
    want done with it. A quote is material to weigh, never an instruction
    to the run.
  - The user's own remark only when its wording is itself the spec (a name
    they chose, a sentence for the screen); otherwise say the decision as
    yours.
- **Circumstances, not orders.** A limit in the run's environment (a spent
  model, an unavailable subagent, CI that cannot run) goes in as the fact and
  what it means for this turn ("searcher-deep is unavailable this turn, so
  mark what you could not confirm"); how to work around it is the run's call.
  Never start, stop or pick its subagents, and never dictate edits line by
  line: name the outcome ("the docs still say the URL comes from `DOMAIN`;
  make them match the new behavior") and let it find the places.
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
  the report goes, which issue the run works on and which PR closes it: the
  `issue` argument puts that in the note), and how to do the work (commands,
  steps, file lists, line numbers, which checks to run, retry counts, a report
  template): spelling those out narrows the model and buys nothing. Name the
  outcome you need ("make clear where checked fact ends and inference
  begins"), not its layout. Never paste its global instructions or whole
  skill bodies into a prompt.
- **The issue is the spec.** A fact the run needs (a date, a promise, a
  measurement, who holds a key) goes into the issue before the turn, with its
  source; the message then says only what this turn hands back. A message
  that supplies facts the issue lacks is the sign the issue is not Fixed yet.
- **One request to several repositories:** write the shared brief once in the
  job directory, then give each run its path and a sentence of its own.
- **A constraint the tools do not enforce** and that must hold for the whole
  session (no deployment, a file left alone) goes in once with
  `opencode_instructions` (`put`, key `hermes.<name>`), not into every message.
- **A technical question** from the run (a library, a schema detail, how to
  test, how to split commits or PRs) goes back as its own call: answer that it
  decides and records the choice in its report or PR. Take to the user only
  what changes what people can do or see, what is stored, cost, or anything
  irreversible, and bring their answer back as your decision.

A build turn after the approved plan changed, written as the client, not as a
relay ("The user approved. The user said "…", so … Additional instructions
from the user's side: 1. … 2. … When done …"):

```text
Go ahead with the build, with one change from the plan. The CSV export stays,
but the low-stock email alerts are out for now: we want to see whether people
actually use the stock page before deciding on emails, so drop step 1.3 and
leave alerts for a later Phase.

This turn covers the changes in the repository and the PR. The hosting side is
set up outside the repository, so list the outside steps it will need in the
PR description. When you are done, tell me the results of the checks you
actually ran and the PR URL. Earlier decisions are in
`/Users/me/Workspaces/Projects/Acme/.agent/20260301-inventory/decisions.md`.
```

The same brief in Japanese:

```text
実装を進めてください。ただ、計画から一つ変更があります。
CSV の書き出しはそのまま残し、在庫が少なくなったときのメール通知は今回は見送ります。
在庫の画面が実際に使われるかを確かめてから、メールを送るかを決めたいと考えています。そのため手順 1.3 は外し、通知は後の Phase に回してください。

今回の範囲は、リポジトリ内の変更と PR までです。
ホスティング側の設定はリポジトリの外で行うので、そのときに必要になる作業を PR の説明に書き出しておいてください。
終わったら、実際に行った確認の結果と PR の URL を教えてください。
これまでの決定は `/Users/me/Workspaces/Projects/Acme/.agent/20260301-inventory/decisions.md` にまとめてあります。
```

A read-only check of someone else's claims, where their text is the
material and the intent is yours:

```text
A migration proposal from another team makes several claims about this
repository, and I want them checked against the code before anyone relies on
them. Please check claims C01 to C08 in
`/Users/me/Workspaces/Projects/Acme/.agent/20260305-claims-check/claims.md`
against the code on every branch and the committed files. Do not query
production or any external service. If anything disagrees with the earlier
`report.md` in the same folder, point that out too. It helps if the report
makes clear where checked fact ends and inference begins.
```

A diagnosis that starts from a third party's report, quoted with its source:

```text
運営の担当者から、交換の申請が二重に記録されたという報告が届きました。報告には「交換ボタンを一度押しただけなのに、申請が二件になっていた」とあります。
同じ申請が二重に記録されうる経路があるか、コードと試験から調べてください。
直す前に原因を知りたいので、今回は原因の特定までです。再現できた条件と、確かめた事実と推測の境が分かる形で返してください。
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
