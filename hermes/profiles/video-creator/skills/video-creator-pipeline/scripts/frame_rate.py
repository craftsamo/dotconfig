"""Frame rates the authored HyperFrames video leaves may render at.

One list for create-promotion, create-story, create-ad, create-tour and the
HyperFrames path of create-explainer-video. Plans that name no rate keep 30,
so existing approved plans keep their bytes and hashes. Rates above 60 stay
out: create-master and edit-clip accept at most 60, and render time grows
with the frame count. Integer rates only; NTSC fractions are not offered.
"""

from __future__ import annotations

import re

ALLOWED = (24, 25, 30, 50, 60)
DEFAULT = 30
DRAFT_MAX = 30


def valid(value) -> bool:
    """True for an allowed integer rate (a JSON/YAML int, never a bool or float)."""
    return type(value) is int and value in ALLOWED


def parse_text(value) -> int | None:
    """An allowed rate from storyboard front matter text, else None."""
    if type(value) is int:
        return value if value in ALLOWED else None
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,3}", value.strip().strip("\"'")):
        return None
    rate = int(value.strip().strip("\"'"))
    return rate if rate in ALLOWED else None


def nearest(measured: float) -> int:
    """The allowed rate closest to a measured reference rate (59.94 -> 60, 23.976 -> 24)."""
    return min(ALLOWED, key=lambda rate: (abs(rate - measured), rate))


def draft(rate: int) -> int:
    """Draft renders never exceed 30 fps; the final renders at the approved rate."""
    return min(rate, DRAFT_MAX)


def describe() -> str:
    return "/".join(str(rate) for rate in ALLOWED)
