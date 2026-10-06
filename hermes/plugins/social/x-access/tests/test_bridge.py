"""The real bridge in the engine venv, with a fake ``secret`` CLI and no request to X."""

import json
import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "bridge.py"
PYTHON = ROOT.parents[2] / "local" / "twscrape" / "venv" / "bin" / "python"
AUTH, CT0 = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0", "c0ffeec0ffeec0ffeec0ffeec0ffee"

pytestmark = pytest.mark.skipif(not PYTHON.exists(), reason="engine venv not installed (scripts/x-access.sh install)")


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    (h / ".config" / "bin").mkdir(parents=True)
    return h


def fake_secret(home: Path, value: str | None):
    script = home / ".config" / "bin" / "secret"
    body = f"printf '%s\\n' '{value}'" if value is not None else "exit 1"
    script.write_text(f"#!/bin/sh\n[ \"$*\" = 'get X_READER_COOKIES -p hermes --scope x-reader' ] || exit 9\n{body}\n")
    script.chmod(0o755)


def run(home: Path, cwd: Path, **request):
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "TWS_TELEMETRY": "0", "TWS_LOG_LEVEL": "WARNING"}
    proc = subprocess.run([str(PYTHON), str(BRIDGE)], input=json.dumps(request), capture_output=True, text=True,
                          env=env, cwd=cwd, timeout=60)
    assert AUTH not in proc.stdout + proc.stderr and CT0 not in proc.stdout + proc.stderr
    return json.loads(proc.stdout)


def test_check_reads_the_keychain_but_not_x(home, tmp_path):
    fake_secret(home, f"auth_token={AUTH}; ct0={CT0}")
    reply = run(home, tmp_path, op="check")
    assert reply["ok"] is True and reply["contacted"] is False and len(reply["fingerprint"]) == 12


def test_a_refused_fingerprint_short_circuits(home, tmp_path):
    fake_secret(home, f"auth_token={AUTH}; ct0={CT0}")
    fingerprint = run(home, tmp_path, op="check")["fingerprint"]
    reply = run(home, tmp_path, op="search", query="x", limit=1, refused=fingerprint)
    assert reply == {"ok": False, "kind": "refused", "fingerprint": fingerprint, "contacted": False, "warnings": []}


@pytest.mark.parametrize("value,match", [
    (None, "no sub-account cookies in the Keychain"),
    (f"auth_token={AUTH}", "both auth_token and ct0"),
])
def test_missing_or_partial_cookies_are_setup_errors(home, tmp_path, value, match):
    fake_secret(home, value)
    reply = run(home, tmp_path, op="search", query="x", limit=1)
    assert reply["kind"] == "setup" and match in reply["error"] and reply["contacted"] is False


def test_the_account_pool_stays_in_memory(home, tmp_path):
    """The pool twscrape gets is the in-memory database: the session never reaches a file."""
    script = tmp_path / "probe.py"
    script.write_text(f"""
import asyncio, json, sys
sys.path.insert(0, {str(ROOT)!r})
import bridge
async def main():
    from twscrape import API
    anchor = bridge._memory_pool()
    api = API(bridge.POOL)
    await api.pool.add_account_cookies(bridge.ACCOUNT, "auth_token={AUTH}; ct0={CT0}")
    print(json.dumps(await bridge._session(api)))
    anchor.close()
asyncio.run(main())
""")
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "TWS_TELEMETRY": "0", "TWS_LOG_LEVEL": "WARNING"}
    proc = subprocess.run([str(PYTHON), str(script)], capture_output=True, text=True, env=env, cwd=tmp_path, timeout=60)
    assert json.loads(proc.stdout.strip().splitlines()[-1]) == {"active": True, "error": None, "locks": {}}
    files = [p for p in tmp_path.rglob("*") if p.is_file() and p.name != "probe.py"]
    assert not any(AUTH.encode() in p.read_bytes() for p in files) and not any("x-access-pool" in p.name for p in files)
    assert not [p for p in tmp_path.iterdir() if p.name.startswith("file:")]


def test_mask_scrubs_cookie_values():
    namespace = {}
    exec(compile((ROOT / "bridge.py").read_text(), "bridge.py", "exec"), namespace)
    namespace["SECRETS"].extend([AUTH, CT0])
    assert namespace["mask"](f"bad cookie {AUTH} and {CT0}") == "bad cookie … and …"
