# Guide and runbook

Start from a concrete task, its preconditions, permissions and known starting
state. Use supplied operational evidence, not a guessed screen sequence.
Separate an introduction meant to be read once from instructions used later
at the point of work, when that distinction is useful.

Order dependent steps by execution. For each meaningful step, explain the
action and supported observable result. Put conditions and safety warnings
before the affected action. Add failure branches or escalation contacts only
when they are known. A missing recovery procedure is not a license to invent
one or promise a destructive operation is reversible.

Let task-oriented headings support lookup. Do not require a glossary, chapter
bridges or a fixed number of steps when the task does not need them.

## Connect action to consequence

Use an ordered path for dependent actions and a symptom-to-action entry for
readers returning with a known problem. Place background separately only when
the procedure still makes sense without it. These are construction choices,
not mandatory chapter types or a reason to add a glossary to a short guide.

At a consequential action, name the supplied condition and consequence before
the reader acts; a warning in a remote appendix is too late. Pair the action
with an observable result rather than "complete the process." Include a
recovery branch only for the state and version its source actually covers.
Do not turn an expected result into a witnessed outcome or execute the guide
as part of authorship. Missing recovery evidence stays a named limitation.

## Worked example and retain condition

Fictional teaching material: an operator note says only workspace admins can
archive a project, archived projects become read-only, and a successful
archive changes the badge to Archived. The documented action is to select
Archive and confirm. On "Active job," cancel the dialog
and wait for that job to finish before reopening it; no undo is documented.

An action passage could read: "Only workspace admins can archive a project.
Archiving makes it read-only. If that is intended, select Archive
and confirm. The operator note gives Archived as the expected badge.
If Active job appears, cancel the dialog and wait for the job to finish
before reopening it. An undo procedure is not supplied."
The consequence sits at the decision point, and recovery addresses the
specific supplied obstruction rather than promising that every retry is safe.

Retain a short, independent lookup instruction such as "Find the invoice ID
under Billing > History" when sufficient. It needs neither a recovery tree
nor an invented prerequisite just to resemble a runbook.

QA: inspect only the released task and its dependencies; any warning relocation
must leave the condition visible before the affected action.

QA: prerequisites precede dependent steps, result claims have evidence, and
known error branches remain visible. A reader's ability to follow the prose
does not establish that the actual procedure has been tested.

Source: task lookup and action/consequence guidance adapted from [natural-japanese v1.5.0 guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/doctypes/guide.md).
The operational boundaries and fictional example are local applications, not upstream quotations.
