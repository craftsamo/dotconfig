# Neon

A dark tiled wall at night with a pink glow pooling behind the copy. The
title is lit like neon tubing: a white-hot core with a pink halo; the
label and brand glow cyan; the accent is a lit pink tube. No generated
texture, so the glow stays clean. Reads best large; long copy is calmer in
another style.

```css
:root { --surface: #120e18; --ink: #fff4fa; --accent: #ff3d8b; }
.stage { background: radial-gradient(ellipse 55% 50% at 28% 50%, #ff3d8b2e, transparent 70%), repeating-linear-gradient(0deg, transparent 0 46px, #0000005c 46px 50px), repeating-linear-gradient(90deg, transparent 0 96px, #00000047 96px 100px), linear-gradient(180deg, #1c1524, #0d0a12); }
.panel { background: transparent; }
.accent { background: #ffd1e3; border-radius: 3px; box-shadow: 0 0 6px #ff3d8b, 0 0 18px #ff3d8b, 0 0 36px #ff3d8bb3; }
h1 { font-weight: 600; letter-spacing: 0.02em; text-shadow: 0 0 2px #ffffff, 0 0 8px #ff3d8b, 0 0 20px #ff3d8b, 0 0 42px #ff3d8bb3; }
h2 { text-shadow: 0 0 6px #ff3d8b; }
p { color: #f3e8ff; }
.label { color: #d8fbff; letter-spacing: 0.12em; text-shadow: 0 0 4px #3df0ff, 0 0 14px #3df0ff; }
.brand { color: #d8fbff; text-shadow: 0 0 6px #3df0ff; }
```
