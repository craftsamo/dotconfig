# Notification text

Identify the actual event, affected object, current state and any known action
the recipient can take. Distinguish an event being queued, processed or
completed. Do not infer completion from a request being accepted or create
urgency/deadlines that were not supplied.

When title and body are needed, make their roles clear without duplicating
the whole message. Put the relevant change first, then the known action or
destination if useful. A notification does not always need a call to action.

Avoid exposing unnecessary private details on a surface that may be visible
to others. Use the supplied privacy/display constraints; if sensitive content
is essential and the surface is unknown, ask rather than disclose by default.

## Craft decisions

Lead with the verified state, then its supported impact on the reader. Add a
supported action only if needed; a status update can end without one.
If title and body are supplied roles, let the title identify the event and
the body explain the consequence rather than repeating a generic alert.
Missing response evidence supports neither a success claim nor a failure claim.
For in-product text, distinguish task-essential information from an elsewhere
notification; flag a placement dependency, never implement or relocate a banner.

## Worked example

Fictional material: the service owner confirms that report export is paused
and reports cannot currently be downloaded. A title/body notice is requested;
no cause, restoration time or recovery control is supplied. No action is needed.
Draft title: 「レポートの書き出しを停止しています」
Draft body: 「現在、レポートをダウンロードできません。」
Why: title and body separate the verified state from its practical impact.
Neither invents a reason for the pause nor tells the reader to use a control
whose existence and suitability have not been established.

Retain: a single-line notice that already communicates state and impact needs
no extra heading. Counterexample: 「まもなく復旧します。再試行してください。」
adds a recovery promise and instruction absent from this material.

QA evidence: map each state verb and impact to the supplied event record;
record missing completion evidence as unverified, not success. Any action must
trace to a known destination and a reason it is appropriate for this event.

Sources: local adaptation of [natural-japanese v1.5.0 writing constitution](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md)
and [revision guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md)
for grounding and bounded claims; [GOV.UK notification banner](https://design-system.service.gov.uk/components/notification-banner/)
for task relevance only, not implementation. No upstream notification manual
is implied; examples and channel decisions are locally authored adaptations.

QA: event and state match the evidence, any action really exists, and title/body
can be extracted without instructions. Character fit, truncation and notification
delivery are unverified without the corresponding measurement or rendered test.
