# Browser

How browser tools attach to a real, signed-in Brave profile through a cloned
bundle, and the invariants that keep logins from being invalidated. Read it
before touching `browser.*` config, the Brave clone, or anything that relaunches
a browser.

Part of the Hermes mechanics docs — entry: [`README.md`](../../README.md).

## Browser

The real-profile path depends on local hermes-agent patches; run
`scripts/check-local-patches.sh` after every `hermes update` (a missing patch
fails silently at runtime, e.g. browser isolation).

**Routing and precedence.** With `browser.backend` unset and `uvx` present,
`browser_exec` → `uvx browser-use` → `browser_harness` attaches over CDP to the
endpoint Hermes resolves; the built-in `browser_navigate` surface and the
`browser.engine` / `camofox` keys describe the dormant path. A `BU_CDP_URL` /
`BU_CDP_WS` in the **process env** wins over everything, silently — it is copied raw from `os.environ`, so under
multiplex one value pre-empts real-profile browsing for every profile. Never add
either key to a Keychain layer the gateway launcher evals (`global`, `hermes`).
See also [marketer.md](../profiles/marketer.md) "Browser lease".

**Real-profile pins.** Only profiles that need the owner's logins set
`browser.use_real_profile: true`, `real_profile_pin:` (a Brave profile
**directory** — the `Local State → profile.info_cache` key, not the display
name) and `real_profile_binary:` (the clone, `scripts/brave-agent-sync.sh
path`). Everyone else gets upstream's on-demand packaged Chromium in a throwaway
profile. To sign an agent in, log in to services in its pinned profile in the
everyday Brave; cookies/logins are merged into the profile's ignored
`browser-profile/brave/` on every cold clone launch. There is no separate
headful login step.

- **One Brave profile per consenting Hermes profile, never shared** — Google
  rotates its session cookies and treats an older value as a stolen session, so
  every client sharing one Google login signs the others out.
- **The owner must not browse in a pinned profile** — the owner is one more
  client of the same rotation. Log in, close, work elsewhere; "log in again" in
  the everyday Brave just supersedes the clone's session and moves the sign-out.
- **Preconditions fail closed:** the macOS default browser must be Brave, the
  pinned profile directory must exist, and the clone binary must be executable.

**Why a cloned bundle.** macOS treats one app bundle as one running app, so while
a headless Brave launched from `/Applications/Brave Browser.app` is alive, the
everyday Brave cannot open. An APFS clone (`cp -Rc`) at another path has no
shared identity, and its untouched signature still satisfies the Keychain
`Brave Safe Storage` ACL (bundle id + team, not path), so cookies decrypt
without a prompt. The clone lives in the ignored
`local/brave-agent/Brave Agent.app`; the gateway launcher runs
`scripts/brave-agent-sync.sh sync` before every start to re-clone on version
drift. **Never edit the clone** — any change breaks the signature and with it
cookie decryption; re-clone instead. `browser.real_profile_binary` is honored
only through a local patch; without it the real bundle launches and the Dock
clash returns.

**Clone lifetime.** The clone starts with `--remote-debugging-port=0` and lives
until the Hermes process that launched it exits (only the atexit hook reaps it),
so one headless Brave stays resident per profile that has browsed.
Each Hermes home gets its own attach daemon (`hermes-real-profile-<profile>`),
and CDP calls use an owned daemon runtime scoped by profile + logical
session/task whose binding and browser UUID are verified before code runs (local
patches). Owned-daemon idle cleanup is opportunistic and never refreshes cookies.

**Cookies mirror only on a cold launch.** `_mirror_profile_auth` runs only on the
cold path of `_real_profile_cdp`; a gateway restart re-attaches to the surviving
clone and mirrors nothing. To pick up a fresh login, **relaunch the clone, not
the gateway**. The cookie store is merged row by row, newest `last_update_utc`
wins, so a relaunch keeps the clone's freshly rotated tokens (local patch;
schema drift falls back to overwrite). Deletions do not
propagate: a sign-out in the everyday Brave leaves the clone signed in.

**Stop the clone and its daemon together.** Upstream closes the daemon session
only when `get cdp-url` succeeds, so a daemon that outlived a killed clone keeps
the dead port, ignores the next launch's `--cdp`, and every call fails with
`All CDP discovery methods failed` until the gateway restarts. The
private-overlay skill `hermes-browser-relaunch` (`scripts/relaunch.sh`) does it
right: SIGTERM clone → stop daemon → clear socket dir; it never launches — the
next `browser_exec` does. Each of Assistant and Marketer relaunches only its own
pair (Marketer while holding its browser lease). Do not use the old generic
`bu-default` kill workaround. Debugging traps: `Browser.getVersion` reports
`Chrome/…` on Brave, so check the process, not the product string; the daemon
resolves the npx-cache `agent-browser` ahead of the mise shim, so the one on
`PATH` may not be the one running.

**UA gate pages are not a relaunch case.** Sites gating on the UA string reject
headless `HeadlessChrome/<v>`, so the headless launch passes `--user-agent` with
the binary's major version (local patch; headed is untouched). An "update your
browser / unsupported browser" page is a UA gate — never a relaunch case and
never evidence that the owner's login expired.

**Session-restore purge.** The long-lived copy directory would let Chromium's
session restore replay old tabs into every new clone until the browser wedges;
`_launch_real_profile_chrome` purges `<profile>/Sessions` before launch and
`Sessions` is in `_SNAPSHOT_IGNORES` (local patch). Tab growth is launcher state — never fix it
with prompt-side rules. Rising `pages=` / `rss=` in `relaunch.sh --status` means
the purge went missing.

**IndexedDB-backed logins.** The snapshot excludes `IndexedDB` (it wedges a fresh
renderer) and only auth DBs re-sync per launch, so a site that keeps its session
there (WhatsApp Web) arrives signed out even when the everyday Brave is signed
in. Such a site needs its own login **in the clone** (WhatsApp: pair it as a
separate linked device); that persists across relaunches but not across a
snapshot rebuild or `use_real_profile` going off. **Never copy IndexedDB across
profiles** — for WhatsApp that shares one linked-device identity between two
clients, the same failure as a shared Google session.

The worker-facing rule (spawn your own browser with port 0, never attach to
Hermes' instance) lives in `~/Workspaces/AGENTS.md` (private overlay).
