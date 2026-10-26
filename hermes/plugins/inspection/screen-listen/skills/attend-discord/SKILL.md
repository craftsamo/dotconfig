---
name: attend-discord
description: "Use from screen-listen:listen when the Discord app on this Mac must get into a voice channel, stage or stream, or out of it. The app's steps only."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [screen-listen, discord, computer_use, voice-channel, stream]
---

# Discord: into the channel or stream, and out

How the Discord app on this Mac is opened, joined, muted, watched and left,
for the procedure in `screen-listen:listen`. Names and ids come from
`discord_account` (`guilds`, `channels`; a voice channel is `kind: voice`, a
stage `kind: stage`); nothing here touches the Discord API or the user's token.

The app is logged in to whatever account the person uses in it, which may not
be the account `discord_account` reads; the Mac joins as the app's account,
and that is the name others see.

## Open

With the terminal, in the background, so no focus is taken:

```
open -g -b com.hnc.Discord "discord://-/channels/<guild_id>/<channel_id>"
```

Discord may take several seconds to start or to log in: `computer_use` `wait`
a few seconds, then `capture` with `app: "Discord"`, `mode: "som"` and read
the result — the channel should be selected in the sidebar. A login or a
verification screen means stop and tell the user. Note whether Discord was
running before you opened it: that decides whether you quit it at the end.

## Join

- **Voice channel**: there is no "join" button. The link only selects the
  channel; a `click` on the **channel's own row in the sidebar** (the element
  whose label is the channel name) joins it. Discord's channel list is often
  not exposed as elements at all (the row's label appears only as the window
  title); then click by `coordinate` in the screenshot's own pixels — read the
  row's position off the som image (`skill_view(name="screen-listen:listen",
  file_path="references/computer-use.md")` says how).
- **Stage channel**: joining makes the Mac an audience member (no microphone
  by design), through its join control ("ステージに参加" / "Join Stage" or
  similar).

Re-capture after the click and follow the verdict. You are in when the
capture shows the voice-connected panel (a disconnect control appears), and
`screen_listen` `status` reports the app `playing: true` once anyone speaks
or streams. If nobody else is in the channel and no stream is live, say so
and leave; there is nothing to hear.

## Microphone

Joining a voice channel opens the Mac's microphone to it unless Discord was
left muted last time. Right after joining, capture again and read the
microphone control in the voice panel:

- "ミュート" / "Mute" means the microphone is **live** — click it.
- "ミュート解除" / "Unmute" means it is already muted.

Report what you found, not what you intended: "muted (the control read
ミュート解除)" or "could not find the microphone control — disconnected".
Whatever the user is saying in the room, or on another call, must not reach
the channel, so if you cannot confirm the state, disconnect and tell the user
instead of staying in. **Never deafen** ("スピーカーミュート" / "Deafen"):
that silences the app's output, which is exactly what `screen_listen` hears,
and would make every listen or recording silent. A stage audience member has
no microphone to mute. When the user is in the channel themselves, touch none
of this.

## The stream

A live stream shows a watch control on the streaming member ("配信を視聴" /
"Watch Stream"). Click it; the stream plays in the channel view, as a panel
above the speakers and the audience.

For a look, that panel is enough: `capture` with `mode: "vision"` of the main
window (`app: "Discord"`).

For a **video recording**, give the stream a window of its own first:

1. **Pop it out** — the pop-out control on the stream ("ポップアウト" / "Pop
   Out"). The new window is titled with the channel name alone; the main
   window's title carries the channel and the server ("… | <server> -
   Discord"). `computer_use` `list_windows` and `screen_listen` `windows`
   both show it. As opened, the pop-out shows the stage as the app does:
   the stream panel on top, the speakers and the audience below.
2. **Frame it** for the framing chosen in `screen-listen:listen`:
   - `full` (the whole stage): leave the pop-out as it is, and make the
     window large with its green zoom button so the stream panel is not
     tiny.
   - `share` (the shared screen alone): put the stream in full screen —
     the stream's own full-screen control (bottom right of the stream,
     "全画面" / "Full Screen") or a `double_click` on the stream; the stream
     then fills the window and the speakers and audience are out of frame.
   - **Chat panel** (`share` with the chat): the stream view has a chat
     toggle ("チャットを表示" / "Show Chat", top right; also in full screen)
     that opens the channel's text chat beside the stream. Open it when the
     shape says so, otherwise make sure it is closed ("チャットを非表示" /
     "Hide Chat" showing means it is open). If full screen offers no toggle
     in this build of Discord, record `full` with the chat open instead and
     say so.
   Capture the pop-out afterwards (`capture` with its `window_id`) and look:
   it should show what the shape means — the share alone, with or without
   the chat, or the whole stage. Dragging a window edge needs foreground
   delivery (a separate approval) — prefer the controls above.
3. **Record that window**: its id from `screen_listen` `windows` as
   `window_id` (or its exact title as `window`; a containing match would pick
   the bigger main window). Check `video_window` in the start answer. A
   stream that ends mid-session leaves the pop-out showing the stage, and
   the recording follows the window: say so if it happens, do not restart.

Leave the pop-out showing the stream for the whole recording. Do not switch
channels in the main window either: the audio tap follows the app, so a
different channel's audio would be recorded.

## Leave

Close a pop-out you opened, then disconnect: the disconnect control in the
voice panel (a stage has a leave control). Leave Discord as it was — running
in the background is fine; quit it
(`osascript -e 'quit app id "com.hnc.Discord"'`) only if it was not running
when you started. When the user is in the channel themselves, leave the
channel state alone; they leave when they are done.

## When Discord cannot be used

- Not installed, not logged in, or a verification screen: tell the user.
- A channel the app's account cannot join (no permission, full, a stage with
  no speaker invite): report the screen's message and stop.
