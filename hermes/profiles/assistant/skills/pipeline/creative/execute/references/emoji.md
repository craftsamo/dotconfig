# Commission — image-creator: emoji

Read [commissioning](../SKILL.md) first.

## Leaves

| Deliverable | Leaf | Notes |
| --- | --- | --- |
| a custom-emoji pack of ONE character (a face / pet / mascot photo, or described) in a style, across a pack of expressions, for Slack / Discord / Telegram / LINE | `generate-emoji` | metered, TWO rounds: without `anchor` it draws 3 character sheets and stops; the user approves one, then `intent: revise` + `anchor:` draws the pack (default anchor 3 + 1/item + ceil(n/4) correctives) |
| text emoji (承認 / LGTM / 助かる) as a set | `create-emoji` | free; text travels in the `items` field, never as generated pixels |
| a photo cropped to a circle / rounded emoji, a flat-background cut-out, an outline, or a delivered pack re-finished for another platform | `edit-emoji` | free; real background removal is not this leaf |
| findings on an emoji file or pack against a platform (size / format / cap / alpha, 32 px read, identity vs anchor, light / dark), no file | `analyze-emoji` | free |
| a published emoji glyph (Twemoji, Noto, OpenMoji, Fluent) | `source-icon` | free — `icon: twemoji:rocket`, `size: 128`; there is no source-emoji leaf on purpose |

## Choosing and filling

### Budget

A metered leaf takes a `budget:` line; absent, the leaf's default applies —
for emoji: 3 anchor candidates, then 1 per item + ceil(items/4) correctives
for the pack.

### Two-round leaves — the shared gate

`generate-emoji` and `generate-mascot` refuse to draw a pack on an
unapproved likeness: the first handoff carries no `anchor` and comes
back with three candidates (emoji: character sheets; mascot: full-body
concepts plus a silhouette sheet and the hands' recommendation). Show
the user the three files and your pick, asking which to approve, then
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

### A character lives once

An approved mascot anchor becomes this leaf's `reference:` when the
user's emoji is of an existing mascot — see [mascot](mascot.md) "A
character lives once" for that hand-off, including the two-forms-in-order
case when no mascot exists yet.

## Transport

`generate-emoji` is metered and runs in a resident session: use the generic
`generate` row (`kind="work"`) in [commissioning](../SKILL.md)'s transport
table — round A (no anchor) and round B (with anchor) stay in the SAME
conversation whenever the platform keeps it open; a fresh conversation still
carries the exact `revise` line the hands printed. `create-emoji`,
`edit-emoji`, `source-icon` and `analyze-emoji` are free and bounded
one-reply: use the generic `inquiry` row there instead.

## Round-trip and approvals

### The shared two-round relay

Round A returns three character-sheet candidates and stops; show them to
the user exactly as the hands delivered them (paths + the recommended one),
then send the SAME `revise <that dir>` line the hands printed in their
report, with `anchor:` set to the user's approved file — never a path you
picked yourself. Round B's budget is the leaf's default (3 anchor candidates,
then 1 per item + `ceil(items/4)` correctives) unless the user's `budget:`
line overrides it; preserve it across a revise the same way a metered leaf's
tally survives a resume. An item that comes back `passed: false` in the
manifest is not a failure to relay as a defect: it means the hands ran out
of correctives — bring the choice (`budget: N correctives — <items> only` or
ship with the marks) back to the user rather than deciding it yourself.
`generate-mascot` follows the identical relay shape — see
[mascot](mascot.md) for its pack-specific `pack:`/`items:` fields.
