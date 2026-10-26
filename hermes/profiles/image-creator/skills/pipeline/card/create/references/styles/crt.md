# CRT

A late-night television screen: dusk purple to near-black with a warm glow
low in the frame, horizontal scanlines and a dark vignette behind the copy,
a rounded screen edge with inner shadow, and an orange accent bar with a
slight red/cyan channel split. Retro broadcast, but the type stays crisp. On tiled destinations the
scanlines and vignette span the whole panorama once, not each tile.

```css
:root { --surface: #120d1f; --ink: #fff4e0; --accent: #ff7a3d; }
.stage { background: radial-gradient(ellipse at 50% 72%, #ff7a3d40, transparent 55%), linear-gradient(180deg, #2a1845, #120d1f 55%, #07050c); }
.orb { background: repeating-linear-gradient(0deg, #0000004d 0 2px, transparent 2px 4px), radial-gradient(ellipse at center, transparent 42%, #000000b3 72%); }
.panel { background: transparent; border-radius: 40px; box-shadow: inset 0 0 120px #000000cc, 0 0 0 2px #ffffff14; }
.accent { background: var(--accent); box-shadow: -3px 0 0 #3df0ff99, 3px 0 0 #ff3d7a99, 0 0 18px #ff7a3dcc; }
h1 { font-weight: 700; letter-spacing: 0.01em; }
.label { color: var(--accent); letter-spacing: 0.1em; }
```
