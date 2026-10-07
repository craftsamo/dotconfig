---
name: execute-assistant-engineering
description: "Execute engineering: supervise approved work to PR delivery. Preserve Engineer ownership and explicit Issue grants; no competing OpenCode session, merge or deployment."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
    tags: ["execute", "engineering"]
---

<ReadBeforeWork>

Re-evaluate the entry when the request, mode or domain changes, including within a turn.
Reuse full-body instructions only while present in the current context, not a past load or summary.
Check the kernel and common mode procedure independently. Load each whose full body is missing:

```text
skill_view(name="assistant-pipeline")
skill_view(name="assistant-pipeline", file_path="references/execute/index.md")
```

These dependencies also apply to direct entry. Loading does not restart an approved plan or expand a grant.
If a tool returns unchanged while the earlier body is unavailable, use read_file on `${HERMES_SKILL_DIR}/../SKILL.md` and `${HERMES_SKILL_DIR}/../references/execute/index.md`.
Recover this entry and its own references from ${HERMES_SKILL_DIR} likewise.
Follow next_offset until the whole required document is available; do not invent alternate paths or ranges to evade dedup.
If the required instructions remain missing, stop the affected action and report it, never infer a pass.
Read only applicable detail references below.

</ReadBeforeWork>

# Engineering - Client execution

Engineer is the developer responsible for technical planning and implementation
with OpenCode. You are its Client. Engineering is resident-only and has no
card_units. Reserve kind="inquiry" for a short question Engineer can answer
within its inbound A2A limits, without terminal, browser or OpenCode. Any filesystem
inspection, script or audit run, or other OpenCode-backed investigation - even
a findings-only assessment - goes through specialist_call(kind="work")
resident instead; sending kind="work" only selects that transport and tool
access, it is not implementation approval.

1. Send the outcome, repository location, constraints, existing decisions,
   success criteria and supplied inputs. State explicitly when the user asked
   only for a read-only assessment of current state, so Engineer does not edit.
   Do not require an Issue, Base session, preset authority code or a pre-built
   unit decomposition.
2. Relay Engineer's material questions and proposal to the user. Preserve what
   was suggested vs decided. Once the user gives explicit implementation approval,
   send that scoped decision in the same Engineer conversation.
3. That single approval releases the agreed plan through PR delivery, including
   its task-branch push. Engineer self-sequences internal phases; no per-unit
   release loop. Handle reported scope/permission changes with the user, not a
   silently widened grant. Respect an explicit local-only or smaller request.
   Size each resident turn to its 90-minute budget: one verifiable increment
   per turn (a feature slice with its checks, a QA pass, a checkpoint commit),
   continued in the SAME conversation, never "everything to PR" in one turn.
   A large approved scope is many turns of one conversation. Ask Engineer to
   checkpoint-commit verified work on the task branch as it goes.
   A model/variant preference is passed as a preference for Engineer's
   opencode_call arguments (the maintainer allowlist decides); a refused name
   is reported back, never a reason to stall the job or to invent a
   restriction the user did not make. A narrower grant (local commit only, no
   push) still runs through Engineer's ordinary build wrapper with that
   instruction; do not forbid the wrapper itself.
4. Issue create/edit/comment is delegated ONLY when the Client explicitly requests
   Issue management for this job. A supplied Issue URL remains a read-only spec
   without that request. No automatic epics, board updates or bookkeeping.
5. Check the delivered report/PR against
   [Client QA](../qa-assistant-engineering/SKILL.md). Return concrete
   defects to the same conversation. Close accepted work with specialist_session;
   follow-up review changes can be released as further scoped work.

Keep conversation identity across turns. Unknown transport completion is not
proof that work failed: inspect status, never resubmit through another route.
Never drive Engineer outside specialist_call — no `hermes -p engineer` from the
terminal, no `--resume` of its session, no environment stripping; a foreign
route cannot own its OpenCode records and only deepens the block. After a
timeout (exit 124) follow resident-sessions.md: reconcile, then send ONE
`kind="reconcile"` turn on that same conversation so the owning session clears
its OpenCode holds, then continue the work in a fresh conversation seeded with
the committed checkpoint. Do not run a competing OpenCode session, copy
Engineer's browser session, or patch its target code yourself: your own
opencode_call exists for the Admin topic's scope (this config repo, Hermes
upkeep, a named workspace repo), and its registry is separate from
Engineer's, so it would not even see Engineer's hold on a worktree. Independent
jobs need separate worktrees and explicitly disjoint scope; concurrency is not
a reason to multiply one job.

After a context compaction, the summary is not the request. Before sending a
continuation, read the conversation's latest `.handoff` record (path in
`specialist_session status`) and the deliverable evidence you cite, and send a
complete self-contained request; a message containing `[truncated]` or an
elided path is a defect on your side, and Engineer will refuse it.

[github-ops.md](references/github-ops.md) defines conditional Issue ownership, repository
lifecycle and the separate user-gated merge boundary. Engineer never merges,
deploys or pushes the default branch. A plan/review-only request ends with its
answer; do not turn it into implementation because a fix looks easy.
