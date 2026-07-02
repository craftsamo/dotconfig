---
name: approach-refactor
description: >-
  Use when improving structure without changing behavior — refactor, reorganize,
  clean up, extract, rename, or simplify under a test safety net in small
  behavior-preserving steps (リファクタリング, 整理, リファクタ, refactor,
  restructure code, clean up, extract method, rename). Behavior must stay
  identical. For wholesale rebuilds or data migration, use
  `approach-rebuild-migration`. Apply on top of the `approach` spine.
---

<Goal>

Improve the structure of working code without changing its behavior. If the
system or its data is being replaced or moved wholesale, use
`approach-rebuild-migration` instead. Apply this on top of the `approach`
spine (load it first if not already in context): investigate → confirm the
real goal → co-design one decision at a time → proceed in small reversible
verified steps.

</Goal>

<AntiPatterns>

- Do not refactor without a behavior-asserting safety net (tests or a spec).
- Do not mix behavior changes into a refactor — keep the two in separate steps
  or separate commits.
- Do not attempt a large restructure in one move; break it into verifiable
  steps.
- Do not rename or move public API without checking call sites and consumers.

</AntiPatterns>

<Steps>

1. Secure a safety net: confirm existing tests cover the behavior you will
   touch. If coverage is thin, characterize the current behavior with tests
   first — the refactor must keep them green.
2. Define the target structure: name the smell and the intended shape (extract,
   inline, rename, move, simplify). Keep the goal structural, not behavioral.
3. Plan small, behavior-preserving moves: decompose into steps where each
   leaves the system working and the tests green.
4. Execute one move at a time: make the change, run the safety net, commit
   (or checkpoint) before the next move.
5. Verify behavior is identical: run the full build/lint/test suite; confirm
   no public behavior, API, or output changed beyond intent.
6. Close the loop: summarize what moved, why, and what follow-up refactors (if
   any) remain.

</Steps>

<Gates>

- [ ] Behavior-asserting safety net in place before any structural change.
- [ ] Goal is structural only; no behavior change mixed in.
- [ ] Each move left the tests green and the system working.
- [ ] Full build/lint/test suite passes; public behavior/API unchanged.

</Gates>
