"""Scope the runtime's skill discovery to chosen roots, whatever shape it returns them in.

The scanner's names AND return shape differ between runtimes: ``_skill_search_dirs`` /
``_find_all_skills`` before, ``skill_search_dirs`` / ``find_all_skills`` after; the search
dirs were ``(project_dirs, all_dirs, active_dir)`` before, ``(tier_roots, active_dir)``
after. Tests reach the scanner only through this module: it resolves the names and
builds the stub's value. The shape is read off the real function.
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


def search_dirs_name() -> str:
    """The runtime's name for the skill search-dirs function."""
    from tools import skills_tool

    return "skill_search_dirs" if hasattr(skills_tool, "skill_search_dirs") else "_skill_search_dirs"


def find_all_skills(**kwargs) -> list:
    """Run the runtime's skill scanner, whichever name it has."""
    from tools import skills_tool

    scan = getattr(skills_tool, "find_all_skills", None) or skills_tool._find_all_skills
    return scan(**kwargs)


def search_dirs_result(*roots: Path, active: Path | None = None) -> tuple:
    """What the search-dirs function returns when ``roots`` are the only skill roots."""
    from tools import skills_tool

    active = Path(active if active is not None else roots[0])
    with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"HERMES_HOME": home}):
        shape = len(getattr(skills_tool, search_dirs_name())())
    if shape == 3:
        return ([], [Path(r) for r in roots], active)
    if shape == 2:
        from agent.skill_utils import TIER_EXTERNAL

        return ([(TIER_EXTERNAL, Path(r)) for r in roots], active)
    raise RuntimeError(f"{search_dirs_name()} returns {shape} values; teach skill_roots.py this shape")
