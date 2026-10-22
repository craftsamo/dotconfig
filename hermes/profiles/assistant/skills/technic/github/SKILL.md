---
name: github
description: "Use for this user's GitHub conventions on top of the github-access tools: merging a pull request they asked to merge (method, message, stacks, BEHIND), keeping repo-external words out of commits and PR text, reading why CI is red, and briefing a history repair."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [github, merge, pull-request, stack, ci, conventions]
    category: technic
---

# GitHub: the user's conventions

The tools' mechanics live in the `github-access` skills
(`skill_view(name="github-access:github-pr")` for pull requests and merges,
`skill_view(name="github-access:github-repo")` for repositories and Actions).
This skill adds what this user expects on top of them. Read the reference for
the work in front of you; each stands alone.

## Contract

- **Through the tools.** Read with `github_pr`, `github_repo`, `github_issue`
  and `github_board`; change with `github_change`. A terminal write through
  gh (its merge, its API, the stack extension) is blocked.
- **Never bypass.** No tool bypasses rules or required checks. A bypass is the
  user's own act in GitHub's page; say what it would skip.
- **History surgery is not yours.** Rewriting commit messages on a branch or
  on main, re-seating a chain, and any force-push need the user's explicit
  go and run in an OpenCode build you brief.

## References

| Work | Read |
| --- | --- |
| Merging a pull request the user asked to merge: method and message, stacks and chains, BEHIND, a wrong squash message, tidying branches after | [merge](references/merge.md) |
| A commit message, PR title or body that lands where outsiders read it: what must not be in it, and rewriting it safely | [text-hygiene](references/text-hygiene.md) |
| Waiting for CI, and telling a red run caused by the code from one caused by the infrastructure | [ci](references/ci.md) |
| A repair that rewrites history or force-pushes, as steps for a build run | [history-repair](references/history-repair.md) |

A new kind of GitHub convention gets a reference of its own and a row here.
