"""turn_env: a value the launching shell set for this one turn (``RESIDENT_DEADLINE``, ...).

A turn started as ``hermes chat -q`` used to run inside that CLI process, so plugin code read the
shell's environment. Where the CLI is a gateway client, the turn runs inside the gateway: the
launching shell's values never arrive, and the gateway's own environment is not the turn's (a
gateway the CLI started on demand may even carry a resident's stale values). There the value is
unknown and ``default`` is answered, so callers degrade to their own bounds.

Shared by the orchestration plugins (each loads this file by path; it is not a plugin and has no
manifest).
"""

from __future__ import annotations

import functools
import importlib.util
import os


@functools.cache
def gateway_client_runtime() -> bool:
    """Whether this runtime runs CLI turns inside the gateway rather than in the CLI process."""
    return importlib.util.find_spec("hermes_cli.gateway_agent") is not None


def value(name: str, default: str = "") -> str:
    """The value ``name`` had in the shell that launched this turn, else ``default``."""
    if gateway_client_runtime():
        return default
    return os.environ.get(name, default)
