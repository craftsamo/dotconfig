# note access

note.com for the Assistant and Marketer. Both read note; the Assistant alone
saves the user's unpublished drafts, each save behind an approval card. The tool
reads public articles, creators, comments and hashtags, plus the user's own
drafts and stats. Drafts are written in Markdown, and images are uploaded from
local files. An offline `check` tells whether a body would save; Writer gets
that action alone, and Searcher gets the public reads alone (never the user's
drafts or stats). Nothing publishes, deletes, likes, follows or comments: the
user publishes in the browser. Read it when changing the plugin, the Markdown
conversion or the save path. Common rules: [access-common.md](access-common.md).
Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                                                                       | Home                                                                                                              | Reader                        |
| ------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| Engine: validation, pacing, session state, public reads, result shapes, image checks, write plan, approval card, image upload, bypass guard | `plugins/social/note-access/na.py`                                                                                | all                           |
| Markdown ⇄ note editor HTML                                                                                                                 | `plugins/social/note-access/notefmt.py`                                                                           | all                           |
| The only process holding the session; a fixed set of signed-in operations                                                                   | `plugins/social/note-access/bridge.py`                                                                            | all                           |
| `note` tool and the `pre_tool_call` hook (toolset `note_access`), the actions each profile gets                                             | `plugins/social/note-access/__init__.py`                                                                          | Assistant, Marketer, Writer   |
| How a profile reads note: actions, budget, results, recovery                                                                                | the `note-access:note-com` plugin skill (`plugins/social/note-access/skills/note-com/`)                           | Assistant, Marketer, Searcher |
| Preparing a body with the offline `check`                                                                                                   | the `note-access:note-com-format` plugin skill (`.../skills/note-com-format/`)                                    | Assistant, Marketer, Writer   |
| Saving a draft: the card, the whole-body update, results                                                                                    | the `note-access:note-com-drafts` plugin skill (`.../skills/note-com-drafts/`); registered for the Assistant only | Assistant                     |
| When Chat uses it                                                                                                                           | the Assistant's private Chat reference `note.md`                                                                  | Assistant                     |
| How Marketer reads and measures on note                                                                                                     | `marketer-pipeline/references/platforms/note.md`                                                                  | Marketer                      |
| How Writer writes and checks a note source draft                                                                                            | `writer-pipeline/<write\|edit\|analyze>/article/references/note.md`                                               | Writer                        |

note has no public API. The tool calls the internal endpoints that note's own
web app and editor use. They can change without notice. note's terms let it
suspend an account that puts excessive load on the service or posts spam, so
every request is paced. The user accepted this risk for their own account
([risk acceptance](access-common.md#risk-acceptance)). Everything is standard
library, so there is no venv and no install step; the bridge runs under Hermes'
own interpreter in isolated mode
([bridge process](access-common.md#state-directory-and-bridge-process)).

Marketer reads note through the tool, never note's editor; only a visual look
the user asks for opens its browser ([marketer.md](profiles/marketer.md)).

## Profiles

| Profile   | Actions                    | Inbound A2A       |
| --------- | -------------------------- | ----------------- |
| Assistant | every read, `check`, saves | refused           |
| Marketer  | every read, `check`        | reads and `check` |
| Writer    | `check` only               | `check`           |
| Searcher  | public reads               | refused           |

The action list a profile gets (`PROFILES`) is fixed when the plugin registers
and checked again by the gate, the handler and the engine
([profile gating](access-common.md#profile-gating)). An inbound request runs
only what `A2A` lists for the profile, never a save or a `preview`, and only
when the turn's bound profile home is that profile's, failing closed otherwise.
Marketer answers a peer's question with a read, the user's drafts and stats
included, on the shared request budget.

Where no person can answer the card (cron, webhooks, API sessions, single
queries) the plugin refuses the Assistant's save and its answer tells the agent
to return the exact save to its caller. No approval is relayed or inferred
across sessions.

## Session and state

One account: the user's main note account. Its session cookie lives only in the
Keychain, as `NOTE_SESSION` (`_note_session_v5=…`) in the `hermes` project under
the scope `note-session` ([secret scoping](access-common.md#secret-scoping)).
The bridge reads it at start and masks it in every string it returns, before any
clipping. It also removes every e-mail field and every e-mail address inside an
error message, because note's current-user reply carries the account's address;
note content (a draft that mentions an address) passes unchanged so that it
round-trips. Public reads never go through the bridge and never carry a cookie.
Neither do image uploads.

Logging in is not automated (reCAPTCHA). A stale cookie fails silently on some
endpoints (the draft list comes back empty), so the bridge asks who is signed
in before listing drafts and treats a 401, or an `auth` error inside a 200, as
a refusal, stored as in
[refusal memory](access-common.md#state-directory-and-bridge-process).

`~/.note-access/` (mode 700, outside every repository) holds no secret:
`state.json` (pacing times, the refusal, the end of a rate-limit pause, and the
signed-in account's public id with the cookie fingerprint it was seen under),
lock files, and `outbox/` (private copies of the images for one write).
`note_access.attach_roots` in the Assistant's `config.yaml` bounds where images
may be taken from.

## Reads

`status` and `check` never contact note. Every other action is paced per
request across sessions (`call.lock`); past a cap the tool answers
`paused: …` without calling note, and after a 429 every request waits. Public
reads need no sign-in; the user's own `drafts`, `draft` and `stats` do.

Results carry a note that their text is other people's words, never
instructions.

## Markdown

Draft bodies are Markdown, and `notefmt.py` converts them to the exact HTML
note's editor stores (and is the list of supported formats). Converting a
stored body to Markdown and back gives identical HTML apart from fresh block
UUIDs.

Ruby (`｜漢字《かんじ》`) and math (`$${…}$$`) are plain text in note, so they
pass through. Embeds, files, sounds and anything else Markdown cannot express
read as `[label](note-block:<uuid>)`. On update, such a line puts back the
stored HTML of that block verbatim, so those blocks are kept by leaving their
lines in place. Anything note cannot hold is refused with its line number.

Outside code blocks, three things note could store are refused too, because a
reader would see their marks: Writer's insertion markers (`[[image:id]]`,
`[[embed:id]]`, `[[table:id]]`, which stand for assets that do not exist yet),
table rows and rules, and HTML comments. Other Markdown note has no form for is
saved as typed. A stored body that only looks like one of the refused marks
reads back escaped, so it still round-trips.

## Check

`check` runs the same scan and parse as a save, without contacting note or
spending a request, and returns each problem with its line. The parse stops at
the first structural error, which hides the image checks and the length.
`markers` keeps the insertion markers apart from `errors` so Writer can report
the draft as needing assets.

`ready` means a save would accept the format. It says nothing about the account,
the draft an update targets or the approval card, which only `preview` and the
save check.

## Writes

`create_draft` and `update_draft` replace the whole title and body, only after
Hermes' approval card for that exact call. `base` is required for an update: the
`saved` time of the `draft` read the edit starts from. A draft saved since is
refused, so an edit made after that read is never overwritten. `preview=true` on either action runs every check below
and returns the card the save would show, without saving or asking; it works in
any run. The `pre_tool_call` hook builds the write plan first and blocks a
write that would fail:

- An update reads the draft as it is now and refuses a published or scheduled
  article, a note that is not the account's own, and a draft with a paid area
  (the paid boundary is a block id, which a new body would orphan).
- Image paths must resolve inside an attach root and must not be
  credential-like; each must be a real image, sniffed from its header, within
  the size and count limits.
- A remote image URL is accepted only if the draft being updated already has it.

The card stays within Telegram's budget and names the draft, the account, the
new title, the new and kept images (each new image with its SHA-256), the cover
and the start of the Markdown. Long titles and the current text are shortened first, then the
images are counted under one combined fingerprint. A save whose header still
cannot fit is refused, so a cover or an image is never cut off the card.

The rule key covers the action, the account and the cookie's fingerprint, the
draft and its last saved time, the title and the whole Markdown, and every image
hash. "Session" or "always" therefore only repeats that identical save under
that session. Approval records are per tool call and allow one save.

At execution, plugin writes to one draft run one at a time (`drafts/<key>.lock`)
from re-checking through saving. The handler re-derives the plan and refuses if
the rule key differs (the user editing the draft after the card, an image
changing, another account's cookie stored meanwhile). Every write request
carries the approved fingerprint, and the bridge sends nothing under a
different stored session. The handler copies every image into the outbox and
refuses if any copy's hash differs from the card. The steps run in this order:

1. Per new image: an upload slot, then a multipart POST to note's S3 bucket.
   Only `https` to an `*.s3.*.amazonaws.com` host is accepted, without the
   cookie and without redirects.
2. A new draft is created empty. An update takes a last look at the draft and
   refuses if it was saved since the card (the uploads take time). note's save
   has no conditional form, so a browser edit landing between this look and the
   save is still overwritten.
3. The title and body are saved, then the cover.
4. A read-back: the stored body and title must equal what was sent (`verified`).

Images upload before the draft is created, so a failed upload leaves no empty
draft behind. Each outcome is reported this way:

- **`not saved`:** nothing in a draft changed. Uploaded images may sit unused in
  note's storage.
- **`stopped part way`:** note confirmed some draft changes, then refused a later
  step. The answer lists the steps done and the key.
- **`UNCERTAIN`:** a draft-changing request was sent and note's answer does not
  show whether it applied. Read the draft first.

Nothing is retried.

## Where a write may run

A save is refused wherever no person can answer its card
([approval gate](access-common.md#approval-gate)); the hook and the handler each
refuse, before a card or a save is built, and the answer names the reason.
Reads, `check` and `preview=true` are unaffected.

## Ways around the tool

On every profile with the tool the hook blocks terminal calls whose text names
the plugin, the Keychain item or scope, the cookie name or `note.com/api`, and
file-tool calls on the state directory or the cookie names. File tools may still
read the plugin source, and the browser may still open note. Patterns:
`_TERMINAL` and `_STORE` in `plugins/social/note-access/na.py`. Shared rules:
[bypass guard](access-common.md#bypass-guard-ways-around-the-tool). The toolset
is in an `a2a` platform toolset only where `A2A` lists actions (Marketer,
Writer), never the Assistant's.

## Setup

Service-specific steps; the rest is in [shared setup](access-common.md#setup-shared).

1. Sign in to the user's note account in a private browser window, copy
   `_note_session_v5` from `https://note.com`, then
   `secret set NOTE_SESSION -p hermes --scope note-session -D COOKIE` and paste
   `_note_session_v5=…` at the hidden prompt.
2. Enable the plugin and add `note_access` to the profile's `toolsets` and
   `platform_toolsets` (`a2a` only for Marketer and Writer), then restart the
   gateway. Marketer and Writer have it in this repo; the Assistant's lives in
   the private overlay.
3. `status` shows whether the cookie is stored and accepted.
