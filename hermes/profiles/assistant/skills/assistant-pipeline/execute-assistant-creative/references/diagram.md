# Commission — image-creator: diagram

Read [commissioning](../SKILL.md) first.

## Leaves

| Deliverable | Leaf | Notes |
| --- | --- | --- |
| an architecture, flow, sequence or concept diagram as HTML with inline SVG + PNG renders | `create-diagram` | free, deterministic, exact labels |

## Choosing and filling

Settle with the user:

- **Purpose and audience** → `what_for`.
- **Kind** → `kind`: architecture, flow, sequence or concept.
- **The complete content** → `content`: every node, group, edge and label,
  verbatim. A missing label is a Writer dependency or a question to the
  user, never invented.
- Optional `size` (default 1600x900), `theme` (light or dark) and a
  `reference` diagram to follow.

A diagram whose labels are dense data is still this leaf. An illustrated
scene without exact labels is not: that is `generate-*` work.

## Transport

Free and bounded: `kind="inquiry"` for a small diagram — use the generic
`inquiry` row in [commissioning](../SKILL.md)'s transport table. Use
`kind="work"` when a reference must be studied or several revisions are
expected.

## Round-trip and approvals

No proposal round. A revision is `intent: revise <path of the previous
delivery>` with the changed content only; the hands reread the previous
`labels.json` and HTML.
