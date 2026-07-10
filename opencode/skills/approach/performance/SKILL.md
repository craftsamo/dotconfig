---
name: approach-performance
description: >-
  Use to resolve a performance problem — measure a baseline, locate the
  bottleneck, improve, and re-measure (パフォーマンス改善, 高速化, ボトルネック,
  遅い, 重い, performance, optimize, speed up, slow, latency, throughput).
  Measurement-driven; avoid premature optimization.
---

<Goal>

Resolve a concrete performance problem with measurement, not guesswork.

</Goal>

<Method>

Non-trivial work runs through this spine; do not jump straight to edits:

1. Investigate before asserting — read the relevant code, files, and history
   first.
2. Confirm the real goal — mirror it back instead of designing from
   assumptions. Do not ask what investigation can answer; take the recommended
   default on low-risk details and report it.
3. Co-design one decision at a time — widen to the realistic candidates (not
   just two straw options), present tradeoffs with a recommendation, and let
   the user decide.
4. Align on a concise plan before heavy or irreversible work. Persist durable
   or cross-session plans via `approach-github-projects`, not local TODO files.
5. Execute in small reversible verified steps; checkpoint before anything
   irreversible.
6. Close the loop — summarize what changed and what remains.

</Method>

<AntiPatterns>

- Do not optimize without a target metric and a failing baseline.
- Do not guess the bottleneck; measure before changing code.
- Do not trade correctness or readability for speed without confirming the gain
  is real and worth it.
- Do not declare faster based on a single run; re-measure and watch for
  variance and regressions elsewhere.

</AntiPatterns>

<Steps>

1. Define the target: what metric matters (latency, throughput, memory, p99),
   what the current number is, and what "good enough" is. Confirm the user's
   real constraint before optimizing.
2. Measure a baseline: capture the current metric under realistic conditions
   (representative input/load, warm caches, repeated runs). Record how you
   measured so it is repeatable.
3. Locate the bottleneck: profile to find where time/resources actually go, not
   where they feel like they go. Rank candidates by impact. This read-only
   diagnosis can be delegated to the `debugger` subagent (via the task tool)
   when the profiling is involved or the cause is disputed.
4. Form one hypothesis and improve: pick the highest-impact bottleneck, make
   the smallest change aimed at it, and keep behavior correct. Prefer doing
   less work (cache, batch, skip, precompute) and algorithmic wins over
   micro-optimizations.
5. Re-measure: compare against the baseline with the same method. Confirm the
   gain is real, not noise, and that correctness is unchanged (tests still
   pass).
6. Iterate or stop: if the target is met, stop. If not, repeat from step 3 on
   the next bottleneck. Avoid gold-plating past the agreed target.
7. Close the loop: report before/after numbers, the method, and any tradeoffs
   (complexity, memory, readability) accepted.

</Steps>

<Gates>

- [ ] Target metric and threshold agreed before optimizing.
- [ ] Repeatable baseline captured under realistic conditions.
- [ ] Bottleneck chosen by measurement, ranked by impact.
- [ ] Improvement re-measured against the baseline; gain is real, not noise.
- [ ] Correctness unchanged (tests pass); tradeoffs made explicit.

</Gates>
