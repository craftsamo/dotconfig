# Access plugins — common contract

What the access plugins have in common: Discord, Telegram, WhatsApp, Signal,
Google, GitHub, Git, X, note, Substack, YouTube, Stripe and Cloudflare. Each
`*-access` doc inherits this one and records only its own differences; read it
first when changing or adding an
access plugin. Web3 follows the same approval and bypass-guard rules in its own
doc ([web3.md](web3.md)). Two kinds of write skip their card only inside a
mandate the user approved on a card of its own: a Hyperliquid order
([hyperliquid.md](hyperliquid.md)) and a
gcloud command ([google-access.md](google-access.md#gcloud-mandates)).
Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

## Risk acceptance

Most of these plugins reach their service through an unofficial client, an
undocumented web endpoint or a browser session's cookies, which the service's
terms forbid or do not cover; the account can be limited or suspended at any
time. The user accepted that risk per service (each doc says what it is), so
the designs stay low-volume and client-like — paced requests, no read receipts
— rather than pretending the risk away. Google's, YouTube's, Stripe's and
Cloudflare's own APIs are the exception.

## Secret scoping

Hermes receives only shared secret layers: `profile-secrets.sh` and the
tool-mode `secret-shim` pin `--scope <project>`, because without it `secret
env` adds the scope named after the working directory's repository. A
credential kept in the `hermes` keychain sits under a scope of its own (each
doc names the item and scope; WhatsApp, Signal, Telegram and Discord keep
their sessions in the engine's own store instead), so it never enters any profile's secret scope or a
CLI session, and the engine reads it only when it needs it. Cloudflare's tokens are the exception: the
package reads them from the gateway's process environment
([cloudflare-tools.md](cloudflare-tools.md#tokens)). The engine reads them when it
needs them and never prints or logs them; replacing one needs no gateway
restart. Short rule: [AGENTS.md](../AGENTS.md) "Secrets, auth and accounts".

## State directory and bridge process

State lives outside every repository and is private (mode 700). The cookie
services (X, note, Substack) keep pacing timestamps, caps, locks and
the service's last verdict in `~/.<name>-access/`, with no secret; Stripe
keeps its key's last verdict there the same way. The
messaging plugins keep their mirror and outbox under
`~/.local/state/hermes-<name>/` (their docs say what else).

- **Refusal memory.** When the service refuses the session (expired, logged
  out, locked), the refusal is stored with a fingerprint of the cookie (12 hex
  characters of a SHA-256) and every later call is answered without contacting
  the service until the stored cookie changes. A rate limit stores its end and
  calls wait for it. Fresh cookies need nothing else reset.
- **Bridge process.** The code that holds a credential runs as a child process
  with a minimal environment (`HOME`, `PATH`, `LANG`, none of the gateway's
  keys), so the gateway's own Python does not hold the key or import the
  client. Google's and YouTube's API calls are the exception: they use Google's
  client libraries in Hermes' own Python, and keep access tokens in memory (their
  docs say how). Where there is a venv it is hash-locked under `~/.hermes/local/<name>/venv`
  and never Hermes' interpreter; note's and Stripe's bridges are
  stdlib only and run under Hermes' interpreter in isolated mode (`-I`).

## Profile gating

The action list a profile gets is fixed when the plugin registers and checked
again by the gate, the handler and the engine, so naming an action outside it
is refused even though the tool is the same. Inbound A2A never reaches the
Assistant's account or write tools (the toolset is not in its `a2a` platform
toolset); a profile that answers a peer reads only when the turn's bound
profile home is its own, failing closed otherwise.

## Approval gate

A change that gets a card goes through Hermes' own gate
(`request_tool_approval`): the inline card on Telegram, a prompt in the CLI.
Denial, silence, a gate error and contexts without a human all mean nothing
was changed.

- **It runs only where a person can answer the card.** Hermes approves a
  plugin's card unasked under `--yolo`, `approvals.mode: off` and `hermes -z`
  (which switches YOLO on), and consults stored "always" approvals before its
  cron rule. So the plugin refuses itself in those modes, in cron, in
  single-query runs, on unattended platforms (`webhook`, `msgraph_webhook`,
  `api_server`) and wherever no interactive terminal, gateway or ask bridge
  exists. Google, note and Stripe use the shared check
  `plugins/_shared/human_gate.py` (`no_human`), which fails closed when
  Hermes' approval context cannot be read, and so does the guard of the
  third-party Signal, Telegram, Discord, WhatsApp, GitHub, Git and Cloudflare packages
  ([signal-tools.md](signal-tools.md), [telegram-tools.md](telegram-tools.md),
  [discord-tools.md](discord-tools.md), [whatsapp-tools.md](whatsapp-tools.md),
  [github-tools.md](github-tools.md),
  [git-tools.md](git-tools.md), [cloudflare-tools.md](cloudflare-tools.md)); Substack and YouTube refuse through
  their own `_unattended()` and `is_approval_bypass_active()`. A write
  inside a mandate (Hyperliquid, a gcloud command) has no card to answer and runs also unattended; the mandate's bounds, checked at the
  write, take the card's place. A mandate is stored by the one shared store
  (`plugins/_shared/mandate_store.py`) and its MAC key is a Keychain item under a
  scope of the plugin's own, which no profile receives.
- **Hook and handler both refuse**, so a write never depends on the hook
  having run; the hook refuses before any card, snapshot or file copy is
  built. The refusal says nothing was sent or changed. Reads are unaffected.
  Signal, Telegram, Discord, WhatsApp, GitHub, Git and Cloudflare are the exceptions: their package handlers
  are not ours, so only the guards' hooks refuse, and the profile validator refuses a
  config that enables a package without its guard.
- **A card must outlast a tap.** The Assistant keeps `approvals.timeout` at
  600 s so a card stays answerable on Telegram.
- **Every card has one shape** ([below](#card-shape)), so the user reads
  them all alike. Names and quotes are collapsed to one line and control,
  bidi-override and invisible characters are spelled out (`⟨U+202E⟩`), so other
  people's words cannot forge card lines. Long text is cut on the card with the
  rest counted, never refused; its full wording is agreed with the user in chat
  first.
- **The key binds the exact request, unless the action has a standing rule.**
  The allowlist key hashes the request (and each file's content), so "session"
  or "always" only repeats that identical one. `plugins/_shared/approval_tier.py`
  holds the exceptions: an action whose rule is `standing` gets a key bound to
  its target (a spreadsheet, a video, an account) when the card's own level is
  one the rule lists, ✅ unless it says otherwise, so one answer covers the
  later calls to that target. A card at any other level keeps the exact key.
  `scripts/tests/test_approval_tiers.py` pins the table
  ([decision](decisions/approval-tiers.md)).
- **Outcomes are never guessed, and a write is never retried.** A refusal
  known to happen before anything left reads `not sent` / `not done`; an
  ambiguous one reads `UNCERTAIN` and the Assistant checks with the user before
  any resend.

To try a write, ask the Assistant in a chat where its card reaches the user;
`hermes -z` can check reads, never a write.

### Card shape

Hermes shows a card as the reason on its own prompt, right after "Why it was
flagged: " and before the deadline line, as plain text (Telegram escapes
markup). So a card has only lines to read by, and every one is laid out alike:

```
Signal · Send message            title: service · action, never "Label: value"
⚠️ They see it at once           what is at stake, one line with its marker
Account: +81…                    one fact a line
Chat: Alice (+81…)

--- Files (1, 1.2 KB) ---        a block per list, its heading counting it
- photo.png (image/png, 1.2 KB) in trip, sha256 1a2b3c4d5e6f

--- Text ---                     the free text last, under a heading that
see you                          names it (Text, Caption, Message…)
```

The marker means the same on every card, web3's included:

| Marker | When                                                                                                                                                                                |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ✅     | it stays the user's or can be undone: a draft, an own private target, an own wallet, a reduce-only order                                                                            |
| ⚠️     | it reaches or shows to others, or replaces what is there, and can still be dealt with afterwards: a message, a comment, a replaced draft, someone else's repository, added exposure |
| 🚨     | it cannot be undone or leaves the user's hands: a delete, publishing that cannot be taken back (an emailed post), funds leaving, a ban, an admin change, a mandate                  |

A card fits what the chat shows of a reason: 480 escaped UTF-16 units on
Telegram and the CLI, 290 on Discord (Hermes cuts at 500 and 300). The
patched runtime gives the reason the room its short command leaves, most of
the message, so there a card may take 3500 units on Telegram and 1200 on
Discord (room kept for its approval mentions); `card.py` reads that from the gateway it runs in, and a runtime
without the patch keeps the short budgets. Facts the
card marks as context go first when it is short of room, then the free text is
cut with the rest counted (on Discord's shorter card the facts keep their room
first, so less of the text shows); a card whose facts still do not fit is
refused, never shown cut. `plugins/_shared/card.py` builds this shape for the
access plugins, and the Hyperliquid trader builds its own cards in it
([hyperliquid.md](hyperliquid.md)). Two cards keep a shape of their own: a
wallet transfer on EVM or Solana, built and signed in the web3 engine
([web3.md](web3.md)), and a Sheets edit, cell by cell
([google-access.md](google-access.md)).

## Chat files and archives

Telegram, WhatsApp and Discord take files someone sent and send the user's
files under the same rules. Each plugin's module holds its own lists and
passes them to the shared code (`plugins/messaging/_shared/archive_check.py`,
which is not a plugin and has no manifest); each doc records only its
differences. The Signal package keeps rules of its own
([signal-tools.md](signal-tools.md)); its guard runs the same unpacked guard.

- **Received files.** Programs are refused by name, declared type and sniffed
  content, and so are archive formats that cannot be inspected. Every saved
  file carries the macOS quarantine flag, so macOS asks before it opens an
  application or script from it.
- **Received archives.** A `.zip`, `.tar`, `.tar.gz`/`.tgz`, `.tar.bz2` or
  `.tar.xz` is saved only after the shared inspection (`vet_received`) passes
  on the downloaded copy: no program, installer, other archive, link,
  encrypted entry or escaping path, within the entry and size caps. Unlike a
  send, key and secret names and private key blocks are not refused (nothing
  here can leak), and source scripts are allowed: they do nothing until
  someone runs them. The listed file names are the sender's words, so they are
  cleaned of control, bidi and invisible characters and the result's note says
  they are data. A name that says zip or tar over other content, `.rar`, `.7z`
  and the like are refused, and the file is deleted.
- **Unpacking** (`unpack`, and `entries` for only some of the names or
  folders). The plugin unpacks the archive itself (`extract`), never a system
  tool, into `<name>.unpacked/` next to it. The saved archive is copied to a
  private folder and inspected again there, and the entries are written from
  that same copy, so nothing can change between the check and the unpacking.
  Each file is created below the new folder through descriptors that follow no
  link and overwrite nothing, with mode 0644 (the sender's execute bit is
  dropped) and the quarantine flag. Any failure removes everything written and
  leaves the archive saved. The unpacked files are for reading as data and for
  analysis with the Assistant's own scripts, kept outside the folder.
- **Never run what was received.** Each plugin's hook blocks a terminal call
  that would run a file inside a `*.unpacked` folder (an interpreter or a path
  as the command, `source`, `open`, `chmod`, `xattr` changing the quarantine
  flag, build and package tools, `find -exec` and `xargs`). Reading (`cat`,
  `head`, `grep`, `jq`, `file`, `ls`, `cp` out) and `python analyze.py
<folder>/data.csv` are not blocked: the script that runs is the
  Assistant's, and the data is only read. It is a pattern match on the call's
  text, not a sandbox; a file copied out of the folder, a script that loads a
  file inside it (`pickle`, an unsafe `yaml` load, a notebook, a macro) or a
  changed working directory kept from an earlier call are not seen. The
  execute bit, the quarantine flag and the Assistant's own rules are the other
  layers.
- **Files sent** come only from `~/Workspaces`, judged by real path, so a link
  that leads out counts as outside. Refused always: paths through key or
  settings folders, key- and secret-like names, installers and programs (by
  name and by sniffed type), archives other than the ones below, anything
  containing a private key block anywhere in the file, empty files. **Source
  scripts** are sent like any other file if the sniffed type says script or
  plain text too: a `run.sh` that is really a binary is refused. A bundle or
  shortcut (`.app`, `.command`, `.lnk`) is not a script.
- **Archives sent** (`.zip`, `.tar` and its compressed forms) are read, never
  unpacked to disk. The first bytes must match the extension, so a ZIP named
  `photo.jpg` stays refused as an archive by content. Every entry is held to
  the sender's rules for a single file, plus a plain relative name (no `..`,
  absolute or backslash path), a regular file or folder (no links, devices or
  pipes), not another archive, not encrypted. Source scripts are allowed
  inside an archive as they are alone: each sender passes `allow_scripts`, and
  `SCRIPT_FILES` / `SCRIPT_MIME` in the module say what counts as a script, so
  the plugins agree. Entry count and unpacked size are capped, counted from the
  bytes actually read rather than the sizes the archive claims. One bad entry
  refuses the whole archive and the message names it. Formats the standard
  library cannot read (`.rar`, `.7z`, a bare `.gz`) and ZIP-based programs
  (`.jar`, `.apk`, `.ipa`) stay refused; Office files are not archives here.
  A file that changes while the send is prepared, the inspection included, is
  refused.

## Bypass guard (Ways around the tool)

A `pre_tool_call` hook blocks terminal calls and file-tool calls whose text
names the plugin's engine, state, credentials, client libraries or raw API.
Terminal calls naming the plugin itself are blocked too, since importing the
engine would skip the hook; file tools may still read the plugin source. It is
a pattern match on the call's text, not a sandbox: the approval gate is a
guarantee for the tool and a policy for everything else. The patterns live in
each plugin's module (named in its doc); never copy them into docs.

The third-party git package's guard also restricts terminal git and protects
its installed directory, including real paths and profile copies; its scope
and limits are in [git-tools.md](git-tools.md).

A CLI the plugin owns (`gcloud`, `wrangler`, `stripe`, `signal-cli`, `wacli`)
counts where a command runs it: `plugins/_shared/shell_commands.py` reads the
line as a shell would (quotes, separators, substitutions, `bash -c`, `eval`,
`trap`, wrappers such as `env` or `sudo`, package runners such as `npx` and
`pnpm exec`). A mention passes as an argument of a command known to treat its
arguments as data (`grep -n 'gcloud auth' scripts/deploy.sh`, `sed`, `cat`,
`echo`, `git log`), so reading a project's scripts and docs is never a way
around. The plugin's strict pattern judges the whole line instead when
another command names a CLI in its arguments (`ssh host gcloud`, an inline
`python -c`), or when the reader cannot follow the line (a here-document, a
command name from an expansion, a shell or interpreter reading its code from
input).

In a project, the Google, Cloudflare and Stripe guards also let the project
run its own tooling. A project is a Git repository under `~/ghq` or
`~/Worktrees` that the call names as its working directory (`workdir`, or a
leading `cd <absolute path> &&`); Hermes' own configuration (this checkout,
the private overlay and their worktrees) never is one, since its scripts
change Hermes itself. There the project's entry points and scripts (`nps`,
`make`, `./scripts/…`, `node scripts/…`) are not unknown commands, and a CLI
the plugin lists as a project dependency runs through the project's package
manager when the project has it in `node_modules/.bin` (`pnpm exec wrangler
deploy`), never as a download (`dlx`, `npx -y`). The CLI run directly, or
named in an entry point's arguments, is judged as anywhere else. What the
project's tooling runs uses the user's own CLI logins (`~/.config/gcloud`,
wrangler's), not the tools' credentials. Code:
`plugins/_shared/project_place.py`.

## Setup (shared)

- Store a credential with `secret set NAME -p hermes --scope S [-D KIND]`,
  pasted at the hidden prompt.
- Cookie capture: sign in in a private browser window, copy the cookie from
  DevTools → Application → Cookies, close the window **without logging out**
  (that ends the session), and paste it at the hidden prompt of `secret set`.
  Fresh cookies after a refusal are stored the same way.
- Enabling a plugin means its toolset in `toolsets` and `platform_toolsets`,
  the plugin in `plugins.enabled` and a gateway restart; changing its code
  needs a restart too, a new credential does not.
- The launcher (`launchd/<name>-access-launchctl.sh` or `scripts/<name>-access.sh`)
  has `status` (credentials by presence only) and `install`. After bumping an
  engine pin, recompile the lock (command in `requirements.in`), run `setup`
  (or the launcher's equivalent) and `restart`: `install` builds the venv only
  when it is missing, so an existing venv keeps the old dependencies silently.
