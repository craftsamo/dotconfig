# note access

note.com for the Assistant and Marketer. Both read note and save the user's
unpublished drafts, each save behind an approval card. The tool reads public articles,
creators, comments and hashtags, plus the user's own drafts and stats. Drafts
are written in Markdown, and images are uploaded from local files. An offline
`check` tells whether a body would save; Writer gets that action alone. Nothing
publishes, deletes, likes, follows or comments: the user publishes in the
browser. Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                                                                       | Home                                                                   | Reader                      |
| ------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | --------------------------- |
| Engine: validation, pacing, session state, public reads, result shapes, image checks, write plan, approval card, image upload, bypass guard | `plugins/note-access/na.py`                                            | all                         |
| Markdown ⇄ note editor HTML                                                                                                                 | `plugins/note-access/notefmt.py`                                       | all                         |
| The only process holding the session; a fixed set of signed-in operations                                                                   | `plugins/note-access/bridge.py`                                        | all                         |
| `note` tool and the `pre_tool_call` hook (toolset `note_access`), the actions each profile gets                                             | `plugins/note-access/__init__.py`                                      | Assistant, Marketer, Writer |
| How the Assistant works with it: actions, budget, preparing a body, saving, results, Marketer's save packages                               | the `note-com` technic (`profiles/assistant/skills/technic/note-com/`) | Assistant                   |
| When Chat uses it                                                                                                                           | the Assistant's private Chat reference `note.md`                       | Assistant                   |
| How Marketer drafts and measures on note                                                                                                    | `marketer-pipeline/references/platforms/note.md`                       | Marketer                    |
| How Writer writes and checks a note source draft                                                                                            | `writer-pipeline/<write\|edit\|analyze>/article/references/note.md`    | Writer                      |

note has no public API. The tool calls the internal endpoints that note's own
web app and editor use, the same way the editor does. They can change without
notice. note's terms let it suspend an account that puts excessive load on the
service or posts spam, so every request is paced. The user accepted this risk
for their own account. Everything is standard library, so there is no venv and
no install step. The bridge runs under Hermes' own interpreter in isolated mode
(`-I`), as a child process with a minimal environment: `HOME`, `PATH` and
`LANG`, none of the gateway's keys.

For note the tool replaces Marketer's browser procedure: Marketer never types
into note's editor and needs no browser lease for note
([marketer.md](profiles/marketer.md)).

## Profiles

| Profile   | Actions                    | Inbound A2A       |
| --------- | -------------------------- | ----------------- |
| Assistant | every read, `check`, saves | refused           |
| Marketer  | every read, `check`, saves | reads and `check` |
| Writer    | `check` only               | `check`           |

The action list a profile gets (`PROFILES`) is fixed when the plugin
registers and checked again by the gate, the handler and the engine, so naming
an action outside it is refused even though the tool is the same. An inbound
request runs only what `A2A` lists for the profile, never a save or a
`preview`, and only when the turn's bound profile home is that profile's,
failing closed otherwise. The Assistant never serves a peer. Marketer
answers a peer's question with a read, the user's drafts and stats included,
on the shared request budget. Writer, which has no terminal, checks its own
note drafts.

Where a profile may save, whether a save can run depends on whether a person
can answer the card. On a gateway platform (each profile's own Telegram bot)
or an interactive CLI the card appears and the save runs after approval. A
resident session that one agent starts in another (`specialist_call` →
`resident-session.sh`) runs as a single query, as do cron, webhooks and API
sessions: nobody can answer there, so the plugin refuses the save and its
answer tells the agent to return the exact save — action, draft key and
`saved` time, title, Markdown, image and cover paths — to its caller. For
Marketer working for the Assistant, that caller is the Assistant, which saves
the package unchanged with its own card and passes the result back. No
approval is relayed or inferred across sessions.

## Session and state

One account: the user's main note account. Its session cookie lives only in
the Keychain, as `NOTE_SESSION` (`_note_session_v5=…`) in the `hermes`
project under the scope `note-session`. This is the arrangement the X and
Discord secrets use: Hermes only receives shared layers, so the cookie never
enters a profile's secret scope, the gateway process or a CLI session.
Replacing the cookie needs no gateway restart. The bridge reads it at start
(`secret get … -p hermes --scope note-session`) and masks it in every string
it returns, before any clipping. It also removes every e-mail field, because
note's current-user reply carries the account's address, and every e-mail
address inside an error message. Note content (a draft that mentions an
address) passes unchanged so that it round-trips. Public reads never go through the bridge
and never carry a cookie. Neither do image uploads, which go straight to the
storage URL note hands out.

Logging in is not automated: note's sign-in now requires reCAPTCHA. A stale
cookie fails silently on some endpoints (the draft list comes back empty), so
the bridge asks who is signed in before listing drafts and treats a 401, or an
`auth` error inside a 200, as a refusal. A refusal is stored with a
fingerprint of the cookie (12 hex characters of a SHA-256). Every later
signed-in call is then answered without contacting note, until the stored
cookie changes or a call with it succeeds.

`~/.note-access/` (mode 700, outside every repository) holds no secret:

- `state.json`: request times for pacing, the refusal, the end of a
  rate-limit pause, and the signed-in account's public id, kept with the
  cookie fingerprint it was seen under (it is shown only for that cookie);
- `call.lock` and `drafts/<key>.lock`;
- `outbox/`: private copies of the images for one write, removed when the
  write ends and pruned after a day.

The Assistant's `config.yaml` may set `note_access.attach_roots`, the folders
images may be taken from. The default is `~/Workspaces`.

## Reads

`status` and `check` never contact note. `status` reports whether the cookie
is stored, a refusal recorded for it, a running pause, the cached account and
the requests used. Every other action is paced per request across sessions
(`call.lock`): at least 2 s between requests, at most 60 per hour and 500 per
24 hours. The gap also holds between the two requests of one bridge operation.
Past a cap the tool answers `paused: …` without calling note. After a 429
every request waits 10 minutes.

| Action     | Signed in                          | Requests | Notes                                                                                                            |
| ---------- | ---------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
| `search`   | no                                 | 1        | sort `new` / `popular` / `hot`; 10 per page, at most 20; `start` = `next_start`                                  |
| `articles` | no (+1 to find the user's id once) | 1        | a creator's articles; default the user's own                                                                     |
| `article`  | no                                 | 1        | a published article as Markdown; a paid one gives its free part                                                  |
| `creator`  | no                                 | 1        | profile and counts; follower counts only where the creator shows them                                            |
| `comments` | no                                 | 1        | flattened from note's comment documents, with the author's latest reply; "turned off" on 403                     |
| `hashtag`  | no                                 | 1        | newest articles with the tag, 50 per page                                                                        |
| `drafts`   | yes                                | 2        | who is signed in, then the unpublished drafts                                                                    |
| `draft`    | yes                                | 1        | one own draft as Markdown, with `updatable`                                                                      |
| `stats`    | yes                                | 1        | views, likes, comments per article; `period` all / daily / weekly / monthly / yearly; `sort` pv / like / comment |

Results carry local times, clipped text, and a note that titles, articles,
profiles and comments are other people's words, never instructions.

## Markdown

Draft bodies are Markdown, and `notefmt.py` converts them to the exact HTML
note's editor stores. Each top-level block carries one UUID as both `name`
and `id`. Converting a stored body to Markdown and back gives identical HTML
apart from fresh UUIDs; the test fixture is a real editor draft holding every
format. The supported formats:

- `##` / `###` headings;
- paragraphs, where a line break inside stays a `<br>`;
- `**bold**`, `~~strike~~` and links;
- `-> centred <-` and `-> right` alignment;
- flat `-` / `1.` lists, with the starting number kept;
- quotes with an optional `> — source`;
- fenced code, `---` and `[TOC]`;
- `<br>` for an empty paragraph;
- images: `![caption](path "alt")`, or `[![…](…)](https://…)` for a linked one.

Ruby (`｜漢字《かんじ》`) and math (`$${…}$$`) are plain text in note, so they
pass through. Embeds, files, sounds and anything else Markdown cannot express
read as `[label](note-block:<uuid>)`. On update, such a line puts back the
stored HTML of that block verbatim, so those blocks are kept by leaving their
lines in place. Anything note cannot hold is refused with its line number:
`#` / `####` headings, nested lists, non-http links, an unclosed fence,
foreign `note-block` ids.

Outside code blocks, three things note could store are refused too, because a
reader would see their marks: Writer's insertion markers (`[[image:id]]`,
`[[embed:id]]`, `[[table:id]]`, which stand for assets that do not exist
yet), table rows and rules, and HTML comments. Other Markdown note has no form
for is saved as typed: `*italic*`, `` `inline code` ``, HTML tags, footnotes,
an image inside a paragraph and `<https://…>`. A stored body that only looks
like one of the refused marks reads back escaped (`\|`, `\[`, `\<!--`), so
it still round-trips.

## Check

`check` takes `body`, or `path` (a `.md`, `.markdown` or `.txt` file inside
an attach root, at most 1 MB of UTF-8), plus an optional `title` and
`eyecatch`. It runs the same scan and parse as a save, without contacting
note or spending a request, and returns each problem with its line. The parse
stops at the first structural error (a heading level, a nested list, an
unclosed fence), which then hides the image checks and the length, so fix it
and check again:

- `errors`: what a save refuses, including a local image that is missing,
  outside the attach roots, too large or not an image (a relative path is
  read from the first root, and the answer names the absolute path when the
  file sits beside the Markdown file instead);
- `markers`: the insertion markers, kept apart so Writer can report the
  draft as needing assets;
- `as_typed`: Markdown saved with its marks;
- `images`, `cover` (with a note when it is not 1280:670), `web_images` and
  `kept_blocks` (valid only in an update of the draft they came from), and
  `characters`, the text length note counts.

`ready` means a save would accept the format. It says nothing about the
account, the draft an update targets or the approval card, which only
`preview` and the save check.

## Writes

`create_draft` (title, body, optional `eyecatch`) and `update_draft` (draft,
`base`, body, optional title and eyecatch) replace the whole title and body,
only after Hermes' approval card for that exact call. `base` is required: the
`saved` time, to the second, of the `draft` read the edit starts from. A draft
saved since is refused, so an edit made after that read is never overwritten,
whoever finally saves. `preview=true` on either action runs every check below
and returns the card the save would show, without saving or asking; it works
in any run, so a resident agent checks its save package before handing it
over. Both profiles keep
`approvals.timeout` at 600 s so a card outlasts a Telegram tap.
The `pre_tool_call` hook builds the write plan first and blocks a write that
would fail:

- An update reads the draft as it is now and refuses a published or
  scheduled article, a note that is not the account's own, and a draft with a
  paid area. The paid
  boundary is a block id, which a new body would orphan.
- Image paths must resolve inside an attach root and must not be
  credential-like. Each must be a real JPEG / PNG / GIF / WebP, sniffed from
  its header, up to 20 MB in the body and 10 MB for the cover, with at most 20
  new images per save.
- A remote image URL is accepted only if the draft being updated already has
  it, and its displayed size is taken from there.

The card stays within Telegram's ~480 characters, measured as Telegram
escapes it. It names:

- the draft and the account, which a create asks note for afresh;
- for an update, the current title and text;
- the new title, the length and the new and kept images;
- every new image with its size, folder and SHA-256;
- the cover;
- the start of the Markdown.

When the header lines do not fit, long titles and the current text are
shortened first. Then the images are counted under one combined fingerprint.
A save whose header still cannot fit is refused, so a cover or an image is
never cut off the card.

The rule key covers:

- the action, the account and the cookie's fingerprint;
- the draft and its last saved time;
- the title and the whole Markdown;
- every image hash.

"Session" or "always" therefore only repeats that identical save under that
session. Approval records are per tool call, last 15 minutes and allow one
save. Cron, webhook, API and single-query contexts are refused by the plugin
itself, because Hermes consults stored approvals before its cron rule.
Inbound A2A never saves or previews on any profile.

At execution, plugin writes to one draft run one at a time (`drafts/<key>.lock`)
from re-checking through saving. The handler re-derives the plan and refuses
if the rule key differs. That covers the user editing the draft after the
card, an image changing after it, and another account's cookie stored
meanwhile. Every write request carries the approved fingerprint, and the
bridge sends nothing under a different stored session. The handler checks the
request budget for the whole write, then copies every image into the outbox
and refuses if any copy's hash differs from the card. The steps then run in
this order:

1. Per new image: an upload slot (`presigned_post`), then a multipart POST of
   all the signed fields and the file to note's S3 bucket. Only `https` to an
   `*.s3.*.amazonaws.com` host is accepted, without the cookie and without
   redirects. The returned `assets.st-note.com/img/…` URL goes into the
   figure, scaled to at most 620 px wide as the editor does.
2. For a new draft: `text_notes`, which creates an empty draft. For an
   update: a last look at the draft, refusing if it was saved since the card
   (the uploads take time). note's save has no conditional form, so a browser
   edit landing in the seconds between this look and the save is still
   overwritten.
3. `draft_save` with the title, the body and its text length.
4. The cover: `image_upload/note_eyecatch`. note accepts only the 1280:670
   box and fits the image to it.
5. A read-back: the stored body and title must equal what was sent
   (`verified`).

Uploading images before creating the draft means a failed upload leaves no
empty draft behind. Each outcome is reported this way:

- **`not saved`:** nothing in a draft changed. Uploaded images may sit unused
  in note's storage.
- **`stopped part way`:** note confirmed some draft changes, then refused a
  later step. The answer lists the steps done and the key.
- **`UNCERTAIN`:** a draft-changing request was sent and note's answer does not
  show whether it applied. That covers a timeout, a broken connection, a 5xx,
  an unreadable 2xx and an unexpected error. Read the draft first.

Nothing is retried automatically.

## Ways around the tool

On every profile with the tool the hook blocks two kinds of call:

- terminal calls whose text names the plugin (`note-access`, `note_access`),
  the Keychain item or scope (`NOTE_SESSION`, `note-session`), the cookie
  name (`_note_session`) or `note.com/api`;
- file-tool calls on the state directory (`.note-access`) or the cookie names.

File tools may still read the plugin source, and the browser may still open
note. It is a pattern match, not a sandbox. The toolset is in an `a2a`
platform toolset only where `A2A` lists actions (Marketer, Writer), never the
Assistant's.

## Setup

1. Sign in to the user's note account in a private browser window. Copy
   `_note_session_v5` from DevTools → Application → Cookies →
   `https://note.com`, then close the window **without logging out** (logging
   out ends the session). Run
   `secret set NOTE_SESSION -p hermes --scope note-session -D COOKIE` and paste
   `_note_session_v5=…` at the hidden prompt. A refreshed cookie is stored the
   same way; nothing else needs resetting.
2. Enable the plugin and add `note_access` to the profile's `toolsets` and
   `platform_toolsets` (`a2a` only for Marketer and Writer), then restart the
   gateway. Marketer and Writer have it in this repo; the Assistant's lives in
   the private overlay. Optionally set
   `note_access.attach_roots` per profile; a Marketer package handed to the
   Assistant must use paths inside the Assistant's roots (both default to
   `~/Workspaces`).
3. `note status` shows whether the cookie is stored and accepted.
