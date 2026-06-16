"""_cross — shared cross-skill contract + resolver for the workspaces skill cluster (stdlib only).

Lives at skills/workspaces/_cross.py, beside its consumers (people / household-budget / projects /
message-reply). The integration convention across these workspace-data skills:

  * Cross-domain reads call a SIBLING SKILL'S CLI — never open its DB or read its files,
    and never call its `validate` (prevents mutual recursion). Writes never cross domains.
  * A producer answers a read with a JSON envelope on stdout:
        {"contract_version": N, "skill": "<logical-name>", "data": <payload>}
  * A consumer resolves the sibling CLI, runs a read subcommand, checks contract_version,
    and SKIPS WITH A WARNING on absence / error / version skew (mirrors the old behaviour:
    "every cross-store check skips with a warning if the other store is absent").

Resolution order for a logical skill name (resolve()):
  1. env override  <CLI>_BIN   (e.g. PP_BIN, HB_BIN, PJ_BIN) — absolute path to the CLI
  2. manifest      <cluster>/cross.json  ->  {"people": "/abs/path/pp", ...}
  3. convention    <cluster>/<name>/scripts/<cli>          (all siblings share this dir)

`call()` execs the sibling CLI DIRECTLY (argv0 = pp/hb/pj, allowlist-friendly), falling back to
the interpreter only if the file is not directly executable.

Imported by adding the cluster dir (this file's parent) to sys.path, e.g.:
    import sys; from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # skills/workspaces/
    try:
        import _cross
    except Exception:
        _cross = None        # degrade: skip cross-domain checks
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

CONTRACT_VERSION = 1

# logical skill name -> cli basename. The skill dir == the logical name (same cluster dir).
REGISTRY = {
    "people": "pp",
    "household-budget": "hb",
    "projects": "pj",
}


def cluster_root() -> Path:
    """The workspaces cluster dir (this module sits directly in it)."""
    return Path(__file__).resolve().parent


def warn(msg: str) -> None:
    print(f"WARN: cross: {msg}", file=sys.stderr)


def resolve(skill: str) -> Optional[Path]:
    """Resolve a logical skill name to its CLI path, or None if unavailable."""
    cli = REGISTRY.get(skill)
    if not cli:
        return None
    # 1. explicit env override
    env_path = os.environ.get(f"{cli.upper()}_BIN")
    if env_path and Path(env_path).exists():
        return Path(env_path)
    # 2. manifest
    manifest = cluster_root() / "cross.json"
    if manifest.exists():
        try:
            mapped = json.loads(manifest.read_text(encoding="utf-8")).get(skill)
            if mapped and Path(mapped).exists():
                return Path(mapped)
        except Exception as e:  # malformed manifest must not break callers
            warn(f"ignoring cross.json ({e})")
    # 3. convention (siblings in the same cluster dir)
    p = cluster_root() / skill / "scripts" / cli
    return p if p.exists() else None


def available(skill: str) -> bool:
    return resolve(skill) is not None


def envelope(skill: str, data) -> dict:
    """Wrap a read payload in the cross-skill envelope (for producers)."""
    return {"contract_version": CONTRACT_VERSION, "skill": skill, "data": data}


def emit(skill: str, data) -> None:
    """Print a read payload as a contract envelope on stdout (for producers)."""
    print(json.dumps(envelope(skill, data), ensure_ascii=False, indent=2))


def call(skill: str, argv, *, root: Optional[str] = None, timeout: int = 30):
    """Call a sibling skill's read subcommand; return its `data`, or None (skip) on any failure.

    argv is the subcommand + flags, e.g. ["list", "--json"]. A global --root (if given) is
    placed before the subcommand, matching the CLIs' argparse layout. The CLI is run DIRECTLY
    (argv0 = the cli, e.g. `pj members --json`) so it is recognizable to a command allowlist;
    if the file is not directly executable we fall back to running it via this interpreter.
    Never raises: on any problem it warns and returns None so cross-checks degrade gracefully.
    """
    cli = resolve(skill)
    if cli is None:
        warn(f"cannot resolve skill {skill!r}; skipping cross-call {argv}")
        return None
    tail = (["--root", str(root)] if root else []) + list(argv)
    proc = None
    for cmd in ([str(cli), *tail], [sys.executable, str(cli), *tail]):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            break
        except (PermissionError, OSError):
            proc = None
            continue  # not directly executable -> retry via the interpreter
        except Exception as e:
            warn(f"failed to run {skill} {argv}: {e}; skipping")
            return None
    if proc is None:
        warn(f"failed to exec {skill} {argv}; skipping")
        return None
    if proc.returncode != 0:
        warn(f"{skill} {argv} exited {proc.returncode}: {proc.stderr.strip()}; skipping")
        return None
    try:
        env = json.loads(proc.stdout)
    except Exception as e:
        warn(f"{skill} {argv} produced non-JSON output ({e}); skipping")
        return None
    cv = env.get("contract_version")
    if cv != CONTRACT_VERSION:
        warn(f"{skill} contract_version {cv!r} != {CONTRACT_VERSION}; skipping")
        return None
    return env.get("data")
