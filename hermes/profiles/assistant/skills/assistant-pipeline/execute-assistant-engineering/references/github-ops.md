# Engineering - GitHub boundaries

| Operation | Owner and permission |
| --- | --- |
| Code, commits, task-branch push, PR creation | An OpenCode build run you drive, within explicit implementation approval |
| A PR's text, labels, reviewers, attachments (screenshots), ready / draft, closing | You, through `github_change` (`skill_view(name="github-access:github-pr")`), when the user asks; each attached file with their yes |
| Issues and boards | You, through `github_change` (github-access), only for a job the user chose to track (below); never an OpenCode run |
| Repo creation and settings, labels, milestones, clone, workspace registry | Assistant, when separately requested/approved; GitHub changes through `github_change` |
| Merge | Assistant, only when the user asks, after readiness checks: `pr_merge`, whose card is their go |
| Deploy/publish | Outside the implementation grant; separately scoped work |

Do not create Issues or change boards for a job the user did not choose to
track, and never as an automatic close-out. Reading an Issue is not
authorization to change it. A PR's closing reference must reflect the actual
complete scope; do not close a multi-PR Issue on its first layer. A build
delivers a PR, not a merge. Review corrections are further turns of the same
build session when released.

## Tracking a job on GitHub

Read `skill_view(name="github-access:github")` and
`skill_view(name="github-access:github-tracking")` before the first GitHub
change of a job.

**The choice.** Propose tracking once, and only with the roadmap of a job of
several Phases or when others will pick the work up; the user may ask for it
on any job. One sentence names the board (`github_board` `resolve` on the
repository tells which) and the repository; when no board resolves, the same
sentence proposes making one (its owner and title), as the tracking skill's
"Setting up a board" says. The user's answer goes in the decision log. A yes
covers this job only. The job's operational work around its repository
(hosting, DNS, a domain, a contract, a hand-over item) is part of it: drafts
on the same board.

**The record.** For a tracked job GitHub holds the plan; the job directory
keeps what is private: the decision log with the user's own words, mocks,
reports and each run's `progress.md`. Issue text is written for the
repository's readers: facts linked to their sources as the read skill's
"Background" says, never the user's quotes, and on a `shared` or `other`
tier the wording agreed first.

**Starting.** In this order, once tracking is agreed:

1. Gather the background: read what the job touches that you can reach
   (the conversation, the synced messages and sheets, the repository
   inventory, OpenCode's plan) and note each fact's source.
2. When the agreed board does not exist yet, make it first, in a call of its
   own: `board_create` with its owner, title and `link_repo` the repository.
3. Write the parent issue and every sub-issue (and the operational drafts)
   into one Markdown file in the job directory. On a `shared` or `other`
   tier ask with `clarify`, the file in its `context`; on `own` the card is
   enough.
4. One `github_change` list: the parent first, then a sub-issue per Phase
   with `parent: "$1"` and `blocked_by` the one before (`"$2"`, `"$3"`, …:
   an issue an earlier change of the same list creates), each with
   `board_fields`; the drafts with it. One card shows the whole plan.
5. Propose the **mandate**: `routine`, boards = the job's board, repos = its
   repository, parent = the parent issue (so it covers that issue tree and
   nothing else in the repository), until the job is expected to be
   delivered (at most 30 days). Creating issues, commenting and closing still
   ask, unless the user's own private board and repository are all the job
   touches and the user wants those covered too.
6. Record the parent issue, the board and the mandate id in the decision
   log: a new session finds the job's GitHub record from there.

| Plan | On GitHub |
| --- | --- |
| A single-PR job | one issue (the mandate's parent is that issue) |
| A roadmap | a parent issue (the outcome, the acceptance) with one sub-issue per Phase (what people can do once it lands, how to try it), each blocked by the one before; a milestone when the user names a date or release |
| A Phase's approval | its sub-issue's body becomes Fixed: the Phase's steps as a checklist; Status In Progress |
| A finished step (a progress notification) | with a mandate in force, its checklist line ticked at once; without one, nothing until the next row |
| The Phase's PR is up | without a mandate, the steps ticked so far in one list, with the PR's link |
| An accepted, merged Phase | its sub-issue closed (by the PR's closing reference, else `issue_close` `completed`); Status Done |
| All Phases accepted | the parent's acceptance checked against the evidence, then closed; the mandate revoked |

**When the plan moves.**

| Event | On GitHub |
| --- | --- |
| The roadmap changes (a Phase split, merged, added or dropped) | after the user approves the new roadmap, "Replacing issues" in the tracking skill: successors first, then the replaced ones closed with their numbers |
| The job is dropped | each open issue closed `not planned` with one comment saying why, Status Cancelled, drafts archived, the mandate revoked |
| The job pauses on someone outside | a dated note on the parent, Status Waiting; revoke the mandate when the pause outlasts it |
| A new session resumes the job | the parent issue from the decision log, read fresh with `github_issue` `view` before any report |
| The user supplies an existing issue to track | it is the parent; on `shared` or `other` its body stays as it is, and the plan goes into sub-issues and comments |

**OpenCode reads; you write.** A brief names the issue a run works on
(`owner/repo#N`) so the run reads it with its own tools, and the build is told
which issue its completing PR closes. Never pass `issue_approval`: a build
does not write Issues or boards. What a run reports is mirrored to GitHub by
you, after you have read it.

## Repository lifecycle

Use the decisions from [bootstrap](../../plan-assistant-engineering/references/bootstrap.md).
Before any registry call, read `skill_view(name="workspace-registry:workspace-registry")`.
Create a missing Group with the `workspace_registry` `group_create` action only when approved;
pass an organization only when it names a real approved registry record.
Establish GitHub repositories with approved owner, visibility and history
through `github_change` `repo_create` (`skill_view(name="github-access:github-repo")`,
always on its own card): `template` for a starter, or an empty repository for
an approved scratch or history-preserving path (the history is pushed into
it). Clone through `ghq`, not an unregistered local `git init`; preserve
`upstream` when lineage is requested.
Register/link with the `workspace_registry` actions `repo_set` then `link_repo` using
the approved Group.

OpenCode receives the established clone and proposes/implements its skeleton,
project instructions and code. Do not invent an initial default-branch push to
make PR creation possible in an empty repository; resolve that bootstrap boundary
explicitly. Verify owner/visibility, remotes, workspace link and registry entry.
No credentials or private records belong in the repository or public descriptions.

## Merge

Use [acceptance](../../qa-assistant-engineering/references/acceptance.md) before the
`pr_merge` card. After the merge, verify actual state with `github_pr` `view`. If further
stacked work was requested, tell the build session what changed so it can
propose the appropriate update; do not grant history rewriting implicitly.
Close Issues or change a board only for a tracked job, as above.
