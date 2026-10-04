"""The sync agent against a fake signal-cli: a small script that serves the daemon's socket,
answers subscribeReceive, emits envelopes, then exits like a daemon whose device was unlinked
(or crashed). Never the real signal-cli."""

import importlib.util
import json
from pathlib import Path
import shutil
import sys
import textwrap

import pytest

spec = importlib.util.spec_from_file_location("signal_access_fakes", Path(__file__).resolve().parent / "fakes.py")
fakes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fakes)

store = fakes.load("store")
sync = fakes.load("sync")

FAKE_CLI = textwrap.dedent("""
    import json, os, socket, sys, threading, time
    argv = sys.argv[1:]
    path = argv[argv.index("--socket") + 1]
    events = json.loads(os.environ["FAKE_EVENTS"])
    ending = os.environ.get("FAKE_ENDING", "crash")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    server.listen(4)
    subscribed = threading.Event()
    holder = {}

    def client(conn):
        buffer = b""
        while True:
            chunk = conn.recv(65536)
            if not chunk:
                return
            buffer += chunk
            while b"\\n" in buffer:
                line, buffer = buffer.split(b"\\n", 1)
                request = json.loads(line)
                method = request["method"]
                if method == "subscribeReceive":
                    result = 7
                    early = json.loads(os.environ.get("FAKE_EARLY", "[]"))
                    for event in early:  # emitted before the subscription's own answer
                        note = {"jsonrpc": "2.0", "method": "receive", "params": {"subscription": 7, "result": event}}
                        conn.sendall(json.dumps(note).encode() + b"\\n")
                elif method == "listContacts":
                    result = [{"uuid": "%(alice)s", "number": "+819011111111", "givenName": "Alice"}]
                else:
                    result = []
                conn.sendall(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}).encode() + b"\\n")
                if method == "subscribeReceive":
                    holder["sub"] = conn
                    subscribed.set()

    def serve():
        while True:
            conn, _ = server.accept()
            threading.Thread(target=client, args=(conn,), daemon=True).start()

    threading.Thread(target=serve, daemon=True).start()
    subscribed.wait(30)
    time.sleep(0.5)
    for event in events:
        note = {"jsonrpc": "2.0", "method": "receive", "params": {"subscription": 7, "result": event}}
        holder["sub"].sendall(json.dumps(note).encode() + b"\\n")
    if ending != "abrupt":
        time.sleep(0.5)
    if ending == "unlinked":
        print("ERROR AuthorizationFailedException: device is no longer linked", file=sys.stderr, flush=True)
        os._exit(0)
    os._exit(3)
""") % {"alice": fakes.ALICE}


@pytest.fixture
def agent(monkeypatch):
    base = fakes.short_dir()
    monkeypatch.setenv(store.STATE_ENV, str(base))
    fake = base / "fake-signal-cli.py"
    fake.write_text(FAKE_CLI)
    monkeypatch.setattr(sync, "cli_path", lambda: sys.executable)
    real_argv = sync.daemon_argv
    monkeypatch.setattr(sync, "daemon_argv", lambda cli, state, number: [cli, str(fake), *real_argv(cli, state, number)[1:]])
    sync._stop.clear()
    yield base
    shutil.rmtree(base, ignore_errors=True)


def events(*payloads):
    return json.dumps(list(payloads))


def test_no_account_exits_quietly(agent):
    assert sync.run() == 0
    conn = store.connect(store.db_path(agent))
    assert store.get_meta(conn)["status"] == "not linked"


def test_unlinked_before_start(agent):
    fakes.link_account(agent, registered=False)
    assert sync.run() == 0
    assert store.get_meta(store.connect(store.db_path(agent)))["status"] == "unlinked"


def test_mirrors_events_then_restarts_after_a_crash(agent, monkeypatch):
    fakes.link_account(agent)
    monkeypatch.setenv("FAKE_EVENTS", events(
        fakes.envelope(data={"timestamp": 1790000000000, "message": "hello"}),
        {"account": fakes.NUMBER, "exception": {"message": "decrypt failed"}},
        fakes.envelope(fakes.ME, sync={"sentMessage": {"destinationUuid": fakes.ALICE, "timestamp": 1790000001000,
                                                       "message": "hi back"}})))
    assert sync.run() == 1
    conn = store.connect(store.db_path(agent))
    assert [r["body"] for r in conn.execute("SELECT body FROM messages ORDER BY ts")] == ["hello", "hi back"]
    assert conn.execute("SELECT name FROM contacts WHERE uuid = ?", (fakes.ALICE,)).fetchone()[0] == "Alice"
    meta = store.get_meta(conn)
    assert meta["status"] == "failed" and "exited (3)" in meta["error"] and meta["uuid"] == fakes.ME
    assert not store.socket_path(agent).exists()


def test_events_before_the_subscription_answer_and_before_an_abrupt_exit_are_kept(agent, monkeypatch):
    fakes.link_account(agent)
    monkeypatch.setenv("FAKE_EARLY", events(fakes.envelope(data={"timestamp": 1790000000000, "message": "early"})))
    monkeypatch.setenv("FAKE_EVENTS", events(*[fakes.envelope(data={"timestamp": 1790000000100 + i, "message": f"m{i}"})
                                               for i in range(50)]))
    monkeypatch.setenv("FAKE_ENDING", "abrupt")
    assert sync.run() == 1
    conn = store.connect(store.db_path(agent))
    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 51


def test_a_mirror_that_cannot_be_written_stops_receiving(agent, monkeypatch):
    fakes.link_account(agent)
    monkeypatch.setenv("FAKE_EVENTS", events(fakes.envelope(data={"timestamp": 1, "message": "a"}),
                                             fakes.envelope(data={"timestamp": 2, "message": "b"})))
    calls = []

    def broken(conn, payload, **kwargs):
        calls.append(payload)
        raise sync.sqlite3.OperationalError("disk I/O error")
    monkeypatch.setattr(sync.store, "ingest", broken)
    assert sync.run() == 1
    assert len(calls) == 1  # stopped at the first failure instead of discarding the rest
    meta = store.get_meta(store.connect(store.db_path(agent)))
    assert meta["status"] == "failed" and "cannot be written" in meta["error"]


def test_a_malformed_envelope_is_skipped(agent, monkeypatch):
    fakes.link_account(agent)
    monkeypatch.setenv("FAKE_EVENTS", events(fakes.envelope(data={"timestamp": 1, "message": "a"}),
                                             fakes.envelope(data={"timestamp": 2, "message": "b"})))
    real = sync.store.ingest

    def flaky(conn, payload, **kwargs):
        if payload["envelope"]["dataMessage"]["timestamp"] == 1:
            raise KeyError("odd")
        return real(conn, payload, **kwargs)
    monkeypatch.setattr(sync.store, "ingest", flaky)
    assert sync.run() == 1
    assert [r[0] for r in store.connect(store.db_path(agent)).execute("SELECT body FROM messages")] == ["b"]


def test_unlinked_while_running_stays_down(agent, monkeypatch):
    fakes.link_account(agent)
    monkeypatch.setenv("FAKE_EVENTS", events())
    monkeypatch.setenv("FAKE_ENDING", "unlinked")
    assert sync.run() == 0
    assert store.get_meta(store.connect(store.db_path(agent)))["status"] == "unlinked"


def test_daemon_arguments_never_send_read_receipts(tmp_path):
    argv = sync.daemon_argv("/x/signal-cli", tmp_path, fakes.NUMBER)
    assert "--send-read-receipts" not in argv
    assert argv[argv.index("--receive-mode") + 1] == "manual" and "--scrub-log" in argv
    assert argv[argv.index("--data-dir") + 1] == str(tmp_path / "signal-cli")
