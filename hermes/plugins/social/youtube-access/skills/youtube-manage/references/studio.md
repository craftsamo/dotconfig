# Studio settings in the browser

Only for what the `youtube` tool cannot change: the channel's name, handle,
profile picture, banner, links, contact email, home-tab layout (featured
video and sections) and upload defaults. Anything `channel_update`,
`update`, `watermark` or the playlist actions can do goes through the tool,
never Studio. Only in a live conversation with the user who asked — never in
cron, a single query, an inbound A2A request or a delegated task.

There is no approval card on this path: the `clarify` answer is the
confirmation, so it is asked for every single change.

## Steps

1. Open `https://studio.youtube.com` in the browser. The browser is signed in
   as the user; if it shows a sign-in page, stop and ask the user to sign in
   to YouTube in the "Hermes Agent (Assistant)" Brave profile — never type a
   password or a code yourself. With several channels, switch to the one the
   user named (account menu → switch account) and check the channel name on
   the page before going on.
2. Go to the setting and read its current value from the page:
   - name, handle, picture, banner, links, contact email → Customization →
     Profile (Studio labels: カスタマイズ → プロフィール);
   - featured video and sections → Customization → Layout (レイアウト);
   - upload defaults → Settings → Upload defaults (設定 → アップロード動画の
     デフォルト設定).
3. Ask with `clarify`: the channel, the setting, "before → after" in full,
   and choices such as "変更する" / "やめる". Images (picture, banner) come only
   from files under `~/Workspaces` the user named; name the file in the
   question. For a name or handle, also say:
   - YouTube limits how often each can change (recalled as twice in 14 days;
     Studio shows the limit next to the field — read it from there rather
     than stating it);
   - an old handle is held only for a while, then anyone may take it, and
     links pasted elsewhere stop working.
4. Only on a clear yes, make exactly that change and press the page's own
   save button (公開 / Publish on Customization, 保存 / Save in Settings).
   No answer, a timeout or anything but yes → nothing changes; say so.
5. Reload the page and read the value again. Report what the page shows now.
   If it does not match, or the page asks for something unexpected
   (verification, a policy notice, a dialog you did not expect), stop, leave
   it unsaved, and tell the user what you saw.

## Limits

- One setting per confirmation; never batch several Studio changes behind
  one yes.
- Never touch permissions, monetization, advanced settings (channel deletion,
  transfer, moving to a brand account), the Google account itself, or
  anything the user did not ask for.
- Studio changes without notice. When the page does not look like these
  steps, do not explore: stop and hand the change to the user with where to
  find it.
