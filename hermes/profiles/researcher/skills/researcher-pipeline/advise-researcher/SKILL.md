---
name: advise-researcher
description: >-
  Advise a named consumer with evidence-backed directives: agree the decision
  points, trace each MUST/SHOULD to scored evidence, self-check and deliver
  guidance. Not the consumer's artifact or a verdict on it.
version: 1.0.0
author: CraftSamo
license: MIT
compatibility: Requires Hermes Agent and the parent researcher-pipeline kernel.
metadata:
  hermes:
    category: researcher-pipeline
    tags: [research, advise]
---

<ReadBeforeWork>

Load `skill_view(name="researcher-pipeline")` first, including on direct entry,
before any stage. On every inbound turn/completion and before a midturn mode,
stage or scope change, reselect the mode and load this entry with
`skill_view(name="advise-researcher")` and the current stage's shared reference with
`skill_view(name="researcher-pipeline", file_path="references/<stage>.md")`:
[Plan](../references/plan.md) or [Build](../references/build.md). Reuse only full bodies in current context, never a
past load, preload or summary.

Gathering beyond a few direct lookups requires
`skill_view(name="researcher-pipeline", file_path="references/gather.md")`:
[Gather](../references/gather.md). Reading strategy does not authorize searches.
Evidence from a chain also requires that chain's shared reference:
[EVM](../references/platforms/evm.md) or [Solana](../references/platforms/solana.md).
If `skill_view` returns unchanged with a missing body or cannot supply it, use
`read_file` on canonical `${HERMES_SKILL_DIR}/../SKILL.md`,
`${HERMES_SKILL_DIR}/SKILL.md`, `${HERMES_SKILL_DIR}/../references/<stage>.md`,
`${HERMES_SKILL_DIR}/../references/gather.md` and
`${HERMES_SKILL_DIR}/../references/platforms/<chain>.md` as applicable. Follow
`next_offset` through actual truncation; if recovery fails, stop the affected
action. Never evade dedup with alternate paths or artificial ranges.
Selection/resume is not a new grant, budget reset or permission to replay work.

</ReadBeforeWork>

# Advise

Use for principles, constraints, dos/don'ts and selection rules someone will
act on. The result is guidance derived from sources and/or parent-task results,
directives the agreed consumer can act on without rereading sources; it is not
production of the artifact they will make.

## Plan

1. Name the consumer and the decision points the guidance must close. Propose
   them from the client's purpose rather than demanding a prebuilt list. A missing
   consumer is a spec gap when it changes what to research; otherwise label the
   harmless assumption for agreement.
2. Identify the supplied evidence base, prior task IDs/results and examples.
   These are source inputs, not authorization for wider inquiry. Propose targeted
   evidence fills, recency needs and the depth/budget needed for this consumer.
3. Agree done criteria: each decision point closes with a traced, checkable
   directive or is explicitly left open. Plan MUST constraints, SHOULD
   recommendations and consumer-owned open choices as separate output categories;
   do not predeclare unsupported preferences as constraints.
4. State scope/exclusions, durable outputs if requested and review material.
   Lead with the two or three decisions that would most change the consumer's
   behavior, not an exhaustive list of dos/don'ts.

If asked for both guidance and the artifact, propose the guidance within this
role and report the production mismatch to caller. Scripts/storyboards/copy,
media and code remain other roles' production, not assignments made here.
Use supplied material in Plan; get agreement before any external evidence fill.

## Build

1. Restate the agreed consumer and decision points. Missing consumer information
   that changes research returns to Plan; harmless assumptions stay labeled.
2. Gather using Build's Method. Prior results/parent task IDs supplied by the
   brief are source inputs, not fresh authorization. Add only agreed targeted
   fills; cite examples like any other source and score their trust.
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
trace or wording correction returns to Build within remaining budget; a new
consumer decision, evidence-base expansion or additional unit requires Plan
and agreement. The caller still owns final acceptance and production choices.

## Handoff

Plan ends at the client's agreement. Build ends, in the same turn, with the
self-check against this entry's Verification, and the reply carries what it
found unmet or unknown. Each stage's own Handoff in its shared reference says
what follows. Keep this mode for the unit; another kind of question is another
agreed unit with its own mode entry, never a silent switch.
