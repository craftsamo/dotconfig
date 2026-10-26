---
name: answer
description: "Use when an OpenCode run is waiting on you: its pending permissions and questions, what a build sends back (a publish, metadata, a push, a package runner, an Issue write), and replying once, in scope, or rejecting with a reason. Runs are opencode:drive."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [opencode, opencode_request, permissions, engineering, coding-agent]
---

# Answering an OpenCode run

A run pauses when it needs a decision from you. This skill owns reading what
it asks and replying; the run itself is `opencode:drive`, the message you
send it is `opencode:brief`. The engineering entries say what the user has
approved; nothing here widens that.

## Requests

A run pauses as `waiting` when it needs a decision: a permission (a path
outside the worktree, a push, a shell history rewrite, a branch move, a package
runner, an Issue write without the grant, a subagent command outside its
allowlist) or a question the agent would put to a person.
`opencode_request(action="list", session_id)` shows each pending item with its
`kind`, `id`, whether a subagent asked, and its action and resources or its
fields and options. A shell request names every simple command of a chain as
its own resource, and the one that needs you is often the last (`kill`,
`rm`, `git push`): judge them all before answering. A notification shortens
them; where it says `complete: false`, read the request with `list` first.

`opencode_request(action="reply", session_id, replies=[{request_id, …}, …])`
answers every pending request in one call (`request_id` alone answers one); all
replies are checked before any is sent. The result is the run's next state when
it comes within a few seconds (often the next request), so answer that in the
same way rather than waiting for a notification.

- A permission inside the user's approved scope → `decision: "once"`. Outside
  it or unclear → `decision: "reject"` with a short `reason` OpenCode can act
  on, then take the decision to the user if the work needs it.
- A question: a technical choice goes back as the run's own call
  (`answer` that it decides and states the choice in its report). Relay to the
  user, first, only a decision about what people can do or see, what is stored,
  cost or anything irreversible, and pass their answer back as a plain
  sentence that keeps their wording where it carries the intent.
  `decision: "reject"` declines it.

There is no broader approval: `always` would save a project-wide rule the
person's own sessions inherit. If the same in-scope request keeps coming, say
so once with `opencode_instructions` (for example: use the read and grep tools
instead of `cat`/`grep`, run the project script instead of `node -e`). A
request stays pending until answered, and the run waits meanwhile.

## What a build sends back

A build may edit files in its worktree and run routine commands; its tools
refuse the default branch, shared commits and protected branches, and what
follows comes to you as a request.

- **Publishing a PR**, plain or stacked, arrives as a `git_publish` request
  (push, submit or link). The request carries only a preview token: approve
  it against the `git_publish_preview` the build reported (the base, each
  layer, its commits, its PR, whether it is force-pushed, and under `text`
  the PR titles and bodies a submit will set, with what they trip), and ask
  for that preview first if it did not; the metadata it judged (labels,
  assignees, review requests, a milestone) is set with that approval. The
  titles and bodies are pinned in the token, so what you read is what is
  published. The preview only flags what trips a pattern; you read the whole
  text as someone who has only the repository, and reject the request, with
  the words to change, when it names a Phase, a decision number, the tools
  or agents that did the work, a local path or this machine's or account's
  state.
- **Metadata on an existing PR** is applied without asking when nothing
  reacts to it; the rest arrives as a `gh_pr_meta_apply` request, to approve
  against the reasons the build reported (a workflow, a merge bot, a webhook,
  or the people it notifies).
- **Pushes** (a rebased branch's
  `git push --force-with-lease origin HEAD:refs/heads/<task branch>`,
  `git_publish` and `gh stack push` included), shell history rewrites, branch
  moves, package downloaders (`npm exec`, `pnpm dlx`), anything naming
  `deploy`, `publish`, `secret`, `--remote` or `--prod`, per-command git
  configuration (`git -c`) and Issue writes without `issue_approval` come
  back to you as requests, also behind a prefix or a wrapper such as `env` or
  `sh -c`.
- **Denied outright**, however spelled, and never yours to approve: every
  other force push, protected-branch pushes, merges, `gh api`, Project
  writes, git config and remote rewrites, `gh` aliases and extensions, edits
  under `.git/` or the global git and gh config, and secret reads. A
  read-only run is denied the requests above as well.
- A build refuses a worktree another OpenCode session is running in (a
  person's included); read-only runs may run alongside.
