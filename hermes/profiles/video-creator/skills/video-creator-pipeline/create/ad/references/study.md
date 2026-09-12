# Explicit diagnostic study

Use only when Creator releases a bounded visual/motion question within an ad
production, not because a final ad is missing a CTA. This is an opt-in purpose of
create-ad, not a new media family or an unrestricted animation tool. Final ad
requirements remain unchanged.

## Proposal, still zero production

Require `purpose: study`, an explicit 1..10 second duration and a concrete
`question`. Preserve product, audience, approved message/copy, assets, style and
constraints relevant to the question. Do not invent placeholder CTA text to pass
the final-ad schema. A study has no `cta` field or CTA-role row. It retains at
least one real message row and the ordinary first/last/hold proof samples; a
text-free study is not supported by this version's contrast/copy proof contract.
Mix mode is not supported here; approved supplied WAV cues remain available under
the unchanged media rules. No new synthesis, upload, capture or model call.

Write the ordinary v1 plan with `purpose: "study"` and `question`, omit `cta` and
`mix`, and keep all other required fields. Run the read-only `preflight` command
on the plan and existing asset directory. Return the exact plan/hash and STOP.
The client approves the study's actual scope and bytes before source authoring.
The host's existing attempt/review allowance applies; study is not a new parallel
budget or an automatic retry. A parent request for advice is not this release.

For final purpose, omit `purpose`/`question` from plan JSON so existing final plans
retain their exact schema and behavior. A final must still have its real CTA and
6..30 second duration.

## Execution after exact approval

Use the same source contract and Python invocation as the owning leaf, but call:

```text
ad-render.py freeze-study --source SOURCE --plan PLAN --approval-sha256 HASH --project NEW_PROJECT
ad-render.py snapshot --project NEW_PROJECT --out NEW_PREVIEW
```

Inspect the preview against the question and exact copy, write findings in qa.md,
and obtain actual approval of its printed preview hash. Only then call:

```text
ad-render.py render-study --project NEW_PROJECT --approved-preview NEW_PREVIEW --approval-sha256 PREVIEW_HASH --out NEW_OUTPUT
```

The source root is still `data-composition-id="ad"`; that is a renderer identity,
not the output's status. The frozen integrity and plan bind `purpose: study`.
Ordinary `freeze` rejects study plans and ordinary `render` rejects study projects.
`render-study` likewise rejects final projects. Output is `study.mp4`, with
`artifact_role: diagnostic-study` and `final_eligible: false` in qa.json.

All original source/hash/runtime/preview checks and decoded-media QA still run.
Report sampled versus continuous-motion evidence honestly. Any changed source or
question needs a fresh proposal/project/preview and the real approvals. Never
mutate the existing frozen bundle or its purpose to promote it.

## Result and continuation

Return the answer to the named question, observed limitations and exact evidence.
A successful study can inform a new final-ad proposal; it cannot supply the
final's copy/CTA approval or bypass its new frozen-preview approval. Other media
use their own supported bounded units, never this helper as an unauthorized
cross-profile fallback.
