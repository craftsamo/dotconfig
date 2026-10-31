# Assistant calls Researcher directly

Status: in force
Owner doc: docs/profiles/specialist-calls.md, docs/topology.md

## Decision

`assistant` may call `researcher` directly via `specialist_call` for standalone
research deliverables (evidence packs, tradeoff matrices, fact checks, guidance).
The existing path routing research through a consuming primary (`creator`,
`marketer`) remains in force when research grounds their creative or marketing work.

Short bounded inquiries use Researcher's existing A2A peer endpoint (:9906);
planning dialogue and metered work use resident sessions.

## Why

- Standalone depth research questions previously had to be routed through
  `creator` or `marketer` even when no media production or marketing strategy was
  involved. This added an extra agent hop, duplicate proposal relaying, and
  artificial primary mediation.
- `researcher` already listens on localhost A2A port 9906 and serves resident
  sessions. Opening `TARGETS["assistant"]` and Assistant's `resident_targets` to
  include `researcher` completes direct specialist coverage alongside Searcher,
  Writer, and hands.
- When research grounds media copy or marketing campaigns, routing through
  `creator` or `marketer` is preserved so the consuming primary owns the
  baseline, verifies evidence against the artifact, and gates the deliverable.

## Do not

- Remove `creator` or `marketer` access to `researcher`: they continue to call
  Researcher when grounding their own deliverables.
- Route research that grounds media or marketing directly from Assistant,
  bypassing the consuming primary's ownership of the baseline.
