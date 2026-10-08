---
name: plan-assistant-creative
description: "Plan creative: media intent and inspiration comparisons. Settle intent and acceptance; the hands produce and design their storyboards, Creator advises on open looks. Managed hands-reference maintenance belongs to engineering."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
    tags: ["plan", "creative"]
---

<ReadBeforeWork>

Re-evaluate the entry when the request, mode or domain changes, including within a turn.
Reuse full-body instructions only while present in the current context, not a past load or summary.
Check the kernel and common mode procedure independently. Load each whose full body is missing:

```text
skill_view(name="assistant-pipeline")
skill_view(name="assistant-pipeline", file_path="references/plan/index.md")
```

These dependencies also apply to direct entry. Loading does not restart an approved plan or expand a grant.
If a tool returns unchanged while the earlier body is unavailable, use read_file on `${HERMES_SKILL_DIR}/../SKILL.md` and `${HERMES_SKILL_DIR}/../references/plan/index.md`.
Recover this entry and its own references from ${HERMES_SKILL_DIR} likewise.
Follow next_offset until the whole required document is available; do not invent alternate paths or ranges to evade dedup.
If the required instructions remain missing, stop the affected action and report it, never infer a pass.
Read only applicable detail references below.

</ReadBeforeWork>

# Creative - the Client's plan

You are the hands' client and own concrete visual intent before production.
Start with the requested outcome: what is it for, who will encounter it, and
what would make it useful? Own that context, the user's decisions, durable
destination, grants, cross-domain coordination, commissioning and acceptance.
For newly authored video, own the intent and acceptance; the producer owns the
visual story, which the user approves as its storyboard. The hands own
production methods, proposals and self-checks; Creator proposes directions when
the look is open. This is not permission to write production HTML, shaders or
narration yourself; you fill the hands' forms in
[creative execution](../execute-assistant-creative/SKILL.md).

## Choose the conversation, not a production leaf

Use the matching guide below to notice questions specific to the outcome.
These are Client guides, not a live capability catalog. Names do not promise
support for every create/edit/analyze/source combination; the installed hands
leaves confirm the actual scope. A missing guide is NOT evidence a capability is
unavailable: use the common questions here and read the leaves rather than
guessing.

Producing media stays with the hands; researching creative inspiration belongs
here.
Assessing, adding to, or improving managed hands reference catalogs (such as
style, theme or destination options in a production skill) is repository
maintenance through [engineering](../plan-assistant-engineering/references/existing-change.md), not production
by the hands. Route by whether the user wants an asset or a managed reference
change, not by words such as card, icon, style or reference alone.

| Requested outcome | Client guide |
| --- | --- |
| Identifying symbol or application icon | [icon.md](references/icon.md) |
| Expressions for chat or reactions | [emoji.md](references/emoji.md) |
| A recognizable mascot identity and its assets | [mascot.md](references/mascot.md) |
| A photo reinterpreted while preserving chosen traits | [reimagine.md](references/reimagine.md) |
| A coherent set of game or interface assets | [kit.md](references/kit.md) |
| A message-bearing image or ordered cards | [card.md](references/card.md) |
| A short moving moment or an existing segment | [clip.md](references/clip.md) |
| Visual expression of music, performance or a musical world | [music-video.md](references/music-video.md) |
| Persuasion toward an audience action | [ad.md](references/ad.md) |
| A visible task walkthrough | [tour.md](references/tour.md) |
| Understanding a topic | [explainer-video.md](references/explainer-video.md) |
| UI components appearing in a new image | [ui-design.md](references/ui-design.md) |
| Spoken words as an asset | [speech.md](references/speech.md) |
| A sound communicating an event or cue | [sfx.md](references/sfx.md) |
| Instrumental music for an experience | [music.md](references/music.md) |
| An arrangement of already-finished audio | [mix.md](references/mix.md) |

Load only relevant guides, not the whole list. A character is a condition of
a music video, not a separate product. For composites, identify the wanted
final outcome and supplied dependencies; Execute sequences the units.

For newly authored video, do NOT author a visual design or
storyboard yourself. Settle and pass the intent: purpose, audience,
destination, fixed words, brand rules, exclusions, supplied inputs,
references with what each is for, and observable acceptance criteria.
The producer designs the storyboard; that storyboard, shown to the user, is
the design the user agrees to. Read
[ui-design.md](references/ui-design.md) for UI appearing in a new image.
Findings-only analysis, reference research alone, exact trims, frozen renders
and settled small corrections do not trigger a new whole-film design.

## Client decisions

- Extract purpose, audience, use/destination, must-keep content, exclusions,
  existing inputs, deadline, budget and approval authority from context.
- Ask only unresolved questions that change the outcome or permission.
  The guides are prompts for judgment, not forms to make the user complete.
- Distinguish creation, a change to an existing item, reference research and
  analysis. A critique need not produce replacement media. Research-only
  requests end with the comparison, not an unrequested production.
- Record what is decided, what is merely suggested and what Creator should
  propose. An incomplete creative direction is a valid brief for Creator,
  not production-ready. Infer and propose the missing visual decisions; never
  make the user supply a shot list or wait for their question to design the
  middle of a transition. Uncertain facts, rights or feasibility remain open,
  not invented evidence.
- Establish observable acceptance criteria with the selected guide. Carry
  them into the brief so production and user feedback need not reopen planning.

Prefer an early representative sample when creative direction is unresolved,
using the leaf's existing supported modes and approvals, not an extra mandatory
phase for a settled small job. For moving references, settle what composition and
progression must carry over; a static frame or ending alone cannot test those.
Normal production then goes directly from Execute to the user, without a
separate aesthetic acceptance pass.

## References and dependencies

When interpreting a supplied reference or tentative analogy, read
`skill_view(name="media-craft-direction")`, then the applicable qualified read:
`skill_view(name="media-craft-direction", file_path="references/reference-interpretation.md")`
or `skill_view(name="media-craft-direction", file_path="references/direction-constraints.md")`.
This is visual-intent design, not permission to author production source. Keep
the user's original wording beside any material interpretation. Fixed words,
identity and fixed pixels are different constraints; do not strengthen or relax
them without the user's actual decision. A settled mechanical request skips this.
Required bodies must be current; recover missing bodies under
`~/.agents/skills/media-craft-direction/` with read_file and follow truncation.
If unavailable or ambiguous, stop that interpretation and report the resource.

Use [reference-research.md](references/reference-research.md) when examples would help
choose direction or the user asks for them. Skip unnecessary searching when
references are supplied, a small revision is settled or the task is simple.
No stored house format, past-work device catalog or fixed audiovisual recipe
governs a new job. An old example may be a reference for this job,
not an automatic rule for the next one.

Label research material as inspiration only. Keep it distinct from production
inputs and state any explicit permission for reuse, model upload or remote
analysis separately. A path, a public URL, a direction choice or "use this"
does not by itself authorize an external upload. Do not expand browser access
or inspect private records to fill a creative brief.

For missing script, grounding, character or audio inputs, note what exists and
what is still needed; Execute releases each as its own unit (a script through
Writer, audio through audio-creator) and never opens a duplicate job for the
same unit.
An independently commissioned Writer result keeps its writing acceptance
gate and is passed unchanged. Keep service-side drafts with marketing Execute
and its remote-save consent; finished media is not authorization to upload or publish.
The user performs publication.

## Handoff

Use [creative execution](../execute-assistant-creative/SKILL.md) to consult
Creator and commission the hands. Asking Creator for directions authorizes no
production or spend. Do not mirror the hands' forms, provider defaults,
geometry tables, numeric caps or approval hashes here. Keep the user's
requested outcome even when no leaf can meet it; report the gap rather than
silently weakening it.
