# Analyzing error wording

Identify the operation, result claimed, reason and proposed recovery action.
Compare them with supplied evidence where requested. A timeout does not prove
non-delivery, an error string does not establish root cause, and a retry button
does not prove that repeating the operation is safe.

An unknown recovery path is an evidence gap, not a reason to invent instructions.
Distinguish readability concerns from system diagnosis. Quote only necessary,
sanitized text, keeping secret values and internal data out of the report.

## Craft decisions

Separate a known result from an unknown outcome, then inspect cause and recovery
wording independently. If field validation evidence exists, compare the named
field/condition; an empty field is not the same as an invalid supplied value.
Quote the claim, compare evidence, identify the mismatch and explain its possible
consequence. UI availability establishes neither retry safety nor user blame.
If no validation rule is supplied, report that limit instead of diagnosing input.
An analysis describes these boundaries without a replacement error message.

## Worked example

Fictional material: the message says 「送信に失敗しました。再送してください。」
A supplied record reports a timeout with delivery unknown. A retry button exists,
but no safety or duplicate-prevention evidence is supplied. Review state and advice.
Finding: quote 「送信に失敗しました」 against the unknown delivery result, and
「再送してください」 against the absence of established safe repetition.
Mismatch: the wording claims failure and recommends recovery beyond the record.
Consequence: retry could duplicate a submission if the first attempt completed;
neither duplication nor non-delivery is established as an actual event.
Why: the finding isolates two unsupported claims rather than inventing a cause,
blaming the user or treating the retry control as a safety guarantee.

Retain: a supplied empty-field rule can justify an entry instruction, while a
known range violation needs its actual constraint. Counterexample: deriving a
password rule from a network error fabricates a validation diagnosis.

QA evidence: include the minimal quotes, known/unknown result and limits on
recovery evidence. Explain conditional consequences; do not test transactions
or write replacement instructions to make a findings-only report feel complete.

Sources: local adaptation of [natural-japanese v1.5.0 writing constitution](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md)
and [revision guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md)
for evidence and bounded conclusions; [GOV.UK error message](https://design-system.service.gov.uk/components/error-message/)
for field/condition distinctions, and [Microsoft writing style](https://learn.microsoft.com/en-us/windows/apps/design/style/writing-style)
for no blame. Examples are local; no upstream Writer error manual, implementation
instructions, validation execution or review loop is imported.

QA: observed wording and inferred risk remain distinguishable. The report does
not verify transactions, promise recovery, repair the application or replace
the error message. Describing the text need not find a defect.
