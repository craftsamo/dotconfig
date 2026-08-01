---
name: planner-pipeline
description: Planner's pipeline — turn a settled goal into an approved-ready dependency-graph outline (cards with assignees, technic skills, grants, parents) via tiered investigation and the boundary-based granularity rubric. Plan-only; never creates build cards.
version: 1.2.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [planning, decomposition, outline, kanban, routing, granularity]
    category: orchestration
---

<Goal>

Turn the task body's goal into a **dependency-graph outline** the assistant can
register verbatim after user approval: which cards, who runs each (profile +
technic skills), what each may do (grants), and what depends on what. The
outline is the deliverable — planning ends here; execution belongs to others.

</Goal>

<Scope>
<UseWhen>

- Any planner kanban task: a settled goal that needs multi-card decomposition
  and user-approvable routing/grants.

</UseWhen>
<DoNotUseWhen>

- Requirements are still unsettled (that is the assistant's chat Plan Loop —
  block with Q<n> instead of guessing).
- The work fits one card (report that in the outline: a single-card plan is a
  valid outcome).
- In-repo Wave planning for an implementation card — that is the engineer's
  plan altitude; your outline carries ONE engineer card and delegates Wave
  detail to it.

</DoNotUseWhen>
</Scope>

<Steps>

1. **Read the card.** `kanban_show` the task; parse Goal / Inputs / Done
   criteria / Constraints. A premise that decides the plan's *shape* is
   missing (goal, scope, success criterion) → <Blocking>, don't guess.
2. **Read the parents.** Each parent id in Inputs carries an orient/advisory
   result — `kanban_show` it; summaries name attachments, read those paths.
3. **Investigate (tiered).** See <InvestigationTiers>. Default is Tier 1:
   read the repo/workspace and do light web verification yourself.
4. **Decompose by boundaries.** Apply <GranularityRubric>: split only at
   coordination boundaries, never at process steps. Map every card to a
   profile + technic per <Roster>; write grants per card (Authority for
   engineer, Budget for creator, Publish for marketer, Review where the user
   must sign off on a deliverable).
5. **Write the outline.** Exactly the <OutlineSchema> YAML. Every card body
   must be self-contained (the worker never sees this plan's context beyond
   its own body + parent summaries).
6. **Deliver.** Write the YAML to the workspace (e.g. `outline.yaml`), put the
   full YAML plus a 5-10 line human summary (shape, risks, grants asked) in
   the final message, then `kanban_complete` with a one-line summary and
   `artifacts: [<abs path to outline.yaml>]`.
   - The planner profile has **no terminal tool**, so `kanban_attach` (which
     needs base64 bytes) is impractical for a multi-KB YAML. Passing the path
     in `kanban_complete(artifacts=[...])` copies the scratch file into the
     task's durable attachments before workspace cleanup — same end state.
     Use `kanban_attach` only for something you can inline by hand.

</Steps>

<GranularityRubric>

A card = one worker session's worth of work with verifiable Done criteria.
Split **only** at coordination boundaries:

| Boundary | Split because |
| --- | --- |
| assignee changes | different profile = different process/identity |
| parallelizable | independent branches should fan out |
| human approval gate | Review-gated deliverable isolates the sign-off |
| time deferral | scheduled parts park independently |
| failure isolation | risky step gets its own retry unit |
| fan-in join | synthesis waits on several results |

Never split a straight line of same-profile work into micro-cards (each card
costs a dispatch tick + spawn + context rebuild). Workers fan out sub-tasks
themselves mid-run — don't pre-chop what the worker can request. An engineer
implementation card is bounded by "implement feature X, tests pass, PR" —
Wave/phase detail inside it belongs to the engineer's own plan altitude, not
to your outline.

Engineer **implementation** cards additionally honor the **one-intent
boundary**: one card = one kind of work (feature / bugfix / refactor /
rebuild / perf / deps) — never mix a refactor and a feature in one card (a
preparatory cleanup is its own card, ordered before the feature).
Consultation/decomposition cards (opener-hinted assess/shape slices) sit
outside this list and carry their own contracts. When an implementation goal
needs finer requirement-level slicing than you can ground, don't guess:
put ONE engineer shape card (`Specify —` opener, S1/S2) in the graph and
let its Issue decomposition drive the per-Issue implement cards — the
engineer's split is the granularity source, yours is a copy.

</GranularityRubric>

<Roster>

Two-tier vocabulary: **profile** (execution contract — model, tools, grant
type) + **technic skills** (task-pinnable playbooks, passed as `skills:`).
Pipelines load automatically per profile; you never name them — with the
PIN exceptions: **every engineer card carries
`skills: ["engineer-pipeline"]`, every creator card
`skills: ["creator-pipeline"]`, every writer card
`skills: ["writer-pipeline"]`, every qa card carries `qa-pipeline` plus
every mapped `qa-*` technic, every marketer card
`skills: ["marketer-pipeline"]`, every researcher card
`skills: ["researcher-pipeline"]`, and every searcher card
`skills: ["searcher-pipeline"]`** (the dispatcher preloads pinned skills
mechanically, making those workers' routing/grant kernels a guarantee
instead of a prompt-level hope). Keep
this table in sync with `profile.yaml` descriptions and the orchestration
skill's `<Workers>` table.

| Profile | Sweet spot | Technics you may pin | Grant |
| --- | --- | --- | --- |
| searcher | retrieval, routed by deliverable: targeted lookups, enumerations/surveys with a coverage claim, exhaustive multi-hop hunts (signal with `goal_mode`) | `searcher-pipeline` (MANDATORY pin on every card); no optional technics — `deep-retrieval` is a deprecated stub, use `goal_mode` | — |
| researcher | routes by deliverable: analysis/synthesis (evidence-pack), option comparison with a recommendation (tradeoff-matrix), external claim/source/specification verdicts (fact-check), evidence-backed direction for a downstream worker or QA (guidance) | `researcher-pipeline` (MANDATORY pin on every card); optional learned retrieval aids only when actually present | — |
| engineer | code, tests, builds, PRs via OpenCode; routes by deliverable (assess / shape / implement) — openers (`Orient —` / `Advisory —` / `Bootstrap —` / `Specify —` / `Plan —`) remain valid altitude hints | `engineer-pipeline` (MANDATORY pin on every card), `opencode-env`, `machine-env` | Authority A1/A2/A3, B1/B2, S1/S2 |
| creator | ALL media production (image/video/GIF/voice); media advisories + style-anchor plan rounds; revisions carry `Intent: revise` + previous-card pointers in Inputs | `creator-pipeline` (MANDATORY pin on every card); canonical leaves: `creator-generated-image`, `creator-article-illustration`, `creator-infographic`, `creator-svg-diagram`, `creator-excalidraw-diagram`, `creator-logo-icons`, `creator-text-card`, `creator-meme`, `creator-ascii-art`, `creator-audio-visualization`, `creator-gif-sourcing`, `creator-generated-video`, `creator-ascii-video`, `creator-manim-explainer`, `creator-pixel-art`, `creator-pixel-video`, `creator-knowledge-comic`, `creator-brand-asset-sourcing`; external support: `hyperframes`, `media-use` | Budget |
| writer | reader-facing prose, drafts only | `writer-pipeline` (MANDATORY pin on every card); Japanese norms layers (`japanese-*`) auto-route inside the pipeline — never pin them | — |
| qa | independent read-only audit of a final Creator/Writer candidate; actual parent artifacts + predeclared Researcher evidence; never edits or researches | `qa-pipeline` (MANDATORY) plus mapped leaves: `qa-raster-image`, `qa-infographic`, `qa-svg-diagram`, `qa-excalidraw-diagram`, `qa-icon-set`, `qa-text-visual`, `qa-pixel-art`, `qa-ascii-art`, `qa-data-visualization`, `qa-video`, `qa-pixel-video`, `qa-ascii-video`, `qa-audio`, `qa-song`, `qa-voice`, `qa-browser-media`, `qa-sourced-asset`, `qa-comic`, `qa-prose`, `qa-script` | — |
| marketer | routes by deliverable: assess (consultations, honest critiques of assets/drafts, market-judgment memos), shape (strategy/calendar — nothing ships), campaign (drafts to approval / ship within grant) | `marketer-pipeline` (MANDATORY pin on every card), `social-video-research` (platform-native format/spec recon) | Publish (absent = draft-only) |

- Technic missing for a niche? Do NOT block: route to the
  profile's pipeline default, write the technique requirements into the card
  body, and flag the gap in `plan.notes` as a technic-authoring signal. QA is
  the exception: never invent a generic QA route. Flag an unsupported final
  capability explicitly until a canonical QA leaf exists.
- Suggest a NEW profile in `plan.notes` only when the execution contract
  itself differs (different toolset/permissions, different model, isolated
  long-term memory, conflicting standing prompt) — a different playbook is a
  technic, a different style is a brief.

Every ship-ready Creator `produce` card and Writer completed-deliverable card
has exactly one downstream `qa` card. Advisory, plan, assess/critique, and rough
draft cards do not. The QA card:

- has the production card as a parent;
- also has a Researcher fact-check parent when the final artifact contains
  external factual gating claims (the Researcher card itself depends on the
  production card when it checks final wording/media);
- pins `qa-pipeline` plus every route required by the QA capability table;
- copies the approved Done criteria, expected artifact inventory, producer
  capability/Writer type, and parent ids into its own body;
- never carries a human `Review:` gate — the Assistant owns release and any
  later human approval.

</Roster>

<OutlineSchema>

```yaml
plan:
  goal: <one line — what the user gets when this DAG completes>
  notes: |
    <assumptions, risks, best-effort gaps, missing-technic signals,
     new-profile suggestions (rare)>
cards:
  - key: <local-key>            # unique within this outline; assistant maps to task ids
    title: <imperative, <=80 chars>
    assignee: <profile name from <Roster>>
    skills: [<technic>, ...]    # optional; only technics from <Roster>.
                                # engineer cards: ALWAYS include "engineer-pipeline";
                                 # creator cards: ALWAYS include "creator-pipeline";
                                 # writer cards: ALWAYS include "writer-pipeline";
                                 # qa cards: ALWAYS include "qa-pipeline" plus mapped qa-* leaves;
                                 # marketer cards: ALWAYS include "marketer-pipeline";
                                # researcher cards: ALWAYS include "researcher-pipeline";
                                # searcher cards: ALWAYS include "searcher-pipeline"
    parents: [<local-key>, ...] # optional; omit for roots (roots run first)
    params:                     # optional kanban_create params
      workspace_kind: scratch|worktree|dir
      workspace_path: <abs path, worktree/dir only>
      project: <slug>
      goal_mode: true
      goal_max_turns: <n>
      max_runtime_seconds: <n>
      priority: <int>
    body: |
      Goal: ...
      Inputs: ...               # include parent local-keys as "results of <key>"
      Done criteria: ...
      Output: ...
      Constraints: ...
      Review: required — <what to present>   # only when the user must sign off
      QA: required | exempt — <reason>       # Creator/Writer final only; required
                                              # cards have a downstream qa card
      Authority: A1|A2|A3 ...   # engineer only
      Budget: ...               # creator only
      Intent: new|revise|salvage  # creator produce cards; revise/salvage MUST
                                  # carry source-card pointers in Inputs
      Publish: ...              # marketer only
```

Rules:
- Grants are outline text the user approves — grant only what the task body
  or the requester already sanctioned; when in doubt, the tighter preset plus
  a note in `plan.notes`.
- Every body is written for a worker with zero context beyond that body and
  its parents' summaries.
- Registration mechanics (topological order, idempotency keys) are the
  assistant's job, not yours.

</OutlineSchema>

<InvestigationTiers>

1. **Tier 1 — yourself (default).** Read the repo/workspace with file tools;
   verify library/tool existence with quick web checks. Most plans end here,
   in a single run.
2. **Tier 2 — parents.** The assistant pre-seeded orient/advisory cards as
   your parents; their summaries + attachments are your ground truth. Prefer
   them over re-deriving.
3. **Tier 3 — advisory fan-out (continuation pattern).** Only when the plan
   hinges on a specialist assessment you cannot make (engineer feasibility,
   creator chain/Budget estimate, deep source landscape):
   1. Create advisory cards — body opens
      `Advisory — inform the plan, don't ship.`, `workspace_kind: scratch`,
      small `max_runtime_seconds` (e.g. 600). Breadth sweeps go to searcher
      here — never burn your own turns on exhaustive search.
   2. Create ONE continuation card assigned to `planner`,
      `parents: [advisory ids]`, body = original card id + your working notes
      (attach interim `outline-draft.yaml` if useful).
   3. `kanban_complete` this card (one line: "investigating via N advisories,
      continuation <id>"). Never wait in-process.
4. **Card-creation floor.** Advisory cards + your own continuation card are
   the ONLY cards you ever create. No build/execution cards, ever — those are
   registered by the assistant after user approval.

</InvestigationTiers>

<Blocking>

- Block (`kanban_block(kind=needs_input)`) only for premises that decide the
  plan's shape: the goal itself, scope boundaries, success criteria, or a
  grant posture the requester must pick (e.g. "may the engineer push?").
- Before blocking: comment `STATE:` (what you've read, what's drafted), then
  numbered `Q<n>:` questions — 2-4 options + your recommendation each.
- Everything else is best-effort: proceed and record the assumption in
  `plan.notes`.
- After unblock, a fresh worker resumes from the comments — keep them
  mechanical (`DECISION(Q<n>):` answers are your input).

</Blocking>

<AntiPatterns>

- Doing the work: writing implementation code, producing media/prose, running
  builds. The outline is the only deliverable.
- Creating build cards, or any card that doesn't open with `Advisory —`
  (except your own continuation card).
- Micro-cards along a straight line of same-profile work ("git init" as a
  card); pre-chopping what a worker can fan out itself.
- Wave/phase detail inside an engineer implementation card's body — delegate
  to the engineer's plan altitude.
- Pinning technics not in <Roster>, or inventing profile names — unknown
  needs are `plan.notes` signals, not fabricated assignees.
- Minting grants the requester never sanctioned; widening grants "to be
  safe".
- Blocking for anything answerable by Tier 1 reading, or blocking instead of
  noting a best-effort assumption.
- Exhaustive web research yourself (searcher advisory exists for that);
  burning Opus turns on breadth.
- Outline only in prose — the YAML attachment is the registration artifact.

</AntiPatterns>
