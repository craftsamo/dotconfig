---
name: orchestration
description: >-
  Front-door control plane shared by assistant on Telegram and default on the
  CLI. Normalize every request into a RequirementSpec, choose the cheapest
  execution shape (inline / single / chain / planned), and keep every Kanban
  registration under Assistant ownership. Planned work uses two explicit
  approvals: a PlanningGraph before specialist planning, then an
  ExecutionOutline before execution. Workers hand off typed FanOutManifest or
  SpecialistPlan data instead of registering cards. Preserve scoped grants,
  QA, scheduled parking, structured block decisions, status reporting,
  idempotent recovery, and truthful archival.
version: 4.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [orchestration, pipeline, requirement-spec, planning-graph, execution-outline, dispatch, routing, kanban, delegation, task-spec, workers]
    category: orchestration
    related_skills: []
---

<Goal>

Turn each request into an explicit outcome and choose the least expensive safe
way to produce it. Inline work ends in chat. Direct work becomes one Assistant-
registered card or a short dependency chain. Planned work follows
`RequirementSpec → PlanningGraph approval → specialist plans → ExecutionOutline
approval → execution registration`. Every card must be self-contained,
subscribed, grant-bounded, and recoverable.

</Goal>

<Scope>
<UseWhen>

- Always in a Telegram DM session: this skill is auto-loaded at session
  start (chat-wide skill binding) — apply <Pipeline> to every request.
- Elsewhere (CLI session, other platforms): load it before any non-trivial
  work.
- A kanban notification (done / blocked / gave up / crashed / timed out)
  needs follow-up: expanding results or re-dispatching.

</UseWhen>
<DoNotUseWhen>

- Never skip <Pipeline>; the sections from <Workers> onward apply only when the
  selected execution shape uses Kanban.

</DoNotUseWhen>
</Scope>

<UserInteraction>

Prefer the `clarify` tool over plain-chat questions whenever the user has
options to pick from. `clarify` shows up to 4 choices as buttons (CLI
arrows → inline buttons → numbered text on simpler platforms) and appends
an automatic "Other (type your answer)" for free-text — one structured
question, no chat noise.

Use `clarify` for:
- Step 1 ambiguity (Projects vs Personal vs cross-cutting)
- Step 2 ambiguity (which group/repo)
- RequirementSpec gaps that change the outcome, scope, cost, or grant
- PlanningGraph and ExecutionOutline approval gates (`references/plan.md`)
- <BlockedTriage> relays (worker questions that come with options)

Plain chat is fine only when:
- The question is open-ended with no meaningful preset options — even then,
  `clarify` with no `choices` is cleaner than prose.
- You're informing, not asking.

Rules:
- **One question at a time.** `clarify` enforces this; don't stack.
- Put your recommendation in the question text ("I'd pick X because …"),
  not as a fifth option.
- **Max 4 choices.** The auto "Other" covers free-text — don't bypass this
  by pouring more options into chat around the call.

</UserInteraction>

<Pipeline>

Every request walks the same front door. Capability references are composable
dispatch aids, not mutually exclusive request approaches.

```
Step 1  Classify     Projects | Personal | cross-cutting | neither
Step 2  Locate       <Group> (and repo if Projects)
Step 3  Normalize    RequirementSpec
Step 4  Shape        inline | single | chain | planned
                       ├─ inline  → answer and stop
                       ├─ single  → register one TaskSpec
                       ├─ chain   → register 2-3 settled TaskSpecs
                       └─ planned → references/plan.md (two approvals)
Step 5  Register     Assistant only; validate grants, skills, parents, keys
Step 6  Supervise    notifications, manifest handoffs, blocks, QA, failures
Step 7  Deliver      verified result in the front-door persona
```

Classify, Locate, normalization, and shape selection are silent unless a
material ambiguity requires `clarify`. Load `references/inline.md`, `build.md`,
`search.md`, `research.md`, or `creative.md` only for the capabilities present
in the selected shape. Planned work always loads `references/plan.md` too.

</Pipeline>

<Step1Classify>

Sort the request by where its work lives:

| Request kind | Category |
| --- | --- |
| Code, repos, builds, project docs/data | **Projects** (`~/Workspaces/Projects/<Group>/`) |
| Personal data & automation (people, household-budget, etc.) | **Personal** (`~/Workspaces/Personal/<Group>/`) |
| Cross-cutting notes, scratch, deliverables, inbox triage | **cross-cutting** (`~/Workspaces/.{notes,scratch,deliverables,inbox}/`) |
| Pure conversation / emotion / opinion / no workspace | **neither** |

- Decide silently; surface only if ambiguous enough to merit a `clarify`
  (e.g. a request that could be Projects or Personal).
- Note: there is a `Projects/Personal/` directory — that is a project group
  named "Personal", not the Personal category. Disambiguate by path level:
  the **category** is the first segment under `~/Workspaces/`.

</Step1Classify>

<Step2Locate>

Identify the workspace concretely:

- **Projects**: identify the `<Group>` (e.g. `CareerCodeClub`, `SEVENDAO`)
  and the `github/<repo>` if code work is implied. Confirm via the registry:
  `pj show <Group>` returns identity, repos, links, members. The full path
  becomes `~/Workspaces/Projects/<Group>/github/<repo>` for code, or
  `~/Workspaces/Projects/<Group>/{docs,data}` for project prose/data.
- **Personal**: identify the `<Group>` (e.g. `HouseholdBudget`, `People`).
  No registry — directory lookup only. The full path is
  `~/Workspaces/Personal/<Group>/{data,docs}`. **Personal data is
  sensitive**: never dump raw values to chat or send externally without an
  explicit OK.
- **cross-cutting**: pick the right `.{notes,scratch,deliverables,inbox}/`
  subdir.
- **neither**: no workspace; the request lives entirely in chat/memory.

Surface a `clarify` only if the user's reference is ambiguous between
several groups/repos.

</Step2Locate>

<RequirementAndShape>

Normalize the request into this in-memory `RequirementSpec` before doing work:

```yaml
request_id: <new stable run id for this user request>
goal: <outcome and beneficiary>
done_criteria: [<observable checks>]
constraints: [<scope, deadline, prohibited actions>]
audience: <optional>
scope: <optional workspace/repo boundary>
inputs: [<paths, URLs, task ids, supplied facts>]
open_questions: [<only material unresolved decisions>]
```

Infer fields from the request, workspace, and stable preferences. Ask one
`clarify` only when an unresolved item changes the outcome, scope, cost,
irreversible action, or grant. Do not turn obvious requests into a form-filling
interview.

Choose one execution shape:

| Shape | Use when | Approval |
| --- | --- | --- |
| `inline` | conversation, local workspace operation, cron registration, or a quick lookup | only the operation's own confirmation |
| `single` | one settled outcome owned by one Worker | no planning approval; normal grant/Review rules still apply |
| `chain` | 2-3 settled stages with obvious dependencies and no specialist planning decision | no planning approval; each TaskSpec must already be settled |
| `planned` | 3+ likely cards, 2+ specialist profiles, fan-out/fan-in, distributed grants, meaningful uncertainty, or irreversible coordination | PlanningGraph and ExecutionOutline approvals |

Implementation is `planned` when architecture, scope, dependency, migration,
or grant decisions remain. A narrow implementation whose RequirementSpec and
method are already settled may be `single`. When uncertain between `chain` and
`planned`, choose `planned`; when uncertain between `inline` and Kanban, ask one
question. Medium parallel lookups for a waiting user may use `delegate_task` in
turn. Dispatch ticks run roughly every 15 seconds, so keep quick work inline.

</RequirementAndShape>

<Workers>

Keep in sync with each worker's `profile.yaml` description:

| Assignee | Sweet spot | Technics (pin via `skills:`) | Tools |
| --- | --- | --- | --- |
| planner | integrates approved specialist plans into one ExecutionOutline (assignees, technics, grants, parents) for the second user approval; plan-only, never executes or registers cards | — | file, web |
| searcher | retrieval, routed by deliverable: targeted lookups (facts/links/latest), enumerations and surveys with an explicit coverage claim, exhaustive multi-hop source hunts (signal with `goal_mode`) | **always pin `searcher-pipeline`** (see note below); no optional technics (`deep-retrieval` is a deprecated stub — use `goal_mode` instead) | web, x_search |
| researcher | depth: analysis, synthesis, comparison, evaluation, reports; external claim/source/specification verification; evidence-backed guidance consumed by a downstream worker or QA | **always pin `researcher-pipeline`** (see note below); optional learned retrieval aids when actually present | file, web, vision, video |
| engineer | implementation + GitHub flow: drives OpenCode — code changes, debugging, tests, builds, PRs; specifies requirements into Issues, works from Issues, answers PR reviews, syncs Projects boards; confirms material decisions via block round-trips | **always pin `engineer-pipeline`** (see note below); optional: `opencode-env`, `machine-env` | terminal (hermes-cli) |
| creator | ALL media production: image, video, GIF, voice assets, batch and single; media advisories (feasibility, chain fit, cost) and style-anchor plan rounds; revisions (`Intent: revise` + previous-card pointers) and salvage of interrupted work; delivers via kanban_attach | **always pin `creator-pipeline`** (see note below); canonical leaves come from `workflow-contract.yaml`, including generated/deterministic image, diagram, audio/song, sourced GIF/brand assets, generated/browser/Manim/ASCII/pixel video, p5.js, and comic routes; external support: `hyperframes`, `media-use` | media gen chains + terminal |
| writer | text deliverables: reader-facing prose (marketing long copy, tech articles/blog, documentation) AND producer-facing scripts (漫画台本, 絵コンテ, storyboards, screenplays consumed by creator/artists); tone-calibrated JP quality; drafts only — never publishes | **always pin `writer-pipeline`** (see note below); Japanese norms layers auto-route inside the pipeline — never pin `japanese-*` | file, web |
| qa | independent read-only gate for final Creator/Writer candidates; inspects actual parent artifacts and consumes predeclared Researcher evidence; never edits or researches | **always pin `qa-pipeline`** plus every mapped `qa-*` technic from its capability table: `qa-raster-image`, `qa-infographic`, `qa-svg-diagram`, `qa-excalidraw-diagram`, `qa-icon-set`, `qa-text-visual`, `qa-pixel-art`, `qa-ascii-art`, `qa-data-visualization`, `qa-video`, `qa-pixel-video`, `qa-ascii-video`, `qa-audio`, `qa-song`, `qa-voice`, `qa-browser-media`, `qa-sourced-asset`, `qa-comic`, `qa-prose`, `qa-script` | terminal (read-only probes), file, browser (supplied artifact only), vision, video |
| marketer | campaign orchestration + approved publishing (X via xurl): consultations and honest critiques of assets/drafts (assess), content strategy/calendar (shape), post/thread copy + ship within a Publish grant (campaign); fans out prose to writer, media to creator, research to searcher/researcher | **always pin `marketer-pipeline`** (see note below); optional: `social-video-research` (platform-native format/spec recon) | terminal (hermes-cli), web, browser, x_search |

Two-tier vocabulary: the **profile** is the execution contract (model,
tools, grant type); a **technic** is a task-pinnable playbook passed as
`skills: [...]` on `kanban_create`. Each worker's pipeline skill
(`<profile>-pipeline`) auto-loads via its operating contract — never name
it in a task, with the PIN exceptions: **every engineer card carries
`skills: ["engineer-pipeline"]`, every creator card
`skills: ["creator-pipeline"]`, every writer card
`skills: ["writer-pipeline"]`, every qa card
`skills: ["qa-pipeline", "<mapped qa technic>", ...]`, every marketer card
`skills: ["marketer-pipeline"]`, every researcher card
`skills: ["researcher-pipeline"]`, and every searcher card
`skills: ["searcher-pipeline"]`**. The dispatcher preloads pinned skills
mechanically into the worker's system prompt, which turns those workers'
routing/grant kernels from a prompt-level instruction into a guarantee.
A technic layers ON TOP of the pipeline and never overrides
lifecycle. No technic fits? For production profiles, route to the profile
default and put the technique requirements in the body. QA is the exception:
an unmapped final deliverable is `can't_verify`, never generic review. A
recurring gap is a signal to author
a new technic skill, not a new profile (new profile only when the execution
contract itself differs: toolset/permissions, model, isolated long-term
memory, conflicting standing prompt).

Mixed work commonly flows searcher -> researcher -> engineer, with creator
(assets) and writer (prose) as specialist stages and qa as their final
independent gate. **Only the Assistant registers cards.** When a Worker needs
children, it attaches one `fan-out.yaml` matching `<FanOutManifest>` and blocks
with `FAN_OUT_READY:`. Validate the full DAG, persist its pending overlay,
register only eligible roots, then record an event-bound decision and resume the
obsolete checkpoint through the guarded resolver. The same-profile continuation
remains pending until every direct parent passes CompletionAdmission. Grants do
not propagate: each child TaskSpec carries only the minimum approved grant.
Because the Assistant creates every card, each ordinary child and continuation
must return `subscribed=true`; QA cards follow `<QualityGate>`.
Writer vs researcher: researcher's deliverable is a verified conclusion;
writer's is the text itself (voice, structure, reader experience).
Writer tasks: pass the WritingBrief fields you already know — deliverable
type (copy / article / documentation / script), audience, purpose, medium,
tone, length/budget, source links — in the body; the writer routes prose
vs script and the norms layers itself, and blocks once (tone samples /
missing premises) rather than guessing. Script cards for downstream
production (comic panels, video) should name the artifact file and any
unit/field conventions the producer expects.

In a planned workflow, approved specialist branches run in **plan-only mode**
(see `references/plan.md`). Their deliverable is a `SpecialistPlan`, not the
work product. Searcher and Researcher may supply evidence through an
Assistant-registered FanOutManifest.

The engineer routes internally by **deliverable** (its `assess` / `shape` /
`implement` modes) — the openers below remain supported as explicit hints
and are still the recommended way to pin the altitude on consultation
cards.

The engineer additionally answers at **orient altitude** (assess/facts) — a
read-only situational-awareness pass on a repo / environment. Dispatch an
engineer task whose body opens with `Orient — inform the plan, don't judge
or ship.` and it reports repo / GitHub / env state (structure, conventions,
build/test, open PRs — or "no repo, bootstrap needed") without judging
feasibility or touching code. Use it to ground a plan before Wave 1, or
when the user just asks "what's the state of X"; it needs no planned-work gate
(nothing ships). Distinct from advisory, which judges a proposed change.

When orient reports **"no repo, bootstrap needed"**, the repo must be
established before any OpenCode slice (plan/implement) is meaningful — the
engineer's **bootstrap altitude**, a non-OpenCode write pass (git/gh/
scaffolder). Decide the target (`owner`/`repo`, the
`~/ghq/github.com/<owner>/<repo>` path) and the path — `clone <url>` /
`starter <scaffolder+source>` / `greenfield` (survey starter candidates via
searcher/researcher if needed). Dispatch an engineer task
(`workspace_kind: scratch` — the repo is created at the absolute ghq path,
which persists; a `dir` workspace can't point at a not-yet-existing greenfield
path) whose body opens
with `Bootstrap — establish the repo, don't plan or ship.` carrying a `B1`/`B2`
grant, the target, and the path. It creates the repo + initial commit (B2 also
`gh repo create` + push) and reports the ghq path, remote url, and a suggested
Group/slug. **On completion the assistant registers it** —
`pj repo-set --project <Group> --name <repo> --owner <owner> --url <url>
--ghq-path <path>` then `pj link-repo` (materializes the
`~/Workspaces/Projects/<Group>/github/<repo>` symlink); bootstrap never touches
pj. The repo is then resolvable for plan/implement via `project: <slug>` or the
workspace path. Details: engineer's `references/implement.md` (bootstrap
branch).

The engineer's **specify altitude** concretizes a requirement you settled with
the user. You own the HIGH-level requirement ("login feature", "blog
feature" — what & why, settled in the RequirementSpec); the engineer owns the
LOW-level split ("account creation", "email verification"), grounded on the
repo and registered as GitHub Issues (epic → sub-issues) via OpenCode's own
conventions. Dispatch an engineer task on the repo whose body opens with
`Specify — concretize the requirement, don't build.` carrying the settled
requirement, an `S1` (draft-only, default) or `S2` (+ register the Issues)
grant, and normally `Review: required — the decomposition` so the user
approves the split before registration. It may block once with batched
requirement questions (`Q<n>` — relay per <BlockedTriage>). On completion its
metadata carries the Issue numbers — **dispatch implement per Issue**
(body: `Issue: #n`, usually A2): the Issue is the outline, so no plan slice
is needed for that work. Details: engineer's `references/shape.md`.

The engineer's **plan altitude** turns a settled implementation goal into a
grounded **Wave outline** — coarse milestones + their order — before implement
runs, for work OUTSIDE the GitHub Issue flow (scratch builds, small refactors,
repos without Issues; if specify registered Issues, skip plan and dispatch
implement per Issue). Dispatch an engineer task on the repo (`project: <slug>`,
or `worktree`)
whose body opens with `Plan — outline the Waves, don't build.`; it runs an
OpenCode plan session, self-assesses, and reports the Wave outline plus a
**base session id** (no code). On completion, review the outline (approve
within the grant, or relay a `Review: required` outline to the user), then
dispatch implement from the same repo/worktree — implement forks each Wave
from that base session so the settled outline doesn't drift. Phase/unit detail
inside a Wave is OpenCode's job at implement time, not the outline's. Distinct
from advisory (which judges feasibility) and from the assistant's own Plan
Loop (requirements/scope with the user). Details: engineer's
`references/shape.md` (outline branch).

Engineer implement tasks on GitHub-flow repos can also carry: `Issue: #n`
(work from that Issue; the PR's `Closes #n` closes it — no issue-write grant
needed), a PR-review-response brief (review comments arrived on its PR), and
the Authority override `issues: write` when the task should also update
Issues/board items directly (rare — default is leaving board state to you).

</Workers>

<TaskSpec>

Workers never see this chat — the task body is their entire context. Always
self-contained:

```text
title: <imperative, <=80 chars>
body:
  Mode: <integrate | plan | execute | analyze | retrieve | verify; use the
         assignee's canonical mode from workflow-contract.yaml>
  Goal: <what outcome, for whom — one short paragraph>
  Inputs: <links, paths, parent task ids, pasted data the worker needs>
  Input attachments: [{"name":"...","sha256":"...","purpose":"...",
                      "source_task_id":"..."}, ...]  # exact JSON array of
                      # attachment_spec objects; [] when none.
  Done criteria: <objective checks the worker can verify itself>
  Output: <shape of the final message: language, format, length; name any
          artifact files to produce>
  Constraints: <scope limits, deadlines, things NOT to do>
  Review: <optional — human-approval gate, decided in the RequirementSpec or
           approved ExecutionOutline (see references/plan.md).
           "Review: required — <what to present>"
          makes the worker checkpoint and block with a `REVIEW:` headline
          instead of completing, so the user approves the deliverable
          before the task closes. Omit for fire-and-forget tasks — the
           default stays post-hoc review via the completion notification.>
  QA: <Creator/Writer final deliverables only — `required`; advisory, plan,
       assess/critique and rough cards write `exempt — <reason>`. A QA-gated
        production card never also carries `Review: required`; human approval
        happens after QA pass.>
  Candidate key: <stable card key; mandatory when QA is required>
  Producer QA requirement: <single-line canonical JSON object; mandatory when
        QA is required, with candidate_key, evidence_keys, capability, routes,
        criteria, done_criteria, and output_inventory>
  Budget: <creator tasks only — generation-spend caps; omitted = creator
          defaults. See references/creative.md. Expanded mid-task only via
          AUTHORITY+ comments.>
  Authority: <engineer tasks only — the pre-approval grant, carried over
              from the approved ExecutionOutline or written tight for a
              settled direct task (see references/build.md). Open with a preset level,
             then optional override lines. Anything not granted forces the
             engineer into a block round-trip, so grant what the user has
             already sanctioned and no more.>
  Publish: <marketer tasks only — the publishing grant. Omitted = draft-only:
           the marketer blocks with the exact post text/attachments/
           destination and ships only what a DECISION approves, verbatim.
           P1 grants autonomous posting within named caps (account, post
           count, content scope), e.g. "Publish: P1 @acct, <=3 posts".
           Expanded mid-task only via AUTHORITY+ comments. Publishing is
           irreversible — grant only what the user already sanctioned.>
  Plan: <integration task id; planned execution only>
  Outline key: <stable ExecutionOutline card key; planned execution only>
  Fan-out policy: <forbidden, or allowed assignees / max children / purpose /
                   optional cost cap approved by the graph or outline>
  Registration anchor: <pending-registration anchor; multistage work only>
  Pending manifest digest: <sha256; multistage work only>
  Pending overlay task: <FanOut origin task id; dynamic expansion only>
  Pending overlay digest: <FanOut overlay sha256; dynamic expansion only>
  Pending overlay lineage: [{"task_id":"...","digest":"..."}, ...]
```

Authority presets (shared contract with engineer's `engineer-pipeline` skill):

| Preset | Grants | Give when |
| --- | --- | --- |
| `A1` | commit to the worktree only | **default** — user hasn't sanctioned anything remote |
| `A2` | A1 + push feature branch + open PR | user already asked for a PR / push or approved it in the ExecutionOutline |
| `A3` | A2 + dependency additions/upgrades | user explicitly sanctioned dependency changes |

- **Repo-establishment work** (no worktree yet) uses `B1`/`B2` instead:
  `B1` = create the repo locally + initial commit; `B2` = + `gh repo create`
  + push. See the bootstrap dispatch note in <Workers>.
- **Requirement-decomposition work** uses `S1`/`S2` instead: `S1` = draft
  the decomposition only (nothing written to GitHub); `S2` = + register the
  approved Issues/board items. See the specify dispatch note in <Workers>.
- **Issue/board writes are in no A-preset**: implement tasks that should
  also update Issues or Projects items directly need the override line
  `issues: write` (rare — a PR's `Closes #n` needs no grant, and board
  state is normally yours to update).
- Override lines refine the preset: `scope: only src/foo`,
  `do not touch: migrations/`, `branch: feat/x`. Overrides win.
- An absent Authority section is read as bare `A1` — write it anyway, with
  scope boundaries.
- Mid-task expansions never edit the body: post an `AUTHORITY+: <grant>`
  comment (see <BlockedTriage>). Grants only expand; a shrink means the
  plan changed — revise the plan and issue a replacement task (never edit
  the live task's Authority body).

- Write the body in the language you want the deliverable in.
- Never reference "the conversation above", screenshots, or memories the
  worker lacks; paste or link what matters.
- Scratch workspaces are deleted on completion: require findings in the
  final message / completion summary, never only in files.

</TaskSpec>

<PendingRegistration>

Every `chain` and approved ExecutionOutline with descendants has one immutable
pending-registration manifest matching `workflow-contract.yaml`:

```yaml
anchor: <stable request-run chain key or integration task id>
digest: <sha256 of normalized cards>
cards: [<ordered child_spec objects>]
request_id: <request id, when planned>
integration_task_id: <planner task id, when planned>
```

For a chain, include the complete normalized manifest and digest atomically in
the root body. For planned execution, comment the complete manifest on the
completed integration card with `ORCHESTRATION_PENDING:` before registering any
root. Every root, late-created descendant, replacement, and FanOut continuation
carries `Registration anchor:` and `Pending manifest digest:` in its TaskSpec.
Those fields identify the sole durable pending-state source after a session
reset or origin replacement.

Every QA-bound TaskSpec stores one closed `producer_qa_requirement` object with
`candidate_key`, `evidence_keys`, `capability`, `routes`, `criteria`,
`done_criteria`, and `output_inventory`. Normalize these fields as part of the
card spec and pending-manifest or overlay digest. Do not reconstruct them from
free-form body prose after restart.
Planner integration may deterministically rebind only `candidate_key` and
`evidence_keys` from SpecialistPlan-local keys to final ExecutionOutline keys;
the approved outline fixes that rebound object before execution registration.

Progress is append-only on the anchor:
`PROGRESS: registration valid=<key:id,...> pending=<keys...> replacement=<old:new,...>`.
Never reconstruct pending work from notification order or an obsolete task's
memory. A changed card set gets a new digest and, when approval covered the old
set, the corresponding approval gate again.

A FanOut does not mutate or fork this base manifest. It appends one typed
overlay on the blocked origin:

```yaml
overlay_task_id: <FanOut origin task id>
overlay_key: <checkpoint key>
digest: <sha256 of normalized overlay cards>
cards: [<dependent child and continuation specs>]
lineage: [<ordered prior overlay task/digest identities>]
base_anchor: <Registration anchor, when the origin belongs to a base graph>
base_digest: <Pending manifest digest, when the origin belongs to a base graph>
replaces_key: <base card key replaced by the continuation, when any>
```

Comment it as `ORCHESTRATION_PENDING_OVERLAY:`. A direct single or QA-gated
card with no base graph omits `base_anchor` and `base_digest`; its immutable root
is the overlay task/digest itself. Every overlay child and continuation carries
the unchanged base identity when present, plus `Pending overlay task:`, `Pending
overlay digest:`, and the full ordered `Pending overlay lineage:`. A nested
FanOut appends its parent overlay identity to that lineage. The effective
pending state is the optional base manifest plus this explicit overlay chain; it
is never inferred from obsolete origin memory.

</PendingRegistration>

<FanOutManifest>

A Worker that discovers additional work does not call `kanban_create` and does
not complete first. It attaches one manifest as `fan-out.yaml`, comments its
checkpoint state, and blocks with `FAN_OUT_READY:`. This durable block remains
the retry trigger across notification loss, partial registration, and Assistant
restart. The TaskSpec's approved Fan-out policy bounds what may be registered.

```yaml
origin_task_id: <current task id>
checkpoint_key: <stable name, unique within the origin task>
children:
  - key: <stable child key>
    title: <imperative, <=80 chars>
    assignee: <Workers roster name>
    skills: [<mandatory pipeline pin>, <optional technics>]
    parents: [<child key or existing task id>, ...]
    params: {workspace_kind: scratch, max_runtime_seconds: 600}
    task_spec:
      goal: ...
      inputs: ...
      input_attachments: []
      done_criteria: ...
      output: ...
      constraints: ...
      producer_qa_requirement: <closed object when qa is required>
continuation:
  title: <resume title>
  assignee: <same profile as origin>
  skills: [<mandatory pipeline pin>, ...]
  parents: [<child key>, ...]
  params: {...}
  task_spec:
    goal: ...
    inputs: ...
    input_attachments: []
    done_criteria: ...
    output: ...
    constraints: ...
attachments:
  - name: <durable task attachment name>
    sha256: <digest>
    purpose: <how a child or continuation consumes it>
    source_task_id: <origin task id>
```

On the block/watchdog notification:

1. Run `~/.hermes/profiles/assistant/scripts/kanban-fanout-manifest-probe.sh
   <origin-task-id>` before persisting an overlay or creating any card. Reject
   any probe failure, including a predeclared QA child or continuation. Then
   reject a reused
   `checkpoint_key`, unknown assignee/skill, missing TaskSpec field, parent
   cycle, unresolved parent key, widened grant, or continuation assigned to a
   different profile. Do not improvise a repair; create a corrected replacement
   checkpoint or relay a material decision.
    - If the origin carries `Planning graph:` or `Plan:`, compare the manifest
     with its approved `Fan-out policy`. Only the named profiles, purpose, child
     count, cost cap, and grant ceiling may expand automatically. Missing policy
      means `forbidden`. Anything else is a PlanningGraph or ExecutionOutline
      revision and requires the corresponding user approval before registration.
    - Copy any `Registration anchor:` and `Pending manifest digest:` into every
      child and continuation. Whether or not a base exists, add the current
      origin id/digest and append the prior overlay pointer to the full `Pending
      overlay lineage:`. The continuation replaces only the origin's live result
      owner; it does not mutate the base manifest or prior overlays.
   - Before blocking, the Worker must attach every scratch file needed after its
     completion. Probe each listed attachment, compare its SHA-256, and verify
     every child/continuation Input names the attachment and purpose. An empty
     list is valid only when no intermediate file is needed. Never rely on an
      origin scratch path; it is deleted after completion.
      The `task_spec.input_attachments` field must be `[]` when no attachment is
      consumed, or a single-line JSON array of normalized `attachment_spec`
      objects when an existing attachment is consumed.
2. Validate the complete child DAG and normalize every TaskSpec with an exact
   `Input attachments: [...]` JSON array of attachment_spec objects derived from
   the manifest attachments that task consumes; use `[]` when none. Before any
   card creation, persist the complete child, continuation, and replacement
   specs with `ORCHESTRATION_PENDING_OVERLAY:`. For each QA-bound candidate,
   persist only the immutable QA requirement already carried by its TaskSpec:
   candidate/evidence keys, capability, routes, criteria, and Done criteria.
   A QA `child_spec`, artifact digest, and QA idempotency key do not exist yet.
   This write-ahead overlay and its digest are the restart source.
3. Create only child roots. Use
   `<origin-task-id>:fanout:<checkpoint-key>:child:<child-key>` as each
   idempotency key, require `subscribed=true` for every card, and run the
   task-spec probe. Comment `PROGRESS: fan_out checkpoint=<checkpoint>
   live=<key:id,...> pending=<child-keys...,continuation>` after the returned ids
   match the write-ahead overlay. Ship-ready production and Researcher children
   use the ordinary late-bound QA registration sequence.
4. Keep the continuation as a pending spec with key
   `<origin-task-id>:fanout:<checkpoint-key>:continuation`. Register dependent
   children and finally the continuation only after every direct parent passes
   <CompletionAdmission>. Require `subscribed=true` for the continuation.
5. For a pending downstream, record `replaces_key` in the overlay so it consumes
   the continuation when later registered; never mutate the base manifest. A
   new graph should have no live downstream because descendants are registered
   only after CompletionAdmission. If a legacy or partially migrated downstream
   is already live, keep the origin blocked until the continuation exists, then
   redirect it before origin completion: first `hermes kanban link <continuation-id>
   <downstream-id>`, then `hermes kanban unlink <origin-id> <downstream-id>`.
   Verify the continuation edge exists, the origin edge is gone, and the
   downstream is not `ready` or `running`. Preserve legitimate `scheduled`,
   sticky `blocked`, and `triage` parking states; a waiting descendant remains
   `todo`. Never repoint stale QA; the replacement candidate receives fresh
   late-bound QA after CompletionAdmission.
6. After running the resolver inspection, comment
   `DECISION(FAN_OUT_READY): live_children=<ids>
   pending=<keys> anchor=<anchor> base_digest=<digest> overlay_task=<id>
   overlay_digest=<digest> replacement_qa=<id-if-any>
   block_event=<id> block_digest=<sha256>` and run the resolver `apply`
   operation only after every pending spec, created root, required link, and
   late-bound QA requirement is durable.
   The resumed Worker completes only the obsolete checkpoint. A leaf has no
   downstream to rewire but still requires this guarded decision/resume handshake.
7. Ack live and pending branches. Never poll; subscribed child completion wakes
   the Assistant, which probes the handoff before registering the next stage.

A repeated block is safe: replay the same deterministic keys and verify returned
ids and rewired edges match the recorded map. A changed manifest under the same
checkpoint key is a protocol error; use a replacement checkpoint key.

</FanOutManifest>

<ExecutionRegistration>

The selected execution shape determines registration:

1. **`single`**: create one settled TaskSpec with an explicit assignee, mandatory
   pipeline pin, and deterministic key derived from the request/session anchor.
2. **`chain`**: validate all 2-3 TaskSpecs first, but register only the root.
   Include the complete normalized pending manifest, digest, and deterministic
   keys atomically in that root body. After creation, comment only a pointer and
   progress line on the root; the comment is not a second manifest. After a root completes, run
   <CompletionAdmission>; register the next card only when every input parent
   passes. Downstream bodies list the validated parent ids and exact results
   they consume. This late registration prevents runtime parent promotion from
   bypassing handoff validation.
3. **`planned`**: follow `references/plan.md`. Do not create specialist plan
   cards before PlanningGraph approval, and do not create execution cards before
   ExecutionOutline approval. Execution keys are
   `<integration-task-id>:execution:<card-key>`.

For every create, validate <Parameters>, call `kanban_create`, require
`subscribed=true`, then run
`~/.hermes/profiles/assistant/scripts/kanban-task-spec-probe.sh <id>`. Compare
every immutable create parameter: title/body digest, assignee, parent set,
skills, workspace kind/path, project/tenant, priority, runtime/goal-mode/model
parameters, and the created event. Any mismatch or unobservable field is an
idempotency collision and a hard stop.
If subscription is false, retry once with the same key; if still false, stop and
report. If an idempotent create returns `done`, process its completion
metadata/artifacts synchronously and update the durable map instead of waiting
for a past notification. `blocked`, terminal failure, archived, or active
existing cards enter their normal recovery/status path; never acknowledge them
as a fresh registration. Runtime auto-decomposition stays disabled
(`auto_decompose: false`); no fallback decomposer carries this TaskSpec, grant,
manifest, or QA contract.

</ExecutionRegistration>

<CompletionAdmission>

Every `done` notification is untrusted until its run metadata passes the
canonical completion contract. Before delivery, SpecialistPlan integration,
downstream registration, QA registration, or Publish release, run:

```text
~/.hermes/profiles/assistant/scripts/kanban-completion-probe.sh <task-id>
```

The probe validates `metadata.completion`, summary equality, attached artifact
handoffs, and required role envelopes. A nonzero result is fail-closed:

1. Do not deliver the result or consume it as a parent.
2. Do not register or release any pending descendant. Newly registered chains
   and ExecutionOutlines keep descendants as pending specs until all direct
   parents pass this probe.
3. Comment `CONTRACT_INVALID: <probe errors>` on the task and report the
   malformed handoff. A done card is immutable; create a bounded replacement
   with a fresh recovery key rather than pretending the metadata was repaired.
4. For a production chain, QA must return `can't_verify`; never let a
   digest-only pass compensate for a missing completion or artifact envelope.

When an idempotent create returns an old `done` card, probe it synchronously
before reuse. Cards completed before this fully enforced contract are not valid
inputs to a new graph; replace them under a fresh run/key.

</CompletionAdmission>

<QualityGate>

Every ship-ready Creator `produce` result and Writer completed deliverable is a
candidate until a dedicated `qa` card passes. Advisory, plan, assess/critique,
and rough-draft cards are exempt. Engineer remains on its OpenCode review path.

This asynchronous QA gate requires a source that can own a QA notification
subscription. A classic CLI session has no durable chat subscription: do not
start a ship-ready Creator/Writer chain there. Ask the user to dispatch it from
the messaging Assistant instead; advisory/plan/rough work may still use CLI.

The standard DAG is:

```text
production -> final Researcher fact-check -> qa
production -------------------------------> qa
```

The Assistant creates ship-ready production and any necessary Researcher
evidence with ordinary `kanban_create`, requires `subscribed=true`, and runs
the task-spec probe for every card. Production completion is candidate
progress, not delivery. After verifying the completion probe and artifact
inventory/digest, the Assistant late-binds the necessary final Researcher
fact-check as a normal card. After production and evidence pass
CompletionAdmission, it late-binds QA as a normal subscribed card. QA directly
lists the production card and final Researcher evidence as its parents.
Use idempotency key `<target-task-id>:qa:<qa-contract-digest>` for QA.

Research needed to author the work may also precede production. The production
body carries `QA: required`; Writer `Output` names the complete attached text
file (default `deliverable.md`). The QA body copies the approved Done criteria,
artifact inventory, producer capability/Writer type, parent ids, and the exact
claims plus claim-ledger attachment settled by each Researcher parent. Pin
`qa-pipeline` plus every mapped leaf in QA's `references/capabilities.md`.
Unknown mappings do not fall back: they become `can't_verify`.

Before QA registration, resolve every candidate and evidence attachment to its
actual SHA-256. A producer that cannot compute its own digest may use the
`pending-assistant-probe` sentinel in its completion handoff, but the Assistant
must replace that sentinel with the measured digest in the late-bound QA
TaskSpec. QA then runs mandatory before/after `qa-file-probe.sh` probes and
records the measured digest in `metadata.qa.target_artifacts`. After QA passes,
the Assistant runs CompletionAdmission on production, every Researcher evidence
parent, and QA, recomputes the target digest, and compares it with
`metadata.qa.target_artifacts`. Formal delivery requires this digest-checked
pass.

Materialization never mutates the pending overlay. Compute the normalized QA
TaskSpec and `<qa-contract-digest>` from the immutable QA requirement plus the
resolved candidate/evidence attachment specs. Before creation, comment
`QA_PENDING_MATERIALIZATION: <canonical-single-line-JSON>` on the origin or
integration card. The JSON contains the complete normalized QA TaskSpec,
producer completion event, idempotency key, contract digest, and input digest.
This write-ahead marker is the sole create/reconcile source after restart. Create
QA exactly from it with key `<target-task-id>:qa:<qa-contract-digest>`, verify an
idempotent result matches it, then comment
`QA_MATERIALIZED: requirement=<candidate-key> task=<qa-id>
producer=<target-task-id> completion_event=<producer-completed-event-id>
contract_digest=<qa-contract-digest> inputs_digest=<attachment-set-digest>` on
the origin or integration card. The producer and completion event binding is
mandatory; it lets the watchdog recover a lost completion wake without accepting
a stale materialization. This binding is the restart and replay source.

Every block, failure, and completion notification is normal and wakes the
Assistant. A missing subscription is an invariant violation handled by the
watchdog, not a delivery mechanism. The watchdog also reconciles QA-required
candidates whose materialization wake was lost and completed QA cards whose
handling wake was lost. Never poll the chain.

**Verdict handling:**

- `pass`: run <CompletionAdmission> for QA, the production parent, and every
  Researcher evidence parent, then `kanban_show` them, recompute each target
  digest, and compare it with QA metadata. A missing or malformed completion
  envelope is non-passing and requires recovery. On an
  exact match, send the actual artifact/text first, confirm delivery, then ask
  for optional human approval in a later message. Comment on QA:
  `QA_HANDLED: pass released target=<id> digest=<sha256>`. Assistant acceptance
  checks user intent and inventory; it does not redo specialist QA.
- `fail`: create a bounded, normally subscribed Creator/Writer revision from
  the itemized findings with key `<failed-qa-id>:revision:<spec-digest>` and a
  `Recovery lineage` object naming the failed QA and replaced producer. Keep
  fresh QA as a pending requirement until the revision and any changed Researcher
  evidence pass CompletionAdmission and their actual digests are known. Then
  create QA with key `<recovery-task-id>:qa:<qa-contract-digest>` and comment on
  the failed QA:
  `QA_HANDLED: fail revision=<id> replacement_qa=<id>`.
- `can't_verify`: create exactly the missing, normally subscribed Researcher
  verification, packaging repair, or canonical QA support with key
  `<source-task-id>:recovery:<kind>:<spec-digest>`. Keep fresh QA pending until
  every recovery parent passes CompletionAdmission and its actual digest is
  known, then register it under the replacement-QA key above. It is never a
  release. Comment `QA_HANDLED: can't_verify recovery=<ids>` after the recovery
  graph exists.

A verdict certifies one parent task and exact attachments only. Never repoint a
completed QA card or let QA edit its input. User `Review:` is approval, not QA;
for a QA-gated final deliverable it occurs only after pass, outside both cards.

**Fan-out cannot bypass a QA gate.** A QA-gated Creator/Writer,
QA-bound Researcher, or Marketer checkpoint attaches `fan-out.yaml` and blocks
with `FAN_OUT_READY:` before completion; it never creates cards. While the
origin is still blocked, the FAN_OUT_READY origin remains normally subscribed;
the watchdog is not its normal notification path:

1. Validate the manifest per <FanOutManifest>. An existing QA verdict is never
   repointed to a continuation or replacement candidate; every new immutable
   candidate receives fresh late-bound QA.
2. Persist children, the same-profile continuation, each candidate's immutable
   QA requirement, and any later Marketer continuation in one
   pending-registration overlay. Register only eligible child roots. The
   continuation remains a pending spec; QA is materialized only after candidate
   and evidence completion admission and digest resolution.
3. As pending children become eligible, register them and finally the
   same-profile continuation with `kanban_create` and `subscribed=true`. After a
   Creator/Writer continuation completes and passes CompletionAdmission,
   late-bind fresh QA with direct parents consisting of that continuation and
   every final Researcher evidence continuation. QA is a normal subscribed
   card.
4. Register a Marketer continuation only after every latest QA passes
   <CompletionAdmission> and digest checks match. Put
   `QA_PASS_SET: <qa ids + target digests>` in its TaskSpec/comment before
   dispatch. A failed QA creates revision and replacement-QA pending specs; it
   never releases or links an already-live publisher.
5. Comment `DECISION(FAN_OUT_READY): ...` and retire the origin once the overlay,
   eligible roots, candidate specs, QA requirements, and replacement mapping are
   durable. QA need not exist yet. The resumed origin completes only its
   obsolete checkpoint; subscribed roots drive later stages.

For the **Researcher** variant, the final artifact still lives on the original
Creator/Writer production card. Preserve that production id in the pending QA
spec, register the final Researcher continuation only after its Searcher inputs
pass, then late-bind fresh QA with direct parents
`[original-production-id, final-researcher-continuation-id]`. The original
Researcher task is a checkpoint, not a replacement-QA parent.

</QualityGate>

<Parameters>

- `assignee` is required — tasks without one never dispatch. Use an exact
  roster name from <Workers>; the dispatcher never validates it, and a card
  with an unknown assignee sits unclaimed with no error.
- `workspace_kind`: `scratch` (fresh tmp, deleted on completion) is right for
  searcher/researcher and specialist planning branches. Coder work
  on a repo: `worktree` + absolute `workspace_path`, or `project: <slug>`
  for a deterministic project branch. `dir` (shared directory, absolute
  path, no isolation) is rare.
- `priority` (int): dispatcher tiebreaker among ready tasks; higher = sooner.
- `idempotency_key`: set when retrying or re-dispatching — a duplicate card
  returns the existing task id instead of forking work.
- `max_runtime_seconds`: cap runaway tasks (exceeded -> SIGTERM + `timed_out`).
  Set small (e.g. 600-900) for specialist planning and retrieval branches.
- `skills: [...]`: force-load a specialist skill installed on the assignee's
  profile when the task depends on it, plus the mandatory pipeline pins (see
  <Workers>). Learned skills are not stable dispatch identities.
- `goal_mode: true` (+ `goal_max_turns`): open-ended cards where one shot
  rarely finishes — a judge loops the worker until done or budget exhausted.
  Searcher's exhaustive source hunts are the classic case (goal-looped Hunt).

</Parameters>

<Scheduled>

Time-deferred work ("金曜にやって", "hold until the invoice arrives") lives
on the board in the `scheduled` column — not in chat memory, MEMORY.md, or
a cron prompt. `scheduled` is a parking state with **no built-in timer**;
the release mechanism is the assistant's sweeper cron
(`kanban-scheduled-sweeper`, every 15 min), which reads each scheduled
card's newest `SCHEDULED:` comment.

- **New deferred task**: `kanban_create(..., initial_status="blocked")` —
  never a plain create, a `ready` card can be dispatched within ~15 s,
  before you can park it — then park it via terminal:
  `hermes kanban schedule <id> "until=<ISO8601> — <reason>"`.
  Park **in the same turn, immediately**: a created-blocked card carries no
  block event, so `recompute_ready` treats it as non-sticky and can
  auto-promote it to `ready` on the next tick. If it slipped to
  `ready`/`running` before you parked it, run the same schedule command
  anyway — it accepts both and clears any claim.
- **Existing card**: same CLI; works from todo/ready/running/blocked.
- **`until=` format**: local-time ISO 8601, e.g. `until=2026-07-25T09:00`
  (same shape as upstream's planned `schedule --at`, so a future migration
  is a find-replace). The CLI stores the text as a `SCHEDULED: …` comment;
  the sweeper unblocks the card on the first sweep past that time
  (→ `ready`, or `todo` while parents are open) and normal dispatch +
  completion notifications take over — subscriptions survive scheduling.
- A scheduled card whose newest `SCHEDULED:` comment has **no `until=`**
  is a manual hold: the sweeper skips it; release it with
  `hermes kanban unblock <id>` when the user says so.
- Condition-deferred (not time-deferred) work: prefer a `parents` link when
  the trigger is another task; `scheduled` + manual release when the
  trigger is external to the board.

</Scheduled>

<AfterCreate>

- Creating from a gateway chat auto-subscribes this chat to the task's
  terminal events; the create call returns the task id.
- `<QualityGate>` uses the same subscription contract as every other card.
  Ack the production, evidence, and QA stages separately; candidate completion
  is progress and formal delivery follows the digest-checked QA pass.
- Ack immediately in the persona's voice: what was dispatched, to whom, the
  task id. Then end the turn — never poll, busy-wait, or promise a completion
  time.
- Completion arrives as an automatic template notification (✔ + title + first
  summary line + artifacts). When the user wants more, `kanban_show <id>` and
  present the result in the persona's voice — summarize, never paste raw
  worker output.

</AfterCreate>

<Failures>

Notifications also fire for `blocked`, `gave_up` (after `failure_limit`
failed runs), `crashed`, and `timed_out`:

1. `kanban_show <id>` — read status, comments, and the worker's last report.
2. State the cause plainly in chat; never hide a failure.
3. Blocked on a question -> apply <BlockedTriage> below.
4. Separate replay from replacement. A transient create/subscription transport
   failure may replay the **same immutable spec** under the same key. A broken,
   impossible, or changed spec is a replacement with key
   `<source-task-id>:recovery:<kind>:<spec-digest>` and a `Recovery lineage`
   object containing `kind`, `source_task_id`, `reason`, `spec_digest`, and when
   applicable `failed_qa_id` / `replaces_task_id`. Never reuse an old key for
   changed work or re-run the same terminal failure unchanged.
5. Wrong worker or scope -> re-route to a new task with the right assignee and
   close out the dead card (step 6), so the board stays truthful.
6. Dead card (superseded spec, duplicate, wrong worker) -> archive via
   terminal: `hermes kanban archive <id>` — there is **no kanban tool** for
   archiving. Permanent delete (`hermes kanban archive --rm <id>`) only on
   an explicit user ask.
7. A dispatched task vanished from `blocked`/`running` and sits in
   `triage` with a `block_loop_detected` event (visible in `kanban_show`)
   -> it hit the block-loop breaker (see <BlockedTriage> — this transition
   does NOT notify chat). Auto-decompose is disabled, so the card just
   sits in `triage` untouched; answer the open `Q<n>`/`REVIEW:` questions
    as usual, record every required `DECISION(...)`, then restore the card with
    `~/.hermes/profiles/assistant/scripts/kanban-resolve-block.sh apply <id>`. The
   wrapper verifies a decision follows the latest block, restores `triage` to
   `todo`, resets recurrence state, and lets the dispatcher promote it.
8. A `🚨 kanban watchdog` chat message (the `kanban-orphan-watchdog` cron,
   every 5 min) lists generic no-subscription invariant violations, completed
   QA cards whose handling wake was lost, and block-loop triage falls. For each listed id:
   `kanban_show`, then apply <BlockedTriage> (blocked), the normal failure
   recovery above (failed), or step 7 (triage fall). Manifest children answer
   to the durable fan-out map on their origin checkpoint; read the relevant
   production, evidence, and QA threads first.

</Failures>

<BlockedTriage>

Engineer (and other workers) block with numbered questions + options + a
recommendation. The block round-trip is the worker's conversation channel —
answer it fast and keep the loop moving.

**Always `kanban_show <id>` first.** The chat notification truncates the
block reason to ~160 chars — it's only a headline (e.g. `Q3: ORM vs raw
SQL?`); the full `STATE:` note and `Q<n>:` questions (options +
recommendation) live in the task comments.

A graph-change block is an internal handoff, not a user question. For
`FAN_OUT_READY:`, read the attached `fan-out.yaml`, apply <FanOutManifest>, and
run `kanban-fanout-manifest-probe.sh` before any mutation. Apply <QualityGate>
atomically, persist the pending overlay, and
register only eligible roots. Then run the resolver inspection, comment
`DECISION(FAN_OUT_READY):` with its event/digest binding, and resume through
the resolver `apply` operation. Any noncanonical graph-change marker is a protocol error after
migration: do not normalize or register it; require a replacement Worker run
that emits the canonical manifest. Never unblock until descendants are rewired
and any stale QA is gone.

**Review gate first.** If the block headline starts with `REVIEW:`, the
task body carried `Review: required` and the worker is presenting its
deliverable for human sign-off. NEVER answer it autonomously, whatever the
grant — relay to the user (a `clarify`: approve / request changes, with
the worker's summary and artifacts). On approve: comment
`DECISION(REVIEW): approved` with the latest event/digest binding, then run the
resolver `apply` operation so the worker completes. On change requests, comment
`DECISION(REVIEW): changes — <list>` with the same binding and use the resolver;
the worker revises and opens a fresh `REVIEW:` round.

For everything else, the grant that frames every answer is the task's
**effective grant**: for
engineer, the body's `Authority:` preset + overrides (from the approved
ExecutionOutline, `references/plan.md`, or a settled direct task,
`references/build.md`); for creator, the body's `Budget:` caps
(`references/creative.md`); for marketer, the body's `Publish:` line
(absent = draft-only) — each plus any prior `AUTHORITY+:` comments.
Two altitudes to keep straight:

- **Feasibility altitude** (the approved premise was wrong on a material point:
  an assumption turned out impossible, scope needs re-thinking, architecture
  has to change) — this changes the approved contract. Relay it to the user.
  For `planned`, rerun approval gate 1 when the PlanningGraph changes or create
  a Planner revision and rerun approval gate 2 when the ExecutionOutline
  changes. Replace affected live cards instead of widening their bodies. For a
  direct shape, normalize a replacement TaskSpec. Resolve the blocked origin
  only as superseded through an event-bound decision and the resolver.
- **Execution altitude** (a tactical call inside the agreed plan: which
  library, how to name a symbol, whether to add a test for an edge case)
  — handle inside the effective Authority:
  - **Within the Authority / the user's already-stated intent** -> answer
    autonomously (pick the worker's recommendation unless the grant argues
    otherwise), bind the decision to the latest block, and resume through the
    resolver. Report the decision to the user in
    one short line afterwards — inform, don't ask.
  - **Outside the grant** (push/PR not sanctioned, spend, scope expansion,
    destructive/irreversible, or genuinely the user's call) -> relay the
    question to the user. Prefer a `clarify` with the worker's options +
    recommendation; on reply, bind the decision and resume through the resolver.
  - **Marketer P0 publish approvals are always the user's call.** An
    `APPROVAL:` block headline (kind=needs_input — same always-relay
    contract as `REVIEW:`) marks it; the exact post
    text/attachments/destination live in the task comments and are relayed
    verbatim (publishing is public and irreversible — never approve a post
    autonomously, whatever the chat context); the approved text is echoed
    back in `DECISION(APPROVAL):` with the latest event/digest binding so the
    worker ships it verbatim.

Answer format — the respawned worker parses comments mechanically (the resolver
does not carry the decision text):

- First run
  `~/.hermes/profiles/assistant/scripts/kanban-resolve-block.sh inspect <id>`.
  It returns the latest blocking event ID and a digest of that event's reason
  plus exact question/gate comments. Append the returned
  `block_event=<id> block_digest=<sha256>` binding verbatim to every decision in
  this batch; a stale decision from an earlier block must never authorize the
  current one.
- One `DECISION(Q<n>): <choice> — <short reason>` comment line per open
  question, using the worker's numbering and the binding above. Answer **every**
  open `Q<n>` in the batch before resolving — a half-answered batch is rejected.
- If the answer grants something new (push, PR, deps, wider scope — or for
  creator, extra generation spend beyond the Budget), add an
  `AUTHORITY+: <grant line>` comment — never rely on prose in the decision,
  and never edit the task body for a grant.

Never leave a blocked engineer waiting on a question you can already
answer from the grant or the chat context; never unblock without the
`DECISION(Q<n>)` comments (the respawned worker reads only the comments to
resume).

**After recording every DECISION, resolve through the block wrapper**:

```
~/.hermes/profiles/assistant/scripts/kanban-resolve-block.sh apply <id>
```

Why: the board escalates the SECOND same-kind block of a task's life
straight to `triage` — silently (no chat notification), where it sits
untouched until you notice (`BLOCK_RECURRENCE_LIMIT = 2`;
unblock deliberately never resets the counter, only completion does).
That breaker exists to stop *blind cron-unblock loops*; your answered
`DECISION` comments ARE the human-in-the-loop it wants to force. The wrapper
requires an Assistant decision after the latest blocking event, unblocks the
card, and resets the counter as one guarded operation. Never use it from
automation or without answering every open question. It also handles recovery
after a card fell to `triage` (<Failures> step 7).

</BlockedTriage>

<StatusCheck>

Worker comments are **not** pushed to chat — between dispatch and a terminal
event the board is silent by design. Mid-run visibility is on-demand:

- When the user asks how a task is going ("どうなってる?", "status?"),
  `kanban_show <id>` and summarize the latest `PROGRESS:` / `STATE:`
  comments in the persona's voice — one or two lines, current phase + what's
  next. Never paste the raw comment trail.
- Workers write `PROGRESS:` at their natural boundaries (engineer per
  implementation unit, creator per finished asset), so the newest one is
  the authoritative "where are we".
- No comments yet and the run is young → say it's in progress since <claimed
  time>; suspiciously long with no trail → check `kanban_list` /
  last events for a stale or crashed run instead of guessing.
- "何が保留中?" / what's parked → `hermes kanban list --status scheduled
  --json` (terminal) and summarize each card's newest `SCHEDULED:` comment
  (until / reason). The board, not chat memory, is the source of truth for
  deferred work.
- This is user-initiated only — it does not license proactive polling;
  terminal events still arrive as automatic notifications.

</StatusCheck>

<AntiPatterns>

- Dispatching before the RequirementSpec has `goal`, `done_criteria`, and
  `constraints`, or asking the user to restate fields already evident.
- Bypassing `clarify` for plain-chat questions whenever the user has options
  to pick from.
- Asking the user more than one `clarify` question at a time, or stacking
  options outside the `clarify` call (worker block batches are different:
  answer every open `Q<n>` in one round-trip).
- Using `delegate_task` for durable specialist planning — approved planning
  branches go to Kanban with plan-only TaskSpecs.
- Treating a SpecialistPlan as an execution deliverable or live grant.
- Quick lookups on the board (dispatch ticks) — answer them inline. Media is
  the deliberate exception: it always goes to creator, with a full brief
  from `references/creative.md`.
- Generating or improvising media yourself instead of dispatching creator.
- Dispatching a media task without the MediaBrief essentials (see
  `references/creative.md`) in the body.
- Posting to a public channel yourself, or via any worker but marketer —
  outbound publishing always goes to marketer, and a task without a
  `Publish:` grant means draft-only (the safe default, on purpose).
- Task bodies that depend on chat context the worker can't see.
- Engineer tasks without an explicit `Authority:` preset (an absent section
  is read as bare A1 — write the grant and scope on purpose).
- Editing a task body to change a grant mid-task (expansions are
  `AUTHORITY+:` comments; shrinks are a plan revision).
- Unblocking without a `DECISION(Q<n>)` comment per open question, or
  answering only part of a question batch.
- Calling `kanban_unblock` directly after a DECISION instead of
  `kanban-resolve-block.sh` — the next same-kind block silently escalates to
  `triage`.
- Calling the block resolver from automation, or without having answered every
  open question.
- Answering a `REVIEW:` block yourself, however obvious the approval —
  the review gate exists precisely for the user's own sign-off.
- Moving a card into the `review` column (UI drag or otherwise) — it has
  no supported ingress, and the dispatcher auto-claims review cards for an
  `sdlc-review` run. The human-approval gate is a `REVIEW:` block, not a
  column.
- Parking time-deferred work in chat memory / MEMORY.md / a cron prompt
  instead of `scheduled` + `until=` (<Scheduled>).
- Creating a deferred task without `initial_status="blocked"` — a plain
  create can be dispatched before you park it.
- Answering a block from the 160-char notification headline without
  `kanban_show` (the options and recommendation live in the comments).
- Polling the board after dispatch (notifications are automatic;
  <StatusCheck> is user-initiated only).
- Duplicate cards for the same ask (use `idempotency_key` on retries).
- Registering specialist plan cards before PlanningGraph approval, or execution
  cards before ExecutionOutline approval.
- Letting any Worker or Planner create cards. They return SpecialistPlan or
  FanOutManifest metadata; registration is Assistant-owned, topological,
  subscribed, and idempotent.
- Pinning a `skills:` technic that isn't in the <Workers> table for that
  profile — unknown needs go into the card body + a technic-authoring note.
- Sending `single` or obvious `chain` work through the planned workflow. The
  Planner integrates multi-specialist work; it is not a tax on settled tasks.
- Raw worker reports pasted into chat.
- Naming pipeline categories or this skill's mechanics in chat — the routing
  is silent; the user hears the persona, not the machinery.

</AntiPatterns>
