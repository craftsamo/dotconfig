# Explanation Performance

In explainer and walkthrough content, the visual track must carry the state
change on its own — a viewer who mutes the narration should still be able
to follow what changed, when it changed, and roughly why. Narration adds
context and pacing, but it should not be the only channel carrying the
actual before/change/after sequence. If the only place a state change is
communicated is in what the narrator says, the visual is decorative rather
than explanatory, and the piece fails for any viewer who cannot rely on
audio.

## Show before, the change itself, and after

Treat a demonstrated state change as three visual beats, not two: the
starting state, a visible moment of the change happening (a toggle flipping,
a value updating, an element moving from one position to another), and the
resulting state. Cutting directly from "before" to "after" with no visible
middle beat forces the viewer to infer that something happened rather than
see it happen — acceptable for context the narration alone can safely carry
(minor asides), but not for the core mechanic the explainer exists to
demonstrate.

## Use the rig or tool's actual supplied cues

When a project provides real animation infrastructure — a character rig
with named cues, a software timeline with authored markers, a template with
defined transition points — map motion decisions onto those supplied cues
rather than inventing freeform interpolation that ignores them. Supplied
cues usually encode intent (a marker named "reveal" or a rig control meant
for "point at X") that a from-scratch tween would have to guess at.

## Do not assume automatic lip-sync

Never assume that a rendering pipeline will automatically synchronize a
character's mouth movement to narration audio unless that specific
capability (viseme data, a phoneme-to-mouth-shape mapping, an explicit
lip-sync feature) is confirmed to exist in the actual tool being used for
that render. A brief or script that describes a talking character without
checking for this capability is assuming a feature that may not exist.
Where lip-sync is not confirmed, either keep the mouth in a neutral/closed
state, use a generic non-synced talk-cycle loop that does not claim to
track the words, or hold off on animating the mouth until the capability is
verified and wired up.

## Cases

**Revision — missing middle beat.** Request: a software walkthrough shows a
settings panel in its "off" state, then cuts directly to the same panel in
its "on" state with no visible toggle action between them. Weak observation:
a viewer without audio (or one who glances away during narration) cannot
tell what specifically changed or how to reproduce it. Cause: the edit
skipped the actual state-change beat, relying on the narrator to describe an
action the visual never showed. Revision: insert a short clip or animated
diff showing the toggle itself flipping (or an on-screen arrow/highlight
marking exactly what changed) between the before and after frames.

**Revision — assumed lip-sync.** Request: a brief for an animated
spokesperson explainer describes the character's mouth as naturally
lip-syncing to the recorded narration, but the render pipeline in use has no
viseme or phoneme-mapping feature. Weak observation: the delivered render
shows a mouth moving on a generic loop with no relationship to the actual
words, contradicting what was promised in the brief. Cause: the brief
assumed a capability that was never confirmed to exist in the specific
pipeline being used. Revision: rewrite the brief to either use a neutral or
generically-cycling mouth with no lip-sync claim, or confirm and explicitly
wire up an available viseme/lip-sync feature before promising synced
mouth movement.

**Retain — loosely decoupled narration in an overview segment.** Request/
observation: an explainer keeps a single diagram fixed on screen as a
reference while the narrator discusses its facets in a different order than
they appear visually in the diagram; a reviewer flags this as narration and
visual being "out of sync." Evidence for retaining the loose coupling: this
segment is an overview, not a step-by-step demonstration — the diagram is
meant to stay visible as a stable reference point while narration explores
it, not to be revealed piece by piece in narration order. Forcing strict
visual/narration lockstep here would require redesigning the diagram itself
for no benefit to comprehension; the loose coupling is retained.
