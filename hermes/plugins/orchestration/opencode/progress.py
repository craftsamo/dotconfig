"""A Phase's step list that a Hermes-driven run keeps in its output directory.

A run that implements a Phase writes `<output_dir>/progress.md`, one checklist line per
step (the operating note asks for it). The plugin only reads that file, to tell the
caller when a step finished or stalled. It is the run's own deliverable, not a run
record: nothing here writes it, and the run's state still comes from the service.
"""

from __future__ import annotations

import contextlib
import importlib.util
import os
from pathlib import Path
import re
import stat
import sys


def _load(name, filename):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent / filename)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


policy = _load("hermes_opencode_policy", "policy.py")

FILE = "progress.md"
# `- [x] Phase2.1 - title`: the marker, the step id and its title.
LINE = re.compile(r"^\s*[-*]\s*\[([ ~xX!])\]\s*(Phase\s*\d+(?:\s*\.\s*\d+)+)\s*(?:[-–—:]\s*)?(.*?)\s*$")
STATES = {" ": "pending", "~": "doing", "x": "done", "X": "done", "!": "blocked"}
# A state the caller hears about as it is reached.
REPORTED = ("done", "blocked")
SIZE_LIMIT = 65536
TITLE_LIMIT = 120


def location(meta):
    """`<output_dir>/progress.md` of a session's Hermes metadata, or None. The stored
    output directory is service metadata, so it is checked again before use."""
    stored = (meta or {}).get("output_dir")
    if not stored:
        return None
    with contextlib.suppress(ValueError, OSError):
        return Path(policy.output_dir(stored)) / FILE
    return None


def parse(text):
    """The checklist's steps in file order; a repeated id keeps its last line."""
    steps = {}
    for line in text.splitlines():
        match = LINE.match(line)
        if match:
            marker, step, title = match.groups()
            key = re.sub(r"\s+", "", step)
            steps.pop(key, None)
            steps[key] = {"id": key, "state": STATES[marker], "title": title[:TITLE_LIMIT]}
    return list(steps.values())


def read(meta):
    """The run's steps, or None when it keeps no progress file. Never follows a link
    and never reads more than SIZE_LIMIT bytes."""
    path = location(meta)
    if path is None:
        return None
    try:
        # Non-blocking, so a FIFO planted there cannot hang a status read or a notifier.
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        raw = os.read(fd, SIZE_LIMIT)
    except OSError:
        return None
    finally:
        os.close(fd)
    return parse(raw.decode("utf-8", errors="replace"))


def summary(steps):
    """What a state record carries: counts, the step in hand and any blocked step."""
    if not steps:
        return None
    out = {"done": sum(s["state"] == "done" for s in steps), "total": len(steps)}
    doing = [s["id"] for s in steps if s["state"] == "doing"]
    blocked = [{"id": s["id"], "title": s["title"]} for s in steps if s["state"] == "blocked"]
    if doing:
        out["doing"] = doing
    if blocked:
        out["blocked"] = blocked
    return out


def reached(before, after):
    """Steps that reached a reported state since `before` (a new step that arrives
    already finished or blocked counts too)."""
    earlier = {s["id"]: s["state"] for s in before or ()}
    return [s for s in after or () if s["state"] in REPORTED and earlier.get(s["id"]) != s["state"]]


class Watch:
    """A notifier's view of the progress file: the steps as they stood when it started,
    held in memory only. `__call__(now)` returns the steps that reached a reported state
    once `settle` seconds passed since the first of them, so steps finishing together
    arrive as one notification."""

    def __init__(self, meta, settle):
        self.meta, self.settle = meta, settle
        self.before = read(meta)
        self.since = None

    def __call__(self, now):
        changed = reached(self.before, read(self.meta))
        if not changed:
            self.since = None
            return None
        self.since = self.since if self.since is not None else now
        if now - self.since < self.settle:
            return None
        return [{"id": s["id"], "state": s["state"], "title": s["title"]} for s in changed]
