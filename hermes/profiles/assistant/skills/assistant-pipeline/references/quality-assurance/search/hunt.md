# QA contract — hunt

The orchestrating assistant performs a read-only inspection of the
hunt's source map, measured against the brief's done criteria.

## Scope
Inspect the complete source map, trail notes, and gaps as
findings-only verification. Never take additional hops yourself.

## Required inputs
The released brief (question, done criteria, scope exclusions,
primary-source requirement, budget); the source map with every
source marked primary/secondary and dated; trail notes; the named
gaps. For a card, the `goal_max_turns` budget and the card body's
done criteria.

## Checks
1. Done criteria: the map establishes what the brief asked — the
   origin located, the claim traced, every named sub-area covered —
   or the shortfall is named as a gap with the frontier that was
   exhausted; a budget-exhausted hunt with honest gaps can pass,
   a "done" verdict with unexamined sub-areas cannot.
2. Open the load-bearing sources: URLs resolve, quotes match,
   primary/secondary marking is right (a blog citing the paper is
   secondary; the paper is primary), dates carried.
3. Scope: exclusions honored — no hops into excluded languages,
   dates, or adjacent topics padding the map; the
   primary-source requirement met where the brief demanded it.
4. Contested claims: conflicting sources appear side by side, dated
   and marked, with the disagreement described — not adjudicated,
   not averaged.
5. Boundary: the map holds sources and trails, not conclusions —
   synthesis, verdicts, or "the debate summarized" are findings;
   open judgments live under `Open for researcher`.

## Not verified / never do
Missing trail notes, an unmarked source map, or done criteria the
map neither meets nor names a gap for means NOT verified — fail the
unit plainly or return it as feedback. Do not hop further, resolve
the contested claim, or narrow the question — a narrowed re-hunt is
a Plan decision.
