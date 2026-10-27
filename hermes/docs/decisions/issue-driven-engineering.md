# Every repository job is an issue before it is built

Status: in force
Owner doc: docs/opencode.md "Who owns what"; the Assistant's engineering
entries (`profiles/assistant/skills/pipeline/engineering/`)

## Decision

A job that changes a repository the user owns or belongs to is recorded on
GitHub as it is planned, not on request: the roadmap's approval files a
parent issue with one sub-issue per execution unit (a single-unit job files
one issue), each unit's approval makes its issue Fixed and In Progress before
its build, and the Assistant mirrors the run to it. The user excludes a job
in their own words, and that exclusion is the only thing that keeps such a
job off GitHub.

Someone else's repository (an open-source project, a client's) is outside
the default: its tracker takes only what its own conventions ask for, on a
card each time, and the user's record of the job, if they want one, lives on
their fork or their own board. The plan of a job is never written where
people the user cannot name read it as the project's business.

The unit of planning and of GitHub is the **execution unit**: one goal told by
what people can do once it lands, implemented by one PR or one native stack
that lands in one merge. Phase N (one PR layer) and Phase N.m (a checkpoint
commit) live inside a unit; a layer is a checklist line of the unit's Fixed
body and never an issue of its own.

Every issue body passes through one Writer round before the user or GitHub
sees it: proofreading, and the gaps a reader would find in it as a spec.

Issues and boards are written by the Assistant through `github_change`; an
OpenCode run reads the issue bound to its session (the `issue` argument of
`opencode_run_*`), and a build is refused until the session has one or the
caller passes the user's words excluding the job. The one thing a build
writes itself is its own issue's execution state (a ticked layer, its board
Status to In Progress), inside the job's mandate and checked against it at
the write ([mandates](./github-mandates.md)); the plan, the other issues,
Done, closing and comments stay the Assistant's.

## Why

- Tracking proposed "once, with a roadmap" is skipped under pressure, and a
  job that reaches its first merge with no issue has no record a second
  session or another person can pick up. Information only the Assistant
  holds (a promise in a message, a date, a measurement) reaches OpenCode
  only through the issue.
- One issue per PR layer multiplies issues past what the plan has: the
  GitHub mechanics skill and OpenCode's own planning model already said "a
  sub-issue is a unit, a layer is a PR", and the engineering entries were the
  one text that disagreed.
- A rule the profile must keep (Writer reads the body, facts go into the
  issue first) belongs in its skill; the Assistant's memory is bounded and
  not reloaded on a compaction.
- The default "every job is an issue" read literally would file the user's
  internal plan in an open-source project's tracker, and the board fallback
  (`Roadmap` of the user) would carry a one-off upstream fix. A public
  repository, the user's own included, is read by anyone: its issues still
  hold the plan, but as facts about the code, with what the plan rests on
  (the user's business, customers, accounts) kept in the decision log
  (`github-ops.md` "The record").

## Do not

- Decide tracking by size, duration or how small a fix sounds: a small fix is
  one issue with one layer.
- File an issue per PR layer, or put a status line, a Phase number or a
  parent reference into a body: relations and Status carry those.
- Let a brief carry a fact the issue lacks; put it in the issue first.
- File a parent, a unit or a progress comment in a repository the user does
  not own or belong to, or name such a repository in a mandate's scope.
