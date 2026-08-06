# Card runtime — dialogue and completion mechanics

Load this FIRST on any kanban card run (`HERMES_KANBAN_TASK` set), after
the kernel's unit gate has admitted the card as one legal catalog unit.
The unit gate itself lives in the kernel (<KanbanMode>); this file owns
the comment grammar, block mechanics, and completion contract. Prior
runs on the card → also load `references/resume.md`.

## Comment grammar

Card dialogue travels as comments with a fixed first-token marker (shared
contract across workers). You WRITE:

- `STATE:` — before a block: what's produced so far, what the question
  decides, which intermediates sit in the workspace, the locked anchor
  values if any, and the spend tally.
- `Q<n>: <question>` — numbered questions, 2-4 concrete options, your
  recommendation marked. Numbering continues across the card's lifetime;
  batch all pending questions into one block round-trip.
- `PROGRESS: <one-two lines>` — per finished asset (or batch chunk),
  ending with the running spend tally. Comments are NOT pushed to chat;
  keep them frequent but terse.

You READ: `DECISION(Q<n>): <choice>` — the binding answer — and
`AUTHORITY+: <grant line>` — a Budget expansion.

## Block mechanics

Checkpoint first (attach work-so-far or name the workspace intermediates
in `STATE:`), then `kanban_block(kind=needs_input, reason=...)` with a
**<=160-char headline** naming the open question ids (the notification
truncates); the full `Q<n>:` text lives in comments. Stop producing after
the block call. Questions get exactly ONE batched `needs_input` round for
the card's life — a second block ends the card (the assistant pulls it
back), so never ask incrementally.

A card body carrying `Review: required` is malformed — a catalog card is
fire-and-forget by definition; `kanban_block(kind=capability)` instead of
running it (human sign-off belongs to the resident runtime).

## Completion

End every run with `kanban_complete` (summary naming every artifact +
spend tally; attach the files and also copy them to the durable
destination the body names) or `kanban_block`. Never create cards;
propose follow-up work in your completion summary instead. The
`kanban_complete` summary is 1-2 plain user-facing sentences; detail
belongs in the final message.

## Pitfalls

- Blocking without a checkpoint, block reasons that don't survive
  160-char truncation, or reusing a question number.
- Long runs with no `PROGRESS:` trail.
- Completing without attaching the files AND copying them to the durable
  destination — scratch dies on completion.
