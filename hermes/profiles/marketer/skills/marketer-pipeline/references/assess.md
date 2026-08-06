# Assess route (Mode: execute) - the deliverable is judgment, not content

Loaded when the card asks for marketing judgment and no deliverable ships:
direct consultations, critiques of existing assets or drafts, and
market-judgment memos. Three branches, one invariant: **nothing ships,
nothing is produced** beyond illustrative one-liners — even under a P1
grant (the goal decides, not the grant).

## Branch routing

| The card asks for | Branch |
| --- | --- |
| A fast verdict for a direct `single`/`chain` decision (channel fit, feasibility, effort, risk) | Consultation |
| An honest evaluation of an existing asset, draft, or campaign ("is this good enough to post?", "評価して", "忖度なし") | Critique |
| Brand/positioning/market judgment that needs grounding (landmark research, competitor read, audience analysis) | Market judgment |

## Consultation (fast, time-boxed)

The orchestrator needs direct judgment fast — not drafts. Answer this
route from your own knowledge + the brief + quick lookups; a
heavier market question is itself a finding ("needs searcher/researcher
legwork"). **Assume, don't block, by default** — block only when every
plausible reading changes the verdict.

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

## Critique (verify engine as rubric)

Load the verify engine and judge the asset against V1-V5: brief fit, brand
& voice, fact grounding, platform compliance, asset inspection. Rules:

- Lead with the verdict (ship / fix-first / do-not-ship), then findings
  severity-ranked, each naming the failing check + concrete evidence.
- Honest over comfortable — the owner asked precisely because they want
  the un-flattered read. "Do not ship this" is a complete, useful answer.
- **Report, don't repair.** Fixing the asset is a new card for its
  producer; at most sketch the one highest-leverage fix per finding.

## Market judgment

A memo whose value is marketing judgment over raw facts: positioning,
brand landmarks, what an audience will actually react to. Ground it:

- Facts from the brief first; quick gaps, close with your own tools.
- Heavier grounding (competitor scans, cultural checks, multi-source
  hunts) → emit the bounded Assistant-owned FanOutManifest and resume through
  its continuation — do not burn your turns on breadth.
- The memo ends in a recommendation with options, not a data dump.

## Report

- Final message = the assessment/critique/memo (attach via `kanban_attach`
  if long). `kanban_complete` summary = 1-2 plain sentences carrying the
  verdict.

## Pitfalls

- Drifting into a content plan (calendar, skeletons) — that is a shape
  task the orchestrator dispatches if wanted.
- Producing or publishing real copy/assets from this mode.
- Softening a critique to be agreeable, or critiquing without naming
  checks and evidence.
- Blocking on detail an assumption would cover (consultation), or fixing
  the asset in place (critique).

## Verification

- Deliverable follows its branch's format; verdict explicit; assumptions
  labeled; findings name checks + evidence + severity.
- Nothing was produced or shipped; heavy grounding was requested via
  `references/delegate.md`, not ground in-turn.
