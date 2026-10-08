# Discord roles

Only in a server the user names, and only the change they asked for — never
bulk tidying on your own initiative. Every role write is logged under the
user's name in the server's audit log, and other members can see roles
appear and vanish.

## Read first

1. `roles` with `guild`. It lists each role from the top with its position,
   member count, colour, `strong` permissions and whether the user can manage
   it (`manageable`), plus the user's own roles and permissions. Any role
   write needs this list read within the last 15 minutes; `refresh=true`
   reads it again.
2. `roles` with `role` shows one role's full permission list.
3. `member` with `guild` + `user` shows one person's roles; `role_members`
   up to 100 ids holding a role (Discord lists no more); `members` with
   `query` finds people by name, only where the user has Manage Server.
   Elsewhere user ids come from messages, `mentions` or `friends`.

## Writes

- `role_add` / `role_remove` (`role`, `user`), `role_bulk_add` (`users`, up
  to 30; the result says who got it).
- `role_create` (`name`; `permissions` as names such as `send_messages`;
  `color` `#RRGGBB`, `hoist`, `mentionable`).
- `role_edit` (`role`; `name`, `color`, `hoist`, `mentionable`, `grant` /
  `revoke` permission names). The whole new permission set is sent.
- `role_delete` (cannot be undone; the card shows how many members hold it).
- `reason` on any of them goes to the audit log. Pass the user's reason when
  they give one.

Permission names are the tool's; an unknown name is refused.

## What the tool refuses

Relay the refusal; never look for another route.

- Roles at or above the user's highest role (unless they own the server),
  roles managed by an integration (`managed`), and `@everyone`, except that
  `role_edit` may change `@everyone`. A role shown with `manageable: false`
  cannot be changed: do not try.
- The Administrator permission in any form: creating, granting, or assigning
  a role that holds it. Removing it is allowed.
- Any permission the user lacks.
- A card that does not fit: split the change into smaller requests.

## On the card

A card starting with `⚠ Strong permissions: …` gives power over other people
or the server (ban, kick, manage roles, messages or channels, …). Mention
that, or a `role_delete`'s member count, in your reply; it is not a separate
question, the card is the confirmation.

## Outcomes

- `done` — the result is the check; the mirror already follows it.
- `not done` — nothing happened. A two-factor request from Discord means the
  user makes that change in the app.
- `UNCERTAIN` — read once (`member`, or `roles` with `refresh=true`) and
  report what you saw. A `role_create` is never repeated without the user,
  since it could make a second role; other role writes set a state and may
  be repeated once the user agrees.

## Testing role writes

When the user asks to try the role actions: in the test server they name,
create a test role with a harmless permission (e.g. `add_reactions`, never
one listed as strong), assign it to someone already in the test context
(warn that they may see it appear and vanish), then remove and delete it.
Pass a reason on each write and report the audit-log entries left behind.
