# Creator hands — overview

The v3 hands contract: client model, skill tree, form, handoff, media craft, migration. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Creator hands (v3, 2026-09)

Creator's production moves, one asset family at a time, out of the generic
`creator-*` technics and into **hands** profiles — `image-creator`
(A2A `:9907`), `video-creator` (`:9908`) and `audio-creator` (`:9909`). Each
is a receive-only A2A endpoint with the tools of its medium and nothing else.
Family details: [`image.md`](./image.md), [`video.md`](./video.md),
[`audio.md`](./audio.md); Creator's side: [`broker.md`](../broker.md).

The rule is **one skill = one concrete deliverable = one form**, with nothing
above the skill but a reader. A hands leaf is never a technic and never a
generated index. Add no `menu.yaml`, no generated `MENU.md`, no preset layer
and no cross-media Styles — generic technics decided nothing, and a governing
layer above the leaves encoded one choice in several places and drifted.

### Client model

Specialist transport preserves the original agent request and a per-turn
private handoff record, distinguishes current instructions from non-actionable
history, and identifies the caller as an agent even during conversational
follow-ups. This is provenance for inspection, not authenticated human approval.
Keep relayed human decisions with their source/proposal/scope separate from
agent implementation choices. Do not weaken the outcome to match a template;
use the granted discretion without unnecessary repeated questions.

Creator has **clients**, not entry points: the human (Creator's own Telegram
bot) or the assistant (resident session / A2A, carrying a SessionBrief).
Creator uses runtime caller context before message shape; conversational
follow-ups are not proof of human origin or approval. Its job is the same for
both clients: pick the skill, **fill its form** — with the `clarify` tool for a
direct human (Telegram renders one inline button per option; the form's
`options` become the choices, `other: true` is the UI's own "Other" row), by
parsing the brief for an agent client, returning a text `Q<n>:` block for
whatever required field it cannot fill — hand the filled form to the hands,
gate the result against the intent (visual inspection or audio evidence),
deliver. The hands never see the client or invent its requirements: they
receive a filled form or return `Q<n>:`. A leaf may own creative execution
within that form (MV direction, for example), with its explicit proposal
approval gate.

The assistant keeps delivery to the user, the durable path, Budget lines and
GitHub bookkeeping; it does not make production decisions on Creator's behalf.
Its outcome guides support Client dialogue; the old production decision leaves
live at `plan-assistant-creative/references/legacy/<family>.md`, with their QA
`Covers` mapping under `qa-assistant-creative/references/legacy/`. Those old
mappings retire family by family only after the gates in "Migration" below,
independently of the Client guides.

For a stuck resident transport, `specialist_session(action="reconcile", ...,
evidence=...)` verifies its recorded process group is gone and its shell lock is
absent or belongs to that same dead process. It retains an owned dead lock and
records `interrupted`, with external effects still unknown and no continuation
allowed. A2A, missing handles and foreign/unverifiable locks remain blocked.
Bookkeeping close is neither acceptance nor evidence that a retry is safe.

Acceptance follows the initial audience/outcome and the actual returned version,
not the producer's chosen metaphor or successful process exit. Record component
versions and dependent checks in existing job notes; revisions invalidate only
affected evidence. Local acceptance, preview approval and a reopened service-side
draft are separate facts. The work-continuity verification (see `AGENTS.md`)
checks routing coverage for all hands, real skill discovery and the
profile/runtime regressions; subjective comprehension and live save behavior
still need actual-use evidence.

### Skill tree

```
profiles/<hands>/skills/
  <hands>-pipeline/
    SKILL.md                 # <=40 lines: validate form -> load leaf -> run -> QA -> report
    scripts/                 # helpers shared by several leaves (e.g. img-postprocess.sh)
    <verb>/<subject>/
      SKILL.md               # name: <verb>-<subject>  (one deliverable, one form)
      references/styles/*.md # this leaf's style notes only — never cross-media
      assets/reference-*.*   # optional: a sample the leaf has actually produced
      scripts/
```

- **Verbs** (closed set): `create` — drawn deterministically from inputs
  (script / SVG / grid; free); `generate` — a model draws the pixels or the
  waveform (free local synthesis or metered provider); `edit` — transform an
  existing asset (free unless the edit itself generates); `source` — fetch a
  published asset and record its license (free); `analyze` — inspect an
  existing asset and return findings, not new/repaired media (free). Most
  analyze leaves return reply findings; analyze-ad may retain its report and
  evidence at an explicit deliver path for a later creative brief, never a new
  ad. The `create`/`generate` boundary is whether a generation model is asked
  to draw.
- **Cost is independent of verb.** `free` means no metered media-provider fee,
  not zero reasoning cost or unlimited compute. Local speech synthesis still
  has a take allowance: one take plus one corrective per script by default.
  Failed synthesis invocations count. Long free work still uses resident sessions.
- **Subjects** are concrete nouns (`icon`, `hero`, `clip`, `voice-line`),
  **unique across all hands** because Creator reads every hands' tree through
  one `skills.external_dirs` list; the validator (`validate_hands`) enforces
  the shape and rejects a subject that appears under two hands. `name` equals
  `<verb>-<subject>` and equals the path.
- The pipeline root holds no router and no lifecycle beyond the five steps
  above; discovery is Creator reading the leaves' front matter directly. No
  generated index, no shared Style system, no palette vocabulary above the leaf.
- Hands report a defect in a leaf's own scripts or references to the
  maintainer; they never patch tracked skill roots (`skill-topology` blocks
  such writes at the tool layer).

**Execution-environment traps** go into the Procedure of the leaf that hits
them, not into a shared note:

- Japanese `。` in an argv string trips the terminal guard → pass text as a file.
- Foreground terminal calls die at 420 s → long renders run `background: true`
  and are polled.
- Vision holds ~3 images → contact sheet first, then one image at a time.
- Append each look's finding to `qa.md` before the next `vision_analyze`; an
  unwritten look did not happen — an image leaves the context three looks later.
  `qa.md` is appended, never rewritten.
- `magick montage` aborts without a default font → use `+append`.
- A multi-file `rm` trips the guard → leave `/tmp` alone.
- An inline `for` loop over a script variable trips the guard → run batches
  through a script file.
- The write guard reads the WHOLE terminal command, so `cp … && <skill script>`
  is refused → run a skill script in a command of its own.
- A 32 px tile is judged point-magnified 4x.

**Instruction context.** The hands' always-on contracts re-evaluate the named
leaf and selected references on inbound turns/completions and before a changed
operation, subject or option. The executing profile's full kernel and required
instructions must be in current context, not merely recorded as loaded.
Canonical `read_file` recovery follows genuine truncation offsets; unrecoverable
required instructions stop the action. Optional advisory references keep their
fallback. Loading never grants a new operation, resets spend or reruns a
completed render. Creator inspecting a hands form does not become that hands'
executor.

### The form (front matter is the only representation)

```yaml
---
name: generate-icon
description: >-
  <one sentence: what this leaf delivers, from which inputs — the only line
  Creator needs to choose it>
version: 1.0.0
metadata:
  hermes:
    category: hands
    hands: image-creator
    cost: metered                      # free | metered
    output: "icon_<slug>_<size>.png (transparent, square) + .svg when vector"
    form:
      what_for:   {required: true,  label: "何のアイコンか", example: "Slack 通知 bot"}
      style:      {required: true,  options: [flat-minimal, glass, pixel, line, clay], other: true}
      background: {required: false, options: [transparent, brand-fill, tile], other: true}
      reference:  {required: false, type: image, label: "参照画像のパス"}
      note:       {required: false, type: text}
---
```

Field keys: `required` (bool), `label` / `example` (interview prompts),
`options` + `other: true` (a controlled vocabulary that still accepts a
free value — the leaf's `references/styles/<option>.md` backs each listed
option), `type` (`text` default, `image`, `file`, `path`, `int`). `note` is
the escape hatch every leaf carries. The SKILL.md body has exactly three
sections — `<Procedure>`, `<QA>`, `<Report>` — no Goal / Inputs / Presets
sections, because `description` and `form` already say that.

If a field has options and its leaf has `references/<field>/`, every
listed option must have a matching Markdown file. `style` keeps its
mandatory `references/styles/` mapping. This lets kit content tables live
under `references/contents/` without a generated registry. Theme uses
`references/themes/`; an explicit `references` declaration makes option
backing mandatory even when the directory is missing. MV keeps style
(rendering), theme (world vocabulary) and direction (staging) within one leaf.
Multi-value text fields describe their comma-list syntax in the label;
`other: true` permits that string at intake, and the leaf validates each
member. An option is not a requirement to generate every default item:
Creator confirms the expanded item list and spend before batch production.

Hermes discovery reads only the first 4,000 characters of a SKILL.md before
parsing YAML, so a leaf's complete front matter must close inside that prefix
(use compact labels; keep full procedures in the body) — an incomplete fence
silently collapses sibling leaves into one parent-named skill even though the
topology validator passes.

### Handoff message (Creator → hands, A2A or resident session alike)

```
skill: generate-icon
intent: new | revise <path of the previous delivery>
deliver: ~/Workspaces/Projects/<Group>/.agent/deliverables/<job>/
budget: 4 variants + 1 corrective          # media calls or local speech takes
form:
  what_for: Slack 通知 bot のアプリアイコン
  style: glass
  background: transparent
  reference: /path/to/ref.png
  note: 青系、角丸は控えめ
```

The selected Group must already exist. Its `.agent/deliverables/<job>/`
directory and job-owned descendants (such as `video-plan` or `music-plan`)
are accepted by all three hands; the Group root itself and
`~/Workspaces/.deliverables/<job>/` remain valid for existing callers.
A job directory may be created beneath an existing parent, subject to the
leaf's exclusive-output checks. Never create a new Group or relocate a
valid Group-local job merely because it is below the Group root. This is
an operating contract, not a filesystem sandbox or upload/overwrite consent.

The hands reply with the leaf's `<Report>` (paths, every QA check with its
evidence, spend) or with one batched `Q<n>:` block naming the missing
required fields — never with a substitute. A request no leaf fits is a
finding back to Creator (`no skill fits: …`), which Creator relays to the
client and records for the maintainer; neither side improvises a leaf.
Short free single-reply leaves use `specialist_call(kind="inquiry")`; anything
metered, multi-turn or longer than one reply window uses `kind="work"` from
Creator. Continue with the same target and returned conversation_id. Released
inputs, permissions, budgets and the exact handoff text are unchanged. CLI
calls wait within a finite deadline; A2A inbound cannot launch work and must
ask its caller to reissue the unit through a work conversation.

Transport limits: A2A identifies loopback callers by IP, not by a
cryptographically verified profile, so a verbal origin confirmation adds no
security; keep the localhost restriction and never widen the transport. All
three hands run in the single multiplex gateway; after a restart, readiness is
proven by the agent card answering HTTP 200 plus listener ownership, not by
launchctl's return. An early `Unknown toolsets: a2a` CLI warning during plugin
discovery is benign — never add a second gateway to work around it.

### Media craft knowledge

The four tracked, portable `media-craft-direction`, `media-craft-visual`,
`media-craft-motion` and `media-craft-audio` skills live in `agents/curated/`,
not in hands' production trees or generated Styles catalogs, and use the
standard shared-store install links. Creator's shared store already exposes
them; image-creator pins direction/visual, video-creator direction/visual/motion,
and audio-creator direction/audio individually. No hands receives the whole store.
Each hands kernel's `references/craft.md` owns conditional reading for all its
current subjects and actual creative decisions. Creator's Plan/Build/QA entries
and the confirmed legacy path share Creator's own `references/craft.md`; legacy
production uses that knowledge without retiring or silently replacing its methods.

These are technique and judgment resources, not new forms, producer roles,
cross-media Styles, permissions, outside workflows or executable scripts. The
optional HyperFrames technical pins keep their own leaf scope and fallback
([`video.md`](./video.md) "Video authoring references"); craft pins are a
separate knowledge-only exception. Local procedures still own engines, source
integrity, proposal/preview approvals, budgets and QA commands. Required craft
bodies must be current before the affected creative decision; missing or
ambiguous knowledge is a named stop for that decision, never an install or
capability expansion. Mechanical work skips the craft reading. Audio perception
stays human-reported: acceptance uses attributed human listening, meters and ASR
never become a listening verdict, and the shared skill authorizes no new tool.
Fresh conversations are needed after an explicitly approved install/cutover.
Existing jobs and frozen outputs are not migrated. Candidate and
structural/discovery validation is neither live cutover nor artistic acceptance.

### Vision window

Native `vision_analyze` puts the image itself into the tool result, and Hermes
sends only the newest three image-bearing tool results with each request. A
step that asked for 29 frames showed three, while the other 26 results still
read "Image loaded into your context"; the model saw no image, assumed the
load had failed and asked again. In the 2026-09-23 Creator A/B one frame was
opened 68-80 times, 566-972 looks per 16 s job over 30-44 files, against 19-47
for OpenCode on the same brief. Most of the 20-40M input tokens per job were
that long history replayed, not the images.

The `vision-window` plugin (enabled on creator and the three hands) rewrites
native `vision_analyze` results through the `transform_tool_result` hook, with
no Hermes core change:

- The 4th and later image in one step returns "Image not shown: <path>. Only 3
  images can be shown to you per step ... request it again in your next step."
  The model is told the truth instead of a false "loaded".
- An image whose bytes were already shown 3 times in the turn returns "Image
  not shown again ... Use what you already noted about it." This stops
  flip-flopping comparisons; a re-rendered file has new bytes and is shown.

Which three of a parallel batch are shown follows completion order. Verified
on an isolated home with the unmodified runtime (6 parallel frames: 3 shown, 3
"not shown", and the model reported exactly which). Leaf procedures keep their
rules: contact sheets, at most three looks per step, a finding in `qa.md`
before the next look.

### Migration

Each family moves on its own, each step verified before the next: (0) contract
+ validator, (1) the hands skeleton, (2) the family's leaves proven from the
hands' own CLI with a pasted filled form, (3) Creator routes that family to the
hands while every other family stays on its technic, (4) the assistant's legacy
plan leaf, QA contract and the creator technic for that family retire, (5) soak
from both clients and record what the form got wrong. Nothing is retired in
bulk. Retire legacy capability only after replacement caller coverage and the
both-client soak — not merely because a leaf exists; a technic's card goes once
every family it covered has moved. When the last family moves, `legacy/` goes,
and so do `image_gen` / `video_gen` / `tts` / `unreal-engine` from Creator's
toolsets. The abandoned `refactor/creator-profile` branch is read only for
scripts worth porting.

| Family | Hands | Leaves | Legacy retained / retirement gate |
|---|---|---|---|
| icon | image-creator | source, create, generate, edit, analyze | `creator-logo-icons` and its assistant plan/QA retired; both-client soak (step 5) still open |
| emoji | image-creator | create, generate, edit, analyze | never had a technic; published glyphs use `source-icon` |
| mascot | image-creator | generate, edit, analyze | no technic mapping |
| reimagine | image-creator | generate | no technic mapping |
| kit | image-creator | source, create, generate, edit, analyze | no legacy family maps 1:1; nothing retired |
| card | image-creator | create, generate, edit, analyze | `creator-text-card` and private-overlay mappings kept until handoff coverage, paid live validation and legacy caller migration prove retirement safe |
| clip | video-creator | generate, edit, analyze | `creator-generated-video` and its assistant plan/QA kept for explicit legacy coverage (e.g. local ComfyUI) |
| music-video | video-creator | generate | broader legacy video kept; nothing retires on partial MV coverage |
| tour | video-creator | create | `creator-html-motion` and its 1:1 mappings kept intact |
| ad | video-creator | analyze, create (`generate-ad` planned; an authored PV is create-promotion) | no legacy mapping retired |
| explainer-video | video-creator | create | `creator-manim-explainer` kept for explicit Manim / math / 3D scope |
| promotion | video-creator | create | `creator-html-motion` kept, narrowed in routing to what no served video leaf covers (overlays on footage, captioned narration, audio-reactive, >60 s); its 1:1 mappings kept until caller coverage and both-client soak |
| story | video-creator | create | `creator-html-motion` kept for captioned narration and pieces outside the served scopes; nothing retires on this leaf alone |
| master | video-creator | create | `creator-media-assembly` kept, narrowed in routing to what create-master does not cover (overlays on footage, segments' own sound, ducking, edit-spec trims); its mappings kept until caller coverage and both-client soak |
| speech | audio-creator | generate, edit, analyze | voice card, assistant plan/QA and canonical TTS special case retired; AudioCraft/HeartMuLa/songsee technics withdrawn without replacement |
| sfx | audio-creator | create, generate, edit, analyze | no technic mapping |
| music | audio-creator | create, generate, edit, analyze | vocal-song generation and standalone audio visualization withdrawn, not migrated |
| mix | audio-creator | create, edit, analyze | no technic mapping |
