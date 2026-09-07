# Plan — from a client's words to filled forms

Plan ends with one or more **filled forms** (each a hands leaf + its
fields), sequenced when there are several, each with a budget line where
metered — or with the finding that no leaf fits. Nothing is produced in
Plan; nothing is spent.

## The client

You have clients, not entry points; the same procedure serves both.
**Tell them apart by the shape of the message, not by the surface**: the
assistant always writes in the brief shape (`Goal:` / `Context:` /
`Inputs:` / `Deliverable:` / `Constraints:` / `Budget:` lines) — on the
CLI of a resident session or over A2A alike. A message in that shape is
the assistant; anything conversational is a human, even on the CLI.
(`clarify` in a non-interactive `-q` run cannot be answered and returns
at once — a brief-shaped message never gets one.)

- **Human** (your Telegram bot, a DM, the CLI). Fill the form with the
  **`clarify` tool** — the platform renders it natively (Telegram: one
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
  Parse its brief — `Goal:` / `Context:` / `Inputs:` / `Deliverable:` /
  `Constraints:` / `Budget:` — into the form. Anything required the brief
  does not settle is ONE `Q<n>:` **text** block back (2-4 options + your
  recommendation) — a peer reads text, not buttons; it answers from its
  own context or asks the user with its own clarify.

Infer before you ask: a colour named in the message, a path pasted, a
"transparent" said in passing are answers. Ask only what is truly open.

## Choosing the leaf

`capabilities.md` lists the served families first. Read the candidate
leaf's front matter with `skill_view("<verb>-<subject>")` — the
`description` says what it delivers, the `form` says what it needs. Pick
by **verb**:

| The client has / wants | Verb |
| --- | --- |
| an existing file to change | `edit` |
| a look no library draws, or a subject no library has | `generate` |
| a symbol a published library already has | `source` |
| a set derived from something first-party (an SVG, a master) | `create` |
| a judgment, no file | `analyze` |

A family with no leaf yet is **legacy**: it is still yours to produce,
through `capabilities.md`'s technic table — see `build.md` "Legacy".

## Composite requests — a sequence of forms

UI task walkthroughs use `create-tour`: fill what_for/audience and reference
images, designs or text. Never demand per-step screenshots or steps JSON.
You own semantic flow and fidelity approval (faithful or explanatory simplified,
never invented real-product functions); VideoCreator owns task-local UI/motion
authoring. Frame/background style belongs to presentation, not blind UI reskinning.
Intro/outro default ON (title-reveal/result-hold). Offer the three reference
examples with `other: true`, not an exhaustive menu. Preserve custom directions
verbatim; unresolved ones need ONE clarification or concrete proposed beat.
Only explicit none omits, never absence/blank. The whole tour is <=60 seconds.
URLs are context, not capture permission; sufficient text needs no image.
This leaf does not capture URLs or automate browsers. Narration is a prior
audio-creator delivery, not TTS in video-creator. Send tour work via
`specialist_call(kind="work")` even though free. Broader authored motion
remains creator-html-motion; this new subject retires no legacy 1:1 mapping.

"An icon set for the new bot" is two forms: `generate-icon` (the mark),
then `create-icon` from an SVG — which `generate-icon` does not produce,
so say so and offer `edit-icon` sizes instead. Decompose into leaves,
order them by what feeds what, and note the dependency ("form 2's
`source` = form 1's recommended variant"). Fill form 1 completely now;
fill a dependent form only when its input exists. Two independent forms
(a light and a dark icon) can run in parallel — `build.md`. Do not invent
structure beyond the leaves: no menus, presets, or Styles above the
form; a request that needs a leaf that does not exist is `no skill fits`
to the client, noted for the maintainer.

## Budget lines

A metered leaf takes a `budget:` line; absent, the leaf's default (icon:
4 variants + 1 corrective; emoji: 3 anchor candidates, then 1 per item +
ceil(items/4) correctives for the pack; mascot: 3 concepts, then 1 per
item + ceil(items/4) correctives; reimagine: 2 per style + 1 corrective
per style; kit: 3 style sheets, then 1 per item + ceil(items/4)
correctives; clip: 2 variant attempts + 1 corrective total, including
failed video_generate invocations; speech: 1 take + 1 corrective per
script, counting every synthesis call including failures). The
assistant's `Budget:` line is copied through; a human is told the
default and asked only when they want more. Never hand a metered form
off without knowing who pays for a corrective. A leaf's `cost: free`
metadata means no provider fee, not an unlimited attempt allowance —
speech's take grant is enforced exactly the way a metered leaf's variant
grant is.

## A photo that leaves the machine

For clip, load the form rather than borrowing image defaults. Ask for the
subject/use, one motion/camera direction and a style; aspect defaults to
16:9 and duration to 5 seconds. A native still to animate is `source`,
appearance guidance is `reference` (one image). Both require
`upload_inputs: yes` before generation. `remote_analysis: yes|no` is a
separate decision for generated or supplied video: yes uploads the clip
to the configured analysis provider; no leaves temporal/audio QA
unverified. Ask in the same clarify round, not after production. An
assistant brief must carry that consent or explicitly request remote
analysis; never infer consent from a bare local file path. No TTS happens
inside VideoCreator; tour narration uses completed audio-creator inputs,
and other narration/assembly remain separate legacy jobs.

For edits, destination (landscape/portrait/square/exact size) and fit
(contain/cover) are separate. Default contain avoids losing edges. GIF
loses audio and `loop` only controls GIF playback; do not promise a
seamless animation or silently discard sound. If the requested work is
outside the clip contract (narrated explainer, multi-shot montage,
ComfyUI, pixel-grid animation), choose its existing legacy family up
front rather than force it into clip and fall back after failure.

`generate-reimagine` (and any leaf given a `reference:` / `photo:` of a
real person) sends that file to the image backend. A human client is
told so in the SAME clarify round as the style — one entry, "the photo
is uploaded to the image model (codex, else xAI); go ahead?" with yes
first — never after the fact; the assistant's brief is taken as
consent already given by the user it relays. Several styles on one
photo are ONE form (`style: comic-book, 80s-anime`), not one per style:
the hands write the identity lock once and every style is judged
against the same note. `keep` stays at its default unless the client
asked for a new scene ("put me in a 70s New York street" → `keep:
identity`; "make this photo a comic" → the default).

## An approved script, not a draft

`generate-speech` takes an approved script file, not text to compose:
never rewrite, translate or extend what the client wrote, and keep each
section to 600 characters or less — a longer script is a Plan finding
(split it into sections), never one paid-by-time take stretched to fit.
`voice:` is filled from a name the client actually gave (`house`, or the
exact `<engine>:<voice>` id); do not guess an id from a description. A
qualified voice's optional `style` or `seed` may only be offered from
what that engine's catalogue advertises — look it up first with a
no-synthesis `character_voices` A2A query to audio-creator, never invent
a control the client did not ask about.

`house` may reach the online Edge engine as its fallback for an
unsupported or English-dominant script; for a private or explicitly
local-only brief, ask in the SAME clarify round whether the client wants
a qualified local voice instead of the house default, rather than
defaulting to a fallback that leaves the machine. House and a qualified
voice never cross-fall-back into each other. The grant is 1 take + 1
corrective per script even though the leaf costs no provider fee — free
is not unlimited, and every synthesis call counts, successful or failed.
The hands' readback is ASR text-match evidence, not a listening
certification: never tell the client the line was heard, and never ask
for another take merely because the transcript came back with an
alternate spelling or homophone of a correctly spoken word.

Instrumental music, ambience/SFX, vocal-song generation, and audio
visualization are withdrawn without a hands replacement — a request for
one of them is `no skill fits` to the client, noted for the maintainer;
never picked up through a technic, core route, or external skill as a
stand-in.

## Two-round leaves

`generate-emoji` and `generate-mascot` refuse to draw a pack on an
unapproved likeness: the first handoff carries no `anchor` and comes
back with three candidates (emoji: character sheets; mascot: full-body
concepts plus a silhouette sheet and the hands' recommendation). Show
them to the client (a human: the three files + one `clarify` with the
candidates as choices; the assistant: the paths and your pick), then
send `intent: revise <that dir>` with `anchor: <the approved file>` —
the hands print that exact line in their report. For a mascot the
second round also needs `pack:` (`turnaround` for a model sheet,
`poses` for the everyday eight, `custom` + `items`); a client who only
wanted the character stops after round A — the concept IS the
deliverable. A pack that comes back with items marked `passed: false`
is not a failure: the hands ran out of correctives; you decide whether
to send a `budget: N correctives — <items> only` revise or ship with the
marks. Correctives on a pale-haired or pale-skinned character almost
always mean a prop (tears, sweat, "?") that must be large, saturated
and off the hair — say so in the `note:`.

A character lives once: an approved mascot anchor is the `reference:`
for its emoji pack (`generate-emoji`), and a mascot the client wants
for video goes through `edit-mascot` with `background: chromakey`
rather than a second generation. When a client asks for "an emoji of
our mascot" and no mascot exists yet, that is two forms in order —
`generate-mascot` first, `generate-emoji` on its anchor second — and
you say so.

## A kit is a list, not one image

`generate-kit` follows the two-round gate too. First fill `what_for`,
`style`, `contents` and any explicit `items`, and send a no-anchor form.
The hands propose one style sheet containing representative props/UI
per candidate and an expanded item list. Show the sheet AND list before
requesting approval. Round B takes the approved anchor, list, design lock
and explicit image-call allowance; more than 24 items always requires
an explicit budget line. Normal/pressed/hover/disabled each count as an
item, not a free variant hidden in the count. Do not conflate call counts
with a verified currency quote.

The listed categories are suggestions, not a closed world or a five-item
cap. Explicit `items` REPLACE defaults. A described category needs agreed
items and canvases before the batch. World props use the chosen camera;
UI faces the screen. `size` in kit forms is an integer scale, not a single
square imposed on every category. Reference images may be uploaded;
confirm authority to send them, do not treat a local path alone as consent.

An AI-generated state pair can differ in silhouette even on the same
anchor. If the client needs exact interchangeable controls, offer
`create-kit` for supported flat-vector/pixel UI; explain its generic
geometry instead of promising a hand-painted reproduction. PNGs that
fail the state check stay flagged, never become a production-ready kit
by removing their failed status. `source-kit` is stock retrieval, with
the pack's own look and license, not a route to redesign it.

## Advisory — a conversation that may not end in a form

"Would a glass icon work on a dark sidebar?" is answered from what you
know and from a leaf's style notes (`references/styles/<style>.md` via
`skill_view(..., file_path=)`), at zero spend, with a proposal: "if yes,
this form". A cheap `analyze-*` leaf may back the opinion with
measurements — that is a handoff like any other.

## Plan is done when

- every form's required fields hold a value the client gave or you could
  infer (and said you inferred), or the open ones are in flight as one
  clarify / one `Q<n>:` block;
- the `deliver:` path is decided: the brief's, else the owning Group's
  `.agent/deliverables/<job>/`, else `~/Workspaces/.deliverables/<job>/`;
- a reference image, if any, has been copied under `deliver:`;
- metered forms carry a budget line;
- the sequence and its dependencies are written down for `build.md`.
