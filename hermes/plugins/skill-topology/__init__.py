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
"""

from __future__ import annotations

from typing import Any


LEARNED_CATEGORY = "learned"


def register(ctx: Any) -> None:
    """Register the topology policies (none rewrite skill creation)."""
