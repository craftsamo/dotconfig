import importlib.util
import io
import json
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


xa = _load("x_access_engine_test", ROOT / "xa.py")

STAMP = "2026-10-01 12:34:56+00:00"


def user(handle="alice", **extra):
    u = {"id": 42, "id_str": "42", "url": f"https://x.com/{handle}", "username": handle, "displayname": "Alice A",
         "rawDescription": "bio text", "created": "2020-01-02 03:04:05+00:00", "followersCount": 10,
         "friendsCount": 5, "statusesCount": 100, "favouritesCount": 1, "listedCount": 0, "mediaCount": 0,
         "location": "Tokyo", "profileImageUrl": "", "protected": False, "verified": False, "blue": True,
         "descriptionLinks": [{"url": "https://example.com", "text": "example.com", "tcourl": "https://t.co/x"}]}
    u.update(extra)
    return u


def post(pid="100", text="hello", **extra):
    p = {"id": int(pid), "id_str": pid, "url": f"https://x.com/alice/status/{pid}", "date": STAMP,
         "user": user(), "lang": "en", "rawContent": text, "replyCount": 1, "retweetCount": 2, "likeCount": 3,
         "quoteCount": 0, "bookmarkedCount": 0, "conversationId": int(pid), "conversationIdStr": pid,
         "hashtags": [], "cashtags": [], "mentionedUsers": [], "links": [],
         "media": {"photos": [], "videos": [], "animated": []}, "viewCount": 50, "retweetedTweet": None,
         "quotedTweet": None, "inReplyToTweetId": None, "inReplyToTweetIdStr": None, "inReplyToUser": None,
         "possibly_sensitive": False}
    p.update(extra)
    return p


FP = "fp0123456789"


class Bridge:
    """Stands in for xa.bridge: a canned reply per op (data, or a whole reply dict), every call recorded."""

    def __init__(self):
        self.calls = []
        self.replies = {"user": user(), "posts": [post("1"), post("2")], "search": [post("3")],
                        "details": post("100"), "thread": [post("100"), post("101")],
                        "check": {"ok": True, "data": None, "fingerprint": FP, "contacted": False}}

    def __call__(self, op, **fields):
        self.calls.append({"op": op, **fields})
        value = self.replies[op]
        if isinstance(value, BaseException):
            raise value
        if isinstance(value, dict) and "contacted" in value:
            return value
        return {"ok": True, "data": value, "warnings": [], "fingerprint": FP, "contacted": True,
                "session": {"active": True, "error": None, "locks": {}}}


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    section = {"main_handle": "@MainAcct", "download_dir": str(tmp_path / "inbox")}
    monkeypatch.setattr(xa, "_config", lambda home: section if home == h else {})
    return h


def test_config_section_is_read_from_the_profile(tmp_path):
    pytest.importorskip("yaml")  # the Hermes runtime has it; the test interpreter may not
    (tmp_path / "config.yaml").write_text("x_access:\n  main_handle: '@MainAcct'\n  download_dir: ~/in/x\n",
                                          encoding="utf-8")
    assert xa.main_handle(tmp_path) == "MainAcct"
    assert xa.download_dir(tmp_path) == Path.home() / "in" / "x"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    venv_python = tmp_path / "python"
    venv_python.write_text("")
    monkeypatch.setattr(xa, "STORE", store)
    monkeypatch.setattr(xa, "VENV_PYTHON", venv_python)
    monkeypatch.setattr(xa, "MIN_GAP", 0)
    fake = Bridge()
    monkeypatch.setattr(xa, "bridge", fake)
    return fake


# --- arguments ----------------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("1234567890", "1234567890"),
    ("https://x.com/alice/status/1234567890", "1234567890"),
    ("https://twitter.com/alice/status/1234567890?s=20", "1234567890"),
    ("https://mobile.x.com/i/web/status/1234567890/photo/1", "1234567890"),
    (1234567890, "1234567890"),
])
def test_post_ids(value, expected):
    assert xa._post_id({"post": value}) == expected


@pytest.mark.parametrize("value", [None, "", "abc", "https://evil.com/alice/status/1", "https://x.com/alice"])
def test_bad_post_ids(value):
    with pytest.raises(xa.XError):
        xa._post_id({"post": value})


def test_handles_and_limits():
    assert xa._handle("@Name_1") == "Name_1"
    for bad in ("", "a b", "x" * 16, "@", 5):
        with pytest.raises(xa.XError):
            xa._handle(bad)
    assert xa._limit({}, "search") == 20 and xa._limit({"limit": 500}, "search") == 50
    for bad in (0, -1, "3", True):
        with pytest.raises(xa.XError):
            xa._limit({"limit": bad}, "search")


def test_unknown_action():
    with pytest.raises(xa.XError):
        xa.execute({"action": "post"})


# --- reads --------------------------------------------------------------------------------------

def test_mentions_search_the_main_handle(isolated, home):
    result = xa.execute({"action": "mentions", "since": "2026-09-01"}, home=home)
    call = isolated.calls[-1]
    assert call["op"] == "search" and call["top"] is False and call["limit"] == 20
    assert call["query"] == "(@MainAcct OR to:MainAcct) -from:MainAcct since:2026-09-01"
    assert result["ok"] and result["handle"] == "@MainAcct" and result["note"] == xa.UNTRUSTED
    with pytest.raises(xa.XError):
        xa.execute({"action": "mentions", "since": "yesterday"}, home=home)


def test_mentions_need_the_main_handle(tmp_path):
    with pytest.raises(xa.XError, match="main_handle"):
        xa.execute({"action": "mentions"}, home=tmp_path)


def test_posts_resolve_and_cache_the_user_id(isolated, home):
    result = xa.execute({"action": "posts"}, home=home)
    assert [c["op"] for c in isolated.calls] == ["user", "posts"]
    assert isolated.calls[0]["handle"] == "MainAcct" and isolated.calls[1]["user_id"] == "42"
    assert result["count"] == 2 and result["more"] is False
    xa.execute({"action": "posts", "handle": "@mainacct", "replies": True}, home=home)
    assert [c["op"] for c in isolated.calls[2:]] == ["posts"]  # cached, case-insensitive
    assert isolated.calls[-1]["replies"] is True


def test_posts_refuse_protected_accounts(isolated, home):
    isolated.replies["user"] = user(protected=True)
    with pytest.raises(xa.XError, match="protected"):
        xa.execute({"action": "posts", "handle": "locked"}, home=home)


def test_search_shapes_posts(isolated):
    quoted = post("7", text="q" * 400)
    reply = post("3", text="t" * 3000, inReplyToTweetIdStr="2", inReplyToUser={"username": "bob"},
                 quotedTweet=quoted, possibly_sensitive=True,
                 links=[{"url": "https://example.com/a", "text": "", "tcourl": ""}],
                 media={"photos": [{"url": "https://pbs.twimg.com/media/A.jpg"}],
                        "videos": [{"thumbnailUrl": "", "duration": 65000, "variants": []}], "animated": [{}]})
    isolated.replies["search"] = [reply]
    result = xa.execute({"action": "search", "query": "  from:alice   lang:ja ", "top": True, "limit": 1})
    assert isolated.calls[-1]["query"] == "from:alice lang:ja" and result["tab"] == "top"
    shaped = result["posts"][0]
    assert shaped["author"] == "@alice" and shaped["text"].endswith("(+1000 characters)")
    assert shaped["reply_to"] == {"id": "2", "author": "@bob"}
    assert shaped["quoted"]["id"] == "7" and len(shaped["quoted"]["text"]) < 330 and "counts" not in shaped["quoted"]
    assert shaped["media"] == ["photo", "video 1:05", "gif"] and shaped["links"] == ["https://example.com/a"]
    assert shaped["counts"] == {"replies": 1, "reposts": 2, "likes": 3, "quotes": 0, "views": 50}
    assert shaped["sensitive"] is True and shaped["time"].startswith("2026-10-01") and result["more"] is True


def test_reposts_show_the_original(isolated):
    isolated.replies["search"] = [post("3", text="RT @bob: cut", retweetedTweet=post("9", text="full", user=user("bob")))]
    shaped = xa.execute({"action": "search", "query": "x"})["posts"][0]
    assert "text" not in shaped and shaped["repost_of"]["author"] == "@bob" and shaped["repost_of"]["text"] == "full"


def test_thread_reads_the_whole_conversation(isolated):
    isolated.replies["details"] = post("101", conversationIdStr="100")
    result = xa.execute({"action": "thread", "post": "https://x.com/alice/status/101"})
    assert [c["op"] for c in isolated.calls] == ["details", "thread"] and isolated.calls[1]["root"] == "100"
    assert result["post"]["id"] == "101" and result["root"] == "100" and result["count"] == 2


def test_missing_posts_explain_why(isolated):
    isolated.replies["details"] = None
    with pytest.raises(xa.XError, match="deleted"):
        xa.execute({"action": "thread", "post": "5"})


def test_user_profile(isolated):
    result = xa.execute({"action": "user", "handle": "alice"})
    u = result["user"]
    assert u["handle"] == "@alice" and u["verified"] is True and u["links"] == ["https://example.com"]
    assert u["joined"].startswith("2020-01-0") and result["note"] == xa.UNTRUSTED


def test_status_needs_no_request_to_x(isolated, home):
    result = xa.execute({"action": "status"}, home=home)
    assert [c["op"] for c in isolated.calls] == ["check"]
    assert result["main_handle"] == "MainAcct" and result["cookies"] is True
    assert "problem" not in result and result["usage"]["last_hour"] == 0


def test_status_reports_missing_setup(isolated, home):
    isolated.replies["check"] = {"ok": False, "kind": "setup", "error": "no sub-account cookies", "contacted": False}
    result = xa.execute({"action": "status"}, home=home)
    assert result["cookies"] is False and "no sub-account cookies" in result["problem"]
    xa.VENV_PYTHON.unlink()
    assert xa.execute({"action": "status"}, home=home)["problem"] == xa.NOT_INSTALLED


def test_reads_without_cookies_are_not_counted(isolated):
    isolated.replies["search"] = {"ok": False, "kind": "setup", "error": "no sub-account cookies", "contacted": False}
    with pytest.raises(xa.XError, match="not set up"):
        xa.execute({"action": "search", "query": "x"})
    assert xa.usage()["last_day"] == 0


def test_a_refused_session_is_remembered_until_the_cookies_change(isolated, home):
    isolated.replies["search"] = {"ok": False, "kind": "no_account", "fingerprint": FP, "contacted": True,
                                  "session": {"active": False, "error": "(32) Could not authenticate you",
                                              "locks": {}}}
    with pytest.raises(xa.XError, match="Could not authenticate"):
        xa.execute({"action": "search", "query": "a"})
    assert xa._read_state()["refused"]["fingerprint"] == FP
    assert "Could not authenticate" in xa.execute({"action": "status"}, home=home)["problem"]
    # the next call hands the fingerprint over; the bridge answers without contacting X
    isolated.replies["search"] = {"ok": False, "kind": "refused", "fingerprint": FP, "contacted": False}
    with pytest.raises(xa.XError, match="Could not authenticate"):
        xa.execute({"action": "search", "query": "b"})
    assert isolated.calls[-1]["refused"] == FP and xa.usage()["last_day"] == 1
    # fresh cookies: the bridge reads with them and the refusal is forgotten
    isolated.replies["search"] = [post("3")]
    assert xa.execute({"action": "search", "query": "c"})["count"] == 1
    assert "refused" not in xa._read_state()


def test_a_rate_limit_pauses_reads_without_contacting_x(isolated):
    isolated.replies["search"] = {"ok": False, "kind": "no_account", "fingerprint": FP, "contacted": True,
                                  "session": {"active": True, "error": None,
                                              "locks": {"SearchTimeline": "2999-01-01T00:00:00+00:00"}}}
    with pytest.raises(xa.XError, match="rate-limiting"):
        xa.execute({"action": "search", "query": "a"})
    with pytest.raises(xa.XError, match="rate-limiting"):
        xa.execute({"action": "user", "handle": "alice"})
    assert len(isolated.calls) == 1 and xa.usage()["last_day"] == 1


# --- pacing -------------------------------------------------------------------------------------

def test_hourly_cap(isolated, monkeypatch):
    monkeypatch.setattr(xa, "HOURLY", 2)
    xa.execute({"action": "search", "query": "a"})
    xa.execute({"action": "search", "query": "b"})
    with pytest.raises(xa.XError, match="paused"):
        xa.execute({"action": "search", "query": "c"})
    assert len(isolated.calls) == 2 and xa.usage()["last_hour"] == 2


def test_daily_cap(monkeypatch):
    monkeypatch.setattr(xa, "DAILY", 1)
    xa.execute({"action": "search", "query": "a"})
    with pytest.raises(xa.XError, match="24 hours"):
        xa.execute({"action": "search", "query": "b"})


def test_gap_between_calls(monkeypatch):
    slept = []
    monkeypatch.setattr(xa, "MIN_GAP", 5)
    monkeypatch.setattr(xa.time, "sleep", lambda s: slept.append(s))
    xa.execute({"action": "search", "query": "a"})
    xa.execute({"action": "search", "query": "b"})
    assert len(slept) == 1 and 0 < slept[0] <= 5


# --- bridge -------------------------------------------------------------------------------------

@pytest.fixture
def real_bridge(monkeypatch):
    original = _load("x_access_engine_bridge_test", ROOT / "xa.py")
    monkeypatch.setattr(original, "STORE", xa.STORE)
    monkeypatch.setattr(original, "VENV_PYTHON", xa.VENV_PYTHON)
    monkeypatch.setattr(original, "MIN_GAP", 0)
    return original


def completed(reply, returncode=0):
    return subprocess.CompletedProcess([], returncode, stdout=reply if isinstance(reply, str) else json.dumps(reply),
                                       stderr="")


def test_bridge_request_and_minimal_env(real_bridge, monkeypatch):
    seen = {}

    def run(argv, **kwargs):
        seen.update(argv=argv, **kwargs)
        return completed({"ok": True, "data": [1], "warnings": ["w"], "contacted": True})

    monkeypatch.setenv("TWS_PROXY", "socks5://x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-gateway")
    monkeypatch.setattr(real_bridge.subprocess, "run", run)
    assert real_bridge.request("search", query="q", limit=5) == ([1], ["w"])
    payload = json.loads(seen["input"])
    assert payload["op"] == "search" and payload["query"] == "q" and payload["refused"] is None
    assert seen["argv"][1].endswith("bridge.py") and seen["cwd"] == str(xa.STORE)
    env = seen["env"]
    assert env["TWS_TELEMETRY"] == "0" and env["TWS_HTTP_BACKEND"] == "curl"
    assert "TWS_PROXY" not in env and "ANTHROPIC_API_KEY" not in env


@pytest.mark.parametrize("reply,match", [
    ({"ok": False, "kind": "error", "error": "ValueError: boom", "contacted": True}, "boom"),
    ({"ok": False, "kind": "no_account", "contacted": True, "session": {"active": True, "locks": {}}},
     "no usable session"),
    ("Traceback", "without a result"),
])
def test_bridge_failures_count_as_contact(real_bridge, monkeypatch, reply, match):
    monkeypatch.setattr(real_bridge.subprocess, "run", lambda argv, **kw: completed(reply, 1))
    with pytest.raises(real_bridge.XError, match=match):
        real_bridge.request("search", query="q", limit=5)
    assert real_bridge.usage()["last_day"] == 1  # X may have been reached: counted


def test_bridge_timeout(real_bridge, monkeypatch):
    def run(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, 1)
    monkeypatch.setattr(real_bridge.subprocess, "run", run)
    with pytest.raises(real_bridge.XError, match="did not answer"):
        real_bridge.request("details", id="1")
    assert real_bridge.usage()["last_day"] == 1


# --- media --------------------------------------------------------------------------------------

def media_post():
    return post("100", media={
        "photos": [{"url": "https://pbs.twimg.com/media/ABC.jpg"}],
        "videos": [{"thumbnailUrl": "", "duration": 1000, "variants": [
            {"contentType": "video/mp4", "bitrate": 256000, "url": "https://video.twimg.com/low.mp4"},
            {"contentType": "video/mp4", "bitrate": 2176000, "url": "https://video.twimg.com/high.mp4"}]}],
        "animated": [{"thumbnailUrl": "", "videoUrl": "https://video.twimg.com/gif.mp4"}]},
        quotedTweet=post("7", media={"photos": [{"url": "https://pbs.twimg.com/media/Q.png"}]}))


def test_media_items_pick_originals_and_best_video():
    items = xa.media_items(media_post(), quoted=False)
    assert [(i["kind"], i["url"]) for i in items] == [
        ("photo", "https://pbs.twimg.com/media/ABC.jpg?name=orig"),
        ("video", "https://video.twimg.com/high.mp4"),
        ("gif", "https://video.twimg.com/gif.mp4")]
    assert xa.media_items(media_post(), quoted=True)[-1] == {
        "post": "7", "kind": "photo", "url": "https://pbs.twimg.com/media/Q.png?name=orig"}
    repost = post("1", retweetedTweet=media_post())
    assert len(xa.media_items(repost, quoted=False)) == 3


class Response(io.BytesIO):
    def __init__(self, body, mime, length=True):
        super().__init__(body)
        declared = len(body) if length is True else length
        self.headers = {"Content-Type": mime, **({"Content-Length": str(declared)} if declared is not False else {})}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def serve(monkeypatch, responses, seen):
    def open_(req, timeout=None):
        seen.append(req)
        return responses[req.full_url]
    monkeypatch.setattr(xa._OPENER, "open", open_)


def test_media_downloads_into_the_post_folder(isolated, home, monkeypatch, tmp_path):
    isolated.replies["details"] = media_post()
    seen = []
    serve(monkeypatch, {
        "https://pbs.twimg.com/media/ABC.jpg?name=orig": Response(b"jpg", "image/jpeg"),
        "https://video.twimg.com/high.mp4": Response(b"mp4", "video/mp4"),
        "https://video.twimg.com/gif.mp4": Response(b"gif", "video/mp4", length=False)}, seen)
    result = xa.execute({"action": "media", "post": "https://x.com/alice/status/100"}, home=home)
    folder = tmp_path / "inbox" / "100"
    assert result["folder"] == str(folder) and "failed" not in result
    assert [Path(f["path"]).name for f in result["files"]] == ["100-1.jpg", "100-2.mp4", "100-3.mp4"]
    assert (folder / "100-1.jpg").read_bytes() == b"jpg"
    assert sorted(p.name for p in folder.iterdir()) == ["100-1.jpg", "100-2.mp4", "100-3.mp4"]
    assert all("Cookie" not in r.headers for r in seen)
    again = xa.execute({"action": "media", "post": "100"}, home=home)  # already there: not fetched again
    assert len(seen) == 3 and all(f["reused"] for f in again["files"])


def test_media_refuses_wrong_types_and_hosts(isolated, home, monkeypatch, tmp_path):
    isolated.replies["details"] = media_post()
    serve(monkeypatch, {
        "https://pbs.twimg.com/media/ABC.jpg?name=orig": Response(b"<html>", "text/html"),
        "https://video.twimg.com/high.mp4": Response(b"x" * 10, "video/mp4"),
        "https://video.twimg.com/gif.mp4": Response(b"x", "application/zip")}, [])
    monkeypatch.setattr(xa, "MEDIA_MAX_BYTES", 5)
    with pytest.raises(xa.XError, match="no file was downloaded"):
        xa.execute({"action": "media", "post": "100"}, home=home)
    assert not [p for p in (tmp_path / "inbox" / "100").iterdir()]
    with pytest.raises(xa.XError, match="CDN"):
        xa._check_url("https://evil.example/a.jpg")
    with pytest.raises(xa.XError, match="CDN"):
        xa._check_url("http://pbs.twimg.com/a.jpg")


def test_media_refuses_truncated_downloads(isolated, home, monkeypatch, tmp_path):
    isolated.replies["details"] = post("100", media={"photos": [{"url": "https://pbs.twimg.com/media/A.jpg"}]})
    serve(monkeypatch, {"https://pbs.twimg.com/media/A.jpg?name=orig": Response(b"half", "image/jpeg", length=10)}, [])
    with pytest.raises(xa.XError, match="stopped after 4 of 10"):
        xa.execute({"action": "media", "post": "100"}, home=home)
    assert list((tmp_path / "inbox" / "100").iterdir()) == []


def test_cache_writes_keep_the_pacing_ledger(isolated):
    xa.execute({"action": "search", "query": "a"})
    xa._cache_user_id("Bob", "7")
    xa.execute({"action": "search", "query": "b"})
    state = xa._read_state()
    assert len(state["calls"]) == 2 and state["users"]["bob"]["id"] == "7"
    assert sorted(p.name for p in xa.STORE.iterdir()) == ["call.lock", "state.json"]


def test_media_without_files(isolated, home):
    isolated.replies["details"] = post("100", quotedTweet=post("7", media={"photos": [{"url": "u"}]}))
    with pytest.raises(xa.XError, match="quoted=true"):
        xa.execute({"action": "media", "post": "100"}, home=home)


def test_default_download_dir(tmp_path):
    assert xa.download_dir(tmp_path) == tmp_path / "x-downloads"


# --- guard --------------------------------------------------------------------------------------

@pytest.mark.parametrize("tool,args", [
    ("terminal", {"command": "twscrape search foo"}),
    ("terminal", {"command": "~/.config/hermes/local/twscrape/venv/bin/python -c 'import twscrape'"}),
    ("terminal", {"command": "sqlite3 ~/.x-access/accounts.db .dump"}),
    ("terminal", {"command": "python3 plugins/x-access/bridge.py"}),
    ("terminal", {"command": "TWS_PROXY=x python3 run.py"}),
    ("terminal", {"command": "secret get X_READER_COOKIES -p hermes --scope x-reader"}),
    ("terminal", {"command": "security find-generic-password -s secret.hermes/x-reader -w"}),
    ("read_file", {"path": "/Users/u/.config/hermes/local/twscrape/venv/lib/site.py"}),
    ("terminal", {"command": "ls", "workdir": "/Users/u/.x-access"}),
    ("read_file", {"path": "/Users/u/.x-access/accounts.db"}),
    ("search_files", {"path": "~/.x-access", "pattern": "ct0"}),
])
def test_bypass_blocked(tool, args):
    assert xa.bypass(tool, args) == xa.BYPASS_MESSAGE


@pytest.mark.parametrize("tool,args", [
    ("terminal", {"command": "curl -H 'X-Access-Token: 1' https://api.example.com"}),
    ("terminal", {"command": "ls ~/Workspaces/.inbox/x/100"}),
    ("read_file", {"path": "/Users/u/Workspaces/.inbox/x/100/100-1.jpg"}),
    ("read_file", {"path": "/Users/u/.config/hermes/plugins/x-access/xa.py"}),
    ("web_search", {"query": "twscrape"}),
])
def test_bypass_allowed(tool, args):
    assert xa.bypass(tool, args) is None
