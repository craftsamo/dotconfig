# Editing a notification

Preserve event identity, affected object, state, action destination and known
privacy constraints. Concision must not turn queued/processing into completed,
or a possible event into a confirmed one. Evidence is required for state changes.

Keep title/body roles distinct and do not move essential conditions into an
unseen secondary field just to meet a length target. Never insert urgency,
a deadline or a required action that the notification did not establish.

## Craft decisions

Within authorized changes, clarify the verified state first and its supported
impact next. Keep a supported action only if it is needed for the released purpose.
If the title repeats the body, use the editable body for the known consequence;
do not promote a missing response into a success claim to sound reassuring.
Protect intent, event identity and uncertainty. A clear status-only notice may
be a no-op. Task-essential information should not be hidden in an elsewhere
notification; report the placement concern without moving or implementing UI.

## Worked example

Fictional material: title 「書き出し処理中」 is protected. Body 「書き出し処理を
行っている状態です。まだダウンロードはできません。」 may be shortened.
The supplied state confirms processing prevents downloading; no completion
time or next action is known. The notice is informational.
Revision body: 「処理中のため、まだダウンロードできません。」
Why: the shorter sentence keeps the supplied connection between state and impact.
The protected title stays unchanged, and the notice still makes no demand.
Nothing in the edit establishes completion or when downloading will become possible.

Retain: a clear body that already states this limitation needs no rewrite;
return a no-op. Counterexample: 「書き出しました。ダウンロードしてください。」
converts processing into success and offers an action unavailable in the material.

QA evidence: compare state verbs and the impact before/after against the record;
confirm the protected title. Quote any retained action and its support, or note
that none is needed. Display and actual completion checks remain separate.

Sources: local adaptation of [natural-japanese v1.5.0 writing constitution](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md)
and [revision guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md)
for bounded claims and selective edits; [GOV.UK notification banner](https://design-system.service.gov.uk/components/notification-banner/)
for task relevance, not implementation. No upstream notification manual is
implied; examples and channel-specific editing decisions are local adaptations.

QA: text still describes the same event and only necessary private detail is
included. A shorter source is not proof of correct truncation, display fit or
successful delivery; preserve unperformed checks in the report.
