# Analyzing an issue

Distinguish a bug report, feature request and task before judging completeness.
For a bug, inspect observed/expected behavior, reproduction conditions and
environment. For a feature, inspect the desired outcome and constraints.

Quote the evidence behind a claimed ambiguity or unsupported diagnosis.
Logs may show a failure without proving its cause. Missing reproduction
information is not evidence that the bug cannot occur. Do not execute steps,
access production systems or research a diagnosis under this writing task.

## Evaluate what the report establishes

For bugs, trace the observed versus expected outcome, supplied ordered steps,
environment and sanitized evidence. Check whether the expectation has a stated
basis and whether reproduction claims exceed the supplied conditions. For
features/tasks, inspect the desired outcome instead. These guides do not
require bug fields for every issue or authorize reproducing supplied steps.

Build a finding from quote to source/evidence, mismatch and consequence for
triage. Separate an actual defect in the text from missing evidence and
optional preference for another template. Distinguish a hypothesis from an
established cause, even if plausible. Give findings or a correction direction,
not a replacement draft, system diagnosis or tracker operation.

## Worked example and retain condition

Fictional teaching material: an issue title says "Cache corruption prevents
archiving." The supplied v3.2 report describes selecting Archive and seeing
"Request timed out." Help establishes expected Archived status; the reporter
asks "Cache issue?" and supplies no causal investigation.

Quote: "Cache corruption prevents archiving."
Source: the timeout observation and reporter's question establish failure and
a hypothesis, not cache corruption.
Mismatch: the title elevates that hypothesis to a confirmed cause.
Consequence: triage could be steered toward an unproved component. Recommend
separating observed failure from suspected cause without rewriting the issue
or claiming to have reproduced the timeout.

Retain "Possible cache issue" when labeled as a hypothesis. Missing exact OS
version limits reproduction confidence, not the possibility of the bug.
An alternate issue template is optional preference unless explicitly required;
missing logs mean missing evidence, not proof that the reported failure is false.

QA: ground only the requested textual findings in the supplied report; do not
turn a clarity review into root-cause research or new reproduction evidence.

QA: the report answers the requested textual question, sanitizes quoted
sensitive evidence, and separates hypotheses from facts. It does not require
a new issue template of its own or create, edit or close a tracker entry.

Source: fact/interpretation separation adapted from [natural-japanese v1.5.0 writing constitution](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md).
Issue-analysis decisions and the fictional example are local applications, not upstream quotations.
