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

QA: prerequisites precede dependent steps, result claims have evidence, and
known error branches remain visible. A reader's ability to follow the prose
does not establish that the actual procedure has been tested.
