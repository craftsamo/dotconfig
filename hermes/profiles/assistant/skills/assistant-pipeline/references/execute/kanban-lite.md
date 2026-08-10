# Kanban (lean) — catalog units, fire-and-forget

Load when the selected tier is `kanban`. The board is the minority path:
it exists for work where conversation adds nothing —

- **fire-and-forget** units with a fully settled spec you would accept
  sight unseen,
- **cron-originated** work (a schedule, not a chat, is the requester),
- **mass-parallel production** across independent items with no per-item
  feedback loop,
- **time-parked** work (`scheduled.md`).

Everything interactive belongs in a resident session instead. The v4
machinery — pending manifests, digests, overlays, fan-out, admission
probes, QA cards — is retired; do not write or expect those markers.

## The closed catalog

**A card must be one catalog unit.** The catalog is the union of
`card_units` front matter across `execute/<capability>/*.md`; a card is
legal only when:

1. its work matches one unit's `name` and unit definition,
2. every `required_inputs` item exists and is settled (an approved
   anchor, a final script, a fixed spec list — by reference or pasted),
3. it respects the unit's `unit_cap`, and carries the unit's
   `runtime_cap` as `max_runtime_seconds`.

No matching unit → resident session or further decomposition at plan
time. A detailed body is NOT a unit; a composite deliverable (a whole
video, a campaign, a feature) is NEVER a unit. **Never send 0→10 of
anything as one card.** The catalog grows only by explicitly editing an
execute leaf — never by run-time interpretation.

Workers enforce this too: a card that turns out composite or is missing a
required input comes back as `blocked(capability)` fast, without burning
budget. That is the system working, not an error to argue with.

## Card contract

Workers never see the chat — the body is their entire context:

```text
title: <imperative, <=80 chars>
body:
  Unit: <card_units name, e.g. anchored-image-batch>
  Goal: <what outcome, for whom — one short paragraph>
  Inputs: <links, paths, pasted data — every required_inputs item,
          settled; paste what matters>
  Deliverable: <format/language/length; the card workspace dies on
               completion, so require final files at an explicit owning-Group
               ~/Workspaces/{Projects,Personal}/<Group>/.agent/deliverables/<job>/
               destination, revision-worthy intermediates under the same
               Group's .agent/scratch/<job>/, and reuse evidence under
               .agent/notes/ or assets/; also kanban_attach finals; use root
               state only when no single Group owns the work>
  Constraints: <scope limits, deadlines, things NOT to do>
  <Budget: / Authority: / Publish: line when the profile uses one — same
   semantics as resident sessions; tightest default when unsanctioned>
```

Parameters:

- `assignee` — required; exact profile name (`creator`, `writer`,
  `researcher`, `searcher`, `engineer`, `marketer`). The dispatcher never
  validates it: a typo leaves the card sitting unclaimed forever, so
  double-check the name.
- `skills: ["<profile>-pipeline", ...optional technics]` — always pin the
  pipeline; add a technic only when the deliverable clearly selects one
  that exists on that profile.
- `workspace_kind`: `scratch` default; `worktree` + absolute
  `workspace_path` (or `project: <slug>`) for repo work; `dir` rare.
- `max_runtime_seconds` = the unit's `runtime_cap`; `goal_mode: true`
  (+ `goal_max_turns`) only where the unit says so (open-ended hunts).
- `idempotency_key` on any retry/re-dispatch so a duplicate returns the
  existing card.
- Require `subscribed=true` on create (a gateway chat auto-subscribes);
  if false, retry once with the same key, then stop and report.

Ack with the task id and end the turn. Register only the **frontier**:
when a planned stage consumes another card's output, create it only after
that output passed your QA.

## Wakeup triage

Wakes are terminal events only — `completed`, `blocked`, `gave_up`,
`crashed`, `timed_out`. A comment alone never wakes you; a worker that
needs an answer blocks with `kind=needs_input` plus its question comment.
Always `kanban_show` first — notification headlines truncate.

| Wake | Handling |
| --- | --- |
| `completed` | Read result + artifacts, run Quality Assurance mode on the actual deliverables. Pass → deliver or feed/register the next frontier stage. Fail → revision goes to a **resident session** seeded with artifacts + itemized defects (`resident-sessions.md`); only a purely mechanical re-render may be a fresh card. |
| `blocked(needs_input)` — answerable from the approved plan/inputs | Answer **once**: one `DECISION(Q<n>): <choice> — <reason>` comment per open question (`REVIEW:`/`APPROVAL:` headlines are ALWAYS the user's — relay, never answer), then resolve through the wrapper below. One round is the cap. |
| `blocked(needs_input)` — the question reveals a spec gap or unit mismatch | Pull back: archive the card, return to Plan (decompose or go resident). Answering would be improvising the spec the plan should have settled. |
| `blocked(capability)` | The worker's fast-fail: wrong unit shape, composite work, missing input. Always pull back — never argue the card into running. |
| `blocked(transient)` / `crashed` / `timed_out` | Retry once (same `idempotency_key`); on recurrence, pull back and report. |
| `gave_up` | `kanban_show`, state the cause plainly, pull back (resident or re-plan). |
| Second block of any kind on the same card | Pull back unconditionally — the kernel escalates repeat blocks to `triage` (`BLOCK_RECURRENCE_LIMIT = 2`); treat a triage-fallen card as pulled back, don't restore it. |

Resolving an answered block — never `kanban_unblock` directly:

```bash
~/.hermes/profiles/assistant/scripts/kanban-resolve-block.sh apply <id>
```

The wrapper verifies a decision follows the latest block event, unblocks,
and resets the counter as one guarded operation.

"Pull back" = archive via terminal (`hermes kanban archive <id>` — there
is no kanban tool for archiving), then continue the work on the right
tier: usually a resident session seeded with whatever the card produced,
or a re-plan with the user when the premise broke. Tell the user in one
plain line what happened and what you did.

Card completion is producer verification, not user acceptance. Before a
worker completes, every final, revision-worthy intermediate, and reuse
contract item must leave the disposable card workspace for the owning
Group paths named in the card. The Assistant alone clears those job paths
after QA, delivery, and user acceptance.

## Pitfalls

- Registering a card that matches no `card_units` entry, or stretching a
  unit definition because the body "is detailed enough".
- Sending feedback-likely work here — if you expect to comment on the
  result, it was a resident session.
- Bodies that reference chat context, or deliverables left only in
  scratch.
- Registering QA cards, manifests, digests, or fan-out markers — v4 is
  retired; you are the quality gate.
- Answering a blocked card a second time, restoring a triage-fallen card,
  or unblocking without the guarded resolver.
- Cycling revisions through fresh cards — revisions converge in resident
  sessions.
- Duplicate cards for the same ask (use `idempotency_key`).
- Wrong assignee → the card sits unclaimed forever; archive and
  re-register, and say so.
