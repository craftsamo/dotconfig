# Marketing — the improvement loop

Shipping without learning is spend without compounding. The loop
turns measurements into at most a few adjudicated changes, on three
rhythms. You run it; the marketer collects and drafts; the user
adjudicates anything material. Its state lives in the project's
marketing record (`../../plan/marketing/marketing-state.md`:
`kpi.md`, `experiments.md`, `decisions.md`, `non-goals.md`).

## Daily — guardrails, not judgment

Collection and threshold-watching are green automation: metrics
land, and a breach of an approved tolerance (complaint spike,
delivery failure, anomalous drop) stops the affected queue and
notifies. No daily "optimization" — daily data is for stopping harm,
not steering.

## Weekly — the improvement session

One marketer turn + your adjudication, eight steps:

1. **Health first** — ledgers current, connections alive, metrics
   flowing; broken instrumentation is the week's finding, ahead of
   any interpretation.
2. **Adjudicate finished experiments** — adopt, revert, or a
   justified extension; nothing stays "running" by default.
3. **Detect** anomalies and gains against comparable baselines;
   insufficient samples stay under observation, unjudged.
4. **Draft proposals — at most three**, each evidence-linked:
   hypothesis, target metric, confidence, observation window,
   tolerance limit. Ten proposals produce zero actions; **zero
   proposals is a valid week** ("no change supported" is a real
   result).
5. **Decide** — you triage; material calls (spend, offer, channel,
   anything near the red floor) go to the user, presented without
   pressure.
6. **Register** approved experiments: lock baselines before the
   change ships; approved external changes enter the queue as
   approved inventory (green dispatch).
7. **Log every decision** — including rejections and their reasons —
   append-only in `decisions.md`.
8. **Digest** — a short sourced summary to the user: results,
   experiment states, decisions, plus your own observation line.

## Monthly — promotion and reflux

- Promote a pattern into standing practice only after it reproduced
  **twice in distinct contexts**; one win is an anecdote.
- Reverted experiments flow into `non-goals.md` with their reason —
  the loop's failures become the plan's guardrails.
- Audit the loop itself: are guardrails firing, are proposals
  landing, is the record being read? A loop nobody consults is
  retired, not maintained.

## Pitfalls

- Interpreting daily noise; weekly is the judgment rhythm.
- Proposals without a named metric, window, and tolerance.
- Adopting a one-time win; skipping the reproduction bar.
- Deciding user-level calls (spend, pricing implications) inside
  the loop because they arrived dressed as "optimization".
