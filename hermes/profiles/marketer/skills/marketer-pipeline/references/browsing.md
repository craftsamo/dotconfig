# Read-only browsing

Marketer's browser is the existing dedicated Marketer profile, logged in to
the user's accounts. It reads what no tool reaches: a service dashboard, an
authenticated page, a script-heavy public page. It never writes. Prefer a tool
whenever one answers the question (`x`, `substack`, `youtube`, `note`, web
extract); they need neither the browser nor the lease.

The browser runs only in a resident conversation; an inbound A2A inquiry has
no browser and asks the client to reissue the unit as resident work.

## What the browser may do

Navigate, scroll, read the page, take screenshots and expand read-only views
(a stats period, a post's details). Nothing that changes state on a service:

- never type into an editor or composer, never create or open a new draft
  (opening some editors creates one), never save, upload or import;
- never click post, publish, schedule, send, reply, quote, repost, like,
  follow, subscribe, comment, react or DM;
- never change a setting, visibility, audience, paid option or sharing scope,
  and never generate a sharing or preview link;
- never submit a form, accept a dialog that commits something, or click an
  ambiguous forward/confirmation button to see what happens.

A page that needs any of these to show what you came for stops the read:
report what you saw and what stays uninspected. Authentication challenges go
to the user; never bypass a login, CAPTCHA or two-step check.

## The lease

All navigation, including public pages, holds the profile-wide lease, which
serializes Marketer's resident conversations in the one browser. Resolve the
actual Marketer profile home and a stable owner token from the originating
session and job identity; retain the token across resumes. Resolve the
script's absolute path from the marketer-pipeline skill_view result and the
home from the actual profile-scoped runtime. Replace the quoted placeholders
below with those literal paths/identity; do not assume skill template
variables are exported in the terminal or that the multiplex process
environment is scoped:

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
browser sandbox, and holding it grants no authority to change anything.

Use the existing `browser_exec` route. Reuse the named browser session and
task identity, but do not assume Python variables or the active tab persist
across exec calls: retain the owned tab's target identity and reselect it
before each action. Never navigate a different session's tab, attach to the
Assistant's browser or create another profile.

When the reading is done, release only this job's lease:

```sh
python3 "<marketer-pipeline-directory>/scripts/browser-lease.py" release --home "<profile-home>" --owner "<session-job-id>"
```

If the original session cannot resume, ask the user or maintainer to confirm
no operation is in flight before a recovery release with the retained token;
that is an explicit recovery, never permission for another job to steal it.

## If something changed anyway

An unexpected state change (a draft created by opening a page, a click that
liked or followed, a dialog that sent something) is an incident: stop, keep
the lease, record what you know and report it to the client and the user.
Never undo it silently, delete anything or retry.
