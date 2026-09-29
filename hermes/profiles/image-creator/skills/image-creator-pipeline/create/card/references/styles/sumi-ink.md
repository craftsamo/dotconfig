# Sumi ink

Warm washi with long fibres from the generated washi texture, faint grey ink
washes low in the frame, and one brushed ensō in the top-right corner: a
thick black ring left open where the brush lifted, its ends tapering.
Near-black type with a slight ink bleed and a vermilion label. Quiet and
spacious; no calligraphy is drawn.

```css
:root { --surface: #f2ede2; --ink: #141414; --accent: #b8352b; }
.stage { background: radial-gradient(ellipse 60% 22% at 72% 104%, #14141438, transparent 70%), radial-gradient(ellipse 38% 16% at 98% 94%, #1414142e, transparent 70%), var(--surface); }
.orb { background: radial-gradient(circle closest-side at 71.4% 25.7%, transparent 0 34%, #141414f0 34.5% 39.5%, transparent 40%), radial-gradient(circle closest-side at 71.2% 25.9%, transparent 0 34.6%, #141414d9 35% 41.2%, transparent 41.8%); -webkit-mask-image: conic-gradient(from 20deg at 71.4% 25.7%, transparent 0deg 16deg, #0005 30deg, #000 70deg 300deg, #000b 330deg, transparent 348deg); filter: blur(0.7px); }
.panel { background: transparent; }
.accent { background: var(--accent); }
h1 { font-weight: 700; letter-spacing: 0.02em; text-shadow: 0 0 1px #141414b3, 0.6px 0.4px 0 #14141459; }
.label { color: var(--accent); letter-spacing: 0.12em; }
.texture { opacity: 1; }
```

```texture
washi
```
