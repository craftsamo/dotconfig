"""Keep runtime-authored Hermes skills inside the learned boundary.

Placement of new skills is NOT decided here. Every ``config.yaml`` sets
``skills.create_dir: skills/learned`` (HERMES_HOME-relative), which
``skill_manage`` consults on every create — flat or ``operations[]``
shape, curator, ``/learn``, background review and the ``/skills approve``
replay alike — so a runtime-authored skill lands at
``<HERMES_HOME>/skills/learned/[<category>/]<name>``.

This plugin used to inject ``category: learned`` through a ``tool_request``
middleware keyed on a top-level ``action == "create"``. Upstream ``72874b0675``
(2026-08-28) made ``operations[]`` the only advertised call shape, so the
rewrite silently missed every batched create and those skills landed in the
profile's skill root (2026-09-07..09). ``create_dir`` cannot miss, and with
it a middleware would only double the path (``learned/learned/<name>``), so
the rewrite is gone. The plugin stays registered as the home of the
topology guard (maintainer-owned skill roots are read-only at runtime).

The remaining policy: maintainer-owned skill files are read-only at
runtime. ``write_file`` / ``patch`` / ``skill_manage`` edits and terminal
writes that resolve into a tracked skill root (``<repo>/hermes/**/skills/…``
outside ``learned/``) are blocked. A hands leaf's procedure that no longer
matches the runtime is REPORTED in the reply ("reported, never patched: the
tree is the maintainer's"); on 2026-09-05 image-creator patched
``text-emoji.sh`` in place instead, and the fix it chose was not the one
the maintainer wanted.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any


LEARNED_CATEGORY = "learned"
MANAGED_ROOT = Path(__file__).resolve().parents[2]  # <repo>/hermes
_FILE_WRITE_TOOLS = {"write_file", "patch"}
_TERMINAL_WRITE = re.compile(r"(?:>>?|\bsed\s+-i|\btee\b|\bmv\b|\bcp\b|\brm\b|\bchmod\b|\btruncate\b)")
_PATH_TOKEN = re.compile(r"[~/][^\s'\"`;|&<>]*")


def _is_managed(path_text: str) -> bool:
    """True when the path resolves into a tracked skill root (not learned/)."""
    try:
        resolved = Path(os.path.expanduser(path_text)).resolve()
    except (OSError, RuntimeError, ValueError):
        return False
    try:
        rel = resolved.relative_to(MANAGED_ROOT)
    except ValueError:
        return False
    parts = rel.parts
    if "skills" not in parts:
        return False
    after = parts[parts.index("skills") + 1:]
    return bool(after) and after[0] != LEARNED_CATEGORY


def _block(path_text: str) -> dict[str, str]:
    return {
        "action": "block",
        "message": (
            f"{path_text} is a maintainer-owned skill file. A procedure that no "
            "longer matches the runtime is REPORTED in your reply, never patched; "
            "runtime-authored skills belong under learned/."
        ),
    }


def _guard_managed_skill_writes(**kwargs: Any) -> dict[str, str] | None:
    tool_name = kwargs.get("tool_name")
    args = kwargs.get("args")
    if not isinstance(args, Mapping):
        return None

    if tool_name in _FILE_WRITE_TOOLS:
        path_text = args.get("path")
        if isinstance(path_text, str) and _is_managed(path_text):
            return _block(path_text)
        patch_text = args.get("patch")
        if isinstance(patch_text, str):
            for line in patch_text.splitlines():
                for prefix in ("*** Update File: ", "*** Add File: ", "*** Delete File: "):
                    if line.startswith(prefix) and _is_managed(line[len(prefix):].strip()):
                        return _block(line[len(prefix):].strip())
        return None

    if tool_name == "skill_manage":
        if args.get("action") == "create":
            return None
        for key in ("name", "path", "file_path"):
            value = args.get(key)
            if isinstance(value, str) and "/" in value and _is_managed(value):
                return _block(value)
        return None

    if tool_name == "terminal":
        command = args.get("command")
        if isinstance(command, str) and _TERMINAL_WRITE.search(command):
            for token in _PATH_TOKEN.findall(command):
                if _is_managed(token):
                    return _block(token)
    return None


def register(ctx: Any) -> None:
    """Register the write guard (placement is skills.create_dir)."""
    ctx.register_hook("pre_tool_call", _guard_managed_skill_writes)
