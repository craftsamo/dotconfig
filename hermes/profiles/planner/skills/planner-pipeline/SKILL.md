---
name: planner-pipeline
description: >-
  Final planning compiler for workflow-contract.yaml v1. In Mode: integrate,
  read the approved RequirementSpec and PlanningGraph plus every final
  SpecialistPlan parent, reconcile them into one schema-valid
  ExecutionOutline, and return execution-outline.yaml for the Assistant's
  second approval. Plan-only: never investigates anew, executes, or creates
  cards.
version: 2.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [planning, integration, execution-outline, kanban, routing, granularity]
    category: orchestration
---

<Goal>

Compile approved specialist planning results into one executable proposal. The
Planner receives settled requirements and final SpecialistPlans; it does not
rediscover the problem or replace specialist judgment. Its only deliverable is
an `ExecutionOutline` that the Assistant can validate, render for approval, and
register verbatim after approval gate 2.

</Goal>

<LifecycleContract>

Follow the canonical lifecycle from `workflow-contract.yaml`:
`admit -> route -> act_or_plan -> verify -> handoff -> terminal`. `admit` the
complete integration TaskSpec and approved planning identities, `route` only to
`Mode: integrate`, `act_or_plan` by reconciling final SpecialistPlans, `verify`
the ExecutionOutline, `handoff` its attached YAML and metadata, then `terminal`
as `complete` or `block`. Planner never fans out or registers cards.

Every completion returns exactly one `metadata.completion` and, because the
ExecutionOutline is attached, exactly one `metadata.artifact_handoff`. The
role-specific `metadata.execution_outline` remains alongside them. A block
returns none of these completion envelopes.

</LifecycleContract>

<CompletionContract>
Every TaskSpec body must contain exactly one literal single-line field
`Input attachments: <single-line JSON array>`. When there are no inputs, the
line must be exactly `Input attachments: []`. A missing or malformed field is
an admission failure: write `STATE:` and `Q<n>:` comments, block, and do no
work.

Decide `FINAL_SUMMARY` exactly once. The terminal call must use
`kanban_complete(summary=FINAL_SUMMARY, metadata={"completion":{"status":"completed","summary":FINAL_SUMMARY,"metadata":ROLE_METADATA,...}, ...})`.
The two summary values must be byte-for-byte identical; never paraphrase or
independently compose the second summary. `metadata.execution_outline` is a
sibling of `completion` directly under the `kanban_complete` metadata argument,
never inside `completion`. Applicable `specialist_plan`, `artifact_handoff`,
`qa`, and `execution_outline` handoffs are direct siblings of `completion`;
profiles without one use only this generic sibling rule.
`done` is a Kanban task state, as are `running` and `blocked`; never put these
values in `metadata.completion.status`. Normal completion status is always the
string `completed`.
</CompletionContract>

<Scope>
<UseWhen>

- A Kanban card has `Mode: integrate` and direct parents that are exactly the
  latest final SpecialistPlan tasks for an approved PlanningGraph.

</UseWhen>
<DoNotUseWhen>

- Requirements or the PlanningGraph are unsettled.
- A specialist branch is missing, still blocked on `FAN_OUT_READY:`, or ended
  at a checkpoint rather than a final SpecialistPlan.
- The request is a single task or an obvious short chain that does not use the
  planned workflow.

</DoNotUseWhen>
</Scope>

<InputContract>

First run `kanban_show` and require a self-contained body with:

```text
Mode: integrate
Request run: <RequirementSpec request_id>
Goal: Integrate the approved specialist plans into one ExecutionOutline.
Inputs: <complete RequirementSpec, approved PlanningGraph key/attachment,
  final specialist task ids, and attachment names>
Input attachments: []
Done criteria: <schema, coverage, DAG, grant, QA, and granularity checks>
Output: execution-outline.yaml plus metadata summary
Constraints: plan only; do not investigate, execute, publish, or create cards
```

`Request run: <RequirementSpec request_id>` is the canonical request identity.
The `request_id` in `metadata.execution_outline`,
`metadata.completion.metadata`, and `execution-outline.yaml` must exactly match
this value. An alternate request-identity label is forbidden; use `Request run:`
only.
The RequirementSpec and PlanningGraph share one `request_id`. Every direct
parent must return exactly one `metadata.specialist_plan` with:

```yaml
origin_task_id: <that final parent task id>
branch_key: <one approved PlanningGraph branch key>
summary: <specialist recommendation>
proposed_cards: [<child_spec objects>]
assumptions: [<optional>]
evidence: [<optional parent ids, URLs, or attachment names>]
```

Reject duplicate branch keys, origin/task mismatches, unknown branches,
checkpoint-only parents, or a missing approved branch. Do not fill a missing
specialty with Planner guesses. Block with one batched `Q<n>` package only when
the Assistant must repair or replace an input.

</InputContract>

<CanonicalContract>

Read the canonical registry at:

```text
~/.hermes/skills/orchestration/references/workflow-contract.yaml
```

Use it for Worker modes, mandatory pipeline pins, active/deprecated technics,
TaskSpec fields, grants, QA routes, and the exact `execution_outline` and
`child_spec` schemas. Do not maintain a second roster in this skill and do not
invent a generic QA fallback.

</CanonicalContract>

<Procedure>

1. **Validate identity.** Confirm `Mode: integrate`, request id equality, the
   PlanningGraph digest/key supplied by the Assistant, and the exact direct
   parent set.
2. **Read final parents.** `kanban_show` each final specialist task and inspect
   its completion metadata and named attachments. Evidence is only a planning
   input; it is not permission to execute.
3. **Account for every proposal.** Map each proposed card to one outcome in the
   RequirementSpec. Merge duplicate candidates only when their goal, assignee,
   inputs, done criteria, and grant are materially the same. Record rejected or
   superseded proposals in `notes` with the reason.
4. **Split at coordination boundaries.** Apply <Granularity>. Preserve useful
   parallel branches and explicit fan-in. Do not split one Worker session into
   process-step micro-cards.
5. **Normalize contracts.** Give every card an exact `child_spec`, mandatory
   pipeline pin, known technics, API-only `params`, self-contained TaskSpec,
   minimum grant, and explicit `fan_out_policy` or `forbidden`.
6. **Build the DAG.** Resolve proposed local parents into final outline keys.
   Every parent key exists, the graph is acyclic, and every downstream TaskSpec
   names the exact parent result it consumes.
7. **Apply gates.** Add the canonical QA route to every ship-ready
   Creator/Writer result. Keep irreversible descendants behind QA, Review, or
   Publish approval as required. Do not emit a QA card in the ExecutionOutline;
   store the immutable QA requirement on the producer TaskSpec so the Assistant
   can materialize QA after candidate/evidence completion admission and digest
   resolution. QA inspects immutable candidate artifacts and never repairs them.
8. **Write and deliver.** Produce exactly <ExecutionOutlineSchema>, save it as
   `execution-outline.yaml`, and complete per <Delivery>.

</Procedure>

<Granularity>

One card is one Worker session with objective done criteria. Split at these
boundaries:

| Boundary | Reason |
| --- | --- |
| assignee changes | different execution contract or tool authority |
| independent work can run in parallel | useful fan-out |
| several results must be combined | explicit fan-in |
| human approval or QA | isolated gate |
| time deferral | independently scheduled work |
| risky action needs isolated retry | failure boundary |
| Engineer intent changes | feature, bugfix, refactor, rebuild, perf, and deps stay separate |

Do not create cards for internal steps such as reading a file, drafting a
prompt, running one command, or performing one verification check. Engineer
Wave detail stays inside one Engineer execute card. Creator asset batches may
stay together when they share one brief, direction, Budget, and QA boundary.

</Granularity>

<ExecutionOutlineSchema>

Write exactly this top-level shape:

```yaml
request_id: <RequirementSpec request_id>
goal: <one-line user outcome>
assumptions: [<explicit best-effort assumptions>]
risks: [<material execution or release risks>]
notes: |
  <merge decisions, rejected proposals, capability gaps, and approval notes>
cards:
  - key: <stable unique outline key>
    title: <imperative, <=80 chars>
    assignee: <known Worker profile>
    skills: [<mandatory pipeline pin>, <active technics>]
    parents: [<outline key>, ...]
      params:
        workspace_kind: <scratch|worktree|dir>
        max_runtime_seconds: <bounded integer>
      task_spec:
        mode: <mode allowed for the assignee>
        goal: <one outcome>
        inputs: <self-contained facts, paths, links, and parent results>
        input_attachments: []
        done_criteria: <objective checks>
        output: <result/artifact and completion shape>
        constraints: <scope and prohibited actions>
      review: <optional human gate>
      qa: <optional Creator/Writer gate>
      producer_qa_requirement: <closed object, mandatory when qa is required>
      grant: <optional minimum Authority, Budget, or Publish proposal>
      fan_out_policy: <forbidden or bounded policy>
```

The required top-level fields are `request_id`, `goal`, and `cards`; the other
top-level fields are optional. Every card has exactly the seven `child_spec`
fields: `key`, `title`, `assignee`, `skills`, `parents`, `params`, and
`task_spec`. Every TaskSpec has `goal`, `inputs`, `done_criteria`, `output`, and
`constraints`; use only optional fields listed by the canonical contract.

`params` contains only Kanban creation parameters such as workspace, project,
priority, runtime, goal mode, or model/provider overrides. Domain briefs,
planning identity, grants, and QA requirements belong in `task_spec`.
Any Creator/Writer TaskSpec with `qa: required` must preserve the closed
`producer_qa_requirement` semantic fields from its SpecialistPlan; never
synthesize them from prose. Build one deterministic local-to-outline key map
before writing cards, then rebind only `candidate_key` and every `evidence_keys`
entry through that map. The rebound keys must name the final ExecutionOutline
cards and are included in its approved digest.

</ExecutionOutlineSchema>

<ReconciliationRules>

- The RequirementSpec is the outcome authority. SpecialistPlans refine how to
  achieve it but cannot widen its scope.
- A PlanningGraph approval authorizes planning only. Proposed cards and grants
  remain inert until the user approves this ExecutionOutline.
- Use the minimum grant. Engineer gets only the required Authority preset and
  overrides; Creator gets a bounded Budget; Marketer defaults to P0 unless the
  RequirementSpec explicitly supports a bounded P1 proposal.
- A SpecialistPlan conflict is not resolved by silently choosing one domain.
  Preserve the conflict in `risks` or block when the choice changes topology,
  scope, cost, grant, or the user-visible result.
- Unknown profiles and technics are notes/capability gaps, not fabricated
  routing. Unknown final Creator/Writer capabilities cannot receive generic QA.
- Every proposed fan-out slot is explicit. Missing policy means `forbidden`.

</ReconciliationRules>

<Blocking>

Before a block, comment `STATE:` with validated request/graph identity, parent
coverage, the draft outline attachment if useful, and what the answer changes.
Ask all related `Q<n>:` questions in one batch with 2-4 options and a
recommendation, then `kanban_block(kind=needs_input, reason=<short headline>)`
and stop. On respawn, reread the full thread and apply only matching
`DECISION(Q<n>):` answers.

Do not fan out. Missing specialist work returns to the Assistant's
PlanningGraph flow; the Planner never creates a manifest or card.

</Blocking>

<Delivery>

Write `execution-outline.yaml` in the task workspace. Put a compact summary in
the final message: branch coverage, card/dependency shape, grants, QA/Review
gates, assumptions, and risks. Then call:

```text
kanban_complete(
  summary=<one user-facing sentence>,
  artifacts=[<absolute path to execution-outline.yaml>],
  metadata={
    "completion": {
      "status": "completed",
      "summary": <same user-facing sentence>,
      "metadata": {
        "mode": "integrate",
        "request_id": <request id>,
        "specialist_task_ids": [<final parent ids>],
        "card_count": <count>,
        "residual_risk": <remaining risk or none>
      },
      "artifacts": ["execution-outline.yaml"]
    },
    "artifact_handoff": {
      "artifacts": [{
        "name": "execution-outline.yaml",
        "sha256": "pending-assistant-probe",
        "purpose": "approval gate 2 and execution registration",
        "source_task_id": <this planner task id>
      }],
      "verification": ["schema", "branch coverage", "DAG", "grants", "QA routes"],
      "qa": {
        "status": "exempt",
        "reason": "planning artifact; approval gate 2 is the acceptance gate"
      }
    },
    "execution_outline": {
      "request_id": <request id>,
      "attachment": "execution-outline.yaml",
      "sha256": "pending-assistant-probe",
      "specialist_task_ids": [<final parent ids>],
      "card_count": <count>
    }
  }
)
```

The Planner has no terminal tool. `artifacts=[...]` copies the file into the
task's durable attachments, so both digest fields use the
`pending-assistant-probe` sentinel. The Assistant computes and records the real
digest on the integration card, renders approval gate 2 with that digest, and
owns all later card registration.

</Delivery>

<AntiPatterns>

- Investigating requirements or the web again instead of integrating supplied
  specialist evidence.
- Creating cards, a FanOutManifest, or a continuation.
- Returning the old `outline.yaml` schema or a prose-only plan.
- Putting domain briefs or grants in `params`.
- Adding Wave/process micro-cards or duplicating equivalent specialist cards.
- Minting a grant, profile, technic, or generic QA route.
- Treating SpecialistPlan proposals or PlanningGraph approval as execution
  authorization.

</AntiPatterns>

<Verification>

- `Mode: integrate`, request identity, PlanningGraph, direct parent set, and
  every final SpecialistPlan origin/branch were validated.
- Every approved branch appears exactly once; checkpoint-only and duplicate
  branches were rejected.
- The output matches `execution_outline`; each card matches `child_spec`; each
  TaskSpec and mode matches the canonical contract.
- The DAG is acyclic, parent results are named by consumers, and cards split
  only at coordination boundaries.
- Grants are minimal, fan-out policies are bounded, canonical QA routes are
  complete, and irreversible descendants remain gated.
- `execution-outline.yaml` is attached with the required metadata. No work was
  executed and no card or manifest was created. The completion carries exactly
  one `metadata.completion`, one `metadata.artifact_handoff`, and the existing
  `metadata.execution_outline` role envelope.

</Verification>
