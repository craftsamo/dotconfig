# Plan — image-creator: emoji

Read [common plan](../index.md) first.

## Budget

A metered leaf takes a `budget:` line; absent, the leaf's default applies —
for emoji: 3 anchor candidates, then 1 per item + ceil(items/4) correctives
for the pack.

## Two-round leaves — the shared gate

`generate-emoji` and `generate-mascot` refuse to draw a pack on an
unapproved likeness: the first handoff carries no `anchor` and comes
back with three candidates (emoji: character sheets; mascot: full-body
concepts plus a silhouette sheet and the hands' recommendation). Show
them to the client (a human: the three files + one `clarify` with the
candidates as choices; the assistant: the paths and your pick), then
send `intent: revise <that dir>` with `anchor: <the approved file>` —
the hands print that exact line in their report. A pack that comes back
with items marked `passed: false` is not a failure: the hands ran out
of correctives; you decide whether to send a `budget: N correctives —
<items> only` revise or ship with the marks. Correctives on a
pale-haired or pale-skinned character almost always mean a prop (tears,
sweat, "?") that must be large, saturated and off the hair — say so in
the `note:`.

`generate-mascot` follows this same gate with its own pack-specific
fields and a mascot-only stopping point — see [mascot](mascot.md)
"Two-round leaves — mascot-specific".

## A character lives once

An approved mascot anchor becomes this leaf's `reference:` when the
client's emoji is of an existing mascot — see [mascot](mascot.md) "A
character lives once" for that hand-off, including the two-forms-in-order
case when no mascot exists yet.
