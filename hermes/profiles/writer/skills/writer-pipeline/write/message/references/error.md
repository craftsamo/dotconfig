# Error message

Identify the affected operation, what is actually known about its result, and
which recovery actions are established. A timeout or missing acknowledgement
can leave completion unknown. Do not say "not sent", "not saved" or "not
charged" merely because no success response was received.

State the known problem in user-facing terms. Include a reason only when
supported and a next action only when available and appropriate. A retry
button's existence does not prove repeating an operation avoids duplicates
or double charges. A missing recovery path is a gap, not a template slot to fill.

For a supplied unknown send result, "送信結果を確認できませんでした。" can
state that uncertainty without inventing failure or a safe retry. Add a
history-check instruction only if such a control and its use are confirmed.
Do not blame the user or expose raw errors, secret values or internal paths.

## Craft decisions

Separate a known result from an unknown outcome before choosing the verb.
If validation evidence names a field and condition, name both: an empty field
needs an entry instruction; an invalid value needs its supplied constraint.
Do not infer a validation rule from a generic error or a service interruption.
For uncertain completion, describe what could not be confirmed, not a guessed
cause, blame or non-delivery. UI availability alone establishes no retry safety.
Use a recovery instruction only when its applicability and safety are supported.

## Worked example

Fictional material: a form's validator reports that the required 「予約人数」
field is empty. The supplied rule is a whole number from 1 to 6; the requester
wants separate wording for empty input and a value outside that range.
Draft, empty input: 「予約人数を入力してください。」
Draft, outside range: 「予約人数は1〜6の整数で入力してください。」
Why: each message names the same field but responds to a different known
condition. Neither attributes carelessness or promises that submission succeeded.
This validation example establishes no facts about any transaction outcome.

Retain: 「送信結果を確認できませんでした。」 remains appropriate when only
confirmation is unavailable. Counterexample: replacing it with 「未送信です。
再送してください。」 invents non-delivery and potentially unsafe repetition.

QA evidence: pair each field/condition with the supplied validation rule, or
pair the outcome wording with the known result and explicit unknowns. List
unsupported cause or recovery claims as gaps; do not diagnose the application.

Sources: local adaptation of [natural-japanese v1.5.0 writing constitution](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md)
and [revision guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md)
for grounding and preserved uncertainty; [GOV.UK error message](https://design-system.service.gov.uk/components/error-message/)
for field/condition specificity, and [Microsoft writing style](https://learn.microsoft.com/en-us/windows/apps/design/style/writing-style)
for no blame. Examples are local; no upstream Writer error manual, implementation,
validation execution or source review loop is imported.

QA: outcome, cause and recovery claims retain their actual evidence level.
Error codes/placeholders stay exact when required. No false data-loss,
restoration-time or safe-retry guarantee; the draft is not a system fix.
