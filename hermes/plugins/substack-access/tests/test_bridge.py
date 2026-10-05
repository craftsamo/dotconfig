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
