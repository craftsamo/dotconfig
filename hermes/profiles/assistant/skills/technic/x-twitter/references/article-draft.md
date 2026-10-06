# Finishing an X Article draft in the browser

The one sanctioned browser use on x.com. It writes into the user's main
account, so the conditions are strict.

## When

- **Only on request.** The user asked, in this conversation, for a specific
  X Article draft to be finished or edited in the editor: an edit URL, or a
  draft they name. Writing or revising an article otherwise ends with the
  Markdown and images delivered to the user, who pastes them.
- **Stop at a saved draft.** Never press publish or schedule, and never
  change the audience or paid settings. Open nothing else on x.com
  (timeline, profile, notifications, account pages).
- **Report the edges.** Say what changed, what was left alone, any wrong
  insertion and how it was reverted, and what you could not verify.

## Before opening X

1. **One canonical source.** Keep the title, headings, body, image markers
   (`[IMAGE: chart.png — what it shows]`), source URLs and any comparison
   table as pipe rows in one local Markdown file. Strip the H1 (it goes into
   the title field) and `## ` from headings for paste. Omit blank separator
   lines unless the author wants visual spacers: X supplies paragraph
   margins, and empty blocks look double-spaced.
2. **Expected state.** From that file compute the non-empty prose lines, the
   heading list, the image-marker list and each table's cell matrix. These
   become the reload assertions.
3. **The live draft outranks the file.** If the author edited the draft
   after the file was written, the live draft is the source of truth.

## The editor

X's article editor is Draft.js, not a textarea:

- Images and tables are atomic blocks; pasted newlines become text blocks.
- Whole-body paste keeps the characters but drops inline bold, italic and
  links.
- A DOM-only selection or `document.execCommand` can change the visible DOM
  without updating Draft's state, so autosave restores the old text or acts
  on a stale block. Prefer native clicks and keys through CDP.
- Two hidden `input[data-testid="fileInput"]` inputs exist. The inline-media
  one has `video/mp4` in its `accept`; the image-only one replaces the cover.
  Rediscover inputs for every upload instead of caching node ids.
- Subheadings carry the class `longform-header-two`.
- Preview counts the cover as an image, and X may proxy a 1600×900 image to
  a smaller 16:9 size; check aspect ratio, count and rendering, not source
  pixels.

## Open and freeze

1. Open the edit URL with the user's authenticated browser profile, then
   check `page_info()`: a blank or different tab is a navigation issue, not a
   corrupt draft or a signed-out session.
2. Snapshot the **whole** draft before any change: ordered block text, type
   and HTML, headings and lists, media identity and order, table cells, and
   inline bold, italic and link ranges. Diff it against the previous snapshot
   and freeze every changed span; the author may have edited past the spot
   they mentioned.
3. Keep one editor tab as the only writer for the whole task.

## Choose the smallest mutation

Edit one paragraph or one figure in place when that is the request. Rebuild
the body only when most of the prose actually changed: whole-body paste
discards inline formatting.

### A paragraph span

1. Find the exact first and last target text nodes. Use DOM Range geometry
   only to measure caret coordinates.
2. `click_at_xy(x, y)` at the start caret. Scroll and remeasure the end, then
   Shift-click it with `cdp('Input.dispatchMouseEvent', ...)` (`modifiers=8`,
   `button='left'`, `clickCount=1`, pressed and released).
3. Read `getSelection()` and require the exact text and endpoints; abort if
   it differs. Coordinates measured before a scroll are not reusable.
4. Dispatch one bubbling, cancelable `ClipboardEvent('paste')` to the focused
   editor whose `DataTransfer` carries escaped `text/html` (for example one
   `<p>`) and `text/plain`. If the editor rejects it, do not fall back to
   whole-body plain text.
5. Read the result back at once: only the authorized span changed, the
   neighbours and retained emphasis are intact.

### One image

1. To replace, scope `メディアを削除` to that inline-image block only, then
   re-read the block sequence: deletion can leave an empty block and change
   block ids. Re-find later targets by content and neighbours.
2. Place the caret natively. After a paragraph: a collapsed range at its last
   text node, then one Enter. Before a heading: click its first character,
   then Command+ArrowLeft (`modifiers=4`), Enter, ArrowUp. Check the
   selection before going on.
3. `button[aria-label="メディアを追加"]` → the `role=menuitem` whose text is
   `メディア` → `DOM.setFileInputFiles` on the inline-media input.
4. Wait for the image, then read the blocks immediately before and after it.
   An upload can land after a heading it belonged before; if so, remove only
   that image and reinsert. One image at a time.
5. Do not retry on a single DOM-count timeout: uploads can finish late. Reload
   and count first, or the image is duplicated.

### Rebuilding the body

1. **Clear without a hidden tail.** Delete every inline image and every
   native table through its own block control first; only then select all
   and delete. Atomic blocks end a select-all range, leaving the old version
   below the new one. Confirm the selection started in the body, not the
   title, and that the body is empty before pasting.
2. **Paste as blocks.** Grant clipboard access and paste through Chromium's
   command; one bulk `Input.insertText` puts the article into a single block:

   ```python
   cdp('Browser.grantPermissions', origin='https://x.com',
       permissions=['clipboardReadWrite', 'clipboardSanitizedWrite'])
   js('(async()=>{await navigator.clipboard.writeText('+json.dumps(body)+');return true})()')
   cdp('Input.dispatchKeyEvent', type='keyDown', key='v', code='KeyV',
       modifiers=4, commands=['Paste'])
   cdp('Input.dispatchKeyEvent', type='keyUp', key='v', code='KeyV', modifiers=4)
   ```

   Then check the first and last lines, a plausible block count, every image
   marker and raw table row once, and a title field holding only the title.

3. **Headings.** For each heading, scroll its block into view, click it,
   open the block-style menu and choose `小見出し`; verify the class. A
   programmatic range alone can format an older block.
4. **Image markers.** For each marker in order: walk the marker block's text
   nodes with `TreeWalker(NodeFilter.SHOW_TEXT)`, select first to last node,
   delete, confirm it is gone, then insert media as above. Selecting only the
   first text node leaves most of a split marker behind.
5. **Native tables.** A pasted pipe table stays raw text. At its position
   choose `挿入 → 表` with the exact rows (header included) and columns, open
   `ブロックを編集`, set the dialog's textarea to the full pipe table and press
   `更新`. Verify the whole cell matrix, then remove the raw rows: select from
   the first row's text node to the last row's and send a real Backspace
   through CDP. Check every block that starts and ends with `|`, not just the
   header.

## Prove it saved

1. Watch the visible save status change to a fresh saved state; elapsed time
   is not proof.
2. Issue a real `cdp('Page.reload')` (same-URL SPA navigation is not a
   reload) and assert in the editor: exact title; ordered headings with no
   empty heading blocks; every canonical prose line; inline-media count and
   order; each table's cell matrix; no `[IMAGE` text and no `^\|.*\|$` rows;
   no unintended empty blocks; inline formatting and lists unchanged against
   the snapshot outside the edited span; the intended ending.
3. Open Preview and repeat the structural checks. Capture the opening and
   each changed figure or table at native scale with
   `print(capture_screenshot())` and look at them: DOM checks miss oversized
   gaps, clipped headers and unreadable wrapping.
4. Close every target you opened. Report the exact scope completed: a
   finished introduction is not a deployed article.

## Recovery

- After an error, read the reloaded state before acting again. A paste or
  upload may already have landed; replaying it duplicates.
- Cmd+Z right after a wrong insertion is the cheapest revert; confirm it
  against the block snapshot.
- A target that stalls after a file chooser or long input: stop mutating it,
  close every stale editor target so two Draft sessions cannot overwrite each
  other's autosaves, open the edit URL once in a fresh session and continue
  from the server-saved blocks.
- If the browser harness is the stalled layer but its browser is alive, a
  bounded direct-CDP repair may use the profile's current
  `DevToolsActivePort` and the target's `webSocketDebuggerUrl`; never assume
  a fixed port. Reload and verify afterwards.
- Keep recovery proportional: fix the failed boundary, and stop building
  editing tools once the needed operation works.
