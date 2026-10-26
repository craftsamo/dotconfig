---
name: build-advise
description: >-
  Advise, Build stage: gather the agreed evidence fills, convert findings into
  MUST/SHOULD directives traced to scored evidence, self-check and deliver
  the guidance. Requires the client's agreement from Plan; not the consumer's
  artifact or a verdict on it.
version: 1.0.0
author: CraftSamo
license: MIT
compatibility: Requires Hermes Agent and the parent researcher-pipeline kernel.
metadata:
  hermes:
    category: pipeline
    tags: [research, advise, build]
---

<ReadBeforeWork>

Load `skill_view(name="researcher-pipeline")` first, including on direct entry;
its `<Build>` section is the stage this entry specializes. On every inbound
turn/completion and before a midturn mode, stage or scope change, reselect the
mode and stage and load this entry with
`skill_view(name="build-advise")`. Reuse only full bodies in
current context, never a past load, preload or summary.

Gathering beyond a few direct lookups requires
`skill_view(name="researcher-pipeline", file_path="references/gather.md")`:
[Gather](../../references/gather.md). Reading strategy does not authorize searches.
Evidence from a chain or from Hyperliquid also requires its shared reference:
[EVM](../../references/platforms/evm.md), [Solana](../../references/platforms/solana.md) or
[Hyperliquid](../../references/platforms/hyperliquid.md).
A technic the brief names or [Capabilities](../../references/capabilities.md)
matches is loaded too with `skill_view(name="<technic>")`; it adds to this mode
and never replaces it.
If `skill_view` returns unchanged with a missing body or cannot supply it, use
`read_file` on canonical `${HERMES_SKILL_DIR}/../../SKILL.md`,
`${HERMES_SKILL_DIR}/SKILL.md`, `${HERMES_SKILL_DIR}/../../references/gather.md`
and `${HERMES_SKILL_DIR}/../../references/platforms/<chain>.md` as applicable.
Follow `next_offset` through actual truncation; if recovery fails, stop the
affected action. Never evade dedup with alternate paths or artificial ranges.
Selection/resume is not a new grant, budget reset or permission to replay work.

</ReadBeforeWork>

# Advise: Build

Use for principles, constraints, dos/don'ts and selection rules someone will
act on. The result is guidance derived from sources and/or parent-task results,
directives the agreed consumer can act on without rereading sources; it is not
production of the artifact they will make.

## Build

1. Restate the agreed consumer and decision points. Missing consumer information
   that changes research returns to Plan; harmless assumptions stay labeled.
2. Gather using the kernel's Build Method. Prior results/parent task IDs
   supplied by the brief are source inputs, not fresh authorization. Add only
   agreed targeted fills; cite examples like any other source and score their
   trust.
3. Convert findings into directives, each traced to evidence. Separate MUST
   (constraints strongly supported by evidence), SHOULD (recommendations with
   reasoning) and open choices deliberately retained by the consumer.
4. Make each directive checkable: concrete parameters over adjectives, such as
   "hook within 2s" rather than "start strong", only when that parameter is
   actually evidenced and appropriate to the agreed context. Do not invent a
   universal rule from an example or present taste as a finding.
5. Lead with the two or three decisions that most change consumer behavior,
   not exhaustive dos/don'ts. Close each agreed point with a traced directive
   or explicitly leave it open; never decide a consumer-owned choice silently.

## Output template

```markdown
## For
<consumer + what they will do with this, one line>
## Constraints (MUST)
- <directive> - <evidence [Reliability; Credibility]>
## Recommendations (SHOULD)
- <directive> - <evidence + reasoning; confidence high/med/low>
## Open choices
- <left to consumer, with options where useful>
## Evidence base
- <URL/id or parent task id> - <contribution>; Reliability <A-F>; Credibility <1-6>
## Uncertainty
- <weakly supported directives, gaps, what would firm them up>
```

If asked to craft the artifact too, deliver only agreed guidance and report
the mismatch; scripts/storyboards/copy, media and code stay outside this role.
Write requested artifacts to the durable path, name them in the reply and check
the directives and evidence base against Verification below. Unsupported taste
and uncheckable adjectives are not evidence-backed guidance.

## Verification

Check the actual directives against the agreed consumer, decision points and
evidence base. Do not judge or produce the downstream artifact.

- Consumer and intended use are named; every agreed decision point closes with
  a traced directive or is explicitly open, not silently decided or omitted.
- Every MUST/SHOULD traces to scored evidence or a parent result. MUST reflects
  a strongly supported constraint; SHOULD has evidence, reasoning and confidence.
  Taste is not presented as a finding, nor an example generalized without support.
- For, Constraints (MUST), Recommendations (SHOULD), Open choices, Evidence base
  and Uncertainty are present. The evidence base names URLs/IDs or parent task
  IDs, contributions and reliability/credibility; examples are cited as sources.
- A stranger could act on the directives without rereading sources: parameters
  are concrete and checkable, not adjectives such as "make it punchy". Claimed
  parameters are grounded, not invented merely to make a directive testable.
- The two or three behavior-changing decisions lead rather than being buried
  in exhaustive dos/don'ts. Consumer-owned open choices remain explicit.
- Weak support, gaps and what would firm them up remain visible; prior results
  were not treated as new authorization. Requested durable files are named.
- The result is guidance, not scripts/storyboards/copy, media or code, and not
  a quality verdict about such an artifact.

Return checked/unmet/unknown conditions, not a numeric self-score. An in-scope
trace or wording correction stays in Build within remaining budget; a new
consumer decision, evidence-base expansion or additional unit requires
[plan-advise](../plan/SKILL.md) and agreement. The caller still
owns final acceptance and production choices.

## Handoff

Build ends, in the same turn, with the self-check against this entry's
Verification, and the reply carries what it found unmet or unknown; the
kernel's Build section says how the findings are delivered. Keep this mode for
the unit; another kind of question is another agreed unit with its own
entries, never a silent switch.
