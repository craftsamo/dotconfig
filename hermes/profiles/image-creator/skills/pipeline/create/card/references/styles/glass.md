# Glass

Cool, luminous, frosted. A translucent inset panel, fine bright border and
cyan/indigo field distinguish this from an unframed gradient. The CSS block
is canonical; palette overrides its surface/ink/accent roles.

```css
:root { --surface: #122859; --ink: #ffffff; --accent: #79e0eb; }
.stage { background: linear-gradient(135deg, #101b35, var(--surface), #6135a0); }
.panel { background: #ffffff18; border: 1px solid #ffffff66; border-radius: 28px; backdrop-filter: blur(24px); box-shadow: 0 24px 64px #00000040; }
.orb { background: radial-gradient(ellipse, #62e4f370, transparent 65%); }
.accent { background: var(--accent); }
```
