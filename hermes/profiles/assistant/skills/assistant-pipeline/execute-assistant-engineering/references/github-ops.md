# Engineering - GitHub boundaries

| Operation | Owner and permission |
| --- | --- |
| Code, commits, task-branch push, PR creation | An OpenCode build run you drive, within explicit implementation approval |
| Issue create/edit/comment | An OpenCode build run with `issue_approval`, ONLY when the user explicitly requests management for this job |
| Repo creation, clone, workspace registry | Assistant, when separately requested/approved |
| Project-board changes | Assistant, only within an explicit bookkeeping request |
| Merge | Assistant, only on the user's explicit go after readiness checks |
| Deploy/publish | Outside the implementation grant; separately scoped work |

Do not create Issues/epics or sync boards as automatic close-out. Reading an
Issue is not authorization to change it. A PR's closing reference must reflect
the actual complete scope; do not close a multi-PR Issue on its first layer.
A build delivers a PR, not a merge. Review corrections are further turns of
the same build session when released.

## Repository lifecycle

Use the decisions from [bootstrap](../../plan-assistant-engineering/references/bootstrap.md).
Create a missing Group with the `workspace_registry` `group_create` action only when approved;
pass an organization only when it names a real approved registry record.
Establish GitHub repositories with approved owner, visibility and history:
`gh repo create <owner>/<repo> --private --template <starter>` for a template,
or an approved scratch/history-preserving path. Clone through `ghq`, not an
unregistered local `git init`; preserve `upstream` when lineage is requested.
Register/link with the `workspace_registry` actions `repo_set` then `link_repo` using
the approved Group.

OpenCode receives the established clone and proposes/implements its skeleton,
project instructions and code. Do not invent an initial default-branch push to
make PR creation possible in an empty repository; resolve that bootstrap boundary
explicitly. Verify owner/visibility, remotes, workspace link and registry entry.
No credentials or private records belong in the repository or public descriptions.

## Merge

Use [acceptance](../../qa-assistant-engineering/references/acceptance.md) before asking
for the user's go. After an authorized merge, verify actual state. If further
stacked work was requested, tell the build session what changed so it can
propose the appropriate update; do not grant history rewriting implicitly. Close Issues or
change a board only within the separate requested management scope.
