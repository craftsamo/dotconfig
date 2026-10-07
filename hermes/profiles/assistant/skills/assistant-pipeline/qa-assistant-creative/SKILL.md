---
name: qa-assistant-creative
description: "QA creative: inspect ONLY on explicit user request. Return bounded findings against the named criteria, without automatic revision. Ordinary hands completions use execute-assistant-creative for direct delivery."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
    tags: ["quality-assurance", "creative"]
---

<ReadBeforeWork>

Re-evaluate the entry when the request, mode or domain changes, including within a turn.
Reuse full-body instructions only while present in the current context, not a past load or summary.
Check the kernel and common mode procedure independently. Load each whose full body is missing:

```text
skill_view(name="assistant-pipeline")
skill_view(name="assistant-pipeline", file_path="references/quality-assurance/index.md")
```

These dependencies also apply to direct entry. Loading does not restart an approved plan or expand a grant.
If a tool returns unchanged while the earlier body is unavailable, use read_file on `${HERMES_SKILL_DIR}/../SKILL.md` and `${HERMES_SKILL_DIR}/../references/quality-assurance/index.md`.
Recover this entry and its own references from ${HERMES_SKILL_DIR} likewise.
Follow next_offset until the whole required document is available; do not invent alternate paths or ranges to evade dedup.
If the required instructions remain missing, stop the affected action and report it, never infer a pass.
Read only applicable detail references below.

</ReadBeforeWork>

# Creative - requested inspection

Use this entry only for an explicit user inspection request. Normal production uses
[direct delivery](../execute-assistant-creative/SKILL.md) without this pass.
Inspect the named artifacts and criteria once, then return findings. Do not
chain inspections, launch an
autonomous correction or iterate until acceptable. The common QA procedure's
automatic feedback loop does not apply here. A correction requires a client
request and the original scoped release, budget and proposal/preview gates.

Apply the [common QA floor](../references/quality-assurance/index.md) to the actual returned artifacts
and the acceptance criteria carried in the brief. The hands own production QA;
you judge whether their result meets the user's intended outcome.

## What returned?

Distinguish advice, questions, proposals, previews, final media and analysis
findings. A proposal/preview is an approval stop, not a missing video. Analysis
findings can be the final deliverable; do not demand corrected media when the
user asked only for a judgment. Never present an input or reference example
as newly produced output.

## Acceptance

When judging a perceptual mismatch or an ineffective revision, read
`skill_view(name="media-craft-direction")` and
`skill_view(name="media-craft-direction", file_path="references/critique-revision.md")`.
Keep these bodies current; recover missing bodies with read_file under
`~/.agents/skills/media-craft-direction/`, following truncation, or stop the affected
judgment if unavailable/ambiguous. This adds no production or repeated QA loop.
Ask whether the chosen effect serves the user's purpose, not only whether its
mechanics work. Name the actual evidence and proposed scope, not coordinate fixes.
For audio, prepare bounded neutral comparisons for the user's listening; never
invent perceived differences from meters. Record the version and reported choice.

1. Compare the result with the brief's purpose, audience, destination,
   must-keep content and selected guide's job-specific acceptance criteria.
   Verify that decided direction survived; an Assistant suggestion was not
   itself a user decision. Do not reopen settled planning questions.
2. Inspect supplied visual evidence at its size of use where available.
   Read the hands' technical evidence, provenance and spend rather than
   mandating duplicate measurements or a fresh upload. If a required claim
   lacks evidence, ask the producing hands for the missing check in the same conversation.
3. Keep evidence limits explicit. Sampled frames do not prove continuous
   motion. Audio readback/measurements are not a listening verdict. A local
   layout is not proof of a platform's real crop. An artifact only shown or
   copied to you does not establish its provenance, sound or factual claims.
   If user listening is needed, ask about the named criterion on the exact
   candidate and record the file/version and actual answer as user-reported
   evidence. A general "accepted" is not a listening observation or a
   replacement for technical QA.
4. Preserve failed and unknown flags. Required failures block acceptance
   until corrected or until the user knowingly changes the requirement;
   retain the original finding. Accepted uncertainty must be disclosed, not
   renamed PASS. Check that the approved scope and permitted spend still match.
5. Report concrete findings and proposed corrections, naming the criterion and
   affected artifact. Do not dispatch repairs from this inspection or repair,
   crop, resynthesize or re-encode it yourself. Return findings and caveats through
   [media ops](../execute-assistant-creative/references/media-ops.md).

Service-side drafts are saved through marketing Execute under separate
remote-save consent; publication is the user's action, not a producer grant.
Neither successful media QA nor the user's preview approval authorizes a post.
