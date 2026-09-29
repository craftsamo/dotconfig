# Risograph

Warm off-white stock with generated paper grain, printed in two spot inks:
fluorescent pink and a deep riso blue. Interleaved pink and blue halftone dots
texture the paper, a flat pink disc sits over a blue plate printed a few
pixels out of register (a blue crescent peeks out), and the accent bar carries
the same offset. Zine-like and graphic; the type is solid blue ink, never
dotted. On tiled destinations the disc appears once, near the top of the last
tile.

```css
:root { --surface: #f3ede0; --ink: #1d3b8f; --accent: #ff5a4e; }
.stage { background: radial-gradient(circle, #ff5a4e40 0 2px, transparent 2.6px) 0 0 / 12px 12px, radial-gradient(circle, #1d3b8f24 0 1.6px, transparent 2.2px) 6px 6px / 12px 12px, var(--surface); }
.orb { background: radial-gradient(circle at 78.6% 24.3%, #ff5a4ef2 0 7%, transparent 7.12%), radial-gradient(circle at 79.3% 25.2%, #1d3b8fd9 0 7%, transparent 7.12%); }
.panel { background: transparent; }
.accent { background: var(--accent); box-shadow: 4px 3px 0 #1d3b8fb3; }
h1 { font-weight: 800; letter-spacing: -0.01em; }
.label { color: var(--accent); font-weight: 700; letter-spacing: 0.08em; }
.texture { opacity: 0.9; }
```

```texture
paper
```
