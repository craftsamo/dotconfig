"""Keep runtime-authored Hermes skills inside the learned boundary."""

from __future__ import annotations

from typing import Any


LEARNED_CATEGORY = "learned"


def _route_skill_create(**kwargs: Any) -> dict[str, Any] | None:
    """Force skill_manage create calls into the learned category."""
    if kwargs.get("tool_name") != "skill_manage":
        return None

    args = kwargs.get("args")
    if not isinstance(args, dict) or args.get("action") != "create":
        return None

    return {
        "args": {**args, "category": LEARNED_CATEGORY},
        "source": "skill-topology",
    }


def register(ctx: Any) -> None:
    """Register the skill creation routing policy."""
    ctx.register_middleware("tool_request", _route_skill_create)
