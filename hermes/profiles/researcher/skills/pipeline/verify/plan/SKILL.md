---
name: plan-verify
description: >-
  Verify, Plan stage: fix the exact claims to check, preserved byte-for-byte,
  with source requirements, closure and the durable ledger destination, and
  obtain the client's agreement. No gathering; not an open investigation,
  option comparison or consumer directives.
version: 1.0.0
author: CraftSamo
license: MIT
compatibility: Requires Hermes Agent and the parent researcher-pipeline kernel.
metadata:
  hermes:
    category: pipeline
    tags: [research, verify, plan]
---

<ReadBeforeWork>

Load `skill_view(name="researcher-pipeline")` first, including on direct entry;
its `<Plan>` section is the stage this entry specializes. On every inbound
turn/completion and before a midturn mode, stage or scope change, reselect the
mode and stage and load this entry with
`skill_view(name="plan-verify")`. Reuse only full bodies in
current context, never a past load, preload or summary.

Plan uses supplied material only, so no gathering reference is needed here.
A technic the brief names or [Capabilities](../../references/capabilities.md)
matches is loaded too with `skill_view(name="<technic>")`; it adds to this
mode and never replaces it.
If `skill_view` returns unchanged with a missing body or cannot supply it, use
`read_file` on canonical `${HERMES_SKILL_DIR}/../../SKILL.md` and
`${HERMES_SKILL_DIR}/SKILL.md`. Follow `next_offset` through actual
truncation; if recovery fails, stop the affected action. Never evade dedup
with alternate paths or artificial ranges. Selection/resume is not a new
grant, budget reset or permission to replay work.

</ReadBeforeWork>

# Verify: Plan

Use for specific external claims, cited sources or current specifications.
The output is claim-level verdicts, never a survey or an artifact-quality gate.
Corroboration and counterevidence matter more than breadth.

## Plan

1. Identify the claims from supplied text or an artifact inspected only for
   its factual claims and context. Preserve each source claim byte-for-byte in
   a verbatim code span/block, including punctuation and Unicode. Do not normalize
   apostrophes, quotes, dashes, spacing, numbers or capitalization.
2. Propose individually checkable subclaims for compound sentences, retaining
   the exact original plus a separate neutral investigation restatement and
   mapping. Agree the fixed claims list and source requirements before Build;
   an unavailable or moving list is a spec gap, not license to check a vibe.
3. Define recency/context, source coverage, exclusions, budget and closure:
   every input claim receives a confidence-rated `supported`, `refuted`,
   `partly true` or `unverifiable` verdict, evidence, counterevidence and gaps.
   Research stops at a stable verdict, not an exhaustive topic survey.
4. Name the consumer and output. If downstream QA consumes the results, settle
   the durable path and requested filename (default `claim-ledger.md`) for the
   complete verdict ledger, not just a one-line conclusion. Missing durable
   destination is a blocking input for that required delivery, never a guessed path.

Bring the proposal into the kernel's Plan template and agreement reply. State
explicitly that extracting claims from text/image/video/audio does not
authorize judging craft, rendering, mechanical specifications, completeness or
fit to the brief. If the claims list sprouts a topic survey, report the
granularity issue and propose a separate investigate unit for agreement.
No external verification occurs in Plan without an approved preliminary Build.

## Handoff

Plan ends at the client's agreement; a short approval advances this retained
Plan into [build-verify](../build/SKILL.md), not a restart. Keep
this mode for the unit; another kind of question is another agreed unit with
its own entries, never a silent switch.
