# Tutorial

State the intended result, environment and prerequisites from the supplied
evidence. Order steps by actual dependencies. Keep warnings before the action
they constrain, and place observable results after the relevant steps.

Distinguish verified commands/output from illustrative snippets. Writer
does not gain a terminal by documenting one. Missing runtime evidence goes
back to the requester; do not fabricate success logs or invent a recovery
command. Preserve actual versions and the limits of the tested environment.

QA: each step has enough context to be followed, its stated outcome has
support, and failure handling does not promise an unverified safe retry.

## Build a Followable Step

If an action depends on a state, put that precondition before the action,
then give the expected result and supported recovery for a mismatch. Keep
the action's subject and object close: readers should not carry several
conditions across a long sentence to discover what they must select.
Spend explanation on the step where choices or failure states diverge;
do not pad routine steps to the same length.

Locally authored example (assume these details were supplied in a guide):
Precondition: "Open the saved draft with editing permission."
Action: "Select Export, then choose PDF."
Expected result: "The guide says an export dialog opens."
Recovery: "If Export is unavailable, check the document's permission panel
as the guide directs; an unexpected error has no supplied recovery here."
Reason: each observation belongs to one action, and the permission check is
not an invented command or an assertion that Writer ran the application.
Label documented expectations separately from a supplied user's run record.

Retain: a concise numbered sequence whose dependencies and results are
already explicit. Step repetition helps execution; varying verbs for rhythm
can obscure that the reader repeats the same operation on another object.
Do not turn a missing recovery into "run again" or a fabricated success log.

QA evidence: map each consequential action to its source precondition,
expected result and recovery boundary. Quote any unsupported transition
and name the missing evidence rather than executing code to fill the gap.
Check that a shortened warning still appears before the risky action.

Local adaptation of [natural-japanese v1.5.0 readability principles](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/readability-principles.md)
(one main assertion, nearby modifiers) and [genre notes](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/genre-notes.md)
(technical precision); this step model and example are locally authored, not runtime evidence.
