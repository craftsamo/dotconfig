"""discord-access permissions: Discord's permission bits by name, and what a member holds.

Standard library only (read by the plugin). Role writes are checked against these before a card is
shown: the user's own permissions in a server come from the @everyone role, their roles and server
ownership. Discord enforces the same rules again; these checks only keep impossible or forbidden
requests off the approval card. Contract: docs/discord-access.md.
"""

from __future__ import annotations

# Bit positions as Discord documents them. Bits not named here are kept as they are on an edit and
# shown as bit<N>.
BITS = {
    "create_instant_invite": 0, "kick_members": 1, "ban_members": 2, "administrator": 3,
    "manage_channels": 4, "manage_guild": 5, "add_reactions": 6, "view_audit_log": 7,
    "priority_speaker": 8, "stream": 9, "view_channel": 10, "send_messages": 11, "send_tts_messages": 12,
    "manage_messages": 13, "embed_links": 14, "attach_files": 15, "read_message_history": 16,
    "mention_everyone": 17, "use_external_emojis": 18, "view_guild_insights": 19, "connect": 20,
    "speak": 21, "mute_members": 22, "deafen_members": 23, "move_members": 24, "use_vad": 25,
    "change_nickname": 26, "manage_nicknames": 27, "manage_roles": 28, "manage_webhooks": 29,
    "manage_guild_expressions": 30, "use_application_commands": 31, "request_to_speak": 32,
    "manage_events": 33, "manage_threads": 34, "create_public_threads": 35, "create_private_threads": 36,
    "use_external_stickers": 37, "send_messages_in_threads": 38, "use_embedded_activities": 39,
    "moderate_members": 40, "view_creator_monetization_analytics": 41, "use_soundboard": 42,
    "create_guild_expressions": 43, "create_events": 44, "use_external_sounds": 45,
    "send_voice_messages": 46, "send_polls": 49, "use_external_apps": 50, "pin_messages": 51,
}
ADMINISTRATOR = 1 << BITS["administrator"]
MANAGE_ROLES = 1 << BITS["manage_roles"]
MANAGE_GUILD = 1 << BITS["manage_guild"]
ALL = (1 << 64) - 1

# Power over other people or the server itself: these put a warning at the top of a role card.
STRONG = ("administrator", "ban_members", "kick_members", "manage_guild", "manage_roles", "manage_channels",
          "manage_webhooks", "manage_messages", "moderate_members", "mention_everyone", "manage_nicknames",
          "manage_guild_expressions", "manage_events", "manage_threads", "view_audit_log", "pin_messages")


class UnknownPermission(ValueError):
    pass


def value(raw) -> int:
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def names(bits: int) -> list[str]:
    """Every permission in ``bits``, named; unnamed bits as bit<N>."""
    out = [name for name, bit in BITS.items() if bits & (1 << bit)]
    known = sum(1 << b for b in BITS.values())
    out += [f"bit{i}" for i in range(64) if bits & ~known & (1 << i)]
    return out


def strong(bits: int) -> list[str]:
    return [name for name in STRONG if bits & (1 << BITS[name])]


def parse(given) -> int:
    """A list of permission names (as names() writes them) as bits; raises for unknown names."""
    if given in (None, "", []):
        return 0
    if isinstance(given, str):
        given = [given]
    if not isinstance(given, list) or not all(isinstance(g, str) for g in given):
        raise UnknownPermission("permissions must be a list of names such as send_messages")
    bits, unknown = 0, []
    for raw in given:
        name = raw.strip().lower().replace("-", "_").replace(" ", "_")
        if name in BITS:
            bits |= 1 << BITS[name]
        elif name.startswith("bit") and name[3:].isdigit() and int(name[3:]) < 64:
            bits |= 1 << int(name[3:])
        else:
            unknown.append(raw)
    if unknown:
        raise UnknownPermission("unknown permission(s): " + ", ".join(unknown)
                               + "; use names such as send_messages or manage_messages (action=roles with role "
                                 "lists a role's permissions)")
    return bits


def base(owner: bool, everyone: int, roles: list[int]) -> int:
    """A member's server-wide permissions: the owner and administrators hold everything."""
    if owner:
        return ALL
    bits = everyone
    for r in roles:
        bits |= r
    return ALL if bits & ADMINISTRATOR else bits
