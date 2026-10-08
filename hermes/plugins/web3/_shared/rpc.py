"""JSON-RPC and HTTP for the web3 engine, run in the engine venv (docs/web3.md "Chains and RPC").

Provider keys (``ALCHEMY_API_KEY``, ``HELIUS_API_KEY``) are read from the Keychain scope
``web3-rpc`` with the ``secret`` CLI on first use, stdin closed. Provider URLs embed the key, so
nothing here ever lets a URL out: every error names the chain and the provider only, and
``mask`` scrubs any known secret from text before it leaves the process.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

import chains

SECRET = Path.home() / ".config" / "bin" / "secret"
RPC_SCOPE = "web3-rpc"
SECRET_TIMEOUT = 20
TIMEOUT = 20
USER_AGENT = "hermes-web3/1"
TEST_ENV = "WEB3_ENGINE_TEST"  # set only by the engine's own tests; the plugins pass a minimal env

BATCH_MAX = 10         # items per JSON-RPC batch: public endpoints refuse larger ones outright
BATCH_PAUSE = 1.0      # seconds before a retry round, times (1 + rounds in a row that accepted nothing)
BATCH_IDLE_ROUNDS = 5  # retry rounds in a row that accept nothing before giving up (about 15 s of waiting)
BATCH_ITEM_TRIES = 6   # times one item may be refused before it alone is given up

SECRETS: list[str] = []
_KEYS: dict[str, str | None] = {}


def rate_limited(error) -> bool:
    """A JSON-RPC error that means "slow down", not "this call fails"."""
    if not error:
        return False
    code = error.get("code") if isinstance(error, dict) else None
    message = str(error.get("message") if isinstance(error, dict) else error).lower()
    return code in (-32016, -32005, 429) or "rate limit" in message or "too many requests" in message


class ChainError(Exception):
    """A failure the caller sees as the result's error; its text never holds a URL or a key."""


def mask(text) -> str:
    text = str(text)
    for value in SECRETS:
        if value:
            text = text.replace(value, "…")
    return text


def secret(name: str, scope: str) -> str | None:
    """A Keychain value by name, or None when it is not stored (or the CLI is missing)."""
    key = f"{scope}/{name}"
    if key in _KEYS:
        return _KEYS[key]
    value = None
    if SECRET.exists():
        try:
            proc = subprocess.run([str(SECRET), "get", name, "-p", "hermes", "--scope", scope],
                                  stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                  timeout=SECRET_TIMEOUT)
            if proc.returncode == 0 and proc.stdout.strip():
                value = proc.stdout.strip()
                SECRETS.append(value)
        except subprocess.TimeoutExpired:
            value = None
    _KEYS[key] = value
    return value


def testing() -> bool:
    return os.environ.get(TEST_ENV) == "1"


class Rpc:
    """One chain's JSON-RPC endpoint: the provider's when its key is stored, else the public one."""

    def __init__(self, chain: str, override: str | None = None):
        self.chain = chain
        entry = chains.info(chain)
        self.url, self.provider = entry["rpc"], "public RPC"
        if override and testing():
            self.url, self.provider = override, "test RPC"
        elif chain in chains.EVM:
            key = secret("ALCHEMY_API_KEY", RPC_SCOPE)
            if key:
                self.url, self.provider = f"https://{entry['alchemy']}.g.alchemy.com/v2/{key}", "Alchemy"
        else:
            key = secret("HELIUS_API_KEY", RPC_SCOPE)
            if key:
                self.url = f"https://{entry['helius']}.helius-rpc.com/?api-key={urllib.parse.quote(key)}"
                self.provider = "Helius"
        self.ids = 0
        self.timeout = TIMEOUT

    @property
    def label(self) -> str:
        return f"{chains.info(self.chain)['name']} ({self.provider})"

    def _post(self, body):
        request = urllib.request.Request(self.url, data=json.dumps(body).encode(), method="POST",
                                         headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            hint = " (rate-limited; a provider key in the Keychain lifts this)" if exc.code == 429 else ""
            raise ChainError(f"{self.label} answered HTTP {exc.code}{hint}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise ChainError(f"{self.label} could not be reached ({mask(type(reason).__name__)})") from None
        except ValueError:
            raise ChainError(f"{self.label} returned something that is not JSON") from None

    def request(self, method: str, params=None) -> dict:
        """The whole reply of one call, an ``error`` member included (revert data lives there)."""
        self.ids += 1
        reply = self._post({"jsonrpc": "2.0", "id": self.ids, "method": method, "params": params or []})
        if not isinstance(reply, dict):
            raise ChainError(f"{self.label} returned an unexpected reply to {method}")
        return reply

    def call(self, method: str, params=None):
        """The result of one call; raises ChainError on an RPC error."""
        reply = self.request(method, params)
        if reply.get("error"):
            error = reply["error"]
            message = error.get("message") if isinstance(error, dict) else error
            raise ChainError(f"{self.label} refused {method}: {mask(message)[:300]}")
        return reply.get("result")

    def try_call(self, method: str, params=None):
        """(result, None) or (None, error text) — for optional parts of a result."""
        try:
            return self.call(method, params), None
        except ChainError as exc:
            return None, str(exc)

    def batch(self, calls: list[tuple[str, list]]) -> list:
        """Results in order, None for a call that failed (see ``batch_detailed`` for why)."""
        return [result for result, _ in self.batch_detailed(calls)]

    def batch_detailed(self, calls: list[tuple[str, list]]) -> list[tuple]:
        """(result, None) or (None, error text) per call, in order. Public endpoints answer only
        the first few items of a batch and refuse the rest as rate-limited, refilling slowly. So
        refused (and missing) items go again in rounds, each no larger than the previous round
        accepted and waiting longer after a round that accepted nothing, until a few such rounds
        in a row.
        Falls back to single calls when the endpoint refuses batches."""
        out: list[tuple] = [(None, "no reply")] * len(calls)
        pending = list(range(len(calls)))
        refused = [0] * len(calls)
        size, idle, first = min(len(calls), BATCH_MAX), 0, True
        while pending and idle < BATCH_IDLE_ROUNDS:
            if not first:
                time.sleep((0.02 if testing() else BATCH_PAUSE) * (1 + idle))
            send, rest = pending[:size], pending[size:]
            body, owner = [], {}
            for index in send:
                method, params = calls[index]
                self.ids += 1
                owner[self.ids] = index
                body.append({"jsonrpc": "2.0", "id": self.ids, "method": method, "params": params})
            try:
                reply = self._post(body)
            except ChainError as exc:
                if not first and "HTTP 429" in str(exc):  # the whole round was rate-limited
                    idle += 1
                    size = 1
                    continue
                reply = None
            if isinstance(reply, dict) and "batch" in str(reply.get("error", "")).lower() and size > 1:
                size = max(1, size // 2)  # "maximum N calls in 1 batch": smaller rounds
                continue
            if not isinstance(reply, list):
                if not first:  # a refused retry round: leave what is still pending unread
                    break
                for index in pending:
                    out[index] = self.try_call(*calls[index])
                return out
            first = False
            by_id = {item.get("id"): item for item in reply if isinstance(item, dict)}
            retry, answered = [], 0
            for request_id, index in owner.items():
                item = by_id.get(request_id)
                if item is None or rate_limited(item.get("error")):
                    refused[index] += 1
                    if refused[index] < BATCH_ITEM_TRIES:
                        retry.append(index)
                    out[index] = (None, f"{self.label} rate-limited the request")
                    continue
                answered += 1
                if item.get("error"):
                    error = item["error"]
                    message = error.get("message") if isinstance(error, dict) else error
                    out[index] = (None, f"{self.label} refused {calls[index][0]}: {mask(message)[:300]}")
                else:
                    out[index] = (item.get("result"), None)
            pending = rest + retry  # refused items wait behind the ones not yet tried
            idle = 0 if answered else idle + 1
            # grow back after a round that was fully answered, else send what the last one took
            size = min(BATCH_MAX, size * 2) if answered == len(send) else max(1, answered)
        return out


def http_json(url: str, timeout: int = 8):
    """GET a public JSON API (Sourcify, 4byte, CoinGecko); None on any failure or a 404."""
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
