# Substack

Load `skill_view(name="substack-access:substack")` before any Substack work:
it owns the mechanics — the `substack` tool only (never the terminal, the
cookies or substack.com in the browser), paced reads, which action to read
with, and recovery. Every write (drafts, releases, scheduling, Notes, each on
an approval card) is `skill_view(name="substack-access:substack-drafts")`.
This file holds only what is particular to Chat.

Marketing work (a campaign, a series of posts) goes through Plan and Execute
marketing, which consults Marketer on strategy and saves its drafts with the
`substack` tool under the writing rules, never publishing or scheduling them.
Inline here are the user's own direct requests ("この記事を下書きにして", "あの下書きを
明日 9 時に予約して").
