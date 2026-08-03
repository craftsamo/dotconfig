# Plan mode — PlanningGraph SpecialistPlan

Loaded only for a card routed to top-level `Mode: plan`. This is the engineer
specialist branch described by `workflow-contract.yaml` v1 and the
orchestration planned-flow reference. The deliverable is a grounded
`SpecialistPlan`, not an implementation or an execution card.

## Required input

The card body must contain all of these fields. Workers do not see the
orchestrator's chat, so do not infer missing context from memory:

```text
Planning graph: <PlanningGraph key or complete graph context>
Request run: <request-run id>
Planning branch: <branch key>
Mode: plan
Fan-out policy: <approved allowed_assignees, max_children, purpose, and
  optional cost_cap; or forbidden>
Goal: <settled planning question>
Inputs: <RequirementSpec facts, repo/env paths, references, and parent results>
Input attachments: []
Done criteria: <SpecialistPlan and proposed-card checks>
Output: summary plus metadata.specialist_plan
Constraints: plan only; no implementation, generation, publishing, or card
  registration
```

The TaskSpec fields `goal`, `inputs`, `done_criteria`, `output`, and
`constraints` are required. `mode`, `review`, `qa`, `grant`, `plan_id`,
`outline_key`, and `fan_out_policy` may be supplied when relevant. A plan card
must also carry the PlanningGraph fields above; a missing or contradictory
field is a routing/input defect to report or block, not a reason to execute.

## Purpose and read-only floor

Inspect the repository and environment needed to answer the branch's planning
question. Ground the recommendation in actual structure, conventions,
interfaces, build/test information, dependency state, and relevant parent
results. Use read-only terminal, file, Git, or environment inspection only.

Plan mode MUST NOT:

- edit, generate, scaffold, install, or delete repository files;
- commit, change branches, push, open or modify a PR, or perform any GitHub
  write;
- add or upgrade dependencies;
- publish, spend generation budget, or create production artifacts;
- register cards or treat a proposed card as authorized execution.

The Authority field does not widen this floor. A SpecialistPlan proposes work;
it authorizes nothing.

## Build the SpecialistPlan

1. Confirm the PlanningGraph, Request run, Planning branch, and approved
   Fan-out policy. The branch key is stable for this run.
2. Inspect only the repo and environment relevant to the branch. Record
   assumptions explicitly and keep evidence to parent task ids, URLs, and
   attachment names.
3. Shape execution candidates at one intent or coordination boundary each.
   Do not split a straight line of one specialist's reasoning into process
   steps. Use the minimum authority and the smallest necessary assignee,
   skills, parents, and parameters.
4. Validate every candidate against the exact `child_spec` shape below. The
   list is a proposal for later ExecutionOutline integration, not live card
   registration.

### Exact proposed card shape

Every item in `proposed_cards` has exactly the keys below with no legacy
wrapper:

| Assignee | TaskSpec mode |
| --- | --- |
| engineer, creator, writer, marketer | `execute` |
| searcher | `retrieve` |
| researcher | `analyze` |
| qa | `verify` |

```yaml
key: <stable candidate key>
title: <imperative title, <=80 chars>
assignee: <worker profile>
skills: [<mandatory pipeline pin>, <optional technics>]
parents: [<proposed card key or approved parent task id>, ...]
params:
  workspace_kind: <dir|worktree|scratch as required>
  max_runtime_seconds: <bounded value>
task_spec:
  mode: <execute|retrieve|analyze|verify, mapped from assignee>
  goal: <one implementation or coordination outcome>
  inputs: <self-contained paths, facts, links, and parent outputs>
  input_attachments: []
  done_criteria: <objective checks>
  output: <artifact/report shape>
  constraints: <scope, role grant, QA/review, and explicit prohibitions>
  fan_out_policy: <approved policy or forbidden>
```

Engineer proposals use one execute intent per coordination boundary. Other
assignees use their canonical mode and omit irrelevant Authority or QA fields.
`key`, `title`, `assignee`, `skills`, `parents`, `params`, and `task_spec` are
the required and complete child-spec fields. The nested TaskSpec must include
`goal`, `inputs`, `input_attachments`, `done_criteria`, `output`, and `constraints`; add only the
contract's optional fields when they are necessary. The mandatory pipeline pin
must match the assignee. Proposed grants never exceed the approved planning
ceiling and are not live grants.

## Additional Search or Research

If the approved Fan-out policy allows more Search or Research, the worker does
not register those cards. Prepare one `fan-out.yaml`, attach it, write the
checkpoint, and block. The manifest must have exactly this shape:

```yaml
origin_task_id: <current task id>
checkpoint_key: <stable unique checkpoint key>
children:
  - key: <stable child key>
    title: <imperative title, <=80 chars>
    assignee: <allowed searcher or researcher>
    skills: [<mandatory pipeline pin>, <optional technics>]
    parents: [<child key or existing task id>, ...]
    params: {workspace_kind: scratch, max_runtime_seconds: <bounded value>}
    task_spec:
      mode: retrieve|analyze
      goal: <one evidence-gathering question>
      inputs: <self-contained facts and attachment references>
      input_attachments: []
      done_criteria: <evidence requirements>
      output: <evidence report shape>
      constraints: <read-only, plan-only, no card registration>
      fan_out_policy: forbidden
continuation:
  title: <resume the specialist plan>
  assignee: engineer
  skills: [engineer-pipeline]
  parents: [<child key>, ...]
  params: {workspace_kind: scratch, max_runtime_seconds: <bounded value>}
  task_spec:
    mode: plan
    goal: <finish this same Planning branch's SpecialistPlan>
    inputs: <all required branch facts, child outputs, and attachments>
    input_attachments: []
    done_criteria: <final SpecialistPlan requirements>
    output: summary plus metadata.specialist_plan
    constraints: <same PlanningGraph and branch key; plan-only>
    fan_out_policy: <same approved policy>
attachments:
  - name: <durable attachment name>
    sha256: <digest>
    purpose: <how the child or continuation consumes it>
    source_task_id: <current task id>
```

The manifest is allowed only for the named assignees, purpose, bounded child
count, cost cap, and grant ceiling. Grants do not propagate. Attachment
digests must be checked, and every child/continuation must name the attachment
and purpose in its self-contained inputs. Never rely on a scratch path after
the origin completes.

After attaching the manifest, write `STATE:` with the checkpoint and current
findings, then block with `FAN_OUT_READY:`. Do not complete and do not return
`metadata.specialist_plan` in this handoff. The continuation is engineer-owned,
remains `Mode: plan`, carries the same PlanningGraph and Planning branch key,
and returns the final plan after all children finish. The handoff is
exclusive: `FAN_OUT_READY:` and a final SpecialistPlan cannot be returned
together.

## Final completion

Only the final plan run, after no pending fan-out checkpoint, may complete. The
completion metadata contains exactly one `metadata.completion` envelope and
exactly one `metadata.specialist_plan` object in parallel. Use this actual call
template, not an outer metadata object:

```text
FINAL_SUMMARY = <one string>
ROLE_METADATA = {
  "changed_files": [],
  "verification": [<read-only checks and outcomes>],
  "dependencies": [],
  "retry_notes": [],
  "residual_risk": [<remaining planning risk>]
}
SPECIALIST_PLAN = {
  "origin_task_id": <this final task or continuation id>,
  "branch_key": <same Planning branch key>,
  "summary": <grounded domain plan and recommendation>,
  "proposed_cards": [<child_spec objects>],
  "assumptions": [<optional explicit assumptions>],
  "evidence": [<optional parent task ids, URLs, or attachment names>]
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

`origin_task_id` is the final continuation itself when a continuation was
used. `branch_key` must match the Planning branch exactly. Evidence may
contain only parent ids, URLs, or attachment names; do not include raw logs,
secrets, or unreviewed local paths. Keep execution metadata inside the
completion envelope, not beside the specialist plan.

The final `FINAL_SUMMARY` is byte-for-byte identical in the
`kanban_complete` summary and `metadata.completion.summary`, and
`metadata.specialist_plan` is a sibling of `completion`, not nested inside it.

## Verification

- All required input fields are present and consistent with `Mode: plan`.
- Repository and environment inspection was read-only; no implementation,
  Git/GitHub write, dependency change, generation, publication, or card
  registration occurred.
- Proposed candidates use the exact child-spec keys, one intent or
  coordination boundary, self-contained TaskSpecs, mandatory pipeline pins,
  bounded parameters, and minimum authority.
- Fan-out, when present, matches the approved policy, has one digest-checked
  manifest, is attached before `STATE:` and `FAN_OUT_READY:`, and has a
  self-contained same-branch plan continuation.
- Final metadata is exactly `specialist_plan` with the required fields;
  origin and branch identity are correct, and evidence is schema-safe.

## Pitfalls

- Treating the old Execute `Plan —` opener as this top-level plan mode. That
  opener is the Execute/Shape Wave-outline branch; it is distinct from a
  PlanningGraph specialist plan.
- Returning an execution card as if it were already registered or authorized.
- Completing the origin at a fan-out checkpoint, or returning a SpecialistPlan
  alongside `FAN_OUT_READY:`.
- Widening fan-out, grants, assignees, or purpose beyond the approved policy;
  such a change requires the PlanningGraph approval flow again.
- Omitting attachment digests or assuming the continuation can read the
  origin's scratch workspace.
