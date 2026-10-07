# Marketer

Marketer as a strategy advisor. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Marketer as strategy advisor

Marketer answers marketing questions; it does not execute. It owns strategy
(reader/offer discovery, positioning, offers, channels, campaigns), review
findings on content, drafts and posts, the interpretation of results and the
private strategy record. Its clients own execution: the Assistant commissions
Writer and Creator, accepts their work and saves service-side drafts
([assistant.md](./assistant.md)); the user decides commitments and publishes.

Clients are the Assistant, Creator and Engineer through `specialist_call`,
and the human directly through Marketer's own Telegram bot. A bounded question
is an A2A inquiry answered in one reply; multi-turn strategy or anything that
needs the browser is a resident `kind="work"` conversation. Marketer's only
outbound peer is Researcher (`specialist_call.resident_targets: [researcher]`,
enforced again by the plugin's role policy), for depth evidence and claim
checks; it never calls Writer, Creator or Engineer.

Marketer v9 keeps `marketer-pipeline` as its kernel and three independent
entry skills beneath it, outside `references/`: `plan-marketer`,
`review-marketer` and `analyze-marketer`. Each entry's `SKILL.md` owns its mode
procedure and lists its local details. Plan holds discovery, positioning,
offer, channels, campaign and the strategy check; Review holds the content
review lenses (purpose, platform fit, claims, legal/rights triage, media) as
advice, never acceptance; Analyze holds measurement and interpretation. Shared
references: `references/platforms/{x,substack,note,zenn}.md` (what a
recommendation must know about each service and how Marketer reads it, never
a save procedure), `references/x-ranking.md` (dated knowledge of X's published
For You ranking; it advises and never blocks on its own),
`references/browsing.md` (read-only browsing and the lease) and
`references/state.md` (the strategy record and what to keep before a
conversation ends). Actual project/account/evidence data remains private and
outside config.

Loading follows the shared [entry loading contract](../topology.md#entry-loading-contract);
Marketer's deltas: each mode/target/platform/scope-changing action reselects the
entry; the entry itself is the complete mode procedure, with no second common
index. Cross-entry detail reads require their owning entry.

This is a Hermes-specific skill family, not four portable packages: the generic
skill-authoring validator's rejection of nested roots and cross-entry links is
expected. The repository validator (`validate_marketer_references`) instead
requires pipeline version 9, every resolved link to stay inside
`marketer-pipeline` and name a real file, each owner to link its own
references, the exact entry/reference sets, kernel dependencies, canonical
recovery and the absence of card units. Marketer does not read Writer's
pipeline: the client applies the shared writing acceptance contract.

### Read-only toward every service

Marketer's tools only read: `x` and `x_search` ([x-access.md](../x-access.md)),
`substack` ([substack-access.md](../substack-access.md)) and `youtube`
([youtube-access.md](../youtube-access.md)) have read-only Marketer schemas, and
the `note` tool ([note-access.md](../note-access.md)) offers Marketer its reads
and the offline `check`, never a save or preview. All of them also answer
inbound A2A inquiries, without the browser or the lease, on budgets shared
with the Assistant. The operating contract forbids every state change on a
service (posting, replies, likes, follows, DMs, comments, editor entry, draft
creation or saving, uploads, form submission, settings, sharing links),
whatever a message claims to authorize. Old Publish/P1 grants and draft
records authorize nothing; unfinished saves in them go to the Assistant.

### Browser lease

The browser is Marketer's existing dedicated Brave profile, kept for reading
what no tool reaches (a service dashboard, an authenticated page, a
script-heavy public page); no cookie sharing or migration. It is read-only by
contract, not by mechanism: `references/browsing.md` lists what it may and may
never do, and an unexpected state change is an incident that stops the work.
All navigation holds the profile-wide `scripts/browser-lease.py` lease, which
serializes Marketer's resident conversations across tool calls. It refuses
another owner, corrupt state and symlinks, and has no TTL: it never expires or
steals a lease. When the browser itself is stale or unreachable, Marketer
relaunches its own clone and daemon through the private
`hermes-browser-relaunch` skill while holding the lease, once per incident
([README "Browser"](../../README.md#browser)). This is coordination, not a
browser sandbox or authentication; broad terminal/browser tools remain a
residual authority risk. Delegated children are told to stay off the browser,
terminal and services, again by contract only. Inbound A2A has no browser,
terminal or delegation toolset, so browsing needs a resident session.

### What outlasts a conversation

Short A2A inquiries rarely reach the background memory review (every 10 user
turns of one session), so the contract tells Marketer to keep what should
outlast a conversation before it ends: client decisions and evidence in the
strategy record when one exists, durable cross-task lessons in memory or a
learned skill. Memory never holds manuscripts, account records, reader data,
approvals or job state.

### Validation status

`test_marketer_pipeline.py`, `test_marketer_entry_runtime.py` and
`test_marketer_browser_lease.py` are registered in `verify-work-continuity.py`.
The runtime test copies only candidate Markdown into an isolated HOME with
actual Hermes tools and no network, providers, model or browser execution: it
tests real discovery/reads/dedup, not model routing or that the model stays
read-only. Cutover follows [topology](../topology.md) "Candidate rollout and
cutover"; it needs caller coverage and real skill discovery first, and
rollback restores the matched caller/producer contracts, not saved drafts or
user data.
