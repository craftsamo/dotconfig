# Typography: relative weight, width, leading, optical alignment

Read this when text inside an image (a label, wordmark, masthead, caption, or
button-like element) needs a decision about weight, width, leading, size, or
alignment, or when a request is phrased as "make the text bigger" without a
stated reason.

Typographic decisions in an image are relative, not absolute. There is no
universal minimum size; a caption that is fine on a printed sign is
illegible shrunk to a 32px thumbnail, and a size that looks small in a design
file can dominate at its actual display size. Judge weight, width, and size
against the other type in the same image and against the size the image will
actually be viewed at, not against a rule of thumb pulled from a different
context.

Leading (line spacing) and optical alignment matter as much as size. Tight
leading on a multi-line label reads as urgent or cramped; loose leading reads
as calm or sparse. Optical alignment (nudging a quotation mark or a cap
height so it looks aligned to the eye) usually needs a manual adjustment,
because mathematically centered text often looks off-center next to
asymmetric glyphs.

## Case 1: a transit sign where "bigger" made it less readable

Request: increase the size of the platform number on a "Northline Transit"
digital departure sign because riders said it was hard to read from a
distance.

Weak result (observed): the platform number was enlarged uniformly along
with its bounding box, which pushed the destination name onto a second line
at a much smaller size than before, so the sign now had three very different
text sizes with no clear relationship between them.

Diagnosis: the actual complaint was about the platform number's contrast and
weight at viewing distance, not literally its point size. Enlarging it without
adjusting the surrounding hierarchy created a new, worse hierarchy problem
one level down (the destination name, which riders also need, got harder to
read).

Revision (specific choice): increased the platform number's weight (regular
to bold) and size by a smaller amount than the original request, and kept the
destination name at a size clearly one step below the platform number rather
than two steps below, preserving a two-level hierarchy instead of creating
three competing sizes.

Retain: the departure time stayed at its original size and weight, since no
one had reported it being hard to read and enlarging it would have crowded
the layout without solving the reported problem.

When NOT to use this fix: if the actual constraint is a fixed physical
viewing distance from an approved sign standard, do not eyeball weight and
size; use the standard's specified minimum for that distance instead, and
treat this reference's relative-hierarchy approach as secondary to it.

Evidence method: viewed the sign layout scaled to approximate its real
on-screen size at a simulated viewing distance (stepping back from the
screen) rather than judging it zoomed in on an editor canvas.

## Case 2: a masthead where the wrong weight killed the wordmark identity

Request: refresh the "Riverbend Community" newsletter masthead by using the
brand's condensed display font, currently only used for section headers.

Weak result (observed): the masthead in the condensed weight looked thin and
generic next to the newsletter's warm, informal body content; several
readers described the new masthead as "cold" compared to the old one.

Diagnosis: the newsletter's identity depended on the masthead reading as
confident and rounded at a large display size, which needs a heavier weight
of the condensed family; using the same weight that worked for small section
headers at a much larger size lost that character because weight perception
shifts with size (a weight that looks solid small can look thin large).

Revision (specific choice): kept the condensed family for consistency with
the section headers, but selected its bold or heavy cut for the masthead
specifically, and widened the tracking slightly to keep the condensed
proportions from feeling cramped at the larger size.

Retain: the section headers kept their original lighter weight, because they
were legible and consistent at their own (smaller) size; the fix was scoped
to the masthead, not applied uniformly across every use of the family.

When NOT to use this fix: do not default to the heaviest available weight
whenever type is enlarged; a masthead for a quiet, minimal newsletter brand
might correctly want a lighter weight held at a larger size instead, if that
matches the brand's actual voice.

Evidence method: placed the revised masthead next to an actual newsletter
page spread (not in isolation) and next to the old masthead, at final output
size, to judge the "cold vs. warm" perception change directly rather than
from the typeface name or weight label alone.

## Sources

Hierarchy-by-relative-emphasis (not fixed point sizes) draws on
[Apple Human Interface Guidelines, Typography](https://developer.apple.com/design/human-interface-guidelines/typography)
(relative hierarchy over absolute minima; read 2026-09-12). The guideline is
platform-specific UI advice; the transferable idea used here is relative
weight and size judged against context, not the platform's specific type
scale or point values.
