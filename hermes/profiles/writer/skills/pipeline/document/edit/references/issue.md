# Editing an issue

Keep observed and expected behavior, reproduction conditions, feature goals
and proposed solutions distinguishable. Clarifying a report must not invent
a reproduction, elevate a hypothesis to root cause or imply a fix was tested.

Preserve relevant IDs, versions and sanitized evidence. Redact secrets or
personal data without replacing their absence with a fictitious log result.
An issue template may organize the report but cannot supply missing facts.

## Clarify evidence without diagnosing

For a bug, repair the released observed/expected distinction or the ordering
of supplied reproduction steps, without inventing a starting state. Keep
environment and evidence attached to the observation. Reordering sections
needs structure scope; clarifying a title need not redesign the report.
For features/tasks, retain desired outcomes rather than adding bug sections.

Leave untouched sections and protected content unchanged. A no-op is legitimate
when the report is already clear. A hypothesis stays a hypothesis even when
it suggests a plausible fix; an unprovided log cannot become proof of cause.
These are editing guides, not authority to reproduce the bug or operate a tracker.

## Worked example and retain condition

Fictional teaching material: the request permits correcting only the title's
unsupported diagnosis. The reporter's v3.2 steps end with "Request timed out"
after Archive. "Cache issue?" is a guess; expected Archived status comes
from supplied help. Sanitized evidence and environment fields are protected.

Before: "Cache corruption prevents archiving."
After: "Archive shows Request timed out in v3.2."
The title now states the observation the report supports rather than its
unestablished cause. The steps, expected status, environment and evidence stay
unchanged; the edit does not imply successful reproduction or a tested fix.

Retain "Possible cache issue" in an explicitly labeled hypothesis section.
If only spelling corrections were authorized, flag the title's diagnosis as
outside scope rather than silently replace it. A feature request with a clear
desired outcome needs no fabricated observed failure to qualify as complete.

QA: inspect changed claims against their specific supplied evidence and scope;
preserve uncertainty and do not widen a partial report into a runtime verdict.

QA: changes remain within the requested editing scope, each new factual
statement has support, and uncertainty is retained. Return the edited text;
do not modify a tracker, add invented closing links or run reproduction steps.

Source: fact/interpretation separation adapted from [natural-japanese v1.5.0 writing constitution](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md).
Issue-edit boundaries and the fictional example are local applications, not upstream quotations.
