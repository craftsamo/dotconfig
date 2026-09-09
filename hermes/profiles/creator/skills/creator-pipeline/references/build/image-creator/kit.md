# Build — image-creator: kit

Read [common build](../index.md) first.

## Transport

`generate-kit` is metered and runs in a resident session, the same
two-round shape as [emoji](emoji.md)/[mascot](mascot.md): use the generic
`generate` row (`kind="work"`) in [common build](../index.md)'s transport
table. `source-kit`, `create-kit`, `edit-kit` and `analyze-kit` are free and
bounded one-reply: use the generic `inquiry` row there instead.

## Supervising

Round A (no anchor) returns a style sheet plus an expanded item list and
stops; relay both to the client before requesting approval — a sheet alone
is not enough. Round B's `revise <dir>` + `anchor:` carries the approved
style sheet, the approved item list and the design lock unchanged; an item
the client adds or removes after that needs its own count/budget
reconfirmation, not a silent batch against the old total. More than 24
items always needs an explicit `budget:` line before round B. Normal/
pressed/hover/disabled each count as one item in that budget, never a free
variant hidden in the count. A PNG that fails the state check stays flagged
in the manifest — do not relay a kit as production-ready by dropping its
failed status, and offer `create-kit` for exact interchangeable geometry
instead of a second `generate-kit` attempt at the same silhouette match.
