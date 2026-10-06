from datetime import datetime, timedelta, timezone
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
    assert shaped["counts"] == {"replies": 1, "reposts": 2, "likes": 3, "quotes": 0, "bookmarks": 0, "views": 50}
    assert result["read_at"][:4].isdigit()
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


# --- snapshot and insights ----------------------------------------------------------------------

def ago(hours):
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def own(pid, hours, **extra):
    return post(pid, **{"user": user("MainAcct"), "date": ago(hours), **extra})


def test_snapshot_records_the_main_accounts_own_posts(isolated, home):
    isolated.replies["posts"] = [
        own("1", 5, viewCount=100, likeCount=5, bookmarkedCount=2,
            media={"photos": [{"url": "https://pbs.twimg.com/media/A.jpg"}], "videos": [], "animated": []}),
        own("2", 30, links=[{"url": "https://example.com", "text": "", "tcourl": ""}], rawContent="x" * 300),
        own("3", 1, retweetedTweet=post("9")),          # a repost: not the account's own post
        post("4"),                                      # another author
    ]
    result = xa.execute({"action": "snapshot"}, home=home)
    assert [c["op"] for c in isolated.calls] == ["user", "posts"] and isolated.calls[1]["replies"] is False
    assert result["recorded"] == 2 and result["skipped"] == 2 and result["handle"] == "@MainAcct"
    assert result["posts"][0] == {"id": "1", "age_h": result["posts"][0]["age_h"], "views": 100, "likes": 5,
                                  "replies": 1, "reposts": 2, "quotes": 0, "bookmarks": 2}
    ledger = xa._ledger_path()
    assert ledger.stat().st_mode & 0o777 == 0o600
    first, second = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert first["handle"] == "mainacct" and first["format"] == "photo" and 4.9 < first["age_h"] < 5.1
    assert second["format"] == "link" and second["link"] is True and second["chars"] == 300
    assert second["text"].endswith("characters)")
    xa.execute({"action": "snapshot", "replies": True, "limit": 5}, home=home)
    assert [c["op"] for c in isolated.calls[2:]] == ["posts"] and isolated.calls[-1]["limit"] == 5
    assert len(ledger.read_text().splitlines()) == 4


def test_snapshot_and_insights_need_the_main_handle(tmp_path):
    for action in ("snapshot", "insights"):
        with pytest.raises(xa.XError, match="main_handle"):
            xa.execute({"action": action}, home=tmp_path)


def rec(pid, posted_ago, age_h, views, **extra):
    posted = datetime.now(timezone.utc) - timedelta(hours=posted_ago)
    r = {"v": 1, "at": (posted + timedelta(hours=age_h)).isoformat(timespec="seconds"), "handle": "mainacct",
         "id": pid, "posted": posted.isoformat(timespec="seconds"), "age_h": age_h, "views": views,
         "likes": views // 10, "replies": 1, "reposts": 0, "quotes": 0, "bookmarks": 0, "format": "text",
         "link": False, "reply": False, "chars": 100, "text": f"post {pid}"}
    r.update(extra)
    return r


def seed():
    records = []
    for n in range(6):
        fmt = "photo" if n < 2 else "text"
        records += [rec(str(n), 72 + n, 5.5, 10 * (n + 1), format=fmt),
                    rec(str(n), 72 + n, 24.5, 100 * (n + 1), format=fmt, chars=200 if n == 5 else 100)]
    records += [rec("young", 2, 2, 7), rec("missed", 100, 70, 900), rec("old", 24 * 60, 24, 5),
                {**rec("other", 50, 24, 5), "handle": "someone"}]
    xa._append(records)


def test_insights_compare_at_equal_age_without_contacting_x(isolated, home):
    seed()
    result = xa.execute({"action": "insights"}, home=home)
    assert isolated.calls == []
    assert result["at_age_h"] == 24 and result["days"] == 30
    assert result["health"]["posts"] == 8
    assert (result["health"]["comparable"], result["health"]["too_young"],
            result["health"]["no_snapshot_near_age"]) == (6, 1, 1)
    assert result["baseline"]["n"] == 6 and result["baseline"]["median_views"] == 350
    assert set(result["by_format"]) == {"photo", "text"} and result["by_format"]["photo"]["inconclusive"] is True
    assert result["by_format"]["text"]["n"] == 4 and result["by_length"]["141–280"]["n"] == 1
    assert [p["id"] for p in result["top"]] == ["5", "4", "3"] and [p["id"] for p in result["bottom"]] == ["2", "1", "0"]
    assert result["top"][0]["url"] == "https://x.com/MainAcct/status/5" and "by_reply" not in result
    early = xa.execute({"action": "insights", "at": 6, "days": 365}, home=home)
    assert early["days"] == 180 and early["baseline"]["median_views"] == 35
    assert early["health"]["posts"] == 9  # the 60-day-old post is inside 180 days


def test_insights_trajectory_of_one_post(isolated, home):
    seed()
    result = xa.execute({"action": "insights", "post": "https://x.com/MainAcct/status/3"}, home=home)
    assert [o["age_h"] for o in result["observations"]] == [5.5, 24.5]
    assert result["observations"][1]["views"] == 400 and result["observations"][1]["engagement_rate"] == 0.1025
    with pytest.raises(xa.XError, match="no snapshot"):
        xa.execute({"action": "insights", "post": "123"}, home=home)
    assert isolated.calls == []


def test_insights_arguments_and_an_empty_ledger(home):
    for bad in ({"at": 12}, {"at": True}, {"days": 0}, {"days": "7"}):
        with pytest.raises(xa.XError):
            xa.execute({"action": "insights", **bad}, home=home)
    result = xa.execute({"action": "insights"}, home=home)
    assert result["ok"] and result["health"]["posts"] == 0 and "problem" in result


def test_protected_posts_never_enter_the_ledger(isolated, home):
    isolated.replies["user"] = user("MainAcct", protected=True)
    xa.execute({"action": "user", "handle": "MainAcct"})        # not cached: it would skip the check
    with pytest.raises(xa.XError, match="protected"):
        xa.execute({"action": "snapshot"}, home=home)
    isolated.replies["user"] = user("MainAcct")
    isolated.replies["posts"] = [own("1", 5, user=user("MainAcct", protected=True))]  # became protected
    with pytest.raises(xa.XError, match="protected"):
        xa.execute({"action": "snapshot"}, home=home)
    assert not xa._ledger_path().exists()


def test_a_quote_attachment_is_not_a_link():
    quoted = post("7")
    attach = {"url": "https://x.com/alice/status/7", "text": "", "tcourl": ""}
    other = {"url": "https://example.com/a", "text": "", "tcourl": ""}
    assert xa.post_format(post("1", quotedTweet=quoted, links=[attach])) == "quote"
    assert xa.own_links(post("1", quotedTweet=quoted, links=[attach])) == []
    assert xa.post_format(post("1", quotedTweet=quoted, links=[attach, other])) == "link"
    assert xa.post_format(post("1", links=[attach])) == "link"   # a pasted post URL without a quote


def test_a_damaged_line_is_skipped_and_the_next_append_stays_whole(home):
    xa._append([rec("1", 30, 24, 10)])
    with open(xa._ledger_path(), "ab") as out:
        out.write('{"id": "日本'.encode("utf-8")[:-1])        # an append cut mid-character
    xa._append([rec("2", 30, 24, 20)])
    assert [r["id"] for r in xa._ledger("MainAcct")] == ["1", "2"]
    assert xa.execute({"action": "insights"}, home=home)["health"]["posts"] == 2


def test_the_cron_entry_is_silent_unless_something_is_broken(isolated, home, capsys):
    isolated.replies["posts"] = [own("1", 5)]
    assert xa.cli(["snapshot", str(home)]) == 0 and capsys.readouterr().out == ""
    assert len(xa._ledger("MainAcct")) == 1
    isolated.replies["posts"] = xa.XError("paused: 30 reads of X in the last hour")
    assert xa.cli(["snapshot", str(home)]) == 0
    isolated.replies["posts"] = xa.XError("X refused the sub-account's session")
    assert xa.cli(["snapshot", str(home)]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "refused" in captured.err
    assert xa.cli(["posts", str(home)]) == 2


def test_the_cron_script_runs_the_engine_for_its_own_profile():
    script = ROOT.parents[2] / "profiles/assistant/scripts/x-snapshot.sh"
    text = script.read_text()
    assert script.stat().st_mode & 0o111
    assert 'home=$(cd "$(dirname "$0")/.." && pwd)' in text and "${HERMES_HOME" not in text
    assert (script.parent / "../../../plugins/social/x-access/xa.py").resolve() == ROOT / "xa.py"
    assert '"$engine" snapshot "$home"' in text and "--no-agent" in text


def test_the_ledger_is_pruned_once_large(monkeypatch):
    monkeypatch.setattr(xa, "LEDGER_MAX_BYTES", 600)
    xa._append([rec("old", 24 * 200, 24, 1, at=ago(24 * 200))])
    xa._append([rec(str(n), 30, 24, n) for n in range(3)])
    xa._append([rec("new", 30, 24, 9)])
    ids = [json.loads(line)["id"] for line in xa._ledger_path().read_text().splitlines()]
    assert "old" not in ids and ids[-1] == "new"


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


# --- verify -------------------------------------------------------------------------------------

def fx_tweet(pid="100", handle="alice", **extra):
    t = {"id": pid, "url": f"https://x.com/{handle}/status/{pid}", "text": "hello", "raw_text": {"text": "hello"},
         "created_timestamp": 1759322096, "lang": "en", "likes": 3, "retweets": 2, "replies": 1, "quotes": 0,
         "bookmarks": 4, "views": 50, "replying_to": None, "replying_to_status": None, "possibly_sensitive": False,
         "author": {"screen_name": handle, "name": "Alice A", "followers": 10, "protected": False},
         "media": {"all": [{"type": "video", "duration": 27.326, "width": 1920, "height": 1080,
                            "url": "https://video.twimg.com/v.mp4"}]}}
    t.update(extra)
    return t


class Fx:
    """Stands in for FxTwitter: a canned (status, body) per post id, every request recorded."""

    def __init__(self, monkeypatch):
        self.requests = []
        self.replies = {}
        monkeypatch.setattr(xa._FX_OPENER, "open", self.open)

    def found(self, pid, **extra):
        self.replies[pid] = (200, json.dumps({"code": 200, "message": "OK", "tweet": fx_tweet(pid, **extra)}).encode())

    def open(self, req, timeout=None):
        self.requests.append(req)
        pid = req.full_url.rsplit("/", 1)[1]
        status, body = self.replies.get(pid, (404, b'{"code":404,"message":"NOT_FOUND","tweet":null}'))
        if isinstance(body, BaseException):
            raise body
        if status != 200:
            raise xa.urllib.error.HTTPError(req.full_url, status, "x", {}, io.BytesIO(body))
        return Response(body, "application/json")


@pytest.fixture
def fx(monkeypatch):
    monkeypatch.setattr(xa, "FX_GAP", 0)
    return Fx(monkeypatch)


def test_verify_checks_posts_without_the_sub_account(isolated, home, fx):
    fx.found("100")
    fx.found("200", quote=fx_tweet("7", handle="bob"), replying_to="carol", replying_to_status="9")
    result = xa.execute({"action": "verify", "posts": ["https://x.com/alice/status/100?s=20", "200", "100", "300"]},
                        home=home)
    assert isolated.calls == [] and xa.usage()["last_day"] == 0
    assert [r.full_url for r in fx.requests] == [xa.FX_API + p for p in ("100", "200", "300")]
    first, second, missing = result["results"]
    assert first["status"] == "ok" and first["author"] == "@alice" and first["followers"] == 10
    assert first["counts"] == {"views": 50, "likes": 3, "replies": 1, "reposts": 2, "quotes": 0, "bookmarks": 4}
    assert first["media"] == [{"type": "video", "width": 1920, "height": 1080, "duration_s": 27.3}]
    assert "handle_mismatch" not in first and "saved" not in first
    assert second["quoted"]["author"] == "@bob" and second["reply_to"] == {"id": "9", "author": "@carol"}
    assert missing == {"id": "300", "status": "not_found", "reason": missing["reason"]}
    assert result["summary"] == {"ok": 2, "not_found": 1} and result["checked"] == 3
    assert xa.verify_usage()["last_day"] == 3
    assert "folder" not in result and not (home.parent / "inbox").exists()


def test_verify_flags_a_url_naming_another_author(fx):
    fx.found("100", handle="realauthor")
    item = xa.execute({"action": "verify", "posts": ["https://x.com/someoneelse/status/100",
                                                     "https://x.com/i/web/status/100"]})["results"]
    assert len(item) == 1 and item[0]["handle_mismatch"] is True and item[0]["url_handle"] == "@someoneelse"
    assert "handle_mismatch" not in xa.execute({"action": "verify", "posts": ["https://x.com/i/status/100"]})["results"][0]


def test_verify_saves_raw_replies(home, fx, tmp_path):
    fx.found("100")
    result = xa.execute({"action": "verify", "posts": ["100", "404"], "save": True}, home=home)
    folder = tmp_path / "inbox" / "verify"
    assert result["folder"] == str(folder) and result["results"][0]["saved"] == str(folder / "100.json")
    assert json.loads((folder / "100.json").read_text())["tweet"]["id"] == "100"
    assert sorted(p.name for p in folder.iterdir()) == ["100.json"]


def test_verify_statuses(fx):
    fx.replies["401"] = (401, b'{"code":401,"message":"PRIVATE_TWEET","tweet":null}')
    fx.replies["500"] = (500, b"<html>")
    fx.replies["201"] = (200, b"<!DOCTYPE html>")
    fx.replies["429"] = (429, b"")
    result = xa.execute({"action": "verify", "posts": ["401", "500", "201", "429", "1"]})
    assert [(r["id"], r["status"]) for r in result["results"]] == [
        ("401", "protected"), ("500", "unavailable"), ("201", "unavailable"), ("429", "not_checked"),
        ("1", "not_checked")]
    assert result["checked"] == 4 and "rate-limiting" in result["results"][-1]["reason"]


def test_verify_stops_after_repeated_network_failures(fx):
    for pid in ("1", "2", "3", "4"):
        fx.replies[pid] = (200, xa.urllib.error.URLError("offline"))
    result = xa.execute({"action": "verify", "posts": ["1", "2", "3", "4"]})
    assert [r["status"] for r in result["results"]] == ["error", "error", "error", "not_checked"]
    assert len(fx.requests) == 3


def test_verify_has_its_own_daily_cap(fx, monkeypatch):
    monkeypatch.setattr(xa, "FX_DAILY", 2)
    fx.found("1")
    result = xa.execute({"action": "verify", "posts": ["1", "2", "3"]})
    assert [r["status"] for r in result["results"]] == ["ok", "not_found", "not_checked"]
    with pytest.raises(xa.XError, match="paused: 2 public-post checks"):
        xa.execute({"action": "verify", "posts": ["1"]})
    assert len(fx.requests) == 2


def test_verify_refuses_redirects_off_fxtwitter():
    handler = xa._FxOnly()
    with pytest.raises(xa.XError, match="redirected"):
        handler.redirect_request(None, None, 302, "", {}, "https://evil.example/i/status/1")


@pytest.mark.parametrize("posts,match", [
    (None, "posts is required"), ([], "posts is required"), ("100", "posts is required"),
    (["1"] * 51, "at most 50"), (["100", "https://evil.com/a/status/1"], r"posts\[2\]"),
])
def test_verify_arguments(posts, match):
    with pytest.raises(xa.XError, match=match):
        xa.execute({"action": "verify", "posts": posts})


def test_verify_opener_carries_no_cookies_and_stays_on_fxtwitter():
    handlers = xa._FX_OPENER.handlers
    assert any(isinstance(h, xa._FxOnly) for h in handlers)
    assert not any(isinstance(h, xa.urllib.request.HTTPCookieProcessor) for h in handlers)


def test_verify_accepts_mirror_links():
    assert xa._post_ref("https://fxtwitter.com/alice/status/100") == ("100", "alice")
    assert xa._post_ref("https://fixvx.com/i/status/100") == ("100", None)


def test_verify_survives_odd_reply_shapes(fx):
    fx.replies["100"] = (200, json.dumps({"code": 200, "tweet": {
        "id": None, "author": "x", "text": 5, "media": [], "quote": "q", "views": "many"}}).encode())
    item = xa.execute({"action": "verify", "posts": ["100"]})["results"][0]
    assert item["id"] == "100" and item["status"] == "ok" and item["author"] == "@" and item["counts"] == {}


def test_verify_server_failures_end_the_call(fx):
    for pid in ("1", "2", "3", "4"):
        fx.replies[pid] = (503, b"<html>down</html>")
    result = xa.execute({"action": "verify", "posts": ["1", "2", "3", "4"]})
    assert [r["status"] for r in result["results"]] == ["unavailable"] * 3 + ["not_checked"]
    assert "HTTP 503" in result["results"][0]["reason"] and len(fx.requests) == 3


@pytest.mark.parametrize("error", [TimeoutError(), xa.http.client.IncompleteRead(b"")])
def test_verify_counts_broken_replies_as_errors(fx, error):
    for pid in ("1", "2", "3"):
        fx.replies[pid] = (200, error)
    result = xa.execute({"action": "verify", "posts": ["1", "2", "3"]})
    assert [r["status"] for r in result["results"]] == ["error"] * 3


def test_verify_rejects_oversized_and_non_object_replies(fx, monkeypatch):
    monkeypatch.setattr(xa, "FX_MAX_BYTES", 10)
    fx.found("1")
    fx.replies["2"] = (200, b"[]")
    result = xa.execute({"action": "verify", "posts": ["1", "2"]})
    assert [r["status"] for r in result["results"]] == ["unavailable", "unavailable"]


def test_verify_remembers_a_rate_limit(fx):
    fx.replies["1"] = (429, b"")
    xa.execute({"action": "verify", "posts": ["1", "2"]})
    assert "limited_until" in xa.verify_usage()
    with pytest.raises(xa.XError, match="paused: FxTwitter is rate-limiting; try again after"):
        xa.execute({"action": "verify", "posts": ["2"]})
    assert len(fx.requests) == 1


def test_verify_time_budget_starts_after_the_lock(fx, monkeypatch):
    ticks = iter([0, 0, 0] + [1000] * 10)
    monkeypatch.setattr(xa.time, "monotonic", lambda: next(ticks))
    fx.found("1")
    result = xa.execute({"action": "verify", "posts": ["1", "2"]})
    assert [r["status"] for r in result["results"]] == ["ok", "not_checked"]
    assert "time budget" in result["results"][1]["reason"]


def test_verify_waits_for_another_verify(fx, monkeypatch):
    monkeypatch.setattr(xa, "FX_LOCK_WAIT", 0.2)
    xa.STORE.mkdir(exist_ok=True)
    with open(xa.STORE / "fx.lock", "a+") as held:
        xa.fcntl.flock(held, xa.fcntl.LOCK_EX)
        with pytest.raises(xa.XError, match="another verify is still running"):
            xa.execute({"action": "verify", "posts": ["1"]})
    assert fx.requests == []


def test_verify_drops_a_stale_saved_file(home, fx, tmp_path):
    fx.found("100")
    xa.execute({"action": "verify", "posts": ["100"], "save": True}, home=home)
    saved = tmp_path / "inbox" / "verify" / "100.json"
    assert saved.exists()
    del fx.replies["100"]  # deleted since
    assert xa.execute({"action": "verify", "posts": ["100"], "save": True}, home=home)["results"][0]["status"] == "not_found"
    assert not saved.exists()


def test_verify_reports_a_failed_save_without_losing_the_row(home, fx, monkeypatch):
    fx.found("100")
    def broken(folder, post_id, body):
        raise PermissionError("read-only")
    monkeypatch.setattr(xa, "_save_fx", broken)
    item = xa.execute({"action": "verify", "posts": ["100"], "save": True}, home=home)["results"][0]
    assert item["status"] == "ok" and "read-only" in item["save_error"] and "saved" not in item


def test_verify_results_fit_the_plugin_cap(fx):
    long = "長い本文" * 600
    ids = [str(n) for n in range(1, 51)]
    for pid in ids:
        fx.found(pid, text=long, quote=fx_tweet("9" + pid, text=long))
    result = xa.execute({"action": "verify", "posts": ids})
    assert result["summary"] == {"ok": 50} and result["text_clipped_to"] < xa.TEXT_CLIP
    assert len(json.dumps(result, ensure_ascii=False)) <= xa.FX_RESULT_MAX
    small = xa.execute({"action": "verify", "posts": ["1"]})
    assert "text_clipped_to" not in small and small["results"][0]["text"].startswith("長い本文")


def test_status_reports_verify_usage(isolated, home):
    assert xa.execute({"action": "status"}, home=home)["verify_usage"] == {"last_day": 0, "daily_cap": xa.FX_DAILY}


# --- guard --------------------------------------------------------------------------------------

@pytest.mark.parametrize("tool,args", [
    ("terminal", {"command": "twscrape search foo"}),
    ("terminal", {"command": "~/.config/hermes/local/twscrape/venv/bin/python -c 'import twscrape'"}),
    ("terminal", {"command": "sqlite3 ~/.x-access/accounts.db .dump"}),
    ("terminal", {"command": "python3 plugins/social/x-access/bridge.py"}),
    ("terminal", {"command": "TWS_PROXY=x python3 run.py"}),
    ("terminal", {"command": "secret get X_READER_COOKIES -p hermes --scope x-reader"}),
    ("terminal", {"command": "security find-generic-password -s secret.hermes/x-reader -w"}),
    ("read_file", {"path": "/Users/u/.config/hermes/local/twscrape/venv/lib/site.py"}),
    ("terminal", {"command": "ls", "workdir": "/Users/u/.x-access"}),
    ("read_file", {"path": "/Users/u/.x-access/accounts.db"}),
    ("search_files", {"path": "~/.x-access", "pattern": "ct0"}),
    ("terminal", {"command": "curl -s https://api.fxtwitter.com/i/status/100"}),
    ("terminal", {"command": "curl -s https://api.vxtwitter.com/alice/status/100"}),
    ("terminal", {"command": "python3 fetch.py https://fixupx.com/alice/status/100"}),
    ("terminal", {"command": "curl -s https://api.fixvx.com/alice/status/100"}),
])
def test_bypass_blocked(tool, args):
    assert xa.bypass(tool, args) == xa.BYPASS_MESSAGE


@pytest.mark.parametrize("tool,args", [
    ("terminal", {"command": "curl -H 'X-Access-Token: 1' https://api.example.com"}),
    ("terminal", {"command": "ls ~/Workspaces/.inbox/x/100"}),
    ("read_file", {"path": "/Users/u/Workspaces/.inbox/x/100/100-1.jpg"}),
    ("read_file", {"path": "/Users/u/.config/hermes/plugins/social/x-access/xa.py"}),
    ("web_search", {"query": "twscrape"}),
])
def test_bypass_allowed(tool, args):
    assert xa.bypass(tool, args) is None
