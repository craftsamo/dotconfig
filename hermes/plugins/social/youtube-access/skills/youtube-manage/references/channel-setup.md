# Starting a channel: the mechanics

What the channel is for, which audience and how many channels are strategy
decisions for the task skill or Marketer. This file covers what the tool and
Studio make possible and where the traps are.

## Before the channel exists

- `youtube(action="status")` shows whether a channel is attached. A Google
  account authorized without a channel serves public reads only; `my_videos`,
  `analytics`, `my_channel` and every write need a channel.
- After the user creates the channel on YouTube, they run `yaccess check`
  once in a terminal so the authorization picks it up. A brand-account
  channel is a different identity and needs `yaccess auth` with that channel
  picked. Do not quote the channel's analytics before that.

## Name and handle

- The display name is what viewers see; the `@handle` matters for links and
  mentions. Both are changed in Studio (`references/studio.md`), never
  through the tool.
- Probing a handle: `youtube(action="channels", of="@name")`. "no channel has
  the handle" does not prove it is free — a private or terminated channel or
  a release hold can keep it, and the public API cannot tell which. Say so.
  When the preferred handle is taken, the usual way out is the closest free
  handle now, with the brand in the display name, and a switch later if the
  original frees up.
- Choose the handle before pasting links anywhere: a changed handle frees
  the old one, and links to it break.
- Channel count is the irreversible decision: subscribers never move between
  channels. Name, handle, description, keywords, playlists and thumbnails
  can all change later.

## First settings

Once the channel exists, in this order:

1. `my_channel` to see what is set.
2. `channel_update`: `default_language` first (translations need it), then
   `description`, `keywords`, `country`, and `localizations` if the channel
   speaks to more than one language.
3. A trailer for visitors (`trailer`) only once a public or unlisted video
   exists to show.
4. Picture, banner and links in Studio, one confirmation each.
5. Uploads from this API project stay private until the user publishes them
   in Studio; plan the first release with that step in it.
