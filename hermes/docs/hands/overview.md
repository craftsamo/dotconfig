# Creator hands — overview

The contract shared by the three media hands (image-creator, video-creator, audio-creator): client model, skill tree, form, handoff message and media craft knowledge. Read it before adding or changing a hands leaf. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Creator hands

Media production runs in three **hands** profiles — `image-creator`
(A2A `:9907`), `video-creator` (`:9908`) and `audio-creator` (`:9909`). Each
is a receive-only A2A endpoint with the tools of its medium and nothing else.
The Assistant commissions them; Creator only advises. Family details:
[`image.md`](./image.md), [`video.md`](./video.md), [`audio.md`](./audio.md);
the client side: [`broker.md`](../broker.md).

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
agent implementation choices.

The hands have one **client**, the Assistant. It picks the leaf, **fills its
form** from the user's words and relayed decisions (with Creator's draft
handoff when Creator was consulted), sends it, relays proposals and approvals,
and delivers. The hands never see the user or invent requirements: they
receive a filled form or return one batched `Q<n>:` text block. A leaf may own
creative execution within that form (a storyboard or MV direction, for
example), behind its explicit proposal approval gate. A request from any other
caller is answered with a pointer to the Assistant and nothing is produced.

Creator reads the forms and option references to propose directions and
revisions, but never sends a handoff and never receives a report. When to
consult it, and how a `Q<n>:` is answered: [`broker.md`](../broker.md). A stuck
resident transport is closed with `specialist_session(action="reconcile")`
([`profiles/specialist-calls.md`](../profiles/specialist-calls.md)); a
bookkeeping close is neither acceptance nor evidence that a retry is safe.

Acceptance follows the initial audience/outcome and the actual returned version,
not the producer's chosen metaphor or successful process exit. Revisions
invalidate only affected evidence; local acceptance, preview approval and a
reopened service-side draft are separate facts.

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
  existing asset; `source` — fetch a published asset and record its license
  (free); `analyze` — inspect an existing asset and return findings, never
  new or repaired media (free). The `create`/`generate` boundary is whether a
  generation model is asked to draw.
- **Cost is independent of verb.** `free` means no metered media-provider fee,
  not zero reasoning cost or unlimited compute: local speech synthesis still has
  a take allowance and failed invocations count.
- **Subjects** are concrete nouns (`icon`, `hero`, `clip`, `voice-line`),
  **unique across all hands** because the Assistant and Creator each read every
  hands' tree through one `skills.external_dirs` list; the validator
  (`validate_hands`) enforces the shape. `name` equals `<verb>-<subject>` and
  equals the path.
- The pipeline root holds no router and no lifecycle beyond the five steps
  above; discovery is the client reading the leaves' front matter directly.
- Hands report a defect in a leaf's own scripts or references to the
  maintainer; they never patch tracked skill roots (`skill-topology` blocks
  such writes at the tool layer).
- **Execution-environment traps** (terminal-guard limits, foreground timeouts,
  vision-window habits) go into the Procedure of the leaf that hits them, not
  into a shared note.

**Instruction context.** The hands' always-on contracts re-evaluate the named
leaf and selected references on inbound turns/completions and before a changed
operation, subject or option. The executing profile's full kernel and required
instructions must be in current context, not merely recorded as loaded;
unrecoverable required instructions stop the action, optional advisory
references keep their fallback. Loading never grants a new operation, resets
spend or reruns a completed render. The Assistant or Creator reading a hands
form does not become that hands' executor.

### The form (front matter is the only representation)

<!-- prettier-ignore -->
```yaml
---
name: generate-icon
description: >-
  <one sentence: what this leaf delivers, from which inputs>
metadata:
  hermes:
    category: hands
    hands: image-creator
    cost: metered                      # free | metered
    output: "icon_<slug>_<size>.png (transparent, square)"
    form:
      what_for: {required: true, label: "何のアイコンか", example: "Slack 通知 bot"}
      style:    {required: true, options: [flat-minimal, glass, pixel], other: true}
      note:     {required: false, type: text}
---
```

The validator is the authority on field keys. `options` + `other: true` is a
controlled vocabulary that still accepts a free value; a leaf
that has `references/<field>/` must back every listed option there (`style` maps
to `references/styles/`, `theme` to `references/themes/`; an explicit
`references` declaration makes the backing mandatory even when the directory is
missing). An option reference describes a look by its traits, never by a
studio, director, artist, title or brand: Creator proposes from it and the
hands build prompts from it, and a name invites imitation of someone else's
designs or a provider refusal. `note` is the escape
hatch every leaf carries. The SKILL.md body has exactly three sections —
`<Procedure>`, `<QA>`, `<Report>` — because `description` and `form` already
say the rest. An option is not a requirement to generate every default item:
the Assistant confirms the expanded item list and spend with the user before
batch production.

Hermes discovery reads only the first 4,000 characters of a SKILL.md before
parsing YAML, so a leaf's complete front matter must close inside that prefix
(use compact labels; keep full procedures in the body) — an incomplete fence
silently collapses sibling leaves into one parent-named skill even though the
topology validator passes.

### Handoff message (Assistant → hands, A2A or resident session alike)

```
skill: generate-icon
intent: new | revise <path of the previous delivery>
deliver: <Group root>/.agent/<YYYYMMDD>-<job>/
budget: 4 variants + 1 corrective          # media calls or local speech takes
form:
  what_for: Slack 通知 bot のアプリアイコン
  style: glass
  note: 青系、角丸は控えめ
```

The selected Group must already exist. Its draft job directory
`.agent/<YYYYMMDD>-<job>/` and job-owned descendants are accepted by all three
hands, as are the Group root itself and the unassigned
`~/Workspaces/.agent/<YYYYMMDD>-<job>/`. Everything under `.agent/` is a draft;
the Workspaces rules own promotion and cleanup. Never create a new Group or
relocate a valid Group-local job merely because it is below the Group root.
This is an operating contract, not a filesystem sandbox or upload/overwrite
consent.

The hands reply with the leaf's `<Report>` (paths, every QA check with its
evidence, spend) or with one batched `Q<n>:` block naming the missing
required fields — never with a substitute. A request no leaf fits is a
finding back to the Assistant (`no skill fits: …`), which tells the user and
records it for the maintainer; neither side improvises a leaf. Short free
single-reply leaves use `specialist_call(kind="inquiry")`; anything metered,
multi-turn or longer than one reply window uses `kind="work"`, continued with
the same target and returned conversation_id with inputs, permissions, budgets
and handoff text unchanged. A2A inbound cannot launch work and must ask its
caller to reissue the unit through a work conversation.

Transport limits: A2A identifies loopback callers by IP, not by a
cryptographically verified profile, so a verbal origin confirmation adds no
security; keep the localhost restriction and never widen the transport. All
three hands run in the single multiplex gateway; after a restart, readiness is
the agent card answering HTTP 200 plus listener ownership, not launchctl's
return. Never add a second gateway to work around an `Unknown toolsets: a2a`
warning.

### Media craft knowledge

The four tracked, portable `media-craft-direction`, `media-craft-visual`,
`media-craft-motion` and `media-craft-audio` skills live in `agents/curated/`,
not in hands' production trees or generated Styles catalogs. Creator's shared
store exposes them; image-creator pins direction/visual, video-creator
direction/visual/motion, audio-creator direction/audio individually, and the
Assistant pins direction. No hands receives the whole store. Each hands kernel's
`references/craft.md` owns conditional reading for its subjects; Creator reads
the same knowledge to name directions and changes.

These are technique and judgment resources, not new forms, producer roles,
cross-media Styles, permissions, outside workflows or executable scripts. The
optional HyperFrames technical pins keep their own leaf scope and fallback
([`video.md`](./video.md) "Video authoring references"); craft pins are a
separate knowledge-only exception. Local procedures still own engines, source
integrity, approvals, budgets and QA commands. Required craft bodies must be
current before the affected creative decision; missing or ambiguous knowledge is
a named stop for that decision, never an install or capability expansion.
Mechanical work skips the craft reading. Audio perception stays
human-reported: meters and ASR never become a listening verdict, and the shared
skill authorizes no new tool.

### Vision window

Hermes sends only the newest three image-bearing tool results with each
request; older native `vision_analyze` results read "Image loaded into your
context", so the model sees no image, assumes the load failed and asks again, in
a loop that replays a long history. The `vision-window` plugin (creator and the
three hands) rewrites those results through the `transform_tool_result` hook —
never fix this with a hermes-agent patch:

- The 4th and later image in one step returns "Image not shown: <path> ...", so
  the model is told the truth instead of a false "loaded".
- An image whose bytes were already shown 3 times in the turn is not shown
  again; a re-rendered file has new bytes and is shown.

Which three of a parallel batch are shown follows completion order. Leaf
procedures keep their own rules (contact sheets, at most three looks per step).

### Families and former technics

A family lands on its hands in steps, each verified before the next: (0)
contract and validator, (1) the hands skeleton, (2) the family's leaves proven
from the hands' own CLI with a pasted filled form, (3) both client-side
references ([`broker.md`](../broker.md) "References each side owns"), (4) a soak
through the Assistant, recording what the form got wrong.

Creator's former technics are not hands subjects: which became leaves and which
are archived is owned by [`broker.md`](../broker.md) "Legacy routes".

Families by hands (the leaves are the `<verb>/<subject>` directories; the
validator is the inventory):

- **image-creator:** icon, emoji, mascot, reimagine, kit, card, diagram,
  pixel-art, illustration. Published emoji glyphs use `source-icon`; there is no
  `source-emoji`.
- **video-creator:** clip, music-video, tour, ad, explainer-video, promotion,
  story, master, pixel-animation. A generated ad is `generate-clip` shots
  composed by `create-ad`; an authored PV is `create-promotion`.
- **audio-creator:** speech, sfx, music, mix.
