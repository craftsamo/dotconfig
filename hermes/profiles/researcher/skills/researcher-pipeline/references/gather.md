# Gather engine — retrieval strategy and fan-out

Load when gathering goes beyond a few direct lookups: choosing between your
own tools, searcher delegation, and technic playbooks — or when part of the
task belongs on the board. The kernel's <SourceEvaluation> and
<CitationRules> govern everything gathered here.

## Search route

Breadth, in order; trace every claim to its original context:

1. Primary / official (docs, specs, papers, filings, source code) — reliability A
2. Reputable secondary (established docs/news, recognized experts) — B
3. General web — C/D; investigate the source (lateral read) before trusting
4. X / social — real-time / primary-witness value, but C–F; corroborate, never sole support
5. Reddit / forums / blogs — lived experience; D by default

Virality != truth. A high search rank is not reliability.

## Who gathers what

- **Your own web/vision/video/file tools** — depth reads and source
  inspection. Media tools may extract a final artifact's exact factual claim
  and context; artifact-quality inspection belongs to QA. Extract directly,
  never from memory of a snippet.
- **`delegate_task`** — quick parallel lookups you can wait out inside one
  run (a handful of URL fetches, a definition check).
- **Searcher child cards** — breadth hunts and link harvesting that would
  eat your runtime. Always pin `skills: ["searcher-pipeline"]`; for
  exhaustive multi-hop hunts add `goal_mode: true`. Searcher hands back
  links + snippets; the trust scoring stays yours.
- **Learned playbooks on this profile** may inform retrieval when available,
  but are not stable dispatch identities and are never pinned by the
  orchestrator. Load one internally only when its retrieval method fits.

## Fan-out — manifest handoff only

Researcher does not register cards or create child work. For heavy breadth that
fits the approved `fan_out_policy`, prepare exactly one attached `fan-out.yaml`
with the canonical fields `origin_task_id`, `checkpoint_key`, `children`,
`continuation`, and `attachments`. Each child is a self-contained `searcher`
TaskSpec in `Mode: retrieve`, and the continuation is a self-contained
Researcher TaskSpec in `Mode: analyze` with the same deliverable, consumer,
claims, and attachment purposes. Each attachment entry has `name`, `sha256`,
`purpose`, and `source_task_id`; probe its digest before handoff.

After attaching the manifest, write `STATE:` with the checkpoint and current
findings, then block with `FAN_OUT_READY:`. This is a terminal block, not a
completion: return no completion envelope and no result summary. The Assistant
validates the policy, registers eligible Searcher roots, and preserves dependent
children plus the same Researcher continuation as pending specs. It registers
each only after direct parents pass completion admission.

On respawn, read the complete thread. If `DECISION(FAN_OUT_READY):` names the
live children, pending keys, registration anchor, and digest, verify the checkpoint and retire the
origin. Do not resume or re-gather its result; complete the obsolete origin
with exactly one `metadata.completion` whose status is `superseded`. The
eventual continuation alone owns the final analysis and its normal completion.

For quick parallel lookups that fit the current run, use `delegate_task` and
wait for the results. If the approved policy is missing or the requested fan-out
exceeds its assignees, child count, purpose, cost cap, or grant ceiling, block on
the Researcher card rather than widening the manifest.
