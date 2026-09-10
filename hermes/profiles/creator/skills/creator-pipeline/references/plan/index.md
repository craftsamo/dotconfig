# Plan - from a client's words to filled forms

Plan ends with one or more **filled forms** (each a hands leaf + its
fields), sequenced when there are several, each with a budget line where
metered - or with the finding that no leaf fits. Nothing is produced in
Plan; nothing is spent.

## The client

You have clients, not entry points; the same procedure serves both.
**Tell them apart by the shape of the message, not by the surface**: the
assistant always writes in the brief shape (`Goal:` / `Context:` /
`Inputs:` / `Deliverable:` / `Constraints:` / `Budget:` lines) - on the
CLI of a resident session or over A2A alike. A message in that shape is
the assistant; anything conversational is a human, even on the CLI.
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

Read [capabilities](../capabilities.md), served families before the legacy
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
[Build](../build/index.md#legacy---families-with-no-hands-yet), not a
substitute for an unsupported field of a served leaf. A missing Creator
subject reference is a maintenance finding, not evidence that the hands
can no longer serve that subject; do not improvise its missing guidance.

## Subject references

Load only the subject(s) needed by this request. For a composite, load
each dependency's subject when planning that unit, not every media family.

| Hands | Subject references |
| --- | --- |
| image-creator | [card](image-creator/card.md), [icon](image-creator/icon.md), [emoji](image-creator/emoji.md), [mascot](image-creator/mascot.md), [reimagine](image-creator/reimagine.md), [kit](image-creator/kit.md) |
| video-creator | [clip](video-creator/clip.md), [music-video](video-creator/music-video.md), [ad](video-creator/ad.md), [tour](video-creator/tour.md), [explainer-video](video-creator/explainer-video.md) |
| audio-creator | [speech](audio-creator/speech.md), [sfx](audio-creator/sfx.md), [music](audio-creator/music.md), [mix](audio-creator/mix.md) |

## Composite requests - a sequence of forms

Decompose into leaves, order them by what feeds what, and note the
dependency ("form 2's source = form 1's recommended variant"). Fill
form 1 completely now; fill a dependent form only when its input exists.
Two independent forms may run in parallel - [Build](../build/index.md).
Do not invent structure beyond the leaves: no menus, presets, or Styles
above the form; a request that needs a leaf that does not exist is
`no skill fits` to the client, noted for the maintainer.

Subject-specific dependency and proposal rules live in the references
above. A valid preliminary proposal may explicitly name pending inputs;
it never invents their paths or hashes or authorizes production with them.

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

## Reference-upload consent

Any image leaf given a `reference:` / `photo:` of a real person sends
that file to the image backend. A human client is told so in the SAME
clarify round as the style - one entry, "the photo is uploaded to the
image model (codex, else xAI); go ahead?" with yes first - never after
the fact; the assistant's brief is taken as consent already given by
the user it relays. Preserve stricter leaf-specific consent requirements:
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
- a reference image, if any, has been copied under `deliver:`;
- metered forms carry a budget line;
- the sequence and its dependencies are written down for
  [Build](../build/index.md).
