---
name: approach-debugging
description: >-
  Use to fix a bug or incident systematically — reproduce, isolate, hypothesize,
  verify, fix, and guard against regression (バグ修正, デバッグ, インシデント,
  原因調査, バグの原因, bug, debug, incident, root cause, why is it broken). Find
  the cause; do not patch symptoms. Apply on top of the `approach` spine.
---

<Goal>

Resolve a defect or incident by finding and fixing the root cause, not the
symptom. Apply this on top of the `approach` spine (load it first if not
already in context): investigate → confirm the real goal → co-design one
decision at a time → proceed in small reversible verified steps.

</Goal>

<AntiPatterns>

- Do not apply a fix from a guess without reproducing the failure.
- Do not patch the symptom and move on; the bug will resurface elsewhere.
- Do not change behavior for unrelated reasons while debugging — keep the diff
  to the cause.
- Do not declare fixed without a regression test that would have caught it.

</AntiPatterns>

<Steps>

1. Reproduce: establish a reliable, minimal reproduction before changing
   anything. If it cannot be reproduced, gather logs/state and define what
   "fixed" will look like first.
2. Isolate: shrink the reproduction. If it worked before, treat it as a
   regression: bisect history or trace provenance to the introducing commit.
   Otherwise toggle code paths or reduce inputs until the triggering condition
   is as small as possible.
3. Hypothesize the cause: form one falsifiable hypothesis grounded in the
   observed evidence (not vibes). State what would prove it wrong.
4. Verify the hypothesis: confirm with a targeted check — a log, a probe, a
   failing test, or a minimal experiment. If it fails, discard and form a new
   hypothesis; do not accumulate guesses.
5. Fix the root cause: make the smallest change that removes the cause while
   preserving intended behavior. Explain how it maps to the verified cause.
6. Guard against regression: add a test that fails without the fix and passes
   with it. Run the project's build/lint/test checks.
7. Close the loop: confirm the original reproduction no longer fails, check
   adjacent behavior for regressions, and summarize the cause and the fix.

</Steps>

<Gates>

- [ ] Reliable reproduction (or a precise definition of the failing state).
- [ ] One verified root-cause hypothesis; guesses discarded when falsified.
- [ ] Fix targets the cause, not the symptom; diff stays scoped.
- [ ] Regression test added that would have caught the bug; project checks pass.
- [ ] Original failure gone; no adjacent regressions.

</Gates>
