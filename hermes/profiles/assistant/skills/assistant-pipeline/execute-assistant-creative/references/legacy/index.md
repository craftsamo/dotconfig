# Legacy creative - unit supervision

Use only for a Creator-confirmed legacy method after
[legacy planning](../../../plan-assistant-creative/references/legacy/index.md). Normal work uses
[the Client handoff](../../SKILL.md), not this unit loop. The common approval
and input-permission rules there apply here too, as does its direct delivery
procedure. Legacy is not an exception that restores routine Assistant QA.

## Resident session

Start `specialist_call(target="creator", kind="work", message=...)` with the
first released unit's settled spec, accepted input paths, `Backend:` where
applicable and `Budget:`. Keep the returned `conversation_id` and target for
continuations. Use one session per job so approved anchors, seeds, input
identity and spend history survive revisions; never mix unrelated jobs.

## Unit loop

1. Release the next ready unit: an anchor, a decided part/batch, or a fixed
   assembly. Unlike a normal Client job, do not ask Creator to decompose the
   whole legacy composite. Its family decisions and dependencies must be
   settled before release.
2. Receive durable paths, verification evidence, spend and reusable anchors.
   A proposal is an approval stop, not a finished part. An unexplained missing
   output or mismatched tally is a finding back to the same unit.
3. Relay the producer's checks and show the candidate without another inspection.
   Required failures or missing approval do not become a ready dependency;
   preserve unknowns and request a scoped technical fix or report the blocker.
4. Reconcile the Budget ledger, then release the next ready unit. Assembly
   waits for every input part to pass. Close and deliver through
   [media ops](../media-ops.md) only when the requested result is accepted.

Answer in-spec questions from existing context. Return scope changes,
uncovered taste decisions and grant expansions to the user. A capability gap
returns to Plan; never try a different backend to hide the gap. If a changed
direction invalidates an anchor, obtain the required new approval before
dependent production, without discarding consumed attempts.

## Part handoff

Carry exact, accepted durable input paths between units. A downstream defect
returns to the source unit and invalidates the affected downstream evidence
until rechecked. Accept Writer text through its existing writing gate, then
pass it unchanged to Creator. Finished speech, music or other hands assets
remain Creator-brokered inputs, not new legacy production or a second request
for the same dependency.

## Budget ledger

- Effective per-unit allowance is the released Budget plus explicitly
  sanctioned expansions. Failed attempts count where the contract counts
  calls. Keep the job total as well as each unit's tally.
- A report that does not reconcile needs correction. Unused allowance does
  not silently transfer to the next unit or reset on resume.
- A proposal approval does not grant more spend, and a spending allowance
  does not approve a specific proposal. Preserve both boundaries.

## Parallel work and cards

Independent, style-independent parts may use separate resident sessions.
Shared anchors and unsettled dependencies must pass the gate before their
consumers run. Only the two unchanged `card_units` in [../index.md](../../SKILL.md)
may ride kanban: approved anchored image batches and fully specified
deterministic renders. A whole video is not a card. Card defects normally
return to a resident conversation with the paths and itemized findings, not
a fresh card that loses history. A purely mechanical identical-spec rerender
still follows the existing closed catalog.
