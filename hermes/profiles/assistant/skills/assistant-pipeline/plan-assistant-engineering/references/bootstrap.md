# Bootstrap - Client decisions

Repository creation and workspace registration are separate from Engineer's
work inside a repository. Get the user's approval of owner/name, visibility,
workspace Group and any starter/history choice before establishing them through
[GitHub operations](../../execute-assistant-engineering/references/github-ops.md).

Engineer may research starter candidates and recommend a fit; Assistant need
not choose a framework or design the skeleton first. Discover actual candidates
and their README, lineage, template status and maintenance history, never a
memorized catalog. An unsuitable starter can be worse than starting from scratch.

When applicable, starter lineage is root `<name>-starter`, platform derivative
`<root>-with-<platform>`, then variant. Keeping history vs template instantiation
is an explicit choice; preserve the intended upstream relationship. Concrete
account/repository names remain runtime context, not this guide.

Confirm the Group with the `workspace_registry` `project` action (id = `<Group>`) and
optional organization with the `projects` action (kind = org); never infer an organization
from the GitHub owner. Default
repository visibility is private unless the user explicitly chooses public.
Deploy-target discussion does not authorize deployment or paid provisioning.

Once an established clone exists, hand its location and approved choices to
Engineer. Worktree/skeleton planning and implementation belong there, under the
same implementation approval contract; no separate Assistant OpenCode base
session is required. An empty remote/default branch bootstrap that cannot safely
produce a PR is an explicit blocker to resolve, never permission to push default.
