# Service-side browser draft

This procedure creates or updates an unpublished draft in the selected service.
Read [state](../../references/state.md), [content QA](../../qa-marketer/references/content.md) and the
selected [platform reference](../../plan-marketer/references/channels.md). A local file is an input,
not the requested final draft. Do not substitute xurl/API publishing.

## Before writing to an editor

Resolve the actual Marketer profile home and stable originating session/job
identity from the runtime. Do not guess another profile's home. Make a unique
owner token from that session and job and retain it across resumes. Acquire the
profile-wide lease before ANY browser action, including read-only navigation.
Resolve the script's absolute path from the marketer-pipeline skill_view result and the home
from the actual profile-scoped runtime. Replace the quoted placeholders below
with those literal paths/identity; do not assume skill template variables are
exported in the terminal or that the multiplex process environment is scoped:

```sh
python3 "<marketer-pipeline-directory>/scripts/browser-lease.py" acquire --home "<profile-home>" --owner "<session-job-id>"
```

The helper rejects a home not shaped as the resolved profiles/marketer directory;
do not default to the neutral profile or use the config checkout as runtime home.
Exit 3 means another job holds the lease: wait/report;
exit 5 means untrusted state: stop for investigation. No timeout-based stealing.
Any nonzero acquire exit means do not proceed to the browser, including a
missing script, invalid arguments or an unreadable profile home.
The lease coordinates cooperating sessions; it is not authentication or a
browser sandbox. A holding token grants no upload or editing authority.

1. Read the exact source and approved assets. Record immutable input snapshots
   or hashes and the user's intended destination, account and content type.
2. Distinguish `create` from `update`. For update record the existing private
   editor locator/identity and current draft contents before replacement. Never
   overwrite concurrent human changes. Published or scheduled targets are out
   of scope, even if their editor is reachable.
3. Obtain explicit approval of the exact content/assets, named service/account,
   operation and existing target for updates. Update approval also binds the
   expected current remote draft revision/content, not only replacement text.
   If that baseline is unavailable, inspect without editing and obtain approval
   of the observed baseline before replacement. Record the actual approving message
   or explicitly relayed user approval, not the model's own summary as consent.
   Approval must precede typing/upload: autosave can transmit immediately.
   Approval of an outline or local manuscript alone is not remote-save consent.

## Operate and reconcile

4. Use the existing `browser_exec` browser route. Verify the visible account and
   destination before entry; open the service's current editor and inspect its
   actual controls. No new browser profile, cookie copying, extra CDP browser,
   login bypass, CAPTCHA solving or attachment to Assistant's browser.
   Reuse the named browser session and task identity, but do not assume Python
   variables or the active tab persist across exec calls. Retain the owned tab's
   target identity and explicitly reselect/verify it before subsequent actions.
   If it disappeared, reconcile the browser and service draft before recovery;
   never navigate a different session's active editor as a fallback. Opening a
   new editor can itself create a remote draft, so creation consent precedes it.
5. Enter approved text and media only. Mechanical representation may change
   markup, never meaning, wording, URLs or qualifications. Read back headings,
   code, links and attachment mapping as appropriate. Return necessary wording
   changes to Writer rather than editing them in the browser.
6. Save by the platform's verified draft action or wait for autosave completion.
   Never activate publish, schedule, send/test-send, public/secret sharing or
   a visibility change. Do not click an ambiguous forward/confirmation button
   to discover what happens. Record the identified draft as soon as available.
7. Reopen the SAME draft from service management and run
   [saved-draft QA](../../qa-marketer/references/saved-draft.md). A saved indicator,
   screenshot of typed text, guessed URL or HTTP success alone is insufficient.

On interruption, record known effects and `save-uncertain`; retain the lease
until the editing surface and side effects have been reconciled. Search the
service's draft list for the known identity before ever creating a new draft.
If identity is ambiguous, report and ask; never insert an unapproved visible
tracking marker into the manuscript to make retries easier.

After a verified save, or an explicitly reconciled stop with no pending editor
operation, release only this job's lease:

```sh
python3 "<marketer-pipeline-directory>/scripts/browser-lease.py" release --home "<profile-home>" --owner "<session-job-id>"
```

If the original session cannot resume, ask the user/maintainer to reconcile its
retained job record and current browser state. Only after confirming no operation
is in flight and recording the unresolved draft identity/effects may that recovery
release use the retained original owner token. This is an explicit recovery,
not permission for another job to steal a lease. Preserve the uncertain draft;
if safe suspension cannot be established, keep the lock and report the blocker.

Do not discard, delete or revert a draft as cleanup without explicit instruction.
An unexpected publication/send is an incident: stop, report known URL/effects,
retain evidence and ask; never silently delete, resend or repair it.
