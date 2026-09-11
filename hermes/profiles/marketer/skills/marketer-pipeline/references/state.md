# Private marketing records and resumes

This file defines records; never store actual task/account/reader data in this
skill or either config repository. Use the client's existing private project/job
location. For a direct-human request without one, agree on a location before
durable production. Consultation can remain in the conversation. Do not scan
unrelated workspaces or manufacture an existing fact ledger.

Marketer maintains the record; the user decides commitments/approvals. Assistant
receives a concise handoff and the record location, not a duplicate strategy.
Existing projects may already have positioning.md, offers.md, channels.md,
facts.md, non-goals.md, decisions.md, kpi.md and experiments.md. Reuse those in
place; no schema conversion or eight-empty-file ceremony is required. A small
job can keep the necessary sections in one private file.

## What to retain

- Goal/priorities/non-goals; actual user decisions and their scope/date.
- Evidence: assertion, source/locator, date, scope, uncertainty and relevance.
  Separate observed facts, reported statements, interpretations and hypotheses.
  Recheck facts when prices, products, policies or source conditions change.
- Proposals and experiments: hypothesis, action, constraints, observations,
  decision and reasons. Record unknowns explicitly and retain rejected options.
- Content units: released operation/scope, immutable input version or hashes,
  Writer/Creator target/conversation, actual outputs, acceptance and corrective
  rounds. Changing bytes/assets invalidates dependent approval and evidence.
- Service drafts: platform/content type/account, create or update, existing
  target and expected current remote revision/content when updating, exact approved
  replacement text/assets and approving-message evidence,
  browser lease owner, actual editor identity, save/reopen results and limitations.
- Measurements: source/time/period/definition/denominator and availability state.
  Keep personal identifiers and private reader messages to the minimum needed.

## Draft lifecycle

`proposed -> content-accepted -> save-approved -> editing -> saved -> verified`

Record `blocked` or `save-uncertain` whenever appropriate; they are not success.
These labels record evidence, never create authority. A hash binds content, not
approver identity. Preserve the original approving user message or explicit
relay and its scope; model-generated approval text is not consent.

Before editor entry retain the exact input snapshot/identity and acquire the
profile-wide [browser lease](../scripts/browser-lease.py). During a save retain
the service-assigned identity as soon as it exists. On resume inspect the
retained target and current contents; never restart creation just because the
previous tool call timed out. Human changes need reconciliation and renewed
approval, not overwrite. Do not release another job's lease or expire one by age.

Old v6 Publish/P1 grants and pending posting jobs are not adopted by this
draft-only pipeline. Keep historical records/output bytes unchanged; explicitly
reconcile and release a new draft unit. A user's later publication is recorded
only after observing the actual result, not inferred from approving the draft.

Task state is not MEMORY.md. Persist reusable general lessons only through the
normal learned-skill policy, with conditions and no private data; never promote
an unverified pattern into a new mandatory marketing rule.
