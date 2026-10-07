"""Client for the shared OpenCode 2 service, through the documented `opencode api` command.

`opencode api` finds (or starts) the person's background service and authenticates
the way the TUI does, so no server address or password is handled here. Its output
goes to files, never a pipe: on 2.0.23 a piped reply is cut off at a buffer
boundary (64/256 KiB) with exit status zero.

Query strings are built into the path. `--param` silently drops query parameters
(measured: `parentID` was ignored and every session came back).

Stdlib only: the history CLI runs this from cron without Hermes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import urllib.parse

TIMEOUT = 60
STATUS = re.compile(r"HTTP (\d{3})")


class Unavailable(Exception):
    """The service could not be reached or did not answer usably."""


class ApiError(Exception):
    """The service answered with a client error (4xx) for this request."""

    def __init__(self, status, tag, message):
        super().__init__(f"OpenCode API {status} {tag or ''}: {message}".strip())
        self.status, self.tag, self.detail = status, tag, message


# `opencode api` starts the shared background service when none is running, and
# the service keeps its starter's environment for every session it later serves,
# a person's included. Only what locating the user's tools and config needs
# passes through; gateway secrets, bot tokens and Hermes turn state never do.
ENV_NAMES = {"PATH", "HOME", "USER", "LOGNAME", "SHELL", "LANG", "TERM", "TMPDIR", "TZ"}
ENV_PREFIXES = ("LC_", "XDG_")


def child_env(extra=None):
    """A minimal environment for OpenCode client processes."""
    env = {k: v for k, v in os.environ.items() if k in ENV_NAMES or k.startswith(ENV_PREFIXES)}
    env.update(extra or {})
    return env


def path(template, query=None, **segments):
    """`/api/session/{sessionID}` with quoted segments and an encoded query string."""
    result = template.format(**{k: urllib.parse.quote(str(v), safe="") for k, v in segments.items()})
    query = {k: v for k, v in (query or {}).items() if v is not None}
    return result + ("?" + urllib.parse.urlencode(query) if query else "")


def location(directory):
    """The deepObject query naming a location, as the location-scoped routes expect."""
    return {"location[directory]": directory}


def call(method, route, data=None, *, timeout=TIMEOUT, executable="opencode"):
    """One request. Returns the decoded JSON body, or None for an empty reply."""
    command = [executable, "api", method.lower(), route]
    if data is not None:
        command += ["--data", json.dumps(data)]
    try:
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            proc = subprocess.run(command, stdout=out, stderr=err, stdin=subprocess.DEVNULL,
                                  timeout=timeout, env=child_env())
            out.seek(0)
            err.seek(0)
            body, stderr = out.read().decode("utf-8", "replace"), err.read().decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        raise Unavailable(f"opencode api {method.upper()} timed out") from None
    except OSError as exc:
        raise Unavailable(f"opencode api could not run: {exc.__class__.__name__}") from None
    try:
        decoded = json.loads(body) if body.strip() else None
    except ValueError:
        decoded = None
        if not proc.returncode:
            raise Unavailable(f"opencode api {method.upper()} returned malformed JSON") from None
    if not proc.returncode:
        return decoded
    status = STATUS.search(stderr)
    code = int(status.group(1)) if status else None
    if code and 400 <= code < 500:
        tag = decoded.get("_tag") if isinstance(decoded, dict) else None
        message = decoded.get("message") if isinstance(decoded, dict) else None
        raise ApiError(code, tag, message or stderr.strip()[:200])
    raise Unavailable(f"opencode api {method.upper()} failed" + (f" with HTTP {code}" if code else ""))


def data(body, kind=dict):
    """The `data` member of a reply, checked for its expected type."""
    if not isinstance(body, dict) or not isinstance(body.get("data"), kind):
        raise Unavailable("unexpected OpenCode API reply shape")
    return body["data"]
