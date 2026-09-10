# Editing an error message

Keep the operation, known result, uncertainty and supported next actions.
Shortening "result could not be confirmed" to "failed" changes a fact.
Do not add automatic retry advice or a safe-to-repeat claim without evidence,
especially for payment, submission or deletion.

Clarify wording without inventing the cause: a network error is not proof of
invalid credentials. Preserve supplied codes/placeholders and remove unnecessary
sensitive internals without replacing them with fabricated user-facing facts.

## Craft decisions

Protect intent and distinguish the known result from an unknown outcome before
shortening. Authorized changes may clarify a supplied field validation condition,
not infer a rule or cause from a generic error. An empty field needs different
wording from an invalid value when the supplied evidence distinguishes them.
If outcome wording is already accurate and concise, a no-op is valid. Neither
an available control nor a friendlier tone proves retry safety or user blame.
Keep a supported recovery step separate from any unverified explanation.

## Worked example

Fictional material: source 「予約人数の入力内容に問題があります。」 appears for
values outside 1 to 6. The supplied rule requires an integer in that range;
the requester authorizes clarifying this field's range error, and no other edit.
Revision: 「予約人数は1〜6の整数で入力してください。」
Why: the revision names the field and its actual condition instead of a vague
problem. It does not claim that input was empty, diagnose a cause or add retry.
The supplied rule, not the availability of the input box, authorizes this guidance.

Retain: 「送信結果を確認できませんでした。」 can remain a no-op when confirmation
alone is unavailable. Counterexample: 「送信に失敗しました。再送してください。」
turns an unknown outcome into failure and asserts an unsupported recovery path.

QA evidence: compare changed condition wording to the supplied validation rule,
or show that known/unknown result boundaries survived shortening. Quote unchanged
codes and protected qualifications only as needed, without sensitive internals.
Report an unsupported cause or retry-safety claim as a gap, not a system diagnosis.

Sources: local adaptation of [natural-japanese v1.5.0 writing constitution](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md)
and [revision guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md)
for preserved uncertainty and selective edits; [GOV.UK error message](https://design-system.service.gov.uk/components/error-message/)
for field/condition specificity, and [Microsoft writing style](https://learn.microsoft.com/en-us/windows/apps/design/style/writing-style)
for no blame. Examples are local, not upstream Writer error manuals; component
implementation and source review loops are outside this adaptation.

QA: compare the state and recovery claims before/after, not just the length.
Existing controls do not establish retry safety. The revision is a draft,
not a repair, transaction check, restoration guarantee or sent notification.
