
# Transition: Match Cut

Intent: transition controls boundary grammar - how (or whether) the clip
moves between views - not cut count or motion speed; pace stays an
independent decision. Match-cut means the boundary between two shots
preserves a shape, silhouette or motion line so the viewer's eye lands on
the same target across the cut (a raised arm continuing into a similar
gesture in the next shot, a round object matched by another round shape).
It is not a guarantee of pixel-identical continuity, and it is not a melt
or morph blending one shot into the next.

Prompt guidance: "The shot cuts from <view A>, where <subject/shape/motion>
occupies <position>, to <view B>, where a matching shape or continued
motion line lands the viewer's eye on the same target - an instantaneous
cut, not a blended morph." Rewrite the shapes/motion around the actual
brief; keep the sentence shape, not the exact words.

Avoid: do not describe the boundary as blending, melting or morphing one
shape into another - that is a dissolve-family effect, not a match-cut. Do
not treat "match" as a promise of deterministic pixel alignment between the
two shots; the model may vary the exact framing even while the viewer's eye
target is preserved. Do not apply a match-cut where the proposal never
identified a shape/motion line to carry across.

QA cues: sampled/timecoded frames on either side of the boundary are the
available evidence for whether the eye-target/shape reads as continuous -
they cannot certify frame-exact alignment, only a plausible match at the
sampled points. Flag a boundary where the claimed match is not visually
recognizable as such.
