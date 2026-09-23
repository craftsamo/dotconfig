# Creator hands — overview

The v3 hands contract: client model, skill tree, form, handoff, media craft, migration. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Creator hands (v3, 2026-09)

Creator's production is moving, one asset family at a time, out of the 23
generic `creator-*` technics and into **hands** profiles — `image-creator`
(A2A `:9907`), `video-creator` (`:9908`), and `audio-creator`
(`:9909`) — each a receive-only A2A endpoint with the tools of its medium
and nothing else. Two earlier shapes failed in opposite directions and this
section exists so the third does not repeat either: the technics
**decided nothing** (a "generated image" leaf that accepts any size, look
and tool still needs the whole spec written from scratch, so 23 assistant
plan leaves + a QA index had to be sewn to them 1:1), and the
`refactor/creator-profile` branch **governed everything** (director + three
hands + menu.yaml + generated MENU.md + presets + cross-media Styles +
palette roles + grammars: thirteen interpretive layers between a request
and a tool call, the same choice encoded in five places, and the docs drifted
before the branch was done). The v3 rule is: **one skill = one concrete
deliverable = one form**, nothing above the skill but a reader.

### Client model

Specialist transport preserves the original agent request and a per-turn
private handoff record, distinguishes current instructions from non-actionable
history, and identifies the caller as an agent even during conversational
follow-ups. This is provenance for inspection, not authenticated human approval.
Keep relayed human decisions with their source/proposal/scope separate from
agent implementation choices. Do not weaken the outcome to match a template;
use the granted discretion without unnecessary repeated questions.

Creator has **clients**, not entry points. A client is either the human
(Creator's own Telegram bot) or the assistant (resident session / A2A,
carrying a SessionBrief). Creator's job is the same for both: pick the
skill, **fill its form** — with the `clarify` tool when the client is
human (Telegram renders one inline button per option; the form's
`options` become the choices, `other: true` is the UI's own "Other" row),
by parsing the brief when the client is the assistant, returning a text
`Q<n>:` block for whatever required field it cannot fill, hand the filled form to the hands, gate the
result against the intent (visual inspection or audio evidence), deliver.
The hands never see the client or invent its requirements: they receive a
filled form or return `Q<n>:`. A leaf may own creative execution within that
form (MV direction, for example), with its explicit proposal approval gate.
The assistant keeps
delivery to the user, the durable path, Budget lines and GitHub bookkeeping;
it does not make production decisions on Creator's behalf. Its outcome guides
support Client dialogue; the old production decision leaves now live at
`plan-assistant-creative/references/legacy/<family>.md`, with their QA `Covers` mapping under
`qa-assistant-creative/references/legacy/`. Those old mappings retire family by
family only after replacement coverage and real-use gates (Phase 4 of the
migration), independently of the Client guides.

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
draft are separate facts. The verification command in `AGENTS.md` checks routing
coverage for all hands, real skill discovery and the profile/runtime regressions;
subjective comprehension and live save behavior still need actual-use evidence.

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
  waveform (free local synthesis or metered provider); `edit` — transform an existing asset (free unless the
  edit itself generates); `source` — fetch a published asset and record its
  license (free); `analyze` — inspect an existing asset and return findings,
  not new/repaired media (free). Most analyze leaves return reply findings;
  analyze-ad may retain its report and evidence at an explicit deliver path
  for a later creative brief, never a new ad. The `create`/`generate` boundary is whether a
  generation model is asked to draw.
- **Cost is independent of verb.** `free` means no metered media-provider fee,
  not zero reasoning cost or unlimited compute. Local speech synthesis still
  has a take allowance: one take plus one corrective per script by default.
  Failed synthesis invocations count. Long free work still uses resident sessions.
- **Subjects** are concrete nouns (`icon`, `hero`, `clip`, `voice-line`),
  **unique across all hands** because Creator reads every hands' tree through
  `skills.external_dirs`; the validator rejects a subject that appears under
  two hands. `name` equals `<verb>-<subject>` and equals the path.
- The pipeline root holds no router and no lifecycle beyond the five steps
  above; discovery is Creator reading the leaves' front matter directly. No
  generated index, no `menu.yaml`, no preset layer, no shared Style system,
  no palette vocabulary above the leaf. A leaf's execution-environment traps
  (Japanese `。` in an argv string trips the terminal guard → text travels as
  a file; foreground terminal calls die at 420 s → long renders run
  `background: true` and are polled; vision holds ~3 images → contact sheet
  first, then one frame at a time with the finding written down) are written
  into that leaf's Procedure, not into a shared note.

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
existing mandatory `references/styles/` mapping. This lets kit content
tables live under `references/contents/` without a generated registry.
Theme uses `references/themes/`; an explicit `references` declaration makes
option backing mandatory even when the directory is missing. MV keeps style
(rendering), theme (world vocabulary) and direction (staging) within one leaf.
Multi-value text fields describe their comma-list syntax in the label;
`other: true` permits that string at intake, and the leaf validates each
member. An option is not a requirement to generate every default item:
Creator confirms the expanded item list and spend before batch production.

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

### Media craft knowledge

Create-ad's explicit `purpose: study` is a 1..10s diagnostic unit with a concrete
question and real copy but no CTA or Mix mode. Its separately approved plan uses
`freeze-study`; the ordinary snapshot approval then releases `render-study`.
The frozen purpose is bound into preview integrity and cannot run through final
render. Output is study.mp4 with final_eligible=false, never an ad delivery.
Final-ad schemas/bytes and 6..30s/CTA requirements stay unchanged. Both purposes
have a read-only `preflight --plan --assets` to check actual suffix/path/size/hash
and vendor compatibility before source authoring. Passing it proves neither
source compatibility nor a visual result. Other subjects use existing supported
representative units; they do not inherit an ad study flag or extra attempts.

The four tracked, portable `media-craft-direction`, `media-craft-visual`,
`media-craft-motion` and `media-craft-audio` skills live in `agents/curated/` and
use the standard shared-store install links. Creator already reads that store;
image-creator pins direction/visual, video-creator direction/visual/motion, and
audio-creator direction/audio individually. No hands receives the whole store.
Each hands kernel's `references/craft.md` maps its existing subjects and actual
creative decisions to conditional knowledge. Creator's three entries share its
own `references/craft.md`; confirmed legacy production uses that same knowledge
without retiring or silently replacing its methods.

These are technique and judgment resources, not new forms, producer roles,
cross-media Styles or permissions. Local procedures still own engines, source
integrity, proposal/preview approvals, budgets and QA commands. Required craft
must be present for an affected creative decision; missing or ambiguous bodies
stop that decision with a finding, while mechanical work and optional technical
fallbacks remain unchanged. Audio acceptance uses attributed human listening;
meters and ASR never become a listening verdict. Fresh conversations are needed
after an explicitly approved install/cutover. Existing jobs and frozen outputs
are not migrated. Structural/discovery tests do not prove artistic improvement.

### Migration

Family by family, each step verified before the next: (0) contract +
validator, (1) `image-creator` skeleton, (2) the family's leaves proven from
the hands' own CLI with a pasted filled form, (3) Creator routes that family
to the hands while every other family stays on its technic, (4) the
assistant's plan leaf and the creator technic for that family retire, (5)
soak from both clients and record what the form got wrong. The first family
is `icon` (`source` / `create` / `generate` / `edit` / `analyze`). Nothing is
retired in bulk; `refactor/creator-profile` is read only for scripts worth
porting (`icon-fetch.sh`, `tour.py`, `explainer.py`, `item-loop.py`).

**Creator's own pipeline is shaped for this** (v9): Plan →
Build → Quality assurance, selected through `plan-creator`, `build-creator`
and `qa-creator`, each owning `references/<hands>/<subject>.md` as described
in [`broker.md`](../broker.md) "Broker shape".
The technic-era routes remain under `references/legacy/` for the families
still to move. This reference split retires no production family. Each family that
lands on a hands deletes its technic, its assistant plan leaf and QA
contract, and — once every family it covered has moved — its card. When
the last family moves, `legacy/` goes, and so do `image_gen` /
`video_gen` / `tts` / `unreal-engine` from Creator's toolsets.

Done 2026-09-05 (icon): steps 0-4 — validator rules, `image-creator`
(:9907, in the multiplex allowlist), the five leaves each proven from the
hands' CLI, Creator routing icon to the hands (`references/hands.md`,
`a2a_agents.image-creator`), `creator-logo-icons` retired together with
the assistant's then-current `plan/creative/logo-icons.md` and the `icon-set.md` QA
contract. Both client paths verified from the CLI: a human sentence →
`a2a_call` with the filled `source-icon` form (56 s end to end); an
assistant SessionBrief without a style → `generate-icon` form filled and
ONE `Q1:` on `style` with three options, no spend. Pipeline v7 verified
the same way plus a legacy family (an OG text card → `creator-text-card`,
zero spend, 57 s). Step 5 (soak from the Telegram bot and from assistant
sessions) is open.

Done 2026-09-05 (emoji): the second family, same steps. Prerequisite
found on the way: the `image-fallback` chain never declared
`capabilities()`, so `image_generate` hid `image_url` /
`reference_image_urls` from every profile — fixed in the plugin (the
chain reports the first available member's surface and skips text-only
members for image-carrying calls). One shared script, `emoji-fit.sh`,
is the only home of the platform table (slack / discord 128 PNG,
telegram 512 WebP + stroke, telegram-emoji 100 WebP, line 180 PNG;
`--spec` prints a row for `analyze-emoji`). `generate-emoji` is the
first TWO-ROUND leaf: without `anchor` it draws three character sheets
and stops; `intent: revise` + `anchor:` draws the pack on that one
reference. Earned on Lethe (12 expressions, telegram): identity held
across all twelve; the pack needed `--cutout key` (background trapped
between long side locks and the shoulders — unreachable by the corner
flood at any fuzz) and four correctives, every one of them a prop that
had vanished at 32 px — so the expressions pack now writes every prop
large, saturated and off the hair, and `thinking` carries a blue "?"
instead of a skin-on-skin hand. `create-emoji` (文字絵文字, Hiragino
Sans W8, text via an items FILE) and the two free leaves earned on the
same pack: `edit-emoji` re-cut it for Slack, `analyze-emoji` found white
steam invisible on white hair and that a 12-tile strip exhausts a run's
vision looks (packs over six are read in halves; an unreached check is a
GAP). No technic retires with this family — emoji never had one —
and there is no `source-emoji` on purpose: `source-icon` with
`icon: twemoji:<name>` covers published glyphs. Both client paths
verified from the CLI: a human sentence (three text emoji for Slack) →
`create-emoji` form → `a2a_call` → three files delivered with the hands'
QA relayed; an assistant brief without a style → `generate-emoji` form
filled and ONE `Q1:` on `style` (plus a `Q2:` offering the prior
approved anchor to skip round A), zero spend. The human run also caught
the hands patching `text-emoji.sh` in place — the contract said report,
not patch — so `skill-topology` now blocks writes into tracked skill
roots at the tool layer.

Done 2026-09-05 (mascot): the third family, same steps, three leaves —
`generate-mascot` (two rounds: three full-body concepts + a silhouette
sheet, then `anchor:` + `pack:` turnaround / poses / custom),
`edit-mascot` (background swap incl. a chroma key that re-composites the
cut-out on flat `#00ff00`, head / bust crop, resize, outline — never a
recolour) and `analyze-mascot` (square / cut-out / silhouette / 64 px /
light-dark / measured palette vs asked / identity vs anchor). No
`source-` or `create-mascot` on purpose: a mascot is designed, not
fetched, and a first-party mark becomes an icon set. The finish is
`mascot-fit.sh` (corner flood or global key, `key_px` in its RESULT).
Earned on Forge (a work-robot, game-2d, electric blue + storm grey):
the FIRST run never reported — it looked 152 times at three candidates,
because each image leaves the context three looks later and the model
had written nothing down between looks; the pipeline root now requires
every finding appended to `qa.md` before the next vision call, and round
A is exactly three looks (sheet, silhouette, the recommended one at
native size — no per-candidate look). Same run: on a white `<bg>` the
finish's `key_px` counted eye whites and speculars (thousands on a
clean cut-out), so a mascot is drawn on chroma green (magenta when the
palette has green), never white — and on green the count caught real
background trapped between arms and body and inside the claws, cleared
by `--cutout key` with no coverage loss. The second run: round A in
4 min, round B held identity across eight poses on one corrective (an
`oops` sweat drop too pale and on the head — the emoji prop rule
again). The free leaves on the same delivery: `edit-mascot` re-keyed the
pack for video and cut a head avatar (the 0.40 head default cut the
chin on a big-headed build → 0.50), and `analyze-mascot` found the one
pose whose rig drifted from the anchor (black mitts, long boots) that
round B's own sheet look had passed, plus two instrument lessons — a
20 % key detector read a saturated artwork blue as a leak (now 8 %
around green / magenta only) and a three-colour palette scored FAIL on
its own line-art ink (ink and highlights are tagged, not scored). The
write guard also refused `cp … && <skill script>` as a write into the
skill tree: a skill script runs in a command of its own. Both client
paths verified from the CLI: an assistant brief without a style →
`generate-mascot` form filled and ONE `Q1:` on `style` (three options
with a recommendation), zero spend, 45 s; a human sentence (this
concept, chroma key for video) → `edit-mascot` form → `a2a_call` → the
file delivered with Creator's own measurement of the key, 2 min.

Done 2026-09-05 (reimagine): the fourth family is ONE metered leaf,
`generate-reimagine` — a client's photo re-rendered in a style
(3d-character, comic-book, chibi, 70s-street, 80s-anime, or described)
with the same subject, pose and composition. The photo is the EDIT
INPUT (`image_url`), never a `reference_image_urls` entry; the hands
look at it once and write `subject.md`, the identity lock every look
is judged against (`keep: identity` relaxes it to the subject alone);
one or several styles per form, two candidates each, finished to the
photo's own size next to a photo-plus-candidates sheet per style. No
edit- or analyze-reimagine on purpose: size and format are the leaf's
own fields and identity against the photo is its own QA. Earned on a
rose hedge (comic-book + 80s-anime, then 3d-character as a revise on
the same lock, then chibi from the human path): three of the first
four candidates came back as the photo with a saturation filter — an
edit model keeps the photograph's texture unless told what the picture
IS — so every style reference now opens with a **Medium** line
(redraw / repaint / rebuild / re-photograph; the photo's own texture
must go) and the prompt leads with it; the corrective that did so
passed and every later first pass passed on style. The one shared
corrective left the second style with a named defect and nothing to
spend, so the budget is 2 + 1 corrective PER STYLE. gpt-image-2
transposed a landscape call twice in a row: prompts end with the
canvas spelled out ("a WIDE HORIZONTAL landscape image, do not
rotate"), every raw is measured as it lands, and a transposed raw is
marked failed rather than cover-cropped in half. A corrective rebuilds
the sheet with every candidate; `qa.md` is appended, never rewritten
(one look was lost to a whole-file write). The 80s-anime cues now tell
a figure (cel line) from a place (background art) and forbid opening a
sky the photo does not have; chibi has a reading for a photo with no
figure in it (the touch, not an added character). Both client paths
verified from the CLI: an assistant brief without a style →
`generate-reimagine` chosen, the surviving run on the same photo found
and inspected, ONE `Q1:` on style with the three existing candidates
as options and a `Q2:` on size, zero spend, 100 s; a human sentence
(chibi, one candidate, consent to upload given in the sentence) →
form → hands → delivered in Japanese with Creator's own look and the
hands' maintainer note relayed verbatim, 1 call, 5.5 min. Creator's
plan.md carries the consent rule: a human client hears that the photo
leaves the machine in the SAME clarify round as the style, never
after.
