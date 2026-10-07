# Creator

Creator as creative advisor. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Creator as creative advisor

Creator answers creative-direction questions; it neither produces media nor
commissions the hands. It owns two translations:

- **Intent into directions**: a client's settled intent becomes a few concrete,
  named directions the user can choose between.
- **Feedback into revisions**: a user's own words about a storyboard, draft or
  delivery become located, named changes.

The Assistant owns everything around those translations: the user's goal and
decisions, filling and sending the hands' forms, approvals, budgets, consent and
delivery ([broker.md](../broker.md)). The hands own production, their
storyboards and proposals, and their self-checks
([hands/overview.md](../hands/overview.md)).

The split follows the blind studies under
`~/Workspaces/Projects/Acme/docs/hermes-studies/`. The storyboard author
decided a film's rating, whoever implemented it. A named technique vocabulary
given to that author raised ratings. A rules layer, self-critique, an
independent critic and designs authored above the producer lowered ratings or
left them unchanged. Creator therefore supplies vocabulary and choices. It never
writes a design that binds the producer, and it never judges a result.

### Client

Creator's one client is the Assistant, through `specialist_call`; it has no
Telegram bot, and nothing else calls it. A bounded proposal or revision list is
an A2A `kind="inquiry"` answered in one reply. Work that has to look at several
media files or takes several turns is a resident `kind="work"` conversation. A
runtime specialist handoff is agent-authored; a relayed choice is the user's
only when the Assistant says so, never inferred from message shape.

### Entries

`creator-pipeline` (v10) is the kernel; its two independent entries sit outside
`references/`:

| Entry             | Input                                                                                                                              | Returns                             |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| `propose-creator` | settled intent: purpose, audience, destination, fixed words, exclusions, supplied inputs and what each is for; optional references | 2-3 directions and a recommendation |
| `revise-creator`  | the artifacts (storyboard, draft, delivery, review sheets) and the user's verbatim feedback                                        | located changes                     |

**Directions.** Each direction gives what the viewer sees in plain words, the
vocabulary names it uses and where they come from, an example that already
exists (a leaf's sample asset, a style note, an earlier delivery or a supplied
reference) and the leaf with a draft handoff (`skill / intent / deliver /
budget / form`) the Assistant can send unchanged. With no example to show, the
direction proposes the leaf's representative sample unit instead. A direction
never contains a storyboard, timeline, frame specification, layout or pixel
size. For authored video it travels in the form's existing fields and `note`,
and video-creator writes the storyboard.

**Changes.** Each change names its position (a storyboard beat, or a time and
frame), what is seen there now and the named change, plus a draft revision
handoff (`intent: revise <path>` with the changed fields or `note`). A change
that alters what a storyboard approval covers (beats, timing, copy, audio plan)
is marked as needing a new approval. There is no score, verdict, ranking or
unrequested critique: the user decides.

A request whose required form fields the user's own words already settle does
not reach Creator at all; the Assistant commissions it directly.

### Vocabulary and feasibility

Creator reads its vocabulary in place and never copies it:
video-creator's `references/motion-vocabulary.md`, each leaf's form and option
references (styles, themes, destinations), the hands' `references/craft.md` and
the curated `media-craft-*` skills. One plain reference per served subject,
`references/<hands>/<subject>.md`, says what that leaf can express: its range,
its options, its boundary with neighbouring leaves and where its examples live.
The validator requires exactly one per served subject.

A direction only names what a served leaf can make. Technique names (GSAP,
Three.js, shaders) appear only where the selected leaf supports them, such as
an explicit `graphics: three-webgl2` option; missing runtime support is a named
capability gap for engineering, never a reason to propose an unsupported
method. A request no leaf fits returns `no leaf fits` with the missing
capability.

### Boundaries

- **No production.** Creator has no image, video, music, SFX or TTS
  generation, no hands targets, no kanban card units, no `clarify` and no
  production delegation. Its tools read: files, vision, the web, skills and
  memory, plus the shared media inspection tool below.
- **Media inspection.** The generic `media_inspect` tool (plugin
  `inspection/media-inspect`, shared with the Assistant like the `social/` and
  `messaging/` access plugins, each profile offered its own action list)
  probes a media file and writes stills or a contact sheet at named times or
  frames into a scratch directory under the OS temporary directory. It never
  writes into a deliverable or a `deliver:` directory.
- **Outbound.** `specialist_call` reaches Researcher only, for evidence a
  direction depends on.
- **Approval.** A chosen direction is the user's decision, relayed by the
  Assistant; Creator's recommendation never approves a proposal, preview or
  spend.
- **Audio.** Directions and changes for sound are expressed through form
  fields and named techniques; Creator never claims to have heard anything.

### Model

Creator stays on Opus 5.5 ([models-auth.md](../models-auth.md) "The Creator
family splits by hand").

### Acceptance

The advisor path is accepted only by a blind comparison against the current
best path (the Assistant passes intent and video-creator writes the storyboard
with the vocabulary): it must not rank below it, and it must cut elapsed time
and the user's round-trips.
