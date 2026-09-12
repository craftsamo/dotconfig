# Timing and Spacing

Timing is how many frames or how much duration a move takes. Spacing is how
far the subject travels between those frames — the actual velocity curve a
viewer perceives. The same duration can read as mechanical or alive purely
from how spacing is distributed across it: even spacing reads as constant
speed (linear, often robotic); spacing that starts sparse and packs tighter
near a stop reads as deceleration (ease-out); the reverse reads as
acceleration (ease-in). Treat timing and spacing as two separate decisions
for every move — fixing only the duration and leaving spacing linear is a
common way a "properly timed" animation still feels wrong.

## Ease as an authored curve, not a toggle

Ease is a velocity curve across the move's duration, not a boolean. A tool
that exposes it as keyframe handles on a graph of value over time (the same
idea Blender's animation editors call an F-curve, with each keyframe's
handle shape controlling the interpolation into and out of it) makes this
literal: a shallow handle near a keyframe holds a value longer before or
after it moves, and a steep handle rushes through it. Whether the authoring
surface is a real curve editor, a named easing preset, or hand-set timing on
a small number of frames, the same question applies: does the shape of the
curve match what the move represents (a heavy object should not ease as
crisply as a UI chip), or was a single default preset applied everywhere
regardless of what is moving?

## Anticipation must be sized to be read

Anticipation — a small counter-movement or pause before the main action —
prepares the viewer to register what is about to happen and to correctly
attribute the cause. It is only doing that job if it is actually perceivable
at the target duration and frame rate; a two-frame flicker before a snap cut
is not functioning as anticipation, it is noise. Size anticipation to the
scale of the action it precedes: a large, consequential state change earns a
longer or more visible wind-up than a small, frequent one, where a longer
wind-up would instead slow down repeated interaction.

## Focus and repeated novelty

A viewer's attention should land on the frame(s) where the meaningful state
actually changes, not spread evenly across the whole move. A held pose at
the moment of arrival, or a brief pause at the peak of a highlight, does more
work than uniformly smooth motion with no resting point. When several
similar elements animate in sequence (a row of cards, a list of stats),
identical timing and easing on every one is not automatically wrong — a
consistent, repeated rhythm can be the intended grammar of the sequence —
but if the goal is to hold attention on each new item as it lands, uniform
timing with zero variation can read as a template default rather than a
considered choice per item. The distinguishing question is whether the
repetition is doing a job (establishing a rhythm the viewer learns to expect)
or is simply the unexamined default the tool shipped with.

## Cases

**Revision — templated title cards.** Request: three title cards in a
product ad, each fading in and holding for 0.5s with identical linear
timing. Weak observation: the cards read as an unbroken, forgettable blur
because nothing about the timing distinguishes the third card, which carries
the call to action, from the first two. Cause: a single default duration and
linear ease applied uniformly with no relation to which card matters most.
Revision: keep the first two cards on the templated rhythm, but give the
final card a longer hold and an ease-out with a slight overshoot-settle so
its arrival reads as the destination of the sequence, not another repeat.

**Revision — snapping counter.** Request: a fitness ad's on-screen rep
counter jumps from one number to the next with no in-between frames. Weak
observation: viewers report the counter looks "broken" or laggy rather than
brisk. Cause: zero spacing between the old and new values — an instant swap
has no velocity curve at all, which reads as a dropped frame rather than a
fast action. Revision: add a short (2–3 frame) scale-down/scale-up ease on
each digit change so there is a perceivable, if brief, spacing curve instead
of a hard cut on the number itself.

**Retain — instant state swap in a comparison graphic.** Request/observation:
a reviewer flags an explainer's before/after bar-chart comparison for having
"no easing" when the bars swap from one data state to the next. Evidence for
retaining the hard cut: the graphic represents two discrete, non-continuous
data states (before a change and after it), not an object moving through
space. Adding an eased tween between the two bar heights would visually
imply a continuous transformation occurred, misrepresenting a change that
was actually instantaneous in the underlying data. The instant cut is the
more honest representation here, so no revision is applied.

## Sources

Timing/spacing and anticipation as named terms are described in Adobe's
overview of the traditional animation principles:
https://www.adobe.com/creativecloud/animation/discover/principles-of-animation.html
(consulted 2026-09-12). The keyframe-handle model of an easing curve follows
the interpolation-handle behavior documented for Blender's F-curve editor:
https://docs.blender.org/manual/en/5.2/editors/graph_editor/fcurves/properties.html
(consulted 2026-09-12; technique referenced, not its text or images).
