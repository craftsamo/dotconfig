# Analyzing a guide

Trace the documented starting state, prerequisites, dependencies, results
and failure branches for the task in scope. Cite the exact point where a
reader would need unavailable information or an unexpressed condition.

Do not execute the instructions to fill evidence gaps. A missing recovery
branch is an observation about this text, not proof that no recovery exists.
For comparison, account for different roles, versions and starting states.

## Trace the consequence at the action

For the task in scope, follow prerequisite, ordered action, expected observable
result and supplied recovery. Check where the reader learns a consequential
warning: information after confirmation may be textually too late even when
the underlying procedure is correct. Use symptom-based lookup for a returning
reader, not a compulsory linear introduction or complete runbook template.

Build a finding from quote to source/evidence, mismatch and consequence.
Separate an actual defect in the documented sequence from missing evidence
about behavior and optional preference about headings. Give a correction
direction, not a replacement draft or operational instruction. No execution
is needed or authorized to assess what the text says.

## Worked example and retain condition

Fictional teaching material: the question asks whether the archive warning
arrives in time. The guide says "Select Archive and confirm" in the task,
and "Archiving makes the project read-only" only in a later appendix.
The supplied operator note confirms that consequence.

Quote: "Select Archive and confirm."
Source: the appendix and operator note describe the read-only consequence.
Mismatch: the task offers confirmation before disclosing its consequence.
Consequence: a reader following only the task can act without that information.
Recommend placing the known warning at the affected decision point, without
writing a replacement procedure or certifying the operation's safety.

Retain a warning already visible before the action; a separate warning box
is optional preference. Missing recovery text is a documented gap, not proof
that recovery is impossible. If the operator note is absent, the appendix can
still establish the ordering issue, but actual behavior remains unverified.

QA: report the inspected step and its dependencies; do not demand all possible
failure branches or apply runbook requirements to the analysis report itself.

QA: distinguish textual ordering/ambiguity from actual operational safety.
The report states what was read and what could not be verified, and does not
silently provide a replacement procedure or promise retry safety.

Source: point-of-work and action/consequence guidance adapted from [natural-japanese v1.5.0 guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/doctypes/guide.md).
Finding boundaries and the fictional example are local applications, not upstream quotations.
