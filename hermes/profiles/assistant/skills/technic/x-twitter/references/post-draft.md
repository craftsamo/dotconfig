# Saving an X post draft in the browser

The second sanctioned browser use on x.com, beside the Article editor. It
writes into the user's main account, so the conditions are strict.

## When

- **Only on request, only approved text.** The user asked, in this
  conversation, for a post (or a thread) to be saved as a draft, and
  approved the exact text and media, the account and whether it is a new
  draft or a replacement of a named one. Approval of an outline or a local
  file alone is not that consent. Opening the composer can autosave, so the
  consent comes first.
- **Disclose the account risk once per job.** X's
  [automation rules](https://help.x.com/en/rules-and-policies/x-automation)
  prohibit scripting the website, and per-post approval or draft-only work is
  not a stated exception. Say so and record the user's decision; it is a risk
  they accept, not X's permission. A challenge or CAPTCHA goes to the user.
- **Stop at a saved draft.** Never press Post, Reply, schedule, or change the
  audience or who can reply. Open nothing else on x.com (timeline, profile,
  notifications, messages, account pages). A thread, a long post or media
  combinations need their own check of what the composer actually offers;
  do not assume them from an ordinary text draft.
- **Report the edges.** What was saved, where to find it, what was not
  verified.

## Before opening X

1. Keep the approved text, every media file (with a hash) and the target
   (new, or the named draft to replace) in the task record.
2. For a replacement, open the draft list first and record the current text
   of the named draft: if it changed since the user approved, ask again.

## Save

1. Open the composer in the user's authenticated browser profile and check
   `page_info()` shows the expected account. Keep one composer tab as the only
   writer for the job; reselect it by target id before every action.
2. Enter only the approved text and media. Read back the whole text, line
   breaks, links and the attachment order before saving. A wording change goes
   back to Writer, never edited here.
3. Find the composer's actual save-as-draft action (closing the composer
   offers it today; check the current UI rather than assuming). Never click an
   ambiguous button to find out what it does.
4. Record the draft as soon as it appears in the list; drafts have no stable
   public id, so keep enough of the text and attachment facts to match it
   unambiguously. Never add a marker to the text to make it findable.

## Prove it saved

1. Reload, open the account's draft list (not browser history) and open the
   same draft. Compare the whole text and every attachment with the approved
   version.
2. Check nothing went out: `x(action="posts")` for the user's own account
   shows no new post with this text. One that did is the incident below.
3. A local composer cache is not a server-side draft, and drafts may not
   follow the user to other devices or the app: say so. If server persistence
   cannot be told apart, report `save-uncertain`, not success.
4. Close every target you opened.

## Recovery

- After an error or a timeout, read the draft list before acting again; the
  save may already have landed. Never create a second draft to recover, and
  never delete one as cleanup.
- Several drafts match: stop and ask which one.
- An unexpected post, reply or other public effect is an incident: stop,
  report the URL and what you know, keep the evidence, and let the user
  decide. Never delete or repost silently.
