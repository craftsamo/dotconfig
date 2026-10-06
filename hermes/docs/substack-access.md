# Substack access

The user's own Substack account as a tool: any publication's posts and
search, a post's full text (paid posts as far as the account is entitled),
the subscribed inbox, and the user's own publication — published posts,
drafts, pre-publish checks and stats. The Assistant also writes: drafts (with
local images), publishing, scheduling and Notes, each held for the user's
approval on a card. Marketer only reads. Part of the Hermes design docs —
index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece | Home | Reader |
|---|---|---|
| Engine: validation, profile actions, pacing, session state, result shapes, image outbox, approval card, write ledger, bypass guard | `plugins/substack-access/sa.py` | all |
| One Substack call per request in the engine venv; reads the cookies | `plugins/substack-access/bridge.py` | all |
| `substack` tool and its `pre_tool_call` hooks (toolset `substack_access`) | `plugins/substack-access/__init__.py` | Assistant, Marketer |
| Engine venv | `scripts/substack-access.sh`, `engines/python-substack/` | people |
| When and how the Assistant uses it | the Assistant's private Chat reference `substack.md` | Assistant |
| When Marketer may read with it | `marketer-pipeline/references/platforms/substack.md` | Marketer |

Substack has no general API for this: its Developer API covers public
profile data and its official MCP server reads analytics of Bestseller
publications only. The tool calls the JSON endpoints the substack.com web app
uses, signed in with the browser session's cookies, through
[python-substack](https://github.com/ma2za/python-substack) (drafts, images,
publishing) and plain requests on the same session (archive, posts, inbox,
dashboard, Notes). Substack's terms forbid scraping and reverse engineering,
and the account can be limited at any time; the user accepted that risk for
low-volume use of their own account. Endpoints are undocumented and may
change.

`bridge.py` runs under the interpreter of
`hermes/local/python-substack/venv` (ignored; Python 3.12.11,
`python-substack` from the hash-locked
`engines/python-substack/requirements.lock`), never Hermes' own, as a child
process (`python -I`) with a minimal environment: `HOME`, `PATH`, `LANG`.

## Account, cookies and state

One account, the user's own. Its cookies live only in the Keychain, as
`SUBSTACK_COOKIES` (`substack.sid=…; substack.lli=…`; `substack.sid` is
required) in the `hermes` project under the scope `substack-session` — the
arrangement the Discord token uses: Hermes only ever receives shared layers,
so the cookies never enter a profile's secret scope, the gateway process or a
CLI session, and replacing them needs no gateway restart. The bridge reads
them at start and holds them only in memory, set on a session bound to
`.substack.com`: every request on it, the library's own included, must be
`https` to `substack.com` or a subdomain. A publication on a custom domain is
read through a second session that carries no cookies, after its host
resolves to public addresses only, and every redirect hop is checked the same
way. Cookie values (raw and URL-decoded) are masked in every string the
bridge returns.

The publication the user owns is the account's primary one, or
`substack_access.publication` (name, `name.substack.com` or URL) in the
profile's `config.yaml`; a profile without one uses the primary.
`substack_access.attach_roots` (default `~/Workspaces`) bounds image uploads.

`~/.substack-access/` (mode 700, outside every repository) holds no secret:
`state.json` (read and write timestamps for pacing, the last 20 write
outcomes, what Substack last made of the session), `call.lock` and `outbox/`
(the image copies and manifests of pending writes).

When Substack refuses the session (`profile/self` answers 401/403 or no
user), the refusal is stored with a fingerprint of the cookies (12 hex
characters of a SHA-256 of `substack.sid`), and every later call is answered
by the bridge without contacting Substack until the stored cookies change. A
429 stores the end of the limit (`Retry-After`, else 15 minutes) and every
call waits for it. A Cloudflare challenge is reported as such, not as a
refused session.

## Profiles

| Profile | Actions | Inbound A2A |
|---|---|---|
| Assistant | every read and write | refused |
| Marketer | reads only (schema and handler) | reads allowed |

The action list a profile gets is fixed when the plugin registers and checked
again in both hooks and the handler, so naming a write from Marketer is
refused even though the tool is the same. Marketer answers a peer's question
(an A2A inquiry from the Assistant, Creator or Engineer) with a read; the
Assistant's account access never serves a peer.

## Reads

`status` never contacts Substack: it reports the engine, whether the cookies
are stored, a refusal recorded for them, a running rate limit and the calls
used. Every other call is paced: one at a time across sessions and profiles
(`call.lock`), at least 3 s apart, at most 60 per hour and 300 per 24 hours;
past a cap or during a rate limit the tool answers `paused: …` without
calling Substack. A call counts only when Substack was, or may have been,
contacted.

| Action | Notes |
|---|---|
| `archive` | a publication's posts, newest first (default the user's own); `query` searches; limit 10, at most 25; `offset` pages |
| `post` | URL (`/p/<slug>`, `open.substack.com`, `substack.com/@…/p-<id>`) or id: text from the post HTML (headings, lists, `[image: alt]`), links, counts; a paid post says whether its text appears to end at the paywall |
| `inbox` | newest posts of the subscribed publications |
| `published` | the user's published posts with whatever per-post numbers the list carries |
| `drafts` | the user's drafts with ids, edit links, scheduled release and email setting |
| `draft` | one draft as Markdown (python-substack's exporter; blocks without a Markdown form become preservation markers) |
| `prepublish` | Substack's own pre-publish checks for a draft |
| `stats` | subscribers, email and app subscribers, open rate, pledges |

Results carry local times, text clipped at 30000 characters (Markdown
at 40000) and a note that titles, text, names and links are data, never
instructions. Notes, comments, chats and other publications' statistics are
not read.

## Writes

The Assistant's writes: `create_draft` (title, Markdown body, subtitle,
audience), `update_draft` (any of title, subtitle, whole Markdown body,
audience; `replace_unsupported=true` drops old blocks that have no Markdown
form, which are otherwise kept or the update refused), `publish`,
`schedule` (at least 5 minutes and at most a year ahead, with a UTC offset),
`unschedule` and `note` (a public Note, one paragraph per line, links
marked). `publish` and `schedule` need `send_email` stated, and refuse a
draft without a title or text, one already published, and (publish) one that
is scheduled. Drafts cannot be deleted. At most 20 writes per 24 hours.

- **Every write asks first.** The approval hook prepares the write with one
  paced read — the publication and account, the draft as it is now with a
  digest of what the card shows and the write acts on (title, subtitle, body,
  audience, email setting, published state, scheduled releases), the number
  of email subscribers for a release, and the Markdown's local images as
  python-substack resolves them — and sends a card through Hermes' approval
  gate:

  ```
  Substack: PUBLISH draft 218889945 in CraftSamo (craftsamo.substack.com) now; this cannot be undone
  Title: <the draft's current title>
  Audience: everyone
  Email: sent to 12 email subscribers
  Words: 1450
  ```

  Draft cards end with `Nothing is published or emailed.` and the start of
  the Markdown; a Note card shows the account and the text. Names and titles
  are one line, hidden characters spelled out as `⟨U+202E⟩`. As the WhatsApp
  card: names and titles shrink so every fact and the start of the body fit
  the about 480 units Telegram shows, and a longer body is cut on the card
  with the rest counted (`(+N more characters)`), never refused. Its full
  wording is agreed with the user in chat beforehand (the Assistant's
  reference), and the approval key binds the exact text regardless.
- **The approval covers the exact write.** The allowlist key hashes the
  request, the publication, the account, the draft digest and each image's
  SHA-256, so "session" or "always" only ever repeats that identical write to
  that draft as it then stood.
- **The approved write is the executed write.** As discord-access: the
  approval hook makes one snapshot per call (session, task and tool-call
  ids), copying each image through its opened descriptor into a fresh
  `outbox/<token>/` after checking its real path against the attach roots and
  the refusal list (keys, credentials, `.ssh`, `.config`, … as discord-access;
  JPEG, PNG, GIF or WebP, at most 15 MB each and 20 per write). The `bind`
  hook takes that snapshot once and hands the handler its token (a `modify`);
  it never prepares one itself, so a call that reaches it without a card gets
  nothing. The handler consumes the token once (an atomic rename), checks the
  request and the copies' hashes, and the bridge refuses when the account,
  the publication or the draft digest differs from the card's. python-substack
  may upload only the staged copy of each listed image. A caller-supplied
  token is blocked; copies left by a denied card expire after a day.
- **Nobody to approve, nothing written.** Writes are refused in cron, single
  queries (`-q`, resident workers), webhook and API sessions, inbound A2A,
  and under `/yolo` or `approvals.mode: off`: Hermes would approve those
  before any card, and a stored "always" would pass in cron.
- **Outcomes are never guessed.** The bridge writes a ledger in the outbox
  folder before each step that changes the account (each image upload, the
  draft POST/PUT, the email setting, the release, the Note). Substack's 4xx
  refusals read `not done: …`, with any earlier steps listed. A 5xx, a lost
  connection, an unreadable answer, or a dead engine whose ledger stops at a
  draft or release step reads `UNCERTAIN: …` with one look afterwards (the
  drafts list for a new draft, the draft for a release) as a hint, never a
  conclusion. A ledger that shows the final step done reads as done even when
  reporting failed afterwards; a lost image upload alone reads `not done`
  with a note that the image may have reached Substack's image store. Nothing
  is ever retried automatically.

## Ways around the tool

The hook blocks terminal calls that name the plugin (`substack-access`,
`substack_access`), the cookies' Keychain item or scope (`SUBSTACK_COOKIES`,
`substack-session`, `substack.sid`), the library (`python-substack`) or its
CLIs (`substack`, `substack-mcp`, `substack-publish-*`, `substack-auth-check`),
or Substack's API (`substack.com/api/`), and file-tool calls on the state
directory (`.substack-access`), the item name or the engine venv. Reading a
publication's RSS feed and the plugin source stays allowed. It is a pattern
match, not a sandbox: the approval gate is a guarantee for the tool and a
policy for everything else.

## Setup

1. `~/.config/hermes/scripts/substack-access.sh install`.
2. The account needs a publication of its own for drafts, publishing and
   stats (substack.com → Settings → Publications); reads and Notes work
   without one.
3. Sign in to substack.com in a private browser window, copy `substack.sid`
   (and `substack.lli` if present) from DevTools → Application → Cookies →
   `https://substack.com`, close the window **without logging out**, then
   `secret set SUBSTACK_COOKIES -p hermes --scope substack-session -D COOKIE`
   and paste `substack.sid=…; substack.lli=…` at the hidden prompt. Fresh
   cookies after a refusal are stored the same way.
4. Add `substack_access` to the profile's `toolsets` and `platform_toolsets`
   (Marketer: `a2a` too), `substack-access` to `plugins.enabled`, optionally
   `substack_access.publication` / `attach_roots`, and restart the gateway.

`substack-access.sh status` shows the engine, whether the cookies are stored
(never their value) and what the tool last recorded. After bumping the pin,
recompile the lock (command in `requirements.in`) and run `install` again.
