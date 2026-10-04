"""Shared test helpers: a private state directory with a linked account, envelopes, and a fake
signal-cli daemon that answers JSON-RPC on a UNIX socket. Never the real signal-cli or state."""

import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
NUMBER = "+819000000000"
ME = "00000000-0000-4000-8000-000000000000"
ALICE = "11111111-1111-4111-8111-111111111111"
BOB = "22222222-2222-4222-8222-222222222222"
GROUP_ID = "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789+/AbCd="
GROUP = "group:" + GROUP_ID


def load(name):
    key = f"hermes_signal_{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module


def short_dir() -> Path:
    """UNIX socket paths are limited to ~104 bytes on macOS; pytest's tmp_path is too long."""
    return Path(tempfile.mkdtemp(prefix="sig-", dir="/tmp"))


def link_account(state: Path, *, registered=True) -> None:
    data = state / "signal-cli" / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "accounts.json").write_text(json.dumps(
        {"accounts": [{"path": "123", "environment": "LIVE", "number": NUMBER, "uuid": ME}], "version": 2}))
    (data / "123").write_text(json.dumps({"version": 9, "registered": registered}))


def envelope(source=ALICE, *, name="Alice", data=None, edit=None, sync=None, number="+819011111111"):
    env = {"source": number, "sourceNumber": number, "sourceUuid": source, "sourceName": name,
           "sourceDevice": 1, "timestamp": 1790000000000}
    if data is not None:
        env["dataMessage"] = {"expiresInSeconds": 0, "isExpirationUpdate": False, "viewOnce": False, **data}
    if edit is not None:
        env["editMessage"] = edit
    if sync is not None:
        env["syncMessage"] = sync
    return {"account": NUMBER, "envelope": env}


class FakeDaemon:
    """Answers JSON-RPC requests on a UNIX socket with handlers[method](params) -> result,
    or raises (code, message, data) tuples as errors. Records every request."""

    def __init__(self, path: Path, handlers: dict):
        self.path = Path(path)
        self.handlers = handlers
        self.requests = []
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(self.path))
        self.server.listen(8)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            threading.Thread(target=self._client, args=(conn,), daemon=True).start()

    def _client(self, conn):
        buffer = b""
        with conn:
            while True:
                try:
                    chunk = conn.recv(65536)
                except OSError:
                    return
                if not chunk:
                    return
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    request = json.loads(line)
                    self.requests.append(request)
                    handler = self.handlers.get(request["method"])
                    if handler is None:
                        reply = {"jsonrpc": "2.0", "id": request["id"],
                                 "error": {"code": -32601, "message": "Method not implemented"}}
                    else:
                        try:
                            reply = {"jsonrpc": "2.0", "id": request["id"],
                                     "result": handler(request.get("params") or {})}
                        except FakeError as exc:
                            reply = {"jsonrpc": "2.0", "id": request["id"], "error": exc.payload}
                    if reply.get("result") is not NO_REPLY:
                        conn.sendall(json.dumps(reply).encode() + b"\n")

    def close(self):
        self.server.close()
        try:
            os.unlink(self.path)
        except OSError:
            pass


NO_REPLY = object()


class FakeError(Exception):
    def __init__(self, code, message, data=None):
        super().__init__(message)
        self.payload = {"code": code, "message": message, **({"data": data} if data is not None else {})}
