# Editing an error message

Keep the operation, known result, uncertainty and supported next actions.
Shortening "result could not be confirmed" to "failed" changes a fact.
Do not add automatic retry advice or a safe-to-repeat claim without evidence,
especially for payment, submission or deletion.

Clarify wording without inventing the cause: a network error is not proof of
invalid credentials. Preserve supplied codes/placeholders and remove unnecessary
sensitive internals without replacing them with fabricated user-facing facts.

QA: compare the state and recovery claims before/after, not just the length.
Existing controls do not establish retry safety. The revision is a draft,
not a repair, transaction check, restoration guarantee or sent notification.
