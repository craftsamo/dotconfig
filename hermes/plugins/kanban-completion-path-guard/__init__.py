"""Keep kanban completion payloads free of accidental local paths."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Iterator


_PATH_TOKEN = re.compile(r"(?<![A-Za-z0-9])(?:/|~/|\./|\.\./)(?=\S)\S*")
def _is_nonempty(value: Any) -> bool:
    """Return whether an artifact field contains content or malformed data."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, frozenset, Mapping)):
        return bool(value)
    return True


def _text_values(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for nested in value.values():
            yield from _text_values(nested)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for nested in value:
            yield from _text_values(nested)
    elif value is not None:
        yield str(value)


def _contains_existing_local_path(value: Any) -> bool:
    for text in _text_values(value):
        for match in _PATH_TOKEN.finditer(text):
            token = match.group(0)[:4096]
            while token not in ("", "/", "~/", "./", "../"):
                try:
                    if Path(token).expanduser().is_file():
                        return True
                except (OSError, RuntimeError, TypeError, ValueError):
                    break
                token = token[:-1]
    return False


def _block(message: str) -> dict[str, str]:
    return {"action": "block", "message": message}


def _guard_kanban_complete(**kwargs: Any) -> dict[str, str] | None:
    if kwargs.get("tool_name") != "kanban_complete":
        return None

    args = kwargs.get("args")
    if not isinstance(args, Mapping):
        return None

    if _is_nonempty(args.get("artifacts")):
        return _block(
            "kanban_complete artifacts must be empty; use metadata.artifact_handoff for intended handoffs."
        )

    metadata = args.get("metadata")
    if isinstance(metadata, Mapping) and _is_nonempty(metadata.get("artifacts")):
        return _block(
            "kanban_complete metadata.artifacts must be empty; use metadata.artifact_handoff for intended handoffs."
        )

    summary = args.get("summary", kwargs.get("summary"))
    result = args.get("result", kwargs.get("result"))
    if _contains_existing_local_path(summary) or _contains_existing_local_path(result):
        return _block(
            "kanban_complete summary/result must not contain existing local paths."
        )

    return None


def register(ctx: Any) -> None:
    """Register the kanban completion path guard."""
    ctx.register_hook("pre_tool_call", _guard_kanban_complete)
