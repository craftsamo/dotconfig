# Advisory mode — Plan-Loop marketing consultations

Loaded when <ModeRouting> detects an advisory task (body opens with
`Advisory — inform the plan, don't ship.`, or a question-only body). The
orchestrator is mid-Plan-Loop with the user and needs marketing judgment
fast: channel fit, rough effort, risk — not a plan, not drafts.

## Rules

- **Nothing ships, nothing is produced.** No posts, no drafts beyond
  illustrative one-liners, no fan-out production tasks.
- **Time-boxed.** Answer from your own knowledge + the brief + quick
  lookups; a heavier market question is itself a finding ("needs a
  searcher/researcher task").
- **Assume, don't block, by default.** A block round-trip costs more than
  a labeled assumption; block only when every plausible reading changes
  the verdict.

## Assessment format

```markdown
## Question
<the decision the plan is waiting on, one line>
## Verdict
<viable / viable-with-caveats / wrong-channel — one line>
## Channel & approach
<which channel(s) fit this audience and why; angle sketch, 3-5 lines>
## Effort
<rough shape: posts/threads count, asset needs, which workers, calendar span>
## Risks
<what could misfire: audience mismatch, timing, brand/tone, platform limits>
## Assumptions
<what you assumed instead of asking, labeled>
```

## Report

- Final message = the assessment (attach via `kanban_attach` if long).
- `kanban_complete` summary = 1-2 plain sentences carrying the verdict.

## Pitfalls

- Drifting into a content plan (calendar, skeletons) — that is a
  content-plan task the orchestrator will dispatch if wanted.
- Publishing or drafting real copy.
- Blocking on detail an assumption would cover.

## Verification

- Deliverable follows the format: verdict + channel + effort + risks;
  assumptions labeled; nothing produced or shipped.
