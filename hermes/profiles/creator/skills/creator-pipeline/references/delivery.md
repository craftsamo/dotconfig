# Delivery — the asset handoff and the evidence-backed report (engine)

Load this when produced work leaves the workspace: landing artifacts at
durable paths, running the Review gate, and assembling the final report.
Verification (`references/verify.md`) must already have run — delivery
packages its evidence; it never substitutes for it.

## ArtifactDiscipline

- **Every final artifact lands at a durable path** — the destination the
  brief names (default the owning Group's `.agent/deliverables/<job>/`;
  root `.deliverables/<job>/` only when no single Group owns the work). A
  file that exists only in a tool cache, tmp dir, or scratch workspace is
  a file lost. In a resident session, name every path in the reply. In
  kanban mode, `kanban_attach` every final, copy it to the durable
  destination, and name it in the completion summary.
- Deliver the set, not the darkroom floor: intermediates, rejected
  variants, and raw source frames stay out unless the brief asked for
  them.
- Filenames carry meaning: subject, variant, dimensions
  (`logo-loop_48px_v2.mp4` beats `output_final3.mp4`) — the requester sees
  names before pixels.
- **Preserve the reuse contract**: whatever future work needs to continue
  this — the locked style spec, palette file, seed + reference image,
  voice params, plan/shot list. In a resident session your own context
  holds it; still write the anchor values into the report so a later
  session can inherit from the files alone
  (`references/iterate.md` consumes exactly this).

## ReviewGate

If the brief carries `Review: required`, the resident session presents the
human sign-off (`<ReviewGate>`) in the reply BEFORE the job closes. A kanban
card carrying `Review: required` is malformed per the kernel and must not
run. After verification passes:

1. Land the final assets (and anchor artifacts) at the durable path.
2. Present the review package: per asset — type, dimensions, format; the
   spend tally; verification results; the file paths.
3. Resident session: put the package in your reply and wait — the assistant
   relays it for sign-off; the next message brings the verdict. Kanban
   runtime has no Review block or sign-off round; its card contract is
   `kanban_attach`, durable copy, and completion summary only.
4. `approved` → finish per <ReportAssembly>; `changes — <list>` → treat as
   revise feedback (`references/iterate.md` <FeedbackTriage>) within the
   remaining Budget — a change needing more spend is a question round,
   never a silent overrun — then open a fresh review round.

No `Review:` in the brief → deliver directly; never invent a review round
the spec didn't ask for. This applies to resident sessions; kanban cards are
fire-and-forget and a Review requirement is malformed.

## ReportAssembly

The report — final session reply, or `kanban_complete` summary —
is **evidence-backed**: every claim points at a file, a measurement, or a
reconciled tally.

- **Per asset**: type, dimensions/duration, format, approved Backend, concrete
  tool or local workflow that produced it, and the absolute durable path. For
  core generation, name the configured chain and the provider only when the tool
  reports it. For ComfyUI, name the workflow, checkpoint/model, seed, and
  measured runtime; preserve the approved loopback host, workflow SHA-256,
  effective-graph SHA-256 + allowed injection diff, runner JSON, and same-host
  raw history evidence for its `prompt_id`.
- **Reuse values worth keeping**: prompts, seeds, palette names, voice
  params that would let this work be extended.
- **Verification evidence is itemized** — which V-checks ran
  (`references/verify.md`), what was measured/inspected and the outcomes,
  the intent gate's result (anchor reuse, feedback side-by-side, inventory
  trail). A skipped REQ check is named with its reason, never silent.
- **Spend reconciliation** — final tally vs the effective Budget,
  including failed attempts and corrective passes; granted-but-unused
  headroom noted.
- **Gaps stated plainly** — a best-attempt delivery names what misses the
  brief and why the budgeted passes couldn't close it; honesty here keeps
  the corrective-pass economy working.
- Kanban runtime: the `kanban_complete` summary names every artifact and the
  spend tally in 1-2 plain sentences a non-creator can act on. No review
  round, prompts, or seeds in the summary.

## Pitfalls

- Finishing with artifacts only in scratch/cache — the durable path is
  the delivery.
- Landing files after the Review gate instead of before — a crash between
  question and approval strands the work.
- Reporting "verified" without itemized evidence — an unnamed check
  didn't happen.
- Dropping the anchor/reuse values from the report — the next revision
  pays for the omission in regenerated spend and style drift.
- Treating `changes` feedback as a fresh brief — it is revise feedback
  against THIS delivery, scoped by the remaining Budget.
- Deleting current-job state at producer-verification promotion — remove
  only reproducible caches; keep variants and useful intermediates until
  user acceptance and preserve important anchors outside scratch. The
  orchestrating Assistant owns accepted-job cleanup.

## Verification

- Every final artifact and every reuse-contract artifact exists at a
  durable path (kanban: and is attached); no intermediates shipped.
- The report itemizes V-checks + outcomes, reconciles the spend, and
  names every path and anchor value.
- Review-gated resident-session jobs finished only after an explicit approval.
