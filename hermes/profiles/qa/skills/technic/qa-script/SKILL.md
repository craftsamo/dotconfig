---
name: qa-script
description: Read-only QA inspection of an immutable production script.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, technic, script, storyboard, screenplay, continuity]
    category: technic
---

<Scope>
Inspect the complete attached Writer script/storyboard/screenplay as a
producer-facing contract. Never renumber units, rewrite dialogue, or turn
instructions into deliverable text.
</Scope>

<RequiredEvidence>
The immutable complete script and digest, unit type/count/order, required per-unit
fields, verbatim text ledger, character/duration/count budgets, production
constraints, Japanese norms for Japanese verbatim text, and Researcher evidence
for factual claims or quotations.
</RequiredEvidence>

<ChecksProcedure>
1. Hash and read every unit. Check continuous numbering, required fields, unit
   roles, and count/order against the brief without trusting a summary.
2. Separate verbatim dialogue/captions/narration from producer instructions;
   check exact text, character budgets, beats/duration, and language norms.
3. Check production feasibility, scene/character/prop continuity, and that the
   script works in order without hidden fields. Trace factual claims to
   Researcher evidence.
4. Return unit/field-specific findings only to `qa-pipeline` for rollup.
</ChecksProcedure>

<FailOrCantVerify>
Incomplete attachment, missing unit contract, ambiguous verbatim boundary,
unmeasurable budget, or missing Researcher evidence is `can't_verify`. Do not
renumber, rewrite, fill fields, research facts, or publish the script.
</FailOrCantVerify>
