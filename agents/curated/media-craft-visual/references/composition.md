# Composition: hierarchy, layout, negative space

Read this when an image (a card, poster, slide, or social tile) feels busy,
flat, or hard to scan, or when someone asks to "balance" or "clean up" a
layout without saying exactly what to change.

Composition problems are almost always a hierarchy problem in disguise: too
many elements are fighting at the same visual weight, or the one element that
should lead is not distinguishable from the rest. Fix the ranking first
(what is read 1st, 2nd, 3rd), then adjust spacing and grouping to make that
ranking visible. Do not treat negative space as leftover area to fill; it is
what separates the ranks and gives the eye somewhere to rest.

Density is a choice, not a flaw. A transit map or an event schedule can
legitimately be dense and information-forward; a status card can legitimately
be sparse. Match the density to how the piece will actually be read (glanced
at for two seconds vs. studied for two minutes), not to a generic preference
for whitespace.

## Case 1: a dense poster with no entry point

Request: design a poster announcing a weekend "Harborview Art Fair" with the
date, a map thumbnail, ten participating vendor names, and a sponsor line.

Weak result (observed): every element (title, date, map, vendor list,
sponsor line) was set at a similar size and weight in a single centered
column. Viewed at a normal glance distance, the eye had no clear starting
point, and the vendor list was the same visual weight as the event title.

Diagnosis: the layout had content grouping but no rank. Five different
information types were competing for the same first read, so nothing won.

Revision (specific choice): kept the title as the only large element,
dropped the vendor list to a dense two-column list at a clearly smaller size
than the date/map cluster, and moved the sponsor line to the smallest weight
at the bottom edge, separated by a rule rather than more whitespace (the
poster needed to stay dense for its glance-and-post context, so added a rule
instead of adding a large gap).

Retain: the two-column vendor list stayed dense and information-forward,
because the poster's job is to list every vendor for people already planning
to attend, not to look minimal from across a room.

When NOT to use this fix: do not flatten a genuinely dense reference layout
(a printed train timetable, a full lineup grid) to three tiers of size when
the audience is scanning for one specific row, not for a single lead item;
in that case, work on alignment and repetition instead of size hierarchy.

Evidence method: viewed the poster at the size it will be read (arm's length
for a wall poster, thumbnail size for a social repost) and timed the first
fixation informally by asking "what do I read first" without prompting.

## Case 2: a calm card with dead space that reads as unfinished

Request: a "today's forecast" weather card for a neighborhood community app,
showing temperature, condition icon, and one line of text.

Weak result (observed): the temperature and icon sat centered in the top
half of the card, leaving a large empty band at the bottom that reviewers
described as "looks unfinished" or "like it's missing content."

Diagnosis: the negative space was not doing a job. Good negative space
separates or emphasizes; this space was just unused area with no relationship
to the content above it, so it read as an omission rather than a calm choice.

Revision (specific choice): moved the one-line text (e.g., "Light rain after
3pm") to sit in that lower band, left-aligned to the temperature's left edge
rather than centered, so the space became a deliberate margin around a
secondary line instead of a void. Did not add a graphic or a background
gradient to "fill" the area, since the card's job is calm utility, not
decoration.

Retain: the generous top margin above the temperature stayed, because it
correctly separated this card from the ones above and below it in the feed.

When NOT to use this fix: do not add a line of text or a filler graphic to
negative space that is already doing its job (e.g., separating a hero image
from a caption); in that case the empty space is the correct choice and
should be left alone even if it looks large on its own.

Evidence method: viewed the card inside the actual feed context (stacked with
neighboring cards) at its real render width, not as an isolated crop, since
"unfinished" vs. "calm" only reads correctly next to its neighbors.

## Sources

Alignment and grouping guidance is also informed by
[Carbon Design System, 2x Grid](https://carbondesignsystem.com/elements/2x-grid/overview/)
(grid alignment and responsive grouping; read 2026-09-12). Carbon's specific
grid numbers are one system's implementation choice, not a universal rule;
treat the alignment and grouping principle as portable, not the pixel values.
