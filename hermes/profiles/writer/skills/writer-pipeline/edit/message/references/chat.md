# Editing a chat reply

Use the original and supplied preceding turn to retain what the answer refers
to. Shortening may remove redundant wording but must preserve negation,
uncertainty, the requested action and any condition on availability.

Do not infer a closer relationship from a casual tone request or add emotions,
reactions, excuses or promises that were not authorized. Preserve exact
mentions, links and quoted text when protected. Channel conversion requires
actual destination constraints, not guessed Markdown support.

## Craft decisions

Keep one contextual unit that answers the relevant turn and supports action
only when requested. If previous referents compete, name the one established
by supplied context; do not resolve ambiguity from a guess about intent.
Authorized changes may shorten repetition, not erase a condition or add a demand.
If a short informative reply already works, preserve it as a no-op; no greeting
is required. Protect intent and the original conversational distance rather than
standardizing every message into a formal request or cheerful acknowledgement.

## Worked example

Fictional material: the prior exchange discusses both a room and a meeting time.
The source is 「それで決まりました。」 The sender confirms that only the venue
is decided, 第2会議室, and authorizes replacing the unclear referent. No action
is requested, and the time is not decided. All other meaning must remain intact.
Revision: 「会場は第2会議室に決まりました。」
Why: the named topic and supplied room remove ambiguity without claiming that
the time is settled or asking the colleague to reserve anything.
The edit fixes one reading problem rather than expanding the conversation.

Retain: when the prior turn has only one clear referent, 「それで決まりました。」
can be a no-op. Counterexample: 「第2会議室を予約しておきます。」 changes a venue
decision into the sender's commitment to act, not just a clearer reference.

QA evidence: compare the replaced referent against the supplied turn and the
authorized clarification. Quote any retained condition or negation; confirm that
no extra action or greeting was inserted merely to make the revision longer.

Sources: local adaptation of [natural-japanese v1.5.0 writing constitution](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md)
and [revision guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md):
concrete grounding and selective edits that preserve supplied intention.
These are shared principles, not upstream chat manuals; examples are local.

QA: compare the revision in context, not only sentence by sentence. Untouched
content stays intact and the new tone does not change the response's intent.
Do not send, recall or edit a live message; deliver the revised text only.
