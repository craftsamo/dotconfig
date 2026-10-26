"""project_place: whether a terminal call runs inside one of the user's project repositories.

The access plugins' bypass guards let a project run its own entry points (``nps setup.google``,
``pnpm run deploy``, ``./scripts/deploy.sh``) and the CLIs it depends on through its package
manager (``pnpm exec wrangler``). That holds only in a project: a Git repository checked out under
``PROJECT_ROOTS`` (the ghq root and the task worktree root), and never Hermes' own configuration
(this checkout, its private overlay, or a worktree of either), whose scripts change Hermes itself.

The working directory is the call's ``workdir``, else a leading ``cd <absolute path> &&`` (also
inside ``bash -lc '…'``); a call that moves again (a second ``cd`` or ``pushd``) or whose place is
not written out gets no exception. A persistent shell's earlier ``cd`` is not seen.

Shared by the access plugins (each loads this file by path; it is not a plugin and has no
manifest).
"""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
import re

PROJECT_ROOTS = ("~/ghq", "~/Worktrees")
# Repositories whose scripts change Hermes itself, by the name in their origin URL.
HERMES_REPOS = {"dotconfig", "private-dotconfig"}

_CD = re.compile(r"""^\s*cd\s+(?:--\s+)?('[^']*'|"[^"$`\\]*"|[^\s;&|'"$`\\()<>]+)\s*(?:&&|;|\n)""")
# One shell running one quoted script (`zsh -lc '…'`): the script holds no quote of its kind.
_SHELL_C = re.compile(r"""^\s*(?:[\w./-]*/)?(?:ba|z|da|k)?sh\s+-[A-Za-z]*c[A-Za-z]*\s+(['"])((?:(?!\1).)*)\1\s*$""",
                      re.S)
_MOVES = re.compile(r"(?:^|[\s;&|()`'\"])(?:cd|pushd|popd)(?=$|[\s;&|()`'\"])")
_URL = re.compile(r"""^\s*url\s*=\s*"?([^"\s]+)"?\s*$""", re.IGNORECASE)


def _expand(text: str) -> Path | None:
    """An absolute path as written; `..` is refused, since a shell's `cd` reads it before symlinks
    and the resolved path would not be where the command runs."""
    text = text.strip("'\"")
    if not text or "$" in text:
        return None
    path = Path(os.path.expanduser(text))
    return path if path.is_absolute() and ".." not in path.parts else None


def _script(command: str) -> str:
    inner = _SHELL_C.match(command)
    return inner.group(2) if inner else command


def working_dir(args) -> Path | None:
    """The directory a terminal call runs its command in, when the call writes it out (the
    terminal tool's ``workdir``, or a leading ``cd``)."""
    if not isinstance(args, dict):
        return None
    command = args.get("command")
    if not isinstance(command, str):
        return None
    command = _script(command)
    workdir = args.get("workdir")
    found = _CD.match(command)
    if found:
        rest = command[found.end():]
        place = _expand(found.group(1))
    else:
        rest = command
        place = _expand(workdir) if isinstance(workdir, str) else None
    if place is None or _MOVES.search(rest):
        return None
    return place


def leading_moves(args) -> int:
    """How many changes of directory the call's place itself accounts for: 1 for a leading ``cd``,
    else 0. The reader counts every change of directory in the line against it."""
    command = args.get("command") if isinstance(args, dict) else None
    return 1 if isinstance(command, str) and _CD.match(_script(command)) else 0


def _git_dirs(path: Path) -> tuple[Path, Path] | None:
    """(worktree top, common git directory) of the repository holding ``path``, else None."""
    for top in (path, *path.parents):
        marker = top / ".git"
        if marker.is_dir():
            return top, marker.resolve()
        if marker.is_file():
            try:
                text = marker.read_text(encoding="utf-8").strip()
            except OSError:
                return None
            if not text.startswith("gitdir:"):
                return None
            gitdir = (top / text[len("gitdir:"):].strip()).resolve()
            common = gitdir
            try:
                common = (gitdir / (gitdir / "commondir").read_text(encoding="utf-8").strip()).resolve()
            except OSError:
                pass
            return top, common
    return None


def _origin_name(common: Path) -> str:
    """The repository name in the origin URL of a common git directory, else ''."""
    try:
        lines = (common / "config").read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    in_origin = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            in_origin = stripped.replace(" ", "").replace("\t", "").lower() == '[remote"origin"]'
            continue
        found = _URL.match(line)
        if in_origin and found:
            name = found.group(1).rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]
            return name[:-4] if name.endswith(".git") else name
    return ""


@lru_cache(maxsize=1)
def _own_common() -> Path | None:
    found = _git_dirs(Path(__file__).resolve().parent)
    return found[1] if found else None


def _roots() -> list[Path]:
    roots = []
    for root in PROJECT_ROOTS:
        try:
            roots.append(Path(os.path.expanduser(root)).resolve())
        except OSError:
            continue
    return roots


def project_dir(args) -> Path | None:
    """The working directory of a terminal call when it lies in a project repository, else None."""
    place = working_dir(args)
    if place is None:
        return None
    try:
        place = place.resolve()
    except OSError:
        return None
    if not place.is_dir() or not any(place == root or root in place.parents for root in _roots()):
        return None
    found = _git_dirs(place)
    if found is None:
        return None
    _, common = found
    if common == _own_common() or _origin_name(common) in HERMES_REPOS:
        return None
    return place


def local_bin(place: Path, name: str) -> bool:
    """Whether the project at ``place`` has ``name`` among its own dependencies' binaries, in
    ``node_modules/.bin`` of the directory or of a parent up to the repository's top."""
    found = _git_dirs(place)
    top = found[0] if found else place
    for directory in (place, *place.parents):
        candidate = directory / "node_modules" / ".bin" / name
        if candidate.exists():
            return True
        if directory == top:
            break
    return False
