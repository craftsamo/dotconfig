# Build — image-creator: reimagine

Read [common build](../../SKILL.md) first.

## Transport

`generate-reimagine` is metered and runs in a resident session: use the
generic `generate` row (`kind="work"`) in [common build](../../SKILL.md)'s
transport table.

## Supervising

Relay the photo path and every approved style exactly as filled in Plan —
the photo is sent as the edit input (`image_url`), never as a reference, and
several styles on one photo stay ONE handoff. Preserve `keep`/`background`/
`aspect`/`size` unchanged; a `revise` handoff points at the previous delivery
directory so the hands re-read `subject.md`, `prompt.txt` and
`manifest.json` and keep the same identity lock — only the field the client
actually changed differs, and a note about a drift becomes the corrective
wording, never a fresh identity look unless the note says the lock itself
was wrong. A style whose both candidates failed is one corrective per
style, never a shared corrective spent across styles. Report which backend
member actually received the photo, and any member that refused it, exactly
as the hands stated it — that consent was given once, in Plan's clarify
round, not re-obtained here.
