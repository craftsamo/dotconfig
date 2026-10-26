# Watercolor

Warm cold-press paper with transparent washes of blue, rose, ochre and sage
pooled into the corners with darker dried rims, blooms from the generated
watercolor texture, and paper grain over everything. Indigo type with a faint soft edge;
a rose brush-stroke accent that fades out at its tail. Light and airy; the
text area stays pale.

```css
:root { --surface: #f8f4ec; --ink: #2b3a55; --accent: #d9776b; }
.stage { background: radial-gradient(ellipse 22% 30% at 97% 4%, #8fb3d966, #8fb3d98c 58%, #5f89bab3 64%, transparent 67%), radial-gradient(ellipse 16% 20% at 86% -2%, #8fb3d959, #6f97c499 62%, transparent 66%), radial-gradient(ellipse 20% 26% at 92% 102%, #e8a49c59, #e8a49c80 60%, #cf7d74a6 66%, transparent 69%), radial-gradient(ellipse 12% 16% at 78% 104%, #e9c46a73, #d9a94299 64%, transparent 68%), radial-gradient(ellipse 30% 22% at 0% 104%, #9cc5a14d, #7fae8580 62%, transparent 66%), var(--surface); }
.orb { background: radial-gradient(ellipse 12% 14% at 76% 22%, #8fb3d933, transparent 70%); filter: blur(16px); }
.panel { background: transparent; }
.accent { background: linear-gradient(90deg, var(--accent) 0 60%, #d9776b00); border-radius: 3px; }
h1 { font-weight: 600; letter-spacing: 0.01em; text-shadow: 0 0 1px #2b3a5566; }
.label { color: var(--accent); letter-spacing: 0.08em; }
.texture { opacity: 0.95; }
```

```texture
watercolor
```
