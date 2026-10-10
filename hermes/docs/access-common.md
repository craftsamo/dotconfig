# Access plugins — common contract

What the access plugins have in common: Discord, Telegram, WhatsApp, Signal,
Google, X, note, Substack and YouTube. Each `*-access` doc inherits this one
and records only its own differences; read it first when changing or adding an
access plugin. Web3 follows the same approval and bypass-guard rules in its own
doc ([web3.md](web3.md)). Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

## Risk acceptance

Most of these plugins reach their service through an unofficial client, an
undocumented web endpoint or a browser session's cookies, which the service's
terms forbid or do not cover; the account can be limited or suspended at any
time. The user accepted that risk per service (each doc says what it is), so
the designs stay low-volume and client-like — paced requests, no read receipts
— rather than pretending the risk away. Google's and YouTube's own APIs are
the exception.

## Secret scoping

Hermes receives only shared secret layers: `profile-secrets.sh` and the
tool-mode `secret-shim` pin `--scope <project>`, because without it `secret
env` adds the scope named after the working directory's repository. A
credential kept in the `hermes` keychain sits under a scope of its own (each
doc names the item and scope; WhatsApp and Signal keep their sessions in the
engine's own store instead), so it never enters any profile's secret scope or a
CLI session, and the engine reads it only when it needs it. The engine reads them when it
needs them and never prints or logs them; replacing one needs no gateway
restart. Short rule: [AGENTS.md](../AGENTS.md) "Secrets, auth and accounts".

## State directory and bridge process

State lives outside every repository and is private (mode 700). The cookie
services (X, note, Substack) keep pacing timestamps, caps, locks and
the service's last verdict in `~/.<name>-access/`, with no secret. The
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
  docs say how). Where there is a venv it is hash-locked under `hermes/local/<name>/venv`
  and never Hermes' interpreter; note's bridge is stdlib only and runs under
  Hermes' interpreter in isolated mode (`-I`).

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
  exists. Discord, Telegram, WhatsApp, Signal, Google and note use the shared
  check `plugins/_shared/human_gate.py` (`no_human`), which fails closed when
  Hermes' approval context cannot be read; Substack and YouTube refuse through
  their own `_unattended()` and `is_approval_bypass_active()`.
- **Hook and handler both refuse**, so a write never depends on the hook
  having run; the hook refuses before any card, snapshot or file copy is
  built. The refusal says nothing was sent or changed. Reads are unaffected.
- **A card must outlast a tap.** The Assistant keeps `approvals.timeout` at
  600 s so a card stays answerable on Telegram.
- **A card is plain English, one fact per line.** Names and quotes are
  collapsed to one line and control, bidi-override and invisible characters are
  spelled out (`⟨U+202E⟩`), so other people's words cannot forge card lines.
  Long text is cut on the card with the rest counted, never refused; its full
  wording is agreed with the user in chat first.
- **The key binds the exact request.** The allowlist key hashes the request
  (and each file's content), so "session" or "always" only repeats that
  identical one.
- **Outcomes are never guessed, and a write is never retried.** A refusal
  known to happen before anything left reads `not sent` / `not done`; an
  ambiguous one reads `UNCERTAIN` and the Assistant checks with the user before
  any resend.

To try a write, ask the Assistant in a chat where its card reaches the user;
`hermes -z` can check reads, never a write.

## Bypass guard (Ways around the tool)

A `pre_tool_call` hook blocks terminal calls and file-tool calls whose text
names the plugin's engine, state, credentials, client libraries or raw API.
Terminal calls naming the plugin itself are blocked too, since importing the
engine would skip the hook; file tools may still read the plugin source. It is
a pattern match on the call's text, not a sandbox: the approval gate is a
guarantee for the tool and a policy for everything else. The patterns live in
each plugin's module (named in its doc); never copy them into docs.

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
