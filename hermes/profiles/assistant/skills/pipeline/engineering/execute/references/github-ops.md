# Engineering - GitHub boundaries

| Operation | Owner and permission |
| --- | --- |
| Code, commits, task-branch push, PR creation | An OpenCode build run you drive, within explicit implementation approval |
| A PR for a branch already pushed that the user names | You, through `github_pr_create` (`skill_view(name="github-tools:pull-requests")`), when the user asks; never for a branch a build run made, whose PR comes from that run |
| A PR's text, labels, reviewers, attachments (screenshots), ready / draft, closing | You, through `github_pr_edit`, `github_pr_comment`, `github_pr_ready` and `github_pr_close` (`skill_view(name="github-tools:pull-requests")`; the user's conventions `skill_view(name="github", file_path="references/pull-requests.md")`), when the user asks; each attached file with their yes |
| Issues and boards | You, through the `github_issue_*` and `github_project_*` tools (`skill_view(name="github-tracking")`), as the record of every job on a repository the user owns or belongs to (below) unless the user excluded it; someone else's repository gets only what its conventions ask (below); a build writes none of it: you mirror its progress (below) |
| Repo creation and settings, labels, milestones, branch protection, clone, workspace registry | Assistant, when separately requested/approved; GitHub changes through the `github_repo_*`, `github_label_*`, `github_milestone_*` and `github_ruleset_*` tools (`skill_view(name="github-tools:repos")`; the user's conventions `skill_view(name="github", file_path="references/repository.md")`) |
| CI: why a run failed, re-running it | You read it (`github_run_read`); a real failure goes back to the build session. A re-run (`github_run_rerun`) when the user asks, or proposed by you only for a failure that looks transient; its card is their go |
| Merge | Assistant, only when the user asks, after readiness checks: `github_pr_merge`, whose card is their go; method and message as `skill_view(name="github", file_path="references/merge.md")` says |
| Deploy/publish (publishing a release, starting a workflow that deploys) | Outside the implementation grant; separately scoped work. When the user asks for it: `github_release_create` / `github_release_publish` (`skill_view(name="github-tools:releases")`) or `github_workflow_run` (`skill_view(name="github-tools:actions")`), each on its own card |

Do not create Issues or change boards for a job the user excluded from
GitHub, and never as an automatic close-out of one. Reading an Issue is not
authorization to change it. A PR's closing reference must reflect the actual
complete scope; do not close a multi-PR Issue on its first layer. A build
delivers a PR, not a merge. Review corrections are further turns of the same
build session when released.

## Tracking a job on GitHub

Read `skill_view(name="github-tracking")` (and the package mechanics it
names, `github-tools:issues` and `github-tools:projects`) before the first
GitHub change of a job.

**The default.** A job on a repository the user owns or belongs to (tier
`own` or `shared`, read with `github_repo_read` `view`) is recorded on GitHub:
its units are issues, Fixed before they are built, on the board
`github_project_read` `view` names for the repository. The user excludes a job
in their own words; that goes in the decision log, and the job then gets no
Issue or board change (a supplied Issue URL stays a read-only spec). Nothing
else excludes it: not the job's size, nor a fix the user calls small. When
no board resolves, the roadmap question proposes making one (its owner and
title), as the tracking skill's "Setting up a board" says. The job's
operational work around its repository (hosting, DNS, a domain, a contract,
a hand-over item) is part of it: drafts on the same board. When the user
raises the board or the issues themselves, at any point of the job, the
answer is this same shape, after reading the tracking skill: never a board
of Phase items, columns or update rules you design anew.

**Someone else's repository** (tier `other`: an open-source project, a
client's or a colleague's repository the user does not own or belong to) is
not the user's to plan in. Its tracker takes only what its own conventions
ask for (`CONTRIBUTING`, an issue or PR template: a bug report before a fix,
a discussion first), each on its own card with the wording agreed as the
tracking skill's "Before writing, by tier" says; never a parent issue, a
unit's Fixed body, layers, a Status or a comment that reports your
progress. An upstream issue the work answers is the run's `issue`, read as
the spec and closed by the PR as that project's convention has it; you
never edit it. The user's own record of such a
job, when they want one, is on their side: an issue on their fork (then that
is the run's `issue`, Fixed as usual) or a draft on their own board; the
roadmap question asks which, or none, and a none, in the user's words, is the
build's `untracked_reason`. The build pushes to the user's fork, never to the
upstream: [Execute](../SKILL.md) step 2 checks the checkout's `origin`
before the build. A bug report alone, with no fix asked for, is Chat's one
issue on its card, not a job.

**The record.** GitHub holds the plan; the job directory keeps what is
private: the decision log with the user's own words, mocks, reports and each
run's `progress.md`. Issue text is written for the repository's readers:
facts linked to their sources as the read skill's "Background" says, never
the user's quotes. What only you can know (a promise made in a message, a
date, a measurement you took, who holds a key) goes into the issue before
OpenCode reads it, with its source; a brief never carries facts the issue
lacks. On a `shared` or `other` tier the wording is agreed first, and
everything written there (the Fixed body, its ticks, the PR text) is read by
people you cannot name: a public repository's readers are anyone. Nothing
about the user's business, customers, accounts, other people or this machine
goes there, even where it is true and would help; what the user wants kept
stays in the decision log, as the read skill's "Which links a body may
carry" draws the line.

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
4. The calls in order, each on its own card: the parent first
   (`github_issue_create` with the board as `project`), then a sub-issue per
   unit that names it as `parent` and the one before as `blocked_by`, each
   with `fields` (`Status` Todo), then the drafts; the tracking skill's
   "Recipes" show the shape, and its "Cards and the `session` answer" says
   what to offer the user. A single-unit job is one `github_issue_create`
   with `project` and `fields`.
5. Record the parent issue and the board in the decision log: a new session
   finds the job's GitHub record from there.

| Plan | On GitHub |
| --- | --- |
| A single-unit job | one issue, Status Todo |
| A roadmap | a parent issue (the outcome, the acceptance) with one sub-issue per unit (what people can do once it lands, how to try it), each blocked by the one before, every one Todo; a milestone when the user names a date or release |
| A unit's approval | its issue's body becomes Fixed: the decisions folded in, its layers as a `- [ ]` checklist, open decisions gone; Status In Progress. The parent, if still Todo, In Progress with it |
| A finished step (a progress notification) | nothing on GitHub: steps live in `progress.md` |
| A layer's PR is up | its checklist line ticked by you with the PR's `#n`, after you have read the run's report |
| An accepted, merged unit | its issue closed (by the last PR's closing reference, else `github_issue_close` `completed`); Status Done; then its worktree tidied with `opencode_session cleanup` on the unit's session (a refusal means something is not landed or not committed: report it, never force it) |
| All units accepted | the parent's acceptance checked against the evidence, then closed; Status Done |

**When the plan moves.**

| Event | On GitHub |
| --- | --- |
| The roadmap changes (a unit split, merged, added or dropped) | after the user approves the new roadmap, "Replacing issues" in the tracking skill: successors first, then the replaced ones closed with their numbers |
| A unit's work turns up more work (a bug, a follow-up) | the tracking skill's "Work found mid-job": a sibling under the parent, never under the unit, and the parent's Plan updated with it |
| The job is dropped | each open issue closed `not planned` with one comment saying why, Status Cancelled, drafts archived |
| The job pauses on someone outside | a dated note on the parent, Status Waiting; back to In Progress with a dated note when it resumes |
| A new session resumes the job | the parent issue from the decision log, read fresh with `github_issue_read` `view` before any report |
| The user supplies an existing issue to track | one goal that lands once is the unit itself (Fixed from the plan); a goal of several units is the parent. On `shared` or `other` its body stays as it is, and the plan goes into sub-issues and comments |

**OpenCode reads; every Issue and board write is yours.** The run's `issue`
argument (`owner/repo#N`) names the issue it works on: the run reads it with
its own tools, and the build is told which issue its completing PR closes.
OpenCode reads GitHub, opens its PRs and links its stack (`github_pr_create`,
`github_stack_link`), and may set a PR's metadata through `github_pr_edit`,
each of which you approve `once` when it fits: the push against its preview,
the text for a reader with only the repository, never a board. Metadata is
labels, assignees, reviewers and milestone only; the plugin refuses `once`
on a PR edit that carries a title, body, base, closing issue or attachment,
or a PR create with board arguments (`project`/`fields`)
(`skill_view(name="opencode:answer")`). Everything else on GitHub is yours,
mirrored from the unit's `progress.md` and the run's report once you have
read them: the issue's layers ticked as their PRs open, its Status, the
parent and the other issues, comments, closing, drafts, the board itself. The
task branch reaches the issue through the PR's `Closes`/`Refs`, never a
linked branch. Never pass `issue_approval`.
What a run reports beyond its own steps is mirrored to GitHub by you, after
you have read it; a write the run tried and was refused comes back in its
report and is yours to make or not.

## Repository lifecycle

Use the decisions from [bootstrap](../../plan/references/bootstrap.md).
Before any registry call, read `skill_view(name="workspace-registry:manage")`.
Create a missing Group with the `workspace_registry` `group_create` action only when approved;
pass an organization only when it names a real approved registry record.
Establish GitHub repositories with approved owner, visibility and history
through `github_repo_create` (`skill_view(name="github-tools:repos")`,
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
`github_pr_merge` card, and `skill_view(name="github", file_path="references/merge.md")`
for its method and message. A finished stack lands whole, on one card from
its top layer: merging a layer also lands the open layers below it. After the
merge, verify actual state with `github_pr_read` `view`. If further stacked work was requested,
tell the build session what changed so it can propose the appropriate update;
do not grant history rewriting implicitly: with the user's explicit go, you
commission the repair from a build as
`skill_view(name="github", file_path="references/history-repair.md")`
describes it: the outcome, the conditions it must meet afterwards and the
evidence to hand back, never its commands (a build run cannot load your
skills, and the method is its own). Close the unit's
issue and move the board as the table above says, never for a job the user
excluded.
