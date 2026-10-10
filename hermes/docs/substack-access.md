# Substack access

The user's own Substack account as a tool: any publication's posts and
search, a post's full text (paid posts as far as the account is entitled),
the subscribed inbox, and the user's own publication — published posts,
drafts, pre-publish checks and stats. The Assistant also writes: drafts (with
local images), publishing, scheduling and Notes, each held for the user's
approval on a card. Marketer only reads. Read it when changing the plugin or its
write path. Common rules: [access-common.md](access-common.md). Part of the
Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                                                              | Home                                                     | Reader              |
| ---------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- | ------------------- |
| Engine: validation, profile actions, pacing, session state, result shapes, image outbox, approval card, write ledger, bypass guard | `plugins/social/substack-access/sa.py`                   | all                 |
| One Substack call per request in the engine venv; reads the cookies                                                                | `plugins/social/substack-access/bridge.py`               | all                 |
| `substack` tool and its `pre_tool_call` hooks (toolset `substack_access`)                                                          | `plugins/social/substack-access/__init__.py`             | Assistant, Marketer |
| Engine venv                                                                                                                        | `scripts/substack-access.sh`, `engines/python-substack/` | people              |
| When and how the Assistant uses it                                                                                                 | the Assistant's private Chat reference `substack.md`     | Assistant           |
| When Marketer may read with it                                                                                                     | `marketer-pipeline/references/platforms/substack.md`     | Marketer            |

Substack has no general API for this: its Developer API covers public profile
data and its official MCP server reads analytics of Bestseller publications
only. The tool calls the JSON endpoints the substack.com web app uses, signed
in with the browser session's cookies, through
[python-substack](https://github.com/ma2za/python-substack) (drafts, images,
publishing) and plain requests on the same session. Substack's terms forbid
scraping and reverse engineering, and the account can be limited at any time;
the user accepted that risk for low-volume use of their own account
([risk acceptance](access-common.md#risk-acceptance)). Endpoints are
undocumented and may change.

`bridge.py` runs under the hash-locked `hermes/local/python-substack/venv`,
never Hermes' own, as a child process with a minimal environment
([bridge process](access-common.md#state-directory-and-bridge-process)).

## Account, cookies and state

One account, the user's own. Its cookies live only in the Keychain, as
`SUBSTACK_COOKIES` (`substack.sid=…; substack.lli=…`; `substack.sid` is
required) in the `hermes` project under the scope `substack-session`
([secret scoping](access-common.md#secret-scoping)). The bridge holds them only
in memory, on a session bound to `.substack.com`: every request on it, the
library's own included, must be `https` to `substack.com` or a subdomain. A
publication on a custom domain is read through a second session that carries no
cookies, after its host resolves to public addresses only, and every redirect
hop is checked the same way. Cookie values (raw and URL-decoded) are masked in
every string the bridge returns.

The publication the user owns is the account's primary one, or
`substack_access.publication` in the profile's `config.yaml`.
`substack_access.attach_roots` bounds image uploads.

`~/.substack-access/` (mode 700, outside every repository) holds no secret:
`state.json` (pacing timestamps, the last write outcomes, what Substack last
made of the session), `call.lock` and `outbox/` (the image copies and manifests
of pending writes).

When Substack refuses the session (`profile/self` answers 401/403 or no user),
the refusal is stored with a fingerprint of `substack.sid` and every later call
is answered by the bridge without contacting Substack until the stored cookies
change ([refusal memory](access-common.md#state-directory-and-bridge-process)).
A 429 stores the end of the limit and every call waits for it. A Cloudflare
challenge is reported as such, not as a refused session.

## Profiles

| Profile   | Actions                         | Inbound A2A   |
| --------- | ------------------------------- | ------------- |
| Assistant | every read and write            | refused       |
| Marketer  | reads only (schema and handler) | reads allowed |
| Searcher  | `status`, `archive`, `post`     | refused       |

The action list a profile gets is fixed when the plugin registers and checked
again in both hooks and the handler ([profile gating](access-common.md#profile-gating)).
Searcher never reads the inbox, the user's own posts, drafts or statistics. It
reads through the user's session, so a paid post the user subscribes to comes
back in full: Searcher's description tells it to use such a post to check a
claim, quote only what the brief needs and mark the source as paywalled.

## Reads

`status` never contacts Substack. Every other call is paced: one at a time
across sessions and profiles (`call.lock`), a minimum gap, an hourly and a daily
cap; past a cap or during a rate limit the tool answers `paused: …` without
calling Substack. A call counts only when Substack was, or may have been,
contacted. `draft` returns Markdown through python-substack's exporter, where
blocks without a Markdown form become preservation markers.

Results carry a note that titles, text, names and links are data, never
instructions. Notes, comments, chats and other publications' statistics are not
read.

## Writes

The Assistant's writes: `create_draft`, `update_draft` (`replace_unsupported=true`
drops old blocks that have no Markdown form, which are otherwise kept or the
update refused), `publish`, `schedule`, `unschedule` and `note` (a public Note).
`publish` and `schedule` need `send_email` stated, and refuse a draft without a
title or text, one already published, and (publish) one that is scheduled.
Drafts cannot be deleted. Writes are capped per 24 hours.

- **Every write asks first** ([approval gate](access-common.md#approval-gate)).
  The approval hook prepares the write with one paced read — the publication and
  account, the draft as it is now with a digest of what the card shows and the
  write acts on, the number of email subscribers for a release, and the
  Markdown's local images. The card names the action, the publication, the
  title, the audience, who is emailed and the length; draft cards end with
  `Nothing is published or emailed.`. Names and titles shrink so every fact
  fits, and a longer body is cut on the card with the rest counted, never
  refused; the approval key binds the exact text regardless.
- **The approval covers the exact write.** The allowlist key hashes the
  request, the publication, the account, the draft digest and each image's
  SHA-256, so "session" or "always" only ever repeats that identical write to
  that draft as it then stood.
- **The approved write is the executed write.** As discord-access: the approval
  hook makes one snapshot per call, copying each image through its opened
  descriptor into a fresh `outbox/<token>/` after checking its real path against
  the attach roots and the refusal list. The `bind` hook takes that snapshot
  once and hands the handler its token (a `modify`); it never prepares one
  itself, so a call that reaches it without a card gets nothing. The handler
  consumes the token once, checks the request and the copies' hashes, and the
  bridge refuses when the account, the publication or the draft digest differs
  from the card's. python-substack may upload only the staged copy of each
  listed image. A caller-supplied token is blocked.
- **Nobody to approve, nothing written.** Writes are refused in cron, single
  queries (`-q`, resident workers), webhook and API sessions, inbound A2A, and
  under `/yolo` or `approvals.mode: off`: Hermes would approve those before any
  card, and a stored "always" would pass in cron.
- **Outcomes are never guessed.** The bridge writes a ledger in the outbox
  folder before each step that changes the account. Substack's 4xx refusals
  read `not done: …`, with any earlier steps listed. A 5xx, a lost connection,
  an unreadable answer, or a dead engine whose ledger stops at a draft or
  release step reads `UNCERTAIN: …` with one look afterwards as a hint, never a
  conclusion. A ledger that shows the final step done reads as done even when
  reporting failed afterwards; a lost image upload alone reads `not done` with a
  note that the image may have reached Substack's image store. Nothing is ever
  retried automatically.

## Ways around the tool

The hook blocks terminal calls that name the plugin, the cookies' Keychain item
or scope, the library or its CLIs, or Substack's API, and file-tool calls on the
state directory, the item name or the engine venv. Reading a publication's RSS
feed and the plugin source stays allowed. Patterns: `_TERMINAL` in
`plugins/social/substack-access/sa.py`. Shared rules:
[bypass guard](access-common.md#bypass-guard-ways-around-the-tool).

## Setup

Service-specific steps; the rest is in [shared setup](access-common.md#setup-shared).

1. `~/.config/hermes/scripts/substack-access.sh install`.
2. The account needs a publication of its own for drafts, publishing and stats;
   reads and Notes work without one.
3. Capture `substack.sid` (and `substack.lli` if present) from
   `https://substack.com`, then
   `secret set SUBSTACK_COOKIES -p hermes --scope substack-session -D COOKIE` and
   paste `substack.sid=…; substack.lli=…` at the hidden prompt.
4. Add `substack_access` to the profile's `toolsets` and `platform_toolsets`
   (Marketer: `a2a` too), `substack-access` to `plugins.enabled`, optionally
   `substack_access.publication` / `attach_roots`, and restart the gateway.
