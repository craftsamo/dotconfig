# GitHub

Load the skill for the work before any GitHub call; each owns its
mechanics, and this file holds only what is particular to Chat:

| Work | Skill |
| --- | --- |
| Reading or changing issues | `skill_view(name="github-tools:issues")` |
| Reading or changing boards and their items, a board's setup | `skill_view(name="github-tools:projects")` |
| Keeping a job's record on issues and boards: tiers, which board, bodies, drafts | also `skill_view(name="github-tracking")` |
| A pull request or a stack: where it stands, opening, editing, attachments, merging | `skill_view(name="github-tools:pull-requests")` |
| A repository's settings, labels, milestones, branch protection | `skill_view(name="github-tools:repos")` |
| Releases | `skill_view(name="github-tools:releases")` |
| Actions runs: why one failed, re-running, starting a workflow | `skill_view(name="github-tools:actions")` |
| The user's conventions: pull requests and attachments, merging (method, message, stacks), repositories and releases, commit and PR text, red CI | also `skill_view(name="github")`, then the reference its table names |

Read with the `github_*_read` tools (`github_issue_read`, `github_pr_read`,
`github_project_read`, `github_repo_read`, `github_run_read`, …); change with
the matching `github_*` write tool. In the terminal only gh's reads run.

## What stays in Chat

The user's own direct requests about GitHub itself: "この PR どうなってる？",
"CI が落ちた理由を見て", "マージして", "ラベルを作って", "リリースを下書きして",
"main を保護して", "CI をもう一度回して", "このワークフローを手動で動かして". Do
them inline with the tools, each change on its card: the card is the user's
go, so do not ask first and then raise the card.

- **Re-running and starting workflows.** `github_run_rerun` re-runs a finished
  run (its failed jobs by default); propose one yourself only for a failure that
  looks transient, and say so. `github_workflow_run` starts a workflow only when
  the user names it: read what it does (its file) first, and when it deploys
  or publishes, say so plainly before the card, since it happens for real.
  Publishing a release is the same kind of decision.

- **Code is not Chat's.** Investigating why code fails, fixing a failing
  test, or implementing anything is engineering: promote it through Plan →
  Execute, where an OpenCode build run changes the code and opens its PR. A
  red run you only read and explain stays here.
- **Opening a pull request yourself** (`github_pr_create`) only for a branch that is
  already pushed and that the user names; a branch a build run made gets its
  PR from that run.
- **Tracking a job's work** on a board belongs to the engineering pipeline
  (its GitHub operations); a single draft or issue the user asks for stays
  here. A bug report to someone else's repository is one issue there, in its
  template, on its card, with the wording agreed first: no draft on the
  user's board, no parent, and no fix unless the user asks for one (then it
  is engineering, on the user's fork).
- **Merging** only the pull request the user named, after reading where it
  stands and saying it in the reply; the card is their go.

## Never yours

Say what the user should do, and leave it to them: approving or requesting
changes on a pull request (their judgement, under their name); deleting,
renaming, forking or transferring a repository; secrets, variables, deploy
keys; uploading release assets or deleting releases; cancelling runs;
enabling or disabling workflows; a merge that bypasses the rules.

## In conversation

- An admin change (a new repository, its settings or visibility, archiving,
  a merge, publishing a release, re-running or starting a workflow, branch
  protection) always asks on its own card; never offer the user a `session`
  answer for one.
- An upload into a pull request is permanent: name each file and who can
  open it, and attach only the ones the user picks.
- Do not schedule a job that is meant to change GitHub (nobody could answer
  its card); schedule a read or a reminder for the user instead.
