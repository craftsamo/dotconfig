# QA verdict contract

Use this schema verbatim enough that the Assistant can parse the gate without
reinterpreting prose. Evidence is an observation or measurement, not the word
"verified."

```yaml
qa:
  target_task: "<production task id>"
  producer_capability: "<creator-* | core:tts | writer:marketing-copy | writer:technical-prose | writer:documentation | writer:script>"
  target_artifacts:
    - name: "<attachment or complete text file>"
      sha256: "<digest | unavailable>"
  research_parents: ["<task id>"]
  technics: ["<qa-*>"]
  verdict: pass | fail | can't_verify
  criteria:
    - id: "<stable criterion id>"
      requirement: "<gating requirement>"
      verdict: pass | fail | can't_verify
      method: "<tool, measurement, or direct inspection>"
      evidence: "<observed result and precise location>"
      exclusions: "<uninspected scope, or none>"
  findings:
    - severity: blocker | should-fix | polish
      location: "<artifact/frame/section/line/unit/data field>"
      issue: "<one concrete defect>"
      required_action: "<bounded correction; never a rewritten deliverable>"
  residual_risk: "<remaining uncertainty, or none>"
  reviewer_scope: read-only
```

## Roll-up

- `pass`: every gating criterion is `pass`; no blocker or should-fix finding.
- `fail`: at least one criterion has observable evidence of a mismatch.
- `can't_verify`: no mismatch is proven, but required evidence, access, tooling,
  mapping, or Researcher support is missing.
- When both fail and can't-verify criteria exist, overall verdict is `fail` and
  the unverifiable rows remain explicit.
- `polish` does not change a pass unless the TaskSpec made that property gating.
- Never emit `conditional pass`, percentages, scores as verdicts, or an average
  that hides one failed requirement.

## Revision boundary

A verdict certifies only the named parent task and exact artifacts. Any content
change, regeneration, re-export, or file replacement requires a new QA card.
Metadata-only delivery repair also requires a fresh QA card if it can change
what the user receives.
