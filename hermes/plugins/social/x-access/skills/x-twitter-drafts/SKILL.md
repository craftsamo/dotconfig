---
name: x-twitter-drafts
description: "Use only when the user asked, in this conversation, for an X post or thread to be saved as a draft, or for an X Article draft to be finished, in the browser. Saved drafts only; nothing is ever published."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [x, twitter, x-article, post-draft, browser]
---

# Saving X drafts in the browser

The two exceptions to `x-access:x-twitter`'s rule that the browser stays off
x.com. Each writes into the user's main account and ends at a saved draft the
user asked for; the conditions in each reference are strict.

| Task | Reference |
| --- | --- |
| An ordinary post or a thread, saved as a draft | `references/post-draft.md` |
| An X Article draft the user created, finished in the editor | `references/article-draft.md` |

- Read first, write second. Load `x-access:x-twitter` for the `x` tool's
  mechanics: reading the user's own posts before drafting in their voice, and
  proving after the save that nothing went out.
- Publishing, scheduling, posting, replying, liking, following, DMs and
  account pages stay the user's, whatever the page offers.
- A browser step is not a way around a tool limit. Anything the `x` tool can
  read goes through the tool.
