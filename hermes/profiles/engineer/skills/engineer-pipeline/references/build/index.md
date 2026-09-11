# Build

Read the approved plan/current release and [OpenCode](../opencode.md). One
explicit implementation approval releases the agreed scope through PR delivery.
Do not ask again for every internal step, or force a new planning run on every
continuation. Read [Web UI](web-ui.md) for UI implementation handoffs.

1. Confirm the Git worktree, branch, existing changes and scope. Engineer may
   create a separate task branch/worktree with ordinary Git setup; never move or
   overwrite someone else's changes. This exception is not code generation:
   scaffolders, target edits and commits still go through OpenCode. Build refuses
   default branches; do not disguise one or widen permissions to get past it.
2. Use opencode_call(agent="build", approval="<relayed scoped Client decision>").
   Reference the agreed plan/inputs and request actual check results. Select a
   useful work increment; OpenCode owns detailed coding/subagent choreography.
   No rigid one-call-per-phase requirement or duplicate approach-skill content.
3. Read progress/results for questions, blocked actions and assumptions. Answer
   ordinary technical questions within scope; relay material changes to the Client.
   A follow-up continues the owned conversation. A fork copies its current state,
   not an arbitrary earlier checkpoint; for independent diagnosis use a fresh
   conversation with only the needed inputs.
4. Send implementation evidence to [QA](../quality-assurance/index.md). Apply
   accepted corrections through OpenCode and recheck affected behavior. Do not
   alter code yourself to manufacture a passing report.
5. Once local QA passes, ask OpenCode to stage only intended changes, create
   coherent commits, push the task branch and create the PR with evidence and
   remaining limitations. Follow the repository's Git/PR conventions. Never
   blanket-stage, force a WIP commit or amend without explicit authorization.
6. Verify the actual PR through QA before delivering. CI still running/failed is
   reported honestly; an unmet required check cannot be called complete.

An image-creator/video-creator/audio-creator hands leaf's option-backed
reference change uses [Hands references](hands-references.md) for its actual
authoring and verification steps.

Issue create/edit/comment needs separate issue_approval naming the Client's
request to manage this job; a supplied Issue number is not a grant. Link a
closing Issue only when this PR finishes its scope. No automatic epics, boards,
merge, deploy/publish, new remote/repo or default-branch push. An explicit
local-only exception stops before remote actions and is reported as an exception.
The current wrapper grants build-to-PR, not a sandboxed arbitrary smaller grant:
if tool policy cannot represent a restriction, stop rather than weakening it.

Before waiting, record the current plan/approval, worktree/branch, conversation
IDs, evidence and open question. Stop/reconcile uncertain runs per the shared
contract; never restart blindly or change backends to escape a block. Follow-up
review corrections need a released scope, not an indefinite background loop.
