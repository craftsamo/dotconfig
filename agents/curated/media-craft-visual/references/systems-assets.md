# Systems and assets: kits, components, states, boundaries

Read this when the work is part of a UI kit, component set, badge or sticker
system, or an atlas/9-slice asset, and the issue is consistency across the
set, missing states, or a fidelity-vs-geometry tradeoff.

A kit is judged by its weakest inconsistent member, not by its best piece.
Before adding a new component or badge, check the set's existing rules for
corner radius, stroke weight, padding, and color role usage, and match them
unless the request is explicitly to introduce a new rule (a size tier, a new
color role). Introducing a one-off exception quietly is worse than asking
whether the rule should change, because the next person who copies the
one-off will assume it is the rule.

Components usually need more than one visual state (default, hover/pressed,
disabled, selected), not just the state shown in the request. If a request
only shows one state, check whether the others already exist elsewhere in
the kit and need to match, rather than inventing a new default look for
this one component.

9-slice and atlas assets have a hard technical boundary: content inside the
slice guides or atlas cell can be redesigned, but the guide/cell geometry
itself (slice line positions, padding reserved for stretch regions, atlas
cell boundaries) is a functional constraint, not a stylistic one. Preserve
actual user-facing constraints (padding another element depends on, hit-test
area, safe zone) even when a purely visual change looks like an improvement;
treat geometry meaning as separate from geometry decoration.

## Case 1: a new component drifting from kit rules

Request: add a "route delay" badge (a small pill showing a number and a
color) to the "Northline Transit" app's existing badge system, which already
has "on time" and "cancelled" badges.

Weak result (observed): the new badge used a 4px corner radius and a
different internal padding than the existing badges, which used an 8px
radius and tighter padding; placed next to the existing badges in a stop
list, the new one looked like it came from a different app.

Diagnosis: the new badge was designed by matching the visual idea (a colored
pill with a number) without checking the existing badges' actual radius and
padding values first, so it matched the concept but not the system.

Revision (specific choice): matched the existing 8px corner radius and
padding exactly, and confirmed the delay badge's color (amber) did not
already carry a different meaning elsewhere in the kit (it did not) before
finalizing it as the delay color.

Retain: the badge's number-first layout (number before the label) stayed as
originally designed, since that ordering matched neither an existing rule
nor a conflict, and design judgment was the right basis for that specific
choice.

When NOT to use this fix: do not force a genuinely new category of
information (e.g., a badge type carrying two data points where every
existing badge carries one) into the existing padding and sizing rules if
that information cannot fit; propose a new, clearly related size tier
instead of cramming it, and flag the addition to whoever owns the kit.

Evidence method: placed the new badge directly inside a real stop list mock
next to the two existing badge types at actual size, not compared to them in
isolation, to check whether it read as the same family.

## Case 2: a visual "cleanup" that broke a 9-slice's function

Request: refresh a stretchable button background asset for an "Art Fair"
app's ticket-purchase button, currently a 9-slice PNG with a rounded border.

Weak result (observed): the revised artwork moved the border's rounded
corner further into the slice guides to "make the border feel less thin,"
which caused the corners to visibly distort (stretch and blur) whenever the
button was resized wider than its original design width, because the slice
guides no longer isolated the corner artwork correctly.

Diagnosis: the corner's position relative to the slice guide lines is a
functional boundary, not a decorative choice; moving the border art without
moving the guide lines broke the assumption the 9-slice stretching depends
on, even though the static preview (unstretched) looked fine.

Revision (specific choice): kept the border's visual thickness change, but
moved the slice guide lines to match the new border position so the
non-stretching corner region still fully contained the rounded corner
artwork, then tested the asset at both the button's minimum and a much wider
width to confirm the corners stayed sharp.

Retain: the flat color fill in the stretchable middle region stayed
unchanged, since that region was correctly defined and had no distortion
problem.

When NOT to use this fix: do not treat every visual complaint about a
9-slice asset as a guide-line problem; if a color or shadow inside the
stretch region looks wrong, that is a normal art edit inside the guides and
does not require touching the slice geometry at all.

Evidence method: rendered the button asset at multiple real button widths
(its narrowest and a wide outlier used elsewhere in the app), not only at
the width shown in the original design mock, to check the stretch behavior
directly.

## Sources

Consistent grouping and component alignment across a set draws on
[Carbon Design System, 2x Grid](https://carbondesignsystem.com/elements/2x-grid/overview/)
(system-level alignment numbers, treated as one system's specific choice
rather than a universal rule; read 2026-09-12).
