# Specialist plan - PlanningGraph creator branch

Load this reference only for a top-level `Mode: plan` task. This is the
PlanningGraph specialist branch from workflow-contract.yaml v1. It is not the
execute Direction route in `references/plan.md`.

## Required input

The task body must contain these self-contained fields:

```text
Planning graph: <approved PlanningGraph key and relevant graph facts>
Request run: <request-run id>
Planning branch: <approved branch key>
Mode: plan
Fan-out policy: <approved allowed assignees, max children, purpose, cost cap;
  or forbidden>
Goal: <settled creator planning question>
Inputs: <RequirementSpec facts, MediaBrief facts, references, and parent results>
Input attachments: []
Done criteria: <SpecialistPlan checks>
Output: summary plus metadata.specialist_plan
Constraints: plan only; zero generation spend and no card registration
```

Also require the complete MediaBrief or enough RequirementSpec facts to derive
one. Workers do not see chat, so do not refer to missing conversation context.
The branch key, request run, and graph must remain unchanged across a plan
continuation.

## Plan-only contract

This branch is read-only. Inspect the brief, the capability catalog, existing
references, and supplied attachments, then return a specialist recommendation.
Do not generate an image, video, audio, music, voice, or TTS asset. Do not run
ffmpeg or another production command. Do not make production files, consume
Budget, or publish. Do not register live cards. A required `fan-out.yaml` is
the only coordination exception; it is an attached manifest, not a production
artifact.

The final plan must be exactly one object at `metadata.specialist_plan`. A
checkpoint that needs Search or Research attaches the manifest and blocks with
`FAN_OUT_READY:` instead; it returns no SpecialistPlan. The same creator
branch continues with `Mode: plan`, and only the final continuation returns
the SpecialistPlan. A final SpecialistPlan never accompanies a fan-out
handoff.

## Planning work

1. Validate the PlanningGraph branch and TaskSpec. Confirm the approved
   assignee, pipeline pin, branch parents, and Fan-out policy.
2. Read the MediaBrief: purpose, audience, destination, dimensions, aspect
   ratio, duration, format, quantity, variants, style inputs, references,
   deadline, and constraints. Mark missing facts as assumptions.
3. Select the canonical Creator technic and production method without running
   it. Use the profile catalog and `references/capabilities.md`. Report the
   capability identity and any prerequisite or uncertainty.
4. Estimate the minimum execute Budget from the brief. Include only the
   renders, variants, corrective allowance, local runtime, and quantity that
   the settled method needs. Do not spend this estimate under `Mode: plan`.
5. Map the required QA route from the canonical technic. Include every
   conditional route that the final artifact can trigger.
6. Decide whether additional Search or Research is necessary. If it is,
   request only the approved fan-out policy and follow the manifest contract in
   the pipeline skill. Do not create a card or broaden the policy.
   Searcher children use `mode: retrieve`; Researcher children use
   `mode: analyze` (`retrieve|analyze` in generic examples).
7. Propose the smallest execution DAG. Put the immutable QA requirement and
   canonical routes on each ship-ready Creator TaskSpec; do not propose a QA
   card before the candidate and evidence digests exist.

## Proposed card shape

Each `proposed_cards` item is exactly a workflow-contract `child_spec`: no
extra keys at the item level. The required item fields are `key`, `title`,
`assignee`, `skills`, `parents`, `params`, and `task_spec`. The TaskSpec uses
only its contract fields. A Creator execute proposal must carry the following
facts inside its TaskSpec:

```yaml
key: <stable card key>
title: <imperative title>
assignee: creator
skills: [creator-pipeline, <canonical creator technic>]
parents: [<local parent keys>]
params: {workspace_kind: scratch, max_runtime_seconds: 900}
task_spec:
  mode: execute
  goal: <asset outcome and audience>
  inputs: |
    MediaBrief: <complete brief>
    Technique: <canonical creator technic>
    Intent: new|revise|salvage
    QA route: <canonical QA technic and conditions>
  input_attachments: []
  done_criteria: <objective asset and verification checks>
  output: <artifact and report shape>
  constraints: |
    MediaBrief constraints and production method.
    Fan-out policy: <approved policy or forbidden>
  qa: required
  producer_qa_requirement:
    candidate_key: <this card key>
    evidence_keys: [<final Researcher evidence card keys>]
    capability: <canonical Creator capability>
    routes: [<all required QA technics>]
    criteria: [<approved acceptance criteria>]
    done_criteria: <copied objective Done criteria>
    output_inventory: [<expected durable attachment names and purposes>]
  grant: "Budget: <minimum settled generation-spend grant>"
  fan_out_policy: <approved policy or forbidden>
```

The proposed Budget is the minimum required by this MediaBrief, not the
profile default. Preserve the exact Intent and QA route in the body that
Assistant/Planner later integrates. QA is not a `child_spec` at planning time.
The Creator TaskSpec carries the closed `producer_qa_requirement` object as the
immutable QA requirement, and the Assistant
materializes the QA card only after candidate/evidence completion admission and
digest resolution.

## Final envelope

Return exactly this shape at `metadata.specialist_plan` after no pending
fan-out checkpoint remains. The plan is parallel to the required completion
envelope:

```yaml
origin_task_id: <current branch task id>
branch_key: <PlanningGraph branch key>
summary: <domain plan, method, minimum Budget, QA route, and recommendation>
proposed_cards:
  - key: <stable key>
    title: <imperative title>
    assignee: creator
    skills: [<mandatory pipeline pin>, <canonical technic when applicable>]
    parents: [<local parent keys>]
    params: {workspace_kind: scratch, max_runtime_seconds: 900}
    task_spec: <schema-valid TaskSpec>
assumptions: [<explicit assumptions>]
evidence: [<parent task ids, URLs, or existing attachment names>]
```

The final completion uses this actual call template and exactly one completion
envelope:

```text
FINAL_SUMMARY = <one string>
ROLE_METADATA = {
  "assets": [],
  "verification": [<PlanningGraph, capability, Budget, and QA checks>],
  "spend": "none",
  "anchor": "none",
  "retry_notes": [],
  "residual_risk": [<planning gaps>]
}
SPECIALIST_PLAN = {
  "origin_task_id": <current branch task id>,
  "branch_key": <PlanningGraph branch key>,
  "summary": <domain plan, method, minimum Budget, QA route, and recommendation>,
  "proposed_cards": [<schema-valid child_spec objects>],
  "assumptions": [<explicit assumptions>],
  "evidence": [<parent task ids, URLs, or existing attachment names>]
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

Do not add a second plan envelope, a live-card id, an execution result, or a
fan-out handoff to this final object. The proposal authorizes nothing and
does not consume any grant.

The final `FINAL_SUMMARY` is byte-for-byte identical in the
`kanban_complete` summary and `metadata.completion.summary`, and
`metadata.specialist_plan` is a sibling of `completion`, not nested inside it.

## Verification

- All required inputs are present and identify the same request run and branch.
- No media generation, production command, file production, Budget spend, or
  publication occurred.
- The Creator proposal uses a canonical technic, complete MediaBrief,
  minimum Budget, Intent, QA route, and approved Fan-out policy.
- Every proposal has the exact `child_spec` item shape and a schema-valid
  TaskSpec; no QA card is proposed before digest resolution.
- The final completion contains exactly one `metadata.specialist_plan`, or a
  `FAN_OUT_READY:` checkpoint with an attached manifest, never both.
