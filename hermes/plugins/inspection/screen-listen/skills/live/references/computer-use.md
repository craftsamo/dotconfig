# computer_use, as used here

`computer_use` is Hermes' desktop tool (cua-driver). What matters for joining
a channel and watching a stream without disturbing the person at the Mac.

## Actions

- `capture` (free, no approval): `app: "<name>"` or a `window_id` from
  `list_windows`; `mode: "som"` for numbered elements with their labels,
  `mode: "vision"` for a plain screenshot, `mode: "ax"` for the tree alone.
- `click` / `double_click` by `element` index from a som capture, or by
  `coordinate`; `key`, `type`, `scroll`, `drag`; `list_windows`; `wait`.
- There is no launch, zoom or window-state action: open with a deep link or
  `open -g`, look with `capture`, use the app's own controls for size.

## Coordinates

Element bounds in a som capture are in native desktop points; a `coordinate`
for `click` is in the **screenshot's own pixels** (the image size is in the
capture's first line). Read a position off the som image and pass that
point; a native-space coordinate is refused as "outside the window".

## Delivery and focus

Input actions deliver in the **background** by default: the window is not
raised and the person keeps their focus. Never `focus_app` with
`raise_window`, `bring_to_front` or `delivery_mode: "foreground"` unless a
verdict leaves no other way and the user is not using the Mac — a foreground
action briefly raises the window and is a separate approval. `drag` is
foreground-only on macOS; prefer an app control over dragging. Do not resize
or move the user's other windows, and restore what you changed.

## Approvals

Each input action kind needs an approval card unless auto-approved: the scope
is per action and per delivery mode (`click` background, `click` foreground,
`double_click`, `key`, `type`, `scroll`, `drag` are each their own), granted
for one call, the session or always as the user chooses. `capture`,
`list_windows` and `wait` need none. Plan the clicks so a session grant
covers them; do not escalate to foreground to dodge a denied background
action.

## Verdicts

Every input result carries a `verdict`: `verify_fresh_state` means the input
was delivered but not confirmed — re-capture and read the result before any
retry; `escalate` names the next rung (by coordinate, then foreground) and is
a recommendation to weigh against the focus rule, not an instruction. Never
repeat an input on a recommendation alone. If a person starts using the Mac,
actions are refused with `human_has_control`: stop, tell the user what you
need, and re-capture once they hand back.
