---
name: approach
description: >-
  Use for non-trivial or ambiguous work — planning something new, deciding where to
  start, adding a capability, restructuring, or any "how should I approach this?"
  (計画, 何から, どう進める, 設計, 追加, 作り直し, plan, approach, where to start,
  restructure, migrate). Investigate first, confirm the real goal (don't assume),
  co-design one decision at a time with tradeoffs + a recommendation, then proceed in
  small reversible verified steps. Do NOT use for small, well-specified single-step tasks.
version: 0.1.0
author: CraftSamo
metadata:
  hermes:
    tags: [planning, approach, rebuild, migration, workflow]
    category: plan
---

# Approach

A disciplined, collaborative way to take on **non-trivial or ambiguous work** —
planning something new, adding a capability, deciding where to start, restructuring,
or any "how should I go about this?". Bias toward the user **understanding and owning**
the result, and toward **safe, reversible progress** over rushing.

## When to use
- Open-ended / ambiguous / multi-step asks: "plan X", "where do I start with X",
  "I want to do X", "add X here", "how should I approach X".
- The right move isn't obvious, or the goal could be read several ways.

## When NOT to use
- Small, well-specified, single-step tasks. Don't add ceremony to simple work.

## Principles
- **Investigate before asserting** — understand the context before proposing.
- **Don't assume intent** — confirm the real goal; mirror it back.
- **One decision at a time** — options + tradeoffs + a recommendation; the user decides.
- **Reversibility & checkpoints** — small steps; verify as you go; pause before anything
  heavy or irreversible.
- **Legible & owned** — track with todos, narrate decisions; summarize sensitive data,
  never paste raw secrets/PII.

## The spine
1. **Understand the context.** Inspect what's relevant (code, files, history, the message,
   the surrounding system) before answering.
2. **Clarify the real goal.** What outcome does the user actually want, and why? Surface
   ambiguity and confirm — don't design from assumptions. If they can't see details,
   describe the big picture in their terms.
3. **Co-design top-down, one decision at a time.** Abstract → concrete (goal → shape →
   specifics). Each step: options + tradeoffs + a recommended default; the user chooses.
4. **Align on a plan.** Synthesize decisions into a concise plan; confirm before heavy or
   irreversible work.
5. **Proceed in small, reversible, verified steps.** Smallest useful increment → check →
   report → continue. Keep recovery points; re-confirm before irreversible moves.
6. **Close the loop.** Summarize what changed, what's left, and hand control back.

## Scenario playbooks
Load the matching reference when the task fits:
- Rebuild / restructure / schema-or-data migration → `references/rebuild-migration.md`
- Add a feature to an existing system → `references/new-feature.md`
- Start something from scratch → `references/new-project.md`
- Draft a reply to a received message → `references/message-reply.md`
