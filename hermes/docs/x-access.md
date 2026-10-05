# X access

A read-only view of X (Twitter) for the Assistant and Marketer: the user's
main account's posts and mentions, search, threads, profiles, a post's
photos, videos and GIFs, and a ledger of the main account's public counts.
It reads as a separate **sub-account**; the main account is only a search
subject and never signs in here. Nothing posts, replies, likes, follows or
sends DMs. Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

## Shape

| Piece | Home | Reader |
|---|---|---|
| Engine: validation, pacing, session state, result shapes, media download, bypass guard | `plugins/x-access/xa.py` | all |
| One twscrape read per call in the engine venv; reads the cookies | `plugins/x-access/bridge.py` | all |
| `x` tool and the `pre_tool_call` hook (toolset `x_access`) | `plugins/x-access/__init__.py` | Assistant, Marketer |
| Engine venv | `scripts/x-access.sh`, `engines/twscrape/` | people |
| When and how the Assistant uses it | the Assistant's private Chat reference `x.md` | Assistant |
| How Marketer reads ranking, results and conversations | `marketer-pipeline/references/x-ranking.md` | Marketer |

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
days, and what X last made of the session), `call.lock` and the metrics
ledger `metrics.jsonl` (see [Metrics](#metrics)). Both profiles share it, so
the caps below count every read from either.

Because the pool is rebuilt for every call, the engine remembers X's verdicts
itself. When X refuses the session (twscrape marks it inactive: expired,
logged out, locked, suspended), the refusal is stored with a fingerprint of
the cookies (12 hex characters of a SHA-256 of `auth_token`), and every later
read is answered by the bridge without contacting X until the stored cookies
change. When X rate-limits an endpoint, the end of the limit is stored and
every read waits for it.

Each profile's `config.yaml` carries `x_access.main_handle` — the account
`posts` (without `handle`), `mentions`, `snapshot` and `insights` read: the
Assistant's in the private overlay, Marketer's in its tracked config (a
public handle). `x_access.download_dir` is optional; without it media lands
in `<HERMES_HOME>/x-downloads/`.

## Reads

`status` never contacts X: it reports the engine, whether the cookies are
stored, a refusal recorded for them, a running rate limit and the reads used;
`insights` reads only the local ledger. Every other action reaches X and is paced per twscrape read (one read may
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
| `snapshot` | 1 (+1 to resolve an uncached handle) | the main account's recent posts into the ledger |
| `insights` | 0 | the ledger only |

Limits default to 20 (thread 30), at most 50. Results carry local times with
offset, text clipped at 2000 characters (quoted posts 280), reposts as
`repost_of`, media named by type, expanded links and counts, plus a note that
everything in them is other people's text, never instructions. An empty
result carries twscrape's last warnings as `x_warnings`. The list results
(`posts`, `mentions`, `search`, `thread`) carry `read_at`, and counts include
bookmarks.

## Metrics

`snapshot` reads the main account's recent posts once (`limit` 20, at most
50; `replies=true` includes replies) and appends one line per own post to
`~/.x-access/metrics.jsonl` (mode 600): read time, post id and time, age in
hours, views, likes, replies, reposts, quotes, bookmarks, form (video, photo,
link, quote or text), link and reply flags, length and the first 120
characters. Reposts and other authors are skipped, and a protected main
account is refused (the ledger holds public posts only; `user` never caches
a protected account's id, which would skip that check). Once the file passes
4 MB, the next snapshot keeps the last 180 days and, if that is still over
4 MB, halves it from the oldest end until it fits. A damaged line is skipped
on read, and an append cut short is closed before the next one.

The ledger is filled on a schedule: the Assistant's `no_agent` cron job
`x-snapshot` runs `profiles/assistant/scripts/x-snapshot.sh` every six hours
(four reads a day, no model turn). The script calls the engine directly
(`xa.py snapshot <profile home>`) with the profile home taken from its own
path, never `$HERMES_HOME`, which the multiplex gateway may set to another
profile. It prints nothing on success or on a pause (the next run catches
up) and exits nonzero on a real failure, so Hermes alerts on Telegram. Like
every cron job ([README "Cron"](../README.md#cron)) the job entry itself is
machine-local; create it once with:

```sh
hermes -p assistant cron create "0 */6 * * *" --name x-snapshot --no-agent \
  --script x-snapshot.sh --deliver telegram
```

`insights` never contacts X. It compares posts of the last `days` (30, at
most 180) at one age, `at` = 6, 24 or 48 hours, taking each post's
observation nearest that age within a tolerance (a quarter of the age, at
least 3 hours): data health (posts, observations, comparable, too young, no
snapshot near the age), a baseline, medians of views, engagement rate,
replies and bookmarks by form, link, length and local posting hour (groups
under five posts are flagged inconclusive), and the top and bottom three.
`post` returns one post's trajectory instead. The result restates that these
are public counts, not the ranking score, and that differences are
hypotheses.

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
not a sandbox.

Inbound A2A requests are refused on the Assistant (the toolset is not in its
`a2a` platform toolset either). Marketer's endpoint is inquiry-only and may
read: the tool is in its `a2a` toolset, and the plugin allows an inbound
request only when the turn's bound profile home is Marketer's, failing
closed otherwise. The plugin registers per profile, so each profile's
handler and hook carry their own profile name.

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
4. Set `x_access.main_handle` in the Assistant's and Marketer's
   `config.yaml`, enable the plugin in both and restart the gateway.
5. Create the `x-snapshot` cron job ([Metrics](#metrics)).

`x-access.sh status` shows the engine, whether the cookies are stored (never
their value) and what the tool last recorded. After bumping the pin,
recompile the lock (command in `requirements.in`) and run `install` again.
