"""Keep dispatcher workers from mutating the Kanban graph."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any


_MUTATION_TOOLS = {"kanban_create", "kanban_link", "kanban_unblock"}
_TERMINAL_KANBAN = re.compile(
    r"(?:^|[\s;&|])(?:[^\s;|]*/)?hermes"
    r"(?:\s+(?:-p|--profile)\s+[^\s;&|]+|\s+--profile=[^\s;&|]+)*"
    r"\s+kanban(?:\s|$)"
)


def _block(message: str) -> dict[str, str]:
    return {"action": "block", "message": message}


def _guard_worker_kanban_mutation(**kwargs: Any) -> dict[str, str] | None:
    if not os.environ.get("HERMES_KANBAN_TASK"):
        return None

    tool_name = kwargs.get("tool_name")
    if tool_name in _MUTATION_TOOLS:
        return _block(
            "Dispatcher workers cannot register or release Kanban cards; return the canonical handoff to the Assistant."
        )

    if tool_name == "terminal":
        args = kwargs.get("args")
        command = args.get("command") if isinstance(args, Mapping) else None
        if isinstance(command, str) and _TERMINAL_KANBAN.search(command):
            return _block(
                "Dispatcher workers cannot run Hermes Kanban commands through the terminal; use task-scoped lifecycle tools."
            )

    return None


def register(ctx: Any) -> None:
    """Register the dispatcher-worker Kanban mutation guard."""
    ctx.register_hook("pre_tool_call", _guard_worker_kanban_mutation)
