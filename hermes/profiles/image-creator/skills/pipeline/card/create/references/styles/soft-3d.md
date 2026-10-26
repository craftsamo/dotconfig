# Soft 3D

Pale lavender and peach, rounded white surface, long soft shadow. CSS depth is
an illustration of soft volume, not a generated or physically rendered mesh.

```css
:root { --surface: #eeecfc; --ink: #29233f; --accent: #7160b6; }
.stage { background: radial-gradient(ellipse at 0% 0%, #c9c2fa, transparent 55%), radial-gradient(ellipse at 100% 100%, #ffd6c2, transparent 60%), var(--surface); }
.panel { background: #ffffffbb; border: 1px solid #ffffff; border-radius: 36px; box-shadow: 0 28px 60px #57437838, inset 0 2px 0 #ffffff; }
.accent { background: var(--accent); border-radius: 8px; }
```
