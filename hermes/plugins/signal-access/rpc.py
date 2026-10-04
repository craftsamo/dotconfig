"""signal-access JSON-RPC client for the signal-cli daemon's UNIX socket.

Newline-delimited JSON-RPC 2.0 (``signal-cli daemon --socket``; man signal-cli-jsonrpc(5)).
Standard library only: the sync agent and the plugin both use it. A connection made here never
subscribes, so (with ``--receive-mode manual``) it only ever sees its own responses.
"""

from __future__ import annotations

import itertools
import json
import select
import socket
import time
from pathlib import Path

_ids = itertools.count(1)


class RpcError(Exception):
    """signal-cli answered with a JSON-RPC error."""

    def __init__(self, code, message, data=None):
        super().__init__(message or f"signal-cli error {code}")
        self.code = code
        self.data = data


class NotConnected(Exception):
    """The daemon could not be reached: nothing was written to it."""


class NoAnswer(Exception):
    """The request was written but no answer came in time: its effect is unknown."""


class Connection:
    def __init__(self, path: Path, timeout: float = 10.0):
        self.path = Path(path)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        try:
            self.sock.connect(str(self.path))
        except OSError as exc:
            self.sock.close()
            raise NotConnected(f"the Signal sync service is not running ({exc.strerror or exc})") from exc
        self.buffer = b""

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def write(self, payload: dict) -> None:
        self.sock.sendall(json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n")

    def readline(self, timeout: float | None) -> dict | None:
        """The next JSON message, None when ``timeout`` passes first; EOFError when the daemon hung up."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while b"\n" not in self.buffer:
            remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
            ready, _, _ = select.select([self.sock], [], [], remaining)
            if not ready:
                return None
            chunk = self.sock.recv(65536)
            if not chunk:
                raise EOFError("the signal-cli daemon closed the connection")
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b"\n", 1)
        line = line.strip()
        if not line:
            return self.readline(None if deadline is None else max(0.0, deadline - time.monotonic()))
        return json.loads(line.decode("utf-8"))

    def call(self, method: str, params: dict | None = None, timeout: float = 30.0):
        request = {"jsonrpc": "2.0", "id": next(_ids), "method": method}
        if params:
            request["params"] = params
        try:
            self.write(request)
        except OSError as exc:
            raise NotConnected(f"could not write to the Signal sync service ({exc})") from exc
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise NoAnswer(f"signal-cli did not answer {method} within {int(timeout)}s")
            try:
                message = self.readline(remaining)
            except (OSError, EOFError, ValueError) as exc:
                raise NoAnswer(f"lost the connection to signal-cli during {method} ({exc})") from exc
            if message is None:
                continue
            if message.get("id") != request["id"]:
                continue  # a notification or a stray answer
            if "error" in message:
                error = message["error"] or {}
                raise RpcError(error.get("code"), error.get("message"), error.get("data"))
            return message.get("result")


def call(path: Path, method: str, params: dict | None = None, timeout: float = 30.0):
    """One request on its own short connection."""
    with Connection(path, timeout=min(timeout, 10.0)) as conn:
        return conn.call(method, params, timeout=timeout)
