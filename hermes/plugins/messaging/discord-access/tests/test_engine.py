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


# --- media --------------------------------------------------------------------------------------

def media_message(mid):
    return {**msg(mid, DM1), "attachments": [
                {"filename": "photo.png", "content_type": "image/png", "size": 4,
                 "url": "https://cdn.discordapp.com/attachments/1/2/photo.png?ex=1"},
                {"filename": "tool.zip", "content_type": "application/zip", "size": 4,
                 "url": "https://cdn.discordapp.com/attachments/1/3/tool.zip"},
                {"filename": "huge.mov", "content_type": "video/quicktime", "size": 10 ** 9,
                 "url": "https://cdn.discordapp.com/attachments/1/4/huge.mov"}],
            "embeds": [{"url": "https://example.com/post",
                        "thumbnail": {"url": "https://example.com/t.jpg",
                                      "proxy_url": "https://images-ext-1.discordapp.net/external/abc/t.jpg"}},
                       {"image": {"url": "https://evil.example/x.png", "proxy_url": "https://evil.example/x.png"}}],
            "sticker_items": [{"id": "700000000000000001", "name": "wave", "format_type": 1},
                              {"id": "700000000000000002", "name": "dance", "format_type": 4}]}


class MediaHttp(FakeHttp):
    def __init__(self, routes, files):
        super().__init__(routes)
        self.files = files

    def download(self, url, dest, *, headers, limit, timeout):
        self.calls.append({"method": "DOWNLOAD", "url": url, "headers": headers})
        body = self.files.get(url)
        if body is None:
            return {"status": 404, "type": "", "size": 0, "too_large": False}
        if len(body) > limit:
            return {"status": 200, "type": "", "size": len(body), "too_large": True}
        dest.write_bytes(body)
        return {"status": 200, "type": "image/png", "size": len(body), "too_large": False}


def test_media_items_cover_attachments_previews_and_stickers():
    items = engine.media_items(media_message(flake(1)))
    assert [(i["kind"], i["name"]) for i in items] == [
        ("attachment", "photo.png"), ("attachment", "tool.zip"), ("attachment", "huge.mov"),
        ("preview", "preview-t.jpg"), ("preview", "preview-x.png"), ("sticker", "wave.png"), ("sticker", "dance.gif")]
    assert items[-1]["url"] == "https://media.discordapp.net/stickers/700000000000000002.gif"
    assert items[3]["source"] == "https://example.com/post"


def test_media_downloads_only_from_discord_and_within_limits(tmp_path):
    conn = store.connect(write=True)
    seeded_dm(conn)
    mid = flake(1)
    files = {"https://cdn.discordapp.com/attachments/1/2/photo.png?ex=1": b"\x89PNG",
             "https://images-ext-1.discordapp.net/external/abc/t.jpg": b"jpeg",
             "https://cdn.discordapp.com/stickers/700000000000000001.png": b"x" * 50}
    http = MediaHttp({("GET", f"/channels/{DM1}/messages"): (200, {}, [media_message(mid)])}, files)
    folder = tmp_path / "in"
    folder.mkdir()
    out = engine.media(client(http, conn), DM1, mid, folder, limit=20)["items"]
    status = {i["name"]: i["status"] for i in out}
    assert status == {"photo.png": "saved", "tool.zip": "refused", "huge.mov": "too_large",
                      "preview-t.jpg": "saved", "preview-x.png": "refused", "wave.png": "too_large",
                      "dance.gif": "missing"}
    downloads = [c for c in http.calls if c["method"] == "DOWNLOAD"]
    assert all("Authorization" not in c["headers"] for c in downloads)
    assert not any("evil" in c["url"] or "zip" in c["url"] for c in downloads)
    assert (folder / out[0]["file"]).read_bytes() == b"\x89PNG"


def test_media_of_a_missing_message_is_not_found(tmp_path):
    conn = store.connect(write=True)
    seeded_dm(conn)
    http = MediaHttp({("GET", f"/channels/{DM1}/messages"): (200, {}, [msg(flake(2), DM1)])}, {})
    with pytest.raises(engine.EngineError) as exc:
        engine.media(client(http, conn), DM1, flake(1), tmp_path, limit=10)
    assert exc.value.kind == "not_found"


def test_stickers_are_recorded_and_old_mirrors_migrate():
    import sqlite3
    path = store.state_dir() / "mirror.db"
    old = sqlite3.connect(path)
    old.executescript(store.SCHEMA.replace(", stickers TEXT", ""))
    old.close()
    conn = store.connect(write=True)
    row = store.message_row(media_message(flake(1)), ME)
    store.upsert_messages(conn, [row])
    assert json.loads(conn.execute("SELECT stickers FROM messages").fetchone()[0]) == ["wave", "dance"]


# --- edits and deletions --------------------------------------------------------------------------

def mirrored(conn, *mids, channel=DM1):
    seeded_dm(conn)
    store.upsert_messages(conn, [store.message_row(msg(m, channel), ME) for m in mids])
    conn.commit()


def ids_in(conn, channel=DM1):
    return [str(r[0]) for r in conn.execute("SELECT id FROM messages WHERE channel_id = ? ORDER BY id", (int(channel),))]


def test_a_live_window_applies_edits_and_deletions_inside_it():
    conn = store.connect(write=True)
    a, b, c, d = flake(40), flake(30), flake(20), flake(10)
    mirrored(conn, a, b, c, d)
    page = [msg(c, DM1, content="edited"), msg(a, DM1)]          # b was deleted; d lies outside the page
    engine.messages(client(FakeHttp({**me_route(), ("GET", f"/channels/{DM1}/messages"): (200, {}, page)}), conn),
                    DM1, before=d, limit=2)
    assert ids_in(conn) == [a, c, d]
    assert conn.execute("SELECT content FROM messages WHERE id = ?", (int(c),)).fetchone()[0] == "edited"


def test_a_short_newest_page_vouches_up_to_the_request():
    conn = store.connect(write=True)
    a, gone = flake(30), flake(1)
    mirrored(conn, a, gone)
    engine.messages(client(FakeHttp({("GET", f"/channels/{DM1}/messages"): (200, {}, [msg(a, DM1)])}), conn), DM1)
    assert ids_in(conn) == [a]


def test_a_short_page_before_an_id_vouches_back_to_the_start():
    conn = store.connect(write=True)
    oldest, a, b = flake(90), flake(30), flake(20)
    mirrored(conn, oldest, a, b)
    engine.messages(client(FakeHttp({("GET", f"/channels/{DM1}/messages"): (200, {}, [msg(a, DM1)])}), conn),
                    DM1, before=b, limit=50)
    assert ids_in(conn) == [a, b]


def test_an_empty_page_deletes_nothing():
    conn = store.connect(write=True)
    a = flake(30)
    mirrored(conn, a)
    engine.messages(client(FakeHttp({("GET", f"/channels/{DM1}/messages"): (200, {}, [])}), conn), DM1)
    assert ids_in(conn) == [a]


def test_sync_rechecks_recent_channels_within_its_budget():
    conn = store.connect(write=True)
    old = flake(100 * 24 * 60)
    m1, m2 = flake(60), flake(50)
    engine.sync(client(FakeHttp(sync_routes(m2, (200, {}, [msg(m2, DM1), msg(m1, DM1)]), old)), conn))
    conn.execute("UPDATE cursors SET rechecked_at = 0")
    conn.commit()
    seen = []

    def newest(params, body):
        seen.append(params)
        return 200, {}, [msg(m2, DM1, content="edited")]           # m1 was deleted
    http = FakeHttp(sync_routes(m2, newest, old))
    summary = engine.sync(client(http, conn))
    assert seen == [{"limit": "50"}] and summary["rechecked"] == 1
    assert len(http.api_calls()) == 3          # whoami, the DM list and one recheck (servers are cached)
    assert ids_in(conn) == [m2]
    # Rechecked just now: the next quiet run makes no message request at all.
    engine.sync(client(FakeHttp(sync_routes(m2, lambda p, b: pytest.fail("rechecked again"), old)), conn))


def test_recheck_skips_quiet_and_unreadable_channels():
    conn = store.connect(write=True)
    old = flake(100 * 24 * 60)
    engine.sync(client(FakeHttp(sync_routes(old, None, old)), conn))
    conn.execute("UPDATE cursors SET rechecked_at = 0")
    conn.commit()
    engine.sync(client(FakeHttp(sync_routes(old, lambda p, b: pytest.fail("a quiet DM was rechecked"), old)), conn))


# --- searches, threads, pins, mentions, friends ---------------------------------------------------

def test_search_waits_out_one_index_build():
    conn = store.connect(write=True)
    mirrored(conn)
    hits = []

    def index(params, body):
        hits.append(params)
        if len(hits) == 1:
            return 202, {}, {"message": "Index not yet available", "code": 110000, "retry_after": 0}
        return 200, {}, {"total_results": 1, "messages": [[{**msg(flake(5), DM1, content="found"), "hit": True}]]}
    http = FakeHttp({**me_route(), ("GET", f"/channels/{DM1}/messages/search"): index})
    result = engine.search(client(http, conn), query="found", channel=DM1)
    assert result["total"] == 1 and result["messages"][0]["content"] == "found" and len(hits) == 2
    assert hits[0]["content"] == "found" and hits[0]["sort_by"] == "timestamp"
    http = FakeHttp({("GET", f"/channels/{DM1}/messages/search"): (202, {}, {"code": 110000, "retry_after": 1})})
    with pytest.raises(engine.EngineError) as exc:
        engine.search(client(http, conn), query="x", channel=DM1)
    assert exc.value.kind == "indexing"


def test_search_of_every_dm_posts_the_tabs_query_and_keeps_reactions():
    conn = store.connect(write=True)
    mid = flake(5)
    store.upsert_messages(conn, [store.message_row(msg(mid, DM1, reactions=[{"emoji": {"name": "a"}, "count": 1}]), ME)])
    found = {**msg(mid, DM1, content="hello"), "hit": True}
    http = FakeHttp({("POST", "/users/@me/messages/search/tabs"): (200, {}, {"tabs": {"messages": {
        "total_results": 1, "messages": [[found]]}}})})
    result = engine.search(client(http, conn), query="hello", min_id="1" * 18)
    body = http.api_calls("POST")[0]["body"]
    assert body["tabs"]["messages"]["content"] == "hello" and body["tabs"]["messages"]["min_id"] == "1" * 18
    assert result["messages"][0]["id"] == int(mid)
    assert conn.execute("SELECT reactions FROM messages WHERE id = ?", (int(mid),)).fetchone()[0]


def test_guild_search_filters_a_channel_and_takes_hits_only():
    conn = store.connect(write=True)
    hit, context = {**msg(flake(5), TEXT), "hit": True}, msg(flake(6), TEXT)
    http = FakeHttp({("GET", f"/guilds/{G}/messages/search"): (200, {}, {"total_results": 1,
                                                                          "messages": [[context, hit]]})})
    result = engine.search(client(http, conn), query="q", guild=G, channel=TEXT)
    assert http.api_calls()[0]["params"]["channel_id"] == TEXT
    assert [r["id"] for r in result["messages"]] == [int(hit["id"])]


def test_threads_are_stored_as_channels():
    conn = store.connect(write=True)
    thread = {"id": "450000000000000001", "type": 11, "name": "help", "parent_id": TEXT, "guild_id": G,
              "message_count": 3, "thread_metadata": {"archived": False, "locked": True}}
    first = msg(flake(5), "450000000000000001", content="first post")
    http = FakeHttp({("GET", f"/channels/{TEXT}/threads/search"): (200, {}, {
        "threads": [thread], "has_more": True, "total_results": 9, "first_messages": [first]})})
    result = engine.threads(client(http, conn), TEXT, archived=False, offset=25)
    params = http.api_calls()[0]["params"]
    assert params["archived"] == "false" and params["offset"] == "25" and params["sort_by"] == "last_message_time"
    assert result["has_more"] and result["first"]["450000000000000001"] == "first post"
    row = conn.execute("SELECT * FROM channels WHERE id = 450000000000000001").fetchone()
    assert row["parent_id"] == int(TEXT) and json.loads(row["thread"])["locked"] is True


def test_pins_mentions_and_friends():
    conn = store.connect(write=True)
    mirrored(conn)
    p = msg(flake(9), DM1, content="pinned")
    http = FakeHttp({**me_route(),
                     ("GET", f"/channels/{DM1}/messages/pins"): (200, {}, {"items": [
                         {"pinned_at": "2026-10-01T00:00:00+00:00", "message": p}], "has_more": False}),
                     ("GET", "/users/@me/mentions"): (200, {}, [{**msg(flake(3), TEXT), "guild_id": G}]),
                     ("GET", "/users/@me/relationships"): (200, {}, [
                         {"id": FRIEND, "type": 1, "user": {"id": FRIEND, "username": "taro", "global_name": "Taro"}},
                         {"id": "100000000000000009", "type": 3, "user": {"id": "100000000000000009"}},
                         {"id": "100000000000000008", "type": 2, "user": {"id": "100000000000000008"}}])})
    c = client(http, conn)
    assert engine.pins(c, DM1)["messages"][0]["pinned_at"].startswith("2026-10-01")
    found = engine.mentions(c, guild=G)
    assert found["messages"][0]["guild_id"] == int(G)
    assert [k for k in http.api_calls() if "mentions" in k["url"]][0]["params"]["guild_id"] == G
    out = engine.friends(c)
    assert out == {"friends": [{"id": FRIEND, "name": "Taro", "username": "taro", "nickname": None}],
                   "incoming": 1, "outgoing": 0}
    assert store.get_meta(conn, "friends")["fetched"]


# --- roles ------------------------------------------------------------------------------------------

ROLE, MOD = "600000000000000001", "600000000000000002"


def role_routes(extra=None):
    return {**me_route(),
            ("GET", f"/guilds/{G}/roles"): (200, {}, [
                {"id": G, "name": "@everyone", "position": 0, "permissions": "1024"},
                {"id": ROLE, "name": "Member", "position": 1, "permissions": "2048"},
                {"id": MOD, "name": "Mod", "position": 3, "permissions": str(1 << 28)}]),
            ("GET", f"/guilds/{G}/roles/member-counts"): (200, {}, {ROLE: 12, MOD: 2}),
            ("GET", f"/users/@me/guilds/{G}/member"): (200, {}, {"roles": [MOD], "nick": None}),
            ("GET", "/users/@me/guilds"): (200, {}, [{"id": G, "name": "Guild", "owner": False}]),
            **(extra or {})}


def test_roles_store_the_list_counts_and_my_member():
    conn = store.connect(write=True)
    http = FakeHttp(role_routes())
    assert engine.roles(client(http, conn), G) == {"roles": 3}
    rows = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM roles")}
    assert rows[int(ROLE)]["members"] == 12 and rows[int(MOD)]["position"] == 3
    me = conn.execute("SELECT roles FROM members WHERE user_id = ?", (int(ME),)).fetchone()
    assert json.loads(me[0]) == [MOD]
    assert conn.execute("SELECT owner, roles_at FROM guilds").fetchone()[0] == 0
    engine.roles(client(FakeHttp(role_routes({("GET", "/users/@me/guilds"): lambda p, b: pytest.fail("again")})),
                        conn), G)


# --- writes -----------------------------------------------------------------------------------------

THUMB = "\U0001F44D"


def test_react_puts_the_encoded_emoji_and_counts_it():
    conn = store.connect(write=True)
    mid = flake(5)
    mirrored(conn, mid)
    path = f"/channels/{DM1}/messages/{mid}/reactions/%F0%9F%91%8D"
    http = FakeHttp({("PUT", f"{path}/@me"): (204, {}, "")})
    assert engine.react(client(http, conn), DM1, mid, THUMB, True)["outcome"] == "done"
    assert http.api_calls()[0]["params"] == {"type": "0"}
    assert json.loads(conn.execute("SELECT reactions FROM messages").fetchone()[0]) == [
        {"emoji": THUMB, "count": 1, "me": True}]


def test_unreact_falls_back_to_the_legacy_route_only_when_the_route_is_unknown():
    conn = store.connect(write=True)
    mid = flake(5)
    mirrored(conn, mid)
    path = f"/channels/{DM1}/messages/{mid}/reactions/x"
    http = FakeHttp({("DELETE", f"{path}/0/@me"): (404, {}, {"message": "404: Not Found", "code": 0}),
                     ("DELETE", f"{path}/@me"): (204, {}, "")})
    assert engine.react(client(http, conn), DM1, mid, "x", False)["outcome"] == "done"
    http = FakeHttp({("DELETE", f"{path}/0/@me"): (404, {}, {"message": "Unknown Message", "code": 10008})})
    assert engine.react(client(http, conn), DM1, mid, "x", False)["outcome"] == "not_done"
    assert len(http.api_calls()) == 1


def test_edit_patches_once_and_stores_the_new_text():
    conn = store.connect(write=True)
    mid = flake(5)
    mirrored(conn, mid)
    http = FakeHttp({("PATCH", f"/channels/{DM1}/messages/{mid}"): (200, {}, msg(mid, DM1, author=ME, content="new"))})
    assert engine.edit(client(http, conn), DM1, mid, "new")["outcome"] == "done"
    body = http.api_calls()[0]["body"]
    assert body["content"] == "new" and body["allowed_mentions"]["replied_user"] is False
    assert conn.execute("SELECT content FROM messages").fetchone()[0] == "new"


def test_an_ambiguous_edit_is_confirmed_by_one_read_back():
    conn = store.connect(write=True)
    mid = flake(5)
    mirrored(conn, mid)
    routes = {("PATCH", f"/channels/{DM1}/messages/{mid}"): (502, {}, "bad gateway"),
              ("GET", f"/channels/{DM1}/messages"): (200, {}, [msg(mid, DM1, author=ME, content="new")])}
    result = engine.edit(client(FakeHttp(routes), conn), DM1, mid, "new")
    assert result["outcome"] == "done" and result["confirmed"]
    routes[("GET", f"/channels/{DM1}/messages")] = (200, {}, [msg(mid, DM1, author=ME, content="old")])
    http = FakeHttp(routes)
    assert engine.edit(client(http, conn), DM1, mid, "new")["outcome"] == "uncertain"
    assert len(http.api_calls("PATCH")) == 1


def test_delete_of_a_message_already_gone_is_done():
    conn = store.connect(write=True)
    mid = flake(5)
    mirrored(conn, mid)
    http = FakeHttp({("DELETE", f"/channels/{DM1}/messages/{mid}"): (404, {}, {"message": "Unknown Message",
                                                                              "code": 10008})})
    result = engine.delete(client(http, conn), DM1, mid)
    assert result["outcome"] == "done" and result["already"] and ids_in(conn) == []


def test_a_two_factor_request_is_not_a_rejected_token():
    conn = store.connect(write=True)
    http = FakeHttp({("PUT", f"/guilds/{G}/members/{FRIEND}/roles/{ROLE}"): (401, {}, {
        "message": "Two factor is required for this operation", "code": 60003, "mfa": {"ticket": "t"}})})
    result = engine.role_member(client(http, conn), G, FRIEND, ROLE, True)
    assert result["outcome"] == "not_done" and result["kind"] == "mfa"
    assert store.get_meta(conn, "auth") is None


def test_role_writes_carry_the_audit_reason():
    conn = store.connect(write=True)
    http = FakeHttp({("PUT", f"/guilds/{G}/members/{FRIEND}/roles/{ROLE}"): (204, {}, "")})
    engine.role_member(client(http, conn), G, FRIEND, ROLE, True, reason="新人 / welcome")
    assert http.api_calls()[0]["headers"]["X-Audit-Log-Reason"] == "%E6%96%B0%E4%BA%BA / welcome"


def test_bulk_add_reports_who_got_the_role():
    conn = store.connect(write=True)
    other = "100000000000000003"
    http = FakeHttp({("PATCH", f"/guilds/{G}/roles/{ROLE}/members"): (200, {}, {
        FRIEND: {"user": {"id": FRIEND, "username": "taro"}, "roles": [ROLE]}})})
    result = engine.role_bulk_add(client(http, conn), G, ROLE, [FRIEND, other])
    assert result["added"] == [FRIEND] and result["not_added"] == [other]
    assert http.api_calls()[0]["body"] == {"member_ids": [FRIEND, other]}


def test_an_ambiguous_role_create_stays_uncertain_with_a_hint():
    conn = store.connect(write=True)
    new = flake(-0.01)
    routes = {("POST", f"/guilds/{G}/roles"): engine.TransportError("curl 28 operation timed out", dispatched=True),
              ("GET", f"/guilds/{G}/roles"): (200, {}, [{"id": new, "name": "Helpers", "position": 1}])}
    result = engine.role_create(client(FakeHttp(routes), conn), G, {"name": "Helpers", "permissions": "0"})
    assert result["outcome"] == "uncertain" and new in result["detail"] and "not proven" in result["detail"]


def test_role_delete_of_a_gone_role_is_done():
    conn = store.connect(write=True)
    store.upsert_role(conn, {"id": ROLE, "name": "Member"}, G)
    http = FakeHttp({("DELETE", f"/guilds/{G}/roles/{ROLE}"): (404, {}, {"message": "Unknown Role", "code": 10011})})
    assert engine.role_delete(client(http, conn), G, ROLE)["outcome"] == "done"
    assert conn.execute("SELECT COUNT(*) FROM roles").fetchone()[0] == 0


def test_role_edit_read_back_compares_the_requested_fields():
    conn = store.connect(write=True)
    routes = {("PATCH", f"/guilds/{G}/roles/{ROLE}"): (500, {}, "x"),
              ("GET", f"/guilds/{G}/roles"): (200, {}, [{"id": ROLE, "name": "New", "permissions": "3072",
                                                         "colors": {"primary_color": 255}}])}
    spec = {"name": "New", "permissions": "3072", "color": 255}
    assert engine.role_edit(client(FakeHttp(routes), conn), G, ROLE, spec)["outcome"] == "done"
    assert engine.role_edit(client(FakeHttp(routes), conn), G, ROLE, {**spec, "hoist": True})["outcome"] == "uncertain"


def test_a_write_that_cannot_start_is_not_done(monkeypatch):
    def no_token():
        raise engine.EngineError("setup", "no Discord token in the Keychain")
    monkeypatch.setattr(engine, "read_token", no_token)
    result = engine.run("react", {"channel": DM1, "id": flake(1), "emoji": "x"}, http=FakeHttp())
    assert result == {"outcome": "not_done", "detail": "no Discord token in the Keychain", "kind": "setup"}


def test_a_message_mirrored_during_a_newest_page_read_is_kept():
    conn = store.connect(write=True)
    a = flake(30)
    mirrored(conn, a)
    meanwhile = flake(-0.2)      # stored by another process while the read was in flight

    def page(params, body):
        other = store.connect(write=True)
        store.upsert_messages(other, [store.message_row(msg(meanwhile, DM1), ME)])
        other.commit()
        other.close()
        return 200, {}, [msg(a, DM1)]
    engine.messages(client(FakeHttp({("GET", f"/channels/{DM1}/messages"): page}), conn), DM1)
    assert ids_in(conn) == [a, meanwhile]


def test_a_busy_channel_is_still_rechecked_when_due():
    conn = store.connect(write=True)
    old = flake(100 * 24 * 60)
    m1, m2, m3 = flake(60), flake(50), flake(1)
    engine.sync(client(FakeHttp(sync_routes(m2, (200, {}, [msg(m2, DM1), msg(m1, DM1)]), old)), conn))
    conn.execute("UPDATE cursors SET rechecked_at = 0")
    conn.commit()
    seen = []

    def page(params, body):
        seen.append(params)
        return 200, {}, [msg(m3, DM1)] if "after" in params else [msg(m3, DM1), msg(m2, DM1)]
    summary = engine.sync(client(FakeHttp(sync_routes(m3, page, old)), conn))
    assert seen == [{"after": m2, "limit": "100"}, {"limit": "50"}] and summary["rechecked"] == 1
    assert ids_in(conn) == [m2, m3]
