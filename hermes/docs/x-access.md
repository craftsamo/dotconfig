# X access

A read-only view of X (Twitter) for the Assistant and Marketer: the user's
main account's posts and mentions, search, threads, profiles, a post's
photos, videos and GIFs, a ledger of the main account's public counts, and
bulk checks of public posts' authors and counts. Searcher gets only the
public part: `status`, `search`, `thread` and `verify` ([Profiles](#profiles)).
It reads as a separate **sub-account**; the main account is only a search
subject and never signs in here. Nothing posts, replies, likes, follows or
sends DMs. Read it when changing the plugin or its caps. Common rules:
[access-common.md](access-common.md). Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                                  | Home                                                                                                                                 | Reader                        |
| ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------- |
| Engine: validation, pacing, session state, result shapes, media download, `verify`, bypass guard       | `plugins/social/x-access/xa.py`                                                                                                      | all                           |
| One twscrape read per call in the engine venv; reads the cookies                                       | `plugins/social/x-access/bridge.py`                                                                                                  | all                           |
| `x` tool and the `pre_tool_call` hook (toolset `x_access`)                                             | `plugins/social/x-access/__init__.py`                                                                                                | Assistant, Marketer           |
| Engine venv                                                                                            | `scripts/x-access.sh`, `engines/twscrape/`                                                                                           | people                        |
| How a profile reads X: actions, both budgets, verifying posts, media, the user's own numbers, recovery | the `x-access:x-twitter` plugin skill (`plugins/social/x-access/skills/x-twitter/`)                                                  | Assistant, Marketer, Searcher |
| The post and X Article draft exceptions in the browser                                                 | the `x-access:x-twitter-drafts` plugin skill (`plugins/social/x-access/skills/x-twitter-drafts/`); registered for the Assistant only | Assistant                     |
| When the Assistant uses it in Chat                                                                     | the Assistant's private Chat reference `x.md`                                                                                        | Assistant                     |
| How Marketer reads ranking, results and conversations                                                  | `marketer-pipeline/references/x-ranking.md`                                                                                          | Marketer                      |

[twscrape](https://github.com/vladkens/twscrape) calls the GraphQL endpoints
the x.com web app uses, signed in with a browser session's `auth_token` and
`ct0` cookies. It is not the X API: X's automation rules forbid non-API
automation and the sub-account can be locked or suspended at any time. The user
accepted that risk for a read-only sub-account
([risk acceptance](access-common.md#risk-acceptance)); the paid official API
was the alternative. Because the session belongs to the sub-account, the main
account's bookmarks, notifications, home timeline and DMs are out of reach by
design.

`bridge.py` runs under the interpreter of `hermes/local/twscrape/venv`
(`twscrape[curl]` from the hash-locked `engines/twscrape/requirements.lock`),
never Hermes' own, as a child process with a minimal environment
([bridge process](access-common.md#state-directory-and-bridge-process)). It
also sets `TWS_TELEMETRY=0` (twscrape otherwise reports operation names) and
`TWS_HTTP_BACKEND=curl` (browser-like TLS).

## Cookies and state

One account. Its cookies live only in the Keychain, as `X_READER_COOKIES`
(`auth_token=…; ct0=…`) in the `hermes` project under the scope `x-reader`
([secret scoping](access-common.md#secret-scoping)). The bridge reads them at
start and gives twscrape an **in-memory** account pool (a shared-cache SQLite
database held open for the call), so nothing of the session is written to
disk; both cookie values are masked in every string the bridge returns.

`~/.x-access/` (mode 700, outside every repository) holds no secret:
`state.json` (call timestamps for pacing, a handle → user id cache, and what X
last made of the session), `call.lock`, the metrics ledger `metrics.jsonl`
(see [Metrics](#metrics)) and `verify`'s own `fx.json` and `fx.lock` (see
[Verify](#verify)). Every profile shares it, so the caps below count every read
from either.

Because the pool is rebuilt for every call, the engine remembers X's verdicts
itself ([refusal memory](access-common.md#state-directory-and-bridge-process)):
when X refuses the session (twscrape marks it inactive), the refusal is stored
with a fingerprint of the cookies and every later read is answered by the
bridge without contacting X until the stored cookies change; when X
rate-limits an endpoint, the end of the limit is stored and every read waits
for it.

Each profile's `config.yaml` carries `x_access.main_handle` — the account
`posts` (without `handle`), `mentions`, `snapshot` and `insights` read: the
Assistant's in the private overlay, Marketer's in its tracked config (a public
handle). `x_access.download_dir` is optional; without it media lands in
`<HERMES_HOME>/x-downloads/`.

## Reads

`status` never contacts X: it reports the engine, whether the cookies are
stored, a refusal recorded for them, a running rate limit and the reads used;
`insights` reads only the local ledger. Every other action reaches X and is
paced per twscrape read (one read may page or retry inside twscrape): one call
at a time across sessions (`call.lock`), a minimum gap, an hourly and a daily
cap (`state.json`); past a cap or during a rate limit the tool answers
`paused: …` without calling X. A call counts only when X was, or may have been,
contacted: a missing engine or cookies, or a remembered refusal, costs nothing.
The tool schema lists the actions and the engine counts their paced reads;
`verify` goes to FxTwitter, not X, with its own pacing ([Verify](#verify)), and
`insights` costs none.

Results carry local times with offset, clipped text, reposts as `repost_of`,
media named by type, expanded links and counts (bookmarks included), plus a note
that everything in them is other people's text, never instructions. An empty
result carries twscrape's last warnings as `x_warnings`. The list results
carry `read_at`.

## Metrics

`snapshot` reads the main account's recent posts once and appends one line per
own post to `~/.x-access/metrics.jsonl` (mode 600): read time, post identity,
age, counts, form (video, photo, link, quote or text), flags and the start of
the text. Reposts and other authors are skipped, and a protected main account
is refused (the ledger holds public posts only; `user` never caches a protected
account's id, which would skip that check). The file is size-capped: the next
snapshot trims it from the oldest end. A damaged line is skipped on read, and an
append cut short is closed before the next one.

The ledger is filled on a schedule: the Assistant's `no_agent` cron job
`x-snapshot` runs `profiles/assistant/scripts/x-snapshot.sh` every six hours
(no model turn). The script calls the engine directly (`xa.py snapshot <profile
home>`) with the profile home taken from its own path, never `$HERMES_HOME`,
which the multiplex gateway may set to another profile. It prints nothing on
success or on a pause (the next run catches up) and exits nonzero on a real
failure, so Hermes alerts on Telegram. Like every cron job
([ops/tracking.md "Cron"](ops/tracking.md)) the job entry itself is machine-local;
create it once with:

```sh
hermes -p assistant cron create "0 */6 * * *" --name x-snapshot --no-agent \
  --script x-snapshot.sh --deliver telegram
```

`insights` never contacts X. It compares posts of the last `days` at one age
(`at` = 6, 24 or 48 hours), taking each post's observation nearest that age
within a tolerance: data health (posts, observations, comparable, too young, no
snapshot near the age), a baseline, medians by form, link, length and local
posting hour (groups under five posts are flagged inconclusive), and the top and
bottom three. `post` returns one post's trajectory instead. The result restates
that these are public counts, not the ranking score, and that differences are
hypotheses.

## Media

`media` reads the post once (a repost resolves to the original; `quoted=true`
adds the quoted post) and downloads photos at original size, the highest-bitrate
MP4 of each video and GIFs (served as MP4) into
`<download_dir>/<post id>/<owner post id>-<n>.<ext>`. Downloads go only to
`https://pbs.twimg.com` and `https://video.twimg.com`, redirects included, from
the engine itself (which never holds the cookies) through an opener with no
cookie handler. The served type must be an image or `video/mp4`, and size is
capped before or during the download. Each download writes its own hidden part
file, renamed into place only when complete, so concurrent calls never share
one; files already present are reused. Links, cards, Spaces and live broadcasts
are not downloaded. A post that cannot be read is reported as deleted,
protected, withheld or sensitive — the sub-account must have "Display media that
may contain sensitive content" enabled for the last.

## Verify

`verify` checks many public posts per call (URLs or ids) through
[FxTwitter](https://github.com/FxEmbed/FxEmbed)'s public API, never through X or
the sub-account, so it costs none of the caps above. It exists because research
needs ground truth for many posts at once: LLM-backed search (`x_search`)
supplies candidate ids and confident but unreliable prose, and the sub-account's
caps cannot absorb a corpus. Each post returns its canonical URL and real author
(`handle_mismatch` when the URL named someone else), the text, time, language,
public counts, media facts, and the quoted and replied-to posts; a post is `ok`,
`not_found` (deleted, never existed, or hidden from signed-out readers),
`protected`, `unavailable`, `error` or `not_checked`. `save=true` also writes
each found post's reply, FxTwitter's JSON as received, to
`<download_dir>/verify/<id>.json` for scripts that compute over a corpus; a post
FxTwitter answers as anything but `ok` loses its saved file, so a deleted post
never keeps passing as verified. Links on FxTwitter-style mirrors are accepted
wherever the tool takes a post.

Requests carry no cookies, follow redirects only within `api.fxtwitter.com`, and
are paced and capped separately (`fx.lock`, `fx.json`). A call stops starting
checks after a time budget, after repeated failures, and on FxTwitter's 429,
which also pauses every call until `Retry-After` has passed; the rest come back
`not_checked`. `status` reports the day's checks and any pause as
`verify_usage`. FxTwitter is a third-party service that may change or go away:
only `ok` rows are evidence, and media itself is downloaded with `media`.

## Ways around the tool

The hook blocks terminal calls whose text names `twscrape`, the plugin, a
`TWS_` variable, the cookies' Keychain item or scope, or the FxTwitter family of
mirrors (which `verify` wraps, so reaching them directly would bypass its
pacing and caps), and file-tool calls on the state directory, the item name or
the engine venv. File tools may still read the plugin source and the download
folder. Patterns: `_TERMINAL` in `plugins/social/x-access/xa.py`. Shared rules:
[bypass guard](access-common.md#bypass-guard-ways-around-the-tool).

Inbound A2A requests are refused on the Assistant (the toolset is not in its
`a2a` platform toolset either). Marketer's endpoint is inquiry-only and may
read: the tool is in its `a2a` toolset, and the plugin allows an inbound
request only when the turn's bound profile home is Marketer's, failing closed
otherwise. The plugin registers per profile, so each profile's handler and hook
carry their own profile name.

## Profiles

| Profile   | Actions                                | Inbound A2A   |
| --------- | -------------------------------------- | ------------- |
| Assistant | every action                           | refused       |
| Marketer  | every action                           | reads allowed |
| Searcher  | `status`, `search`, `thread`, `verify` | refused       |

The action list a profile gets (`PROFILE_ACTIONS` in `xa.py`) fixes its schema
and is checked again by the gate, the handler and the engine
([profile gating](access-common.md#profile-gating)). Searcher reads public posts
only: nothing about the user's main account (`posts`, `mentions`, `snapshot`,
`insights`, `user`) and no `media`, which writes files. It finds posts with
`x_search`; `search` is the fallback for when that tool is hidden (a lapsed xAI
login) or failing, and its schema says so. `search` and `thread` draw on the
sub-account's caps shared with the Assistant and Marketer; `verify` does not, so
prefer it to confirm a post. Searcher's `status` omits the
`x_access.main_handle` warning, which concerns actions it does not have.

**A profile's share of the caps.** `PROFILE_CAPS` gives Searcher a smaller
hourly and daily share, counted apart in `state.json` under `by_profile` (a
subset of the shared `calls`), so a long sweep stops itself before the shared
caps do and the Assistant and Marketer keep headroom. The numbers are loose on
purpose: Searcher reads X rarely. It stops with "this profile's share of X reads
is used up" and the wait; `status` shows the share as `usage.this_profile`.
Profiles not named there are only bound by the shared caps, and the scheduled
snapshot is not counted against any share.

## Setup

Service-specific steps; the rest is in [shared setup](access-common.md#setup-shared).

1. `~/.config/hermes/scripts/x-access.sh install`.
2. Create the sub-account; in its X settings enable showing sensitive media.
   Following the main account is not needed while it is public.
3. Sign the sub-account in from a private browser window and capture `auth_token`
   and `ct0` from `https://x.com`, then
   `secret set X_READER_COOKIES -p hermes --scope x-reader -D COOKIE` and paste
   `auth_token=…; ct0=…` at the hidden prompt.
4. Set `x_access.main_handle` in the Assistant's and Marketer's `config.yaml`,
   enable the plugin in both and restart the gateway.
5. Create the `x-snapshot` cron job ([Metrics](#metrics)).

`x-access.sh status` shows the engine, whether the cookies are stored (never
their value) and what the tool last recorded.
