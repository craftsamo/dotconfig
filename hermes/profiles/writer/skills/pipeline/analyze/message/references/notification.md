# Analyzing notification text

Inspect how title/body identify an event, object, state and any requested action.
Quote an ambiguous reference or unsupported completion claim. Use the provided
display/privacy constraints rather than assuming where the notification appears.

Separate the wording's assertion from evidence of the actual event. Source text
does not establish delivery, device truncation or whether a link/control works.
Missing state information limits that check, not every analysis of the text.

## Craft decisions

Trace verified state, supported impact and any needed action across title/body.
If the only evidence is a missing response, neither success nor failure follows.
Quote a claim, compare event evidence, identify any mismatch and explain its
possible consequence without verifying the event through the wording itself.
If the notice contains task-essential information, distinguish that from an
elsewhere notification and flag the content dependency, not an implemented move.
A status-only notice needs no CTA; analysis supplies no replacement notification.

## Worked example

Fictional material: title 「書き出し完了」; body 「ダウンロードできます。」 The
supplied event record confirms only that export was queued; completion and
download availability are unknown. The question asks whether the state is faithful.
Finding: quote 「書き出し完了」 and 「ダウンロードできます」 against the queued record.
Mismatch: the wording asserts completion and availability beyond that evidence.
Consequence: a reader could expect a usable download even though readiness is
unverified. The record also does not prove that export has failed.
Why: the finding distinguishes asserted state from known state and does not
invent an alternative notice, restoration time or recovery instruction.

Retain: an accurately supported status update can stand without an action.
Counterexample: treating absence of a completion response as proof that the
operation succeeded, failed or is safe to repeat exceeds the available evidence.

QA evidence: preserve the relevant state quotes, compared event record and
unknown completion/download status. Explain the bounded consequence; do not
claim actual engagement, display placement or a working action from text alone.

Sources: local adaptation of [natural-japanese v1.5.0 writing constitution](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md)
and [revision guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md)
for evidence and bounded conclusions; [GOV.UK notification banner](https://design-system.service.gov.uk/components/notification-banner/)
for task relevance, not component behavior. No upstream notification manual is
implied; examples and analysis questions are locally authored adaptations.

QA: observations stay within the question and available evidence. Do not claim
measured attention, engagement or actual exposure of private content from a
draft alone. The analysis is not a replacement or dispatched notification.
