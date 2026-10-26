# Dark pro

Near-black, precise, cyan signal. Hairline grid and a narrow accent rule rather
than glows or soft surfaces. A technical title, not a neon poster.

```css
:root { --surface: #0b1016; --ink: #f3f6fa; --accent: #64daee; }
.stage { background: repeating-linear-gradient(90deg, transparent 0 63px, #ffffff08 63px 64px), repeating-linear-gradient(0deg, transparent 0 63px, #ffffff08 63px 64px), var(--surface); }
.panel { background: transparent; }
.accent { background: var(--accent); }
.brand { color: var(--accent); }
h1 { font-weight: 600; letter-spacing: -0.025em; }
```
