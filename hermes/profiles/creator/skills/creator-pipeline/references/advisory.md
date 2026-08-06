# Advisory mode — Plan-Loop media consultations

Loaded when <ModeRouting> detects an advisory task. The orchestrator is
mid-Plan-Loop with the user and needs media judgment fast: is this asset
producible, through which chain, at what Budget — not the asset itself.

## Rules

- **Generate nothing.** No credits spent, no variants "to illustrate".
  The deliverable is an assessment.
- **Answer from the catalog, not by trying.** Chain fit comes from
  `references/produce.md` <AssetRouting> plus the profile's
  available-skills catalog (in-tree + `skills.external_dirs` library);
  prerequisites (running desktop app / MCP) are checked cheaply (`nc -z`,
  process check), never by launching a production run.
- **Assume, don't block, by default** — label assumptions; block (per the
  core comment protocol) only when every plausible reading changes the
  verdict.

## Assessment format

```markdown
## Question
<the decision the plan is waiting on, one line>
## Verdict
<producible / producible-with-caveats / not-with-current-chains — one line>
## Chain & approach
<which chain/skill would produce it and why; style/spec considerations, 3-5 lines>
## Budget estimate
<expected spend in Budget terms: variants/renders per asset, corrective
 passes, batch size — and where overrun risk lives>
## Risks
<quality risks (text rendering, style drift), prerequisite availability,
 platform-spec constraints>
## Assumptions
<what you assumed instead of asking, labeled>
```

## Report

- Final message = the assessment (attach via `kanban_attach` if long).
- `kanban_complete` summary = 1-2 plain sentences carrying the verdict.

## Pitfalls

- Spending generation credits to "check" feasibility — catalog + spec
  knowledge answers it; a genuine unknown is reported as a spike
  recommendation.
- Declaring an asset type unsupported without scanning the opt-in catalog
  (same rule as production).
- Drifting into producing the asset because it seemed cheap.

## Verification

- Deliverable follows the format: verdict + chain + Budget estimate +
  risks; assumptions labeled; zero generation spend
  (`references/verify.md`, advisory profile).
