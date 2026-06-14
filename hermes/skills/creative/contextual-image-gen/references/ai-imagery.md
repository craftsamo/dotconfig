# AI imagery — covers, heroes, illustrations, social backgrounds

For illustrative, brand-styled, **text-free** imagery via `image_generate`.

## Pattern: locked style block × subject

Keep a brand-locked **common style block** and only swap the **subject** per
image. This is what gives a set visual consistency (the tool can't take a
reference image, so consistency is carried in text).

```
<common style block: background, palette, stroke/fill weight, composition,
 contrast, negative list, aspect>
Subject: <one clear hero + a few close, intentional supporting elements>
```

### Build the common block from discovery

- **Background**: brand-driven. A solid/gradient brand fill often reads stronger
  on cards and dark UIs than a pale wash.
- **Palette**: the discovered hexes; name the dominant + accent explicitly.
- **Weight**: "bold, medium-heavy strokes with solid fills" beats "thin line-art"
  at thumbnail size.
- **Composition**: one large hero, few large supporting elements, ~65-70% of the
  frame, 15-18% margin. Keep the subject **center-safe** so it survives every
  crop you found (e.g. 2:1, 21:9).
- **Contrast**: "reads clearly as a small thumbnail and on a dark UI".
- **Negative list**: `NO text, NO letters, NO numbers, NO logos, NO sunburst/
  starburst/spinner, NO person/face avatars, NO human figures` (trim to taste).
- **Aspect**: state the master ratio (e.g. "16:9 aspect ratio").

### Worked example (a tech-education brand, terracotta)

```
Bold flat vector illustration on a brand-orange background. The whole frame is a
soft coral gradient from #EE8366 (top-left) to #E26E54 (bottom-right) — bright,
not burnt — with subtle tonal blobs and a faint corner dot-grid. Keep the
composition COMPACT and centered (~65-70% of the frame, 15-18% margins). ONE
crisp white/cream (#FFF7F2) UI mock as the hero with soft shadows and terracotta
accents, plus a FEW bold supporting elements pulled in close (never tiny
scattered noise). One calm focal motif inside the hero. NO text, NO letters, NO
numbers, NO logos, NO sunburst/starburst, NO person/face avatars. High-contrast;
reads clearly as a small thumbnail and on a dark UI. 16:9 aspect ratio.
Subject: a large white browser window with a simple chat — left-aligned cream
bubbles and right-aligned terracotta bubbles, differentiated by side and color
(no avatars); a magnifier and a pair of curved arrows tucked close.
```

Swap only the `Subject:` line for the rest of the set.

## Procedure

1. Map the master ratio to `image_generate`: 16:9 → `landscape`, 9:16 →
   `portrait`, 1:1 → `square`.
2. Write the full final prompt to `prompts/NN-<slug>.md` (reproducibility).
3. `image_generate(prompt=..., aspect_ratio=...)`. The result `image` is a URL or
   a local path.
4. Normalize + export: `scripts/img-postprocess.sh <image> <out> --format ... --max-bytes ...`.
5. Review at **thumbnail size** and on the real background. Tune with the dials,
   regenerate. For a set, lock course/page 1, then do the rest in the same style.

## Dials

- Washed out → bolder strokes, solid fills, higher contrast.
- Too busy / clipped → fewer larger elements, smaller footprint, more margin.
- Background off → adjust gradient stops (e.g. `from #F2937A to #E8734F`).
- Weird emblem → "no radial/sunburst shapes; keep it simple".
- Heavy shadows → "flatter, lighter shadows".
- Oversized in a multi-panel subject → "keep the SAME compact footprint; do not
  enlarge for extra content".

## Backend note

The active backend is user-configured (here: `img-xai-codex-fal`, xai first) and
**not** agent-selectable. Don't name models in the prompt. If prompt adherence
drifts, suggest switching `image_gen.provider: img-codex-xai` (gpt-image-2 first)
for brand work.
