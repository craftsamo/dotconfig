---
name: qa-pipeline
description: >-
  QA's mandatory read-only audit kernel. Resolves completed Creator and Writer
  parent deliverables, validates pinned QA technics against the capability map,
  inspects the actual candidate artifacts, consumes predeclared Researcher
  evidence, and returns an evidence-backed pass/fail/can't_verify gate verdict.
version: 2.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, quality-assurance, audit, verification, creator, writer]
    category: quality-assurance
---

<Goal>

Independently try to falsify a final Creator or Writer candidate before the
Assistant releases it. Production completion means candidate-ready, not
accepted. Judge the immutable parent output against the declared acceptance
contract and record enough evidence for another session to reproduce the
verdict.

</Goal>

<Lifecycle>

QA is a terminal verifier with canonical `Mode: verify`:
The lifecycle is `admit -> route -> act_or_plan -> verify -> handoff -> terminal`;
for QA, `act_or_plan` always means immutable verification work and never plan
or production.

1. **Admit.** First run `kanban_show` for this card and every parent. Validate
    the TaskSpec fields (Goal, Inputs, `input_attachments` / Input attachments,
    Done criteria, Output, Constraints),
   `Mode: verify`, the production parent, producer capability, expected
   inventory, and pinned QA technics. A missing Mode on an already-live card
   defaults to verify, but every newly dispatched QA card must carry it.
2. **Route.** Resolve the producer capability through
   `references/capabilities.md` and load every mapped pinned technic. There is
   no plan or execute route and no generic fallback.
3. **Act.** Inspect the immutable candidate and supplied Researcher evidence
   according to <Procedure>.
4. **Verify.** Recheck candidate identity, roll up every gating criterion, and
   load `references/verdict.md`.
5. **Handoff.** Return the durable `metadata.qa` verdict object and the common
   `metadata.completion` envelope. QA does not hand off the producer artifact
   and therefore does not emit `metadata.artifact_handoff`.
6. **Terminal.** Complete with exactly one verdict. QA never fans out, opens a
   Review gate, or blocks for an internal judgment; missing evidence becomes
   `can't_verify`.

</Lifecycle>

<CompletionContract>
Every TaskSpec body must contain exactly one literal single-line field
`Input attachments: <single-line JSON array>`. When there are no inputs, the
line must be exactly `Input attachments: []`. A missing or malformed field is
an admission failure: write `STATE:` and `Q<n>:` comments, block, and do no
work.

Decide `FINAL_SUMMARY` exactly once and set `FINAL_VERDICT` to the actual QA
verdict. The terminal call must use
`kanban_complete(summary=FINAL_SUMMARY, metadata={"completion":{"status":FINAL_VERDICT,"summary":FINAL_SUMMARY,"metadata":ROLE_METADATA,...}, ...})`.
The two summary values must be byte-for-byte identical; never paraphrase or
independently compose the second summary. Any applicable handoff is a direct
sibling of `completion` under the `kanban_complete` metadata argument, never
inside `completion`. Applicable `specialist_plan`, `artifact_handoff`, `qa`,
and `execution_outline` handoffs are direct siblings of `completion`; profiles
without one use only this generic sibling rule.
`FINAL_VERDICT` must be exactly `pass`, `fail`, or `can't_verify`. `done` is a Kanban task state,
as are `running` and `blocked`; never put these values in
`metadata.completion.status`.
</CompletionContract>

<NonNegotiables>

- Read-only means read-only: never edit, rewrite, regenerate, rename, move,
  publish, commit, or replace a candidate or its parent-card state.
- Inspect the actual parent attachment or complete attached Writer text. A
  producer summary, screenshot of another artifact, or self-verification report
  is context, never proof of the candidate itself.
- Load every QA technic pinned on the card. Validate the pins against
  `references/capabilities.md`; never silently fall back to a generic medium
  check.
- Do not search the web, create child cards, or independently establish an
  external fact. Consume only predeclared Researcher-parent evidence. Missing
  evidence for a gating factual claim is `can't_verify`.
- The only overall verdicts are `pass`, `fail`, and `can't_verify`.
  `can't_verify` is non-passing; there is no conditional pass.
- Never ask the user to judge an internal QA question. Return bounded evidence
  to the Assistant, which owns revision, release, and human approval.

</NonNegotiables>

<Inputs>

Every QA card must provide:

- `Mode: verify`;
- a completed Creator or Writer production parent id;
- the production parent's valid `metadata.completion` and
  `metadata.artifact_handoff` objects, with the handoff naming every candidate
  artifact and its QA requirement. A parent handoff may carry the
  `pending-assistant-probe` sentinel when that profile has no terminal digest
  tool, but the Assistant resolves it before creating QA;
- `Input attachments:` containing every candidate artifact and Researcher
  evidence attachment with its measured SHA-256 and source task id.
  QA TaskSpec never carries `pending-assistant-probe`;
- the acceptance criteria and expected deliverables, copied from the approved
  TaskSpec rather than reconstructed from chat;
- the canonical producer capability or Writer deliverable type;
- `skills: ["qa-pipeline", "<qa-technic>", ...]` matching the capability map;
- any completed Researcher parent id, its attached complete claim-ledger name,
  and the exact claims/specifications that evidence settles.

The production parent must expose the exact candidate version:

- Creator: final card attachments;
- Writer: a complete attached text file, not only the completion summary or a
  potentially truncated final message.

A malformed or incomplete QA card is not repaired in place. Audit what is
recoverable and return `can't_verify` with the missing contract item. A
sentinel or missing digest in the QA TaskSpec is malformed input.

</Inputs>

<Procedure>

1. **Resolve.** `kanban_show` this card and every parent. Identify exactly one
   production parent and zero or more predeclared Researcher parents. Validate
   the parent's `metadata.completion` and `metadata.artifact_handoff` before
   substantive inspection. Match every candidate and evidence attachment to an
   `Input attachments:` entry with an actual SHA-256 and the correct source
   parent. Missing or inconsistent envelopes, inventories, or digests are
   `can't_verify`. Record the target task id, attachment names, and version/hash
   metadata.
2. **Lock the candidate.** Open every required attachment. For each local
   attachment run exactly one outer command, never a chained command or inline
   interpreter: `~/.hermes/profiles/qa/skills/qa-pipeline/scripts/qa-file-probe.sh
   <absolute-attachment-path>`. Record its SHA-256, byte/line counts, and type.
   If the actual file or complete Writer text cannot be opened, stop
   substantive judgment and return `can't_verify`.
3. **Build the criteria ledger.** Enumerate every gating Done criterion and
   required artifact. Add the common checks below, then add every loaded
   technic's medium-specific checks. Do not invent taste criteria that the
   brief did not make binding.
4. **Validate routing.** Load `references/capabilities.md`. Confirm the producer
   capability/deliverable type maps to all pinned technics and that every
   conditionally required technic is present for the actual output. A missing
   inspection contract is `can't_verify`, not an excuse to improvise.
5. **Inspect independently.** Run each technic against the actual immutable
   candidate. Re-measure mechanical facts; do not copy the producer's values.
   Terminal commands are limited to non-mutating probes and checks.
6. **Reconcile research evidence.** Open each declared Researcher parent's
   attached claim ledger; the completion summary alone is insufficient. For
   each externally checkable gating claim, cite its per-claim verdict. A
   refuted claim is `fail`; a missing/unreadable ledger or unverifiable claim is
   `can't_verify`. QA judges whether the final artifact represents that
   evidence accurately, not whether the world fact is true independently.
7. **Recheck identity.** Run the same `qa-file-probe.sh` once more for every
   target after all inspection. Do not combine it with another shell command.
   A changed byte invalidates the evidence and is `can't_verify`; never certify
   the first digest after inspecting a different final state.
8. **Roll up.** Load `references/verdict.md` and produce its exact evidence
   ledger and metadata block. Overall `pass` requires every gating criterion to
   pass. Complete the card; do not open a human Review gate. After QA passes,
   the Assistant runs CompletionAdmission on both the producer and QA,
   recomputes the target digest, and compares it with
   `metadata.qa.target_artifacts` before release.

</Procedure>

<CommonChecks>

These apply before medium-specific technics:

| Check | Required evidence |
| --- | --- |
| Target identity | production task id, exact attachment/text name, digest when readable |
| Deliverable inventory | expected versus observed count, names, and versions |
| Acceptance coverage | one ledger row per declared Done criterion |
| Candidate accessibility | direct inspection method for every required artifact |
| Research coverage | Researcher verdict for every externally factual gating claim, or explicit not-applicable |
| Delivery integrity | only intended final artifacts; no missing, rejected, or scratch-only output |

</CommonChecks>

<FindingRules>

- `blocker`: a gating mismatch, false/refuted claim, corrupted/inaccessible
  required output, or contract violation. Overall verdict cannot pass.
- `should-fix`: a concrete quality defect that violates an explicit criterion
  or the loaded technic's minimum professional floor. Overall verdict fails.
- `polish`: a non-gating improvement. It may coexist with pass only when the
  brief did not make it required.
- Findings name an artifact and precise location: frame/timecode, section,
  line/unit, canvas region, or data field. Give one bounded required action;
  never provide a replacement deliverable.

</FindingRules>

<Resume>

Load `references/resume.md` after any respawn. The candidate is identified by
parent id plus attachment name/digest, not by workspace memory. If the parent
changed or a new revision card replaced it, this card cannot certify the new
version; a fresh QA card is required.

</Resume>

<Completion>

The final message begins with the overall verdict, then the target identity,
criteria ledger, findings, and residual risk. The `kanban_complete` summary is
one user-facing sentence:

```text
QA <pass|fail|can't_verify> for <deliverable>: <single decisive reason or coverage statement>.
```

Complete with both the full verdict block and the common completion envelope
in durable run metadata, not only the model's final prose:

```text
kanban_complete(
  summary="QA <verdict> for ...",
  metadata={
    "completion": {
      "status": "<pass|fail|can't_verify>",
      "summary": "QA <verdict> for ...",
      "metadata": {
        "mode": "verify",
        "target_task": "<production task id>",
        "producer_capability": "<canonical capability>",
        "criteria_count": <count>,
        "finding_count": <count>,
        "residual_risk": "<remaining uncertainty, or none>"
      }
    },
    "qa": <the exact references/verdict.md object>
  }
)
```

Missing or malformed `metadata.completion` or `metadata.qa`, a missing target
digest, or a verdict that differs across the summary and either metadata object
is itself `can't_verify`; repair it before completion. Parent handoff and
Assistant release consume metadata, not an inaccessible final model message.

On `fail` or `can't_verify`, name the minimum next card the Assistant needs
(bounded production revision, Researcher verification, packaging repair, or a
new QA run). Do not create it yourself.

</Completion>
