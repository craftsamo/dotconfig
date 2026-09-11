# UX persona evaluation

Use for requested usability testing, meaningful changed user journeys or a
critical-flow gate, after blocking visual defects are resolved. It is not a
substitute for functional tests, actual user research or a visual-design review.
Read the [persona definitions](personas.md) before selecting a run.

1. Define one user-level outcome, exact entry URL, prepared test state, allowed
   operations and a bounded run budget. No correct path, implementation vocabulary
   or explanation of controls. Missing safe test data stops the run.
2. Send each persona to its OWN ux-persona resident conversation using
   specialist_call(target="ux-persona", kind="work"). The core three provide
   different failure modes; add extensions when relevant. Parallelize only when
   accounts/application state are independent; otherwise serialize. Never play
   all personas in Engineer's implementation-informed context or one shared chat.
3. Triage FACT before REACTION. Signal: objective task damage (dead end, wrong
   outcome, misleading label, missing feedback, unrecoverable state) or corroborated
   friction across different personas. Noise: task succeeded and only attitude
   differs, with no observable defect. Watch: real but isolated low-impact friction;
   promote when repeated. Discount hostile outrage; do not dismiss a novice's
   real friction merely because their reaction blames themselves.
4. Report Signals with evidence and correction direction, Watches and a count of
   discarded Noise. The persona never performs this triage. Engineer sends accepted
   fixes through OpenCode, then requests a recheck of the same finding IDs in each
   original persona conversation. Returning personas remember earlier attempts;
   add a new clean-context run when testing first-use discoverability.
5. For critical-flow acceptance, run the forced-novice floor AFTER Signals are
   fixed. Pass requires completion without permanent stuck points within the
   bounded test; failure or exhausted budget needs correction or an explicit
   unresolved result. No paid/production transaction is authorized by a floor test.

Keep actual observations separate from inferred causes and simulated reactions.
Do not invent durations, attempts or successful actions. Screenshots are observed
evidence, not an automatic usability verdict. Close accepted specialist sessions;
the implementation remains with OpenCode, not the evaluator.
