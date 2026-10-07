# Commission — image-creator: reimagine

Read [commissioning](../SKILL.md) first.

## Leaves

| Deliverable | Leaf | Notes |
| --- | --- | --- |
| a user's PHOTO (a person, a pet, an object, a place) re-rendered in a style (3d-character, comic-book, chibi, 70s-street, 80s-anime, risograph, sumi-ink, watercolor, origami, stained-glass, crayon, or described) — the same subject, pose and composition, or `keep: identity` for the style's own scene; one or several styles | `generate-reimagine` | metered (default 2 per style + 1 corrective per style); the photo goes to the backend as the edit input — a human user is told it leaves the machine BEFORE the handoff; output at the photo's own size next to a photo-plus-candidates sheet per style |
| a reimagined photo resized / reformatted, or findings on one | — | there is no edit- or analyze-reimagine on purpose: size and format are the leaf's own `size` / `format` fields (a `revise` on the same lock is free of a new look), and identity against the photo is the leaf's own QA — an emoji or sticker OF the person is `generate-emoji` with the photo as `reference:` |

## Choosing and filling

### Budget

A metered leaf takes a `budget:` line; absent, the leaf's default applies —
for reimagine: 2 per style + 1 corrective per style. For another subject,
read that subject's reference and hands leaf for its allowance.

### Reimagine: the photo as the edit input

`generate-reimagine` sends the uploaded photo to the image backend as the
edit input, whatever it shows - a person, a pet, an object, a place.
[Commissioning](../SKILL.md) "Filling the form" covers upload consent for a
real person's photo; here the same-round consent and the user's
asset-and-upload authorization apply to any of those subjects, not only a
person, because every reimagine photo is an edit input the model receives,
never incidental context. Several styles on one photo are ONE form
(`style: comic-book, 80s-anime`), not one per style: the hands write the
identity lock once and every style is judged against the same note. `keep`
stays at its default unless the user asked for a new scene ("put me in a 70s
New York street" → `keep: identity`; "make this photo a comic" → the
default).

## Transport

`generate-reimagine` is metered and runs in a resident session: use the
generic `generate` row (`kind="work"`) in [commissioning](../SKILL.md)'s
transport table.

## Round-trip and approvals

Relay the photo path and every approved style exactly as filled — the photo
is sent as the edit input (`image_url`), never as a reference, and several
styles on one photo stay ONE handoff. Preserve `keep`/`background`/
`aspect`/`size` unchanged; a `revise` handoff points at the previous delivery
directory so the hands re-read `subject.md`, `prompt.txt` and
`manifest.json` and keep the same identity lock — only the field the user
actually changed differs, and a note about a drift becomes the corrective
wording, never a fresh identity look unless the note says the lock itself
was wrong. A style whose both candidates failed is one corrective per
style, never a shared corrective spent across styles. Report which backend
member actually received the photo, and any member that refused it, exactly
as the hands stated it — that consent was given once, when the form was
filled, not re-obtained here.
