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
- Legible and owned: track work with todos (or the "Roadmap" board for durable,
  cross-session work — see `approach-github-projects`), narrate decisions when useful, and
  summarize sensitive data instead of pasting raw secrets or PII.

</Principles>

<Steps>

1. Understand the context. Inspect relevant code, files, history, the message,
   and the surrounding system before answering.
2. Clarify the real goal. Identify what outcome the user actually wants and why.
   Surface ambiguity and confirm instead of designing from assumptions. If the
   user cannot see the details, describe the big picture in their terms.
3. Classify the scenario and load its playbook. Once the goal is confirmed,
   match the work against <ScenarioPlaybooks> and load the matching skill(s)
   before designing. Re-classify when investigation changes the work type
   (e.g., a bug turns out to be a design flaw → rebuild). If the work spans
   scenarios, sequence them (e.g., refactor first, then add the feature) and
   load each playbook at its phase.
4. Co-design top-down, one decision at a time. Move from goal to shape to
   specifics. For each decision, present options, tradeoffs, and a recommended
   default.
5. Align on a plan. Synthesize decisions into a concise plan and confirm before
   heavy or irreversible work.
6. Proceed in small, reversible, verified steps. Take the smallest useful
   increment, check it, report, and continue. Keep recovery points and re-confirm
   before irreversible moves.
7. Close the loop. Summarize what changed, what is left, and hand control back.

</Steps>

<ScenarioPlaybooks>

Load the matching scenario skill when the task fits (each applies on top of
this spine):

- Add a feature to an existing system → `approach-new-feature`
- Start something from scratch → `approach-new-project`
- Rebuild, restructure, or schema/data migration → `approach-rebuild-migration`
- Fix a bug or incident systematically → `approach-debugging`
- Improve structure without changing behavior → `approach-refactor`
- Resolve a performance problem → `approach-performance`

Refactor vs rebuild: behavior stays identical and the change is incremental →
`approach-refactor`; the system or its data is replaced or moved wholesale →
`approach-rebuild-migration`.

Cross-cutting (not a work type; layer on any of the above):

- Persist and track a durable plan on the board → `approach-github-projects`

</ScenarioPlaybooks>

<AntiPatterns>

- Do not skip investigation and assert a plan from vibes.
- Do not assume the user's intent when the request can be read multiple ways.
- Do not present many decisions at once when one decision would unblock progress.
- Do not make irreversible or heavy changes without an explicit checkpoint.
- Do not keep working from the spine alone when the task matches a scenario
  playbook — load it.

</AntiPatterns>
