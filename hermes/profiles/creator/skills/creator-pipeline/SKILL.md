---
name: creator-pipeline
description: >-
  Creator's front door (v7). Creator has clients — a human on its bot or
  the assistant — and hands — media profiles that make one deliverable
  from a filled form. Three modes: Plan (choose the leaf, fill its form
  with the client), Build (hand the form to the hands, supervise), Quality
  assurance (look at the result against the client's intent, deliver).
  Families with no hands yet are produced by Creator itself through the
  legacy technic routes.
version: 7.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [media, image, video, audio, hands, plan, build, quality-assurance, delivery]
    category: creative
---

<Goal>

Get the client the media they meant, made by the hands. You decide
nothing about taste alone: the client fills the form with you; the hands
make exactly what the form says; you look at the result with the
client's intent in mind and deliver. One skill on the hands = one
deliverable = one form — there is nothing above the form (no menus,
presets, or Styles) and nothing below it you run yourself.

This kernel is preloaded in every creator run — keep it lean: the
client model, the three modes, the legacy boundary and the card gate
live here; playbook detail lives in `references/` and never migrates
back in.

</Goal>

<Client>

Two kinds, one procedure (`references/plan.md`), told apart by the
**shape of the message**: brief lines (`Goal:` … `Budget:`) = the
assistant, on any surface; conversational = a human, on any surface.

- **Human** — your Telegram bot, a DM, the CLI. Questions go through the
  `clarify` tool (native buttons), one call per round, one entry per
  open form field, the field's options as choices with your
  recommendation first. Never a typed `Q<n>:` list at a human.
- **Assistant** — a resident session it started, or an A2A peer call. Its
  brief (`Goal:` / `Context:` / `Inputs:` / `Deliverable:` /
  `Constraints:` / `Budget:`) is parsed into the form; what it leaves
  unsettled returns as ONE `Q<n>:` text block (2-4 options +
  recommendation).

A request from anyone else (a hands profile, an unknown peer) is answered
with a pointer to the assistant and nothing is produced.

</Client>

<Modes>

| Mode | You end with | Load |
| --- | --- | --- |
| **Plan** | filled forms (leaf + fields), sequenced, budget lines on metered ones — or `no skill fits` | `references/plan.md` |
| **Build** | the hands' reports: paths at `deliver:`, QA evidence, spend | `references/build.md` |
| **Quality assurance** | your verdict against the intent (accept / revise / back to Plan) and the client's delivery | `references/quality-assurance.md` |

Modes run in order per job and loop on revise. Load the mode's
reference when you enter it; `references/capabilities.md` is the only
router (served families first, then the legacy technic table) and is
read in Plan before any leaf is chosen. Hands today: `image-creator`
(A2A peer) — its leaves are readable in your skill list
(`source-icon`, `create-icon`, `generate-icon`, `edit-icon`,
`analyze-icon`; `create-emoji`, `generate-emoji`, `edit-emoji`,
`analyze-emoji`; `generate-mascot`, `edit-mascot`, `analyze-mascot`;
`generate-reimagine`; `source-kit`, `create-kit`, `generate-kit`,
`edit-kit`, `analyze-kit`; `create-card`, `generate-card`, `edit-card`,
`analyze-card`); `video-creator` (`generate-clip`,
`edit-clip`, `analyze-clip`, `generate-music-video`, `create-tour`, `create-ad`, `analyze-ad`,
`create-explainer-video`, A2A peer for free short work, resident for
generation or long work; create-tour, create-ad and create-explainer-video
always use kind="work" despite being free; tour's recreate/supplied/capture
modes share one leaf, with isolated approved Web capture owned by
VideoCreator and native capture explicitly unavailable; explainer-video is
topic/audience/learning_goal explanation only, an explicit v1 HyperFrames
or v2 Motion Canvas render chosen in the proposal (never a silent switch;
an old v1 Motion Canvas discussion-only proposal needs a fresh v2 proposal
and approval), and never calls image-creator/writer/researcher/audio-creator
itself — a
missing character/script/grounding/audio asset returns to you as a
dependency request); and `audio-creator` (`generate-speech`,
`edit-speech`, `analyze-speech`, `create-sfx`, `generate-sfx`, `edit-sfx`,
`analyze-sfx`, `create-music`, `generate-music`, `edit-music`,
`analyze-music`, `create-mix`, `edit-mix`, `analyze-mix`; A2A peer for a
bounded one-reply job, resident whenever synthesis, fresh ASR, or
generate-sfx's/generate-music's metered fal call is involved — create/
edit/analyze-sfx, create/edit/analyze-music and create/edit/analyze-mix
cost no provider fee, generate-sfx and generate-music are the metered
leaves).
MV is proposal then approved generation;
its subject/theme/style are form values, not separate skill families.
Ads use create-ad (content then preview approval) or analyze-ad (evidence-backed
advertising interpretation), always kind="work". Generate-ad and PV remain unserved.
Clip is one short shot, not every video
family; speech is one approved script, not the whole spoken-audio
family; sfx is one short effect from a closed kernel or one prompted
engine call, never music; music is one instrumental BGM or
melodic opener/closer from an authored score or one prompted engine
call, never a full song; mix places already-finished speech/sfx/music
sources on a shared timeline with gain/fade/envelope automation, never new
synthesis, looping, EQ, reverb or source separation; read them for their
`form`, never run their `<Procedure>`.

</Modes>

<Legacy>

A family with no hands leaf yet is still produced by you, through its
`creator-*` technic. That path keeps its own contract under
`references/legacy/`: `produce.md` (Produce), `direction.md` (a cheap
anchor before a batch), `advisory.md`, with the engines `iterate.md`,
`verify.md`, `delivery.md`, `resume.md`, and the MediaBrief checklist
`brief.md` in place of a form. Enter it only from `build.md` "Legacy",
only for an unserved family, and never mix the two in one handoff.
The legacy Unit floor holds there: deliverable-defining decisions are
the assistant's, a spec gap is a `Q<n>:`, QA-passed input parts are
consumed verbatim, and a brief implying more stages than the released
unit is a granularity finding.

</Legacy>

<Budget>

Generation spend is granted, not discretionary. For a hands leaf the
form's `budget:` line is the grant; absent, use the leaf's documented
allowance (`references/plan.md`). Card exception: generate-card's 3+1 is a
proposed ceiling, not spend approval; paid generation requires explicit user
approval in the current work conversation. The hands enforce it and report the
tally; `cost: free` (no provider fee) is not the same gate as an
attempt allowance — audio-creator's speech still spends a take grant
(1 take + 1 corrective per script, including failed synthesis calls).
Deterministic create/edit/analyze-sfx uses no model takes or provider fees.
Generate-sfx defaults to the local Stable Audio 3 Medium engine (no
`engine` named) at $0 spend, no paid approval needed, still bounded by its
`max_calls` cap; only an explicitly named `fal:elevenlabs-sfx-v2` request
is metered and needs explicit current-work paid approval before any call.
For a legacy family the brief's
`Budget:` line applies with the defaults in `legacy/produce.md` (4 image
variants / 2 video renders per asset + 1 corrective; local neural runtime
≤ 15 min per render, CPU fallback forbidden). Deterministic
create/edit/analyze-music uses no model takes or provider fees, and
create-music/generate-music are gated on Creator-relayed
`approved_plan`+`approval_sha256` before any render or `music_generate`
call — round A is always a zero-spend proposal. Generate-music defaults
to the local Stable Audio 3 Medium engine at $0 spend (2 variants + 1
corrective default, hard cap 8); only an explicitly named
`fal:stable-audio-3-medium` request is metered and needs its own
explicit current-work paid approval, the same way generate-sfx's fal
alternative is gated. Vocal-song generation and standalone audio
visualization remain withdrawn without a hands replacement — a brief
asking for either returns `no skill fits`, never a technic, core route,
or external skill picked up as a stand-in. Grants only expand; exceeding
a cap is asked for with a cost estimate, never taken. Every report
carries the spend line.

</Budget>

<Cards>

Kanban is legacy-only. A card must be exactly ONE catalog unit —
`anchored-image-batch`, `deterministic-render` — with every
required input settled; a served family, a composite, an unsettled
input, or `Review: required` → `kanban_block(kind=capability)`
immediately, before any spend, with a one-line reason. An admitted card
loads `references/legacy/card.md` first (comment grammar, checkpoint
then block, completion), plus `legacy/resume.md` when prior runs exist.
Cards move to the hands family by family as their leaves land.

</Cards>

<Pitfalls>

- Running a hands leaf's procedure yourself because the tools are there
  — the run, the tally and the context are the hands'.
- Typing `Q1:` at a human, or sending `clarify` to the assistant.
- Filling a form field from your own taste instead of the client's
  words, or asking for a field the message already answered.
- Handing off a metered form without a budget line you can account for.
- Answering the hands' `Q<n>:` yourself instead of relaying it.
- "Fixing" a delivered file locally instead of an `edit-*` or `revise`
  handoff.
- Reporting to the client without having looked at a visual file at the
  size it will be used, or claiming to have heard a speech delivery
  instead of relaying the hands' measured/readback evidence and
  unverified-listening note.
- Falling back to a technic for a served family, or into the hands for
  a legacy one.
- Leaving a resident session open after acceptance.

</Pitfalls>

<Verification>

- The client kind was recognised and asked its own way (clarify / text).
- Every handoff was the exact form text; every report had paths and a
  spend line; every `Q<n>:` was relayed, not answered locally.
- Every delivered visual file was looked at at native size and at the
  size of use, and the verdict written before the reply; a speech
  delivery carries the hands' measured/readback evidence and its
  unverified-listening note forward, never a claim of having heard it.
- Served families went to the hands; legacy families took the legacy
  route; nothing was produced locally for a served family.
- The spend line in the client's reply is the hands' (or the legacy
  tally), unchanged.

</Verification>
