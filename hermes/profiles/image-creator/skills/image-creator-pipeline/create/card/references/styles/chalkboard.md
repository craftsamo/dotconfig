# Chalkboard

Dark green slate with soft erased smudges and generated chalk dust,
framed by a warm wooden border; chalk-white type with a soft dusty edge, a
chalk-yellow accent bar and a pale-blue label. The dust sits behind the
letters, so they stay legible.

```css
:root { --surface: #2f4a3c; --ink: #f4f1e6; --accent: #f6d86b; }
.stage { background: radial-gradient(ellipse at 28% 38%, #ffffff17, transparent 45%), radial-gradient(ellipse at 76% 72%, #ffffff0f, transparent 40%), radial-gradient(circle, #ffffff0d 0 0.8px, transparent 1.3px) 0 0 / 7px 7px, var(--surface); }
.panel { background: transparent; border: 14px solid #6b4a2e; border-radius: 6px; box-shadow: inset 0 0 0 2px #00000040, inset 0 0 60px #00000059; }
.accent { background: var(--accent); border-radius: 3px; box-shadow: 0 0 6px #f6d86b66; }
.label { color: #a8d8f0; letter-spacing: 0.06em; text-shadow: 0 0 2px #a8d8f080; }
h1 { font-weight: 600; letter-spacing: 0.02em; text-shadow: 0 0 2px #f4f1e699, 0 0 6px #f4f1e633; }
.texture { mix-blend-mode: screen; opacity: 0.35; }
```

```texture
chalk
```
