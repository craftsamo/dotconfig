# Engineering - GitHub boundaries

| Operation | Owner and permission |
| --- | --- |
| Code, commits, task-branch push, PR creation | An OpenCode build run you drive, within explicit implementation approval |
| A PR for a branch already pushed that the user names | You, through `github_change` `pr_create` (`skill_view(name="github-access:manage-pr")`), when the user asks; never for a branch a build run made, whose PR comes from that run |
| A PR's text, labels, reviewers, attachments (screenshots), ready / draft, closing | You, through `github_change` (`skill_view(name="github-access:manage-pr")`), when the user asks; each attached file with their yes |
| Issues and boards | You, through `github_change` (github-access), as the record of every repository job (below) unless the user excluded it; never an OpenCode run |
| Repo creation and settings, labels, milestones, branch protection, clone, workspace registry | Assistant, when separately requested/approved; GitHub changes through `github_change` (`skill_view(name="github-access:manage-repo")`) |
| CI: why a run failed, re-running it | You read it (`github_repo` `run`); a real failure goes back to the build session. A re-run (`run_rerun`) when the user asks, or proposed by you only for a failure that looks transient; its card is their go |
| Merge | Assistant, only when the user asks, after readiness checks: `pr_merge`, whose card is their go; method and message as `skill_view(name="github", file_path="references/merge.md")` says |
| Deploy/publish (publishing a release, starting a workflow that deploys) | Outside the implementation grant; separately scoped work. When the user asks for it: `release_create` / `release_publish` or `workflow_dispatch` (`github-access:manage-repo`), each on its own card |

Do not create Issues or change boards for a job the user excluded from
GitHub, and never as an automatic close-out of one. Reading an Issue is not
authorization to change it. A PR's closing reference must reflect the actual
complete scope; do not close a multi-PR Issue on its first layer. A build
delivers a PR, not a merge. Review corrections are further turns of the same
build session when released.

## Tracking a job on GitHub

Read `skill_view(name="github-access:read-tracking")` and
`skill_view(name="github-access:manage-tracking")` before the first GitHub
change of a job.

**The default.** A repository job is recorded on GitHub: its units are
issues, Fixed before they are built, on the board `github_board` `resolve`
names for the repository. The user excludes a job in their own words; that
goes in the decision log, and the job then gets no Issue or board change
(a supplied Issue URL stays a read-only spec). Nothing else excludes it:
not the job's size, nor a fix the user calls small. When no board resolves,
the roadmap question proposes making one (its owner and title), as the
tracking skill's "Setting up a board" says. The job's operational work
around its repository (hosting, DNS, a domain, a contract, a hand-over
item) is part of it: drafts on the same board. When the user raises the
board or the issues themselves, at any point of the job, the answer is this
same shape, after reading the tracking skill: never a board of Phase items,
columns or update rules you design anew.

**The record.** GitHub holds the plan; the job directory keeps what is
private: the decision log with the user's own words, mocks, reports and each
run's `progress.md`. Issue text is written for the repository's readers:
facts linked to their sources as the read skill's "Background" says, never
the user's quotes. What only you can know (a promise made in a message, a
date, a measurement you took, who holds a key) goes into the issue before
OpenCode reads it, with its source; a brief never carries facts the issue
lacks. On a `shared` or `other` tier the wording is agreed first.

**Writer reads it once.** Before an issue body (a parent, a unit at Draft,
a unit rewritten to Fixed) goes to the user or GitHub, one `specialist_call`
to `writer` (`kind: "work"`, an edit-document of the body's file: proofread
with the minimal correction, every address, link, number, date, identifier
and code word untouched) that also asks for what it finds unclear as a
spec: a requirement that reads two ways, an acceptance line nobody could
verify, a claim stronger than its evidence. Take a technical gap back to the
plan session as its own call, a decision to the user, and fold the answers
in yourself; one round, not a second proofreading. The corrected file is the
one the user sees and the one that is written.

**Starting.** In this order, once the roadmap (or the single unit) is
approved and before the first unit's build:

1. Gather the background: read what the job touches that you can reach
   (the conversation, the synced messages and sheets, the repository
   inventory, OpenCode's plan) and note each fact's source.
2. When the board does not exist yet, make it first, as the tracking
   skill's "Setting up a board" says.
3. Write the parent issue and every unit (and the operational drafts) into
   one Markdown file in the job directory, Writer's round done, agreed with
   the user as the tracking skill's "Before writing, by tier" says for the
   target's tier.
4. One `github_change` list, the parent first and a sub-issue per unit
   that names it as `parent` and the one before as `blocked_by`, each with
   `board_fields` (`Status` Todo), the drafts with it; the tracking skill's
   "Recipes" show the shape. One card shows the whole plan. A single-unit
   job is one `issue_create` with `board_fields`.
5. Propose the **mandate**: `routine`, boards = the job's board, repos = its
   repository, parent = the parent issue (so it covers that issue tree and
   nothing else in the repository), until the job is expected to be
   delivered, within the term the tracking skill's "Mandates" allows.
   Creating issues, commenting and closing still ask, unless the user's own
   private board and repository are all the job touches and the user wants
   those covered too.
6. Record the parent issue, the board and the mandate id in the decision
   log: a new session finds the job's GitHub record from there.

| Plan | On GitHub |
| --- | --- |
| A single-unit job | one issue (the mandate's parent is that issue), Status Todo |
| A roadmap | a parent issue (the outcome, the acceptance) with one sub-issue per unit (what people can do once it lands, how to try it), each blocked by the one before, every one Todo; a milestone when the user names a date or release |
| A unit's approval | its issue's body becomes Fixed: the decisions folded in, its layers as a `- [ ]` checklist, open decisions gone; Status In Progress. The parent, if still Todo, In Progress with it |
| A finished step (a progress notification) | nothing on GitHub: steps live in `progress.md` |
| A layer's PR is up | its checklist line ticked with the PR's `#n` (with a mandate at once, else with the unit's delivery) |
| An accepted, merged unit | its issue closed (by the last PR's closing reference, else `issue_close` `completed`); Status Done |
| All units accepted | the parent's acceptance checked against the evidence, then closed; Status Done; the mandate revoked |

**When the plan moves.**

| Event | On GitHub |
| --- | --- |
| The roadmap changes (a unit split, merged, added or dropped) | after the user approves the new roadmap, "Replacing issues" in the tracking skill: successors first, then the replaced ones closed with their numbers |
| The job is dropped | each open issue closed `not planned` with one comment saying why, Status Cancelled, drafts archived, the mandate revoked |
| The job pauses on someone outside | a dated note on the parent, Status Waiting; back to In Progress with a dated note when it resumes; revoke the mandate when the pause outlasts it |
| A new session resumes the job | the parent issue from the decision log, read fresh with `github_issue` `view` before any report |
| The user supplies an existing issue to track | one goal that lands once is the unit itself (Fixed from the plan); a goal of several units is the parent. On `shared` or `other` its body stays as it is, and the plan goes into sub-issues and comments |

**OpenCode reads; you write.** The run's `issue` argument (`owner/repo#N`)
names the issue it works on: the run reads it with its own tools, and the
build is told which issue its completing PR closes. Never pass
`issue_approval`: a build does not write Issues or boards. What a run reports
is mirrored to GitHub by you, after you have read it.

## Repository lifecycle

Use the decisions from [bootstrap](../../plan/references/bootstrap.md).
Before any registry call, read `skill_view(name="workspace-registry:manage")`.
Create a missing Group with the `workspace_registry` `group_create` action only when approved;
pass an organization only when it names a real approved registry record.
Establish GitHub repositories with approved owner, visibility and history
through `github_change` `repo_create` (`skill_view(name="github-access:manage-repo")`,
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

Use [acceptance](../../qa/references/acceptance.md) before the
`pr_merge` card, and `skill_view(name="github", file_path="references/merge.md")`
for its method and message. A finished stack lands whole, on one card from
its top layer: merging a layer also lands the open layers below it. After the
merge, verify actual state with `github_pr` `view`. If further stacked work was requested,
tell the build session what changed so it can propose the appropriate update;
do not grant history rewriting implicitly: with the user's explicit go, you
copy the steps of
`skill_view(name="github", file_path="references/history-repair.md")` into
the build's brief (a build run cannot load your skills). Close the unit's
issue and move the board as the table above says, never for a job the user
excluded.
