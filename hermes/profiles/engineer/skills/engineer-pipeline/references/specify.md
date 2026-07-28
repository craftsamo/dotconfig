# Specify mode — concretize a requirement into Issues

Loaded when <ModeRouting> detects a specify task: the body opens with
`Specify — concretize the requirement, don't build.`. The assistant has
settled a **high-level requirement** with the user (feature intent: "login
feature", "blog feature"); specify grounds it on the repo and decomposes it
into **low-level requirement Issues** ("account creation", "email
verification", "session handling"), reviews the decomposition, and — with the
grant — registers it on GitHub. No code ships from a specify task.

This is the requirement rung of the planning ladder (PROFILES.md): assistant
owns what/why at feature level; specify owns the feature → requirement-unit
split; everything below (phases, files, tactics) is OpenCode's altitude at
implement time. On GitHub-flow repos the registered Issues ARE the milestone
layer — implement later consumes one Issue per task (`Issue: #n`), and no
Wave outline is produced for the same work.

## The S grant — specify's Authority analog

Specify tasks use S presets, not A1/A2/A3 (nothing is committed; the risky
act is writing to GitHub):

| Preset | Grants |
| --- | --- |
| `S1` (default) | draft only — deliver the decomposition as an attachment; write NOTHING to GitHub |
| `S2` | S1 + register the approved decomposition (Issues, sub-issue links, board items) via OpenCode |

Missing or unparseable → `S1`. `gh issue delete` is never granted, at any
preset. `AUTHORITY+:` comments can expand S1 → S2 mid-task.

## Rules

- **Read-only on the repo.** No commits, edits, scaffolding, installs. The
  only writes are GitHub registrations under S2.
- **Ground every unit on the real repo.** A requirement unit must name the
  real surface it touches (module, route, table, integration point) — read
  the code first; unverifiable units are how specs drift.
- **Stay at requirement altitude.** Each unit is a user/orchestrator-meaningful
  requirement sized roughly 1-3 PRs, with acceptance criteria. If you are
  listing files, functions, or steps — stop, that is implement's altitude.
- **Registration goes through OpenCode.** Its skills
  (`approach-github-projects`, `manage-github-projects`, `git-pullrequest`)
  own the epic → purpose → work body formats and board conventions — the
  same conventions the user's own OpenCode sessions use. Prompt intent,
  never hand-build Issue bodies with raw `gh issue create`.

## Procedure

1. **Parse** the task: the high-level requirement, the target repo, the S
   grant, and any `Review:` section (specify bodies normally carry
   `Review: required — the decomposition`).
2. **Ground** — read the repo (structure, existing related features,
   conventions). For heavier recon, read-only OpenCode primaries are fine
   (plain `--auto`, `--agent plan` / `--agent explore`; model per
   `references/model-routing.md`).
3. **Draft the decomposition** (format below). Every unit: intent (one
   line), acceptance criteria, dependencies between units, rough size,
   grounded surface (what in the repo it touches).
4. **Ambiguity round** — material requirement choices the assistant/user must
   make (e.g. email verification: magic link vs code) are `Q<n>` questions:
   batch them into ONE checkpoint-then-block round-trip (core
   <CheckpointThenBlock>); label small assumptions in the draft instead of
   blocking on them.
5. **Review gate** — with `Review: required`, attach the draft
   (`kanban_attach`) and block with a `REVIEW:` headline per core
   <ReviewGate>. Never register an unapproved decomposition.
6. **Register (S2 only, after approval)** — drive OpenCode:

   ```text
   OPENCODE_PERMISSION='{"bash":{"*":"allow","git push*":"deny","gh pr create*":"deny","gh pr merge*":"deny","gh issue delete*":"deny","npm publish*":"deny"}}' \
     opencode run --auto --agent build --model <m> \
     'Register this approved requirement decomposition on GitHub per your
      github-projects conventions (epic issue + sub-issues, board items):
      <the approved decomposition, verbatim>. Report every created issue
      number and URL.'
   ```

   Issue/board writes are open here (that is the point of S2); code-shipping
   remains denied — specify never pushes or opens PRs.
7. **Verify independently** — `gh issue view` the created Issues: bodies
   match the approved draft, sub-issue/parent links exist, board items are
   present. Never trust the run's summary alone.
8. **Report** per below and complete.

## Decomposition format (the draft and the attachment)

```markdown
## Requirement
<the high-level requirement, one line, as the assistant settled it>
## Units
1. <unit intent — e.g. "Account creation">  (size: ~n PRs)
   - Acceptance: <criteria, testable>
   - Touches: <grounded surface in this repo>
   - Depends on: <unit #s or —>
2. …
## Open questions
<Q<n> refs already answered, or assumptions labeled>
## Out of scope
<what this decomposition deliberately excludes>
```

## Report

- Final message = the decomposition summary + (S2) created Issue numbers/URLs
  and the epic link, + what was assumed vs decided.
- `kanban_complete` summary = 1-2 plain sentences (e.g. "Login feature split
  into 4 requirement Issues (#12-#15) under epic #11; ready to implement per
  Issue.") — delivered verbatim to the requester's chat.
- `metadata`: `{"epic": "<url-or-#>", "issues": ["#12", …]}` (S2) or
  `{"draft": "<attachment>"}` (S1) so the orchestrator can dispatch
  per-Issue implement tasks without re-reading prose.

## Pitfalls

- Decomposing to phases/files/steps — that is OpenCode's altitude at
  implement; units are requirements with acceptance criteria.
- Registering without the Review gate passing, or on S1 — the draft is the
  deliverable until S2 + approval say otherwise.
- Hand-crafting Issues with raw `gh issue create` — OpenCode's conventions
  (epic/purpose/work bodies, links, board fields) are the contract.
- Serial ambiguity blocks — batch every requirement question into one
  `Q<n>` round.
- Ungrounded units ("add auth module" with no repo surface named) — read
  the code first.
- Shipping any code, or leaving a Wave outline behind for work the Issues
  now own (double-planning).

## Verification

- Every unit is requirement-altitude, grounded on a named repo surface, with
  acceptance criteria and dependencies; no phase/file detail.
- Material requirement choices went through one batched `Q<n>` round or are
  labeled assumptions; the Review gate ran when required.
- S2 registrations were verified with `gh issue view` (bodies, links, board
  items) and reported as numbers/URLs; S1 wrote nothing to GitHub.
- No commits, edits, installs, pushes, or PRs.
