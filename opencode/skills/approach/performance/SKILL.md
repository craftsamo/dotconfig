---
name: approach-performance
description: >-
  Use to resolve a performance problem — measure a baseline, locate the
  bottleneck, improve, and re-measure (パフォーマンス改善, 高速化, ボトルネック,
  遅い, 重い, performance, optimize, speed up, slow, latency, throughput).
  Measurement-driven; avoid premature optimization. Apply on top of the
  `approach` spine.
---

<Goal>

Resolve a concrete performance problem with measurement, not guesswork. Apply
this on top of the `approach` spine (load it first if not already in
context): investigate → confirm the real goal → co-design one decision at a
time → proceed in small reversible verified steps.

</Goal>

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
   where they feel like they go. Rank candidates by impact.
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
