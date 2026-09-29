# Blueprint

Deep drafting blue with a fine and a coarse white grid, a hairline border
with an inner rule like a drawing sheet's title frame, pale-cyan lettering
and one warm yellow accent. Precise and engineered; no drawn machinery.

```css
:root { --surface: #0f3b7a; --ink: #eaf4ff; --accent: #ffd166; }
.stage { background: repeating-linear-gradient(0deg, transparent 0 79px, #ffffff2b 79px 80px), repeating-linear-gradient(90deg, transparent 0 79px, #ffffff2b 79px 80px), repeating-linear-gradient(0deg, transparent 0 15px, #ffffff10 15px 16px), repeating-linear-gradient(90deg, transparent 0 15px, #ffffff10 15px 16px), var(--surface); }
.panel { background: transparent; border: 2px solid #eaf4ffb3; outline: 1px solid #eaf4ff59; outline-offset: -14px; }
.accent { background: var(--accent); }
.label { color: var(--accent); letter-spacing: 0.14em; }
.brand { letter-spacing: 0.08em; }
h1 { font-weight: 500; letter-spacing: 0.01em; }
```
