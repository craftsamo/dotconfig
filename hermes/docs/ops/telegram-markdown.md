# Telegram Markdown — what a script's output must look like

Hermes design docs — index: [`../../PROFILES.md`](../../PROFILES.md).

Everything that reaches Telegram goes through one adapter `send()`: a reply,
a `no_agent` cron job's stdout ([cron.md](cron.md)), a webhook route's
rendered text ([webhook.md](webhook.md)). The adapter takes **ordinary
Markdown** and renders it one of two ways, chosen per message by what the
message contains. A producer that knows which path its message takes writes
the right thing; one that does not gets bullets where it wanted a table, or
backslashes where it wanted none.

## The two paths

|                                                                                                          | Plain path                                                                             | Rich path                                                                                                                    |
| -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Chosen when                                                                                              | the message holds none of the rich constructs                                          | the message holds a pipe table (two columns or more), a task list (`- [ ]`), a line-start `<details>` / `<summary>`, or `$$` |
| How it is sent                                                                                           | converted to MarkdownV2 by the adapter                                                 | sent as Markdown, as written (`sendRichMessage`); needs `rich_messages: true` on the profile                                 |
| `# Heading`                                                                                              | **bold** line                                                                          | heading                                                                                                                      |
| `**bold**`, `*italic*`, `~~strike~~`, `\|\|spoiler\|\|`, `` `code` ``, fences, `[label](url)`, `> quote` | rendered                                                                               | rendered                                                                                                                     |
| `- item`, `1. item`                                                                                      | text lines                                                                             | lists                                                                                                                        |
| pipe table                                                                                               | rewritten as bold-heading + bullet groups                                              | a table                                                                                                                      |
| `<details><summary>…`                                                                                    | shown as text                                                                          | a collapsible block                                                                                                          |
| Punctuation in dynamic text (`_` `*` `\|` `#` `.` `(`)                                                   | **escaped by the adapter** — write nothing; a backslash you add is shown               | **yours to escape** — an unescaped `_` or `*` opens markup, a `\|` breaks a row, a line-start `#tag` becomes a heading       |
| Size                                                                                                     | 4096 UTF-16 units, longer is split (fences re-opened per part, tables already bullets) | 32768; longer falls back to the plain path and its splitting (a `<details>` block does not survive a split)                  |

So the rule for a producer is one sentence: **prose, headings, lists and
bold need nothing; the moment the message carries a table or a `<details>`,
every dynamic string in it must be escaped.** `scripts/tgmd.py` does that.

## Writing it: `scripts/tgmd.py`

Stdlib only, loaded by path (`~/.config/hermes/scripts/tgmd.py`, or
`TGMD_PATH`), also a command for a shell wrapper. The pieces:

| Helper                                                     | Gives                                                                                                                                                                                                                          |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `esc(text)`                                                | a dynamic inline string with every markup character escaped and line breaks flattened; a `Raw` passes through                                                                                                                  |
| `table(headers, rows, aligns=None)`                        | a pipe table, every cell escaped unless `Raw`; refuses one column (the adapter reads that as prose) and a row of another width                                                                                                 |
| `details(title, *parts)`                                   | a `<details>` block; each string part one paragraph on one line, a `Raw` part (a `table`) as is, blank lines around each, no math marker in any of them                                                                        |
| `link(label, url)`, `bold(text)`, `heading(text, level=2)` | the inline pieces, as `Raw` so a table cell or a details paragraph takes them unescaped; a `Raw` joined into a string is a plain string again — wrap it (`Raw(f"{bold(x)} …")`) before handing it to a helper                  |
| `clamp(text, limit=3800, attach=None, note=…)`             | the report when it fits `limit` UTF-8 bytes; otherwise its head up to the first `<details>` (cut again at the last line that fits when that is still too long), `note`, and a `MEDIA:<path>` line so the full file rides along |

Command form, for a `run.sh`: `tgmd table --header A,B --align l,r` (TSV
rows on stdin), `tgmd details --title T` (lines on stdin), `tgmd clamp
--limit N --attach <file>`, `tgmd esc`.

A producer that emits a table or a `<details>` builds every dynamic string
through `esc` (or lets `table` / `details` do it) and writes its fixed text
plain; a producer that emits prose only writes plain Markdown and never
escapes. A webhook route's `prompt` template is prose: it is written plain,
and the substituted fields are escaped by the adapter.

## What the rich parser trips on

- An escaped bracket inside `<details>` (`\(` … `\)`, `\[` … `\]`) is a
  math marker, and math inside details crashes Telegram Desktop, so the
  adapter refuses the rich path for the whole message and it lands as text.
  `details` strips those escapes from everything it holds — its paragraphs,
  a `table`, a `link` (`esc_in_details`).
- `$` is no markup and `esc` leaves it alone (a `\$` the parser did not
  honour would show on every price); a `$$` in dynamic text is the one thing
  that selects the rich path by itself, and opens block math there.
- `#43` at the start of a line (or of a list item) is a heading to Telegram
  even without the space standard Markdown requires; the adapter escapes such
  prefixes itself (`rich_markdown.escape_literal_hash_prefixes`), and `esc`
  already has.
- A table needs a blank line before and after it, or the prose before it
  becomes a row; `details` and the adapter's own normalisation add them.
- Telegram Desktop's rich renderer leaves overlapping glyphs on CJK text;
  `allow_cjk_rich_messages: true` on the profile sends it rich anyway,
  `false` sends a CJK message plain (tables become bullets).
- When Telegram refuses a rich message, the adapter re-sends it through the
  plain path: the escapes a producer added are then shown as backslashes.
  Readable, not pretty — the reason not to escape where the rich path is not
  the aim.

## The standalone sender

When the gateway is not running, cron delivers through the standalone sender
instead (`tools/send_message_senders.py`): a message holding an HTML-looking
tag (`<details>`, `<b>`) is sent as Telegram **HTML**, everything else through
the same MarkdownV2 conversion. A `<details>` block there is rejected by
Telegram and re-sent as plain text. Nothing to design for — the gateway is a
service ([services.md](services.md)) — but the reason a report looks different
after a gateway outage.
