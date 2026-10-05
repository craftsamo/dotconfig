import importlib.util
import json
from pathlib import Path
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sa = _load("substack_access_engine_test", ROOT / "sa.py")

FP = "fp0123456789"
PUB = {"id": 7, "name": "CraftSamo", "subdomain": "craftsamo", "custom_domain": None, "role": "admin",
       "url": "https://craftsamo.substack.com", "api": "https://craftsamo.substack.com/api/v1", "user_id": 1}


def item(pid=1, **extra):
    p = {"id": pid, "title": f"Title {pid}", "subtitle": "Sub", "slug": f"slug-{pid}", "type": "newsletter",
         "post_date": "2026-09-10T17:58:42.659Z", "audience": "everyone", "wordcount": 120,
         "canonical_url": f"https://post.substack.com/p/slug-{pid}", "truncated_body_text": "Preview text",
         "publication_id": 9, "publishedBylines": [{"name": "Ann", "handle": "ann"}], "comment_count": 2,
         "reaction_count": 5, "restacks": 1}
    p.update(extra)
    return p


class Bridge:
    """Stands in for sa.bridge: a canned reply per op (data, or a whole reply dict), every call recorded."""

    def __init__(self):
        self.calls = []
        self.replies = {
            "check": {"ok": True, "data": None, "fingerprint": FP, "contacted": False},
            "archive": {"publication": PUB, "posts": [item(1), item(2)]},
            "post": {"post": item(3, body_html="<h2>Head</h2><p>Hello <a href='https://e.com/x'>link</a></p>"
                                               "<script>bad()</script><ul><li>one</li></ul>"),
                     "publication": {"name": "Post"}, "membership": "free_signup"},
            "inbox": {"posts": [item(4), item(5), item(6)], "publications": {"9": "Post"}, "more": False},
            "published": {"publication": PUB, "posts": [item(7, views=10, stats={"opens": 3})], "total": 1},
            "drafts": {"publication": PUB, "posts": [{"id": 8, "draft_title": "", "audience": "everyone",
                                                      "draft_updated_at": "2026-10-05T06:30:32Z"}], "more": False},
            "draft": {"publication": PUB, "draft": {"id": 8, "draft_title": "Hi"}, "markdown": "# Hi", "unsupported": 0},
            "stats": {"publication": PUB, "summary": {"subscribers": 4, "totalEmail": 3, "openRate": 0.5,
                                                      "isBestseller": False}, "subscriber_count": 4},
        }

    def __call__(self, op, **fields):
        self.calls.append({"op": op, **fields})
        value = self.replies[op]
        if isinstance(value, BaseException):
            raise value
        if isinstance(value, dict) and "contacted" in value:
            return value
        return {"ok": True, "data": value, "fingerprint": FP, "contacted": True, "session": {"active": True}}


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    venv_python = tmp_path / "python"
    venv_python.write_text("")
    monkeypatch.setattr(sa, "STORE", store)
    monkeypatch.setattr(sa, "VENV_PYTHON", venv_python)
    monkeypatch.setattr(sa, "MIN_GAP", 0)
    monkeypatch.setattr(sa, "_config", lambda home: {})
    fake = Bridge()
    monkeypatch.setattr(sa, "bridge", fake)
    return fake


def run(args, profile="assistant"):
    return sa.execute(args, home=None, profile=profile)


# --- profiles and arguments ---------------------------------------------------------------------

def test_profiles_get_their_actions():
    assert sa.actions_for("assistant") == sa.ACTIONS
    assert sa.actions_for("marketer") == sa.READS
    assert sa.actions_for("creator") == () and sa.actions_for(None) == ()
    assert not set(sa.WRITES) & set(sa.actions_for("marketer"))
    with pytest.raises(sa.SubstackError, match="must be one of"):
        run({"action": "nope"})
    with pytest.raises(sa.SubstackError):
        run({"action": "status"}, profile="creator")


@pytest.mark.parametrize("value,host", [
    ("craftsamo", "craftsamo.substack.com"),
    ("craftsamo.substack.com", "craftsamo.substack.com"),
    ("https://craftsamo.substack.com/archive?sort=new", "craftsamo.substack.com"),
    ("https://www.craftsamo.substack.com", "craftsamo.substack.com"),
    ("https://open.substack.com/pub/lenny/p/x", "lenny.substack.com"),
    ("www.lennysnewsletter.com", "www.lennysnewsletter.com"),
    ("https://www.LennysNewsletter.com/p/x", "www.lennysnewsletter.com"),
])
def test_publication_hosts(value, host):
    assert sa.publication_host(value) == host


@pytest.mark.parametrize("value", ["", None, "@ann", "substack.com", "https://substack.com", "https://localhost/",
                                   "ftp://a.substack.com", "a b.com", "127.0.0.1", "-bad-.substack.com"])
def test_bad_publication_hosts(value):
    with pytest.raises(sa.SubstackError):
        sa.publication_host(value)


@pytest.mark.parametrize("value,ref", [
    ("218578359", {"id": "218578359"}),
    (218578359, {"id": "218578359"}),
    ("https://post.substack.com/p/slug-1", {"host": "post.substack.com", "slug": "slug-1"}),
    ("https://post.substack.com/p/slug-1?utm_source=x#c", {"host": "post.substack.com", "slug": "slug-1"}),
    ("https://www.lennysnewsletter.com/p/growth", {"host": "www.lennysnewsletter.com", "slug": "growth"}),
    ("https://open.substack.com/pub/lenny/p/growth?r=1", {"host": "lenny.substack.com", "slug": "growth"}),
    ("https://substack.com/home/post/p-218578359", {"id": "218578359"}),
    ("https://substack.com/@ann/p-218578359", {"id": "218578359"}),
    ("https://substack.com/inbox/post/218578359", {"id": "218578359"}),
])
def test_post_refs(value, ref):
    assert sa.post_ref(value) == ref


@pytest.mark.parametrize("value", [None, "", "abc", "https://post.substack.com/archive", "https://substack.com/@ann",
                                   "file:///etc/passwd", "https://127.0.0.1/p/x", True])
def test_bad_post_refs(value):
    with pytest.raises(sa.SubstackError):
        sa.post_ref(value)


def test_limits_and_offsets():
    assert sa._limit({}, "archive") == 10 and sa._limit({"limit": 500}, "archive") == 25
    assert sa._limit({"limit": 500}, "inbox") == 50
    for bad in (0, -1, "3", True):
        with pytest.raises(sa.SubstackError):
            sa._limit({"limit": bad}, "inbox")
    assert sa._offset({}) == 0 and sa._offset({"offset": 20}) == 20
    for bad in (-1, "2", sa.OFFSET_MAX + 1, False):
        with pytest.raises(sa.SubstackError):
            sa._offset({"offset": bad})


def test_config_section_is_read_from_the_profile(tmp_path, monkeypatch):
    try:
        import hermes_yaml  # noqa: F401  (Hermes' runtime loader)
    except ImportError:
        pytest.importorskip("yaml")
    monkeypatch.setattr(sa, "_config", _load("substack_access_engine_cfg", ROOT / "sa.py")._config)
    (tmp_path / "config.yaml").write_text("substack_access:\n  publication: https://craftsamo.substack.com\n",
                                          encoding="utf-8")
    assert sa.configured_publication(tmp_path) == "craftsamo.substack.com"
    assert sa.configured_publication(tmp_path / "missing") is None


# --- actions ------------------------------------------------------------------------------------

def test_status_never_reaches_substack(isolated):
    result = run({"action": "status"})
    assert result["cookies"] is True and result["engine"] is True and result["can_write"] is bool(sa.WRITES)
    assert [c["op"] for c in isolated.calls] == ["check"]
    assert run({"action": "status"}, profile="marketer")["can_write"] is False
    assert sa.usage()["last_hour"] == 0


def test_status_reports_missing_engine_and_cookies(isolated, monkeypatch, tmp_path):
    isolated.replies["check"] = {"ok": False, "kind": "setup", "error": "no Substack cookies", "contacted": False}
    result = run({"action": "status"})
    assert result["cookies"] is False and "not set up" in result["problem"]
    monkeypatch.setattr(sa, "VENV_PYTHON", tmp_path / "missing")
    result = run({"action": "status"})
    assert result["engine"] is False and "install" in result["problem"] and len(isolated.calls) == 1


def test_archive_of_own_and_other_publications(isolated):
    result = run({"action": "archive"})
    assert result["publication"] == {"name": "CraftSamo", "url": "https://craftsamo.substack.com", "role": "admin"}
    assert result["count"] == 2 and result["posts"][0]["title"] == "Title 1" and result["more"] is False
    assert isolated.calls[-1]["host"] is None
    result = run({"action": "archive", "publication": "post", "query": "  writing   tips ", "limit": 2, "offset": 4})
    call = isolated.calls[-1]
    assert (call["host"], call["query"], call["limit"], call["offset"]) == ("post.substack.com", "writing tips", 2, 4)
    assert result["more"] is True and result["query"] == "writing tips"
    shaped = result["posts"][0]
    assert shaped["author"] == "Ann" and shaped["preview"] == "Preview text" and shaped["counts"]["reactions"] == 5
    assert "body_html" not in shaped and "note" in result


def test_post_text_links_and_untrusted_note(isolated):
    result = run({"action": "post", "post": "https://post.substack.com/p/slug-3"})
    assert isolated.calls[-1] == {"op": "post", "refused": None, "host": "post.substack.com", "slug": "slug-3"}
    assert result["text"] == "## Head\n\nHello link\n\n- one" and result["links"] == ["https://e.com/x"]
    assert result["post"]["publication"] == "Post" and result["your_subscription"] == "free_signup"
    assert "paywall" not in result and "preview" not in result["post"] and result["note"] == sa.UNTRUSTED


def test_paid_post_says_where_it_ends(isolated):
    isolated.replies["post"] = {"post": item(3, audience="only_paid", wordcount=100, body_html="<p>few words only</p>")}
    result = run({"action": "post", "post": "3"})
    assert isolated.calls[-1]["id"] == "3" and "end at the paywall" in result["paywall"]
    isolated.replies["post"] = {"post": item(3, audience="only_paid", wordcount=3, body_html="<p>all three words</p>")}
    assert "appears complete" in run({"action": "post", "post": "3"})["paywall"]
    isolated.replies["post"] = {"post": item(3, body_html="")}
    result = run({"action": "post", "post": "3"})
    assert result["body"] == "preview only" and result["text"] == "Preview text"


def test_inbox_names_publications_and_trims(isolated):
    result = run({"action": "inbox", "limit": 2})
    assert result["count"] == 2 and result["more"] is True
    assert result["posts"][0]["publication"] == "Post"


def test_own_lists_drafts_and_stats(isolated):
    result = run({"action": "published"})
    assert result["total"] == 1 and result["posts"][0]["stats"] == {"views": 10, "opens": 3}
    result = run({"action": "drafts"})
    d = result["drafts"][0]
    assert d["title"] == "(untitled)" and d["edit_url"] == "https://craftsamo.substack.com/publish/post/8"
    result = run({"action": "draft", "draft": 8})
    assert isolated.calls[-1]["id"] == "8" and result["markdown"] == "# Hi" and result["draft"]["title"] == "Hi"
    with pytest.raises(sa.SubstackError, match="numeric"):
        run({"action": "draft", "draft": "x"})
    result = run({"action": "stats"})
    assert result["stats"] == {"subscribers": 4, "subscribers_counted": 4, "email_subscribers": 3, "open_rate": 0.5,
                               "bestseller": False}


def test_marketer_reads_everything_a_reader_can(isolated):
    for action in ("archive", "inbox", "published", "drafts", "stats"):
        assert run({"action": action}, profile="marketer")["ok"] is True


# --- pacing and session state -------------------------------------------------------------------

def test_calls_are_counted_and_capped(isolated, monkeypatch):
    monkeypatch.setattr(sa, "HOURLY", 2)
    run({"action": "inbox"})
    run({"action": "inbox"})
    with pytest.raises(sa.SubstackError, match="last hour"):
        run({"action": "inbox"})
    assert len(isolated.calls) == 2 and sa.usage()["last_hour"] == 2


def test_daily_cap(isolated, monkeypatch):
    now = time.time()
    sa.STORE.joinpath("state.json").write_text(json.dumps({"reads": [now - 7200 - i for i in range(sa.DAILY)]}))
    with pytest.raises(sa.SubstackError, match="24 hours"):
        run({"action": "inbox"})
    assert isolated.calls == []


def test_uncontacted_calls_are_free(isolated):
    isolated.replies["inbox"] = {"ok": False, "kind": "setup", "error": "no cookies", "contacted": False}
    with pytest.raises(sa.SubstackError, match="not set up"):
        run({"action": "inbox"})
    assert sa.usage()["last_day"] == 0


def test_a_refusal_is_remembered_by_fingerprint(isolated):
    isolated.replies["inbox"] = {"ok": False, "kind": "refused", "error": "Substack answered 401", "fingerprint": FP,
                                 "contacted": True, "session": {"active": False, "error": "Substack answered 401"}}
    with pytest.raises(sa.SubstackError, match="refused the account's session"):
        run({"action": "inbox"})
    state = json.loads(sa.STORE.joinpath("state.json").read_text())
    assert state["refused"]["fingerprint"] == FP
    isolated.replies["inbox"] = {"ok": False, "kind": "refused", "fingerprint": FP, "contacted": False}
    with pytest.raises(sa.SubstackError, match="401"):
        run({"action": "inbox"})
    assert isolated.calls[-1]["refused"] == FP
    assert "refused" in run({"action": "status"})["problem"]
    isolated.replies["inbox"] = {"posts": [], "publications": {}}
    run({"action": "inbox"})
    assert "refused" not in json.loads(sa.STORE.joinpath("state.json").read_text())


def test_a_rate_limit_pauses_until_it_ends(isolated):
    isolated.replies["inbox"] = {"ok": False, "kind": "limited", "error": "429", "retry_after": 600,
                                 "fingerprint": FP, "contacted": True}
    with pytest.raises(sa.SubstackError, match="rate-limiting"):
        run({"action": "inbox"})
    calls = len(isolated.calls)
    with pytest.raises(sa.SubstackError, match="paused"):
        run({"action": "archive"})
    assert len(isolated.calls) == calls and "rate_limited_until" in run({"action": "status"})


@pytest.mark.parametrize("kind,match", [("blocked", "Cloudflare"), ("no_publication", "no publication"),
                                        ("not_found", "not found"), ("forbidden", "refused this call"),
                                        ("timeout", "deadline")])
def test_failures_read_plainly(isolated, kind, match):
    error = {"no_publication": "the account has no publication of its own yet",
             "timeout": "Substack did not answer within the deadline"}.get(kind, "x")
    isolated.replies["inbox"] = {"ok": False, "kind": kind, "error": error, "fingerprint": FP, "contacted": True}
    with pytest.raises(sa.SubstackError, match=match):
        run({"action": "inbox"})


def test_real_bridge_passes_a_minimal_environment(monkeypatch, tmp_path):
    engine = _load("substack_access_engine_real", ROOT / "sa.py")
    monkeypatch.setattr(engine, "STORE", tmp_path)
    (tmp_path / "python").write_text("")
    monkeypatch.setattr(engine, "VENV_PYTHON", tmp_path / "python")
    seen = {}

    class Proc:
        returncode = 0
        stdout = json.dumps({"ok": True, "data": None, "contacted": False})

    def fake_run(argv, **kwargs):
        seen.update(argv=argv, **kwargs)
        return Proc()

    monkeypatch.setattr(engine.subprocess, "run", fake_run)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "leak")
    assert engine.bridge("check")["ok"] is True
    assert seen["argv"][1] == "-I" and "ANTHROPIC_API_KEY" not in seen["env"] and seen["cwd"] == str(tmp_path)
    assert json.loads(seen["input"]) == {"op": "check", "deadline": engine.BRIDGE_DEADLINE}
    Proc.stdout = "Traceback"
    with pytest.raises(engine.SubstackError, match="without a result"):
        engine.bridge("check")


# --- writes: arguments --------------------------------------------------------------------------

def test_write_plans_are_checked_and_normalized():
    assert sa.write_plan({"title": " T ", "markdown": "# x"}, "create_draft") == {
        "action": "create_draft", "title": "T", "subtitle": "", "markdown": "# x", "audience": "everyone"}
    for bad in ({"markdown": "x"}, {"title": "T"}, {"title": "T", "markdown": "x", "audience": "friends"},
                {"title": " ", "markdown": "x"}, {"title": "T" * 300, "markdown": "x"}):
        with pytest.raises(sa.SubstackError):
            sa.write_plan(bad, "create_draft")
    plan = sa.write_plan({"draft": 5, "subtitle": ""}, "update_draft")
    assert plan["subtitle"] == "" and plan["title"] is None and plan["replace_unsupported"] is False
    with pytest.raises(sa.SubstackError, match="at least one"):
        sa.write_plan({"draft": "5"}, "update_draft")
    with pytest.raises(sa.SubstackError, match="send_email"):
        sa.write_plan({"draft": "5"}, "publish")
    with pytest.raises(sa.SubstackError, match="send_email"):
        sa.write_plan({"draft": "5", "send_email": "yes"}, "publish")
    assert sa.write_plan({"draft": "5", "send_email": False}, "publish") == {"action": "publish", "draft": "5",
                                                                          "send_email": False}
    assert sa.write_plan({"text": " hi "}, "note") == {"action": "note", "text": "hi"}
    with pytest.raises(sa.SubstackError):
        sa.write_plan({"text": "x" * (sa.NOTE_MAX + 1)}, "note")


def test_schedule_times():
    from datetime import datetime, timedelta, timezone
    soon = datetime.now(timezone(timedelta(hours=9))) + timedelta(hours=2)
    plan = sa.write_plan({"draft": "5", "at": soon.isoformat(), "send_email": True}, "schedule")
    assert plan["at"].endswith("+00:00") and datetime.fromisoformat(plan["at"]) == soon.replace(microsecond=0)
    for at, match in ((soon.replace(tzinfo=None).isoformat(), "UTC offset"), ("tomorrow", "ISO 8601"),
                      ((soon - timedelta(hours=3)).isoformat(), "5 minutes"),
                      ((soon + timedelta(days=400)).isoformat(), "within a year")):
        with pytest.raises(sa.SubstackError, match=match):
            sa.write_plan({"draft": "5", "at": at, "send_email": True}, "schedule")


# --- writes: images, outbox and snapshot --------------------------------------------------------

@pytest.fixture
def images(tmp_path, monkeypatch):
    root = tmp_path / "Workspaces"
    (root / "pics").mkdir(parents=True)
    (root / "pics" / "a.png").write_bytes(b"\x89PNG one")
    (root / "pics" / "b.jpg").write_bytes(b"jpeg two")
    monkeypatch.setattr(sa, "_config", lambda home: {"attach_roots": str(root)})
    return root


def test_image_files_stay_inside_the_attach_roots(images, tmp_path):
    roots = sa.attach_roots(None)
    files = sa.image_files([str(images / "pics" / "a.png")], roots)
    assert files[0]["shown"] == "pics/a.png" and files[0]["size"] == 8
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"x")
    (images / "pics" / "notes.txt").write_text("x")
    (images / ".ssh").mkdir()
    (images / ".ssh" / "k.png").write_bytes(b"x")
    (images / "pics" / "empty.png").write_bytes(b"")
    (images / "pics" / "link.png").symlink_to(outside)
    for path, match in ((outside, "outside"), (images / "pics" / "notes.txt", "not a JPEG"),
                        (images / ".ssh" / "k.png", "credential"), (images / "pics" / "empty.png", "empty"),
                        (images / "pics" / "link.png", "outside"), (images / "nope.png", "no such image")):
        with pytest.raises(sa.SubstackError, match=match):
            sa.image_files([str(path)], roots)
    with pytest.raises(sa.SubstackError, match="at most"):
        sa.image_files([str(images / "pics" / "a.png")] * (sa.MAX_IMAGES + 1), roots)


def draft_prepared(**extra):
    return {"publication": PUB, "draft": {"id": 5, "title": "Old title", "audience": "everyone", "words": 300,
                                          "scheduled": [], "published": False}, "digest": "d1",
            "email_subscribers": 12, **extra}


def test_snapshot_is_shared_by_both_hooks_and_consumed_once(isolated, images):
    src = str(images / "pics" / "a.png")
    isolated.replies["prepare"] = {"publication": PUB, "images": [src]}
    args = {"action": "create_draft", "title": "Hello", "markdown": f"![a]({src})"}
    ids = {"tool_call_id": "c1"}
    card, key = sa.approval_request(args, ids=ids, profile="assistant")
    assert "Images (1): pics/a.png (8 B)" in card and "Nothing is published or emailed." in card
    token = sa.binding(args, ids=ids, profile="assistant")["_prepared"]
    assert [c["op"] for c in isolated.calls] == ["prepare"]
    (images / "pics" / "a.png").write_bytes(b"changed after approval")  # the copy is what goes out
    folder, manifest = sa.consume(sa.request_digest(sa.write_plan(args, "create_draft"), None), token)
    copy = Path(manifest["images"][0]["path"])
    assert copy.parent == folder and copy.read_bytes() == b"\x89PNG one" and manifest["images"][0]["src"] == src
    with pytest.raises(sa.SubstackError, match="already carried out"):
        sa.consume(manifest["request"], token)


def test_a_tampered_copy_or_another_request_is_refused(isolated, images):
    src = str(images / "pics" / "a.png")
    isolated.replies["prepare"] = {"publication": PUB, "images": [src]}
    args = {"action": "create_draft", "title": "Hello", "markdown": f"![a]({src})"}
    sa.approval_request(args, ids={"tool_call_id": "c2"}, profile="assistant")
    token = sa.binding(args, ids={"tool_call_id": "c2"}, profile="assistant")["_prepared"]
    next(p for p in (sa.STORE / "outbox" / token).iterdir() if p.suffix == ".png").write_bytes(b"evil")
    with pytest.raises(sa.SubstackError, match="changed after approval"):
        sa.consume(sa.request_digest(sa.write_plan(args, "create_draft"), None), token)
    assert not (sa.STORE / "outbox" / token).exists()
    sa.approval_request(args, ids={"tool_call_id": "c3"}, profile="assistant")
    token = sa.binding(args, ids={"tool_call_id": "c3"}, profile="assistant")["_prepared"]
    other = sa.write_plan({**args, "title": "Other"}, "create_draft")
    with pytest.raises(sa.SubstackError, match="differs"):
        sa.consume(sa.request_digest(other, None), token)
    for bad in (None, "../x", "0" * 31):
        with pytest.raises(sa.SubstackError, match="not prepared"):
            sa.consume("r", bad)


def test_a_failed_prepare_is_shared_not_repeated(isolated):
    isolated.replies["prepare"] = {"ok": False, "kind": "invalid", "error": "draft 5 is already published",
                                   "fingerprint": FP, "contacted": True}
    args = {"action": "publish", "draft": "5", "send_email": True}
    with pytest.raises(sa.SubstackError, match="already published"):
        sa.approval_request(args, ids={"tool_call_id": "c4"}, profile="assistant")
    assert sa.binding(args, ids={"tool_call_id": "c4"}, profile="assistant") is None
    assert [c["op"] for c in isolated.calls] == ["prepare"]


def test_an_expired_snapshot_is_not_rebuilt_by_bind(isolated, monkeypatch):
    isolated.replies["prepare"] = draft_prepared()
    args = {"action": "publish", "draft": "5", "send_email": True}
    sa.approval_request(args, ids={"tool_call_id": "t1"}, profile="assistant")
    later = time.time() + sa.PENDING_TTL + 1
    monkeypatch.setattr(sa.time, "time", lambda: later)
    assert sa.binding(args, ids={"tool_call_id": "t1"}, profile="assistant") is None
    assert [c["op"] for c in isolated.calls] == ["prepare"]


def test_rule_keys_bind_the_draft_and_the_image_bytes():
    plan = sa.write_plan({"draft": "5", "send_email": True}, "publish")
    one = sa.rule_key(plan, draft_prepared(), [], "r")
    assert one.startswith("substack-access:publish:") and one == sa.rule_key(plan, draft_prepared(), [], "r")
    assert one != sa.rule_key(plan, draft_prepared(digest="d2"), [], "r")
    assert one != sa.rule_key(plan, draft_prepared(), [], "r2")
    staged = [{"name": "a.png", "sha256": "x"}]
    assert sa.rule_key(plan, draft_prepared(), staged, "r") != sa.rule_key(
        plan, draft_prepared(), [{"name": "a.png", "sha256": "y"}], "r")
    other_pub = draft_prepared(publication={**PUB, "id": 8})
    other_user = draft_prepared(publication={**PUB, "user_id": 2})
    assert len({one, sa.rule_key(plan, other_pub, [], "r"), sa.rule_key(plan, other_user, [], "r")}) == 3
    note = sa.write_plan({"text": "hi"}, "note")
    assert sa.rule_key(note, {"account": {"id": 1}}, [], "r") != sa.rule_key(note, {"account": {"id": 2}}, [], "r")


# --- writes: cards ------------------------------------------------------------------------------

def test_cards_say_what_happens():
    publish = sa.card(sa.write_plan({"draft": "5", "send_email": True}, "publish"), draft_prepared(), [])
    assert publish.splitlines() == [
        "Substack: PUBLISH draft 5 in CraftSamo (craftsamo.substack.com) now; this cannot be undone",
        "Title: Old title", "Audience: everyone", "Email: sent to 12 email subscribers", "Words: 300"]
    web = sa.card(sa.write_plan({"draft": "5", "send_email": False}, "publish"), draft_prepared(), [])
    assert "Email: none (web only)" in web
    from datetime import datetime, timedelta, timezone
    at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    sched = sa.card(sa.write_plan({"draft": "5", "at": at, "send_email": True}, "schedule"), draft_prepared(), [])
    assert "SCHEDULE draft 5" in sched and "Email: sent at release to 12" in sched
    update = sa.card(sa.write_plan({"draft": "5", "title": "New", "markdown": "body",
                                    "replace_unsupported": True}, "update_draft"),
                     draft_prepared(unsupported=2), [])
    assert "Draft now: Old title" in update and "New title: New" in update and "Drops 2 block(s)" in update
    unschedule = sa.card(sa.write_plan({"draft": "5"}, "unschedule"),
                         draft_prepared(draft={"title": "", "scheduled": ["2026-10-06T00:00:00Z"]}), [])
    assert "Title: (untitled)" in unschedule and "stays an unpublished draft" in unschedule


def test_long_bodies_are_clipped_to_what_telegram_shows_and_hidden_characters_shown():
    plan = sa.write_plan({"title": "T", "markdown": "word " * 500}, "create_draft")
    text = sa.card(plan, {"publication": PUB}, [])
    assert sa._units(text) <= sa.CARD_LIMIT and "more characters)" in text
    note = sa.card(sa.write_plan({"text": "pay here\u202e"}, "note"), {"account": {"handle": "me"}}, [])
    assert "⟨U+202E⟩" in note


def test_every_fact_fits_or_the_card_is_refused():
    long = "ä" * 200
    plan = sa.write_plan({"draft": "5", "title": long, "subtitle": long, "audience": "only_paid", "markdown": "b",
                          "replace_unsupported": True}, "update_draft")
    text = sa.card(plan, draft_prepared(unsupported=1), [])
    assert sa._units(text) <= sa.CARD_LIMIT
    for fact in ("New audience: only_paid", "Drops 1 block(s)", "Nothing is published or emailed."):
        assert fact in text
    staged = [{"shown": f"very/long/folder/name/image-{i}.png", "size": 10, "name": "x", "sha256": "s"}
              for i in range(20)]
    with pytest.raises(sa.SubstackError, match="split it"):
        sa.card(plan, draft_prepared(unsupported=1, publication={**PUB, "name": "<&>" * 40}),
                staged * 3 + [{"shown": "<" * 200, "size": 1, "name": "y", "sha256": "t"}])


def test_a_card_that_cannot_be_shown_leaves_nothing_to_bind(isolated, monkeypatch):
    isolated.replies["prepare"] = draft_prepared()
    monkeypatch.setattr(sa, "card", lambda *a: (_ for _ in ()).throw(sa.SubstackError("too many changes")))
    args = {"action": "publish", "draft": "5", "send_email": True}
    with pytest.raises(sa.SubstackError, match="too many changes"):
        sa.approval_request(args, ids={"tool_call_id": "k1"}, profile="assistant")
    assert sa.binding(args, ids={"tool_call_id": "k1"}, profile="assistant") is None
    assert not list((sa.STORE / "outbox").iterdir())


# --- writes: carrying out -----------------------------------------------------------------------

def approved(isolated, args, prepared=None, call="c9"):
    isolated.replies["prepare"] = prepared or draft_prepared()
    sa.approval_request(args, ids={"tool_call_id": call}, profile="assistant")
    return {**args, **sa.binding(args, ids={"tool_call_id": call}, profile="assistant")}


def test_an_approved_publish_runs_with_the_card_draft(isolated):
    isolated.replies["write"] = {"post": {"id": 5, "url": "https://craftsamo.substack.com/p/x"}, "emailed": True}
    args = approved(isolated, {"action": "publish", "draft": "5", "send_email": True})
    result = run(args)
    call = isolated.calls[-1]
    assert call["op"] == "write" and call["expect"] == "d1" and call["deadline"] == sa.WRITE_DEADLINE
    assert (call["publication"], call["expect_publication"], call["expect_user"]) == ("craftsamo.substack.com", 7, 1)
    assert call["plan"] == {"action": "publish", "draft": "5", "send_email": True} and call["images"] == {}
    assert result["ok"] is True and result["post"]["url"].endswith("/p/x") and result["emailed"] is True
    state = json.loads(sa.STORE.joinpath("state.json").read_text())
    assert len(state["writes"]) == 1 and state["log"][-1]["outcome"] == "done"
    assert not list((sa.STORE / "outbox").iterdir())


def test_images_reach_the_bridge_as_frozen_copies(isolated, images):
    src = str(images / "pics" / "a.png")
    isolated.replies["write"] = {"draft": {"id": 77, "title": "Hello"}, "images": 1}
    args = approved(isolated, {"action": "create_draft", "title": "Hello", "markdown": f"![a]({src})"},
                    {"publication": PUB, "images": [src]})
    result = run(args)
    sent = isolated.calls[-1]["images"]
    assert list(sent) == [src] and Path(sent[src]).name.endswith(".png") and sa.STORE / "outbox" in Path(sent[src]).parents
    assert result["draft"]["edit_url"] == "https://craftsamo.substack.com/publish/post/77" and result["images"] == 1


@pytest.mark.parametrize("reply,match", [
    ({"ok": False, "kind": "changed", "error": "draft 5 changed after the approval card was shown"}, "not done: draft 5 changed"),
    ({"ok": False, "kind": "rejected", "error": "Substack refused to publish the draft (400: no)"}, "not done: Substack refused"),
    ({"ok": False, "kind": "limited", "error": "x", "retry_after": 900}, "not done: paused"),
])
def test_refused_writes_say_not_done(isolated, reply, match):
    isolated.replies["write"] = {"fingerprint": FP, "contacted": True, **reply}
    result = run(approved(isolated, {"action": "publish", "draft": "5", "send_email": False}))
    assert result["ok"] is False and result["error"].startswith(match)


@pytest.mark.parametrize("ledger,expected", [
    ({"status": "dispatching", "step": "publish the draft", "done": []}, "UNCERTAIN"),
    ({"status": "done", "step": "schedule the release", "done": ["schedule the release"]}, "accepted"),
    ({"status": "rejected", "step": "schedule the release", "done": ["set whether the release is emailed"]},
     "not done: x (already done: set whether"),
])
def test_an_error_reply_is_judged_by_the_ledger_too(isolated, monkeypatch, ledger, expected):
    from datetime import datetime, timedelta, timezone
    at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    args = approved(isolated, {"action": "schedule", "draft": "5", "at": at, "send_email": True})

    def fails(op, **fields):
        Path(fields["ledger"]).write_text(json.dumps(ledger))
        return {"ok": False, "kind": "error", "error": "x", "contacted": True}

    monkeypatch.setattr(sa, "bridge", fails)
    result = run(args)
    assert expected in (result.get("error") or result.get("note"))
    assert result["ok"] is (expected == "accepted")


def test_uncertain_writes_are_never_retried(isolated):
    isolated.replies["write"] = {"uncertain": "Substack answered 502 to 'publish the draft'",
                                 "hint": "the draft now shows as published", "done": []}
    result = run(approved(isolated, {"action": "publish", "draft": "5", "send_email": False}))
    assert result["ok"] is False and result["error"].startswith("UNCERTAIN: Substack answered 502")
    assert "the draft now shows as published" in result["error"] and "action=published" in result["error"]
    assert sum(1 for c in isolated.calls if c["op"] == "write") == 1
    assert json.loads(sa.STORE.joinpath("state.json").read_text())["log"][-1]["outcome"] == "uncertain"


@pytest.mark.parametrize("ledger,expected", [
    (None, "not done"), ({"status": "dispatching", "step": "publish the draft", "done": []}, "UNCERTAIN"),
    ({"status": "rejected", "step": "schedule the release", "done": ["set whether the release is emailed"]},
     "already done: set whether"),
    ({"status": "done", "step": "publish the draft", "done": ["publish the draft"]}, "accepted"),
    ({"status": "dispatching", "step": "upload image a.png", "done": []}, "image may have reached"),
])
def test_a_dead_engine_is_judged_by_its_ledger(isolated, monkeypatch, ledger, expected):
    args = approved(isolated, {"action": "publish", "draft": "5", "send_email": False})

    def dies(op, **fields):
        if ledger is not None:
            Path(fields["ledger"]).write_text(json.dumps(ledger))
        raise sa.SubstackError("Substack did not answer within 180s")

    monkeypatch.setattr(sa, "bridge", dies)
    result = run(args)
    assert expected in (result.get("error") or result.get("note"))
    assert json.loads(sa.STORE.joinpath("state.json").read_text())["writes"]  # it may have reached Substack


def test_the_daily_write_cap(isolated, monkeypatch):
    monkeypatch.setattr(sa, "WRITE_DAILY", 1)
    isolated.replies["write"] = {"note": {"id": 1}}
    first = approved(isolated, {"action": "note", "text": "one"}, {"account": {"handle": "me"}}, "n1")
    second = approved(isolated, {"action": "note", "text": "two"}, {"account": {"handle": "me"}}, "n2")
    assert run(first)["ok"] is True
    result = run(second)
    assert result["ok"] is False and result["error"].startswith("not done: paused") and "24 hours" in result["error"]
    with pytest.raises(sa.SubstackError, match="24 hours"):  # and no card is shown for a third
        sa.approval_request({"action": "note", "text": "three"}, ids={"tool_call_id": "n3"}, profile="assistant")


# --- text -------------------------------------------------------------------------------------

def test_html_text_keeps_structure_and_drops_scripts():
    text, links = sa.html_text("<p>A&amp;B</p><img alt='cat'><style>x{}</style><ol><li>x</li><li>y</li></ol>"
                               "<a href='https://a.com'>a</a><a href='https://a.com'>again</a><a href='/rel'>r</a>")
    assert text == "A&B\n[image: cat]\n\n- x\n- y\naagainr" and links == ["https://a.com"]


# --- guard --------------------------------------------------------------------------------------

@pytest.mark.parametrize("tool,args,blocked", [
    ("terminal", {"command": "secret get SUBSTACK_COOKIES -p hermes --scope substack-session"}, True),
    ("terminal", {"command": "cat ~/.substack-access/state.json"}, True),
    ("terminal", {"command": "hermes/local/python-substack/venv/bin/python -c 'import substack'"}, True),
    ("terminal", {"command": "substack drafts list"}, True),
    ("terminal", {"command": "cd x && substack publish 1"}, True),
    ("terminal", {"command": "substack-mcp"}, True),
    ("terminal", {"command": "curl https://craftsamo.substack.com/api/v1/drafts"}, True),
    ("terminal", {"command": "curl -b 'substack.sid=x' https://substack.com/"}, True),
    ("terminal", {"command": "python3 plugins/substack-access/bridge.py"}, True),
    ("terminal", {"command": "echo 'I read a substack post today'"}, False),
    ("terminal", {"command": "curl https://craftsamo.substack.com/feed"}, False),
    ("terminal", {"command": "ls"}, False),
    ("read_file", {"path": "~/.substack-access/state.json"}, True),
    ("search_files", {"path": "hermes/local/python-substack"}, True),
    ("read_file", {"path": "~/notes/substack-ideas.md"}, False),
    ("web_search", {"query": "SUBSTACK_COOKIES"}, False),
])
def test_bypass(tool, args, blocked):
    assert (sa.bypass(tool, args) == sa.BYPASS_MESSAGE) is blocked
