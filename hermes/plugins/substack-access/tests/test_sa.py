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
                                        ("not_found", "not found"), ("forbidden", "refused this read"),
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
