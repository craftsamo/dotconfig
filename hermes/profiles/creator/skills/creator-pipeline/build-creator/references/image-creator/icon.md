# Build — image-creator: icon

Read [common build](../../SKILL.md) first.

## Transport

`generate-icon` is metered and runs in a resident session: use the generic
`generate` row (`kind="work"`) in [common build](../../SKILL.md)'s transport
table. `source-icon`, `create-icon`, `edit-icon` and `analyze-icon` are free
and bounded one-reply: use the generic `inquiry` row there instead.

## Supervising

For generate-icon, relay the approved `what_for`/`style`/`background`/
`palette`/`reference` unchanged; on a `revise`, pass the previous delivery's
absolute path so the hands re-read its `prompt.txt` and keep the same `<bg>`
and finish options — only the field the client actually asked to change
differs. `generate-icon` does not produce an SVG: when a dependent
`create-icon` form needs one, relay that gap as its own dependency finding
rather than asking generate-icon for a file it cannot make, and offer
`edit-icon` sizes instead — see
[plan/icon.md](../../../plan-creator/references/image-creator/icon.md) "An icon set is two forms"
for the two-form sequencing. Two independent icon forms (a light and a dark
variant, for example) may run in separate `specialist_call` conversations in
parallel — see [common build](../../SKILL.md) "Supervising".
