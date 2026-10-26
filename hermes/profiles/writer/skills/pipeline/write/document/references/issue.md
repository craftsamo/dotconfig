# Issue

Determine whether the supplied request is a bug report, feature request or
task. For a bug, distinguish observed behavior, expected behavior, supplied
reproduction steps and the environment in which observations were made.
For a feature/task, state the desired outcome and constraints instead of
inventing a bug reproduction.

Keep hypotheses separate from demonstrated causes. A log excerpt can support
an observation without proving why it occurred. Include only relevant,
sanitized excerpts; do not expose tokens, personal data or internal paths
merely because they were present in the input.

Missing versions, reproduction steps or acceptance conditions remain gaps.
Do not run code, inspect a production system or assign a diagnosis to make
the report look complete. Use the supplied issue template where applicable.

## Make the report inspectable

For a bug, lead with the observed failure and affected task rather than a
suspected component. Separate the expected outcome and its basis from the
actual observation. Order supplied reproduction steps so another reader can
identify the starting state, action and failure point; do not claim those
steps are reproducible when necessary conditions are missing.

Attach environment and sanitized evidence to the observation they describe.
Label a reporter's hypothesis as a hypothesis even when a log mentions the
same component. Describe missing steps or versions as evidence gaps, not
guessed defaults. For a feature or task, use the desired outcome and supplied
acceptance conditions instead; bug sections are guides, not mandatory slots.

## Worked example and retain condition

Fictional teaching material: a reporter used app v3.2 on macOS, opened an
existing board, selected Archive and saw "Request timed out." The supplied
help says archiving should change the board's status to Archived. The exact
OS version and request log are absent; "cache issue?" is the reporter's guess.

A report passage can read: "Archive shows Request timed out on an existing
board in app v3.2 on macOS. Supplied steps: open an existing board, select
Archive. Observed: Request timed out. Expected from the help: status changes
to Archived. Exact OS version and request log were not supplied. Reporter
hypothesis: a cache issue; cause not established."
The report allows inspection of the known path without pretending that Writer
reproduced it or that the timeout proves a cache defect.

Retain "Add CSV export so analysts can reuse board data" as a feature goal
when that is the request. Inventing a failing export sequence or a confirmed
fix would make the issue less reliable, not more complete.

QA: for the requested issue type and released section, trace observations and
expectations separately; missing runtime evidence limits reproduction claims.

QA: the issue can be understood within its stated evidence and scope, observed
and expected states are distinct, and no unsupported fix or closing link is
invented. Delivering issue text does not create or edit a tracker entry.

Source: fact/interpretation separation adapted from [natural-japanese v1.5.0 writing constitution](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md).
Issue construction and the fictional example are local applications, not upstream quotations.
