# Picture Book

Intent: a gentle, story-like explanation for a general or young audience;
the topic is shown as an illustrated page that comes alive.

Material: soft watercolor washes (layered translucent fills with a slightly
darker, uneven edge), warm off-white paper with subtle grain, rounded
simplified shapes. In HyperFrames build washes as SVG shapes with a seeded
`feTurbulence` + `feDisplacementMap` edge and low-opacity grain overlay; in
Motion Canvas use soft-edged shapes and a static grain texture layer. Grain
and edge wobble are fixed per shape, never re-randomized per frame.

Ink: soft pencil-like outlines (warm dark brown or grey, not black, slightly
varied width). Labels are handwritten-feeling but fully readable; a key
term may sit on a painted wash swatch. Arrows and highlights are painted
strokes, not UI chrome.

Motion: slow and page-like - elements settle in with a gentle ease, scenes
change as if turning to the next spread. Best paired with `process` or
`worked-example`, and with story-like visual metaphors from the kernel's
vocabulary. A custom, equally concrete free-text style is implemented
verbatim, never coerced onto this preset.

QA: labels stay readable over washes at native size (contrast audit where
the engine supports it); textures do not flicker between frames; the page
still reads as one illustration, not a UI with a paper background.
