# Kanban (lean) — fire-and-forget, cron, mass-parallel, scheduled

Load when the selected tier is `kanban`. The board is the minority path in
Workflow v5: it exists for work where conversation adds nothing —

- **fire-and-forget** jobs with a fully settled spec you would accept
  sight unseen (e.g. an exhaustive goal-mode source hunt),
- **cron-originated** work (a schedule, not a chat, is the requester),
- **mass-parallel production** across independent items with no per-item
  feedback loop,
- **time-parked** work (`scheduled` — see the main skill's <Scheduled>).

Everything interactive belongs in a resident session instead. The v4
machinery — pending manifests, digests, overlays, fan-out, admission
probes, QA cards — is retired; do not write or expect those markers.

## Card contract

Workers never see the chat — the body is their entire context:

```text
title: <imperative, <=80 chars>
body:
  Goal: <what outcome, for whom — one short paragraph>
  Inputs: <links, paths, pasted data; paste what matters>
  Deliverable: <format/language/length; artifact files at a durable path —
               scratch dies on completion, so require kanban_attach AND/OR
               an explicit ~/Workspaces/... destination>
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
- `max_runtime_seconds` for anything that could run away;
  `goal_mode: true` (+ `goal_max_turns`) for open-ended hunts.
- `idempotency_key` on any retry/re-dispatch so a duplicate returns the
  existing card.
- Require `subscribed=true` on create (a gateway chat auto-subscribes);
  if false, retry once with the same key, then stop and report.

Ack with the task id and end the turn. Never poll — terminal events
(done / blocked / gave_up / crashed / timed_out) arrive as notifications.

## Completion

`kanban_show <id>`, read the result summary and artifacts, then run
<ModeQA> on the actual deliverables exactly as for a session turn.
Follow-up work the worker proposes in its summary is yours to decide —
plan it conversationally; nothing self-registers.

## Blocked cards

Workers block with `STATE:` + numbered `Q<n>:` questions (options +
recommendation). The notification headline is truncated — **always
`kanban_show` first.**

- Answer within the sanctioned plan yourself; relay the rest (`clarify`
  when options exist). `REVIEW:` / `APPROVAL:` headlines are ALWAYS the
  user's — never answer them autonomously.
- Record one `DECISION(Q<n>): <choice> — <reason>` comment per open
  question — every open question in the batch, never a partial set. Grant
  expansions get their own `AUTHORITY+: <grant>` comment.
- Then resolve through the wrapper — never `kanban_unblock` directly:

  ```bash
  ~/.hermes/profiles/assistant/scripts/kanban-resolve-block.sh apply <id>
  ```

  The kernel escalates the second same-kind block of a card's life to
  `triage` silently (`BLOCK_RECURRENCE_LIMIT = 2`); the wrapper verifies a
  decision follows the latest block event, unblocks, and resets the
  counter as one guarded operation. A card already fallen to `triage` is
  restored the same way after answering its questions.

## Failures

- `gave_up` / `crashed` / `timed_out` → `kanban_show`, state the cause
  plainly in chat, and decide: retry the same spec (same
  `idempotency_key`), fix the spec in a fresh card, or pull the work into
  a resident session where it can be supervised.
- Wrong assignee or superseded spec → archive via terminal
  (`hermes kanban archive <id>` — there is no kanban tool for archiving)
  and re-register correctly. Permanent delete only on an explicit user
  ask.

## Pitfalls

- Sending feedback-likely work here because the spec "seems complete" —
  if you expect to comment on the result, it was a resident session.
- Bodies that reference chat context, or deliverables left only in
  scratch.
- Registering QA cards, manifests, digests, or fan-out markers — v4 is
  retired; you are the quality gate.
- Unblocking without a `DECISION(Q<n>)` per open question, or calling
  `kanban_unblock` directly.
- Duplicate cards for the same ask (use `idempotency_key`).
