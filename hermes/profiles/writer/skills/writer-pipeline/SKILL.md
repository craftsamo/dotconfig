---
name: writer-pipeline
description: >-
  Writer's task front door. Routes the top-level Mode plan or execute. Plan is
  a PlanningGraph specialist branch that returns a SpecialistPlan only.
  Execute retains the assess and write internal routes for prose and scripts.
  The writer never publishes and never registers cards.
version: 4.1.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [writing, copywriting, articles, documentation, scripts, tone, japanese, orchestration]
    category: writing
---

<Goal>

Convert a writing request into either a planning handoff or a finished draft.
The top-level Mode is the lifecycle boundary:

- `plan` is a PlanningGraph specialist branch. It proposes the WritingBrief,
  writer type, tone, structure, inputs, source needs, QA route, and execution
  cards as one SpecialistPlan. It never writes a completed manuscript, public
  draft, or script body.
- `execute` retains the existing internal `assess` and `write` routes. Assess
  returns judgment only. Write produces the requested prose or script, subject
  to QA and review gates.

The writer is draft-only. It does not publish, post, or register cards.

</Goal>

<LifecycleContract>

Follow the canonical lifecycle from `workflow-contract.yaml`:
`admit -> route -> act_or_plan -> verify -> handoff -> terminal`, with terminal
action `complete` or `block`.
Every completed card returns exactly one `metadata.completion` object with
`status`, `summary`, and `metadata`. Put the Writer role payload in
`metadata.completion.metadata`, including `deliverable_type`,
`verification`, `review`, `sources`, `retry_notes`, and `residual_risk` as
applicable.

An execute completion with a completed draft attached returns exactly one
`metadata.artifact_handoff` with `artifacts`, `verification`, and `qa`.
`qa` is `required`, names the canonical `qa-prose` or `qa-script` route, and
records the canonical writer capability (`writer:<writer_type>`). Assess and
completions without an attached final draft use the completion envelope only.
A final plan completion returns the completion envelope and one parallel
`metadata.specialist_plan`. A `FAN_OUT_READY:` wait is block-only and returns
neither completion nor SpecialistPlan. After the Assistant records a fan-out
decision, the obsolete origin completes as `superseded` without a writing
result; card registration belongs to the Assistant.

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
independently compose the second summary. `metadata.specialist_plan` handoff
is a sibling of `completion` directly under the `kanban_complete` metadata
argument, never inside `completion`. Applicable `specialist_plan`,
`artifact_handoff`, `qa`, and `execution_outline` handoffs are direct siblings
of `completion`; profiles without one use only this generic sibling rule.
`done` is a Kanban task state, as are `running` and `blocked`; never put these
values in `metadata.completion.status`. Normal completion status is always the
string `completed`.
</CompletionContract>

<Scope>
<UseWhen>

- Any writing task assigned to the writer through Kanban or delegation.
- A planned specialist branch that needs writing-specific execution design.

</UseWhen>
<DoNotUseWhen>

- Verified research conclusions, production code, media assets, or publishing.

</DoNotUseWhen>
</Scope>

<ModeRouting>

Read the top-level `Mode:` before doing domain work. The value must be
`plan` or `execute`. A legacy card without `Mode:` is treated as `execute` for
compatibility and that compatibility assumption is recorded in the report.

| Top-level mode | Route | First reference |
| --- | --- | --- |
| `plan` | PlanningGraph specialist branch | `references/specialist-plan.md` |
| `execute` | Internal deliverable route | `references/assess.md` or `references/prose.md` or `references/script.md` |

In `execute`, retain the existing internal routing:

| Execute deliverable | Internal route | Load |
| --- | --- | --- |
| Judgment only about structure, tone, effort, or an existing text | `assess` | `references/assess.md` |
| New prose or a reader-facing text deliverable | `write` | `references/prose.md` |
| New producer-facing script, storyboard, or screenplay | `write` | `references/script.md` |

Load the selected reference with `skill_view` before work. A respawn is a
resume overlay, not a new mode: reread the thread and settled decisions first.

</ModeRouting>

<WritingBrief>

Parse the task body into a complete brief. In `plan`, this brief is planning
information only and is copied into the proposed writer execution card.

| Field | Required | Notes |
| --- | --- | --- |
| Deliverable type | yes | marketing copy, article, documentation, or script |
| Audience | yes | end reader; for scripts also name the producer |
| Purpose | yes | what the reader should understand or do |
| Medium / destination | yes | blog, README, landing page, release note, video script, and so on |
| Tone | soft | register, temperature, distance, assertiveness |
| Length / budget | soft | character range, word count, unit count, or duration |
| Language | soft | default Japanese; apply language-specific norms only when relevant |
| Sources / inputs | soft | files, URLs, product facts, and reference texts |
| Constraints | soft | required terms, exclusions, fields, deadlines, and format rules |

If a required field changes the shape of the work, ask one consolidated
`Q<n>` block after a `STATE:` comment. For soft gaps, assume and label the
assumption. In `plan`, do not create sample openings as draft content; describe
the tone decision as a plan.

</WritingBrief>

<ToneCalibration>

Record the planned or settled values for register, temperature, distance, and
assertiveness. For scripts, plan a stable register per speaker. In `execute`,
use the existing one-round tone gate for a long deliverable when tone is
unsettled. In `plan`, recommend a tone and list the decision as planning data;
do not write an opening or any other completed text.

</ToneCalibration>

<TypeTable>

| Deliverable | Writer type | Execute reference | Norm layers | QA route |
| --- | --- | --- | --- | --- |
| Marketing copy | `marketing-copy` | `references/prose.md` | `japanese-writing`; `japanese-tech-prose` if long | `qa-prose` |
| Technical article or blog | `technical-prose` | `references/prose.md` | all three Japanese layers for long-form reading | `qa-prose` |
| Documentation | `documentation` | `references/prose.md` | `japanese-writing`; `japanese-tech-prose` for explanations; never rhythm for reference text | `qa-prose` |
| Comic script, storyboard, or screenplay | `script` | `references/script.md` | `japanese-writing`; `japanese-tech-prose` for explanatory narration; never rhythm | `qa-script` |

Plan output names exactly one writer type and its QA route. If source
verification is needed, propose Searcher and/or Researcher dependencies rather
than presenting unsupported facts.

</TypeTable>

<Procedure>

1. **Intake** - read the task, identify top-level `Mode`, and load the matching
   reference.
2. **Plan branch** - load `references/specialist-plan.md`, parse the
   WritingBrief, identify the writer type, recommend tone and structure, list
   inputs and source needs, choose the QA route, and propose only schema-valid
   execution cards. Stop short of all completed prose or script content.
3. **Execute branch** - parse the WritingBrief, read supplied inputs, route
   internally to `assess` or `write`, and follow the selected reference.
4. **Research need** - if additional research is needed, use the Assistant-owned
   fan-out checkpoint in <FanOut>. Do not complete before the checkpoint and do
   not return a SpecialistPlan from that checkpoint.
5. **Review and QA** - load `references/review.md` and run its four passes for
   execute writing or assessment. A body with `Review: required` blocks for
   human approval. A body with `QA: required` writes and attaches the exact
   named deliverable for the declared QA route.
6. **Complete** - the final `kanban_complete` in plan mode returns exactly one
   `metadata.specialist_plan` object as specified in
   `references/specialist-plan.md`. Execute completion reports the judgment or
   complete draft according to its route; it does not return plan metadata.

</Procedure>

<SpecialistPlanHandoff>

Only a final `Mode: plan` completion, after all research fan-out checkpoints
have resolved, may return `metadata.specialist_plan`. The object has exactly
these required fields:

```yaml
origin_task_id: <current planning branch task id>
branch_key: <PlanningGraph branch key>
summary: <writer plan and recommendation>
proposed_cards: [<child_spec objects>]
assumptions: [<optional assumptions>]
evidence: [<optional parent ids, URLs, or attachment names>]
```

`assumptions` and `evidence` may be omitted. Do not add forbidden child or
production metadata fields. A SpecialistPlan proposes execution; it grants
nothing and creates nothing.

</SpecialistPlanHandoff>

<CompletionHandoff>

Execute completions use this shape for the role payload:

```yaml
metadata:
  completion:
    status: completed
    summary: <one or two user-facing sentences>
    artifacts: [<exact durable output attachment names>]
    metadata:
      deliverable_type: <marketing-copy|technical-prose|documentation|script>
      verification: [<review and integrity outcomes>]
      review: <approved, not required, or blocked>
      sources: [<inspected source names or URLs>]
      retry_notes: [<revisions or retry history>]
      residual_risk: [<remaining gaps>]
  artifact_handoff:
    artifacts: [<completed draft name, sha256: pending-assistant-probe, purpose, source_task_id>]
    verification: [<attachment and content checks>]
    qa:
      status: required
      capability: writer:<writer_type>
      routes: [<qa-prose|qa-script>]
```

An attached completed execute draft must name the identical durable output
inventory in `completion.artifacts` and `artifact_handoff.artifacts`, use the
artifact handoff, and name the canonical writer capability. Writer has no
terminal digest tool, so it uses the exact `pending-assistant-probe` sentinel;
CompletionAdmission computes the durable attachment digest before QA creation.
Assess results and
execute results with no attached final draft set `completion.artifacts: []` and
use only the completion envelope. Plan completion keeps
the completion envelope and `metadata.specialist_plan` as parallel metadata;
the SpecialistPlan is not placed inside the role payload.

</CompletionHandoff>

<FanOut>

Fan-out is always Assistant-owned. The writer never registers a child or
continuation. This applies in both `plan` and `execute`.

Use fan-out only for approved additional research or another dependency that
the current card cannot complete. The task's `Fan-out policy` is the ceiling:
allowed assignees, maximum child count, purpose, optional cost cap, and grant
ceiling. Missing policy means forbidden. Research candidates are limited to
`searcher` and `researcher` unless the approved policy says otherwise. Writer
work remains draft-only; no publish, generation, or wider grant is proposed.

The writer must:

1. Attach exactly one `fan-out.yaml` manifest. Every attachment entry has
   exactly `name`, `sha256`, `purpose`, and `source_task_id`.
2. Put a durable `STATE:` comment before blocking. It names the checkpoint,
   the source need, the manifest attachment, every child input attachment and
   purpose, and the continuation requirements.
3. Block with a `FAN_OUT_READY:` marker. This checkpoint returns no
   `metadata.specialist_plan` and does not complete the origin card.
4. Use a self-contained continuation assigned to `writer`. For a plan branch,
   it is `Mode: plan` and carries the same `Planning graph`, `Request run`, and
   `Planning branch` values. For an execute branch, it is `Mode: execute` and
   carries the same plan or outline identity. It names every parent result and
   attachment because the continuation has no session memory.
5. Resume only after the Assistant records the event-bound
   `DECISION(FAN_OUT_READY):` pending-registration anchor and resolves the
   checkpoint through `kanban-resolve-block.sh apply`. After every parent
   passes completion admission, the plan continuation then
   returns the final SpecialistPlan for the same branch; it never returns both
   a fan-out handoff and a SpecialistPlan.

The manifest uses the workflow contract shape:

```yaml
origin_task_id: <origin task id>
checkpoint_key: <stable checkpoint key>
children:
  - key: <stable child key>
    title: <imperative title>
    assignee: searcher|researcher
    skills: [searcher-pipeline|researcher-pipeline]
    parents: []
    params: {workspace_kind: scratch, max_runtime_seconds: 600}
    task_spec:
      mode: retrieve|analyze
      goal: <research goal>
      inputs: <self-contained inputs and attachment names>
      input_attachments: []
      done_criteria: <evidence checks>
      output: <evidence artifact or summary>
      constraints: <scope and draft-only limits>
      fan_out_policy: forbidden
continuation:
  title: <resume title>
  assignee: writer
  skills: [writer-pipeline]
  parents: [<child key>, ...]
  params: {workspace_kind: scratch, max_runtime_seconds: 900}
  task_spec:
    mode: plan
    goal: <resume the same writer planning branch>
    inputs: <full brief, graph identity, child results, attachment names and purposes>
    input_attachments: []
    done_criteria: <final SpecialistPlan requirements>
    output: summary plus metadata.specialist_plan
    constraints: plan only; no manuscript, public draft, script, publish, or card creation
    fan_out_policy: <same approved policy>
attachments:
  - name: <attachment name>
    sha256: <sha256 digest>
    purpose: <consumer use>
    source_task_id: <origin task id>
```

The execute continuation uses the same manifest shape but `mode: execute` and
the self-contained execute WritingBrief. Its output is the execute deliverable,
not a SpecialistPlan.

</FanOut>

<ReviewGate>

`Review: required` means the exact proposed assessment or completed execute
deliverable is attached, a `REVIEW:` comment describes it, and the writer
blocks before completion. After an approval decision, continue without changing
the approved scope. A plan branch does not use a human review gate to approve
execution; the SpecialistPlan is still only a proposal for the orchestration
approval flow.

</ReviewGate>

<Resume>

After a block or respawn, reread the task body, all `STATE:` comments, every
`DECISION`, the latest `FAN_OUT_READY:` decision, and all attachment digests.
If the current task is the origin of a matching `DECISION(FAN_OUT_READY):`,
verify the checkpoint key, child ids, and continuation id, then complete this
obsolete origin immediately. Return no SpecialistPlan and no writing result;
the different continuation task id owns the sole final result. Do not resume
drafting or request another fan-out from the retired origin.
For plan mode, verify that the same branch key and request run are retained.
For execute mode, verify that no draft is completed twice and that the exact
QA attachment is still the declared artifact.

</Resume>

<Verification>

- Frontmatter and routing recognize only top-level `Mode: plan|execute`.
- Plan mode loaded `references/specialist-plan.md` and returned no completed
  manuscript, public draft, or script body.
- The plan records a complete WritingBrief, writer type, tone, structure,
  inputs, source needs, QA route, and bounded proposed cards.
- Every `proposed_cards` entry is a contract-shaped `child_spec` with
  `key`, `title`, `assignee`, `skills`, `parents`, `params`, and `task_spec`.
- Every writer execute card carries its WritingBrief, `mode: execute`, `qa`,
  and approved `fan_out_policy`; it remains draft-only.
- Final plan completion contains exactly one `metadata.specialist_plan` with
  the required fields and no forbidden metadata keys.
- A research checkpoint has one digest-checked `fan-out.yaml`, attachment
  `purpose` and `source_task_id`, a `STATE:` comment, and `FAN_OUT_READY:`;
  it has no SpecialistPlan handoff.
- The continuation is self-contained, Assistant-owned, same-profile, and
  same-branch; plan continuation uses `Mode: plan`.
- Execute mode preserves the assess/write internal routes, review gate, exact
  deliverable attachment, QA route, and draft-only grant.
- No worker procedure registers cards or uses a legacy fan-out handoff.
- Every completed card has exactly one completion envelope, with the role payload
  under `metadata.completion.metadata`; an attached final draft has exactly one
  artifact handoff with canonical writer capability and required QA.

</Verification>
