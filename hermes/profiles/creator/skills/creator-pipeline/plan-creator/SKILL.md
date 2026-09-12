---
name: plan-creator
description: >-
  Plan media forms with the client; no production or spend.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [creator, plan, forms, hands, budget]
    category: creator-pipeline
---

<ReadBeforeWork>

Select the applicable entry from the available skills on every inbound turn or
completion, and before an action changes mode, subject or scope. A short approval
resumes the retained job; selection never restarts a plan or expands a grant.
Reuse full-body instructions only while present in current context, not a past
load, summary or preload marker. Direct entry requires the full kernel as well:

```text
skill_view(name="creator-pipeline")
```

Load that dependency if its body is missing. This entry is the mode procedure;
there is no separate common-mode file to load. Read only the selected subjects
below. Before applying another entry's detail, load its owning entry and kernel.
A missing required guide blocks the affected action, not the whole capability.
Creator reads hands forms and relevant options as a Client, never their producer
procedure as permission to execute a served leaf locally.

If skill_view returns unchanged while the earlier body is unavailable, use
read_file on the canonical document: `${HERMES_SKILL_DIR}/../SKILL.md` for the
kernel, `${HERMES_SKILL_DIR}/SKILL.md` for this entry, or its selected reference
under `${HERMES_SKILL_DIR}/references/`. Follow next_offset only when that read is
truncated. If the full required body still cannot be recovered, stop the affected
action and report the missing instructions. Never evade dedup with alternate
paths or artificial ranges. In raw text, `${HERMES_SKILL_DIR}` is the directory
of the document's owning SKILL.md, not whichever skill was loaded last.

</ReadBeforeWork>

# Plan - from a client's words to filled forms

Plan ends with one or more **filled forms** (each a hands leaf + its
fields), sequenced when there are several, each with a budget line where
metered - or with the finding that no leaf fits. Nothing is produced in
Plan; nothing is spent.

## The client

You have clients, not entry points; the same procedure serves both.
**Use runtime caller context before message shape**: a specialist handoff is
agent-authored, including conversational follow-ups. Its retained initial
request is context, not a renewed grant. Distinguish relayed human decisions,
agent implementation choices and proposals. Brief shape (`Goal:` / `Context:` /
`Inputs:` / `Deliverable:` / `Constraints:` / `Budget:`) is useful for older
unmarked exchanges, not evidence that other prose is human-authored.
(`clarify` in a non-interactive `-q` run cannot be answered and returns
at once - a brief-shaped message never gets one.)

- **Human** (your Telegram bot, a DM, the CLI). Fill the form with the
  **`clarify` tool** - the platform renders it natively (Telegram: one
  inline button per choice; CLI: a picker). Never type a `Q<n>:` list at a
  human. ONE call carrying one entry per open field: the `required: true`
  fields you cannot infer from what they said, plus at most one optional
  field when it changes the deliverable (`style` for `generate-icon`,
  `what_for` for `analyze-icon`). A field with `options` is a
  single-select whose choices are those options, your recommendation
  FIRST (the UI marks it); the UI appends "Other" itself, which is the
  form's `other: true`. A field without options is open-ended (omit
  `choices`). A field explicitly accepting multiple values, such as kit
  `contents`, is open-ended even when it lists suggested options: omit
  `choices`, show the suggestions and ask for a comma-list. Do not turn
  a request for props AND panels into a single-category choice.
  Put the field's `label` / `example` in the question text,
  never the options. A free-text answer is used as written.
- **Assistant** (a resident session it started, or an A2A peer call).
  Parse its brief - `Goal:` / `Context:` / `Inputs:` / `Deliverable:` /
  `Constraints:` / `Budget:` - into the form. Anything required the brief
  does not settle is ONE `Q<n>:` **text** block back (2-4 options + your
  recommendation) - a peer reads text, not buttons; it answers from its
  own context or asks the user with its own clarify.

Infer before you ask: a colour named in the message, a path pasted, a
"transparent" said in passing are answers. Ask only what is truly open.

## Choosing the leaf

Before interpreting a reference, selecting direction or translating intent into
a producer request, read [craft decisions](../references/craft.md) and its selected
knowledge. Skip this for an already-settled mechanical request; it adds no form.

Read [capabilities](../references/capabilities.md), served families before the legacy
technic table, then the candidate hands leaf with
`skill_view(name="<verb>-<subject>")`. Its `description` says what it
delivers, its `metadata.hermes.hands` names the hands, and its `form`
says what it needs. Read the matching subject reference below **before
filling or releasing that form**. These references explain Creator's
decisions; they do not replace the hands' form or advertise extra verbs.

| The client has / wants | Verb |
| --- | --- |
| an existing file to change | `edit` |
| a look no library draws, or a subject no library has | `generate` |
| a symbol a published library already has | `source` |
| a deterministic composition or set from approved inputs (an SVG, copy, supplied media) | `create` |
| a judgment, not repaired/generated media (ad analysis may retain report/evidence) | `analyze` |

Use only an installed leaf for that verb and subject. A family with no
hands leaf yet follows the confirmed legacy route in
[Build](../build-creator/SKILL.md#legacy---families-with-no-hands-yet), not a
substitute for an unsupported field of a served leaf. A missing Creator
subject reference is a maintenance finding, not evidence that the hands
can no longer serve that subject; do not improvise its missing guidance.

## Subject references

Load only the subject(s) needed by this request. For a composite, load
each dependency's subject when planning that unit, not every media family.

| Hands | Subject references |
| --- | --- |
| image-creator | [card](references/image-creator/card.md), [icon](references/image-creator/icon.md), [emoji](references/image-creator/emoji.md), [mascot](references/image-creator/mascot.md), [reimagine](references/image-creator/reimagine.md), [kit](references/image-creator/kit.md) |
| video-creator | [clip](references/video-creator/clip.md), [music-video](references/video-creator/music-video.md), [ad](references/video-creator/ad.md), [tour](references/video-creator/tour.md), [explainer-video](references/video-creator/explainer-video.md) |
| audio-creator | [speech](references/audio-creator/speech.md), [sfx](references/audio-creator/sfx.md), [music](references/audio-creator/music.md), [mix](references/audio-creator/mix.md) |

## Composite requests - a sequence of forms

Decompose into leaves, order them by what feeds what, and note the
dependency ("form 2's source = form 1's recommended variant"). Fill
form 1 completely now; fill a dependent form only when its input exists.
Two independent forms may run in parallel - [Build](../build-creator/SKILL.md).
Do not invent structure beyond the leaves: no menus, presets, or Styles
above the form; a request that needs a leaf that does not exist is
`no skill fits` to the client, noted for the maintainer.

Subject-specific dependency and proposal rules live in the references
above. A valid preliminary proposal may explicitly name pending inputs;
it never invents their paths or hashes or authorizes production with them.

Keep the audience, intended understanding/action and must-keep conditions in
each dependent request. An implementation metaphor is a proposal, not the goal:
"understanding accumulates" does not require an ever-growing pile of objects.
Test the uncertain representative unit before making a whole series; skip this
extra trial when the direction is already established. Do not impose research
or multiple concepts on every request. A revision rechecks affected dependencies,
not an automatic restart of all accepted work or its consumed allowance.

Before declaring a capability gap, distinguish a real backend/permission limit
from a template default, missing advisory reference, absent input or environment
failure. Check the installed leaf's actual scope and allowed composition paths.
Use supported local authoring or compose existing units within the grant rather
than asking for a new feature for every layout. Remaining gaps return with a
specific unmet requirement and feasible options; do not revive withdrawn routes,
change a specified engine, buy a fallback or silently weaken the outcome.

## Budget lines

A metered leaf takes a `budget:` line. Its documented default allowance
and any exception requiring explicit current-work approval live in the
selected subject reference and hands leaf, not a second budget table here.
The assistant's `Budget:` line is copied through; a human is told the
default and asked when they want more, or when that leaf requires an
explicit grant before spending. Never hand a metered form off without
knowing who pays for a corrective. A leaf's `cost: free` metadata means
no provider fee, not an unlimited attempt allowance. Failed attempts
count wherever the leaf's grant counts calls, and resume never restores
consumed attempts. Transport is never an extra grant.

## Client reference evidence

An assistant brief may append `References:` and `Direction:` as ordinary
briefing text, not a second form. Preserve observed evidence, suggested
direction, user-decided constraints and open choices as different things.
A research example is inspiration only, not automatically a production asset
or a hands form's `reference:`. Use it to inform your proposal, not to claim
the user approved an exact composition or supplied a licensed model input.

You still own creative proposals, forms and production sequencing. Infer
within the user's granted discretion, preserve explicit constraints, and
return material open decisions as `Q<n>:`. Do not require a new taste vote
for every minor suggestion, or bypass a leaf's exact-plan/preview approval
because the user chose a general direction. An absent input stays pending;
research screenshots are not substitutes for missing production assets.

## Reference-upload consent

When the selected image operation sends a `reference:` / `photo:` of a real
person to the image backend, a human client is told so in the SAME
clarify round as the style - one entry, "the photo is uploaded to the
image model (codex, else xAI); go ahead?" with yes first - never after
the fact. For an assistant Client, require its explicit relay of the user's
authorization for the named asset and upload operation, within that scope.
Brief shape, a public URL, a local path, a selected style or "use this" alone
is not external-upload consent. Reuse rights, model upload, remote analysis
and publication are distinct permissions; don't infer one from another.
If permission is missing or denied, return `Q<n>:` before the affected upload.
Missing permission does not block harmless local planning or discussion.
Never put research-only examples into production fields or upload them
merely because they traveled in the brief. This is an operating contract,
not cryptographic proof of the caller's authorization.

Preserve stricter leaf-specific consent requirements:
Kit and Card reference authority, Clip/MV image upload and separate remote
video analysis, and Speech's online house-voice fallback are settled in
their subject references. A local path alone does not override them.

## Advisory - a conversation that may not end in a form

"Would a glass icon work on a dark sidebar?" is answered from what you
know and from a leaf's style notes (`references/styles/<style>.md` via
`skill_view(..., file_path=)`), at zero spend, with a proposal: "if yes,
this form". A cheap `analyze-*` leaf may back the opinion with
measurements - that is a handoff like any other.

## Plan is done when

- every form's required fields hold a value the client gave or you could
  infer (and said you inferred), or the open ones are in flight as one
  clarify / one `Q<n>:` block;
- the `deliver:` path is decided: the brief's, else the owning Group's
  `.agent/deliverables/<job>/`, else `~/Workspaces/.deliverables/<job>/`;
- an actual production reference image, if required, has been copied under
  `deliver:` with its role and necessary permissions settled; research-only
  examples are not required production inputs or copied into a hands form;
- metered forms carry a budget line;
- the sequence and its dependencies are written down for
  [Build](../build-creator/SKILL.md).
