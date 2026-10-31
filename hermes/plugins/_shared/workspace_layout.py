"""workspace_layout: where the Workspaces root is and which areas it holds, read from one place.

The layout is ``~/.config/workspaces/layout.json`` (``$XDG_CONFIG_HOME/workspaces/layout.json``
when that is set; ``WORKSPACES_LAYOUT`` names another file). Without the file the public defaults
apply, so a machine with no private overlay works as before:

    {"root": "~/Workspaces",
     "areas": [{"name": "Projects", "role": "projects", "sensitive": false},
               {"name": "Personal", "role": "personal", "sensitive": true}]}

An area is a top-level folder of Groups. ``role`` says what it holds: ``projects`` is the one area
the workspace registry creates project Groups in, ``personal`` any other. ``sensitive`` marks an
area whose data must not leave the machine unprotected. What lives inside a Group (``github/``,
``docs/``, ``data/``, ``assets/``, ``.agent/``) and at the root (``.agent/``, ``.inbox/``,
``.registry/``) is a fixed convention, not part of the layout. ``WORKSPACES_ROOT``, when set,
overrides the root (the scanners' existing override).

A file that cannot be read or does not validate raises ``LayoutError``: what the root bounds (the
files a message may attach) must never fall back to a guess. Stdlib only and Python 3.9-compatible,
because the ``ws-*`` launchers run on the system interpreter. Shared by the workspace plugins and
launchers (each loads this file by path; it is not a plugin and has no manifest). Run as a script,
it prints the resolved layout (``ws-layout``). Contract: docs/workspace-layout.md.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import NamedTuple, Optional, Tuple

ROLES = ("projects", "personal")
KEYS = ("root", "areas")
AREA_KEYS = ("name", "role", "sensitive")
DEFAULT = {
    "root": "~/Workspaces",
    "areas": [
        {"name": "Projects", "role": "projects", "sensitive": False},
        {"name": "Personal", "role": "personal", "sensitive": True},
    ],
}


class LayoutError(ValueError):
    """The layout file is unreadable or invalid."""


# NamedTuple, not dataclass: a dataclass looks its module up in sys.modules, which a module loaded
# by path (as every sibling loads this one) need not be in.
class Area(NamedTuple):
    name: str
    role: str
    sensitive: bool


class Layout(NamedTuple):
    root: Path
    areas: Tuple[Area, ...]
    source: Optional[Path]          # the file read, or None for the defaults

    @property
    def names(self) -> Tuple[str, ...]:
        return tuple(a.name for a in self.areas)

    @property
    def projects(self) -> Area:
        return next(a for a in self.areas if a.role == "projects")

    def area(self, name: str) -> Optional[Area]:
        return next((a for a in self.areas if a.name == name), None)

    def area_of(self, path) -> Optional[Area]:
        """The area a path lies in (lexically, after ``~`` expansion), or None outside every area."""
        try:
            rel = Path(os.path.normpath(Path(path).expanduser())).relative_to(self.root)
        except ValueError:
            return None
        return self.area(rel.parts[0]) if rel.parts else None

    def sensitive(self, path) -> bool:
        area = self.area_of(path)
        return bool(area and area.sensitive)

    def as_dict(self) -> dict:
        return {"root": str(self.root), "areas": [dict(a._asdict()) for a in self.areas],
                "source": str(self.source) if self.source else None}


def config_path() -> Path:
    named = os.environ.get("WORKSPACES_LAYOUT")
    if named:
        return Path(named).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base).expanduser() / "workspaces" / "layout.json"


def _fail(source, message):
    raise LayoutError(f"{source}: {message}")


def _parse(data, source) -> Layout:
    if not isinstance(data, dict):
        _fail(source, "the layout must be a JSON object")
    unknown = sorted(set(data) - set(KEYS))
    if unknown:
        _fail(source, f"unknown key(s) {', '.join(unknown)} (allowed: {', '.join(KEYS)})")
    root = data.get("root", DEFAULT["root"])
    if not isinstance(root, str) or not root.strip():
        _fail(source, "root must be a non-empty path")
    root_path = Path(os.path.normpath(Path(root).expanduser()))
    if not root_path.is_absolute():
        _fail(source, f"root must be absolute or start with ~: {root!r}")
    raw_areas = data.get("areas", DEFAULT["areas"])
    if not isinstance(raw_areas, list) or not raw_areas:
        _fail(source, "areas must be a non-empty list")
    areas, seen = [], set()
    for i, item in enumerate(raw_areas):
        if not isinstance(item, dict):
            _fail(source, f"areas[{i}] must be an object")
        extra = sorted(set(item) - set(AREA_KEYS))
        if extra:
            _fail(source, f"areas[{i}]: unknown key(s) {', '.join(extra)} (allowed: {', '.join(AREA_KEYS)})")
        name, role, sensitive = item.get("name"), item.get("role"), item.get("sensitive", False)
        if (not isinstance(name, str) or not name or name.startswith(".") or "/" in name or "\\" in name
                or name != name.strip()):
            _fail(source, f"areas[{i}].name must be a plain folder name not starting with '.': {name!r}")
        if name.casefold() in seen:     # macOS folders are case-insensitive
            _fail(source, f"area {name!r} is listed twice")
        seen.add(name.casefold())
        if role not in ROLES:
            _fail(source, f"areas[{i}].role must be one of {', '.join(ROLES)}: {role!r}")
        if not isinstance(sensitive, bool):
            _fail(source, f"areas[{i}].sensitive must be true or false")
        areas.append(Area(name, role, sensitive))
    if sum(a.role == "projects" for a in areas) != 1:
        _fail(source, "exactly one area must have role projects")
    return Layout(root_path, tuple(areas), source)


def load() -> Layout:
    """The layout in force now: the file if there is one, else the defaults; WORKSPACES_ROOT wins
    over either root. Read on every call, so a changed file applies without a restart."""
    path = config_path()
    # lexists, not exists: a link to a file that is gone is a layout that cannot be read, never
    # an absent one (the defaults could widen a root the file had narrowed).
    if os.path.lexists(path):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise LayoutError(f"{path}: cannot read the layout ({exc})") from None
        layout = _parse(data, path)
    else:
        layout = _parse(DEFAULT, None)
    override = os.environ.get("WORKSPACES_ROOT")
    if override:
        # A relative override is taken from the working directory, as the scanners always did.
        root = Path(os.path.abspath(Path(override).expanduser()))
        layout = Layout(root, layout.areas, layout.source)
    return layout


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ws-layout", description="Print the Workspaces layout in force.")
    show = parser.add_mutually_exclusive_group()
    show.add_argument("--root", action="store_true", help="the root only")
    show.add_argument("--areas", action="store_true", help="the area names, one a line")
    show.add_argument("--projects", action="store_true", help="the area project Groups live in")
    show.add_argument("--path", action="store_true", help="the layout file read (or that would be)")
    args = parser.parse_args(argv)
    if args.path:
        print(config_path())
        return 0
    try:
        layout = load()
    except LayoutError as exc:
        print(f"ws-layout: {exc}", file=sys.stderr)
        return 1
    if args.root:
        print(layout.root)
    elif args.areas:
        print("\n".join(layout.names))
    elif args.projects:
        print(layout.projects.name)
    else:
        print(json.dumps(layout.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
