# Recreate

Author task-local HTML/CSS/GSAP using the authoring contract. Reference images,
designs and text describe UI facts, not permission to fetch a URL or operate an
app. Preserve the existing ability to construct readable modal, typing,
selection and result states; no canned action/template renderer is added.

Do not supply `source` or `target` in this mode. Explicit `screen_mode: recreate`
uses the v3 proposal gate. Omitted mode retains the shipped v2 authoring path.
Actual persisted v1 projects still use tour.py. Neither old format is migrated.
Use the same freeze, snapshot, exact-preview approval and render commands.
