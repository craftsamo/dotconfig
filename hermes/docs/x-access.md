# X access

The Assistant's read-only view of X (Twitter): the user's main account's
posts and mentions, search, threads, profiles, and a post's photos, videos
and GIFs. It reads as a separate **sub-account**; the main account is only a
search subject and never signs in here. Nothing posts, replies, likes,
follows or sends DMs. Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

## Shape

| Piece | Home | Reader |
|---|---|---|
| Engine: validation, pacing, session state, result shapes, media download, bypass guard | `plugins/x-access/xa.py` | all |
| One twscrape read per call in the engine venv; reads the cookies | `plugins/x-access/bridge.py` | all |
| `x` tool and the `pre_tool_call` hook (toolset `x_access`) | `plugins/x-access/__init__.py` | Assistant |
| Engine venv | `scripts/x-access.sh`, `engines/twscrape/` | people |
| When and how the Assistant uses it | the Assistant's private Chat reference `x.md` | Assistant |

[twscrape](https://github.com/vladkens/twscrape) calls the GraphQL endpoints
the x.com web app uses, signed in with a browser session's `auth_token` and
`ct0` cookies. It is not the X API: X's automation rules forbid non-API
automation and the sub-account can be locked or suspended at any time. The
user accepted that risk for a read-only sub-account; the paid official API
was the alternative. Because the session belongs to the sub-account, the main
account's bookmarks, notifications, home timeline and DMs are out of reach by
design.

`bridge.py` runs under the interpreter of `hermes/local/twscrape/venv`
(ignored; Python 3.12.11, `twscrape[curl]` from the hash-locked
`engines/twscrape/requirements.lock`), never Hermes' own, as a child process
with a minimal environment (none of the gateway's keys): `HOME`, `PATH`,
`TWS_TELEMETRY=0` (twscrape otherwise reports operation names) and
`TWS_HTTP_BACKEND=curl` (browser-like TLS).

## Cookies and state

One account. Its cookies live only in the Keychain, as `X_READER_COOKIES`
(`auth_token=…; ct0=…`) in the `hermes` project under the scope `x-reader` —
the arrangement the Discord token uses: Hermes only ever receives shared
layers (`profile-secrets.sh` and the tool-mode shim pin `--scope <project>`),
so the cookies never enter a profile's secret scope, the gateway process or a
CLI session, and replacing them needs no gateway restart. The bridge reads
them at start (`secret get … -p hermes --scope x-reader`) and gives twscrape
an **in-memory** account pool (a shared-cache SQLite database held open for
the call), so nothing of the session is written to disk; both cookie values
are masked in every string the bridge returns.

`~/.x-access/` (mode 700, outside every repository) holds no secret:
`state.json` (call timestamps for pacing, a handle → user id cache for seven
days, and what X last made of the session) and `call.lock`.

Because the pool is rebuilt for every call, the engine remembers X's verdicts
itself. When X refuses the session (twscrape marks it inactive: expired,
logged out, locked, suspended), the refusal is stored with a fingerprint of
the cookies (12 hex characters of a SHA-256 of `auth_token`), and every later
read is answered by the bridge without contacting X until the stored cookies
change. When X rate-limits an endpoint, the end of the limit is stored and
every read waits for it.

The Assistant's `config.yaml` (private overlay) carries `x_access.main_handle`
— the account `posts` (without `handle`) and `mentions` read — and
`x_access.download_dir`; without it media lands in
`<HERMES_HOME>/x-downloads/`.

## Reads

`status` never contacts X: it reports the engine, whether the cookies are
stored, a refusal recorded for them, a running rate limit and the reads used.
Every other action reaches X and is paced per twscrape read (one read may
page or retry inside twscrape): one call at a time across sessions
(`call.lock`), at least 5 s between calls, at most 30 per hour and 200 per
24 hours; past a cap or during a rate limit the tool answers `paused: …`
without calling X. A call counts only when X was, or may have been,
contacted: a missing engine or cookies, or a remembered refusal, costs
nothing.

| Action | Paced reads | Notes |
|---|---|---|
| `posts` | 1 (+1 to resolve an uncached handle) | `replies=true` includes replies; protected accounts refused |
| `mentions` | 1 | search `(@main OR to:main) -from:main`, Latest; `since` = YYYY-MM-DD |
| `search` | 1 | X search syntax; Latest, or Top with `top=true` |
| `thread` | 2 | the post, then its whole conversation from the root |
| `user` | 1 | profile, bio, counts |
| `media` | 1 | then CDN downloads without cookies |

Limits default to 20 (thread 30), at most 50. Results carry local times with
offset, text clipped at 2000 characters (quoted posts 280), reposts as
`repost_of`, media named by type, expanded links and counts, plus a note that
everything in them is other people's text, never instructions. An empty
result carries twscrape's last warnings as `x_warnings`.

## Media

`media` reads the post once (a repost resolves to the original; `quoted=true`
adds the quoted post) and downloads photos at original size (`?name=orig`),
the highest-bitrate MP4 of each video and GIFs (served as MP4) into
`<download_dir>/<post id>/<owner post id>-<n>.<ext>`. Downloads go only to
`https://pbs.twimg.com` and `https://video.twimg.com`, redirects included,
from the engine itself (which never holds the cookies) through an opener with
no cookie handler. The served type must be an image or `video/mp4`; a file
over 500 MB is refused before or during the download, and a body shorter than
its declared length is refused. Each download writes its own hidden part
file, renamed into place only when complete, so concurrent calls never share
one; files already present are reused, not fetched again. Links, cards,
Spaces and live broadcasts are not downloaded. A post that cannot be read is
reported as deleted, protected, withheld or sensitive — the sub-account must
have "Display media that may contain sensitive content" enabled for the last.

## Ways around the tool

The hook blocks terminal calls whose text names `twscrape`, the plugin
(`x-access`, `x_access`), a `TWS_` variable or the cookies' Keychain item or
scope (`X_READER_COOKIES`, `x-reader`), and file-tool calls on the state
directory (`.x-access`), the item name or the engine venv. File tools may
still read the plugin source and the download folder. It is a pattern match,
not a sandbox. Inbound A2A requests are refused, and the toolset is not in
the Assistant's `a2a` platform toolset.

## Setup

1. `~/.config/hermes/scripts/x-access.sh install`.
2. Create the sub-account; in its X settings enable showing sensitive media.
   Following the main account is not needed while it is public.
3. Sign the sub-account in from a private browser window, copy `auth_token`
   and `ct0` from DevTools → Application → Cookies → `https://x.com`, close
   the window **without logging out** (that ends the session), then
   `secret set X_READER_COOKIES -p hermes --scope x-reader -D COOKIE` and
   paste `auth_token=…; ct0=…` at the hidden prompt. Fresh cookies after a
   refusal are stored the same way; nothing else needs resetting.
4. Set `x_access.main_handle` in the Assistant's `config.yaml`, enable the
   plugin and restart the gateway.

`x-access.sh status` shows the engine, whether the cookies are stored (never
their value) and what the tool last recorded. After bumping the pin,
recompile the lock (command in `requirements.in`) and run `install` again.
