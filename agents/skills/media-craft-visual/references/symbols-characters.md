# Symbols and characters: small silhouette, gesture, identity

Read this when the subject is a small icon, an emoji, or a character (a
mascot, avatar, or illustrated figure) and the issue is optical weight at
small size, or a gesture, expression, or pose that reads wrong or
inconsistently across a set.

At small display sizes, an icon or emoji is read as a silhouette first and
details second. Two shapes with the same pixel dimensions can look
mismatched in weight if one has thinner strokes or more open interior space
than the other; a consistent set needs consistent stroke weight and interior
"fill ratio," not just consistent outer bounding box size. Never reuse a
copyrighted logo, a specific brand's mascot, or another platform's licensed
icon set as a shape reference; match the visual weight and structural idea,
not the specific protected artwork.

For characters, gesture and pose read before facial detail, especially at
small size or in motion. A pose's silhouette should communicate the intended
action or emotion even with the face blurred out; if it does not, no amount
of facial expression detail will fix the read. Consistency across a set of
character poses means consistent proportions, consistent "energy" in the
line work, and a recognizable identity feature that survives every pose, not
identical poses.

## Case 1: an icon set with uneven optical weight

Request: a set of five toolbar icons ("home," "search," "settings," "alerts,"
"profile") for a community app, all drawn at the same 24x24 bounding box.

Weak result (observed): in the toolbar, the "search" icon (a thin-stroke
magnifying glass) looked noticeably lighter than the "settings" icon (a solid
gear shape), even though both were sized to the same bounding box; the set
read as inconsistent even though every icon technically matched the grid.

Diagnosis: bounding box size was consistent, but optical weight (how much
ink/fill sits inside that box) was not; a thin outline shape and a solid
filled shape at the same box size do not carry the same visual mass, and a
toolbar viewer perceives that mass difference, not the box dimensions.

Revision (specific choice): increased the magnifying glass's stroke weight
and shortened its handle slightly so its filled area (ink coverage) moved
closer to the gear icon's coverage, without changing its recognizable
silhouette; did not simply scale the whole icon up, since that would have
broken alignment with the other icons' grid.

Retain: the gear icon's shape and weight stayed as the reference the rest of
the set was matched to, since it was already reading correctly.

When NOT to use this fix: if the design system intentionally uses outline
icons for inactive states and filled icons for active/selected states, do not
"balance" their weight to match; the weight difference there is a deliberate
state signal, not an inconsistency.

Evidence method: viewed the full icon set together in an actual toolbar mock,
at real display size, and squinted or slightly blurred the view to check
silhouette weight, rather than comparing icons individually side by side at
a large zoomed-in size.

## Case 2: a mascot whose gesture didn't match the caption

Request: an illustrated mascot for "Riverbend Community" for a "we're excited
to announce..." social post, waving.

Weak result (observed): the mascot's arm was raised and hand open, technically
a wave, but the shoulders were low, the pose was static, and the face was
neutral; reviewers said it "doesn't feel excited," even though a wave was
present.

Diagnosis: an isolated correct gesture (a raised, open hand) is not the same
as a pose reading as "excited." Excitement needs supporting body language:
weight shift, an open chest, energy in the line (a slight diagonal lean or
a bounce implied by foot position), which a single static, symmetrical pose
does not communicate even with an accurate wave gesture.

Revision (specific choice): shifted the mascot's weight onto one leg, tilted
the torso slightly toward the viewer, and raised the opposite shoulder
slightly higher than the waving arm's shoulder to imply motion, while keeping
the exact same wave hand shape (the shape reviewers had already approved).

Retain: the mascot's core identity features (color palette, head shape, and
the wave hand shape itself) stayed unchanged; only the supporting body
language changed, so the character remained recognizable as the same mascot.

When NOT to use this fix: do not add dynamic tilt and weight shift to a
mascot pose meant to convey calm reassurance (e.g., a "we're here to help"
support-context pose); a stable, symmetrical, low-energy pose is the correct
choice there, and adding excitement-coded body language would misrepresent
the message.

Evidence method: showed the revised pose next to the caption it will
actually ship with (not the pose alone) and asked whether the pose alone,
with the face covered, still communicated "excited," to isolate gesture from
facial expression.

## Sources

Small-icon optical weight draws on
[Apple Human Interface Guidelines, SF Symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols)
(optical weight consistency across a symbol set, not the specific licensed
glyphs themselves; read 2026-09-12). Gesture and pose staging draws on
[Adobe, Principles of Animation](https://www.adobe.com/creativecloud/animation/discover/principles-of-animation.html)
(staging and gesture read before detail; read 2026-09-12). Do not reuse
Apple's SF Symbols artwork or any other licensed icon set directly; only the
optical-weight and staging principles are portable here.
