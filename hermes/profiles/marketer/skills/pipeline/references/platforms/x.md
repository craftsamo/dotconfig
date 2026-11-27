# X: posts, threads and Articles

## What a recommendation must know

An ordinary Post, a thread and an X Article are different destinations with
different reach and length; do not treat an Article as an automatic substitute
for a post or assume long-post entitlements. Writer owns the text; the
Assistant saves drafts the user approves and the user posts. Ranking facts,
review lenses and discovery live in [X ranking](../x-ranking.md).

The [automation rules](https://help.x.com/en/rules-and-policies/x-automation)
prohibit non-API automation such as scripting the website; per-post approval or
draft-only work is not a stated exception (reviewed 2026-09-10). When a plan
relies on browser-saved X drafts, disclose this account risk and let the user
decide; do not describe that choice as X permission. Recheck material policy
changes rather than promising compliance.

## Reading

Use the x-tools read tools for X: `x_post_read` (`view` for public counts of up
to 50 posts, `timeline` with `@craftsamo` for the client's own posts,
`conversation`, `thread`, `search`, `quotes`, `mentions`), `x_user_read` (`view`
for a profile), `x_list_read`, `x_community_read`, `x_trend_read`, and
`x_account_read`. Reads try FxTwitter first and fall back to the reading
account (paced and capped, shared with the Assistant and Searcher); there is no
stored history of past counts, so record `read_at` with each observation. The
mechanics (methods, budgets, failures) live in `skill_view(name="x-tools:posts")`
(and `x-tools:users`, `x-tools:account`, `x-tools:lists`, `x-tools:communities`,
`x-tools:trends` as needed).
The browser on x.com is logged in to the user's account, and scripted
activity there risks it under the rules above. Open it only for what the tools
cannot show (the account's own analytics), when the user has decided to
accept that risk for this reading, following [browsing](../browsing.md):
analytics pages only, never the timeline, composer, notifications or messages.

Published content is read-only for result collection. Record only metrics the
tools actually expose; likes and views do not establish unique readers, link
clicks or revenue attribution.

## Sources and status

Reviewed 2026-09-10 (automation rules) and 2026-11-01 (ranking, in
[X ranking](../x-ranking.md)). Recheck before a recommendation depends on them.
