#!/usr/bin/env python3
"""Workspaces Drive: Group folders kept in Google Drive behind links into an rclone mount.

Every Group's assets/, and any folder moved with `move`, lives in Google Drive and is reached
through a relative link into an rclone nfsmount at ~/Workspaces/.drive, so nothing of it stays
on the local disk. Projects/ is stored as is, Personal/ through rclone crypt (folder names
readable, file names and contents encrypted). Which folders are on Drive is read from the links
themselves; nothing else records it. This module is the whole engine: the `ws-drive` command,
the LaunchAgent's run loop and the workspace-drive plugin's tool. Stdlib only.
Design: docs/ops/workspaces-drive.md.

  setup               once: Keychain items, the encrypted rclone config, the Google login
  install             render and load the LaunchAgent, wait for the mount
  restart [--force]   reload the LaunchAgent (refused while a move or restore runs)
  status [--json]     agent, mount, cache, folders on Drive, local assets/, interrupted work
  links [--check]     give every Group its assets/ link, and link Drive folders missing here
  move PATH           move a folder inside a Group (<Tree>/<Group>/<folder>[/...]) to Drive
  restore PATH        bring a moved folder back to this Mac (the Drive copy goes to its trash)
  uninstall           unload the LaunchAgent and unmount (Drive data, config, Keychain kept)
  run                 the LaunchAgent's foreground loop (mount + maintenance)
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import plistlib
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from xml.sax.saxutils import escape

HOME = Path.home()
WORKSPACES = HOME / "Workspaces"
MOUNT = WORKSPACES / ".drive"
# Engine runtime root: machine-local, outside the repository (HERMES_LOCAL overrides).
HERMES_LOCAL = Path(os.environ.get("HERMES_LOCAL") or HOME / ".hermes" / "local")
STATE = HERMES_LOCAL / "workspaces-drive"
CONFIG = STATE / "rclone.conf"
CACHE = STATE / "cache"
LOCK = STATE / "links.lock"
JOURNAL = STATE / "journal"
CONFIG_DIR = Path(os.environ.get("HERMES_CONFIG_DIR") or HOME / ".config" / "hermes")
LABEL = "local.hermes.workspaces-drive.mount"
TEMPLATE = CONFIG_DIR / "launchd" / f"{LABEL}.plist.tmpl"
LAUNCHER = CONFIG_DIR / "launchd" / "bin" / "hermes-workspaces-drive-mount"
ENGINE = CONFIG_DIR / "plugins" / "workspace" / "workspace-drive" / "drive.py"
PLIST = HOME / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG = HOME / "Library" / "Logs" / "workspaces-drive-mount.log"
SECRET = Path(os.environ.get("SECRET_CLI") or HOME / ".config" / "bin" / "secret")
LSOF = "/usr/sbin/lsof"

# The layout is fixed here, not per machine: changing a tree's storage would leave what is
# already on Drive unreadable, so a change is a reviewed edit of this file.
DRIVE_PATH = "Workspaces"          # folder in My Drive holding every tree
DRIVE_SCOPE = "drive"              # sees files added on Drive from the web or a phone too
TREES = {"Projects": "plain", "Personal": "crypt"}
LINK_DIRS = ("assets",)            # every Group gets these as links into the mount
STAY_LOCAL = ("github",)           # first-level Group folders never moved (repositories)
DRIVE_REMOTE = "wsdrive-drive"
CRYPT_REMOTE = "wsdrive-crypt"
SECRET_PROJECT = "hermes"
SECRET_SCOPE = "workspaces-drive"
CONFIG_PASS_ITEM = "WORKSPACES_DRIVE_CONFIG_PASS"
CLIENT_ID_ITEM = "WORKSPACES_DRIVE_CLIENT_ID"
CLIENT_SECRET_ITEM = "WORKSPACES_DRIVE_CLIENT_SECRET"
CRYPT_PASSWORD_ITEM = "WORKSPACES_DRIVE_CRYPT_PASSWORD"
CRYPT_SALT_ITEM = "WORKSPACES_DRIVE_CRYPT_SALT"
CACHE_MAX_SIZE = "20G"
CACHE_MAX_AGE = "168h"
# How long the mount trusts a directory listing. Drive's change feed (polled every minute)
# refreshes it sooner; this bounds how long a copy made outside the mount stays invisible.
DIR_CACHE_TIME = "2m"
MAINTENANCE_INTERVAL = 900
# soft + deadtimeout: a dead server fails calls and unmounts instead of hanging them;
# locallocks: the server has no lock manager, so a lock request would wait forever;
# nonegnamecache: a name once found missing is asked again, so files added on Drive from
# elsewhere appear; nobrowse: no Desktop/Finder volume.
NFS_OPTIONS = "locallocks,soft,intr,timeo=50,retrans=2,deadtimeout=30,mutejukebox,nonegnamecache,nobrowse"
# macOS writes extended attributes the NFS server cannot keep into AppleDouble files.
NOISE = ("._*", ".DS_Store")
EXCLUDE_NOISE = ("--exclude", "._*", "--exclude", ".DS_Store")

# Waits, in seconds (the environment shortens them for tests).
MOUNT_WAIT = int(os.environ.get("WSD_MOUNT_WAIT") or 60)
LOCK_WAIT = int(os.environ.get("WSD_LOCK_WAIT") or 30)
# Three times the mount's directory cache time: when a moved folder must show in the mount.
LIST_WAIT = int(os.environ.get("WSD_LIST_WAIT") or 360)
LIST_STEP = 10
# How long a restore waits for files written through the mount to finish uploading.
UPLOAD_WAIT = int(os.environ.get("WSD_UPLOAD_WAIT") or 600)
RESTORE_HEADROOM = 1 << 30


class DriveError(Exception):
    """A refusal or failure to report as is; nothing half-done is left behind."""


class Busy(DriveError):
    """Another links pass, move or restore holds the lock."""


# --- rclone and the Keychain ---------------------------------------------------------------

def rclone_argv(*args: str) -> list[str]:
    """rclone on the encrypted config. The config password comes from the Keychain through
    --password-command at every start, so it is never in an environment or on a command line,
    and rclone may save a refreshed token into the file."""
    return ["rclone", "--config", str(CONFIG), "--ask-password=false", "--password-command",
            f"{SECRET} get {CONFIG_PASS_ITEM} -p {SECRET_PROJECT} --scope {SECRET_SCOPE} --no-stage",
            *args]


def rclone(*args: str, capture: bool = False, check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    kwargs.setdefault("stdin", subprocess.DEVNULL)
    proc = subprocess.run(rclone_argv(*args), capture_output=capture, text=True, **kwargs)
    if check and proc.returncode:
        detail = (proc.stderr or "").strip()[-400:] if capture else ""
        raise DriveError(f"rclone {args[0]} failed (exit {proc.returncode})" + (f": {detail}" if detail else ""))
    return proc


def secret(*args: str, value: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([str(SECRET), *args, "-p", SECRET_PROJECT, "--scope", SECRET_SCOPE, "--no-stage"],
                          input=value, capture_output=True, text=True,
                          stdin=None if value is not None else subprocess.DEVNULL)


def has_item(name: str) -> bool:
    return secret("show", name).returncode == 0


def get_item(name: str) -> str:
    proc = secret("get", name)
    if proc.returncode or not proc.stdout.strip():
        raise DriveError(f"could not read {name} from the Keychain ({SECRET_PROJECT}/{SECRET_SCOPE})")
    return proc.stdout.strip()


def remote(tree: str, rest: str = "") -> str:
    """The remote path a tree, or anything below it, maps to. Plain trees sit under the Drive
    folder by name; encrypted ones under the same folder through the crypt remote."""
    mode = TREES.get(tree)
    if mode is None:
        raise DriveError(f"{tree} is not a tree ({', '.join(TREES)})")
    base = f"{DRIVE_REMOTE}:{DRIVE_PATH}/{tree}" if mode == "plain" else f"{CRYPT_REMOTE}:{tree}"
    return f"{base}/{rest}" if rest else base


def combine() -> str:
    """One remote whose top-level folders are the trees, so a single mount shows plain and
    encrypted trees side by side."""
    upstreams = " ".join(f"{tree}={remote(tree)}" for tree in TREES)
    return f":combine,upstreams='{upstreams}':"


def check_copy(local: Path, rem: str, both: bool = False) -> bool:
    """rclone's hash check of a local folder against Drive (cryptcheck for encrypted trees);
    one-way: every local file is on Drive; both: the two hold the same files."""
    command = "cryptcheck" if rem.startswith(f"{CRYPT_REMOTE}:") else "check"
    args = [command, str(local), rem, *EXCLUDE_NOISE] + ([] if both else ["--one-way"])
    return rclone(*args, check=False).returncode == 0


def remote_exists(rem: str) -> bool:
    return rclone("lsjson", "--stat", rem, capture=True, check=False).returncode == 0


def pending_uploads(rel: str) -> int:
    """Files below rel written through the mount and not yet uploaded: the mount's cache marks
    them Dirty until the upload ends. A read of Drive itself would miss them."""
    count = 0
    for root in (CACHE / "vfsMeta").glob(f"*/{rel}"):
        for top, _, files in os.walk(root):
            for name in files:
                try:
                    if json.loads(Path(top, name).read_text()).get("Dirty"):
                        count += 1
                except (OSError, ValueError):
                    continue
    return count


def wait_uploads(rel: str) -> None:
    deadline = time.monotonic() + UPLOAD_WAIT
    while (pending := pending_uploads(rel)) and time.monotonic() < deadline:
        time.sleep(2)
    if pending:
        raise DriveError(f"{pending} file(s) under {rel} are still uploading to Drive; try again when they are done")


def progress() -> list[str]:
    if sys.stdout.isatty():
        return ["--progress", "--stats-one-line"]
    return ["--stats", "1m", "--stats-one-line", "--stats-log-level", "NOTICE"]


# --- the mount ----------------------------------------------------------------------------

def mounted() -> bool:
    command = shutil.which("mount") or "/sbin/mount"
    out = subprocess.run([command], capture_output=True, text=True).stdout
    return f" on {MOUNT} (nfs" in out


def force_unmount() -> None:
    for command in (["diskutil", "unmount", "force", str(MOUNT)], ["umount", "-f", str(MOUNT)]):
        try:
            if subprocess.run(command, capture_output=True).returncode == 0:
                return
        except OSError:
            continue


def wait_mounted(seconds: int) -> None:
    for _ in range(seconds):
        if mounted():
            return
        time.sleep(1)
    if not mounted():
        raise DriveError(f"{MOUNT} did not mount within {seconds}s; check {LOG}")


def require_mounted() -> None:
    if not mounted():
        raise DriveError(f"the mount is not up at {MOUNT}; run: ws-drive install")


# --- the lock and the journal -------------------------------------------------------------

def private_state() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE, 0o700)


@contextmanager
def links_lock(wait: float = LOCK_WAIT):
    """One lock for everything that changes links (a links pass, move, restore), so a pass
    never links a folder a move has just set aside. Held by the kernel for the life of the
    process, so a holder that dies releases it."""
    import fcntl

    private_state()
    fd = os.open(LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    deadline = time.monotonic() + wait
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise Busy("another links pass, move or restore holds the lock; try again shortly")
                time.sleep(0.2)
        yield
    finally:
        os.close(fd)


def lock_busy() -> bool:
    try:
        with links_lock(0):
            return False
    except Busy:
        return True


def _journal_file(rel: str) -> Path:
    return JOURNAL / (hashlib.sha256(rel.encode()).hexdigest()[:16] + ".json")


def journal(rel: str, kind: str, phase: str) -> None:
    """Where a move or restore stands, so one that was killed is finished or undone at the
    next start. Holds the path only; removed when the work ends."""
    JOURNAL.mkdir(parents=True, exist_ok=True)
    tmp = _journal_file(rel).with_suffix(".tmp")
    with open(tmp, "w") as f:
        f.write(json.dumps({"path": rel, "kind": kind, "phase": phase, "at": int(time.time())}))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, _journal_file(rel))
    _sync_dir(JOURNAL)


def clear_journal(rel: str) -> None:
    _journal_file(rel).unlink(missing_ok=True)
    _sync_dir(JOURNAL)


def _sync_dir(path: Path) -> None:
    """A phase must be on disk before the step it guards begins, power cut included."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def journal_entries() -> list[dict]:
    entries = []
    for f in sorted(JOURNAL.glob("*.json")) if JOURNAL.is_dir() else ():
        try:
            entries.append(json.loads(f.read_text()))
        except (OSError, ValueError):
            continue
    return entries


# --- paths --------------------------------------------------------------------------------

def rel_of(path: Path) -> str:
    return path.relative_to(WORKSPACES).as_posix()


def link_target(path: Path) -> str:
    """The relative link a folder gets, so it resolves inside ~/Workspaces."""
    return os.path.relpath(MOUNT / path.relative_to(WORKSPACES), path.parent)


def is_our_link(path: Path) -> bool:
    return path.is_symlink() and os.readlink(path) == link_target(path)


def sibling(path: Path, suffix: str) -> Path:
    return path.with_name(path.name + suffix)


def groups():
    for tree in TREES:
        root = WORKSPACES / tree
        if not root.is_dir():
            continue
        for group in sorted(root.iterdir()):
            if not group.name.startswith(".") and group.is_dir() and not group.is_symlink():
                yield tree, group


def folder(arg: str) -> tuple[str, Path]:
    """A folder inside a Group, given as <Tree>/<Group>/<folder>[/...] or a path under
    ~/Workspaces, checked against what may live on Drive. Returns (relative path, path)."""
    raw = Path(os.path.expanduser(arg.strip()))
    if raw.is_absolute():
        try:
            raw = raw.relative_to(WORKSPACES)
        except ValueError:
            raise DriveError(f"{arg} is not under {WORKSPACES}") from None
    parts = raw.parts
    if any(p in ("", ".", "..") for p in parts) or len(parts) < 3:
        raise DriveError("name a folder inside a Group: <Tree>/<Group>/<folder>[/...]")
    tree = parts[0]
    if tree not in TREES:
        raise DriveError(f"{tree} is not a tree ({', '.join(TREES)})")
    if any(p.startswith(".") for p in parts[1:]):
        raise DriveError("folders whose name starts with '.' stay on this Mac "
                         "(drafts and the inbox are promoted first; tool settings stay with their tool)")
    if any(p.endswith((".migrating", ".restoring")) for p in parts):
        raise DriveError("that name belongs to a move or restore in progress")
    if parts[2] in STAY_LOCAL:
        raise DriveError(f"{parts[2]}/ holds repositories, which stay on this Mac")
    group = WORKSPACES / tree / parts[1]
    if group.is_symlink() or not group.is_dir():
        raise DriveError(f"{tree}/{parts[1]} is not a Group here")
    path = WORKSPACES.joinpath(*parts)
    step = group
    for name in parts[2:-1]:
        step = step / name
        if step.is_symlink():
            raise DriveError(f"{rel_of(step)} is already on Drive; {raw.as_posix()} is inside it")
        if not step.is_dir():
            raise DriveError(f"no folder {rel_of(step)}")
    return raw.as_posix(), path


def tally(path: Path) -> tuple[int, int]:
    """Files (AppleDouble and .DS_Store left out) and bytes below a folder."""
    count = size = 0
    for top, _, files in os.walk(path):
        for name in files:
            if name.startswith("._") or name == ".DS_Store":
                continue
            p = os.path.join(top, name)
            if os.path.islink(p):
                continue
            count += 1
            size += os.lstat(p).st_size
    return count, size


def human(size: float) -> str:
    for unit in ("B", "K", "M", "G", "T"):
        if size < 1024 or unit == "T":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}T"


def require_lsof() -> None:
    if not os.access(LSOF, os.X_OK):
        raise DriveError("lsof not found; moves need it to know nothing still writes the files they delete")


def lsof_holders(path: Path) -> list[str]:
    """PIDs with a file below path open. lsof's exit status says nothing here (it is 1 even
    when it lists files)."""
    require_lsof()
    out = subprocess.run([LSOF, "-t", "+D", str(path)], capture_output=True, text=True).stdout
    return sorted({pid for pid in out.split() if pid != str(os.getpid())})


# --- links --------------------------------------------------------------------------------

def links(check: bool = False, quiet: bool = False, relink: bool = True) -> list[str]:
    """Give every Group its LINK_DIRS as links into the mount (a missing one is created on Drive
    through rclone), and with relink link each Drive folder that has no local counterpart below
    a real local folder (a new Mac, or a link removed by hand). A real local folder stays where
    it is, reported unless quiet; check reports what would be linked and changes nothing.
    Folders are made on Drive through rclone, never through the mount: macOS refuses a shell
    that launchd started any access to a network volume."""
    require_mounted()
    lines = []
    for tree, group in groups():
        for name in LINK_DIRS:
            here = group / name
            rel = rel_of(here)
            if here.is_symlink():
                if not is_our_link(here) and not quiet:
                    lines.append(f"foreign link: {rel} -> {os.readlink(here)} (left alone)")
            elif here.exists():
                if not quiet:
                    lines.append(f"local: {rel} stays on this Mac (to keep it in Drive: ws-drive move {rel})")
            elif check:
                lines.append(f"would link: {rel}")
            else:
                try:
                    rclone("mkdir", remote(tree, f"{group.name}/{name}"), capture=True)
                except DriveError:
                    lines.append(f"failed: could not create {rel} on Drive")
                    continue
                here.symlink_to(link_target(here))
                lines.append(f"linked: {rel} -> {link_target(here)}")
    if relink:
        lines += _relink(check)
    return lines


def _relink(check: bool) -> list[str]:
    listing = rclone("lsf", "-R", "--dirs-only", "--fast-list", combine(), capture=True).stdout
    lines = []
    for entry in sorted({line.strip().rstrip("/") for line in listing.splitlines() if line.strip()},
                        key=lambda e: (e.count("/"), e)):
        parts = entry.split("/")
        if len(parts) < 3 or parts[0] not in TREES or parts[2] in STAY_LOCAL:
            continue
        if any(p.startswith(".") or p.endswith((".migrating", ".restoring")) for p in parts[1:]):
            continue
        group = WORKSPACES / parts[0] / parts[1]
        if group.is_symlink() or not group.is_dir():
            continue
        here = WORKSPACES.joinpath(*parts)
        step, real = group, True
        for name in parts[2:-1]:
            step = step / name
            if step.is_symlink() or not step.is_dir():
                real = False
                break
        if not real or os.path.lexists(here):
            continue
        if check:
            lines.append(f"would link: {entry} (on Drive, missing here)")
        else:
            here.symlink_to(link_target(here))
            lines.append(f"linked: {entry} -> {link_target(here)} (on Drive, missing here)")
    return lines


def sweep() -> None:
    """Delete AppleDouble and .DS_Store files on Drive for good (not into its trash, which they
    would fill), across every tree."""
    if mounted():
        rclone("delete", combine(), "--include", "._*", "--include", ".DS_Store",
               "--drive-use-trash=false", "--fast-list", "-q", capture=True, check=False)


# --- move and restore ---------------------------------------------------------------------

def move(arg: str, say=print, expect: str | None = None) -> dict:
    """Copy a local folder to Drive, check the copy by hash, set the folder aside and put its
    link in its place (from then on a new open of the path reaches Drive), refuse while a file
    of the set-aside folder is still open, wait until the mount lists every file, check the
    set-aside folder against Drive once more (so a file changed in between is not lost), and
    only then delete it. Anything that stops it before that puts the folder back."""
    rel, here = folder(arg)
    with links_lock():
        recover(say)
        check_expected("move", rel, expect)
        if is_our_link(here):
            raise DriveError(f"{rel} is already on Drive")
        if here.is_symlink() or not here.is_dir():
            raise DriveError(f"{rel} is not a folder on this Mac")
        aside = sibling(here, ".migrating")
        if os.path.lexists(aside):
            raise DriveError(f"{rel_of(aside)} already exists; move it away first")
        check_movable(rel, here)
        require_mounted()
        require_lsof()
        tree, rest = rel.split("/", 1)
        rem = remote(tree, rest)
        count, size = tally(here)
        say(f"copying {rel} ({count} files, {human(size)}) to Drive")
        journal(rel, "move", "copy")
        swapped = False
        try:
            # The folder itself and empty subfolders too: rclone copies files only.
            rclone("mkdir", rem)
            rclone("copy", str(here), rem, *EXCLUDE_NOISE, "--create-empty-src-dirs", *progress())
            if not check_copy(here, rem):
                raise DriveError(f"the copy of {rel} on Drive does not match; nothing changed here")
            journal(rel, "move", "swap")
            swapped = True
            os.rename(here, aside)
            here.symlink_to(link_target(here))
            holders = lsof_holders(aside)
            if holders:
                raise DriveError(f"files under {rel} are open in another process (PID {' '.join(holders)}); "
                                 "close it and move again")
            wait_listed(MOUNT / rel, count, rel)
            if not check_copy(aside, rem):
                raise DriveError(f"{rel} changed after it was copied; move again")
            journal(rel, "move", "delete")
            swapped = False
            shutil.rmtree(aside)
        except BaseException:
            if swapped:
                undo_move(here, aside, say)
            if swapped or not os.path.lexists(aside):
                clear_journal(rel)
            raise
        clear_journal(rel)
    say(f"moved: {rel} -> Drive ({count} files)")
    return {"path": rel, "files": count, "bytes": size}


def check_movable(rel: str, here: Path) -> None:
    for top, dirs, files in os.walk(here):
        if ".git" in dirs or ".git" in files:
            raise DriveError(f"{rel} holds a Git repository ({rel_of(Path(top))}), which stays on this Mac")
        found = [n for n in dirs + files if os.path.islink(os.path.join(top, n))]
        if found:
            raise DriveError(f"{rel} holds links, which Drive cannot keep; resolve them first: "
                             + ", ".join(rel_of(Path(top) / n) for n in found[:5]))


def plan(kind: str, arg: str) -> dict:
    """What a move or restore would do, checked as far as it can be without starting: the tool's
    approval card shows it, and the tool reads it again before queueing the work. A restore is
    counted through the mount (names and sizes only, nothing is downloaded)."""
    rel, here = folder(arg)
    tree = rel.split("/", 1)[0]
    if kind == "move":
        if is_our_link(here):
            raise DriveError(f"{rel} is already on Drive")
        if here.is_symlink() or not here.is_dir():
            raise DriveError(f"{rel} is not a folder on this Mac")
        if os.path.lexists(sibling(here, ".migrating")):
            raise DriveError(f"{rel}.migrating already exists; a person has to look at it first")
        check_movable(rel, here)
        count, size = tally(here)
    elif kind == "restore":
        if not is_our_link(here):
            raise DriveError(f"{rel} is not a folder on Drive (no link of this mount there)")
        require_mounted()
        count, size = tally(MOUNT / rel)
    else:
        raise DriveError("kind is move or restore")
    return {"kind": kind, "path": rel, "encrypted": TREES[tree] == "crypt", "files": count, "bytes": size}


def plan_digest(p: dict) -> str:
    """The fingerprint of what an approval card showed; the work runs only while it still holds."""
    return hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest()


def check_expected(kind: str, rel: str, expect: str | None) -> None:
    """Under the lock, refuse work whose folder no longer matches what was approved."""
    if expect and plan_digest(plan(kind, rel)) != expect:
        raise DriveError(f"{rel} changed after the {kind} was approved; nothing was done. Ask again")


def wait_listed(path: Path, count: int, rel: str) -> None:
    """The mount learns of a copy from Drive's change feed (about a minute), at the latest when
    its directory listings expire (DIR_CACHE_TIME)."""
    deadline = time.monotonic() + LIST_WAIT
    seen = 0
    while True:
        seen = tally_names(path)
        if seen >= count or time.monotonic() >= deadline:
            break
        time.sleep(LIST_STEP)
    if seen < count:
        raise DriveError(f"the mount shows {seen} of {count} files of {rel} after {LIST_WAIT}s")


def tally_names(path: Path) -> int:
    return sum(1 for _, _, files in os.walk(path) for n in files if not (n.startswith("._") or n == ".DS_Store"))


def undo_move(here: Path, aside: Path, say=print) -> None:
    if here.is_symlink():
        here.unlink()
    if not os.path.lexists(here) and aside.is_dir():
        os.rename(aside, here)
        say(f"rolled back: {rel_of(here)} is on this Mac again; its copy on Drive is kept")


def restore(arg: str, say=print, expect: str | None = None) -> dict:
    """Copy a moved folder from Drive into a staging folder beside its link, check it by hash
    against Drive both ways, refuse while a file of it is open through the mount, replace the
    link with the folder, check again (so nothing written to Drive in between is lost), and
    only then send the Drive copy to Drive's trash."""
    rel, here = folder(arg)
    with links_lock():
        recover(say)
        if not is_our_link(here):
            raise DriveError(f"{rel} is not a folder on Drive (no link of this mount there)")
        check_expected("restore", rel, expect)
        staging = sibling(here, ".restoring")
        if os.path.lexists(staging):
            raise DriveError(f"{rel_of(staging)} already exists; move it away first")
        require_mounted()
        require_lsof()
        tree, rest = rel.split("/", 1)
        rem = remote(tree, rest)
        info = json.loads(rclone("size", rem, "--json", capture=True).stdout or "{}")
        count, size = int(info.get("count") or 0), int(info.get("bytes") or 0)
        free = shutil.disk_usage(here.parent).free
        if free < size + RESTORE_HEADROOM:
            raise DriveError(f"{rel} needs {human(size)} and only {human(free)} is free here")
        wait_uploads(rel)
        say(f"copying {rel} ({count} files, {human(size)}) back from Drive")
        journal(rel, "restore", "copy")
        try:
            staging.mkdir()
            rclone("copy", rem, str(staging), *EXCLUDE_NOISE, "--create-empty-src-dirs", *progress())
            if not check_copy(staging, rem, both=True):
                raise DriveError(f"the local copy of {rel} does not match Drive; {rel} stays on Drive")
            holders = lsof_holders(MOUNT / rel)
            if holders:
                raise DriveError(f"files under {rel} are open in another process (PID {' '.join(holders)}); "
                                 "close it and restore again")
            journal(rel, "restore", "swap")
            here.unlink()
            os.rename(staging, here)
        except BaseException:
            if not os.path.lexists(here):
                here.symlink_to(link_target(here))
            if staging.is_dir():
                shutil.rmtree(staging)
            clear_journal(rel)
            raise
        finish_restore(rel, here, rem)
    say(f"restored: {rel} is on this Mac again ({count} files); its Drive copy is in Drive's trash")
    return {"path": rel, "files": count, "bytes": size}


def finish_restore(rel: str, here: Path, rem: str, purging: bool = False) -> None:
    """The folder is local again: wait for uploads still pending from before the swap, check it
    against Drive once more, then send the Drive copy to Drive's trash (an edit made on Drive
    from elsewhere in the meantime goes there with it, recoverable for 30 days). When they
    differ, both are kept and the journal entry stays. purging resumes a purge already decided."""
    if not purging:
        wait_uploads(rel)
        if not check_copy(here, rem, both=True):
            raise DriveError(f"{rel} is on this Mac again, but its Drive copy differs (written to during the "
                             "restore); both are kept: compare them, then delete the Drive copy")
        journal(rel, "restore", "purge")
    rclone("purge", rem, "--drive-use-trash=true", capture=True, check=False)
    if remote_exists(rem):
        raise DriveError(f"{rel} is on this Mac again, but its Drive copy could not be sent to the trash yet; "
                         "the next pass tries again")
    clear_journal(rel)


def recover(say=print) -> list[str]:
    """Finish or undo moves and restores a stopped process left half-done (run under the lock,
    so nothing is still working on them)."""
    done = []
    for entry in journal_entries():
        rel, kind, phase = entry.get("path", ""), entry.get("kind"), entry.get("phase")
        try:
            _, here = folder(rel)
        except DriveError:
            clear_journal(rel)
            continue
        tree, rest = rel.split("/", 1)
        try:
            if kind == "move":
                aside = sibling(here, ".migrating")
                if phase == "swap":
                    undo_move(here, aside, say)
                    note = f"undid an interrupted move of {rel}: it is on this Mac again"
                elif phase == "delete":
                    shutil.rmtree(aside, ignore_errors=True)
                    note = f"finished an interrupted move of {rel}"
                else:
                    note = f"an interrupted move of {rel} had changed nothing here"
                clear_journal(rel)
            elif kind == "restore":
                staging = sibling(here, ".restoring")
                if phase == "purge":
                    # The local folder was checked against Drive before the purge began.
                    finish_restore(rel, here, remote(tree, rest), purging=True)
                    note = f"finished an interrupted restore of {rel}"
                elif phase == "swap" and staging.is_dir() and not os.path.lexists(here):
                    # Stopped between removing the link and renaming the checked copy into place.
                    os.rename(staging, here)
                    finish_restore(rel, here, remote(tree, rest))
                    note = f"finished an interrupted restore of {rel}"
                elif phase == "swap" and here.is_dir() and not here.is_symlink():
                    finish_restore(rel, here, remote(tree, rest))
                    note = f"finished an interrupted restore of {rel}"
                else:
                    # Before the swap: Drive still holds the folder; drop the partial copy.
                    if not os.path.lexists(here):
                        here.symlink_to(link_target(here))
                    shutil.rmtree(staging, ignore_errors=True)
                    clear_journal(rel)
                    note = f"an interrupted restore of {rel} left it on Drive"
            else:
                clear_journal(rel)
                continue
        except DriveError as exc:
            note = str(exc)
        say(note)
        done.append(note)
    return done


# --- the queue ----------------------------------------------------------------------------
# The workspace-drive tool never moves anything itself: after its approval card it leaves a
# request in QUEUE, and the LaunchAgent runs each request as its own `move` / `restore` process,
# one at a time, so a move outlives a gateway restart and only the agent reads the Keychain.
# A request's outcome lands in JOBS as <id>.json; <id>.request marks the one running.

QUEUE = STATE / "queue"
JOBS = STATE / "jobs"
QUEUE_POLL = float(os.environ.get("WSD_QUEUE_POLL") or 3)
JOB_KEEP = 30 * 86400


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(data, ensure_ascii=False))
    os.replace(tmp, path)


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def enqueue(kind: str, arg: str, origin: str = "", expect: str | None = None) -> dict:
    """Queue a move or restore for the agent; refuses one the agent cannot take (no mount, the
    same folder already queued or running) and, with expect, one whose folder no longer matches
    the approved plan. The job carries that fingerprint, so it runs only while it still holds."""
    import fcntl

    if not mounted():
        raise DriveError(f"the mount is not up at {MOUNT}; the user restarts it (ws-drive restart)")
    request = plan(kind, arg)
    digest = plan_digest(request)
    if expect and digest != expect:
        raise DriveError(f"{request['path']} changed after the {kind} was approved; nothing was queued. Ask again")
    private_state()
    fd = os.open(STATE / "queue.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        for pending in [*QUEUE.glob("*.json"), *JOBS.glob("*.request")]:
            other = _read_json(pending) or {}
            if other.get("path") == request["path"]:
                raise DriveError(f"{request['path']} already has a {other.get('kind')} queued or running")
        job = f"{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"
        entry = {"id": job, "kind": kind, "path": request["path"], "files": request["files"],
                 "bytes": request["bytes"], "expect": digest, "origin": origin, "queued": int(time.time())}
        _write_json(QUEUE / f"{job}.json", entry)
    finally:
        os.close(fd)
    return entry


def jobs_view(recent: int = 5) -> dict:
    queued = sorted((e for e in map(_read_json, QUEUE.glob("*.json")) if e), key=lambda e: e.get("queued", 0))
    running = [e for e in map(_read_json, JOBS.glob("*.request")) if e]
    done = sorted((e for e in map(_read_json, JOBS.glob("*.json")) if e), key=lambda e: e.get("finished", 0))
    return {"queued": queued, "running": running, "recent": done[-recent:][::-1]}


def _log_lines(path: Path) -> list[str]:
    try:
        return [l.strip() for l in path.read_text(errors="replace").splitlines() if l.strip()]
    except OSError:
        return []


def outcome(job: str) -> dict | None:
    return _read_json(JOBS / f"{job}.json")


def wait_job(job: str, timeout: float) -> int:
    """Wait for a queued job's outcome and print one line about it (the tool's watcher)."""
    deadline = time.monotonic() + timeout
    while (result := outcome(job)) is None:
        if time.monotonic() >= deadline:
            print(f"workspace_drive: job {job} is still queued or running; workspace_drive status shows its outcome")
            return 2
        time.sleep(5)
    verb = {"move": "moved to Drive", "restore": "brought back from Drive"}.get(result.get("kind"), "done")
    if result.get("status") == "done":
        print(f"workspace_drive: {result.get('path')} {verb} ({result.get('files', '?')} files).")
        return 0
    print(f"workspace_drive: the {result.get('kind')} of {result.get('path')} did not finish "
          f"({result.get('status')}): {result.get('message')}")
    return 1


class Runner:
    """The agent's queue worker: one job at a time, each its own process, stopped (and so rolled
    back) when the agent stops."""

    def __init__(self, stop: threading.Event):
        self.stop = stop
        self.child: subprocess.Popen | None = None
        self.lock = threading.Lock()

    def halt(self, wait: float = 60) -> None:
        with self.lock:
            child = self.child
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=wait)
            except subprocess.TimeoutExpired:
                child.kill()

    def serve(self) -> None:
        if JOBS.is_dir() and any(JOBS.glob("*.request")):
            # A job an earlier agent was running: wait until nothing holds the lock, then record
            # what its log says (the journal has settled the folder itself).
            while lock_busy() and not self.stop.is_set():
                self.stop.wait(QUEUE_POLL)
            for orphan in JOBS.glob("*.request"):
                entry = _read_json(orphan) or {"id": orphan.stem}
                lines = _log_lines(JOBS / f"{entry.get('id', orphan.stem)}.log")
                if lines and lines[-1].startswith(("moved:", "restored:")):
                    self._finish(entry, "done", 0, lines[-1])
                else:
                    self._finish(entry, "interrupted", None, "the agent stopped while it ran; the folder was put "
                                                             "back or finished (workspace_drive status)")
        while not self.stop.is_set():
            try:
                if not self._one():
                    self.stop.wait(QUEUE_POLL)
            except Exception as exc:  # noqa: BLE001 - keep serving, report the cause
                print(f"workspaces-drive: queue: {exc}", file=sys.stderr)
                self.stop.wait(QUEUE_POLL)

    def _one(self) -> bool:
        requests = sorted(QUEUE.glob("*.json"))
        if not requests:
            return False
        entry = _read_json(requests[0])
        running = JOBS / f"{requests[0].stem}.request"
        JOBS.mkdir(parents=True, exist_ok=True)
        os.replace(requests[0], running)
        if not entry or entry.get("kind") not in ("move", "restore"):
            self._finish(entry or {"id": requests[0].stem}, "failed", None, "unreadable request")
            return True
        log = JOBS / f"{entry['id']}.log"
        with open(log, "w") as out:
            argv = [sys.executable, "-I", str(Path(__file__)), entry["kind"], entry["path"]]
            if entry.get("expect"):
                argv += ["--expect", entry["expect"]]
            child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT)
            with self.lock:
                self.child = child
            print(f"workspaces-drive: job {entry['id']}: {entry['kind']} {entry['path']}")
            while child.poll() is None:
                if self.stop.is_set():
                    self.halt()
                    break
                self.stop.wait(1)
            code = child.wait()
            with self.lock:
                self.child = None
        if code == 75 and not self.stop.is_set():
            os.replace(running, QUEUE / f"{entry['id']}.json")   # the lock was busy: try again shortly
            self.stop.wait(30)
            return True
        lines = _log_lines(log)
        message = lines[-1].removeprefix("ws-drive: ") if lines else ""
        status = "done" if code == 0 else ("stopped" if self.stop.is_set() else "failed")
        self._finish(entry, status, code, message)
        return True

    def _finish(self, entry: dict, status: str, code, message: str) -> None:
        job = entry.get("id", "unknown")
        _write_json(JOBS / f"{job}.json", {**entry, "status": status, "exit": code, "message": message,
                                           "finished": int(time.time())})
        (JOBS / f"{job}.request").unlink(missing_ok=True)
        print(f"workspaces-drive: job {job}: {status}" + (f": {message}" if message else ""))
        cutoff = time.time() - JOB_KEEP
        for old in JOBS.glob("*"):
            if old.suffix in (".json", ".log") and old.stat().st_mtime < cutoff:
                old.unlink(missing_ok=True)


# --- status -------------------------------------------------------------------------------

def scan() -> dict:
    """Walk every Group (not into links, repositories or dot-folders): which folders are links
    into the mount, which assets/ are kept here, foreign links and leftovers of interrupted work."""
    on_drive, local, foreign, leftovers = [], [], [], []
    mount = str(MOUNT)
    for _, group in groups():
        for top, dirs, files in os.walk(group):
            here = Path(top)
            keep = []
            for name in dirs + files:
                p = here / name
                if p.is_symlink():
                    target = os.path.normpath(os.path.join(top, os.readlink(p)))
                    if target == mount or target.startswith(mount + os.sep):
                        (on_drive if is_our_link(p) else foreign).append(rel_of(p))
                    elif here == group and name in LINK_DIRS:
                        foreign.append(rel_of(p))
                elif name.endswith((".migrating", ".restoring")):
                    leftovers.append(rel_of(p))
                elif name in dirs and not name.startswith(".") and not (here == group and name in STAY_LOCAL):
                    keep.append(name)
                if here == group and name in LINK_DIRS and not p.is_symlink() and p.is_dir():
                    local.append(rel_of(p))
            dirs[:] = keep
    return {"on_drive": sorted(on_drive), "local_assets": sorted(local), "foreign_links": sorted(foreign),
            "leftovers": sorted(leftovers)}


def cache_size() -> int:
    total = 0
    for top, _, files in os.walk(CACHE):
        for name in files:
            try:
                total += os.lstat(os.path.join(top, name)).st_blocks * 512
            except OSError:
                pass
    return total


def agent_state() -> dict:
    out = subprocess.run(["launchctl", "list"], capture_output=True, text=True).stdout
    line = next((l for l in out.splitlines() if l.split() and l.split()[-1] == LABEL), "")
    state = {"loaded": bool(line), "pid": None, "python": None, "python_present": None}
    if line and line.split()[0].isdigit():
        state["pid"] = int(line.split()[0])
    try:
        args = plistlib.loads(PLIST.read_bytes()).get("ProgramArguments", [])
        state["python"] = args[1]
        state["python_present"] = os.access(args[1], os.X_OK)
    except (OSError, IndexError, ValueError, plistlib.InvalidFileException):
        pass
    return state


def status_data() -> dict:
    data = {"agent": agent_state(), "mounted": mounted(), "mount": str(MOUNT),
            "cache_bytes": cache_size(), "cache_limit": CACHE_MAX_SIZE, "busy": lock_busy(),
            "interrupted": journal_entries(), "jobs": jobs_view(), **scan()}
    data["would_link"] = []
    if data["mounted"]:
        data["would_link"] = [l.split(": ", 1)[1] for l in links(check=True, quiet=True, relink=False)]
    return data


def status_text(data: dict) -> str:
    agent = data["agent"]
    lines = [f"agent:   {'loaded' if agent['loaded'] else 'not loaded'}"
             + (f" (pid {agent['pid']})" if agent.get("pid") else ""),
             f"{'mounted' if data['mounted'] else 'not mounted'}: {data['mount']}"]
    if agent.get("python_present") is False:
        lines.append(f"python:  {agent['python']} is gone (a Hermes update); run: ws-drive install")
    if data["mounted"]:
        lines.append(f"cache:   {human(data['cache_bytes'])} (soft limit {data['cache_limit']})")
    if data["busy"]:
        lines.append("busy:    a links pass, move or restore is running")
    lines.append(f"on Drive ({len(data['on_drive'])}):")
    lines += [f"  {p}" for p in data["on_drive"]]
    lines += [f"local: {p} stays on this Mac (to keep it in Drive: ws-drive move {p})" for p in data["local_assets"]]
    lines += [f"foreign link: {p} (left alone)" for p in data["foreign_links"]]
    lines += [f"interrupted {e.get('kind')}: {e.get('path')} (finished or undone at the next pass)"
              for e in data["interrupted"]]
    lines += [f"leftover: {p}" for p in data["leftovers"]
              if not any(p.startswith(e.get("path", "") + ".") for e in data["interrupted"])]
    lines += [f"would link: {p}" for p in data["would_link"]]
    jobs = data["jobs"]
    lines += [f"running: {e.get('kind')} {e.get('path')} (job {e.get('id')})" for e in jobs["running"]]
    lines += [f"queued: {e.get('kind')} {e.get('path')} (job {e.get('id')})" for e in jobs["queued"]]
    lines += [f"last: {e.get('kind')} {e.get('path')}: {e.get('status')}"
              + (f" ({e.get('message')})" if e.get("status") != "done" and e.get("message") else "")
              for e in jobs["recent"]]
    return "\n".join(lines)


# --- setup and the LaunchAgent ------------------------------------------------------------

class _UnixHTTP(http.client.HTTPConnection):
    def __init__(self, path: str, timeout: float):
        super().__init__("localhost", timeout=timeout)
        self._path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self._path)


def rc_create(name: str, kind: str, parameters: dict) -> None:
    """Create a remote through a short-lived `rclone rcd` on a unix socket in the private state
    folder, so keys and client secrets never appear on a command line. The daemon holds the
    decrypted config and answers anyone who reaches the socket: it is stopped on every way out."""
    sock = STATE / "setup-rc.sock"
    sock.unlink(missing_ok=True)
    proc = subprocess.Popen(rclone_argv("rcd", "--rc-addr", f"unix://{sock}", "--rc-no-auth"),
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            if sock.exists():
                break
            time.sleep(0.2)
        else:
            raise DriveError(f"rclone rcd did not open {sock} (a unix socket path must stay under 104 bytes)")
        body = json.dumps({"name": name, "type": kind, "parameters": parameters,
                           "opt": {"obscure": True, "nonInteractive": True}})
        conn = _UnixHTTP(str(sock), timeout=60)
        conn.request("POST", "/config/create", body, {"Content-Type": "application/json"})
        reply = conn.getresponse()
        answer = reply.read().decode("utf-8", "replace")
        try:
            error = json.loads(answer).get("Error")
        except ValueError:
            error = answer
        if reply.status != 200 or error:
            raise DriveError(f"could not create the rclone remote {name}: {str(error or answer)[:300]}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        sock.unlink(missing_ok=True)


def ensure_random_item(name: str, label: str) -> None:
    """A random value stored once, through stdin, kept out of `secret env`."""
    if has_item(name):
        return
    proc = subprocess.run([str(SECRET), "set", name, "-p", SECRET_PROJECT, "--scope", SECRET_SCOPE, "--no-stage",
                           "--no-env", "--new", "--stdin", "-j", label],
                          input=secrets.token_hex(32), capture_output=True, text=True)
    if proc.returncode:
        raise DriveError(f"could not store {name} in the Keychain")
    print(f"  stored {name} in the Keychain ({SECRET_PROJECT}/{SECRET_SCOPE})")


def has_remote(name: str) -> bool:
    out = rclone("listremotes", capture=True, check=False).stdout
    return f"{name}:" in out.split()


def require_tools() -> None:
    if not os.access(SECRET, os.X_OK):
        raise DriveError(f"the secret CLI is missing at {SECRET}")
    if not shutil.which("rclone"):
        raise DriveError("rclone not found (brew install rclone)")


def setup() -> None:
    require_tools()
    private_state()
    ensure_random_item(CONFIG_PASS_ITEM, "rclone config password for the Workspaces Drive mount")
    if not CONFIG.exists() or CONFIG.stat().st_size == 0:
        CONFIG.write_text("")
        os.chmod(CONFIG, 0o600)
        rclone("config", "encryption", "set", capture=True)
        print(f"  created the encrypted rclone config {CONFIG}")
    if not has_remote(DRIVE_REMOTE):
        parameters = {"scope": DRIVE_SCOPE}
        # Your own OAuth client avoids rclone's shared, rate-limited one.
        if has_item(CLIENT_ID_ITEM) and has_item(CLIENT_SECRET_ITEM):
            parameters.update(client_id=get_item(CLIENT_ID_ITEM), client_secret=get_item(CLIENT_SECRET_ITEM))
        rc_create(DRIVE_REMOTE, "drive", parameters)
    if rclone("about", f"{DRIVE_REMOTE}:", capture=True, check=False).returncode:
        print(f"  Google sign-in for {DRIVE_REMOTE} (scope {DRIVE_SCOPE}): answer y to use the browser,")
        print("  then n when asked about a shared drive")
        rclone("config", "reconnect", f"{DRIVE_REMOTE}:", stdin=None)
    if not has_remote(CRYPT_REMOTE):
        ensure_random_item(CRYPT_PASSWORD_ITEM, "rclone crypt password of the Workspaces Drive mount")
        ensure_random_item(CRYPT_SALT_ITEM, "rclone crypt salt of the Workspaces Drive mount")
        rc_create(CRYPT_REMOTE, "crypt", {
            "remote": f"{DRIVE_REMOTE}:{DRIVE_PATH}", "filename_encryption": "standard",
            "directory_name_encryption": "false",
            "password": get_item(CRYPT_PASSWORD_ITEM), "password2": get_item(CRYPT_SALT_ITEM)})
        print(f"  created {CRYPT_REMOTE}; keep {CRYPT_PASSWORD_ITEM} and {CRYPT_SALT_ITEM} somewhere off this Mac too:")
        print("  without them the encrypted trees cannot be read again")
    for tree in TREES:
        rclone("mkdir", remote(tree))
    print(f"setup done: {DRIVE_PATH}/ on Drive holds {', '.join(TREES)}")


def require_setup() -> None:
    if not CONFIG.exists() or CONFIG.stat().st_size == 0 or not has_item(CONFIG_PASS_ITEM):
        raise DriveError(f"no rclone config at {CONFIG} or no {CONFIG_PASS_ITEM} in the Keychain; run: ws-drive setup")


def render_plist() -> None:
    """The agent runs this file on the interpreter that runs install (Hermes' own Python, which
    holds macOS's network-volume permission; a shell started by launchd does not)."""
    for need in (TEMPLATE, ENGINE):
        if not need.is_file():
            raise DriveError(f"not found: {need}")
    if not os.access(LAUNCHER, os.X_OK):
        raise DriveError(f"launcher not executable: {LAUNCHER}")
    text = TEMPLATE.read_text(encoding="utf-8")
    for key, value in {"__HOME__": HOME, "__HERMES_LOCAL__": HERMES_LOCAL, "__PYTHON__": sys.executable,
                       "__ENGINE__": ENGINE}.items():
        text = text.replace(key, escape(str(value)))
    plistlib.loads(text.encode("utf-8"))
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    tmp = PLIST.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, PLIST)


def load_agent() -> None:
    subprocess.run(["launchctl", "unload", str(PLIST)], capture_output=True)
    subprocess.run(["launchctl", "load", "-w", str(PLIST)], check=True)


def install() -> None:
    require_tools()
    require_setup()
    render_plist()
    load_agent()
    wait_mounted(MOUNT_WAIT)
    print(f"loaded {LABEL}; Drive is mounted at {MOUNT}")


def restart(force: bool = False) -> None:
    if not PLIST.exists():
        raise DriveError(f"{LABEL} is not installed; run: ws-drive install")
    if not force and lock_busy():
        raise Busy("a links pass, move or restore is running; wait for it (or restart --force, which stops it)")
    load_agent()
    wait_mounted(MOUNT_WAIT)
    print(f"restarted {LABEL}")


def uninstall() -> None:
    subprocess.run(["launchctl", "unload", "-w", str(PLIST)], capture_output=True)
    PLIST.unlink(missing_ok=True)
    if mounted():
        force_unmount()
    print(f"unloaded and removed {LABEL}; the Drive links point at nothing until install "
          "(Drive data, config and Keychain items kept)")


# --- the LaunchAgent's loop ---------------------------------------------------------------

def run_agent() -> int:
    """Mount, then a maintenance pass at start and every MAINTENANCE_INTERVAL: finish or undo
    interrupted work, link new Groups' folders (the first pass also links Drive folders missing
    here and reports everything), and sweep AppleDouble files. Exit 78 (configuration error)
    before setup; launchd retries after its throttle interval."""
    sys.stdout.reconfigure(line_buffering=True)
    for problem in (not os.access(SECRET, os.X_OK) and f"the secret CLI is missing at {SECRET}",
                    not shutil.which("rclone") and "rclone not on PATH (brew install rclone)",
                    not (CONFIG.exists() and CONFIG.stat().st_size) and f"no rclone config at {CONFIG}; run: ws-drive setup"):
        if problem:
            print(f"workspaces-drive: {problem}", file=sys.stderr)
            return 78
    # A mount left by a server that died answers nothing, not even a stat of its mount point:
    # drop it before touching the folder.
    if mounted():
        force_unmount()
    if mounted():
        print(f"workspaces-drive: a stale mount at {MOUNT} did not let go yet; trying again", file=sys.stderr)
        return 1
    MOUNT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    if any(MOUNT.iterdir()):
        # Written to the local disk while nothing was mounted; mounting over it would hide it.
        print(f"workspaces-drive: {MOUNT} is not empty while unmounted; move its contents away first", file=sys.stderr)
        return 78
    proc = subprocess.Popen(rclone_argv(
        "nfsmount", combine(), str(MOUNT), "--vfs-cache-mode", "full", "--cache-dir", str(CACHE),
        "--vfs-cache-max-size", CACHE_MAX_SIZE, "--vfs-cache-max-age", CACHE_MAX_AGE,
        "--dir-cache-time", DIR_CACHE_TIME, "--drive-skip-shortcuts", "-o", NFS_OPTIONS),
        stdin=subprocess.DEVNULL)
    stop = threading.Event()
    runner = Runner(stop)
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, lambda *_: stop.set())

    def halt(code: int) -> int:
        # A move or restore in flight rolls back on its own stop, and needs the mount to do so.
        stop.set()
        runner.halt()
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
        return code

    deadline = time.monotonic() + 30
    while not mounted():
        if proc.poll() is not None:
            return proc.returncode or 1
        if stop.is_set():
            return halt(0)
        if time.monotonic() >= deadline:
            print(f"workspaces-drive: {MOUNT} did not mount within 30s", file=sys.stderr)
            return halt(1)
        stop.wait(0.5)
    print(f"workspaces-drive: mounted {MOUNT}")
    threading.Thread(target=maintain, args=(stop,), daemon=True).start()
    threading.Thread(target=runner.serve, daemon=True).start()
    while proc.poll() is None and not stop.is_set():
        stop.wait(1)
    if stop.is_set():
        return halt(0)
    print("workspaces-drive: rclone stopped; launchd starts the agent again", file=sys.stderr)
    return halt(proc.returncode or 1)


def maintain(stop: threading.Event) -> None:
    """One pass per interval. A failing pass is logged and the next one tries again: the mount
    stays up, so launchd would never restart a maintenance loop that had ended."""
    first = True
    while not stop.is_set():
        try:
            if mounted():
                try:
                    with links_lock(0):
                        recover()
                        for line in links(quiet=not first, relink=first):
                            print(line)
                    first = False
                except Busy:
                    pass
                sweep()
        except Exception as exc:  # noqa: BLE001 - keep the loop alive, report the cause
            print(f"workspaces-drive: maintenance pass failed: {exc}", file=sys.stderr)
        stop.wait(MAINTENANCE_INTERVAL)


# --- command line -------------------------------------------------------------------------

def _stop_on_signal(signum, _frame):
    raise SystemExit(128 + signum)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ws-drive", description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="\n".join(__doc__.split("\n\n")[2].splitlines()))
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("setup", "install", "uninstall", "run"):
        sub.add_parser(name)
    sub.add_parser("restart").add_argument("--force", action="store_true")
    sub.add_parser("status").add_argument("--json", action="store_true")
    sub.add_parser("links").add_argument("--check", action="store_true")
    for name in ("move", "restore"):
        command = sub.add_parser(name)
        command.add_argument("path")
        command.add_argument("--expect", help=argparse.SUPPRESS)
    waiting = sub.add_parser("wait", help="wait for a job the workspace_drive tool queued")
    waiting.add_argument("job")
    waiting.add_argument("--timeout", type=float, default=6 * 3600)
    args = parser.parse_args(argv)
    if args.action == "run":
        return run_agent()
    if args.action == "wait":
        return wait_job(args.job, args.timeout)
    # A stop (Ctrl-C, a terminal closing, a kill) unwinds like an error, so a move or restore
    # in flight puts everything back.
    signal.signal(signal.SIGTERM, _stop_on_signal)
    signal.signal(signal.SIGHUP, _stop_on_signal)
    try:
        if args.action == "setup":
            setup()
        elif args.action == "install":
            install()
        elif args.action == "restart":
            restart(args.force)
        elif args.action == "uninstall":
            uninstall()
        elif args.action == "status":
            data = status_data()
            print(json.dumps(data, ensure_ascii=False, indent=2) if args.json else status_text(data))
        elif args.action == "links":
            with links_lock():
                lines = [] if args.check else recover(say=lambda _line: None)
                lines += links(check=args.check)
            print("\n".join(lines) if lines else "nothing to link")
        elif args.action == "move":
            move(args.path, say=lambda line: print(line, flush=True), expect=args.expect)
        elif args.action == "restore":
            restore(args.path, say=lambda line: print(line, flush=True), expect=args.expect)
    except Busy as exc:
        print(f"ws-drive: {exc}", file=sys.stderr)
        return 75
    except DriveError as exc:
        print(f"ws-drive: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
