# Planned execution reference

Load this reference when <RequirementAndShape> selects `planned`. Planning has
two distinct artifacts and two user approvals:

1. `PlanningGraph`: who will investigate and produce each specialist plan.
2. `ExecutionOutline`: the final executable DAG integrated from those plans.

No specialist plan card exists before PlanningGraph approval. No execution card
exists before ExecutionOutline approval.

## Entry conditions

Start only after the RequirementSpec has settled `goal`, `done_criteria`, and
`constraints`. Use planned execution when any of these apply:

- likely 3+ execution cards or 2+ specialist profiles;
- fan-out/fan-in or cross-domain coordination;
- architecture, migration, production method, or campaign shape needs grounded
  specialist judgment;
- Authority, Budget, Publish, Review, or QA responsibilities span cards;
- the user wants to inspect the structure before work runs;
- an irreversible or high-cost action depends on several intermediate results.

A narrow settled task belongs in `single`; an obvious 2-3 stage pipeline belongs
in `chain`. Planning is not a tax on clear work.

## Phase A: build the PlanningGraph

Draft a compact graph in chat from the RequirementSpec. Each branch is one
specialist plan, not an execution deliverable:

```yaml
request_id: <new request-run id; never reuse for a later intentional rerun>
goal: <same outcome as RequirementSpec>
assumptions: [<best-effort assumptions>]
estimated_cost: <dispatch/spend summary>
grants: [<grant posture to investigate; not live grants>]
branches:
  - key: <stable branch key>
    title: <plan the domain contribution>
    assignee: engineer|creator|writer|marketer
    skills: [<mandatory pipeline pin>, <optional technics>]
    parents: [<branch key>, ...]
    params: {workspace_kind: scratch, max_runtime_seconds: 900}
    fan_out_policy:
      allowed_assignees: [searcher, researcher]
      max_children: <bounded count, or 0 when forbidden>
      purpose: <evidence the specialist plan may request>
      cost_cap: <optional>
    task_spec:
      mode: plan
      goal: <domain planning question>
      inputs: <RequirementSpec facts, paths, references, parent results>
      input_attachments: []
      done_criteria: <SpecialistPlan requirements>
      output: <summary plus metadata.specialist_plan>
      constraints: <plan-only; no implementation/generation/publish/card creation>
```

Branch rules:

- Use Engineer, Creator, Writer, or Marketer in plan-only mode; do not create
  planning-only profiles. These profiles return SpecialistPlan.
- Searcher supplies retrieval coverage and Researcher supplies evidence
  synthesis. They are evidence children requested through an approved
  FanOutManifest, not direct PlanningGraph branches or SpecialistPlan producers.
- One branch per coordination boundary, not per process step. Do not split a
  straight line of one specialist's reasoning into micro-cards.
- Branch grants describe planning access only. Engineer planning is read-only;
  Creator planning has zero generation spend; Marketer planning is draft-only.
- Every branch TaskSpec carries the full facts it needs. Workers do not see chat.
- Generate one stable `request_run_id` for this user request. Compute the
  PlanningGraph digest from the normalized RequirementSpec and graph content.
  A later intentional rerun gets a new run id even when the request text is the
  same; retries within this run reuse the existing id and digest.

## Approval gate 1: PlanningGraph

Render the graph as a short branch/dependency summary plus estimated cost and
grant posture. Ask one `clarify`: approve / request changes / discard.

Approval sanctions only specialist planning. It does not authorize execution,
generation spend, repository writes, or publishing. On changes, revise the graph
and ask again. On discard, create nothing.

## Register specialist plans

After approval, validate every branch against `workflow-contract.yaml` and
<Workers>, then register only branches with no local parents. The approved
PlanningGraph itself is the immutable pending-registration manifest for its
dependent branches:

```text
idempotency_key = <request-run-id>:planning:<planning-graph-digest>:branch:<branch-key>
```

Prepend the mandatory `<profile>-pipeline` pin if absent. Require
`subscribed=true`; retry one false subscription with the same key, then stop if
it remains false. Run `kanban-task-spec-probe.sh <id>` for every returned id and
compare all immutable create parameters, including skills, workspace/project,
runtime, retries, goal-mode, and model/provider overrides. A returned `done`
branch is synchronously consumed from its metadata/artifacts; do not wait for a
past notification. Route blocked, failed, archived, or active existing cards
through recovery/status handling.
Before creating any root, write the complete approved graph to
`planning-graph.yaml`, compute its digest, and include both the digest and the
complete normalized YAML in every root body. The worker therefore receives the
approved graph atomically with card creation; the later attachment is a durable
anchor, not its first access to the graph.
Add these lines to every branch body:

```text
Planning graph: <planning-graph-key>
Planning graph digest: <sha256>
Planning graph YAML: |
  <complete normalized approved PlanningGraph>
Request run: <request-run-id>
Planning branch: <branch-key>
Mode: plan
Input attachments: []
Output: summary plus metadata.specialist_plan
Constraints: plan only; do not implement, generate, publish, or create cards.
Fan-out policy: <normalized approved allowed_assignees, max_children, purpose,
  and optional cost_cap; or forbidden>
```

Every branch TaskSpec carries `Input attachments: []` unless it consumes an
attachment_spec from another task. When it consumes an existing attachment,
render a single-line JSON `attachment_spec` array instead. The embedded
PlanningGraph is the worker input; its later anchor attachment is orchestration
state and is not declared as worker input or output. After all root branches exist, attach the already-written
`planning-graph.yaml` to the lexicographically first root as
the durable graph anchor, verify its digest, and comment:

```text
PROGRESS: planning_graph=<key> digest=<sha256> attachment=planning-graph.yaml live=<branch-key:task-id,...> pending=<branch-keys...>
```

After each root or later planning branch completes, run the canonical completion
probe. Register a dependent branch only when all local parents have passed;
include their validated ids and results in its self-contained TaskSpec. Record
`PROGRESS: planning valid=<branch-key:task-id,...> pending=<branch-keys...>` on
the graph anchor. A replacement or FanOut continuation preserves the Planning
graph key and digest, so the same anchor remains the restart source.

Ack live and pending branch keys separately and end the turn. Never poll.

## Collect SpecialistPlans

A **final** plan-mode completion after no pending `FAN_OUT_READY` handoff must
return exactly one object at `metadata.specialist_plan`:

```yaml
origin_task_id: <branch task id>
branch_key: <PlanningGraph branch key>
summary: <domain plan and recommendation>
proposed_cards:
  - <candidate execution card in child_spec shape>
assumptions: [<explicit assumptions>]
evidence: [<parent ids, URLs, attachment names>]
```

Validate origin, branch key, plan-only behavior, proposed assignees/skills,
grant ceilings, and evidence references. A SpecialistPlan proposes execution;
it authorizes nothing.

The two handoffs are exclusive: a fan-out checkpoint attaches `fan-out.yaml`,
blocks with `FAN_OUT_READY:`, and returns no SpecialistPlan; only its final
continuation returns the SpecialistPlan. Compare a manifest with the branch's approved
`fan_out_policy` before processing <FanOutManifest>. A profile, purpose, child
count, cost, or grant outside that slot changes the PlanningGraph and requires
approval gate 1 again. Its continuation remains plan-only and must return the
final SpecialistPlan for the same branch key. Record the latest final task id on
the graph anchor:

```text
PROGRESS: specialist_final branch=<key> task=<final-task-id>
```

Do not count the checkpoint as final. Once every branch has a validated final
SpecialistPlan, create the Planner integration card with those final task ids as
direct parents.

## Planner integration

The Planner does not rediscover requirements, run execution, or create cards.
Its body contains:

```text
Mode: integrate
Request run: <RequirementSpec request_id>
Goal: Integrate the approved specialist plans into one ExecutionOutline for
  the RequirementSpec.
Inputs: PlanningGraph key, complete RequirementSpec, approved PlanningGraph,
  final specialist task ids and attachment names.
Input attachments: []
Done criteria: schema-valid ExecutionOutline; every proposed action accounted
  for; dependencies acyclic; grants bounded; QA and Review routes explicit;
  no duplicated work; one worker session per coordination boundary.
Output: execution-outline.yaml plus metadata summary.
Constraints: plan only; do not execute or create cards.
```

Use idempotency key
`<request-run-id>:integration:<specialist-id-set-digest>:<revision-digest>` and
require `subscribed=true`. The initial `revision-digest` covers an empty feedback
set. A replacement includes the prior integration id and normalized user
feedback in that digest. When a create returns an existing id, verify its body,
parents, and status match before accepting it. The Planner's direct parents are
exactly the latest final SpecialistPlan task ids.

The resulting `ExecutionOutline` uses the `execution_outline` and `child_spec`
schemas from `workflow-contract.yaml`, including the `request_id`. Each card has
a stable `key`, TaskSpec,
assignee, mandatory pipeline/technic pins, local parent keys, parameters, and
the minimum necessary grant. Each TaskSpec sets `Fan-out policy: forbidden` or
an explicit bounded expansion slot. Ship-ready Creator/Writer cards specify
their QA route; irreversible descendants remain gated.

Run the completion probe and comment its computed attachment digest on the
integration card before approval:

```text
EXECUTION_OUTLINE_DIGEST: task=<integration-id> sha256=<computed digest>
```

Approval gate 2 displays and sanctions this digest. Include it as
`execution_outline_sha256` in the pending-registration manifest. Before every
root registration, after a session reset, and before any late descendant
registration, rerun the probe and require the same digest. A changed byte is a
new Planner revision and requires approval gate 2 again; the sentinel never
authorizes a newer digest.

## Approval gate 2: ExecutionOutline

Render the outline as a compact DAG. For each card show title, assignee,
dependencies, grant, Review/QA gate, and irreversible effect. Include Planner
notes and unresolved best-effort assumptions. Ask one `clarify`: approve /
request changes / discard.

Approval sanctions the exact topology, expansion slots, and grant lines in the
outline. It does not permit later widening. A changed outline requires another
approval. If feedback changes only integration, create a replacement Planner
card carrying the prior outline and feedback and use a fresh revision digest.
Re-run specialist branches only when their premises changed.

## Register execution

After approval:

1. Validate every assignee, mandatory pipeline pin, optional technic, TaskSpec,
   local parent key, parameter, grant, QA route, and DAG acyclicity.
2. Register only root cards initially, using key
   `<integration-task-id>:execution:<card-key>`. Keep every descendant as a
   normalized pending spec on the integration card. After each root or later
   stage completes, run the canonical completion probe; create a card only when
   all local parents have passed and map those validated parent keys to ids.
   Before the first root, write one pending-registration manifest matching the
   canonical schema and comment it on the integration card with
   `ORCHESTRATION_PENDING:`. Every live TaskSpec carries its Registration anchor
   and Pending manifest digest; replacements and FanOut continuations preserve
   them verbatim.
3. Add `Plan: <integration-task-id>` and `Outline key: <card-key>` to every live
   body. Require `subscribed=true` for ordinary cards.
4. Use <QualityGate> for protected Creator/Writer production, Researcher
   evidence, and QA. Irreversible descendants behind QA stay held until fresh
   digest-checked pass.
5. Comment the durable map on the integration card:

```text
PROGRESS: execution live=<card-key:task-id,...> pending=<card-keys,...>
```

6. Ack live and pending ids separately, then use <AfterCreate>, <Failures>, and
   <BlockedTriage> normally.

Partial registration is retried with the same deterministic keys. A meaningfully
changed card gets a replacement outline/card key; never edit a live grant or
reuse a key for different work.

## Continuity

Before approval 1, the draft RequirementSpec and PlanningGraph live in chat.
After branch registration, the graph key, branch map, SpecialistPlans,
immutable `planning-graph.yaml`, integration attachment, approvals, and
execution map live on Kanban cards and comments. On session reset, reconstruct
from the graph anchor and integration card rather than asking the user to repeat
settled decisions.
