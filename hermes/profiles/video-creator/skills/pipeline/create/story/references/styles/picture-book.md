# Picture Book

Intent: a gentle, warm story that feels like an illustrated book whose
pages come alive; suits soft, rounded cast art with pencil or painted line.

World: watercolor and gouache washes on warm off-white paper, uneven
pigment edges, generous empty space, simple rounded places (a hill, a
window, a kitchen table) rather than detailed sets. Build washes as SVG
shapes with a seeded `feTurbulence` + `feDisplacementMap` edge and a
low-opacity grain overlay fixed per shape, never re-randomised per frame.
The cast sits on the page with a soft contact shadow in a darker tone of
the ground wash, not a hard drop shadow.

Camera and seams: slow pushes and trucks across a page; scene changes as
page turns, a wash bleeding into the next place, or a carrier (a leaf, a
paper boat) that drifts across the seam. Hold stillness before the turn.

Type: handwritten-feeling but fully readable captions on a soft wash
swatch; never UI chrome.

QA: the cast art keeps its own line and colours while the world stays in
washes (the two must look like one book, not a sticker on a painting);
textures do not flicker; captions readable over washes at native size.
