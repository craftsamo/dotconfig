#!/usr/bin/env python3
"""Local Stable Audio 3 (Medium/SAME-L) MLX runtime: install, status, render.

Stdlib-only and importable without MLX in the parent process - MLX only ever
runs inside the pinned checkout's .venv as a fresh subprocess. Weights,
checkout code and locked Python dependencies are pinned in
hermes/engines/stable-audio-3/pins.json and requirements.lock; this module never
resolves versions itself and never falls back to a different revision.

Fixed generation recipe only: DiT "medium", decoder "same-l", 8 pingpong
steps, 44.1 kHz 16-bit stereo PCM WAV. No LoRA, no CFG/negative-prompt, no
audio-to-audio/inpainting. Render preflights pinned local assets and sets HF
offline flags; this prevents lazy model downloads, not a network sandbox.

Fingerprint scope: status()'s drift checks are a version-pin guarantee (did
install() run against the exact pinned commit/lock/weights, unmodified since),
not a sandbox against a deliberately tampered venv - a dist-info RECORD or a
weight file can be forged to match its recorded stat without changing what
the interpreter actually imports.

Render lock scope: the child inherits the runtime lock descriptor, so an
abrupt parent death does not allow another GPU job while the child is alive.
Timeout/interrupt kills and reaps the owned process group. After a hard parent
death the child has no surviving timeout supervisor; a stuck child needs
operator recovery. Resume never launches a replacement generation.

CLI:
    stable_audio3.py install --accept-terms [--root PATH]
    stable_audio3.py check [--full] [--root PATH]
    stable_audio3.py refresh --previous-adapter OLD_SOURCE.py [--root PATH]
    stable_audio3.py render --request REQUEST.json --out NEW_DIR [--root PATH]
"""

from __future__ import annotations

import argparse
import base64
import csv
import fcntl
import hashlib
import json
import math
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import wave
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

PINS_SCHEMA_VERSION = 1
MARKER_SCHEMA_VERSION = 2  # bumped: marker no longer trusts checkout state, adds dependency records
SELF_PATH = Path(__file__).resolve()
PINS_PATH = SELF_PATH.parents[1] / "engines" / "stable-audio-3" / "pins.json"
LOCK_PATH = SELF_PATH.parents[1] / "engines" / "stable-audio-3" / "requirements.lock"
DEFAULT_ROOT = SELF_PATH.parents[1] / "local" / "stable-audio-3"
MARKER_NAME = "installed.json"
LOCK_FILE_NAME = ".runtime.lock"

MAX_BYTES = 16 * 1024 * 1024
MAX_TEXT_CHARS = 450
MIN_DURATION = 0.5
MAX_DURATION = 21.5
MAX_SEED = 2**32 - 1
FRAME_TOLERANCE = 1
UV_CANDIDATES = ("/opt/homebrew/bin/uv", "/usr/local/bin/uv")
DOWNLOAD_CHUNK = 8 * 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 880
STDERR_TAIL_BYTES = 4000

# Indirection point for tests: patching this (not the shared `subprocess`
# module) keeps install()'s real git/uv subprocess.run calls unaffected when
# a test fakes out only the generation subprocess.
_POPEN = subprocess.Popen


class RenderError(RuntimeError):
    """Raised for any install/render failure; no artifact is published."""


def _unavailable(reason: str) -> dict:
    return {"available": False, "reason": reason}


# ---- pins / lock / self fingerprint ----------------------------------------

def _load_pins():
    try:
        raw = PINS_PATH.read_bytes()
    except OSError as exc:
        raise RenderError(f"pins.json unavailable: {exc}") from exc
    try:
        pins = json.loads(raw)
    except ValueError as exc:
        raise RenderError(f"pins.json is not valid JSON: {exc}") from exc
    if pins.get("schema_version") != PINS_SCHEMA_VERSION:
        raise RenderError("pins.json schema_version mismatch")
    return pins, raw


def _code_lock_fingerprint(pins_raw: bytes, *, adapter_source: bytes | None = None) -> str:
    """Hashes pins.json + requirements.lock + this adapter's own source, so
    editing any of the three without rerunning install() shows up as drift."""
    try:
        lock_raw = LOCK_PATH.read_bytes()
        self_raw = SELF_PATH.read_bytes() if adapter_source is None else adapter_source
    except OSError as exc:
        raise RenderError(f"pinned dependency file unavailable: {exc}") from exc
    digest = hashlib.sha256()
    for part in (pins_raw, lock_raw, self_raw):
        digest.update(len(part).to_bytes(8, "big"))
        digest.update(part)
    return digest.hexdigest()


def _is_supported_platform() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


def _normalize_name(name: str) -> str:
    """PEP 503 normalization: pip/uv/importlib.metadata disagree on hyphen
    vs. underscore in a package's reported name (e.g. huggingface-hub vs.
    huggingface_hub) - this makes lock names and manifest names comparable."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _expected_dependency_names() -> list[str]:
    names = []
    for line in LOCK_PATH.read_text().splitlines():
        match = re.match(r"^([A-Za-z0-9_.\-]+)==", line.strip())
        if match:
            names.append(_normalize_name(match.group(1)))
    return names


# ---- layout / hashing / stat fingerprints -----------------------------------

def _layout(root: Path, pins: dict) -> dict:
    checkout = root / "checkout"
    mlx_dir = checkout / pins["checkout"]["subpath"]
    return {
        "root": root, "checkout": checkout, "mlx_dir": mlx_dir,
        "venv_python": mlx_dir / ".venv" / "bin" / "python",
        "sa3_mlx": mlx_dir / "scripts" / "sa3_mlx.py",
        "marker": root / MARKER_NAME, "lock_file": root / LOCK_FILE_NAME,
    }


def _weight_paths(layout: dict, pins: dict) -> list[dict]:
    return [{**entry, "runtime_path": layout["mlx_dir"] / entry["runtime_rel_path"]}
            for entry in pins["weights"]["files"]]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(DOWNLOAD_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


_STAT_FINGERPRINT_KEYS = ("inode", "mtime_ns", "size")


def _stat_fingerprint(path: Path) -> dict | None:
    """inode + mtime_ns + size only. st_dev is deliberately excluded: macOS
    renumbers the APFS Data volume's device id across reboots, so a marker
    recording it fails every fast check after the first restart even though
    nothing on disk changed (2026-09-10)."""
    try:
        info = path.stat()  # follows symlinks
    except OSError:
        return None
    return {"inode": info.st_ino, "mtime_ns": info.st_mtime_ns, "size": info.st_size}


def _stat_matches(current: dict | None, recorded: dict | None) -> bool:
    """Compares only the fingerprint keys, so a schema-2 marker written by an
    older adapter (which also recorded `dev`) stays valid without a rewrite."""
    if current is None or not isinstance(recorded, dict):
        return False
    return all(current.get(k) == recorded.get(k) for k in _STAT_FINGERPRINT_KEYS)


def _run(argv: list, cwd=None, timeout=60, env=None) -> str:
    result = subprocess.run([str(a) for a in argv], cwd=cwd, env=env,
                            capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RenderError(f"{' '.join(map(str, argv))} failed: {result.stderr.strip()[-2000:]}")
    return result.stdout


def _git_check(checkout: Path, subpath: str) -> tuple[str, bool]:
    """Live inspection of the actual checkout - never trusts a marker's
    recorded claim. `git status` already honors .gitignore, so pinned
    subpath-local artifacts (.venv/, *.npz, __pycache__/) are excluded."""
    head = _run(["/usr/bin/git", "rev-parse", "HEAD"], cwd=checkout, timeout=30).strip()
    dirty = bool(_run(["/usr/bin/git", "status", "--porcelain", "--", subpath],
                      cwd=checkout, timeout=30).strip())
    return head, dirty


def _runtime_identity(commit: str, code_lock_fingerprint: str, weight_hashes: list[str]) -> str:
    digest = hashlib.sha256()
    digest.update(commit.encode() + b"\0" + code_lock_fingerprint.encode())
    for h in weight_hashes:
        digest.update(b"\0" + h.encode())
    return digest.hexdigest()


# ---- dependency manifest -----------------------------------------------------

_MANIFEST_CODE = (
    "import importlib.metadata as m, json\n"
    "out = {}\n"
    "for d in m.distributions():\n"
    "    name = (d.metadata['Name'] or '').lower()\n"
    "    path = getattr(d, '_path', None)\n"
    "    if name and path is not None:\n"
    "        out[name] = {'version': d.version, 'dist_info': str(path)}\n"
    "print(json.dumps(out))\n"
)


def _collect_dependency_manifest(venv_python: Path) -> dict:
    """Runs importlib.metadata inside the venv under a clean env, so the
    result reflects only what's actually importable there - not this
    process's own site-packages or PYTHONPATH."""
    env = {"PATH": "/usr/bin:/bin", "HOME": tempfile.gettempdir(), "PYTHONDONTWRITEBYTECODE": "1"}
    out = _run([str(venv_python), "-c", _MANIFEST_CODE], timeout=60, env=env)
    return {_normalize_name(name): info for name, info in json.loads(out).items()}


def _dist_info_stat_target(dist_info: str) -> Path:
    """RECORD lists every installed file's hash; its own mtime/size moves on
    a package reinstall/upgrade even when the dist-info directory's mtime
    would not (directory mtime only reacts to add/remove, not in-place edits
    of an existing entry)."""
    record = Path(dist_info) / "RECORD"
    return record if record.exists() else Path(dist_info)


# ---- weight download ---------------------------------------------------------

def _download_weight(pins: dict, entry: dict, root: Path) -> Path:
    """Anonymous, revision-pinned, size/hash-bounded download to
    cache/assets/<revision>/<basename>. No auth, no HF cache, no "latest" -
    the URL always embeds the pinned revision. An existing cache file is
    verified and reused; a mismatching one is refused, never overwritten."""
    revision = pins["weights"]["revision"]
    cache_dir = root / "cache" / "assets" / revision
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / Path(entry["runtime_rel_path"]).name
    if cache_path.exists():
        if _sha256_file(cache_path) != entry["sha256"]:
            raise RenderError(f"cached asset {cache_path} does not match pinned sha256; refusing to overwrite")
        return cache_path

    part_path = cache_path.with_name(cache_path.name + ".part")
    if part_path.exists():
        part_path.unlink()  # our own leftover partial from an interrupted attempt; safe under the install lock

    url = f"https://huggingface.co/{pins['weights']['repo']}/resolve/{revision}/{entry['repo_path']}"
    request = urllib.request.Request(url, headers={"User-Agent": "hermes-stable-audio-3-installer"})
    digest, written, start = hashlib.sha256(), 0, time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=60) as response, part_path.open("xb") as out:
            while chunk := response.read(DOWNLOAD_CHUNK):
                if time.monotonic() - start > DOWNLOAD_TIMEOUT_SECONDS:
                    raise RenderError(f"download of {entry['repo_path']} exceeded {DOWNLOAD_TIMEOUT_SECONDS}s")
                written += len(chunk)
                if written > entry["bytes"]:
                    raise RenderError(f"download of {entry['repo_path']} exceeded expected size")
                digest.update(chunk)
                out.write(chunk)
    except (urllib.error.URLError, OSError) as exc:
        part_path.unlink(missing_ok=True)
        raise RenderError(f"download of {entry['repo_path']} failed: {exc}") from exc
    except RenderError:
        part_path.unlink(missing_ok=True)
        raise

    if written != entry["bytes"] or digest.hexdigest() != entry["sha256"]:
        part_path.unlink(missing_ok=True)
        raise RenderError(f"download of {entry['repo_path']} failed integrity check")
    os.replace(part_path, cache_path)  # hash already verified above, before this becomes visible
    return cache_path


def _ensure_runtime_link(runtime_path: Path, cache_path: Path, entry: dict) -> None:
    """Creates the runtime symlink only when absent; an existing symlink or
    file is verified, never silently replaced."""
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    if runtime_path.is_symlink():
        target = Path(os.readlink(runtime_path))
        if not target.is_absolute():
            target = runtime_path.parent / target
        if target.resolve() != cache_path.resolve():
            raise RenderError(f"{runtime_path} is a symlink to an unexpected target")
        return
    if runtime_path.exists():
        if _sha256_file(runtime_path) != entry["sha256"]:
            raise RenderError(f"{runtime_path} exists and does not match pinned sha256; refusing to overwrite")
        return
    runtime_path.symlink_to(cache_path)


# ---- runtime lock -------------------------------------------------------------

@contextmanager
def _runtime_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = open(lock_path, "a+")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fd.close()
        raise RenderError("busy: another install or render holds the runtime lock")
    try:
        yield fd
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()


def is_busy(root=None):
    """Check the shared process lock without starting work or creating a root."""
    root = Path(root).resolve() if root is not None else DEFAULT_ROOT
    path = root / LOCK_FILE_NAME
    if not path.exists():
        return False
    with path.open("r") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
    return False


# ---- status ------------------------------------------------------------------

def status(root: str | Path | None = None, full: bool = False) -> dict:
    """Report readiness. Every call (fast or full) does a live git inspection
    of the checkout and a stat-fingerprint check of pinned dependency
    dist-infos - never a blind trust of the marker's recorded claims. Fast
    mode stat-checks the weights; full=True re-hashes them INSTEAD (a content
    check, so a same-stat tamper is caught) and re-collects the dependency
    manifest via a subprocess (no re-download, no reinstall)."""
    root = Path(root).resolve() if root is not None else DEFAULT_ROOT
    if not _is_supported_platform():
        return _unavailable("platform must be macOS arm64 (darwin/arm64)")
    try:
        pins, pins_raw = _load_pins()
    except RenderError as exc:
        return _unavailable(str(exc))

    layout = _layout(root, pins)
    if not layout["checkout"].is_dir():
        return _unavailable("not installed: no checkout at root")
    if not layout["marker"].exists():
        return _unavailable("not installed: no installed.json marker")
    try:
        marker = json.loads(layout["marker"].read_text())
    except (OSError, ValueError) as exc:
        return _unavailable(f"installed.json unreadable: {exc}")

    try:
        code_lock_fingerprint = _code_lock_fingerprint(pins_raw)
    except RenderError as exc:
        return _unavailable(str(exc))
    if marker.get("code_lock_fingerprint") != code_lock_fingerprint:
        return _unavailable("drift: code/lock/adapter fingerprint mismatch (adapter-only changes may use refresh)")

    return _check_runtime(layout, pins, marker, full)


def _check_runtime(layout, pins, marker, full):
    """Shared installed-asset checks; status separately enforces adapter identity."""
    code_lock_fingerprint = marker["code_lock_fingerprint"]
    expected_commit = pins["checkout"]["commit"]
    try:
        head, dirty = _git_check(layout["checkout"], pins["checkout"]["subpath"])
    except RenderError as exc:
        return _unavailable(f"checkout inspection failed: {exc}")
    if head != expected_commit:
        return _unavailable(f"drift: checkout HEAD {head} != pinned {expected_commit}")
    if dirty:
        return _unavailable("drift: checkout has local changes under the pinned subpath")

    marker_weights = {w["repo_path"]: w for w in marker.get("weights", [])}
    weight_hashes = []
    for entry in _weight_paths(layout, pins):
        recorded = marker_weights.get(entry["repo_path"])
        if recorded is None or recorded.get("sha256") != entry["sha256"]:
            return _unavailable(f"drift: {entry['repo_path']} missing or mismatched in marker")
        weight_hashes.append(entry["sha256"])
        runtime_path = entry["runtime_path"]
        if full:
            if not runtime_path.exists() or _sha256_file(runtime_path) != entry["sha256"]:
                return _unavailable(f"drift: {entry['repo_path']} content hash mismatch or missing")
        else:
            if not _stat_matches(_stat_fingerprint(runtime_path), recorded.get("stat")):
                return _unavailable(f"drift: {entry['repo_path']} stat fingerprint mismatch or missing")

    marker_deps = marker.get("dependencies", {})
    expected_names = _expected_dependency_names()
    for name in expected_names:
        recorded = marker_deps.get(name)
        if recorded is None:
            return _unavailable(f"drift: pinned dependency {name} missing from marker")
        if not _stat_matches(_stat_fingerprint(Path(recorded["path"])), recorded.get("stat")):
            return _unavailable(f"drift: dependency {name} dist-info changed since install")
    if full:
        try:
            manifest = _collect_dependency_manifest(layout["venv_python"])
        except RenderError as exc:
            return _unavailable(str(exc))
        for name in expected_names:
            wanted = marker_deps.get(name, {}).get("version")
            actual = manifest.get(name, {}).get("version")
            if actual != wanted:
                return _unavailable(f"drift: dependency {name} version {actual!r} != pinned {wanted!r}")

    if not layout["venv_python"].exists() or not layout["sa3_mlx"].exists():
        return _unavailable("drift: venv python or sa3_mlx.py missing")

    return {
        "available": True, "reason": "ready",
        "fingerprint": {
            "commit": expected_commit, "weights_revision": pins["weights"]["revision"],
            "code_lock_fingerprint": code_lock_fingerprint,
            "runtime_identity": _runtime_identity(expected_commit, code_lock_fingerprint, weight_hashes),
        },
    }


# ---- install -------------------------------------------------------------------

def _find_uv_executable() -> str:
    for candidate in UV_CANDIDATES:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    found = shutil.which("uv")
    if found and os.path.basename(os.path.realpath(found)) != "secret-shim":
        return found
    raise RenderError("no direct uv executable found (refusing the secret-shim uv)")


def _write_marker_if_changed(marker_path: Path, core: dict) -> None:
    existing = None
    if marker_path.exists():
        try:
            existing = {k: v for k, v in json.loads(marker_path.read_text()).items() if k != "installed_at"}
        except (OSError, ValueError):
            existing = None
    if existing == core:
        return  # resume: substantively identical marker already present
    marker = {**core, "installed_at": datetime.now(timezone.utc).isoformat()}
    tmp = marker_path.with_suffix(".json.tmp")
    tmp.write_bytes((json.dumps(marker, indent=2, sort_keys=True) + "\n").encode())
    os.replace(tmp, marker_path)


def install(root: str | Path | None = None, accept_terms: bool = False) -> dict:
    """Adopt (or, if absent, clone) the pinned checkout/venv/weights at root,
    downloading only what's missing, then write a fresh installed.json.

    Requires --accept-terms: an explicit personal-evaluation acknowledgment.
    Performs no account actions; commercial use needs separate registration
    with Stability AI. Refuses an existing checkout at the wrong commit or
    with local changes (no reset). Never deletes existing state. Always
    fully re-verifies (git, weight hashes, dependency manifest) even when
    adopting an already-populated root.
    """
    if not accept_terms:
        raise RenderError("install requires --accept-terms (personal evaluation only; "
                           "commercial use needs separate registration)")
    if not _is_supported_platform():
        raise RenderError("platform must be macOS arm64 (darwin/arm64)")

    root = Path(root).resolve() if root is not None else DEFAULT_ROOT
    pins, pins_raw = _load_pins()
    layout = _layout(root, pins)
    root.mkdir(parents=True, exist_ok=True)

    with _runtime_lock(layout["lock_file"]):
        expected_commit = pins["checkout"]["commit"]
        subpath = pins["checkout"]["subpath"]
        if layout["checkout"].is_dir():
            head, dirty = _git_check(layout["checkout"], subpath)
            if head != expected_commit:
                raise RenderError(f"existing checkout is at {head}, expected pinned {expected_commit}; "
                                   "refusing to reset")
            if dirty:
                raise RenderError("existing checkout has local changes under the pinned subpath; refusing to reset")
        else:
            _run(["/usr/bin/git", "clone", pins["checkout"]["repo"], str(layout["checkout"])], timeout=600)
            _run(["/usr/bin/git", "checkout", expected_commit], cwd=layout["checkout"], timeout=60)

        venv_python = layout["venv_python"]
        uv_bin = _find_uv_executable()
        if not venv_python.exists():
            _run([uv_bin, "venv", "--seed", "--python", pins["python"]["version"],
                 str(venv_python.parent.parent)], timeout=300)
        _run([uv_bin, "pip", "sync", "--require-hashes", "--python", str(venv_python), str(LOCK_PATH)], timeout=900)

        weight_records = []
        for entry in _weight_paths(layout, pins):
            cache_path = _download_weight(pins, entry, root)
            _ensure_runtime_link(entry["runtime_path"], cache_path, entry)
            weight_records.append({"repo_path": entry["repo_path"], "sha256": entry["sha256"],
                                   "bytes": entry["bytes"], "stat": _stat_fingerprint(entry["runtime_path"])})

        expected_names = _expected_dependency_names()
        manifest = _collect_dependency_manifest(venv_python)
        missing = [n for n in expected_names if n not in manifest]
        if missing:
            raise RenderError(f"venv is missing pinned packages: {missing}")
        dependency_records = {
            name: {"version": manifest[name]["version"], "path": str(_dist_info_stat_target(manifest[name]["dist_info"])),
                   "stat": _stat_fingerprint(_dist_info_stat_target(manifest[name]["dist_info"]))}
            for name in expected_names
        }

        core = {
            "schema_version": MARKER_SCHEMA_VERSION,
            "code_lock_fingerprint": _code_lock_fingerprint(pins_raw),
            "weights": weight_records,
            "dependencies": dependency_records,
            "python": {"venv_python": str(venv_python)},
        }
        _write_marker_if_changed(layout["marker"], core)

    return {"status": "ready", "root": str(root), "marker": str(layout["marker"])}


def refresh(root: str | Path | None = None, *, previous_adapter: str | Path) -> dict:
    """Offline, maintainer-only activation of an adapter-only source change.

    Old source bytes plus CURRENT pins/lock must reproduce the installed
    fingerprint. This proves the change is adapter-only without trusting a
    new pin set, resetting stat evidence, or weakening status(). All recorded
    dependency file hashes are checked, but RECORD is not signed: as with
    status(), this is drift detection, not a hostile-venv attestation.
    """
    if not _is_supported_platform():
        raise RenderError("platform must be macOS arm64 (darwin/arm64)")
    root = Path(root).resolve() if root is not None else DEFAULT_ROOT
    pins, pins_raw = _load_pins()
    layout = _layout(root, pins)
    marker_path = layout["marker"]
    if not marker_path.is_file() or marker_path.is_symlink():
        raise RenderError("refresh requires an existing regular installed.json marker")
    if layout["lock_file"].is_symlink():
        raise RenderError("refresh refuses a symlinked runtime lock")
    with _runtime_lock(layout["lock_file"]):
        original = marker_path.read_bytes()
        marker = json.loads(original)
        if marker.get("schema_version") != MARKER_SCHEMA_VERSION:
            raise RenderError("refresh requires the current installation marker schema")
        fingerprint = _code_lock_fingerprint(pins_raw)
        old_source = Path(previous_adapter).read_bytes()
        if (fingerprint != marker.get("code_lock_fingerprint")
                and _code_lock_fingerprint(pins_raw, adapter_source=old_source) != marker.get("code_lock_fingerprint")):
            raise RenderError("previous adapter with current pins/lock does not match installed fingerprint")
        if marker.get("python", {}).get("venv_python") != str(layout["venv_python"]):
            raise RenderError("drift: installed Python path differs from configured runtime")
        # Fast checks must also pass: full hashing must not silently bless
        # altered weight/RECORD stat evidence left by a different install.
        for full in (False, True):
            ready = _check_runtime(layout, pins, marker, full)
            if not ready["available"]:
                raise RenderError(ready["reason"])
        locked = {_normalize_name(name): version for name, version in re.findall(
            r"^([A-Za-z0-9_.\-]+)==([^\s\\]+)", LOCK_PATH.read_text(), re.MULTILINE)}
        manifest = _collect_dependency_manifest(layout["venv_python"])
        if not locked or set(manifest) != set(locked) or set(marker.get("dependencies", {})) != set(locked):
            raise RenderError("drift: installed dependency set differs from requirements.lock")
        venv = layout["venv_python"].parent.parent.resolve()
        for name, version in locked.items():
            info = manifest[name]
            record = Path(info["dist_info"]) / "RECORD"
            recorded = marker["dependencies"][name]
            if (info["version"] != version or recorded["version"] != version
                    or record != Path(recorded["path"]) or record.is_symlink()
                    or not record.resolve().is_relative_to(venv)):
                raise RenderError(f"drift: dependency {name} metadata does not match locked installation")
            checked = 0
            with record.open(newline="") as stream:
                for row in csv.reader(stream):
                    if len(row) != 3:
                        raise RenderError(f"drift: dependency {name} has malformed RECORD")
                    relative, encoded_hash, size = row
                    target = (record.parent.parent / relative).resolve()
                    if not target.is_relative_to(venv):
                        raise RenderError(f"drift: dependency {name} RECORD points outside its venv")
                    if not encoded_hash:
                        if target == record.resolve() or target.suffix == ".pyc":
                            continue  # RECORD itself and generated bytecode have no wheel hash.
                        raise RenderError(f"drift: dependency {name} has an unhashed installed file")
                    algorithm, separator, expected = encoded_hash.partition("=")
                    if not separator or algorithm not in ("sha256", "sha384", "sha512"):
                        raise RenderError(f"drift: dependency {name} has an unsupported RECORD hash")
                    if not target.is_file() or target.stat().st_size != int(size):
                        raise RenderError(f"drift: dependency {name} file missing or size mismatch")
                    with target.open("rb") as data:
                        digest = hashlib.file_digest(data, algorithm).digest()
                    if base64.urlsafe_b64encode(digest).rstrip(b"=").decode() != expected:
                        raise RenderError(f"drift: dependency {name} installed file hash mismatch")
                    checked += 1
            if not checked:
                raise RenderError(f"drift: dependency {name} RECORD has no hashed files")
        if marker_path.read_bytes() != original or _code_lock_fingerprint(_load_pins()[1]) != fingerprint:
            raise RenderError("installation marker or adapter/pins/lock changed during refresh")
        if fingerprint != marker["code_lock_fingerprint"]:
            marker["code_lock_fingerprint"] = fingerprint
            fd, temp = tempfile.mkstemp(prefix=".refresh-", dir=root)
            try:
                with os.fdopen(fd, "w") as stream:
                    json.dump(marker, stream, indent=2, sort_keys=True, allow_nan=False)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp, marker_path)
            finally:
                Path(temp).unlink(missing_ok=True)
    return {"status": "ready", "root": str(root), "marker": str(marker_path),
            "code_lock_fingerprint": fingerprint, "job_receipts_migrated": False}


# ---- payload validation --------------------------------------------------------

def _validate_payload(payload: dict, *, min_duration=MIN_DURATION,
                      max_duration=MAX_DURATION) -> tuple[str, float, int]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    allowed = {"text", "duration_seconds", "seed"}
    if set(payload) - allowed:
        raise ValueError(f"unknown payload keys: {sorted(set(payload) - allowed)}")
    if allowed - set(payload):
        raise ValueError(f"payload missing required key(s): {sorted(allowed - set(payload))}")

    text = payload["text"]
    if not isinstance(text, str) or isinstance(text, bool):
        raise ValueError("text must be a string")
    if not 1 <= len(text) <= MAX_TEXT_CHARS:
        raise ValueError(f"text must be 1..{MAX_TEXT_CHARS} characters")
    if not text.strip():
        raise ValueError("text must not be blank")

    duration = payload["duration_seconds"]
    if isinstance(duration, bool) or not isinstance(duration, (int, float)):
        raise ValueError("duration_seconds must be a finite number")
    duration = float(duration)
    if not math.isfinite(duration) or not min_duration <= duration <= max_duration:
        raise ValueError(f"duration_seconds must be finite in [{min_duration}, {max_duration}]")

    seed = payload["seed"]
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if not 0 <= seed <= MAX_SEED:
        raise ValueError(f"seed must be in [0, {MAX_SEED}]")

    return text, duration, seed


def _validate_out(out: Path) -> Path:
    out = Path(out).expanduser()
    if not out.is_absolute():
        raise ValueError("out must be an absolute path")
    if out.exists() or out.is_symlink():
        raise ValueError("out must be a new path (no overwrite, no symlink)")
    if not out.parent.is_dir():
        raise ValueError("out's parent directory must already exist")
    return out.parent.resolve() / out.name


# ---- render ---------------------------------------------------------------------

def _tail(path: Path, n: int = STDERR_TAIL_BYTES) -> str:
    try:
        return path.read_bytes()[-n:].decode("utf-8", "replace")
    except OSError:
        return "(log unavailable)"


def render(payload: dict, out: str | Path, root: str | Path | None = None) -> dict:
    """Render one Stable Audio 3 Medium/SAME-L take; publish a raw-needs-qa
    bundle at `out`. Raises RenderError for busy/not-ready/failed/timeout -
    nothing is published in those cases, and no retry is attempted. See the
    module docstring for the lock's scope if this parent process is killed."""
    return _render(payload, out, root, min_duration=MIN_DURATION,
                   max_duration=MAX_DURATION, max_bytes=MAX_BYTES)


def render_music(payload: dict, out: str | Path, root: str | Path | None = None) -> dict:
    """Explicit music entry: 1..60s, 32 MiB, otherwise the same locked recipe.

    The default render/CLI remains SFX-only. No installation, daemon, fallback
    or timeout increase is implied by this entry point.
    """
    return _render(payload, out, root, min_duration=1, max_duration=60,
                   max_bytes=32 * 1024 * 1024)


def _render(payload, out, root, *, min_duration, max_duration, max_bytes):
    text, duration_seconds, seed = _validate_payload(
        payload, min_duration=min_duration, max_duration=max_duration)
    out = _validate_out(Path(out))

    root = Path(root).resolve() if root is not None else DEFAULT_ROOT
    pins, _pins_raw = _load_pins()
    layout = _layout(root, pins)

    with _runtime_lock(layout["lock_file"]) as runtime_lock:
        state = status(root, full=False)
        if not state["available"]:
            raise RenderError(f"runtime not ready: {state['reason']}")

        gen = pins["generation"]
        with tempfile.TemporaryDirectory(prefix=".sa3-work-", dir=out.parent) as work_str:
            work = Path(work_str)
            raw_wav = work / "raw.wav"
            argv = [str(layout["venv_python"]), str(layout["sa3_mlx"]),
                    "--prompt", text, "--dit", gen["dit"], "--decoder", gen["decoder"],
                    "--seconds", str(duration_seconds), "--steps", str(gen["steps"]),
                    "--seed", str(seed), "--out", str(raw_wav)]
            env = {
                "PATH": "/opt/homebrew/bin:/usr/bin:/bin", "HOME": str(root),
                "TMPDIR": tempfile.gettempdir(), "LC_ALL": "en_US.UTF-8",
                "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
                "DO_NOT_TRACK": "1", "PYTHONDONTWRITEBYTECODE": "1",
            }
            stdout_path, stderr_path = work / "stdout.log", work / "stderr.log"
            start = time.monotonic()
            with stdout_path.open("xb") as stdout_f, stderr_path.open("xb") as stderr_f:
                process = _POPEN(argv, cwd=layout["mlx_dir"], env=env, stdin=subprocess.DEVNULL,
                                 stdout=stdout_f, stderr=stderr_f, start_new_session=True,
                                 pass_fds=(runtime_lock.fileno(),))
                try:
                    returncode = process.wait(timeout=gen["generation_timeout_seconds"])
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    raise RenderError(
                        f"generation exceeded {gen['generation_timeout_seconds']}s timeout; killed owned "
                        f"process group; stderr tail:\n{_tail(stderr_path)}")
                except BaseException:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    raise
            elapsed = time.monotonic() - start
            if returncode != 0:
                raise RenderError(f"generation subprocess exited {returncode}; stderr tail:\n{_tail(stderr_path)}")

            if not raw_wav.exists():
                raise RenderError("generation completed but raw.wav was not written")
            if raw_wav.stat().st_size > max_bytes:
                raise RenderError(f"raw.wav exceeds {max_bytes} bytes ({raw_wav.stat().st_size})")

            with wave.open(str(raw_wav), "rb") as wav_f:
                n_channels, sample_width = wav_f.getnchannels(), wav_f.getsampwidth()
                frame_rate, n_frames = wav_f.getframerate(), wav_f.getnframes()
                pcm_bytes = wav_f.readframes(n_frames)
            if (n_channels, sample_width, frame_rate) != (gen["channels"], gen["sample_width_bytes"], gen["sample_rate"]):
                raise RenderError(
                    f"unexpected WAV format: channels={n_channels} width={sample_width} rate={frame_rate} "
                    f"(expected {gen['channels']}ch {gen['sample_width_bytes'] * 8}-bit {gen['sample_rate']} Hz)")
            expected_len = n_frames * n_channels * sample_width
            if len(pcm_bytes) != expected_len:
                raise RenderError(f"WAV truncated: read {len(pcm_bytes)} PCM bytes, header declares {expected_len}")
            expected_frames = round(duration_seconds * gen["sample_rate"])
            if abs(n_frames - expected_frames) > FRAME_TOLERANCE:
                raise RenderError(f"unexpected frame count {n_frames}, expected {expected_frames} "
                                  f"(+/-{FRAME_TOLERANCE})")

            inference_log = work / "inference.log"
            inference_log.write_bytes(b"# stdout\n" + stdout_path.read_bytes() + b"\n# stderr\n" + stderr_path.read_bytes())
            receipt = {
                "engine": "local:stable-audio-3-medium",
                "model": {"commit": pins["checkout"]["commit"], "revision": pins["weights"]["revision"],
                         "runtime_fingerprint": state["fingerprint"]["runtime_identity"]},
                "request": {"text": text, "duration_seconds": duration_seconds, "seed": seed},
                "raw_wav": {
                    "sha256_pcm": hashlib.sha256(pcm_bytes).hexdigest(), "sha256_file": _sha256_file(raw_wav),
                    "sample_rate": frame_rate, "channels": n_channels, "sample_width_bytes": sample_width,
                    "frames": n_frames, "duration_seconds": n_frames / frame_rate, "elapsed_seconds": elapsed,
                    "inference_log": "inference.log",
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            take_path = work / "take.json"
            take_path.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")

            out.mkdir()
            try:
                shutil.move(str(raw_wav), str(out / "raw.wav"))
                shutil.move(str(inference_log), str(out / "inference.log"))
                shutil.move(str(take_path), str(out / "take.json"))
            except OSError:
                shutil.rmtree(out, ignore_errors=True)
                raise

    return {"status": "raw-needs-qa", "raw": str(out / "raw.wav"), "out": str(out),
            "take_json": str(out / "take.json"), "receipt": receipt}


# ---- CLI --------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subs = parser.add_subparsers(dest="command", required=True)

    p_install = subs.add_parser("install")
    p_install.add_argument("--accept-terms", action="store_true")
    p_install.add_argument("--root", default=None)

    p_check = subs.add_parser("check")
    p_check.add_argument("--full", action="store_true")
    p_check.add_argument("--root", default=None)

    p_refresh = subs.add_parser("refresh", help="Offline adapter-only marker refresh; never installs")
    p_refresh.add_argument("--previous-adapter", required=True)
    p_refresh.add_argument("--root", default=None)

    p_render = subs.add_parser("render")
    p_render.add_argument("--request", required=True)
    p_render.add_argument("--out", required=True)
    p_render.add_argument("--root", default=None)

    args = parser.parse_args(argv)
    try:
        if args.command == "install":
            result = install(root=args.root, accept_terms=args.accept_terms)
        elif args.command == "check":
            result = status(root=args.root, full=args.full)
        elif args.command == "refresh":
            result = refresh(root=args.root, previous_adapter=args.previous_adapter)
        else:
            result = render(json.loads(Path(args.request).read_text()), args.out, root=args.root)
    except (RenderError, ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result.get("available", True) else 1


if __name__ == "__main__":
    sys.exit(main())
