"""card: the one shape of a plugin's approval card.

A plugin's ``approve`` directive carries a ``message`` that Hermes shows as the reason on its own
approval prompt, right after "Why it was flagged: " and before the deadline line. The prompt is
plain text there (Telegram escapes markup), so a card has nothing but lines to read by. Every card
is built the same way, so the person answering reads them all alike:

    <Service> · <Action>              the title, which reads as one after the reason label
    <marker> <what is at stake>       one line: ✅ stays yours or can be undone, ⚠️ reaches others,
                                      🚨 cannot be undone or leaves your hands
    Label: value                      one fact a line
    Context: value                    facts the card may drop first when it is short of room

    --- Files ---                     a block per list, one item a line
    - a.png (image/png, 1.2 KB)

    --- Text ---                      the free text last, under its own heading, cut with the rest
    the message as written            counted when it does not fit

Telegram cuts the reason at 500 escaped UTF-16 units and Discord at 300, so a card is fitted to
``budget()`` for the platform the turn runs on. The patched runtime gives the reason the room its
short command leaves (``ea_reason_budget``), most of the message; there a card may be ``ROOMY``
long. Everything but the free text must fit whole; a card that cannot is refused (``CardError``),
never shown cut.

Shared by the plugins that return an ``approve`` directive (each loads this file by path; it is
not a plugin and has no manifest).
"""

from __future__ import annotations

import html
import re
import sys

SAFE, CAUTION, DANGER = "safe", "caution", "danger"
MARKERS = {SAFE: "✅", CAUTION: "⚠️", DANGER: "🚨"}

BUDGET = 480            # Telegram shows 500 escaped UTF-16 units of the reason
COMPACT_BUDGET = 290    # Discord shows 300
COMPACT_PLATFORMS = {"discord"}
# On the patched runtime: what Telegram's 4096 and Discord's 2000 leave once the prompt's own lines
# are drawn (about 3890 and 1740), less room for a translated header, a smart-deny line and, on
# Discord, approval mentions (about 23 units each); past it the gateway would cut the card itself.
ROOMY = {"telegram": 3500, "discord": 1200}
TEXT_MIN = 40           # room the free text keeps on a card that carries any

# The card's own words, kept in one table so another language can be added beside them.
WORDS = {"text": "Text", "files": "Files", "more": "(+{n} more characters)"}

# Control, bidi-override and invisible characters: spelled out, so other people's words cannot
# forge card lines or hide part of themselves. Newlines and tabs stay (the free text keeps its
# lines); the zero-width joiner stays too, or every family and flag emoji would be spelled out.
SUSPICIOUS = re.compile("[\u0000-\u0008\u000b-\u001f\u007f-\u009f\u061c\u200b\u200c\u200e\u200f"
                        "\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff\ufff9-\ufffb]")
_BREAKS = re.compile(r"[\r\n\u2028\u2029]+")


class CardError(ValueError):
    """The card cannot show everything it must within the platform's budget."""


def units(text: str) -> int:
    """Length as the chat platform counts it: HTML-escaped, in UTF-16 code units."""
    return len(html.escape(text).encode("utf-16-le")) // 2


def visible(text: str) -> str:
    return SUSPICIOUS.sub(lambda m: f"⟨U+{ord(m.group()):04X}⟩", text)


def clip(value, limit: int) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= limit else text[:limit - 1] + "…"


def line(value, limit: int) -> str:
    """One card-safe line of someone else's words: whitespace collapsed, clipped, spelled out."""
    return visible(clip(re.sub(r"\s+", " ", "" if value is None else str(value)).strip(), limit))


def human(size: int) -> str:
    for unit, scale in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if size >= scale:
            return f"{size / scale:.1f} {unit}"
    return f"{size} B"


def platform() -> str:
    """The platform the current turn runs on, '' when it cannot be read."""
    try:
        from gateway.session_context import get_session_env
        return get_session_env("HERMES_SESSION_PLATFORM", "") or ""
    except Exception:  # noqa: BLE001 - outside a gateway, the full card
        return ""


def roomy() -> bool:
    """Whether the gateway showing this turn's card gives the reason the room its command leaves.
    Read from the gateway already loaded, never imported: only a running gateway shows a card on
    Telegram or Discord, and a runtime without the patch keeps the short budgets."""
    return hasattr(sys.modules.get("gateway.platforms.base_exec_approval"), "ea_reason_budget")


def budget(where: str | None = None) -> int:
    where = platform() if where is None else where
    if where in ROOMY and roomy():
        return ROOMY[where]
    return COMPACT_BUDGET if where in COMPACT_PLATFORMS else BUDGET


def _one(value) -> str:
    return visible(_BREAKS.sub(" ", str(value)))


def compose(service: str, action: str, effect: tuple[str, str], facts=(), *, context=(), sections=(),
            text: str | None = None, text_label: str | None = None, text_min: int = TEXT_MIN,
            where: str | None = None) -> str:
    """The card, fitted to the platform's budget.

    ``effect`` is ``(SAFE | CAUTION | DANGER, words)``. ``facts`` and ``context`` are ``(label, value)``
    pairs; a pair whose value is None is left out, and context goes first when the card is short of
    room. ``sections`` are ``(heading, lines)``. Values are shown on one line each, as given: clip
    other people's words with ``line()`` first. ``text`` is shown last with its lines kept, and cut
    with the rest counted when it does not fit; everything above it must fit with ``text_min`` units
    to spare (at most TEXT_MIN on a shorter card), or the card is refused."""
    level, words = effect
    head = [f"{_one(service)} · {_one(action)}", f"{MARKERS[level]} {_one(words)}"]
    facts = [f"{label}: {_one(value)}" for label, value in facts if value is not None]
    context = [f"{label}: {_one(value)}" for label, value in context if value is not None]
    blocks = []
    for heading, lines in sections:
        lines = [_one(item) for item in lines]
        if lines:
            blocks += ["", f"--- {heading} ---", *lines]
    limit = budget(where)
    body = visible(text) if text else ""
    # A shorter card keeps its facts before the start of the text.
    room = (text_min if limit >= BUDGET else min(text_min, TEXT_MIN)) if body else 0
    for kept in range(len(context), -1, -1):
        upper = "\n".join(head + facts + context[:kept] + blocks)
        prefix = upper + (f"\n\n--- {text_label or WORDS['text']} ---\n" if body else "")
        if units(prefix) <= limit - room:
            break
    else:
        raise CardError("the approval card cannot show all of this within the chat's limit")
    if not body or units(prefix + body) <= limit:
        return prefix + body
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if units(prefix + _cut(text, mid)) <= limit:
            lo = mid
        else:
            hi = mid - 1
    return prefix + _cut(text, lo)


def _cut(text: str, keep: int) -> str:
    return visible(text[:keep].rstrip()) + "…\n" + WORDS["more"].format(n=len(text) - keep)
