# HyperFrames technical references (create-tour / create-ad only)

Scope is narrow on purpose: read this leaf's own local authoring reference
FIRST. These four external directories are optional advisory background,
never a substitute for the leaf's own form, approvals or helper scripts.

Before authoring fresh source, attempt `skill_view(name="hyperframes-core")`
and `skill_view(name="hyperframes-animation")`, then read only the relevant
file via `skill_view(name=..., file_path="...")`; do not list or install.

## What each reference may back

- **hyperframes-core**: composition/timing/determinism concepts only. Not
  its brief/production/review-loop material; that is this leaf's own job.
- **hyperframes-animation**: atomic animation rules and GSAP adapters only.
  Not alternate runtimes, a new scene workflow, or its bundled scripts.
- **cut-the-curve**: only the Waterfall ENTRY and Nudge Curve techniques,
  and only when the already-approved design needs in-scene staging or a
  group slide. Never its seam-injector or ledger system.
- **oversized-cursor**: only for an already-approved pointer-led scene.
  Never add a pointer to footage that already has one. Its sizes and house
  look are advisory only and cannot override the approved design; convert
  any sample `left`/`top` motion to `x`/`y`/`scale`/`rotation` per this
  leaf's own animation contract.

## Hard boundaries

No standalone sub-composition expansion, and no clock/async-timeline/
network pattern from a sample that conflicts with this leaf's local rules
(HyperFrames owns the timeline; no autoplay, no remote requests). No
routing through `hyperframes`, `media-use`, `hyperframes-cli`,
`hyperframes-registry`, `hyperframes-creative`,
or any cross-skill chain outside these four names. No new BRIEF/STORYBOARD/
intake document and no new approval gate; the leaf's existing proposal/
preview/final approvals are unchanged. No `npx`, auto-install, auto-update
or other external script execution. Use only the installed local
`hyperframes lint` and this leaf's existing `freeze`/`snapshot`/`render`
wrappers; never edit frozen source, its hash/pin, or invent client content
or assets that were not supplied/approved.

## When a reference is missing or ambiguous

Attempt the lookup once per needed resource. If it is unavailable,
unreadable, or its name resolves ambiguously, stop trying that one reference
and continue with the local authoring reference for that topic. This is not
a blocker; other successfully loaded references remain usable. Record the
exact skill/file name, the reason, and the local-authoring fallback used in
the job's `qa.md` (outside frozen source) and in the final Report. Do not
speculatively list-all, install, retry, or reroute through another skill,
and do not stop work solely because a reference is absent. An optional
reference simply not needed for this job is `not-needed`, not a failure.
A real missing CLI/runtime dependency, or a failed approval/validation
check, still blocks exactly as it already did.

## Resumes

Resuming a frozen project does not reauthor source or reread these
references just because this policy changed. Preserve whatever was
recorded as consulted/unavailable on the earlier pass; a render-only
resume phase records `not-needed` for this policy rather than a fresh
lookup.

## Reporting

Carry the consulted/unavailable-references summary (and any local-authoring
fallback) into the job's existing `qa.md` and the leaf's Report, appended
after any helper-generated QA, never overwriting it. Name only resources
actually read; availability in the catalog is not evidence of consultation.
