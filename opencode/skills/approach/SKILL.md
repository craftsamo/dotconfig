---
name: approach
description: >-
  Use for non-trivial or ambiguous work — planning something new, deciding where to
  start, adding a capability, restructuring, or any "how should I approach this?"
  (計画, 何から, どう進める, 設計, 追加, 作り直し, plan, approach, where to start,
  restructure, migrate). Investigate first, confirm the real goal (don't assume),
  co-design one decision at a time with tradeoffs + a recommendation, then proceed in
  small reversible verified steps. Do NOT use for small, well-specified single-step tasks.
---

<Goal>

Handle non-trivial or ambiguous work through investigation, clarification,
co-design, small reversible steps, and verification. Bias toward the user
understanding and owning the result, not toward rushing into edits.

</Goal>

<Scope>
<UseWhen>

- Open-ended, ambiguous, or multi-step asks: "plan X", "where do I start with
  X", "I want to do X", "add X here", or "how should I approach X".
- The right move is not obvious, or the goal could be read several ways.
- The task involves planning something new, adding a capability, deciding where
  to start, restructuring, or migration.

</UseWhen>

<DoNotUseWhen>

- Small, well-specified, single-step tasks. Do not add ceremony to simple work.

</DoNotUseWhen>
</Scope>

<Principles>

- Investigate before asserting: understand the context before proposing.
- Do not assume intent: confirm the real goal and mirror it back.
- One decision at a time: give options, tradeoffs, and a recommendation; the
  user decides.
- Reversibility and checkpoints: move in small steps, verify as you go, and
  pause before heavy or irreversible work.
- Legible and owned: track work with todos, narrate decisions when useful, and
  summarize sensitive data instead of pasting raw secrets or PII.

</Principles>

<Steps>

1. Understand the context. Inspect relevant code, files, history, the message,
   and the surrounding system before answering.
2. Clarify the real goal. Identify what outcome the user actually wants and why.
   Surface ambiguity and confirm instead of designing from assumptions. If the
   user cannot see the details, describe the big picture in their terms.
3. Co-design top-down, one decision at a time. Move from goal to shape to
   specifics. For each decision, present options, tradeoffs, and a recommended
   default.
4. Align on a plan. Synthesize decisions into a concise plan and confirm before
   heavy or irreversible work.
5. Proceed in small, reversible, verified steps. Take the smallest useful
   increment, check it, report, and continue. Keep recovery points and re-confirm
   before irreversible moves.
6. Close the loop. Summarize what changed, what is left, and hand control back.

</Steps>

<ScenarioPlaybooks>

Load the matching reference when the task fits:

- Rebuild, restructure, or schema/data migration: `references/rebuild-migration.md`
- Add a feature to an existing system: `references/new-feature.md`
- Start something from scratch: `references/new-project.md`

</ScenarioPlaybooks>

<AntiPatterns>

- Do not skip investigation and assert a plan from vibes.
- Do not assume the user's intent when the request can be read multiple ways.
- Do not present many decisions at once when one decision would unblock progress.
- Do not make irreversible or heavy changes without an explicit checkpoint.

</AntiPatterns>
