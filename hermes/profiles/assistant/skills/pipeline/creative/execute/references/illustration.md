# Commission — image-creator: illustration

Read [commissioning](../SKILL.md) first.

## Leaves

| Deliverable | Leaf | Notes |
| --- | --- | --- |
| a model-generated text-free still (cover, hero, editorial or article illustration, thumbnail art, background, document or social art) in a named or described look | `generate-illustration` | metered |

## Choosing and filling

A text-free still is this leaf. Exact copy in the picture is a card
([card](card.md)); an icon, an emoji, a mascot, a kit and a reimagined photo
have their own leaves ([icon](icon.md), [emoji](emoji.md), [mascot](mascot.md),
[kit](kit.md), [reimagine](reimagine.md)).

Settle with the user:

- **Use and audience** → `what_for`.
- **Subject** → `subject`: what the picture shows, with no words in it.
- **Look** → `style`: a named art style or a medium, in the user's words.
- **Size and format** → `size` (WxH or an aspect; default 1536x1024) and
  `format` (png, webp, jpg).
- Optional `avoid`, `variants` and `note`.

Budget: the default is 4 variants + 1 corrective, and a handoff states it in
a `budget:` line. A larger batch needs the user's grant first.

A `reference` image leaves the machine for the backend: it needs the user's
explicit consent; a local path is not consent.

A base image for `create-pixel-art` is this leaf first; its delivery becomes
the `source` of the pixel unit.

## Transport

`kind="work"` (metered).

## Round-trip and approvals

The variants come back with one recommended; the user picks one. A corrective
is `intent: revise <path of the previous delivery>` with the change only,
within the grant; beyond it, ask for a renewed grant.
