# Commission — image-creator: icon

Read [commissioning](../SKILL.md) first.

## Leaves

| Deliverable | Leaf | Notes |
| --- | --- | --- |
| a published library icon (Iconify) as SVG + PNG | `source-icon` | free; a word instead of an id comes back as candidates |
| a vendor's own official logo file (a third-party mark), unmodified | `source-icon` with `official: yes` | free; delivered with source URL, hashes (`provenance.json`) and the usage terms |
| favicon / Apple / PWA / maskable set from a first-party SVG | `create-icon` | free |
| an icon drawn in a named style (flat-minimal, glass, pixel, line, clay, origami, isometric, neon, stained-glass, …) | `generate-icon` | metered |
| recolour / background / cut-out / resize of an existing icon | `edit-icon` | free |
| findings on an icon or icon set, no file | `analyze-icon` | free |
| a published emoji glyph (Twemoji, Noto, OpenMoji, Fluent) | `source-icon` | free — `icon: twemoji:rocket`, `size: 128`; there is no source-emoji leaf on purpose |

## Choosing and filling

### Budget

A metered leaf takes a `budget:` line; absent, the leaf's default applies —
for icon: 4 variants + 1 corrective.

### Official third-party marks

Another company's logo is sourced, never drawn or generated: `source-icon`
with `official: yes`. The user's OWN brand is not this path — their mark is
their file, and a set from it is `create-icon` from their SVG. Settle the
`vendor`, the `variant` (glyph, lockup or wordmark) and the destination
background (`backdrop`: light or dark). When no official mark is distributed the
hands report it with the evidence; a text wordmark instead is the user's call
and a card / typography job, never a lookalike. The vendor's trademark and
usage terms travel with the delivery to the user.

### An icon set is two forms

"An icon set for the new bot" is two forms: `generate-icon` (the mark),
then `create-icon` from an SVG — which `generate-icon` does not produce,
so say so and offer `edit-icon` sizes instead. Decompose into leaves,
order them by what feeds what, and note the dependency ("form 2's
`source` = form 1's recommended variant"). Fill form 1 completely now;
fill a dependent form only when its input exists. Two independent forms
(a light and a dark icon) can run in parallel. Do not invent structure beyond
the leaves: no menus, presets, or Styles above the form; a request that needs
a leaf that does not exist is `no skill fits` to the user, noted for the
maintainer.

## Transport

`generate-icon` is metered and runs in a resident session: use the generic
`generate` row (`kind="work"`) in [commissioning](../SKILL.md)'s transport
table. `source-icon`, `create-icon`, `edit-icon` and `analyze-icon` are free
and bounded one-reply: use the generic `inquiry` row there instead.

## Round-trip and approvals

For generate-icon, relay the approved `what_for`/`style`/`background`/
`palette`/`reference` unchanged; on a `revise`, pass the previous delivery's
absolute path so the hands re-read its `prompt.txt` and keep the same `<bg>`
and finish options — only the field the user actually asked to change
differs. `generate-icon` does not produce an SVG: when a dependent
`create-icon` form needs one, relay that gap as its own dependency finding
rather than asking generate-icon for a file it cannot make, and offer
`edit-icon` sizes instead — see "An icon set is two forms" above for the
two-form sequencing. Two independent icon forms (a light and a dark
variant, for example) may run in separate `specialist_call` conversations in
parallel.
