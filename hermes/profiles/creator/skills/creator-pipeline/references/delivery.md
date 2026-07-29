# Delivery — the asset handoff and the evidence-backed report (engine)

Load this when produced work leaves the workspace: attaching artifacts,
running the Review gate, and assembling the final report. Verification
(`references/verify.md`) must already have run — delivery packages its
evidence; it never substitutes for it.

## AttachmentDiscipline

- `kanban_attach` **every final artifact**. Scratch workspaces are deleted
  on completion — a file not attached is a file lost. Attachments survive
  blocks, so attach BEFORE any Review block, not after approval.
- Deliver the set, not the darkroom floor: intermediates, rejected
  variants, and raw source frames stay out unless the brief asked for them.
- Filenames carry meaning: subject, variant, dimensions
  (`logo-loop_48px_v2.mp4` beats `output_final3.mp4`) — the requester sees
  names before pixels.
- **Attach the reuse contract too**: whatever a future card needs to
  continue this work — the locked style spec, palette file, seed +
  reference image, voice params, plan/shot list. A revise card that cannot
  find the anchor regenerates from scratch and drifts the set
  (`references/iterate.md` consumes exactly this).

## ReviewGate

If the task body carries a `Review:` section (e.g. `Review: required`), the
user signs off BEFORE the task completes. After verification passes:

1. `kanban_attach` the final assets (and the anchor artifacts).
2. Comment a `STATE:` review package: what was produced (per asset: type,
   dimensions, format), the spend tally, verification results, and the
   attachment names — exactly what the `Review:` line asks to present.
3. Block with `kanban_block(kind=needs_input, reason="REVIEW: <one-line
   asset summary>")` — the `REVIEW:` prefix is the contract that makes the
   orchestrator relay to the human instead of answering autonomously.
4. On respawn, read `DECISION(REVIEW):`: `approved` → complete per
   <ReportAssembly>; `changes — <list>` → treat the list as revise feedback
   (`references/iterate.md` <FeedbackTriage>) within the remaining Budget —
   a change that needs more spend is a `Q<n>` round, never a silent
   overrun — then open a fresh `REVIEW:` round.

No `Review:` section → complete directly; never invent a review round the
spec didn't ask for.

## ReportAssembly

The report is **evidence-backed**: every claim points at a file you
attached, a measurement you took, or a tally you reconciled.

- **Per asset**: type, dimensions/duration, format, the chain/provider that
  produced it, and the attachment name.
- **Reuse values worth keeping**: the prompts, seeds, palette names, voice
  params that would let this work be extended — in the final message (they
  are banned from the chat summary, not from the report).
- **Verification evidence is itemized** — which V-checks ran
  (`references/verify.md`), what was measured/inspected and the outcomes,
  the intent gate's result (anchor reuse, feedback side-by-side, inventory
  trail). A skipped REQ check is named with its reason, never silent.
- **Spend reconciliation** — final tally vs the effective Budget, including
  failed attempts and corrective passes; any granted-but-unused headroom
  noted.
- **Gaps stated plainly** — a best-attempt delivery names what misses the
  brief and why the budgeted passes couldn't close it; honesty here is what
  keeps the corrective-pass economy working.
- **Machine-readable handoff** — `kanban_complete(metadata={...})`:
  `assets` (attachment names + specs), `verification` (checks run),
  `spend` (final tally), `anchor` (locked style/palette/seed/voice values,
  when any), `retry_notes`, `residual_risk`. No prompts-as-blobs, no local
  paths.
- **Chat summary** — the `kanban_complete` summary is 1-2 plain sentences a
  non-creator can act on, delivered verbatim to the requester's chat. No
  prompts, seeds, or file paths — those live one layer down in the report.

## Pitfalls

- Completing with artifacts only on disk — attachment is the delivery.
- Attaching after the Review block instead of before — a crash between
  block and approval strands the files.
- Reporting "verified" without itemized evidence — an unnamed check didn't
  happen.
- Dropping the anchor/reuse values from the report — the next revise card
  pays for the omission in regenerated spend and style drift.
- Prompts, seeds, or paths in the chat summary line (report yes, summary
  never).
- Treating `DECISION(REVIEW): changes` as a fresh brief — it is revise
  feedback against THIS delivery, scoped by the remaining Budget.

## Verification

- Every final artifact and every reuse-contract artifact is attached; no
  intermediates shipped.
- The report itemizes V-checks + outcomes, reconciles the spend, and the
  metadata follows the convention (`assets` / `verification` / `spend` /
  `anchor` / `retry_notes` / `residual_risk`).
- Review-gated tasks completed only after `DECISION(REVIEW): approved`.
