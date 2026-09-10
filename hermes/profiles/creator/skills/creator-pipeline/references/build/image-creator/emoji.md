# Build — image-creator: emoji

Read [common build](../index.md) first.

## Transport

`generate-emoji` is metered and runs in a resident session: use the generic
`generate` row (`kind="work"`) in [common build](../index.md)'s transport
table — round A (no anchor) and round B (with anchor) stay in the SAME
conversation whenever the platform keeps it open; a fresh conversation still
carries the exact `revise` line the hands printed. `create-emoji`,
`edit-emoji`, `source-icon` and `analyze-emoji` are free and bounded
one-reply: use the generic `inquiry` row there instead.

## Supervising — the shared two-round relay

Round A returns three character-sheet candidates and stops; relay them to
the client exactly as the hands delivered them (paths + the recommended one),
then send the SAME `revise <that dir>` line the hands printed in their
report, with `anchor:` set to the client's approved file — never a path you
picked yourself. Round B's budget is the leaf's default (3 anchor candidates,
then 1 per item + `ceil(items/4)` correctives) unless the client's `budget:`
line overrides it; preserve it across a revise the same way a metered leaf's
tally survives a resume. An item that comes back `passed: false` in the
manifest is not a failure to relay as a defect: it means the hands ran out
of correctives — bring the choice (`budget: N correctives — <items> only` or
ship with the marks) back to the client rather than deciding it yourself.
`generate-mascot` follows the identical relay shape — see
[mascot](mascot.md) for its pack-specific `pack:`/`items:` fields.
