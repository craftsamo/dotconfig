# Assistant-owned fan-out manifest

This reference is shared by assess, shape, campaign, and specialist-plan
routes whenever another worker is needed. The marketer prepares a manifest and
the Assistant owns card registration, parent wiring, subscriptions, and
continuation creation. The worker never creates cards and never waits
in-process for a child.

Contract bindings: `card_registration_owner: assistant` and
`worker_card_creation: forbidden`.

## When to request fan-out

- Use a manifest for durable or cross-worker work: Writer prose, Creator media,
  Searcher retrieval, or Researcher synthesis.
- Any additional research beyond supplied inputs uses the manifest and its
  checkpoint handoff; do not expand research silently in-turn.
- In `Mode: plan`, only Searcher or Researcher children allowed by the
  approved branch Fan-out policy may be requested.
- In `Mode: execute`, use the same manifest contract. Writer and Creator
  production that feeds a final campaign candidate is protected production and
  must include its QA and release dependencies.

## Manifest contract

Attach one `fan-out.yaml` containing exactly these top-level fields:

```yaml
origin_task_id: <current task id>
checkpoint_key: <stable checkpoint key>
children: [<child_spec objects>]
continuation: <continuation_spec object>
attachments: [<attachment_spec objects>]
```

Each attachment object, when present, has exactly `name`, `sha256`, `purpose`,
and `source_task_id`.

The manifest is valid only when every child is within the approved Fan-out
policy. Grants never propagate to children. A child body is self-contained
and includes its own complete TaskSpec, facts, inputs, constraints, output,
and acceptance criteria.

The continuation is always the same profile and route as the originating
work. For a marketer plan it must have:

```yaml
continuation:
  title: <resume the same marketer branch>
  assignee: marketer
  skills: [marketer-pipeline]
  parents: [<all evidence or QA child keys>]
  params:
    workspace_kind: scratch
    max_runtime_seconds: <bounded value>
  task_spec:
    mode: plan
    goal: <resume the same marketer branch>
    inputs: <same PlanningGraph, Request run, Planning branch, brief, parents, and attachments>
    input_attachments: []
    done_criteria: <final SpecialistPlan requirements>
    output: summary plus metadata.specialist_plan
    constraints: same branch; no draft production, posting, publishing, or card creation
    fan_out_policy: <same approved bounded policy>
```

For execute work, it has `assignee: marketer`,
`skills: [marketer-pipeline]`, `task_spec.mode: execute`, API-only `params`, and the same campaign
brief, acceptance bar, grant ceiling, and release dependencies.

## Protected Writer and Creator production

The manifest is the complete Assistant-owned production contract. For each
Writer or Creator output that may become a final campaign candidate, include:

- the self-contained Writer or Creator child spec;
- the exact QA route and required QA technic;
- the artifact name and expected digest handoff;
- the release dependency on a digest-checked QA pass set;
- the marketer continuation held until all required QA results pass.

The Assistant creates the Writer/Creator production -> QA chain, adds the QA
cards as parents of the held marketer continuation, and releases that
continuation only after the required pass set and artifact digests match.
QA completion alone does not authorize publication. A failed result is
replaced or escalated through the Assistant-owned manifest; it is not silently
accepted or repaired by the marketer.

## Checkpoint handoff

After attaching `fan-out.yaml`, write a complete state checkpoint. Then block
with the marker below and stop:

```text
STATE: fan-out manifest attached; origin=<origin-task-id>; checkpoint=<checkpoint-key>; children=<keys>; continuation=<same-profile-and-mode>
FAN_OUT_READY: fan-out.yaml=<attachment-name>; policy=<allowed profiles, max count, purpose>; continuation=<profile>/<mode>/<branch>
```

The checkpoint returns no `metadata.specialist_plan`. In plan mode, the
Assistant's continuation remains the same marketer, `Mode: plan`, and
`Planning branch`; only that resumed continuation returns the final
SpecialistPlan. In execute mode, the continuation resumes the same internal
route after its declared dependencies pass.

`FAN_OUT_READY` and a final `metadata.specialist_plan` are mutually exclusive.
Do not place either handoff in the same completion.

## Worker briefs

- Writer: pass a complete WritingBrief with audience, purpose, medium, tone,
  length, language, allowed facts, terminology, and expected output.
- Creator: pass a complete MediaBrief with asset type, destination specs,
  source assets, accessibility requirements, exact filename, and expected
  attachment.
- Searcher: pass a narrow retrieval question, source coverage, recency, and
  citation requirements.
- Researcher: pass the synthesis question, decision criteria, evidence
  standard, counterevidence requirement, and uncertainty fields.

## Verification

- `fan-out.yaml` has exactly the five manifest fields and is attached before
  the block.
- The policy allows every child profile, purpose, count, and cost.
- The continuation preserves profile, Mode, Planning branch, grant ceiling,
  inputs, and acceptance criteria.
- Writer and Creator production includes QA route, digest checks, and release
  dependency before marketer fan-in.
- `STATE:` precedes `FAN_OUT_READY:`; no SpecialistPlan is returned at the
  checkpoint; the worker performs no card registration.
