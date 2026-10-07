---
name: execute-assistant-creative
description: "Execute creative: relay briefs and approvals, supervise Creator and deliver candidates promptly with producer checks and caveats. Normal completions stay here, without a separate QA stage."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
    tags: ["execute", "creative"]
---

<ReadBeforeWork>

Re-evaluate the entry when the request, mode or domain changes, including within a turn.
Reuse full-body instructions only while present in the current context, not a past load or summary.
Check the kernel and common mode procedure independently. Load each whose full body is missing:

```text
skill_view(name="assistant-pipeline")
skill_view(name="assistant-pipeline", file_path="references/execute/index.md")
```

These dependencies also apply to direct entry. Loading does not restart an approved plan or expand a grant.
If a tool returns unchanged while the earlier body is unavailable, use read_file on `${HERMES_SKILL_DIR}/../SKILL.md` and `${HERMES_SKILL_DIR}/../references/execute/index.md`.
Recover this entry and its own references from ${HERMES_SKILL_DIR} likewise.
Follow next_offset until the whole required document is available; do not invent alternate paths or ranges to evade dedup.
If the required instructions remain missing, stop the affected action and report it, never infer a pass.
Read only applicable detail references below.

</ReadBeforeWork>

# Creative - Client dialogue

## Hands-served families

Creator is the production owner, including its delegated hands. You own the
user's outcome, context, grants and delivery for the user's judgment, per
[Client planning](../plan-assistant-creative/SKILL.md). These rules apply to the
currently served scope, not a fixed list of media or operations.

Use `specialist_call(target="creator", ...)`. Never call `image-creator`,
`video-creator` or `audio-creator` directly, never use raw `a2a_call`, and
never fill in Creator's hands forms yourself.

## Brief and continuation

Send a self-contained brief with the existing fields:

```text
Goal: intended outcome and audience; consultation, production or analysis
Context: use, purpose, what the user decided and what remains open
Inputs: exact existing paths, their role and known permissions; missing inputs
Deliverable: wanted artifact or findings, durable location, acceptance criteria
Constraints: must-keep content, exclusions, deadline, decisions Creator may make
Budget: the actual sanctioned allowance and any unresolved grant
```

When useful, append `References:` and `Direction:` as plain briefing text:
observations and sources, suggestions, user-decided direction, and explicit
permission scope. Research examples are inspiration only unless separately
authorized as production inputs. An omitted permission is unknown, not yes.
These annotations are not new tool fields, a registry or another form schema.

For newly authored video, send intent, not a design: purpose, audience,
destination, fixed words, brand rules, exclusions, supplied inputs,
references with what each is for, and acceptance criteria. Ask Creator to
have its producer design the storyboard and to return it for the user's
approval; relay that storyboard to the user in plain language and relay the
user's decision back. Do not prescribe layouts, shapes, components or
motion the user did not ask for.

Use `kind="inquiry"` only for a short, bounded, non-generating consultation.
Released production and multi-turn work use `kind="work"`, including any
analysis whose contract requires work. If an inquiry leads to production,
start a work conversation with the settled context; never upgrade the pinned
route in place. Keep target="creator" and its returned `conversation_id` for
work continuations. No repeating the first call to work around a pending reply.

Answer Creator's `Q<n>:` from existing context, or ask the user the unresolved
decision in ordinary language. Do not expose an internal form. Consultation
may end with advice and analysis with findings; neither implies a new file.

## Approval relay

Before resolving a material interpretation during execution, use the conditional
craft reading in [Client planning](../plan-assistant-creative/SKILL.md), with its
current owning entry and kernel. A tentative suggestion remains a suggestion;
do not convert the producer's chosen metaphor into a user-mandated mechanism.
An approved study is not an approved final, and a request to continue cannot
prospectively approve exact plan/preview bytes that do not yet exist.

Keep an explicit distinction in each continuation: human decision with source
and exact affected proposal/preview, your implementation choice within the
grant, or an unapproved suggestion. The transport retains the initial brief and
attributes messages to an agent; this helps inspection, not authorization.
An agent DECISION or a source label cannot turn a weakened requirement into
human approval. Compare any proposed compromise with the original purpose,
audience and must-keep conditions before responding to Creator.

A proposal or preview is a valid approval stop, not a missing final or a
stalled job. Show the actual returned material with a concise explanation;
preserve exact copy, claims, alternatives and the artifact references.
Relay the user's actual decision in the SAME `target` and `conversation_id`,
quoting the exact proposal/preview/option references Creator returned.
Never self-compute, refresh or fabricate approval hashes.

A Budget line is not proposal approval. Proposal approval is not an expanded
spending allowance. Apply the actual user's grant and the selected contract's
required approval stops; do not add a mandatory taste vote for every minor
choice already within granted discretion. Suggestions not yet decided remain
suggestions, even when you favor them. A changed purpose, ratio, protected
content or other approved scope needs impact assessment and the required
new approval, not a silent continuation on an obsolete preview.

## Inputs, progress and findings

- Keep the user's original input paths. A readable local video needs no
  fresh chat attachment. Missing inputs stay missing; do not invent paths,
  substitute identities or search unrelated personal data.
- Separate permission to read, reuse, upload to a production model, run
  remote analysis and publish. Relay the exact granted scope. Missing
  permission blocks the affected operation, not harmless local planning.
- Let Creator coordinate production dependencies. Reuse accepted Writer
  text unchanged and do not request the same unit from another specialist.
- Acknowledge an accepted dispatch, retain its handle and wait for normal
  completion notifications. Use the existing
  [resident-session supervision](../references/execute/resident-sessions.md) for pending or
  interrupted work; uncertainty is not authorization to launch duplicates.
- Reconcile the job's returned spend against the sanctioned allowance.
  Failed attempts and previous consumption survive revisions and resumes.
  Return a discrepancy or missing evidence to the same work conversation.

## Direct delivery

Stay in Execute on normal Creator completion; do not load
`qa-assistant-creative` or request another Creator inspection. This also applies
to confirmed legacy units. Read the returned report for its
output kind, durable paths, producer check status, obvious conflicts with settled
constraints and spend. Do not mandate visual looks, remeasurements, a new QA
report or autonomous aesthetic corrections before showing the candidate.

Distinguish advice, analysis findings, proposals, approval previews and final
candidates. Findings can be the requested outcome; a proposal is not a missing
final. Never present source/reference material as newly produced output. Show
usable previews promptly with failed and unknown checks disclosed, including
unverified motion/listening/taste. Required failures still block final readiness
and dependent use; request a scoped producer fix or report the blocker, never
rename a failure PASS. Missing evidence remains unknown, not an inspection you
performed. Preserve approved part versions and all proposal/preview, budget,
upload, remote-analysis and publication gates.

Deliver through [media-ops.md](references/media-ops.md): attach the actual
viewable file when supported, or give an accessible viewing route and state any
delivery limitation. An internal path alone is not a viewing method. Carry the
producer's spend and relevant caveats forward without a second inspection.
Delivery is not the user's acceptance, listening evidence or permission to
continue production. Close only after acceptance of the requested outcome, not
merely its proposal; leave approval-waiting or unresolved work explicit.

If the user rejects the overall direction, revisit the reference interpretation
with Creator and show a supported representative sample before full production.
For a time-based reference, test the relevant composition AND progression, not
only a static frame or ending. Keep existing sample modes, exact approval stops
and consumed allowances; do not invent a study mode or iterate minor polish on
the rejected idea. An explicit user request to inspect instead routes to
[requested inspection](../qa-assistant-creative/SKILL.md) for bounded findings,
not an automatic revision grant.

## Confirmed legacy work

Only Creator-confirmed legacy unit work loads
[legacy/index.md](references/legacy/index.md).
