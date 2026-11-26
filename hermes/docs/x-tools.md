# X tools

A read-only view of X (Twitter) for the Assistant, Marketer and Searcher:
posts, searches, threads and conversations, quotes, mentions, timelines,
profiles and follower lists, lists, communities, trends, and (for the
Assistant) a post's photos, videos and GIFs saved to disk. Nothing posts,
replies, likes, follows or sends DMs. It runs on the third-party package
[craft-agent/x-tools](https://github.com/craft-agent/x-tools), the same
release the person's OpenCode loads, and a dotconfig guard adds what this
setup requires of every access plugin. Why the package:
[decision](decisions/x-tools-plugin.md). Common rules:
[access-common.md](access-common.md). Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

`x_search` (xAI's search over X) is a Hermes tool of its own, not this
package's; profiles keep it as the first way to find posts.

## Shape

| Piece                                                            | Home                                                                                                   | Reader                        |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ----------------------------- |
| Tools, approval card, skills, engine                             | the package, installed at `~/.hermes/plugins/x-tools`                                                  | Assistant, Marketer, Searcher |
| The pinned release                                               | `scripts/external-plugins.json`, installed by `scripts/external-plugins.py`                            | people                        |
| Refusal where no person can answer, bypass guard, progress lines | `plugins/guards/x-tools-guard`                                                                         | Assistant, Marketer, Searcher |
| Settings (toolsets, read-only, caps, download folder, guard)     | `plugins.entries.x-tools.settings` in each profile's config                                            | each profile                  |
| How the tools are used                                           | the package's skills, `x-tools:<toolset>`                                                              | each profile                  |
| When the Assistant reads X in Chat                               | the Chat reference `x.md`                                                                              | Assistant                     |
| The post and X Article draft exceptions in the browser           | the Assistant's technics `x-draft-post` and `x-draft-article`                                          | Assistant                     |
| How Marketer reads ranking, results and conversations            | `profiles/marketer/skills/pipeline/references/x-ranking.md`                                            | Marketer                      |
| Ranking watch                                                    | `scripts/x-ranking-watch.py`, `profiles/assistant/scripts/x-ranking-watch.sh`                          | Assistant                     |
| OpenCode                                                         | `opencode/opencode.jsonc` (the npm package), denied in Hermes-driven runs ([opencode.md](opencode.md)) | OpenCode                      |

One implementation serves both harnesses: the Hermes plugin spawns Node on the
package's built `dist/cli.js`, and the OpenCode plugin uses the same state.
Both pin the same release: a test holds `external-plugins.json` and
`opencode.jsonc` to one version.

## Reads and the reading account

Every read tries [FxTwitter](https://github.com/FxEmbed/FxEmbed)'s public API
first and falls back to a **reading account** (a separate sub-account; the
user's main account is only ever a search subject) when FxTwitter has no route
for the read, is down or rate-limited, or the target is protected. Lists,
communities and most trend categories read only the reading account. The
reading account calls the GraphQL endpoints the x.com web app uses, through
[twscrape](https://github.com/vladkens/twscrape) and the sub-account's
`auth_token` and `ct0` cookies. It is not the X API: X's automation rules
forbid non-API automation and the sub-account can be locked or suspended at any
time. The user accepted that risk for a read-only sub-account
([risk acceptance](access-common.md#risk-acceptance)). The main account's
bookmarks, notifications, home timeline and DMs are out of reach by design.

The state lives under `~/.local/state/x-tools/` (mode 0700), shared by every
profile and OpenCode: `accounts/default/` (the `cookies` file, mode 0600, the
pacing record and a handle → id cache), `engine/venv` (the hash-locked Python
and twscrape the package installs), `fxtwitter/` (its pacing record) and
`grants/` (unused while `grants` stays off). The cookies' original stays in
the Keychain as `X_READER_COOKIES` in the `hermes` project under the scope
`x-reader` ([secret scoping](access-common.md#secret-scoping)); the package
reads only its own file, which the person writes from that item
([Setup](#setup)). A session X refuses is remembered by the cookies'
fingerprint and answered locally until the cookies change; a rate-limited
endpoint's end is stored and every read waits for it.

**Caps.** The reading account is paced (5 s apart) and capped at 30 reads an
hour and 200 a day, and FxTwitter at 1000 reads a day; both counts are shared
by every profile and OpenCode. Searcher sets lower caps (`reads_per_hour: 20`,
`reads_per_day: 120`) that the package checks against the same shared count,
so a long sweep stops itself while the Assistant and Marketer keep headroom. A
read past a cap fails as `rate_limited` with the time it frees up, without
contacting X.

Post text, names, bios and links are other people's text: profiles treat them
as data, never as instructions.

## Profiles and toolsets

| Profile   | Toolsets                                                               | Settings                                                      | Inbound A2A |
| --------- | ---------------------------------------------------------------------- | ------------------------------------------------------------- | ----------- |
| Assistant | `account`, `posts`, `users`, `lists`, `communities`, `trends`, `media` | `download_dir: ~/Workspaces/.inbox/x`                         | not served  |
| Marketer  | `account`, `posts`, `users`, `lists`, `communities`, `trends`          | `read_only: true`                                             | reads       |
| Searcher  | `account`, `posts`, `users`                                            | `read_only: true`, `reads_per_hour: 20`, `reads_per_day: 120` | not served  |

Every profile sets `require_plugins: [x-tools-guard]` and `language: ja`.
Which platforms carry the tools is the profile's `platform_toolsets`: the
Assistant's `cli`, `telegram` and `discord` (never `a2a`), Marketer's `cli` and
`a2a` (its inquiry endpoint reads), Searcher's `cli`. `grants` stays off and
`unattended` unset: no job saves media unattended.

`x_media_download` saves photos at original size and the best MP4 of each
video or GIF into `<download_dir>/<post id>/`, reusing files already there;
links, cards, Spaces and live broadcasts are not downloaded. The sub-account
must have "Display media that may contain sensitive content" enabled for such
posts to be readable.

Keep every `X_TOOLS_*` environment variable unset. The Hermes adapter emits no
flag for a `false` or empty setting, so an environment variable would override
the config rather than being cancelled by it.

## Approval and guard

`x_media_download` is the one write the profiles hold. It is held by the
package's own `pre_tool_call` card, which pins what it showed into the call.

The guard (`x-tools-guard`) adds:

- **No card where no person can answer.** Every x-tools tool not named as a
  read (`x_account_read`, `x_post_read`, `x_user_read`, `x_list_read`,
  `x_community_read`, `x_trend_read`, `x_grant_read`) is refused under YOLO,
  `approvals.mode: off`, cron, a single query and the unattended platforms
  (`plugins/_shared/human_gate.py`), and for an inbound A2A request. A new
  x-tools tool fails closed as a write; `x_search` is not the package's and is
  left alone.
- **No way around the tools.** Terminal and file-tool calls are blocked when
  they run `x-tools-cli` or twscrape, reach FxTwitter or its mirrors, carry
  session cookie text, name the package's state, its install, an `X_TOOLS_`
  variable or the cookies' Keychain item or scope; paths are also matched by
  their real path and against the terminal's working directory
  ([bypass guard](access-common.md#bypass-guard-ways-around-the-tool)). Post
  URLs and the download folder stay allowed.
- **Progress lines** that name the operation (the method or a fixed label)
  only, never a search, a handle or a path.

## What the old plugin had and this does not

- **No ledger of the user's own numbers.** The six-hourly snapshot and its
  offline comparison by post age are gone. Marketer reads the public counts of
  the user's posts (`x_post_read` `timeline`) with their read time and compares
  posts read at a similar age; X's own analytics stay in the browser, under
  Marketer's browsing rules.
- **No saved FxTwitter replies.** `x_post_read` `view` checks up to 50 posts a
  call (real author, `handle_mismatch`, status) and returns the posts
  themselves; a corpus is kept by the task from those results.
- **Mentions** search `@<handle> -from:<handle>`; replies that do not name the
  handle are read from the post's `conversation`.

## Ranking watch

A weekly Assistant job (kept in the private overlay, because its delivery names
a chat) runs `profiles/assistant/scripts/x-ranking-watch.sh`, which runs
`scripts/x-ranking-watch.py check` against `scripts/x-ranking-baseline.json`.
It compares the published defaults of
[xai-org/x-algorithm](https://github.com/xai-org/x-algorithm): watched
parameters (weights, cold-start, `Enable*` switches), `MAX_POST_AGE`, Notable
Updates headings, and filter and source files; the daily sync commit alone is
not a change. When values match, the script prints `{"wakeAgent": false}` and
no model runs. When values differ, the report wakes the Assistant, which starts
an OpenCode plan on this repository and opens a Telegram topic with its
proposal, building nothing. A read failure exits 1 and reaches the Inbox as a
failure notice. The baseline is refreshed (`x-ranking-watch.py refresh`) in the
same change that updates `x-ranking.md`, and `scripts/tests/test_x_ranking_watch.py`
holds the two together. The script remembers the last diff it reported under
`HERMES_LOCAL` (`x-ranking-watch/state.json`), stays silent while the diff is
unchanged, reports again when the diff changes, clears the record once values
match the baseline, and `x-ranking-watch.py forget` makes the next run report
again (e.g. after a failed plan).

## Install and update

`scripts/external-plugins.py install` (from the live checkout) runs
`hermes plugins install craft-agent/x-tools --ref <commit> --force --no-deps
--no-enable` for the commit `external-plugins.json` pins; `status` compares the
installed commit with the pin. The release commit carries the built `dist/`;
never install it by hand at another commit or link it from a checkout.

The package's command line is the installed copy,
`node ~/.hermes/plugins/x-tools/dist/cli.js` (written `x-tools-cli` below):
`engine install|status`, `login [--account <label>]` (cookies on stdin) and
`remove --account <label>`. The engine needs `uv` and the plugin Node 24 or
later.

A new release: change `version` and `commit` in `external-plugins.json` and the
npm version in `opencode.jsonc` together, run `scripts/external-plugins.py
install`, then `x-tools-cli engine install` (a release may pin another
twscrape), restart the gateway and `opencode service restart`.

## Setup

Service-specific steps; the rest is in [shared setup](access-common.md#setup-shared).

1. Install the plugin (`scripts/external-plugins.py install`) and the engine
   (`x-tools-cli engine install`).
2. Create the sub-account and enable showing sensitive media in its X
   settings. Sign it in from a private browser window, capture `auth_token`
   and `ct0` from `https://x.com`, and store them as
   `secret set X_READER_COOKIES -p hermes --scope x-reader -D COOKIE`
   (`auth_token=…; ct0=…` at the hidden prompt).
3. Write the package's cookie file from it, in a terminal of your own:
   `secret get X_READER_COOKIES -p hermes --scope x-reader | x-tools-cli login`.
   Repeat after new cookies.
4. Enable `x-tools` and `x-tools-guard` in each profile's private
   `plugins.enabled` (the profile validator refuses the first without the
   second, and without the guard in `require_plugins`), with the profile's
   `x-tools-<toolset>` toolsets in `toolsets` and the platforms above.
5. Restart the gateway; each profile's `x_account_read` checks the engine,
   the cookies and the caps.
