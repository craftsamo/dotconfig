# Prompt craft for text-free illustrations

One paragraph per prompt, in this order.

1. **Medium first.** Say what the picture IS (a flat vector illustration, a
   gouache painting, a risograph print), not only an adjective. An image model
   left to itself returns a generic render.
2. **One hero.** One large subject plus a few close supporting elements; many
   small scattered elements read as noise at thumbnail size.
3. **Footprint and margin.** Keep the subject compact and centre-safe
   (about 65-70 % of the frame, 15 % margins) when the picture will be cropped
   to other ratios; say where the quiet area is when the use needs one
   (for a title laid on later).
4. **Palette.** Name the dominant and the accent, as hex or words; a solid or
   gradient ground often reads stronger than a pale wash.
5. **Weight and contrast.** "bold medium-heavy strokes, solid fills" beats
   "thin line art" at small size; ask for contrast that reads as a thumbnail.
6. **Negatives.** End with: no text, no letters, no numbers, no logos, no
   watermark, then the form's `avoid`. Phrase it as the picture's content, and
   never quote a word to be drawn — a quoted string comes back as pixels.
7. **Canvas.** Spell the orientation out in words; the aspect argument alone is
   not honoured reliably.

Common fixes for a corrective: washed out → bolder strokes, solid fills, higher
contrast; too busy or clipped → fewer larger elements and more margin; a
sunburst or odd emblem appears → name it in the negatives; heavy shadows →
"flatter, lighter shadows".

A set that must look alike: keep one common style paragraph and swap only the
subject sentence; the tool carries consistency in text, so lock the first
accepted variant's wording.
