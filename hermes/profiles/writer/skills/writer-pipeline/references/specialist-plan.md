# Writer SpecialistPlan reference

Load this reference for a writer card whose top-level body contains
`Mode: plan`. This is a PlanningGraph specialist branch. The deliverable is a
machine-readable `SpecialistPlan`, not a manuscript, public draft, or script.

## Branch contract

The task body is the complete context. It must identify:

```text
Planning graph: <graph key>
Request run: <request run id>
Planning branch: <branch key>
Mode: plan
Goal: <writing outcome>
Inputs: <requirements, paths, parent task ids, and source links>
Input attachments: []
Done criteria: <SpecialistPlan checks>
Output: summary plus metadata.specialist_plan
Constraints: plan only; no manuscript, public draft, script body, publish, or card creation
Fan-out policy: <approved assignees, max children, purpose, optional cost cap, or forbidden>
```

Do not infer execution approval from this task. The branch may plan a writer
card and candidate research dependencies, but the Assistant and the planning
flow decide whether to register them.

## Planning method

1. Parse the WritingBrief. Required fields are deliverable type, audience,
   purpose, and medium or destination. Record soft fields and label assumptions.
2. Select one writer type: `marketing-copy`, `technical-prose`,
   `documentation`, or `script`.
3. Set tone axes: register, temperature, distance, and assertiveness. For a
   script, set the intended register per speaker without writing dialogue.
4. Propose a structure. Use section or unit names, order, purpose, and
   acceptance criteria. Do not fill sections with finished prose.
5. List all known inputs and missing source needs. Distinguish supplied facts
   from facts that require Searcher retrieval or Researcher synthesis.
6. Select the QA route: `qa-prose` for marketing copy, technical prose, or
   documentation; `qa-script` for scripts. State the condition and the artifact
   name that the execute card must attach.
7. Propose execution cards in `child_spec` shape. The writer execution card
   must include a complete `WritingBrief` in `task_spec.inputs`,
   `mode: execute`, `qa: required`, and a bounded `fan_out_policy`.
8. Add Searcher and Researcher cards only when the source needs justify them.
   They are dependencies or candidates, not completed evidence in this plan.

## WritingBrief planning form

Use this compact form inside the writer execution card's `inputs` value:

```yaml
WritingBrief:
  deliverable_type: <marketing-copy|technical-prose|documentation|script>
  audience: <reader and, for scripts, producer>
  purpose: <reader outcome>
  medium: <destination>
  tone:
    register: <planned value>
    temperature: <planned value>
    distance: <planned value>
    assertiveness: <planned value>
  length_budget: <target or assumed range>
  language: <language>
  sources_inputs: [<paths, URLs, parent artifacts>]
  source_needs: [<retrieval or synthesis need, or none>]
  constraints: [<must include, must avoid, format, deadline>]
  writer_type: <type>
  qa_route: <qa-prose|qa-script>
  output_artifact: <exact execute artifact name>
```

For a script, `sources_inputs` also names unit fields and producer conventions.
For documentation, state which sections are explanatory and which are
reference-like. For marketing copy, state the destination and reader action.

## ChildSpec shape

Every item under `metadata.specialist_plan.proposed_cards` is exactly one
workflow-contract `child_spec` object:

```yaml
key: <stable card key>
title: <imperative title>
assignee: writer|searcher|researcher
skills: [<mandatory profile pipeline>, ...]
parents: [<local card keys or existing task ids>]
params: {workspace_kind: scratch, max_runtime_seconds: 900}
task_spec:
  goal: <card goal>
  inputs: <self-contained inputs; include WritingBrief for writer>
  input_attachments: []
  done_criteria: <objective checks>
  output: <summary and exact artifact shape>
  constraints: <scope, no publishing, and no card registration>
  mode: execute|retrieve|analyze
  qa: <required for writer; omit for searcher/researcher>
  fan_out_policy:
    allowed_assignees: [searcher, researcher]
    max_children: <bounded count>
    purpose: <approved research purpose>
    cost_cap: <optional cap>
```

The required `task_spec` fields are `goal`, `inputs`, `input_attachments`,
`done_criteria`, `output`, and `constraints`. Optional fields must come only from the workflow
contract: `mode`, `review`, `qa`, `grant`, `plan_id`, `outline_key`, and
`fan_out_policy`. Do not add unlisted child or production fields anywhere.

The writer card uses `mode: execute`; Searcher and Researcher cards use
`mode: retrieve` and `mode: analyze` respectively and omit `qa`. The writer
card's `constraints` must say that it is draft-only and cannot
publish. Its `output` must name the exact artifact when `qa: required`. Its
`fan_out_policy` is `forbidden` when no further research is permitted, or the
approved bounded policy when research may still be needed.

## Output envelope

After all approved research checkpoints have resolved, use this actual
`kanban_complete` call template. It carries one completion envelope and one
parallel specialist plan with no competing handoff:

```text
FINAL_SUMMARY = <one string>
ROLE_METADATA = {
  "deliverable_type": "plan",
  "verification": [<PlanningGraph and branch checks>],
  "sources": [<inspected inputs>],
  "retry_notes": [],
  "residual_risk": [<open source or scope gaps>]
}
SPECIALIST_PLAN = {
  "origin_task_id": <branch task id>,
  "branch_key": <PlanningGraph branch key>,
  "summary": <recommended writing execution shape>,
  "proposed_cards": [<schema-valid child_spec objects>],
  "assumptions": [<optional assumptions>],
  "evidence": [<optional parent ids, URLs, or attachment names>]
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

The example is an outline, not content to copy into a public draft. Add
Searcher or Researcher `child_spec` entries only when their source need is
real, and make the writer parents refer to those entries or their existing
task ids. Keep proposed cards acyclic and bounded.

The outer `specialist_plan` has exactly `origin_task_id`, `branch_key`,
`summary`, and `proposed_cards`, plus optional `assumptions` and `evidence`.
Do not put plan data in forbidden child or production metadata fields.

The final `FINAL_SUMMARY` is byte-for-byte identical in the
`kanban_complete` summary and `metadata.completion.summary`, and
`metadata.specialist_plan` is a sibling of `completion`, not nested inside it.

## Research fan-out checkpoint

When the branch discovers a permitted source need that was not completed
inline, do not return the SpecialistPlan yet. Attach one `fan-out.yaml` with
the manifest contract, including attachment digests. Then write a `STATE:`
comment and block with `FAN_OUT_READY:`.

The manifest must use these exact top-level keys:

```yaml
origin_task_id: <current task id>
checkpoint_key: <stable key>
children: [<child_spec-shaped research children>]
continuation:
  title: <continue writer planning>
  assignee: writer
  skills: [writer-pipeline]
  parents: [<child keys>]
  params: {workspace_kind: scratch, max_runtime_seconds: 900}
  task_spec:
    mode: plan
    goal: <complete the same specialist plan>
    inputs: <complete WritingBrief, branch identity, child results, attachments and purposes>
    input_attachments: []
    done_criteria: <final SpecialistPlan checks>
    output: summary plus metadata.specialist_plan
    constraints: plan only; no manuscript, public draft, script body, publish, or card registration
    fan_out_policy: <same approved policy>
attachments:
  - name: <durable filename>
    sha256: <sha256 digest>
    purpose: <how continuation consumes it>
    source_task_id: <current task id>
```

The continuation is self-contained and remains on the same PlanningGraph
branch. Its `Mode: plan` is mandatory. The checkpoint has no
`metadata.specialist_plan`; only the resumed final continuation may return it.
The Assistant owns registration and the event-bound
`DECISION(FAN_OUT_READY):` plus guarded resolver resume.

For an execute card, use the same manifest and attachment rules, but the
continuation uses the same execute WritingBrief and `mode: execute`; it returns
the execute deliverable rather than a SpecialistPlan.
