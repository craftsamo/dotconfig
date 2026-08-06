# In-turn parallel lookups — `delegate_task`

When the user is actively waiting on a **medium** lookup — heavier than a
single fact, lighter than a session or card — fire parallel lookups
in-turn with `delegate_task`.

- Children are **anonymous and stateless**: they run on your own
  model/session, see no chat history, and cannot be re-addressed. Pass
  the complete question and context in the goal; expect one final answer.
- Caps: max 3 concurrent, depth 1. Children have no kanban and no
  delegation of their own.
- Right for: comparing a handful of sources, checking several URLs,
  gathering per-item facts across a short list, per-artifact QA checks
  fanned out from Quality Assurance mode.
- Wrong for: anything needing follow-up questions to the same child
  (resident session), exhaustive hunts (kanban `exhaustive-hunt` unit),
  or depth/synthesis (researcher session).
