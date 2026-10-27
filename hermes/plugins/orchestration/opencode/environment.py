"""What the OpenCode service is and runs with, read-only: its process, the paths it
uses, the configuration sources it loaded, its plugins, MCP servers and locations.

Nothing here returns a value from a configuration file or a process environment:
a config document is reduced to its shape (paths, key names, counts) and the
service's environment to a classification, because the service keeps its
starter's environment for every session and a config may carry headers or
account settings.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def _load(name, filename):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent / filename)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


api = _load("hermes_opencode_api", "api.py")

# Names a process gets from its launcher, the system or OpenCode itself rather than
# from a shell, so they do not tell a person's environment from the plugin's minimal one.
SYSTEM_NAMES = {"_", "PWD", "OLDPWD", "SHLVL", "XPC_FLAGS", "XPC_SERVICE_NAME", "__CF_USER_TEXT_ENCODING"}
SYSTEM_PREFIXES = ("OPENCODE_",)
ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
# The service's environment, by where it came from (`service`): the person's shell, the
# plugin's minimal client environment (then every session, the person's own included,
# runs without their shell's variables), or unreadable.
PERSON_SHELL, HERMES_MINIMAL, UNKNOWN = "person-shell", "hermes-minimal", "unknown"
PS_TIMEOUT = 15
INFO_KEYS = {"version": str, "pid": int, "urls": list, "paths": dict, "capabilities": dict}
# `opencode debug paths` labels; the output is `<label><spaces><path>` per line.
PATH_LABELS = ("home", "data", "cache", "config", "state", "tmp", "bin", "log", "repos", "db")


def _text(value):
    return value if isinstance(value, str) else None


def info(body):
    """`/api/info` as the catalog reports it: scalars, string lists and string maps only."""
    if not isinstance(body, dict):
        return {}
    out = {}
    for key, kind in INFO_KEYS.items():
        value = body.get(key)
        if kind is list and isinstance(value, list):
            out[key] = [v for v in value if isinstance(v, str)]
        elif kind is dict and isinstance(value, dict):
            out[key] = {k: v for k, v in value.items() if isinstance(v, (str, bool))}
        elif kind in (str, int) and isinstance(value, kind) and not isinstance(value, bool):
            out[key] = value
    return out


def _items(body):
    items = body.get("data") if isinstance(body, dict) else body
    return items if isinstance(items, list) else []


def plugins(body):
    out = []
    for item in _items(body)[:300]:
        if not isinstance(item, dict):
            continue
        source = item.get("source") if isinstance(item.get("source"), dict) else {}
        state = item.get("state") if isinstance(item.get("state"), dict) else {}
        entry = {"id": _text(item.get("id")), "source": _text(source.get("type")),
                 "status": _text(state.get("status"))}
        if _text(source.get("path")):
            entry["path"] = source["path"]
        if isinstance(item.get("features"), dict):
            entry["features"] = sorted(k for k, v in item["features"].items() if v)
        out.append(entry)
    return out


def mcp(body):
    out = []
    for item in _items(body)[:100]:
        if not isinstance(item, dict):
            continue
        status = item.get("status") if isinstance(item.get("status"), dict) else {}
        out.append({"name": _text(item.get("name")), "status": _text(status.get("status"))})
    return out


def locations(body):
    return [item["directory"] for item in _items(body)[:300] if isinstance(item, dict) and _text(item.get("directory"))]


def _names(value):
    return sorted(k for k in value if isinstance(k, str)) if isinstance(value, dict) else []


# A plugin spec as a name: a package (`@scope/name@1.2.3`) or a local path. A spec that
# is a URL can carry a token in its userinfo or query, so it is reduced to its host.
PACKAGE = re.compile(r"[A-Za-z0-9@._~/-]+\Z")


def _package(spec):
    if isinstance(spec, dict):
        spec = spec.get("package")
    if not isinstance(spec, str):
        return None
    if "://" in spec:
        host = spec.split("://", 1)[1].split("/", 1)[0].rsplit("@", 1)[-1].split("?", 1)[0]
        return spec.split("://", 1)[0] + "://" + host + "/…"
    return spec if PACKAGE.fullmatch(spec) else None


def config_sources(body):
    """Each loaded configuration source as its shape: the path, the top-level keys, and
    for the keys that name things (agents, plugins, MCP servers, providers) those
    names; counts for rule lists. Values never."""
    out = []
    for item in _items(body)[:50]:
        if not isinstance(item, dict):
            continue
        entry = {"type": _text(item.get("type")), "path": _text(item.get("path"))}
        doc = item.get("info") if isinstance(item.get("info"), dict) else None
        if doc is None:
            out.append(entry)
            continue
        entry["keys"] = _names(doc)
        if isinstance(doc.get("agents"), dict):
            entry["agents"] = _names(doc["agents"])
        if isinstance(doc.get("plugins"), list):
            entry["plugins"] = [_package(p) for p in doc["plugins"]]
        servers = doc["mcp"].get("servers") if isinstance(doc.get("mcp"), dict) else None
        if isinstance(servers, dict):
            entry["mcp"] = {name: {"type": _text(s.get("type")), **({"disabled": True} if s.get("disabled") else {})}
                            for name, s in servers.items() if isinstance(name, str) and isinstance(s, dict)}
        if isinstance(doc.get("providers"), dict):
            entry["providers"] = _names(doc["providers"])
        for key in ("permissions", "policies"):
            if isinstance(doc.get(key), list):
                entry[f"{key}_count"] = len(doc[key])
        out.append(entry)
    return out


# --------------------------------------------------------------------------
# The service process


def _ps(args):
    try:
        proc = subprocess.run(["ps", *args], capture_output=True, text=True, timeout=PS_TIMEOUT,
                              stdin=subprocess.DEVNULL, env=api.child_env())
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout if not proc.returncode else None


def process(pid):
    """The service process as `ps` reports it: parent, start time and executable."""
    if type(pid) is not int or pid <= 0:
        return {}
    text = _ps(["-o", "ppid=,lstart=,comm=", "-p", str(pid)])
    if not text or not text.strip():
        return {}
    fields = text.strip().split(None, 1)
    out = {"pid": pid}
    if fields and fields[0].isdigit():
        out["parent_pid"] = int(fields[0])
    rest = fields[1] if len(fields) > 1 else ""
    # lstart is five space-separated words; the executable follows.
    words = rest.split(None, 5)
    if len(words) >= 6:
        out["started"] = " ".join(words[:5])
        out["executable"] = words[5].strip()
    elif words:
        out["executable"] = rest.strip()
    return out


def environment_kind(pid):
    """How the service's environment reads from its variable names alone (`ps -E`,
    macOS): the person's shell when any name beyond the plugin's minimal set and the
    system's is present, the plugin's minimal environment when none is, unknown when
    `ps` cannot show it. Values are never read."""
    if type(pid) is not int or pid <= 0:
        return UNKNOWN, 0
    text = _ps(["-Eww", "-o", "command=", "-p", str(pid)])
    if not text or "=" not in text:
        return UNKNOWN, 0
    # The column holds the command, its arguments and then the environment; an option
    # (`--flag=x`) is not an identifier, so it never counts as a name.
    names = {name for name, sep, _ in (token.partition("=") for token in text.split()) if sep and ENV_NAME.fullmatch(name)}
    if not names:
        return UNKNOWN, 0
    minimal = api.ENV_NAMES | SYSTEM_NAMES
    extra = {n for n in names if n not in minimal and not n.startswith(api.ENV_PREFIXES + SYSTEM_PREFIXES)}
    return (PERSON_SHELL if extra else HERMES_MINIMAL), len(extra)


def paths():
    """`opencode debug paths` as a map; empty when the command fails."""
    try:
        proc = subprocess.run(["opencode", "debug", "paths"], capture_output=True, text=True, timeout=30,
                              stdin=subprocess.DEVNULL, env=api.child_env())
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if proc.returncode:
        return {}
    out = {}
    for line in proc.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0] in PATH_LABELS and os.path.isabs(parts[1].strip()):
            out[parts[0]] = parts[1].strip()
    return out


def client():
    """The `opencode` the plugin's client processes run, and the file it resolves to."""
    found = shutil.which("opencode", path=api.child_env().get("PATH"))
    if not found:
        return {}
    out = {"command": found}
    real = os.path.realpath(found)
    if real != found:
        out["resolves_to"] = real
    return out


def service(body):
    """The service behind `/api/info`: version, listen URLs, process, environment kind,
    paths and the client command. Each part is best effort and absent when unreadable."""
    head = info(body)
    out = {k: head[k] for k in ("version", "urls") if k in head}
    pid = head.get("pid")
    proc = process(pid)
    if proc:
        out["process"] = proc
    kind, extra = environment_kind(pid)
    out["environment"] = {"kind": kind, **({"names_beyond_minimal": extra} if kind == PERSON_SHELL else {})}
    found = paths()
    if found:
        out["paths"] = found
    elif isinstance(head.get("paths"), dict):
        out["paths"] = head["paths"]
    which = client()
    if which:
        out["client"] = which
    return out
