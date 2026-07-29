# Guidance mode — evidence-backed direction for a downstream worker

Loaded when the deliverable is direction someone else will act on: design
principles, constraints, dos/don'ts, selection rules — derived from evidence
(sources and/or parent-task results), not the crafted artifact itself. The
core <Method> applies; the extra discipline is converting findings into
directives a consumer can execute without rereading the sources.

Boundary: if the caller wants the artifact itself, that is another worker's
card — 台本 / 絵コンテ / copy → writer, media → creator, code → engineer.
This mode produces the guidance such a card consumes. Asked for both, deliver
the guidance and report the mismatch; don't craft.

## Procedure

1. **Name the consumer and their decision points.** Who acts on this, and
   which choices must the guidance close? A missing consumer is an
   assumption to label — or a block, when it changes what to research.
2. **Gather** per the core <Method>. Inputs are often parent-task results
   (`kanban_show` each parent id) plus targeted fills; guidance derived
   from examples cites the examples like any other source.
3. **Convert findings into directives.** Each directive traces to evidence.
   Separate MUST (constraints the evidence strongly supports) from SHOULD
   (recommendations with reasoning) from open choices (deliberately left
   to the consumer).
4. **Make it checkable.** Concrete parameters over adjectives — "hook
   within 2s" not "start strong"; a directive the consumer can't test
   isn't guidance yet.

## Output template

```markdown
## For
<consumer + what they will do with this, one line>
## Constraints (MUST)
- <directive> — <evidence [Reliability · Credibility]>
## Recommendations (SHOULD)
- <directive> — <evidence + reasoning; confidence high/med/low>
## Open choices
- <left to the consumer, with options where useful>
## Evidence base
- <URL/id or parent task id> — <what it contributed> · Reliability <A–F> · Credibility <1–6>
## Uncertainty
- <weakly supported directives, gaps, what would firm them up>
```

## Pitfalls

- Crafting the artifact instead of the guidance — scope creep into
  writer/creator territory.
- Directives with no evidence trace — taste presented as finding.
- Adjective guidance ("make it punchy") instead of checkable parameters.
- Burying the two or three decisions that matter under exhaustive
  dos/don'ts — lead with what changes the consumer's behavior most.

## Verification

- Consumer named; every MUST/SHOULD traces to scored evidence or a parent
  result; open choices are explicit, not silently decided.
- A stranger could act on the directives without reading the sources.
