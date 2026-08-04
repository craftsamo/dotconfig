# Specialist plan reference

Load this reference only for a top-level `Mode: plan` card. The marketer is
one PlanningGraph specialist branch. It plans the marketing contribution; it
does not execute the plan.

## Branch contract

The card body must identify all of these values:

```text
Planning graph: <planning-graph-key>
Request run: <request-run-id>
Planning branch: <branch-key>
Mode: plan
Goal: <settled marketing planning question>
Inputs: <RequirementSpec, approved PlanningGraph, parent results, and supplied facts>
Input attachments: []
Done criteria: <SpecialistPlan and proposed-card checks>
Output: summary plus metadata.specialist_plan
Constraints: plan only; do not implement, produce drafts or assets, publish, post, or create cards.
Fan-out policy: <approved allowed_assignees, max_children, purpose, and cost_cap, or forbidden>
```

The six TaskSpec fields `Goal`, `Inputs`, `Input attachments`, `Done criteria`,
`Output`, and `Constraints` are required. `Request run` is stable for this run. `Planning branch` remains unchanged on
any continuation. The branch must not widen its approved Fan-out policy,
grant posture, or scope. A change requires PlanningGraph approval again.

## Procedure

1. Read the RequirementSpec, approved PlanningGraph, branch TaskSpec, parent
   results, and the complete card thread.
2. Build the marketing plan around channel strategy and campaign strategy.
   State audience, positioning, channel fit, cadence, message angles, and
   campaign dependencies without writing post body text or producing a
   campaign deliverable.
3. Specify required inputs for each downstream boundary:
   - Writer: WritingBrief, audience, purpose, medium, tone, length, allowed
     facts, terminology, and output format.
   - Creator: MediaBrief, exact asset type, channel dimensions, source assets,
     accessibility requirements, filenames, and expected attachments.
   - Searcher: narrow retrieval questions, source coverage, recency, and
     required citation fields.
   - Researcher: synthesis question, decision criteria, evidence standard,
     counterevidence, and uncertainty fields.
4. State the Publish grant posture as a proposal only. The minimum is P0
   (draft-only and approval required). P1 is only an explicit bounded option
   with account, post count, topic scope, and approval of the execution
   outline. Planning approval is not a Publish grant.
5. Define QA and release gates. Writer and Creator production must name the
   required QA route, artifact digest checks, QA pass set, release dependency,
   and the final marketer gate. No release or public action is authorized by
   this branch.
6. Propose only execution candidates in exact `child_spec` shape. A Marketer
   candidate has `mode: execute`, a complete MarketingBrief, the minimum P0/P1
   proposal, QA/release dependencies, and an explicit approved Fan-out policy.
   Other candidates carry their own role brief and canonical mode.
7. If approved research expansion is needed, use the manifest handoff below.
   Do not return `metadata.specialist_plan` at that checkpoint.
8. On the same marketer continuation, after all approved research results are
   consumed, return the final SpecialistPlan exactly once.

The branch TaskSpec is mandatory and must include `goal`, `inputs`,
`input_attachments`, `done_criteria`, `output`, and `constraints`. Its optional `mode`, `qa`,
`grant`, and `fan_out_policy` fields must remain within the approved graph.

## Final SpecialistPlan

The final completion contains exactly one completion envelope and one parallel
object at `metadata.specialist_plan`. Use this actual call template:

```text
FINAL_SUMMARY = <one string>
ROLE_METADATA = {
  "mode": "plan",
  "drafts": [],
  "posts": [],
  "verification": [<PlanningGraph, branch, and proposal checks>],
  "publish_actions": [],
  "retry_notes": [],
  "residual_risk": [<open planning gaps>]
}
SPECIALIST_PLAN = {
  "origin_task_id": <this branch task id>,
  "branch_key": <PlanningGraph branch key>,
  "summary": <marketing strategy and execution recommendation>,
  "proposed_cards": [],
  "assumptions": [],
  "evidence": []
}
kanban_complete(
  summary=FINAL_SUMMARY,
  metadata={
    "completion": {
      "status": "completed",
      "summary": FINAL_SUMMARY,
      "metadata": ROLE_METADATA
    },
    "specialist_plan": SPECIALIST_PLAN
  }
)
```

`"specialist_plan": SPECIALIST_PLAN` is the tool metadata argument's direct
sibling after the completion closing brace. Do not pass an outer `metadata:` wrapper.
Never put `SPECIALIST_PLAN` inside the completion object.

Do not add fields to `metadata.specialist_plan`. `origin_task_id` is the final
task id that produced the plan. `evidence` contains only parent task ids,
URLs, or attached filenames that were actually inspected.

Each item in `proposed_cards` is an exact `child_spec` object. The object has
only these fields:

| Assignee | TaskSpec mode |
| --- | --- |
| marketer, writer, creator | `execute` |
| searcher | `retrieve` |
| researcher | `analyze` |

```yaml
key: <stable execution key>
title: <execution title>
assignee: marketer|writer|creator|searcher|researcher
skills: [<mandatory pipeline pin>, <optional technic pins>]
parents: [<local parent keys>]
params:
  workspace_kind: scratch
  max_runtime_seconds: <bounded value>
task_spec:
  mode: <execute|retrieve|analyze, mapped from assignee>
  goal: <card goal>
  inputs: <self-contained role brief, facts, attachments, and parent outputs>
  input_attachments: []
  done_criteria: <acceptance and QA/release conditions>
  output: <named output and metadata>
  constraints: <grant, channel, and safety limits>
  qa: <required on ship-ready Writer/Creator; omit otherwise>
  grant: <minimum role grant when applicable; omit otherwise>
  fan_out_policy:
    allowed_assignees: [<approved profiles>]
    max_children: <bounded count>
    purpose: <approved purpose>
```

For a Marketer card, `inputs` contains the complete MarketingBrief and explicit
QA/release dependencies, and `grant` is P0 unless a bounded P1 proposal was
sanctioned. Writer and Creator cards carry their WritingBrief or MediaBrief,
`qa: required` and the closed `producer_qa_requirement` object containing its
candidate/evidence keys, capability, routes, criteria, Done criteria, and output
inventory. Do not propose a
QA card before candidate/evidence completion admission and digest resolution.
Searcher and Researcher cards carry only their evidence question and omit
production/release grants.

The seven outer fields above are the complete `child_spec` shape. Do not add
any card collection outside `proposed_cards`. Proposed cards authorize nothing
and do not register themselves.

## Research fan-out handoff

Additional research is allowed only inside the approved branch Fan-out policy.
The marketer prepares and attaches `fan-out.yaml` with the contract fields
below. The Assistant owns registration and creates both children and the
continuation; the worker creates neither.

```yaml
origin_task_id: <current branch task id>
checkpoint_key: <stable checkpoint key>
children:
  - key: <research child key>
    title: <retrieval or synthesis question>
    assignee: searcher|researcher
    skills: [searcher-pipeline|researcher-pipeline]
    parents: []
    params:
      workspace_kind: scratch
      max_runtime_seconds: 600
    task_spec:
      mode: retrieve|analyze
      goal: <approved research question>
      inputs: <complete question, graph/run/branch identity, facts, and source constraints>
      input_attachments: []
      done_criteria: <evidence needed by the specialist plan>
      output: <research result and evidence>
      constraints: plan-only research; no production or public action
      fan_out_policy:
        allowed_assignees: []
        max_children: 0
        purpose: no nested expansion
continuation:
  title: <same marketer planning branch continuation>
  assignee: marketer
  skills: [marketer-pipeline]
  parents: [<research child keys>]
  params:
    workspace_kind: scratch
    max_runtime_seconds: 900
  task_spec:
    mode: plan
    goal: complete the same marketing specialist plan with research results
    inputs: <original TaskSpec plus child results>
    input_attachments: []
    done_criteria: final metadata.specialist_plan for the same branch
    output: summary plus metadata.specialist_plan
    constraints: plan-only; no draft production, posting, publishing, or card creation
attachments: []
```

The outer manifest must contain exactly `origin_task_id`, `checkpoint_key`,
`children`, `continuation`, and `attachments`. Before blocking, attach the
file and write:

```text
STATE: research fan-out manifest attached; branch=<branch-key>; checkpoint=<checkpoint-key>; no SpecialistPlan returned
FAN_OUT_READY: fan-out.yaml=<attachment-name>; policy=<approved-policy>; continuation=marketer/plan/<branch-key>
```

Block after those markers. The handoff is exclusive with
`metadata.specialist_plan`: a checkpoint returns the manifest only, while the
same marketer, `Mode: plan`, and branch continuation returns the final plan.

The final `FINAL_SUMMARY` is byte-for-byte identical in the
`kanban_complete` summary and `metadata.completion.summary`, and
`metadata.specialist_plan` is a sibling of `completion`, not nested inside it.

## Verification

- Planning graph, Request run, Planning branch, Mode plan, and Fan-out policy
  are present and unchanged.
- No post body, campaign deliverable, draft production, publication, or other
  public action was performed.
- Channel and campaign strategy, required Writer/Creator/Searcher/Researcher
  inputs, Publish posture, QA gates, release gates, and execution candidates
  are explicit.
- The final SpecialistPlan has exactly the six listed fields, and every card
  has exactly the seven outer `child_spec` fields.
- Research fan-out stayed within policy, attached `fan-out.yaml`, wrote
  `STATE:` and `FAN_OUT_READY:`, and returned no SpecialistPlan at checkpoint.
