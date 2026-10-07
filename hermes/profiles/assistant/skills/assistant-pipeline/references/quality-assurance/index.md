# Quality Assurance mode — you are the gate

Outside creative production, every specialist deliverable - a session turn -
is a candidate until you verified it. Never forward unseen
output in those domains.

The capability contract decides what the reply represents. Creative advice,
analysis findings and proposal/preview stops do not imply missing final media.
Creative production goes
directly through `../../execute-assistant-creative/SKILL.md`; do not apply this
inspection floor or feedback loop to ordinary completions. Only an explicit user
inspection request selects `../../qa-assistant-creative/SKILL.md`, whose bounded
findings contract replaces the automatic revise loop below. Producer checks,
failed/unknown disclosure, approvals and permissions are not waived.

Research/search acceptance uses the agreed proposal or explicitly released
settled brief, not a planning reply mistaken for findings. Specialist QA is a
self-check, never requester independent acceptance; for Researcher the immediate
primary accepts the research and Assistant still gates its returned deliverable.
Existing per-unit criteria and correction limits remain in force. Search
gap-filling retains its domain-specific protocol rather than changing transport.

## Procedure

1. **Receive** — the session turn names the
   artifact paths. Files must be in the job's draft directory
   (the owning Group's `.agent/<YYYYMMDD>-<job>/`; the root `.agent/` only
   for unassigned/cross-group work), never only in a tool cache
   that dies.
2. **Verify** — apply the matching contract from the QA entries
   below. Look at the actual artifact: vision for images, frame sampling
   + ffprobe for video, read the prose, run the checks. For many
   artifacts, fan the per-artifact checks out via `delegate_task` and
   keep only the verdicts in your context.
3. **Feed back** — defects go back to the SAME resident session as a
   normal turn with itemized feedback (what changes, per artifact;
   everything unnamed is preserved; see
   `../execute/resident-sessions.md`). Iterate until
   acceptable — this loop is minutes.
4. **Deliver** — send the verified artifact/text in the persona's voice
   and wait for acceptance. User acceptance is approval, not QA — it
   comes after your own check, not instead of it. A requested user observation
   (such as a targeted listening judgment under creative QA) may be attributed
   evidence for that criterion; it does not replace the other checks.
5. **Clean** — after acceptance, promote canonical keepers to the owning
   Group's `docs/`, `data/`, `assets/`, or repo surface, then clear that
   job's scratch and delivery staging and close its resident session.
   Retain durable notes. Cleanup does not authorize deletion of original
   inputs, producer-owned frozen bundles, proposals, receipts or reuse sources.

Depth scales with stakes: a quick internal artifact gets a sanity look; a
publishing deliverable gets the full contract.

## Common floor (every verification)

- **Preserve the outcome through decomposition**: judge whether the intended
  reader can understand or act on the actual result, not whether it reproduces
  your implementation metaphor. Technical correctness and reader appeal are
  separate questions; an author explanation is not evidence of comprehension.
- **Reconcile assembled versions**: in the existing job notes, record which
  accepted manuscript/media versions the final artifact and saved service object
  contain. A revision invalidates only dependent evidence. A local file, approved
  preview, completed transport and reopened remote draft are distinct states.
  Do not claim the latest version was saved because an earlier one was.
- **Inspect the actual artifact**, never the producer's description of
  it: open the file at its durable path and measure what the brief
  specifies (dimensions, duration, format, count).
- **Judge against the brief**: the settled done criteria, style anchors,
  and platform constraints — not your own taste. Taste calls belong to
  the user; contract violations belong to feedback.
- **Findings are itemized evidence**: per artifact — what was checked,
  the measured/observed value, and the defect (with timecode/coordinates/
  quote) or the pass. An unnamed check didn't happen.
- **External facts need evidence**: claims, citations, provenance, math —
  require the research evidence supplied in the flow; QA checks the
  artifact represents that evidence accurately, it does not re-research.
- **Never repair**: no editing, re-encoding, cropping, rewriting, or
  regeneration during verification. Defects go back to the producer.
- **Cannot verify ≠ pass**: an unreadable file, missing evidence, or an
  unknown deliverable family means NOT verified — obtain what is missing
  (or say plainly it cannot be checked); never deliver on resemblance.

## Capability routing

The selected QA entry uses this common floor. Navigate below only when
another domain is needed; do not recursively reload the selected entry.

| Capability | Contracts |
| --- | --- |
| creative (explicit user inspection only) | [qa-assistant-creative](../../qa-assistant-creative/SKILL.md) - bounded findings; ordinary delivery stays in Execute |
| writing | [qa-assistant-writing](../../qa-assistant-writing/SKILL.md) — per-unit gate (outline / full) + prose / script contracts |
| engineering | [qa-assistant-engineering](../../qa-assistant-engineering/SKILL.md) — per-unit gate + inspection / acceptance |
| research | [qa-assistant-research](../../qa-assistant-research/SKILL.md) — sources, verdicts, inference |
| search | [qa-assistant-search](../../qa-assistant-search/SKILL.md) — per-unit gate + lookup / sweep / hunt contracts |
| marketing | [qa-assistant-marketing](../../qa-assistant-marketing/SKILL.md) — Marketer advice checked, own acceptance, exact save consent, reopened unpublished draft |

Selection rules:

1. Route from the actual final deliverable, not the file extension alone;
   one deliverable may need several contracts (e.g. p5.js + exported
   MP4).
2. Styles and presets (NES, PICO-8, palette names, aspect ratios, house
   style) are criteria inside the brief, not separate contracts.
3. Outside the hands-served acceptance path above, an unmapped deliverable
   family is NOT verifiable — say so and decide
   with the user; never fall back to a generic look-over for a
   publishing deliverable.
