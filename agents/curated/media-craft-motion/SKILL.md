---
name: media-craft-motion
description: Use when planning, directing, animating, or reviewing motion and camera choreography in a produced clip, product tour, ad, explainer video, or music video — timing and spacing of moves, position/motion continuity across cuts, UI pointer-to-state choreography, explainer visual state changes independent of narration, generative-model shot briefs and identity control, and reviewing rendered motion for smoothness and cut boundaries. Does not cover pure trim/re-encode/analyze-metadata edits with no motion decision, and does not impose a required camera rule, fixed duration, or mandatory motion count — deliberate cuts, held stillness, and reduced motion are valid choices, not defects.
license: MIT
---

<Goal>

Give an agent planning or reviewing motion in a produced piece — clip,
product tour, ad, explainer video, or music video — the judgment to make and
evaluate purposeful motion decisions, instead of applying a fixed animation
formula. This is a knowledge skill: it has no scripts, no render pipeline,
and no required workflow. It does not run independently of the client's
actual tools and approval constraints, which always take precedence.

</Goal>

<Scope>

Covers the craft judgment behind: timing and spacing of a move, continuity of
position and motion across cuts, UI motion that responds to pointer contact,
explainer visuals that carry state on their own, briefing and reading output
from generative video models, and reviewing rendered motion honestly.

Direction selection decides which audience effect or concept to pursue. This
skill owns the temporal execution of that chosen effect, not a new concept vote.

Does not cover: pure trims, re-encodes, container/codec changes, or
metadata-only edits that involve no motion decision. Does not require any
other skill and makes no universal claim about camera movement, shot
duration, or how many motion beats a piece must contain — a static hold, a
hard cut, or reduced motion can be the correct choice; this skill's job is to
tell a purposeful choice from an accidental default, not to forbid stillness.

</Scope>

<References>

Read only the reference(s) that match the task at hand; do not load all six
for a narrow request.

- [Timing and spacing](references/timing-spacing.md) — read when shaping how a single move
  feels: ease, acceleration, anticipation, and where to place visual focus,
  in any subject.
- [Continuity](references/continuity.md) — read when a sequence has more than one
  shot or state and cut discipline (matched vs. deliberate) is in question.
- [UI choreography](references/ui-choreography.md) — read for on-screen interface motion:
  pointer-to-state response, modal/backdrop relationships, and when a camera
  move is deserved versus decorative.
- [Explanation and performance](references/explanation-performance.md) — read for explainer or
  walkthrough content where the visual must carry a state change on its own,
  and for any brief involving a talking character or narrated rig.
- [Generated shots](references/generated-shots.md) — read when writing or evaluating a
  shot brief for a generative video model, including music-video shots cut
  to an existing track.
- [Motion review](references/motion-review.md) — read before reporting that rendered
  motion was checked, or before approving/rejecting a delivered cut.

</References>

<Discipline>

Treat every reference as craft judgment applied to the specific brief, not a
checklist to satisfy mechanically. Where a reference's worked cases show a
"retain" outcome, that is as legitimate an ending as a revision — do not
manufacture a change to look thorough. State the concrete evidence for a
call (timestamps, frame boundaries, confirmed model capability) rather than
an impression.

</Discipline>
