---
name: build-engineer
description: "Build engineering: implement explicitly approved scope."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: engineer-pipeline
    tags: [build, engineering]
---

<ReadBeforeWork>

Re-evaluate the entry when the request, mode or scope changes, including within a turn.
Load the root with skill_view(name="engineer-pipeline") only if its full body
is not already present in the current context; reuse full-body instructions
only while present in the current context, not a past load or summary. This
entry is the mode procedure itself, not a second common mode index. Canonical
root fallback when skill_view returns unchanged without its earlier body is
`${HERMES_SKILL_DIR}/../SKILL.md`; recover this entry's own
body and its references from `${HERMES_SKILL_DIR}` via read_file and
next_offset. Stop the affected action when a required body is unavailable;
never take an alternate path or an artificial range to dodge this check.

Before the first wrapper call, or whenever transport context is lost, load
skill_view(name="engineer-pipeline", file_path="references/opencode.md") if
its full body is not already present, with fallback
`${HERMES_SKILL_DIR}/../references/opencode.md`; no generic per-mode common
transport copy. Reading the root or transport file is not implementation
approval. A cross-mode link requires loading that mode's owning entry and the
root before applying its details -- only the locally relevant details apply here.

</ReadBeforeWork>

# Build

Read the approved plan/current release and [OpenCode](../references/opencode.md). One
explicit implementation approval releases the agreed scope through PR delivery.
Do not ask again for every internal step, or force a new planning run on every
continuation. Read [Web UI](references/web-ui.md) for UI implementation handoffs.

1. Confirm the Git worktree, branch, existing changes and scope. Engineer may
   create a separate task branch/worktree with ordinary Git setup; never move or
   overwrite someone else's changes. This exception is not code generation:
   scaffolders, target edits and commits still go through OpenCode. Build refuses
   default branches; do not disguise one or widen permissions to get past it.
2. Use opencode_call(agent="build", approval="<relayed scoped Client decision>").
   Reference the agreed plan/inputs and request actual check results. Select a
   useful work increment that fits the turn budget; OpenCode owns detailed
   coding/subagent choreography. The call blocks until the run ends: do not
   poll it. No rigid one-call-per-phase requirement or duplicate
   approach-skill content. Pass a Client-requested model/variant through the
   call's own arguments when the allowlist permits it; otherwise report and ask.
3. Read progress/results for questions, blocked actions and assumptions. Answer
   ordinary technical questions within scope; relay material changes to the Client.
   A follow-up continues the owned conversation. A fork copies its current state,
   not an arbitrary earlier checkpoint; for independent diagnosis use a fresh
   conversation with only the needed inputs.
4. Send implementation evidence to [QA](../qa-engineer/SKILL.md). Apply
   accepted corrections through OpenCode and recheck affected behavior. Do not
   alter code yourself to manufacture a passing report.
5. Checkpoint as you go: after each increment whose focused checks pass, ask
   OpenCode to stage only that increment's intended changes and create one
   coherent local commit on the task branch. A turn that dies at its budget
   must strand nothing uncommitted. Once local QA passes overall, push the
   task branch and create the PR with evidence and remaining limitations.
   Follow the repository's Git/PR conventions. Never blanket-stage, commit
   unverified or broken state as a "WIP", or amend without explicit
   authorization; a checkpoint commit is a real commit of verified work.
6. Verify the actual PR through QA before delivering. CI still running/failed is
   reported honestly; an unmet required check cannot be called complete.

An image-creator/video-creator/audio-creator hands leaf's option-backed
reference change uses [Hands references](references/hands-references.md) for its actual
authoring and verification steps.

Issue create/edit/comment needs separate issue_approval naming the Client's
request to manage this job; a supplied Issue number is not a grant. Link a
closing Issue only when this PR finishes its scope. No automatic epics, boards,
merge, deploy/publish, new remote/repo or default-branch push. An explicit
local-only exception stops before remote actions and is reported as an exception.
The current wrapper grants build-to-PR, not a sandboxed arbitrary smaller grant:
if tool policy cannot represent a restriction, stop rather than weakening it.

Before waiting, record the current plan/approval, worktree/branch, conversation
IDs, evidence and open question. When the turn budget nears its end (~15 min),
finish with a checkpoint commit and report instead of starting a run.
Stop/reconcile uncertain runs per the shared contract; never restart blindly
or change backends to escape a block. Follow-up review corrections need a
released scope, not an indefinite background loop.
