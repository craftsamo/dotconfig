# Editing a guide

Identify preconditions, dependent steps, branch conditions and warnings before
shortening the text. Do not reorder operations for prose rhythm, remove a
safety condition as "redundant", or replace a known failure branch with a
generic retry suggestion.

Preserve the distinction between an expected result and a result actually
observed in a test. A substantive procedure change needs operational evidence,
not merely authorization to polish the document.

## Keep the operational dependency intact

For wording edits, clarify the actor, action or observable result without
changing the procedure. Within a released structure edit, move a warning with
its consequential action so the reader encounters the condition before acting.
Keep prerequisites ahead of dependent steps and supplied recovery tied to its
specific failure state. These guides do not require a new runbook template.

Leave untouched sections and protected content unchanged. If the instruction
is already clear, a no-op is legitimate. A protected warning in a poor location
requires a reported conflict, not silent relocation. Missing recovery cannot
be repaired by a generic retry, and editing never requires executing the task.

## Worked example and retain condition

Fictional teaching material: the request permits reordering only the archive
step and its warning. The supplied operator note says Archive makes the
project read-only; the admin prerequisite and Active job branch are protected.

Before: "Select Archive and confirm. Warning: archiving makes the project
read-only."
After: "Archiving makes the project read-only. If that is intended, select
Archive and confirm."
The same consequence now informs the decision before confirmation. The edit
changes presentation order, not the operational sequence, and leaves the
admin prerequisite, Active job recovery and untouched instructions unchanged.

Retain an already adjacent warning that precedes the action. Repeating it in
every step would add noise without fixing a defect. If only spelling changes
were requested, flag a late warning as outside scope rather than moving it;
no-op output is valid when there is no supported correction in scope.

QA: inspect changed actions with their prerequisites, result and recovery;
check linked step references without certifying any operational outcome.

QA: changed instructions retain their starting state, order and relevant
failure paths. Check affected step references in the whole document. Do not
run the guide or certify that an untested procedure is safe.

Source: point-of-work and action/consequence guidance adapted from [natural-japanese v1.5.0 guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/doctypes/guide.md).
Edit boundaries and the fictional example are local applications, not upstream quotations.
