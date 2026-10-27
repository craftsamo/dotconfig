"""Every plugin tool names its own progress-line emoji.

A tool registered without ``emoji=`` shows Hermes' fallback (⚙️ in a gateway chat,
⚡ in the CLI), so every plugin tool reads alike in the progress line.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


HERMES = Path(__file__).resolve().parents[2]
SOURCES = sorted(p for p in (HERMES / "plugins").rglob("*.py")
                 if "tests" not in p.relative_to(HERMES / "plugins").parts)


def _calls(path):
    for node in ast.walk(ast.parse(path.read_text(), str(path))):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "register_tool":
            yield node


@pytest.mark.parametrize("path", [p for p in SOURCES if any(_calls(p))],
                         ids=lambda p: str(p.relative_to(HERMES / "plugins")))
def test_register_tool_passes_an_emoji(path):
    missing = [call.lineno for call in _calls(path) if not any(k.arg == "emoji" for k in call.keywords)]
    assert not missing, f"register_tool without emoji= at line(s) {missing}"
