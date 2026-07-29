# Shape mode — decompose and outline before building

Loaded when the card's deliverable is an **approvable document**, not code:
a requirement decomposition (Issues) or a technical outline (Waves). Absorbs
the former specify and plan modes (their openers still route here). Two
branches:

| Branch | Altitude | Deliverable |
| --- | --- | --- |
| **specify** (ex-specify) | WHAT — high-level requirement → low-level requirement units | intent-labeled unit decomposition; with S2, registered GitHub Issues |
| **outline** (ex-plan) | HOW — implementation goal → coarse Wave milestones | Wave outline + base session id |

The planning ladder (PROFILES.md): assistant owns what/why at feature level →
**specify** owns the feature → requirement-unit split → **outline** owns the
Wave milestones (non-Issue work only) → OpenCode owns phases/units at
implement time. Each rung decides its own altitude ONLY. On GitHub-flow
repos the registered Issues ARE the milestone layer — implement consumes one
Issue per task and no Wave outline is produced for the same work. Never
double-plan.

## Floor rules (both branches)

- **Read-only on the repo.** No commits, edits, scaffolding, installs. The
  only writes are GitHub registrations under S2.
- **A repo must exist.** Shape grounds on a codebase. No repo → report "no
  repo, bootstrap needed" and stop (assess's bootstrap signal); never shape
  against an empty workspace.
- **Ground before splitting.** Read the repo (structure, related features,
  conventions) — or an attached assess report — before decomposing. For
  heavier recon, read-only OpenCode primaries are fine
  (`references/opencode.md`, plain `--auto`; model per <ModelRouting>).
- **Batch ambiguity.** Material requirement choices are `Q<n>` questions in
  ONE checkpoint-then-block round-trip; label small assumptions instead of
  blocking.

## Branch: specify (requirement → Issues)

### The S grant — specify's Authority analog

| Preset | Grants |
| --- | --- |
| `S1` (default) | draft only — deliver the decomposition as an attachment; write NOTHING to GitHub |
| `S2` | S1 + register the approved decomposition (Issues, sub-issue links, board items) via OpenCode |

Missing or unparseable → `S1`. `gh issue delete` is never granted, at any
preset. `AUTHORITY+:` comments can expand S1 → S2 mid-task.

### Units — requirement altitude, one intent each

- Each unit is a user/orchestrator-meaningful requirement sized roughly 1-3
  PRs, with acceptance criteria. Listing files, functions, or steps means
  you dropped an altitude — stop; that is implement's job.
- Every unit must name the real surface it touches (module, route, table,
  integration point) — read the code first; unverifiable units are how specs
  drift.
- **Label every unit with ONE intent token** (core <IntentTriage>):
  `feature` / `bugfix` / `refactor` / `rebuild` / `perf` / `deps`. The label
  travels into the Issue/card body (`Intent: <token>`) and pre-routes the
  implementing engineer's first move and verification profile.
- **Granularity rules the labels enforce** (this is where card sizing is
  decided — downstream dispatchers copy these units 1:1 into cards):
  - one unit = one intent — never mix `refactor` and `feature` in a unit;
    a preparatory cleanup is its own unit, ordered before the feature that
    needs it.
  - `bugfix`: one unit per bug, with the repro (or its source) in the unit.
  - `perf`: one unit per metric target; name the baseline source.
  - `rebuild`: split at the safety boundaries — evacuate → build-alongside →
    cutover — each its own unit.
  - `deps`: one unit per alert group/ecosystem.

### Procedure

1. **Parse** the task: the high-level requirement, target repo, S grant, and
   any `Review:` section (specify bodies normally carry `Review: required —
   the decomposition`).
2. **Ground** on the repo.
3. **Draft the decomposition** (format below).
4. **Ambiguity round** — one batched `Q<n>` block if material choices remain.
5. **Review gate** — with `Review: required`, attach the draft and block with
   a `REVIEW:` headline per core <ReviewGate>. Never register an unapproved
   decomposition.
6. **Register (S2 only, after approval)** — drive OpenCode:

   ```text
   OPENCODE_PERMISSION='{"bash":{"*":"allow","git push*":"deny","gh pr create*":"deny","gh pr merge*":"deny","gh issue delete*":"deny","npm publish*":"deny"}}' \
     opencode run --auto --agent build --model <m> \
     'Register this approved requirement decomposition on GitHub per your
      github-projects conventions (epic issue + sub-issues, board items):
      <the approved decomposition, verbatim — including each unit's
      Intent: label>. Report every created issue number and URL.'
   ```

   Issue/board writes are open here (that is the point of S2); code-shipping
   remains denied — specify never pushes or opens PRs.
7. **Verify independently** (`references/verify.md` spec profile) —
   `gh issue view` the created Issues: bodies match the approved draft
   (intent labels included), sub-issue/parent links exist, board items
   present. Never trust the run's summary alone.

### Decomposition format

```markdown
## Requirement
<the high-level requirement, one line, as the assistant settled it>
## Units
1. <unit intent line — e.g. "Account creation">  (Intent: feature, size: ~n PRs)
   - Acceptance: <criteria, testable>
   - Touches: <grounded surface in this repo>
   - Depends on: <unit #s or —>
2. …
## Open questions
<Q<n> refs already answered, or assumptions labeled>
## Out of scope
<what this decomposition deliberately excludes>
```

## Branch: outline (implementation goal → Waves)

Requirements are already settled; the orchestrator needs a **grounded
technical outline** before implement runs. Deliverable = the Wave outline —
coarse milestones and their order — produced in an OpenCode plan session,
self-assessed, handed back for approval.

- **Shape decides Waves** — human-meaningful milestones + dependency order
  (e.g. `Wave1 theme colors → Wave2 layout → Wave3 sections → Wave4
  responsive`), each a one-line intent, coarse enough to review in seconds.
- **OpenCode owns everything below the Wave** — phase/unit decomposition
  happens at implement time, per Wave. Never write phase-level detail here.
- **Detailed-plan cards** — when the card explicitly asks for a detailed
  plan document (a full PLAN.md, per-file steps, command sequences), the
  deliverable MUST keep two layers separate: a `## Waves` section (coarse,
  one line each — the ONLY part implement consumes as its outline) and a
  clearly-marked `## Reference detail (advisory)` appendix holding
  everything finer. State in the document itself that the appendix is
  advisory: implement re-derives each Wave's phases from it at build time
  (opencode.md <DetailedPlanRule>) — it is never pasted into a build
  prompt as a procedure. Detail that cannot be attached under a Wave goes
  to the appendix, not into the Wave lines.
- An Authority line never authorizes building; outline primaries run plain
  `--auto` (no permission env).

Procedure:

1. **Model** per `references/opencode.md` <ModelRouting>.
2. **Ground** on the repo (or the attached assess report).
3. **Produce the outline** with an OpenCode plan primary:

   ```text
   opencode run --auto --agent plan --title "waves: <goal>" --model <m> \
     'Split this implementation goal into WAVES only — coarse milestones and
      their dependency order, one line each. Do NOT plan phases/units inside a
      wave. <goal, constraints, done criteria, grounded on this repo>'
   ```

4. **Self-assess** — apply the risks lens to your own Waves: what's
   uncertain, where the ordering could be wrong, what a reviewer should
   challenge.
5. **Record the base session id** (`opencode session list`) — this is the
   base implement will fork each Wave from. Put it in the report, a
   `PROGRESS:` comment, and `kanban_complete` metadata.
6. **Report** and complete; approval is the orchestrator's post-completion
   call. `Review: required` in the body → core <ReviewGate> instead.

```markdown
## Goal
<the implementation goal, one line>
## Waves
1. <Wave 1 — one-line intent>
2. <Wave 2 — one-line intent>  (depends on 1)
## Self-assessment
<risks / uncertainties / what a reviewer should challenge — 3-6 lines>
## Base session
opencode plan session <id> — implement forks each Wave from this
## Reference detail (advisory)   ← only on detailed-plan cards
<finer material, per Wave. Advisory: implement re-derives phases from this
at build time (opencode.md DetailedPlanRule); never a build-prompt script.>
```

## MEMORY.md

Outline: nothing durable by default (task-specific; lives in the thread +
attachment). Specify: persist only a genuinely reusable architectural fact
if one surfaced (rare).

## Report

- Final message = the decomposition summary (+ S2: created Issue
  numbers/URLs and the epic link, + assumed vs decided) or the Wave outline
  + self-assessment + base session id.
- `kanban_complete` summary = 1-2 plain sentences (e.g. "Login feature split
  into 4 requirement Issues (#12-#15) under epic #11; ready to implement per
  Issue." / "4-Wave outline: theme → layout → sections → responsive; base
  session s_ab12.") — delivered verbatim to the requester's chat.
- `metadata`: specify → `{"epic": "<url-or-#>", "issues": ["#12", …]}` (S2)
  or `{"draft": "<attachment>"}` (S1); outline → `{"waves": [...],
  "base_session": "<id>"}` — so the orchestrator dispatches follow-up cards
  without re-reading prose.

## Pitfalls

- Decomposing to phases/files/steps — that is OpenCode's altitude at
  implement; units are requirements, Waves are milestones.
- A unit mixing intents (refactor buried inside a feature unit) — split and
  order instead; the granularity rules exist for the dispatcher copying
  units into cards.
- Registering without the Review gate passing, or on S1.
- Hand-crafting Issues with raw `gh issue create` — OpenCode's conventions
  (epic/purpose/work bodies, links, board fields) are the contract.
- Serial ambiguity blocks — batch every requirement question into one round.
- Ungrounded units ("add auth module" with no repo surface named).
- Forgetting the base session id — implement re-plans and the outline
  drifts.
- Bloating the outline into many thin Waves — if it reads like a checklist,
  it's too fine.
- Delivering a detailed-plan card as one undifferentiated document — without
  the Waves / advisory-appendix split, implement inherits a plan it can only
  paste, and the per-Wave decompose gate gets rationalized away.
- Shipping any code, or leaving a Wave outline behind for work the Issues
  now own (double-planning).

## Verification

- Every unit is requirement-altitude, grounded on a named repo surface, with
  acceptance criteria, dependencies, and exactly one `Intent:` label; no
  phase/file detail. Granularity rules hold (no mixed-intent units).
- Material choices went through one batched `Q<n>` round or are labeled
  assumptions; the Review gate ran when required.
- S2 registrations verified with `gh issue view` (bodies, labels, links,
  board items) and reported as numbers/URLs; S1 wrote nothing to GitHub.
- Outline: Waves only, base session id recorded, self-assessment included;
  on detailed-plan cards, fine detail lives in the advisory appendix and the
  Wave lines stayed coarse.
- No commits, edits, installs, pushes, or PRs.
