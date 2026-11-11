---
name: github
description: "Use for this user's GitHub conventions on top of the github_* tools: opening, attaching to, readying and merging a pull request (method, message, stacks, BEHIND), repository, label, milestone, release and Actions etiquette, keeping repo-external words out of commits and PR text, reading why CI is red, and briefing a history repair."
version: 1.1.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [github, merge, pull-request, stack, ci, conventions, repository, release]
    category: technic
---

# GitHub: the user's conventions

The tools' mechanics live in the `github-tools` skills
(`skill_view(name="github-tools:pull-requests")` for pull requests, merges and
stacks, `skill_view(name="github-tools:repos")` for repositories, labels,
milestones and rulesets, `skill_view(name="github-tools:releases")` and
`skill_view(name="github-tools:actions")`). Keeping a job's record on issues
and boards is `skill_view(name="github-tracking")`. This skill adds what this
user expects on top of them. Read the reference for the work in front of you;
each stands alone.

## Contract

- **Through the tools.** Read with `github_pr_read` (`view`, `checks`,
  `diff`), `github_issue_read`, `github_project_read`, `github_repo_read` and
  `github_run_read`; change with the matching `github_*` write tool. Each
  write asks on its own card, one call one card. A `session` answer covers
  later calls of that tool on that repository or board only: offer it for the
  routine updates of a job, never ask the user to pick `always`, and never
  treat an answer on one repository or board as covering another. A terminal
  write through gh (its merge, its API, the stack extension) is blocked.
- **Never bypass.** No tool bypasses rules or required checks. A bypass is the
  user's own act in GitHub's page; say what it would skip.
- **History surgery is not yours.** Rewriting commit messages on a branch or
  on main, re-seating a chain, and any force-push need the user's explicit
  go and run in an OpenCode build you brief.

## References

| Work | Read |
| --- | --- |
| Opening or editing a pull request, attaching images or video, ready / draft, closing references, reviews, who may merge | [pull-requests](references/pull-requests.md) |
| A repository's settings, visibility, labels, milestones, releases, Actions runs, branch protection | [repository](references/repository.md) |
| Merging a pull request the user asked to merge: method and message, stacks and chains, BEHIND, a wrong squash message, tidying branches after | [merge](references/merge.md) |
| A commit message, PR title or body that lands where outsiders read it: what must not be in it, and rewriting it safely | [text-hygiene](references/text-hygiene.md) |
| Waiting for CI, and telling a red run caused by the code from one caused by the infrastructure | [ci](references/ci.md) |
| A repair that rewrites history or force-pushes, commissioned from a build run as outcomes | [history-repair](references/history-repair.md) |

A new kind of GitHub convention gets a reference of its own and a row here.
