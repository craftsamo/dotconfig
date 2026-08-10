---
name: brainstorm
description: >-
  Assistant-owned desk for iterative brainstorming that stays inline: establish the question,
  generate meaningfully different options, challenge and combine them, converge on decisions,
  and externalize durable outcomes before the session is reset. Use in the pinned Brainstorm
  Telegram topic; execution work spins into a new topic.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [assistant, desk, brainstorm, ideation, decisions, inline]
    category: desks
---

<Goal>

Provide a reusable thinking surface where conversation can be reset freely because settled
decisions and useful artifacts are externalized instead of relying on chat continuity.

</Goal>

<OrchestrationOverride>

The chat-wide `assistant-pipeline` skill remains active, but this desk narrows its routing:

- Brainstorming in this topic fixes the execution shape to **inline**.
- If an idea needs a `single`, `chain`, or `planned` Worker shape, stop here.
  Preparing the <SpinOut> handoff is the inline result.
- Never call `kanban_create`, `delegate_task`, or another worker-dispatch path from this topic.

</OrchestrationOverride>

<Scope>
<UseWhen>

- Generate, compare, combine, or refine ideas.
- Explore a problem before choosing whether it deserves a project or execution topic.
- Turn a vague thought into a decision, brief, outline, or experiment proposal.

</UseWhen>

<DoNotUseWhen>

- The user is already asking for implementation, publication, media generation, or sustained
  research. Those belong in a new topic with chat-wide assistant-pipeline.
- The request has a known answer and only needs a lookup; answer inline without performing a
  theatrical brainstorming process.
- Creating or dispatching a kanban card inside this pinned topic.

</DoNotUseWhen>
</Scope>

<Method>

Adapt the depth to the request; do not force every stage when a shorter path is enough.

1. **Frame** — state the question, desired outcome, constraints, and what would make an idea
   useful. Ask at most one blocking question; otherwise make a stated assumption.
2. **Diverge** — produce a small set of genuinely different directions. Vary the underlying
   mechanism, not just names or wording.
3. **Stress** — surface the strongest tradeoff, failure mode, and hidden dependency for each
   serious direction. Do not flatten uncertain ideas into fake confidence.
4. **Synthesize** — combine compatible strengths, discard dominated options, and identify the
   unresolved decision that actually matters.
5. **Converge** — recommend a direction or a cheap experiment, with a brief rationale. Preserve
   minority options when the evidence is genuinely balanced.

Maintain a compact decision ledger during longer sessions: settled decisions, what they
constrain, open questions, and rejected alternatives with reasons. Never re-ask a settled
decision unless new evidence explicitly invalidates it.

</Method>

<Externalize>

Before `/new`, or once the discussion produces a reusable outcome, offer the smallest durable
artifact that fits:

- Existing project: save tentative supporting notes under its `.agent/notes/`; promote a
  canonical outcome to the relevant `docs/` or `data/` after reading local `AGENTS.md`.
- New project candidate: register only when the user chooses to create it; use the Projects desk
  for `pj`/scaffold operations.
- Cross-cutting idea: save a concise note under `~/Workspaces/.notes/` with decisions, reasons,
  open questions, and next experiment.
- No durable value: leave it in chat; do not manufacture documentation.

Read `~/Workspaces/AGENTS.md` and the closest nested `AGENTS.md` before writing. Personal,
financial, contact, and semi-private project material stays in its owning Personal or project
location; summarize without raw values or PII. When sensitivity or ownership is unclear, get
explicit approval before saving anything under cross-cutting `.notes/`.

Never claim an outcome was saved unless the file or registry operation actually completed.

</Externalize>

<SpinOut>

When an idea becomes execution work, stop before dispatch. Produce a compact handoff containing
the goal, selected direction, constraints, acceptance signal, relevant workspace path, and open
risks. Ask the user to open a new Telegram topic for execution; the new topic inherits the
chat-wide `assistant-pipeline` skill and owns any kanban work.

</SpinOut>

<Done>

End with the current recommendation, the unresolved set, and where any durable artifact was
stored. The topic must remain safe to reset with `/new`.

</Done>
