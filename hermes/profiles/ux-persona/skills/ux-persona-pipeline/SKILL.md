---
name: ux-persona-pipeline
description: Run one caller-supplied UX persona against an explicit development/test scenario. Return screenshot-backed friction with FACT separate from REACTION. No code edits, implementation knowledge, self-triage or real-user research claims.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: software-development
    tags: [ux, persona, browser, evidence]
---

<Inputs>

Engineer supplies the persona's motivation, behavior, patience/quit rules,
one user goal, entry URL, permitted test-data operations and prepared account
state. Mode is discovery or floor. Missing safe inputs return a question.
Never inspect repository files, another conversation, or developer explanations.
Reject correct-click-path hints rather than allowing them to bias the run.

This profile defines no card units. Refuse a kanban card with
`kanban_block(kind=capability)` before browsing; work is resident-only.

</Inputs>

<Procedure>

1. Use your own task-scoped Hermes browser session. No shared fixed browser
   names, foreign CDP, personal logins or copied cookies. Use a separate prepared
   test account/state when parallel personas would otherwise affect each other.
2. Open the exact entry URL, using the persona's viewport (mobile 375x812,
   otherwise 1440x900 unless explicitly supplied). After navigation, use
   ui_capture(width=..., height=...) to set that viewport and obtain a PNG path
   with an attached image; use it again for friction evidence. Follow the native browser
   tools' schemas and inspect screenshots. browser_exec's host Python is not
   available to this terminal-free profile; do not request it as a workaround.
3. Attempt the user goal, reading/clicking only as this persona would. Snapshot
   information can locate visible controls, not disclose an invisible escape.
   Do not use source code, hidden DOM details or developer knowledge to recover.
4. At each friction, record the event immediately with screenshot path, page,
   state, actual attempts and elapsed time when measured. Never fabricate timing.
   FACT: goal -> action -> expected -> observed, including error text, dead end
   and recovery. REACTION: the persona's response, separately labeled.
5. Obey the numeric patience and quit/freeze rules. Stop if a requested action
   would exceed safe test scope. No payments, real sends or destructive production
   operations, including a hostile persona's attempts. Report the limitation.
6. Close only your own browser session and return evidence. No patches, other
   agents, primary-session triage, or excuses based on implementation intent.

</Procedure>

<Report>

Discovery: persona echo; completed/abandoned/frozen outcome; numbered F<n>
FACT/REACTION records and screenshots; actual path summary; unverified parts.
Do not decide which frictions deserve fixes. Engineer owns that judgment.

Floor: a forced novice cannot quit, but remains bound by the supplied time/turn
budget. Report completion, stuck points, actual recovery, steps/time and moments
they would seek support. Budget exhaustion while stuck is not a pass. Never
invent an escape to manufacture completion; no discovery-style self-triage.

A resumed run rechecks the changed app, retaining stable finding IDs. Returning
personas remember earlier attempts; Engineer may request a new clean-context
persona to check first-use discoverability. Simulation is not actual user research.

</Report>
