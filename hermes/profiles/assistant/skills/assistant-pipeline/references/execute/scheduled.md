# Scheduled — time-parked work

Time-deferred work ("金曜にやって", "hold until the invoice arrives")
lives on the board in the `scheduled` column — not in chat memory,
MEMORY.md, or a cron prompt. `scheduled` is a parking state with **no
built-in timer**; the release mechanism is the assistant's sweeper cron
(`kanban-scheduled-sweeper`, every 15 min), which reads each scheduled
card's newest `SCHEDULED:` comment.

- **New deferred task**: `kanban_create(..., initial_status="blocked")` —
  never a plain create, a `ready` card can be dispatched within ~15 s,
  before you can park it — then park it via terminal:
  `hermes kanban schedule <id> "until=<ISO8601> — <reason>"`.
  Park **in the same turn, immediately**. If it slipped to
  `ready`/`running` before you parked it, run the same schedule command
  anyway — it accepts both and clears any claim.
- **Existing card**: same CLI; works from todo/ready/running/blocked.
- **`until=` format**: local-time ISO 8601, e.g. `until=2026-07-25T09:00`.
  The sweeper unblocks the card on the first sweep past that time and
  normal dispatch + completion notifications take over.
- A scheduled card whose newest `SCHEDULED:` comment has **no `until=`**
  is a manual hold: the sweeper skips it; release with
  `hermes kanban unblock <id>` when the user says so.
- Condition-deferred work: prefer a `parents` link when the trigger is
  another task; `scheduled` + manual release when the trigger is external
  to the board.
- A parked card still needs a settled catalog-unit spec at park time — do
  not park a vague intention and hope future-you specifies it.
