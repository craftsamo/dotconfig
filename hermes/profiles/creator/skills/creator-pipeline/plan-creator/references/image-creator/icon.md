# Plan — image-creator: icon

Read [common plan](../../SKILL.md) first.

## Budget

A metered leaf takes a `budget:` line; absent, the leaf's default applies —
for icon: 4 variants + 1 corrective.

## An icon set is two forms

"An icon set for the new bot" is two forms: `generate-icon` (the mark),
then `create-icon` from an SVG — which `generate-icon` does not produce,
so say so and offer `edit-icon` sizes instead. Decompose into leaves,
order them by what feeds what, and note the dependency ("form 2's
`source` = form 1's recommended variant"). Fill form 1 completely now;
fill a dependent form only when its input exists. Two independent forms
(a light and a dark icon) can run in parallel — see
[common build](../../../build-creator/SKILL.md). Do not invent structure beyond the
leaves: no menus, presets, or Styles above the form; a request that needs a
leaf that does not exist is `no skill fits` to the client, noted for the
maintainer.
