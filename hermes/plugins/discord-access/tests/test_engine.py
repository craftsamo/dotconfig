import base64
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


engine = _load("discord_access_engine_test", ROOT / "engine.py")
store = engine.store

TOKEN = "user.token-value"
ME = "100000000000000001"
FRIEND = "100000000000000002"
G = "300000000000000001"
DM1, DM2 = "200000000000000001", "200000000000000002"
TEXT, SECRET_ROOM, VOICE = "400000000000000001", "400000000000000002", "400000000000000003"
LOGIN = '<script>window.GLOBAL_ENV = {"BUILD_NUMBER":"627798"}</script>'


def flake(minutes_ago: float, n: int = 0) -> str:
    when = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return str(store.snowflake_at(when) + n)


def msg(mid, channel, author=FRIEND, content="hello", **extra):
    return {"id": mid, "channel_id": channel, "author": {"id": author, "username": "u" + author[-1]},
            "content": content, "type": 0, **extra}


class FakeHttp:
    user_agent = "Mozilla/5.0 (Macintosh) Chrome/150.0.0.0"
    browser_version = "150.0.0.0"

    def __init__(self, routes=None):
        self.routes = dict(routes or {})
        self.calls = []

    def request(self, method, url, *, headers=None, params=None, body=None, timeout=None):
        self.calls.append({"method": method, "url": url, "params": params, "body": body, "headers": headers})
        if url.endswith("/login"):
            return 200, {}, LOGIN
        path = url.split("/api/v9", 1)[1]
        key = (method, path)
        if key not in self.routes:
            raise AssertionError(f"unexpected {method} {path} {params}")
        result = self.routes[key]
        if callable(result):
            result = result(params, body)
        if isinstance(result, Exception):
            raise result
        return result

    def api_calls(self, method=None):
        return [c for c in self.calls if "/api/" in c["url"] and (method is None or c["method"] == method)]


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv(store.STATE_ENV, str(tmp_path / "state"))
    monkeypatch.setattr(engine.time, "sleep", lambda s: None)
    monkeypatch.setattr(engine, "system_locale", lambda: "ja-JP")
    monkeypatch.setattr(engine, "read_token", lambda: pytest.fail("the real Keychain was read"))


def client(http, conn=None):
    conn = conn or store.connect(write=True)
    return engine.Client(conn, http=http, token=TOKEN)


def me_route():
    return {("GET", "/users/@me"): (200, {}, {"id": ME, "username": "me", "global_name": "Me", "locale": "ja"})}


def test_headers_look_like_the_web_client():
    c = client(FakeHttp())
    h = c.headers(referer=f"/channels/@me/{DM1}")
    assert h["Authorization"] == TOKEN and not h["Authorization"].startswith("Bot")
    props = json.loads(base64.b64decode(h["X-Super-Properties"]))
    assert props["client_build_number"] == 627798 and props["os"] == "Mac OS X" and props["browser"] == "Chrome"
    assert props["browser_user_agent"] == h["User-Agent"] and props["system_locale"] == "ja-JP"
    assert h["Referer"].endswith(f"/channels/@me/{DM1}") and h["X-Discord-Locale"] == "ja"


def test_build_number_and_launch_are_cached():
    conn = store.connect(write=True)
    http = FakeHttp()
    first = client(http, conn)
    second = client(http, conn)
    assert len([c for c in http.calls if c["url"].endswith("/login")]) == 1
    assert first.launch == second.launch


def test_build_number_failure_without_cache_fails_closed():
    http = FakeHttp()
    http.request = lambda *a, **k: (200, {}, "no build here")
    with pytest.raises(engine.EngineError, match="build number"):
        client(http)


def test_reads_wait_out_one_short_rate_limit_and_scrub_the_token():
    hits = []

    def limited(params, body):
        hits.append(1)
        return (429, {}, {"retry_after": 1.5}) if len(hits) == 1 else (200, {}, [])
    c = client(FakeHttp({("GET", "/users/@me/guilds"): limited}))
    assert engine.guilds(c) == [] and len(hits) == 2
    c = client(FakeHttp({("GET", "/users/@me/guilds"): engine.TransportError(f"boom {TOKEN}", True)}))
    with pytest.raises(engine.EngineError) as exc:
        engine.guilds(c)
    assert TOKEN not in str(exc.value) and "<token>" in str(exc.value)


def test_401_records_a_rejected_token():
    conn = store.connect(write=True)
    c = client(FakeHttp({("GET", "/users/@me"): (401, {}, {"message": "401: Unauthorized", "code": 0})}), conn)
    with pytest.raises(engine.EngineError) as exc:
        engine.whoami(c)
    assert exc.value.kind == "auth" and store.get_meta(conn, "auth")["state"] == "rejected"


def sync_routes(dm1_last, dm1_messages, dm2_last, guild_channels=None, extra=None):
    routes = {**me_route(),
              ("GET", "/users/@me/guilds"): (200, {}, [{"id": G, "name": "Guild"}]),
              ("GET", "/users/@me/channels"): (200, {}, [
                  {"id": DM1, "type": 1, "last_message_id": dm1_last,
                   "recipients": [{"id": FRIEND, "username": "taro", "global_name": "Taro"}]},
                  {"id": DM2, "type": 1, "last_message_id": dm2_last, "recipients": []}]),
              ("GET", f"/channels/{DM1}/messages"): dm1_messages}
    if guild_channels is not None:
        routes[("GET", f"/guilds/{G}/channels")] = (200, {}, guild_channels)
    routes.update(extra or {})
    return routes


def test_sync_seeds_recent_dms_and_follows_old_ones_from_now_on():
    conn = store.connect(write=True)
    m1, m2, m3 = flake(30), flake(20), flake(10)
    old = flake(100 * 24 * 60)
    http = FakeHttp(sync_routes(m3, (200, {}, [msg(m3, DM1), msg(m2, DM1, author=ME), msg(m1, DM1)]), old))
    summary = engine.sync(client(http, conn))
    assert summary["ok"] and summary["fetched"] == 3 and summary["channels_updated"] == 1
    seed = [c for c in http.api_calls() if c["url"].endswith(f"/channels/{DM1}/messages")]
    assert seed[0]["params"] == {"limit": "50"}
    cur = {r["channel_id"]: dict(r) for r in conn.execute("SELECT * FROM cursors")}
    assert cur[int(DM1)]["newest"] == int(m3) and cur[int(DM1)]["oldest"] == int(m1) and cur[int(DM1)]["complete"] == 1
    assert cur[int(DM2)]["newest"] == int(old) and cur[int(DM2)]["oldest"] == int(old) + 1
    assert cur[int(DM1)]["synced_at"] and cur[int(DM2)]["synced_at"]
    mine = conn.execute("SELECT from_me FROM messages WHERE id = ?", (int(m2),)).fetchone()[0]
    assert mine == 1


def test_sync_fetches_only_channels_whose_last_message_moved():
    conn = store.connect(write=True)
    m1, m2, m3 = flake(30), flake(20), flake(10)
    old = flake(100 * 24 * 60)
    engine.sync(client(FakeHttp(sync_routes(m2, (200, {}, [msg(m2, DM1), msg(m1, DM1)]), old)), conn))
    http = FakeHttp(sync_routes(m3, lambda params, body: (200, {}, [msg(m3, DM1)]), old))
    summary = engine.sync(client(http, conn))
    calls = [c for c in http.api_calls() if "/messages" in c["url"]]
    assert len(calls) == 1 and calls[0]["params"] == {"after": m2, "limit": "100"}
    assert summary["fetched"] == 1
    http = FakeHttp(sync_routes(m3, lambda p, b: pytest.fail("unchanged channel fetched"), old))
    engine.sync(client(http, conn))


def test_sync_cursor_skips_a_deleted_last_message():
    conn = store.connect(write=True)
    m1, gone = flake(30), flake(5)
    old = flake(100 * 24 * 60)
    engine.sync(client(FakeHttp(sync_routes(m1, (200, {}, [msg(m1, DM1)]), old)), conn))
    engine.sync(client(FakeHttp(sync_routes(gone, (200, {}, []), old)), conn))
    newest = conn.execute("SELECT newest FROM cursors WHERE channel_id = ?", (int(DM1),)).fetchone()[0]
    assert newest == int(gone)


def test_sync_list_whole_server_marks_unreadable_channels():
    conn = store.connect(write=True)
    store.sync_add(G, "Guild")
    t1, t2 = flake(3), flake(2)
    old = flake(100 * 24 * 60)
    routes = sync_routes(old, None, old, guild_channels=[
        {"id": TEXT, "type": 0, "name": "general", "last_message_id": t1},
        {"id": SECRET_ROOM, "type": 0, "name": "mods", "last_message_id": t2},
        {"id": VOICE, "type": 2, "name": "voice"}],
        extra={("GET", f"/channels/{TEXT}/messages"): (200, {}, [msg(t1, TEXT)]),
               ("GET", f"/channels/{SECRET_ROOM}/messages"): (403, {}, {"message": "Missing Access", "code": 50001})})
    summary = engine.sync(client(FakeHttp(routes), conn))
    state = {r["id"]: r["state"] for r in conn.execute("SELECT id, state FROM channels")}
    assert state[int(SECRET_ROOM)] == "forbidden" and summary["channels_updated"] == 1
    row = conn.execute("SELECT guild_id FROM messages WHERE id = ?", (int(t1),)).fetchone()
    assert row[0] == int(G)


def test_sync_stops_on_a_rejected_token():
    conn = store.connect(write=True)
    http = FakeHttp({("GET", "/users/@me"): (401, {}, {"message": "401: Unauthorized"})})
    with pytest.raises(engine.EngineError) as exc:
        engine.sync(client(http, conn))
    assert exc.value.kind == "auth"


# --- send ---------------------------------------------------------------------------------------

def seeded_dm(conn):
    store.upsert_channel(conn, store.channel_row({"id": DM1, "type": 1, "recipients": []}), 0)
    store.set_meta(conn, "me", {"id": ME, "username": "me", "name": "Me"})
    conn.commit()


def do_send(http, conn, nonce="n1", text="hello there", reply_to=None):
    seeded_dm(conn)
    plan = {"nonce": nonce, "channel": DM1, "text": text, "reply_to": reply_to}
    return engine.send(conn, plan, lambda: client(http, conn))


def test_send_posts_once_with_an_enforced_nonce():
    conn = store.connect(write=True)
    sent = flake(0)
    http = FakeHttp({("POST", f"/channels/{DM1}/messages"): (200, {}, msg(sent, DM1, author=ME, content="hello there"))})
    result = do_send(http, conn)
    assert result == {"outcome": "sent", "message_id": sent, "channel": DM1}
    posts = http.api_calls("POST")
    assert len(posts) == 1
    body = posts[0]["body"]
    assert body["nonce"] == "n1" and body["enforce_nonce"] is True and body["content"] == "hello there"
    assert "message_reference" not in body and "allowed_mentions" not in body
    assert engine.ledger_status(conn, "n1")["status"] == "sent"
    assert conn.execute("SELECT from_me FROM messages WHERE id = ?", (int(sent),)).fetchone()[0] == 1


def test_reply_references_the_message_without_pinging():
    conn = store.connect(write=True)
    http = FakeHttp({("POST", f"/channels/{DM1}/messages"): (200, {}, msg(flake(0), DM1, author=ME))})
    do_send(http, conn, reply_to="500000000000000001")
    body = http.api_calls("POST")[0]["body"]
    assert body["message_reference"] == {"channel_id": DM1, "message_id": "500000000000000001"}
    assert body["allowed_mentions"]["replied_user"] is False


@pytest.mark.parametrize("response,kind", [
    ((400, {}, {"message": "Cannot send messages to this user", "code": 50007}), "http"),
    ((403, {}, {"message": "Missing Permissions", "code": 50013}), "forbidden"),
    ((429, {"retry-after": "12"}, {"retry_after": 12.0}), "rate_limited"),
    ((400, {}, {"captcha_key": ["captcha-required"], "captcha_sitekey": "x"}), "captcha"),
])
def test_refusals_are_not_sent_and_never_retried(response, kind):
    conn = store.connect(write=True)
    http = FakeHttp({("POST", f"/channels/{DM1}/messages"): response})
    result = do_send(http, conn)
    assert result["outcome"] == "not_sent" and result["kind"] == kind
    assert len(http.api_calls("POST")) == 1 and engine.ledger_status(conn, "n1")["status"] == "not_sent"


def test_network_failure_before_dispatch_is_not_sent():
    conn = store.connect(write=True)
    http = FakeHttp({("POST", f"/channels/{DM1}/messages"): engine.TransportError("curl 7", dispatched=False)})
    assert do_send(http, conn)["outcome"] == "not_sent"


def test_ambiguous_failure_stays_uncertain_with_a_hint():
    conn = store.connect(write=True)
    sent = flake(-0.01)
    http = FakeHttp({
        ("POST", f"/channels/{DM1}/messages"): engine.TransportError("curl 28 operation timed out", dispatched=True),
        ("GET", f"/channels/{DM1}/messages"): (200, {}, [msg(sent, DM1, author=ME, content="hello there")])})
    result = do_send(http, conn)
    assert result["outcome"] == "uncertain" and sent in result["detail"] and "not proven" in result["detail"]
    assert len(http.api_calls("POST")) == 1 and engine.ledger_status(conn, "n1")["status"] == "uncertain"


def test_ambiguous_failure_without_the_message_is_uncertain():
    conn = store.connect(write=True)
    http = FakeHttp({
        ("POST", f"/channels/{DM1}/messages"): (502, {}, "bad gateway"),
        ("GET", f"/channels/{DM1}/messages"): (200, {}, [msg(flake(60), DM1, author=ME, content="hello there")])})
    result = do_send(http, conn)
    assert result["outcome"] == "uncertain" and len(http.api_calls("POST")) == 1
    assert engine.ledger_status(conn, "n1")["status"] == "uncertain"


def test_a_nonce_is_never_dispatched_twice():
    conn = store.connect(write=True)
    http = FakeHttp({("POST", f"/channels/{DM1}/messages"): (500, {}, "x"),
                     ("GET", f"/channels/{DM1}/messages"): (200, {}, [])})
    do_send(http, conn)
    again = do_send(http, conn)
    assert again["outcome"] == "not_sent" and len(http.api_calls("POST")) == 1


def test_missing_token_is_not_sent(monkeypatch):
    conn = store.connect(write=True)
    seeded_dm(conn)

    def no_token():
        raise engine.EngineError("setup", "no Discord token in the Keychain")
    result = engine.send(conn, {"nonce": "n1", "channel": DM1, "text": "x", "reply_to": None}, no_token)
    assert result["outcome"] == "not_sent" and engine.ledger_status(conn, "n1")["status"] == "not_sent"


def test_main_never_prints_a_traceback(monkeypatch, capsys):
    monkeypatch.setattr(engine, "run", lambda command, args: (_ for _ in ()).throw(RuntimeError("bad")))
    monkeypatch.setattr(engine.sys, "stdin", type("S", (), {"read": staticmethod(lambda: "{}")})())
    assert engine.main(["engine.py", "whoami"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out == {"ok": False, "kind": "internal", "error": "RuntimeError: bad"}


# --- review regressions -------------------------------------------------------------------------

def test_read_back_ignores_an_identical_earlier_message():
    conn = store.connect(write=True)
    earlier = flake(0.5)  # the same text, sent 30 s before this POST began
    http = FakeHttp({("POST", f"/channels/{DM1}/messages"): (503, {}, "unavailable"),
                     ("GET", f"/channels/{DM1}/messages"): (200, {}, [msg(earlier, DM1, author=ME, content="hello there")])})
    result = do_send(http, conn)
    assert result["outcome"] == "uncertain" and earlier not in result["detail"] and "no message" in result["detail"]


def test_read_back_hint_needs_the_same_reply_target():
    conn = store.connect(write=True)
    target, elsewhere = "500000000000000001", "500000000000000009"
    reply = {**msg(flake(-0.01), DM1, author=ME, content="hello there"), "type": 19,
             "message_reference": {"message_id": elsewhere}}
    http = FakeHttp({("POST", f"/channels/{DM1}/messages"): (503, {}, "x"),
                     ("GET", f"/channels/{DM1}/messages"): (200, {}, [reply])})
    assert "no message" in do_send(http, conn, reply_to=target)["detail"]
    conn2 = store.connect(write=True)
    good = {**reply, "id": flake(-0.02), "message_reference": {"message_id": target}}
    http = FakeHttp({("POST", f"/channels/{DM1}/messages"): (503, {}, "x"),
                     ("GET", f"/channels/{DM1}/messages"): (200, {}, [good])})
    result = do_send(http, conn2, nonce="n2", reply_to=target)
    assert result["outcome"] == "uncertain" and good["id"] in result["detail"]


def test_forbidden_dms_are_skipped_until_a_live_read_succeeds():
    conn = store.connect(write=True)
    m1 = flake(10)
    old = flake(100 * 24 * 60)
    engine.sync(client(FakeHttp(sync_routes(m1, (403, {}, {"message": "Missing Access"}), old)), conn))
    state = conn.execute("SELECT state FROM channels WHERE id = ?", (int(DM1),)).fetchone()[0]
    assert state == "forbidden"
    engine.sync(client(FakeHttp(sync_routes(flake(5), lambda p, b: pytest.fail("forbidden DM fetched"), old)), conn))
    engine.messages(client(FakeHttp({**me_route(), ("GET", f"/channels/{DM1}/messages"): (200, {}, [msg(m1, DM1)])}),
                           conn), DM1)
    assert conn.execute("SELECT state FROM channels WHERE id = ?", (int(DM1),)).fetchone()[0] is None


def test_the_run_budget_is_a_hard_bound(monkeypatch):
    monkeypatch.setattr(engine, "MAX_REQUESTS", 4)
    conn = store.connect(write=True)
    dms = [{"id": str(200000000000000100 + i), "type": 1, "last_message_id": flake(10 - i), "recipients": []}
           for i in range(6)]
    routes = {**me_route(), ("GET", "/users/@me/guilds"): (200, {}, []), ("GET", "/users/@me/channels"): (200, {}, dms)}
    for d in dms:
        routes[("GET", f"/channels/{d['id']}/messages")] = (200, {}, [msg(d["last_message_id"], d["id"])])
    http = FakeHttp(routes)
    summary = engine.sync(client(http, conn))
    assert summary["requests"] <= 4 and summary["deferred"] >= 1
    assert len([c for c in http.calls]) <= 5  # four API requests and the login page (counted before the run)


def test_a_lagging_channel_is_not_current():
    conn = store.connect(write=True)
    old = flake(100 * 24 * 60)
    m1 = flake(60)
    engine.sync(client(FakeHttp(sync_routes(m1, (200, {}, [msg(m1, DM1)]), old)), conn))
    full = [msg(str(int(m1) + 1 + i), DM1) for i in range(engine.PAGE)]
    engine.sync(client(FakeHttp(sync_routes(flake(1), lambda p, b: (200, {}, full), old)), conn))
    row = conn.execute("SELECT newest, synced_at FROM cursors WHERE channel_id = ?", (int(DM1),)).fetchone()
    assert row["synced_at"] is None and row["newest"] == int(full[-1]["id"])


def test_backfill_pages_from_the_frontier_not_a_stray_window():
    conn = store.connect(write=True)
    seeded_dm(conn)
    frontier, stray = flake(60), flake(60 * 24 * 90)
    store.upsert_messages(conn, [store.message_row(msg(stray, DM1), ME), store.message_row(msg(frontier, DM1), ME)])
    conn.execute("INSERT INTO cursors (channel_id, newest, oldest, complete) VALUES (?, ?, ?, 0)",
                 (int(DM1), int(frontier), int(frontier)))
    conn.commit()
    seen = []

    def page(params, body):
        seen.append(params["before"])
        return 200, {}, [msg(str(int(frontier) - 5), DM1)]
    result = engine.backfill(client(FakeHttp({("GET", f"/channels/{DM1}/messages"): page}), conn), DM1, 2)
    assert seen == [frontier] and result["complete"] is True
    assert conn.execute("SELECT oldest FROM cursors WHERE channel_id = ?", (int(DM1),)).fetchone()[0] == int(frontier) - 5


def test_errors_never_print_a_token_shape(monkeypatch, capsys):
    shaped = ".".join(["x" * 24, "y" * 6, "z" * 27])  # token-shaped, built so no scanner mistakes it
    monkeypatch.setattr(engine, "run", lambda command, args: (_ for _ in ()).throw(RuntimeError(f"x {shaped}")))
    monkeypatch.setattr(engine.sys, "stdin", type("S", (), {"read": staticmethod(lambda: "{}")})())
    engine.main(["engine.py", "whoami"])
    out = capsys.readouterr().out
    assert shaped not in out and "<token>" in out


def test_a_channel_deferred_before_its_first_page_is_not_current(monkeypatch):
    conn = store.connect(write=True)
    old = flake(100 * 24 * 60)
    m1 = flake(60)
    engine.sync(client(FakeHttp(sync_routes(m1, (200, {}, [msg(m1, DM1)]), old)), conn))
    assert conn.execute("SELECT synced_at FROM cursors WHERE channel_id = ?", (int(DM1),)).fetchone()[0]
    monkeypatch.setattr(engine, "MAX_REQUESTS", 2)  # login cached: whoami + DM list, then nothing
    routes = sync_routes(flake(1), lambda p, b: pytest.fail("fetched past the budget"), old)
    summary = engine.sync(client(FakeHttp(routes), conn))
    assert summary["deferred"] == 1
    assert conn.execute("SELECT synced_at FROM cursors WHERE channel_id = ?", (int(DM1),)).fetchone()[0] is None


# --- attachments --------------------------------------------------------------------------------

UPLOAD_URL = "https://discord-attachments-uploads-prd.storage.googleapis.com/abc?upload_id=1"


def outbox_file(name="a.txt", data=b"file-bytes"):
    folder = store.state_dir() / "outbox" / ("0" * 32)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "00"
    path.write_bytes(data)
    return [{"path": str(path), "name": name}]


def upload_routes(post_result, put_status=200, url=UPLOAD_URL):
    def put(params, body):
        return put_status, {}, ""
    return {
        ("POST", f"/channels/{DM1}/attachments"): (200, {}, {"attachments": [
            {"id": 0, "upload_url": url, "upload_filename": "up-0/a.txt"}]}),
        ("PUT", "__upload__"): put,
        ("POST", f"/channels/{DM1}/messages"): post_result,
    }


class UploadHttp(FakeHttp):
    def request(self, method, url, *, headers=None, params=None, body=None, data=None, timeout=None):
        if method == "PUT":
            self.calls.append({"method": method, "url": url, "headers": headers, "data": data, "body": None,
                               "params": None})
            return self.routes[("PUT", "__upload__")](None, None)
        return super().request(method, url, headers=headers, params=params, body=body, timeout=timeout)


def test_files_are_uploaded_then_sent_in_one_post():
    conn = store.connect(write=True)
    seeded_dm(conn)
    sent = flake(0)
    http = UploadHttp(upload_routes((200, {}, msg(sent, DM1, author=ME, content="see file"))))
    plan = {"nonce": "n1", "channel": DM1, "text": "see file", "reply_to": None, "files": outbox_file()}
    result = engine.send(conn, plan, lambda: client(http, conn))
    assert result["outcome"] == "sent"
    reserve = [c for c in http.calls if c["url"].endswith("/attachments")][0]
    assert reserve["body"] == {"files": [{"id": "0", "filename": "a.txt", "file_size": 10}]}
    put = [c for c in http.calls if c["method"] == "PUT"][0]
    assert put["url"] == UPLOAD_URL and put["data"] == b"file-bytes" and "Authorization" not in put["headers"]
    posts = [c for c in http.calls if c["method"] == "POST" and c["url"].endswith("/messages")]
    assert len(posts) == 1
    assert posts[0]["body"]["attachments"] == [{"id": "0", "filename": "a.txt", "uploaded_filename": "up-0/a.txt"}]


@pytest.mark.parametrize("routes", [
    upload_routes(None, put_status=403),
    upload_routes(None, url="https://evil.example.com/upload"),
])
def test_upload_failures_are_not_sent_and_post_nothing(routes):
    conn = store.connect(write=True)
    seeded_dm(conn)
    routes[("POST", f"/channels/{DM1}/messages")] = lambda p, b: pytest.fail("message posted")
    http = UploadHttp(routes)
    plan = {"nonce": "n1", "channel": DM1, "text": "x", "reply_to": None, "files": outbox_file()}
    result = engine.send(conn, plan, lambda: client(http, conn))
    assert result["outcome"] == "not_sent" and engine.ledger_status(conn, "n1")["status"] == "not_sent"
    assert not [c for c in http.calls if c["method"] == "PUT" and "evil" in c["url"]]


def test_attachments_are_read_only_from_the_outbox(tmp_path):
    elsewhere = tmp_path / "secret.txt"
    elsewhere.write_text("x")
    with pytest.raises(engine.EngineError, match="outbox"):
        engine.outbox_files([{"path": str(elsewhere), "name": "secret.txt"}])
    with pytest.raises(engine.EngineError, match="outbox"):
        engine.outbox_files([{"path": str(store.state_dir() / "outbox" / ".." / "mirror.db"), "name": "m"}])
