"""The real bridge: its pure parts under the test interpreter, and the process under the engine venv
with a fake ``secret`` CLI. No request reaches Substack."""

import json
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "bridge.py"
PYTHON = ROOT.parents[1] / "local" / "python-substack" / "venv" / "bin" / "python"
SID, LLI = "s%3AsEcReTsEsSiOn0123456789.AbCdEfGhIjKlMn", "lliSECRETvalue9876543210"

needs_venv = pytest.mark.skipif(not PYTHON.exists(),
                                reason="engine venv not installed (scripts/substack-access.sh install)")


def namespace():
    ns = {"__name__": "substack_bridge_test"}
    exec(compile(BRIDGE.read_text(), "bridge.py", "exec"), ns)
    return ns


# --- pure parts ---------------------------------------------------------------------------------

def test_mask_scrubs_raw_and_decoded_cookie_values():
    ns = namespace()
    ns["SECRETS"].extend([SID, ns["unquote"](SID), LLI])
    assert ns["mask"](f"bad {SID} / {ns['unquote'](SID)} / {LLI}") == "bad … / … / …"


@pytest.mark.parametrize("host,ok", [("substack.com", True), ("craftsamo.substack.com", True),
                                     ("evilsubstack.com", False), ("substack.com.evil.io", False)])
def test_is_substack(host, ok):
    assert namespace()["is_substack"](host) is ok


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost", "printer.local", "10.0.0.8"])
def test_internal_hosts_are_refused(host):
    ns = namespace()
    with pytest.raises(ns["Failure"], match="refused"):
        ns["check_public"](host)


class Response:
    def __init__(self, status=200, data=None, headers=None, text=""):
        self.status_code, self._data, self.text = status, data, text
        self.headers = {"Content-Type": "application/json", **(headers or {})}

    def json(self):
        if self._data is None:
            raise ValueError("no json")
        return self._data


class Session:
    def __init__(self, name, replies):
        self.name, self.replies, self.calls = name, replies, []

    def get(self, url, params=None, timeout=None, allow_redirects=True):
        assert allow_redirects is False
        self.calls.append(url)
        return self.replies.pop(0)


def client(ns, auth=(), anon=()):
    c = object.__new__(ns["Client"])
    c.auth, c.anon = Session("auth", list(auth)), Session("anon", list(anon))
    c.ends, c.contacted = float("inf"), False

    class Requests:
        Timeout = TimeoutError
        RequestException = OSError

    c.requests = Requests
    return c


def test_redirects_switch_sessions_by_host(monkeypatch):
    ns = namespace()
    ns["check_public"] = lambda host: None
    c = client(ns, auth=[Response(301, headers={"Location": "https://www.custom.com/api/v1/x"})],
               anon=[Response(200, data={"ok": 1})])
    assert c.get("https://pub.substack.com/api/v1/x") == {"ok": 1}
    assert c.auth.calls == ["https://pub.substack.com/api/v1/x"] and c.anon.calls == ["https://www.custom.com/api/v1/x"]
    c = client(ns, anon=[Response(302, headers={"Location": "https://substack.com/api/v1/y"})],
               auth=[Response(200, data=[1])])
    assert c.get("https://www.custom.com/api/v1/x") == [1] and c.auth.calls == ["https://substack.com/api/v1/y"]


def test_a_redirect_to_an_internal_or_plain_http_host_is_refused():
    ns = namespace()
    c = client(ns, auth=[Response(302, headers={"Location": "https://127.0.0.1/admin"})])
    with pytest.raises(ns["Failure"], match="address"):
        c.get("https://pub.substack.com/api/v1/x")
    c = client(ns, auth=[Response(302, headers={"Location": "http://pub.substack.com/x"})])
    with pytest.raises(ns["Failure"], match="scheme"):
        c.get("https://pub.substack.com/api/v1/x")


@pytest.mark.parametrize("response,kind", [
    (Response(429, headers={"Retry-After": "120"}), "limited"),
    (Response(403, headers={"cf-mitigated": "challenge", "Content-Type": "text/html"}, text="Just a moment"), "blocked"),
    (Response(503, headers={"Content-Type": "text/html"}, text="<title>Just a moment...</title>"), "blocked"),
    (Response(401, data={"error": "x"}), "forbidden"),
    (Response(404), "not_found"),
    (Response(500), "error"),
    (Response(200, headers={"Content-Type": "text/html"}, text="<html>"), "error"),
])
def test_responses_become_failure_kinds(response, kind):
    ns = namespace()
    with pytest.raises(ns["Failure"]) as caught:
        client(ns, auth=[response]).get("https://substack.com/api/v1/x")
    assert caught.value.kind == kind
    if kind == "limited":
        assert caught.value.retry_after == 120


def test_a_401_is_a_refused_session_only_when_the_profile_says_so():
    ns = namespace()
    c = client(ns, auth=[Response(401, data={"error": "Not authorized"})])
    assert ns["_forbidden_or_refused"](c, ns["Failure"]("forbidden", "x")).kind == "refused"
    c = client(ns, auth=[Response(200, data={"id": 5, "publicationUsers": []})])
    assert ns["_forbidden_or_refused"](c, ns["Failure"]("forbidden", "x")).kind == "forbidden"


def profile_reply(pubs, primary=None):
    return Response(200, data={"id": 5, "handle": "me", "primaryPublication": {"id": primary} if primary else None,
                               "publicationUsers": [{"role": "admin", "publication": p} for p in pubs]})


def test_own_publication_is_primary_or_configured():
    ns = namespace()
    a = {"id": 1, "name": "A", "subdomain": "aaa", "custom_domain": None}
    b = {"id": 2, "name": "B", "subdomain": "bbb", "custom_domain": "www.bee.com"}
    pub = ns["own_publication"](client(ns, auth=[profile_reply([a, b], primary=2)]), None)
    assert pub["api"] == "https://bbb.substack.com/api/v1" and pub["url"] == "https://www.bee.com"
    assert ns["own_publication"](client(ns, auth=[profile_reply([a, b], primary=2)]), "aaa.substack.com")["name"] == "A"
    assert ns["own_publication"](client(ns, auth=[profile_reply([a, b])]), "https://bee.com")["name"] == "B"
    with pytest.raises(ns["Failure"]) as caught:
        ns["own_publication"](client(ns, auth=[profile_reply([a])]), "zzz.substack.com")
    assert caught.value.kind == "no_publication"
    with pytest.raises(ns["Failure"]) as caught:
        ns["own_publication"](client(ns, auth=[profile_reply([])]), None)
    assert caught.value.kind == "no_publication"


def test_slim_drops_bodies_and_keeps_byline_names():
    ns = namespace()
    item = {"id": 1, "body_html": "<p>", "body_json": {}, "draft_body": "{}", "reactions": {},
            "publishedBylines": [{"name": "Ann", "handle": "ann", "bio": "long"}]}
    assert ns["slim"](item) == {"id": 1, "publishedBylines": [{"name": "Ann", "handle": "ann"}]}
    assert ns["slim"](item, keep_body=True)["body_html"] == "<p>"


def test_note_body_marks_links_and_keeps_lines():
    doc = namespace()["note_body"]("First line, see https://example.com/a.\n\n  \nSecond")
    assert doc["attrs"] == {"schemaVersion": "v1"} and len(doc["content"]) == 2
    first = doc["content"][0]["content"]
    assert first[0] == {"type": "text", "text": "First line, see "}
    assert first[1]["text"] == "https://example.com/a" and first[1]["marks"][0]["attrs"]["href"] == "https://example.com/a"
    assert first[2] == {"type": "text", "text": "."}


def test_draft_digest_follows_what_a_card_shows():
    ns = namespace()
    d = {"draft_title": "T", "draft_subtitle": "", "draft_body": "{\"type\":\"doc\"}", "audience": "everyone",
         "draft_updated_at": "1"}
    same = ns["draft_digest"]({**d, "draft_updated_at": "2"})
    assert ns["draft_digest"](d) == same
    for change in ({"draft_title": "U"}, {"draft_body": "{}"}, {"audience": "only_paid"}, {"should_send_email": True},
                   {"postSchedules": [{"trigger_at": "2026-10-07T00:00:00Z"}]}, {"is_published": True}):
        assert ns["draft_digest"]({**d, **change}) != same


def test_draft_brief_reads_schedules_and_words():
    body = json.dumps({"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "a b c"}]}]})
    brief = namespace()["draft_brief"]({"id": 5, "draft_title": "T", "draft_body": body, "is_published": False,
                                        "postSchedules": [{"trigger_at": "2026-10-06T00:00:00Z"}]})
    assert brief["words"] == 3 and brief["scheduled"] == ["2026-10-06T00:00:00Z"] and brief["published"] is False


def test_the_cookie_session_talks_only_to_substack():
    ns = namespace()
    c = object.__new__(ns["Client"])
    c.ends, c.contacted = float("inf"), False
    sent = []

    class Auth:
        def request(self, method, url, **kwargs):
            sent.append((method, url, kwargs))
            return "response"

    c.auth = Auth()
    c._guard_auth()
    assert c.auth.request("POST", "https://pub.substack.com/api/v1/drafts", json={}) == "response"
    assert sent[0][2]["allow_redirects"] is False and sent[0][2]["timeout"] > 0
    for url in ("https://evil.example/api", "http://pub.substack.com/api/v1/drafts"):
        with pytest.raises(ns["Failure"], match="only talks to Substack"):
            c.auth.request("GET", url)
    assert len(sent) == 1


VENV_CHECKS = r"""
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, ROOT)
import bridge
from substack import Api
from substack.exceptions import SubstackAPIException

tmp = Path(tempfile.mkdtemp())
img = tmp / "a b.png"
img.write_bytes(b"png")
found = bridge.scan_images(f"# T\n\n![x](<{img}>)\n\n![r](https://cdn.example/r.png)\n\n![x again](<{img}>)\n")
assert found == [str(img)], found
try:
    bridge.scan_images("![x](/no/such/file.png)")
    raise AssertionError("missing image accepted")
except bridge.Failure as exc:
    assert exc.kind == "invalid" and "absolute paths" in exc.error

ledger = bridge.Ledger(str(tmp / "ledger.json"))
class Requests:
    class RequestException(Exception): pass
class C: requests = Requests
def outcome(call):
    try:
        return bridge.dispatch(C, ledger, "step", call)
    except bridge.Failure as exc:
        return exc.kind
    except bridge.Uncertain:
        return "uncertain"
def raises(exc):
    def call():
        raise exc
    return call
assert outcome(lambda: {"id": 1}) == {"id": 1} and json.loads((tmp / "ledger.json").read_text())["status"] == "done"
assert outcome(raises(SubstackAPIException(400, '{"error": "bad"}'))) == "rejected"
assert json.loads((tmp / "ledger.json").read_text())["status"] == "rejected"
assert outcome(raises(SubstackAPIException(429, "{}"))) == "limited"
assert outcome(raises(SubstackAPIException(502, "<html>"))) == "uncertain"
assert json.loads((tmp / "ledger.json").read_text())["status"] == "dispatching"
assert outcome(raises(bridge.Failure("timeout", "late"))) == "timeout"  # the guarded session stopped before sending
assert outcome(raises(Requests.RequestException())) == "uncertain"
assert outcome(raises(AttributeError("'list' object has no attribute 'get'"))) == "uncertain"

uploads = []
Api.get_image = lambda self, path: uploads.append(path) or {"url": "https://substackcdn.com/x.png"}
api = object.__new__(Api)
bridge._guard_uploads(C, api, {str(img): str(tmp / "00.png")}, ledger)
assert api.get_image(str(img))["url"].startswith("https://") and uploads == [str(tmp / "00.png")]
assert ledger.done[-1] == "upload image a b.png"
try:
    api.get_image(str(tmp / "other.png"))
    raise AssertionError("unapproved image uploaded")
except bridge.Failure as exc:
    assert "not on the approval card" in exc.error

class Fake:
    requests = Requests
    def __init__(self, draft): self.draft, self.auth = draft, None
    def get(self, url, params=None):
        if url.endswith("/user/profile/self"):
            return {"id": 1, "primaryPublication": {"id": 7}, "publicationUsers": [
                {"role": "admin", "publication": {"id": 7, "name": "P", "subdomain": "pub"}}]}
        return self.draft
body = json.dumps({"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "hi"}]}]})
draft = {"id": 5, "draft_title": "T", "draft_body": body, "audience": "everyone", "is_published": False}
WHO = {"expect_publication": 7, "expect_user": 1}
for who in ({"expect_publication": 8, "expect_user": 1}, {"expect_publication": 7, "expect_user": 2}):
    try:
        bridge.op_write(Fake(draft), {"action": "publish", "expect": bridge.draft_digest(draft), **who,
                        "plan": {"action": "publish", "draft": "5", "send_email": False}})
        raise AssertionError("another publication or account written")
    except bridge.Failure as exc:
        assert exc.kind == "changed" and "approval card named" in exc.error
try:
    bridge.op_write(Fake(draft), {"action": "note", "expect_user": 2, "plan": {"action": "note", "text": "x"}})
    raise AssertionError("note from another account")
except bridge.Failure as exc:
    assert exc.kind == "changed"
try:
    bridge.op_write(Fake(draft), {"action": "publish", "plan": {"action": "publish", "draft": "5", "send_email": False},
                                  "expect": "stale", **WHO})
    raise AssertionError("changed draft published")
except bridge.Failure as exc:
    assert exc.kind == "changed", exc.kind
try:
    published = {**draft, "is_published": True}
    bridge.op_write(Fake(published), {"action": "publish", "expect": bridge.draft_digest(published), **WHO,
                    "plan": {"action": "publish", "draft": "5", "send_email": False}})
    raise AssertionError("published twice")
except bridge.Failure as exc:
    assert exc.kind == "invalid" and "already published" in exc.error
class Lost(Exception):
    pass
Requests.RequestException = Lost
def lost(self, path):
    raise Lost("connection reset")
Api.get_image = lost
posts = []
Api.post_draft = lambda self, body: posts.append(body) or {"id": 1}
upload_ledger = tmp / "upload-ledger.json"
try:
    bridge.op_write(Fake(draft), {"action": "create_draft", **WHO, "ledger": str(upload_ledger),
                                  "images": {str(img): str(tmp / "00.png")},
                                  "plan": {"action": "create_draft", "title": "T", "subtitle": "", "audience": "everyone",
                                           "markdown": f"![x](<{img}>)"}})
    raise AssertionError("a lost upload went on to save a draft")
except bridge.Failure as exc:
    assert exc.kind == "invalid", exc.kind
state = json.loads(upload_ledger.read_text())
assert state["status"] == "dispatching" and state["step"] == "upload image a b.png" and posts == [], (state, posts)
empty = {**draft, "draft_title": ""}
try:
    bridge.op_write(Fake(empty), {"action": "publish", "expect": bridge.draft_digest(empty), **WHO,
                    "plan": {"action": "publish", "draft": "5", "send_email": False}})
    raise AssertionError("untitled draft published")
except bridge.Failure as exc:
    assert exc.kind == "invalid" and "no title" in exc.error
print("ok")
"""


@needs_venv
def test_write_steps_under_the_engine(tmp_path):
    script = tmp_path / "checks.py"
    script.write_text(f"ROOT = {str(ROOT)!r}\n" + VENV_CHECKS)
    proc = subprocess.run([str(PYTHON), str(script)], capture_output=True, text=True,
                          env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}, cwd=tmp_path, timeout=60)
    assert proc.stdout.strip().splitlines()[-1:] == ["ok"], proc.stdout + proc.stderr


# --- the process ----------------------------------------------------------------------------------

@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    (h / ".config" / "bin").mkdir(parents=True)
    return h


def fake_secret(home: Path, value: str | None):
    script = home / ".config" / "bin" / "secret"
    body = f"printf '%s\\n' '{value}'" if value is not None else "exit 1"
    script.write_text("#!/bin/sh\n[ \"$*\" = 'get SUBSTACK_COOKIES -p hermes --scope substack-session' ] || exit 9\n"
                      f"{body}\n")
    script.chmod(0o755)


def run(home: Path, cwd: Path, **request):
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}
    proc = subprocess.run([str(PYTHON), "-I", str(BRIDGE)], input=json.dumps(request), capture_output=True,
                          text=True, env=env, cwd=cwd, timeout=60)
    for secret in (SID, LLI, "sEcReTsEsSiOn0123456789"):
        assert secret not in proc.stdout + proc.stderr
    return json.loads(proc.stdout)


@needs_venv
def test_check_reads_the_keychain_but_not_substack(home, tmp_path):
    fake_secret(home, f"substack.sid={SID}; substack.lli={LLI}")
    reply = run(home, tmp_path, op="check")
    assert reply["ok"] is True and reply["contacted"] is False and len(reply["fingerprint"]) == 12


@needs_venv
def test_a_refused_fingerprint_short_circuits(home, tmp_path):
    fake_secret(home, f"substack.sid={SID}")
    fingerprint = run(home, tmp_path, op="check")["fingerprint"]
    reply = run(home, tmp_path, op="inbox", limit=1, refused=fingerprint)
    assert reply == {"ok": False, "kind": "refused", "fingerprint": fingerprint, "contacted": False}


@needs_venv
@pytest.mark.parametrize("value,match", [(None, "no Substack cookies in the Keychain"),
                                         (f"substack.lli={LLI}", "must hold substack.sid")])
def test_missing_or_partial_cookies_are_setup_errors(home, tmp_path, value, match):
    fake_secret(home, value)
    reply = run(home, tmp_path, op="inbox", limit=1)
    assert reply["kind"] == "setup" and match in reply["error"] and reply["contacted"] is False


@needs_venv
def test_cookies_are_bound_to_substack_only(home, tmp_path):
    """The cookie jar sends the session to substack.com and its subdomains, never to another host,
    and the cookieless session carries none."""
    fake_secret(home, f"substack.sid={SID}; substack.lli={LLI}")
    script = tmp_path / "probe.py"
    script.write_text(f"""
import json, sys
import requests
sys.path.insert(0, {str(ROOT)!r})
import bridge
cookies, _ = bridge.read_cookies()
c = bridge.Client(cookies, 30)
def sent(session, url):
    return bool(session.prepare_request(requests.Request('GET', url)).headers.get('Cookie'))
print(json.dumps([sent(c.auth, 'https://substack.com/api/v1/x'), sent(c.auth, 'https://pub.substack.com/api/v1/x'),
                  sent(c.auth, 'https://www.custom.com/api/v1/x'), sent(c.auth, 'https://substack.com.evil.io/'),
                  sent(c.anon, 'https://substack.com/api/v1/x')]))
""")
    proc = subprocess.run([str(PYTHON), str(script)], capture_output=True, text=True,
                          env={"HOME": str(home), "PATH": "/usr/bin:/bin"}, cwd=tmp_path, timeout=60)
    assert json.loads(proc.stdout.strip().splitlines()[-1]) == [True, True, False, False, False]
