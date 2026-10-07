---
name: zenn-dev
description: "Use for Zenn (zenn.dev) work: reading articles, or saving an agreed personal Article as an unpublished draft in the browser and proving it saved."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [zenn, zenn-dev, article, draft, browser]
    category: technic
---

# Zenn through the browser

Task skills (an article, a marketing job) own what goes on Zenn. This skill
owns how it is read and how an agreed draft is saved. When a task skill names
the text, the images or the draft, follow it; the mechanics below still apply.

## Contract

- **Reads first through the web tools.** Public articles, likes and comments
  are public pages: web extract before the browser. There is no Zenn tool.
- **The browser writes only an agreed draft.** Your authenticated browser
  profile is logged in to the user's account. It saves an unpublished
  personal Article the user approved, nothing else: no publishing,
  scheduling, Publication association, preview-sharing toggle, profile or
  settings change, like, comment or follow.
- **Personal Articles only.** Not Scraps, Books or GitHub-synchronized
  content, and never a repository commit as a substitute. Creating an article
  affiliated with a Publication can notify other members even unpublished: a
  Publication is a separate decision for the user.
- **Words are Writer's.** Writer supplies the article and its code; you enter
  it as written. Deciding topics, timing and reading the numbers is
  Marketer's advice. Wording changes go back to Writer, never edited here.

## Before opening the editor

1. **Exact consent.** The user approved, in this conversation, the exact
   Markdown, every image (with a hash), the account, and new versus a named
   existing draft. Opening a new editor can itself create a draft, so the
   consent comes first.
2. **A replacement starts from the live draft.** Open the named draft from
   article management, record its current content and slug, and ask again
   if it changed since the user approved.
3. **Representation.** Keep code fences with their language, indentation,
   links, images and supported embeds. An unsupported required asset or
   construct is reported back, never silently removed.

## Save

1. Open the editor in your authenticated profile; check `page_info()` shows
   the expected account. Signed out, or another account: stop and ask the
   user to sign in to your own Brave profile; never use Marketer's browser
   and never type credentials yourself. Keep one editor tab as the only writer; reselect it
   by target id before every action.
2. Enter only the approved content. Read back headings, code blocks, links and
   image placement.
3. Inspect the current save controls and save explicitly (the official editor
   documents Cmd/Ctrl+S) after verifying editor focus; do not assume autosave.
   Never click an ambiguous button to find out what it does.
4. Record the article slug or editor locator as soon as it exists. Do not
   guess a URL, and do not treat a public-shaped URL as a published result.

## Prove it saved

1. Reload, open the same draft from article management and compare title,
   body, code and images with the approved version.
2. Check the rendered preview without enabling link sharing. Inspect the
   preview's sharing scope rather than presuming it private, and confirm the
   draft is unpublished and has no Publication.
3. Report `draft-created`, `draft-updated`, `save-uncertain` or `blocked`
   with the slug, what was checked and what stays unverified. Close every
   target you opened.

## Recovery

- After an error or a timeout, look in article management before acting
  again; never create a second draft to recover, and never delete one as
  cleanup.
- Several drafts match: stop and ask.
- An unexpected publication, notification or shared link is an incident:
  stop, report what you know, keep the evidence, and let the user decide.

## Sources

- [Editor guide](https://zenn.dev/zenn/articles/editor-guide)
- [Article identity](https://zenn.dev/zenn/articles/what-is-slug)
- [Markdown](https://zenn.dev/zenn/articles/markdown-guide)
- [Draft preview sharing](https://info.zenn.dev/2024-10-15-draft-preview-share)
- [Publication behavior](https://zenn.dev/zenn/articles/how-to-use-publication)

Reviewed 2026-09-10. The save path has no approved live trial yet: treat the
first save as a trial and report what the current editor actually showed.
