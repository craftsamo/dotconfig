"""Scope the runtime's skill discovery to chosen roots, whatever shape it returns them in.

``tools.skills_tool._skill_search_dirs`` is private, and its return value has changed
between runtimes: ``(project_dirs, all_dirs, active_dir)`` before, ``(tier_roots,
active_dir)`` after. A test that stubs it with a literal tuple breaks on the other
shape, so build the stub's value here. The shape is read off the real function.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch


def add_external_skill_dir(path: Path) -> None:
    """List one more skill dir under ``skills.external_dirs`` of the test's own ``HERMES_HOME`` config."""
    import hermes_yaml as yaml
    from agent import skill_utils

    config_path = skill_utils.get_config_path()
    config = yaml.safe_load(config_path.read_text()) or {}
    config.setdefault("skills", {}).setdefault("external_dirs", []).append(str(path))
    config_path.write_text(yaml.safe_dump(config))
    skill_utils._external_dirs_cache_clear()


def search_dirs_result(*roots: Path, active: Path | None = None) -> tuple:
    """What ``_skill_search_dirs`` returns when ``roots`` are the only skill roots."""
    from tools import skills_tool

    active = Path(active if active is not None else roots[0])
    with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"HERMES_HOME": home}):
        shape = len(skills_tool._skill_search_dirs())
    if shape == 3:
        return ([], [Path(r) for r in roots], active)
    if shape == 2:
        from agent.skill_utils import TIER_EXTERNAL

        return ([(TIER_EXTERNAL, Path(r)) for r in roots], active)
    raise RuntimeError(f"_skill_search_dirs returns {shape} values; teach skill_roots.py this shape")
