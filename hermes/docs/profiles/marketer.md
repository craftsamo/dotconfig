# Marketer

Marketer strategy and browser drafts. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Marketer strategy and browser drafts

Marketer owns strategy and its existing authenticated browser; there is no
SNS-Marketer profile or hand, and login profiles are never shared or copied.
Marketer v8 keeps `marketer-pipeline` as its invariant kernel and exposes four
independent entry skills beneath that directory, outside `references/`:
`plan-marketer`, `build-marketer`, `qa-marketer` and `analyze-marketer`.
Each entry's `SKILL.md` owns its mode procedure and lists its local details.
Plan holds discovery,
positioning, offer, channels and campaign decisions; Build commissions parts,
operates service drafts and collects measurements; QA separately checks strategy,
content and saved objects; Analyze interprets results. One shared
`references/platforms/{x,substack,note,zenn}.md` owns each platform's constraints,
browser procedure and verification. `references/state.md` defines records;
actual project/account/evidence/approval data remains private and outside config.
Detailed references remain references, not a hands taxonomy or generated registry.
Shared state/platform paths and `scripts/browser-lease.py` stay at the parent;
Writer acceptance stays at its canonical location (see [writer.md](./writer.md)
"Writer craft and independent editorial QA"). No new external skill roots, and
no other profile's skill menu is expanded.

Loading follows the shared [entry loading contract](../topology.md#entry-loading-contract);
Marketer's deltas: each mode/target/platform/scope-changing action reselects the
entry; the entry itself is the complete mode procedure, with no second common
index. Cross-entry detail reads require their owning entry. Instruction reads may
run in parallel rather than as a serial loading ritual, but ordinary instruction
reads never authorize browser navigation, and browser reads still need the
lease. A short approval resumes recorded work rather than granting a new plan,
save or producer run.

This is a Hermes-specific skill family, not five portable packages: the generic
skill-authoring validator's rejection of nested roots and cross-entry links is
expected. The repository validator (`validate_marketer_references`) instead
requires every resolved link to stay inside `marketer-pipeline` and name a real
file, with each owner linking its own references; it checks the exact
entry/reference sets, kernel dependencies, canonical recovery and the absence of
card units. Hermes metadata remains canonical.

Assistant's old marketing leaves remain thin client pointers so other caller
references still resolve. Marketer owns strategy and its record, including
direct-human intake without a pre-existing offer/ledger. User decisions remain
separate from evidence; a proposal can explicitly be exploratory. Existing state
files retain their bytes/ownership and need no schema conversion.

### Browser lease

Browser operations use Marketer's existing dedicated Brave profile; no cookie
sharing or migration. All browser navigation, including measurement reads, holds
the profile-wide `scripts/browser-lease.py` lease, which serializes cooperating
jobs across tool calls. It refuses another owner, corrupt state and symlinks, and
has no TTL: it never expires or steals a lease. The owner holds it through
saving and reopening, until a verified or reconciled stop. This is coordination,
not a browser sandbox or authentication; broad terminal/browser tools remain a
residual authority risk. Marketer's inbound A2A has no browser, terminal or
delegation toolset, so authenticated work needs a resident session.

### Draft-only saving

There is no publish path. Before typing or upload — i.e. before editor entry —
obtain approval of the exact text/assets, destination account and create/update
target; autosave is already a remote write. No publication, scheduling,
email/test-email, visibility change or shared-preview link generation. Service
draft completion requires reopening the same object and checking content,
attachments and unpublished state; local files and input screenshots alone do
not complete the request. Challenges and ambiguous saves stop for
reconciliation; unknown effects are never retried automatically. Known
automation risk may be accepted by the user but is not platform permission. Old
Publish/P1 grants and v6 publishing sessions are not adopted; reconcile
unfinished old work before a new draft-only release. The user publishes.

### Validation status

The four platform procedures are authored; each service/content type requires
approved, nonpublishing live validation, since static tests never establish
service-side persistence. Verified so far: a note text-only new-draft save with
unpublished-view reopening, plus constrained fresh-candidate-agent runs (a
read-only recheck and a no-typing resave of an existing note fixture) with
allowlisted browser programs. Free-form interaction, gateway deployment, other
platforms, attachments, arbitrary updates/new content and existing-user-draft
updates remain unverified.

The candidate checks `test_marketer_pipeline.py`, `test_marketer_entry_runtime.py`
and `test_marketer_browser_lease.py` are registered in `verify-work-continuity.py`.
The runtime test copies only candidate Markdown into an isolated HOME with actual
Hermes tools and no network, providers, model or browser execution: it tests real
discovery/reads/dedup, not model routing or service-side saves. Cutover follows
[topology](../topology.md) "Candidate rollout and cutover"; it needs caller
coverage and real skill discovery first, and rollback restores the matched
caller/producer contracts, not saved drafts or user data.
