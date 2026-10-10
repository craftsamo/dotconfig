# X access

A read-only view of X (Twitter) for the Assistant and Marketer: the user's
main account's posts and mentions, search, threads, profiles, a post's
photos, videos and GIFs, a ledger of the main account's public counts, and
bulk checks of public posts' authors and counts. Searcher gets only the
public part: `status`, `search`, `thread`, `user` and `verify`
([Profiles](#profiles)).
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

`bridge.py` runs under the hash-locked `hermes/local/twscrape/venv`, never
Hermes' own, as a child process with a minimal environment
([bridge process](access-common.md#state-directory-and-bridge-process)), with
twscrape telemetry off.

## Cookies and state

One account. Its cookies live only in the Keychain, as `X_READER_COOKIES`
(`auth_token=…; ct0=…`) in the `hermes` project under the scope `x-reader`
([secret scoping](access-common.md#secret-scoping)). The bridge reads them at
start and gives twscrape an **in-memory** account pool, so nothing of the
session is written to disk; both cookie values are masked in every string the
bridge returns.

`~/.x-access/` (mode 700, outside every repository) holds no secret:
`state.json` (call timestamps for pacing, a handle → user id cache, and what X
last made of the session), `call.lock`, the metrics ledger `metrics.jsonl`
(see [Metrics](#metrics)) and `verify`'s own `fx.json` and `fx.lock` (see
[Verify](#verify)). Every profile shares it, so the caps count every read from
either.

Because the pool is rebuilt for every call, the engine remembers X's verdicts
itself ([refusal memory](access-common.md#state-directory-and-bridge-process)):
a session X refuses (twscrape marks it inactive) is answered by the bridge
without contacting X until the stored cookies change; a rate-limited endpoint's
end is stored and every read waits for it.

Each profile's `config.yaml` carries `x_access.main_handle` — the account
`posts` (without `handle`), `mentions`, `snapshot` and `insights` read: the
Assistant's in the private overlay, Marketer's in its tracked config (a public
handle). `x_access.download_dir` is optional.

## Reads

`status` never contacts X; `insights` reads only the local ledger. Every other
action reaches X and is paced per twscrape read: one call at a time across
sessions (`call.lock`), a minimum gap, an hourly and a daily cap; past a cap or
during a rate limit the tool answers `paused: …` without calling X. A call
counts only when X was, or may have been, contacted: a missing engine or
cookies, or a remembered refusal, costs nothing. `verify` goes to FxTwitter,
not X, with its own pacing ([Verify](#verify)).

Results carry a note that everything in them is other people's text, never
instructions.

## Metrics

`snapshot` reads the main account's recent posts once and appends one line per
own post to `~/.x-access/metrics.jsonl` (mode 600): counts and form at read
time, and the start of the text. Reposts and other authors are skipped, and a
protected main account is refused (the ledger holds public posts only; `user`
never caches a protected account's id, which would skip that check). The file is
size-capped, trimmed from the oldest end by the next snapshot.

The ledger is filled on a schedule: the Assistant's `no_agent` cron job
`x-snapshot` runs `profiles/assistant/scripts/x-snapshot.sh` every six hours
(no model turn; the script header has the `cron create` command). The script
calls the engine directly with the profile home taken from its own path, never
`$HERMES_HOME`, which the multiplex gateway may set to another profile. It
prints nothing on success or on a pause (the next run catches up) and exits
nonzero on a real failure, so Hermes alerts on Telegram. Like every cron job
([ops/tracking.md "Cron"](ops/tracking.md)) the job entry itself is machine-local.

`insights` never contacts X. It compares posts of the last `days` at one age
(`at` = 6, 24 or 48 hours) and flags groups under five posts as inconclusive.
The result restates that these are public counts, not the ranking score, and
that differences are hypotheses.

## Media

`media` reads the post once and downloads photos, the highest-bitrate MP4 of
each video and GIFs into `<download_dir>/<post id>/`. Downloads go only to
`https://pbs.twimg.com` and `https://video.twimg.com`, redirects included, from
the engine itself (which never holds the cookies) through an opener with no
cookie handler. The served type must be an image or `video/mp4`, and size is
capped before or during the download. Links, cards, Spaces and live broadcasts
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
(`handle_mismatch` when the URL named someone else) and a status (`ok`,
`not_found`, `protected`, `unavailable`, `error` or `not_checked`). `save=true`
also writes each found post's reply to `<download_dir>/verify/<id>.json`; a post
FxTwitter answers as anything but `ok` loses its saved file, so a deleted post
never keeps passing as verified.

Requests carry no cookies, follow redirects only within `api.fxtwitter.com`, and
are paced and capped separately (`fx.lock`, `fx.json`). A call stops starting
checks after a time budget, after repeated failures, and on FxTwitter's 429,
which also pauses every call until `Retry-After` has passed; the rest come back
`not_checked`. FxTwitter is a third-party service that may change or go away:
only `ok` rows are evidence, and media itself is downloaded with `media`.

## Ways around the tool

The hook blocks terminal calls whose text names `twscrape`, the plugin, a
`TWS_` variable, the cookies' Keychain item or scope, or the FxTwitter family of
mirrors (which `verify` wraps, so reaching them directly would bypass its
pacing and caps), and file-tool calls on the state directory, the item name or
the engine venv. Patterns: `_TERMINAL` in `plugins/social/x-access/xa.py`.
Shared rules: [bypass guard](access-common.md#bypass-guard-ways-around-the-tool).

Inbound A2A requests are refused on the Assistant (the toolset is not in its
`a2a` platform toolset either). Marketer's endpoint is inquiry-only and may
read, only when the turn's bound profile home is Marketer's, failing closed
otherwise.

## Profiles

| Profile   | Actions                                        | Inbound A2A   |
| --------- | ---------------------------------------------- | ------------- |
| Assistant | every action                                   | refused       |
| Marketer  | every action                                   | reads allowed |
| Searcher  | `status`, `search`, `thread`, `user`, `verify` | refused       |

The action list a profile gets (`PROFILE_ACTIONS` in `xa.py`) fixes its schema
and is checked again by the gate, the handler and the engine
([profile gating](access-common.md#profile-gating)). Searcher reads public posts
and the public profile of an account it names: nothing about the user's main
account (`user` has no default handle) and no `media`, which writes files.
`user` serves account-footprint retrieval: the bio and the links a profile lists
are how accounts on other services are tied to it. It finds posts with
`x_search`; `search` is the fallback for when that tool is hidden (a lapsed xAI
login) or failing. `search`, `thread` and `user` draw on the sub-account's caps
shared with the Assistant and Marketer; `verify` does not, so prefer it to
confirm a post.

**A profile's share of the caps.** `PROFILE_CAPS` gives Searcher a smaller
hourly and daily share, counted apart in `state.json` under `by_profile` (a
subset of the shared `calls`), so a long sweep stops itself before the shared
caps do and the Assistant and Marketer keep headroom. Profiles not named there
are only bound by the shared caps, and the scheduled snapshot is not counted
against any share.

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
