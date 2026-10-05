import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("note_access_bridge_test", ROOT / "bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

VALUE = "0123456789abcdef0123456789abcdef"


def fake_secret(path: Path, value: str | None = f"_note_session_v5={VALUE}") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = f"#!/bin/sh\necho '{value}'\n" if value is not None else "#!/bin/sh\nexit 1\n"
    path.write_text(body)
    path.chmod(0o700)
    return path


class Reply(io.BytesIO):
    def __init__(self, status, payload):
        super().__init__(json.dumps(payload).encode())
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def net(tmp_path, monkeypatch):
    """note.com as a table of path -> (status, JSON); records each request."""
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path / "secret"))
    monkeypatch.setattr(bridge, "OUTBOX", tmp_path / "outbox")
    bridge.SECRETS.clear()
    routes, sent = {}, []

    def open_(request, timeout):
        sent.append(request)
        path = request.full_url[len(bridge.BASE):].split("?")[0]
        status, payload = routes.get(path, (404, {"error": "nope"}))
        if status >= 400:
            raise urllib.error.HTTPError(request.full_url, status, "x", {}, io.BytesIO(json.dumps(payload).encode()))
        return Reply(status, payload)
    monkeypatch.setattr(bridge._OPENER, "open", open_)
    routes["/api/v2/current_user"] = (200, {"data": {"id": 7, "urlname": "writer", "nickname": "W",
                                                     "email": "me@example.com", "profile": "p"}})
    return routes, sent


def run(req):
    return bridge.main({"deadline": 30, **req})


def test_the_cookie_comes_from_the_keychain_scope_and_is_masked(tmp_path, monkeypatch):
    secret = fake_secret(tmp_path / "secret")
    calls = tmp_path / "args"
    secret.write_text(f"#!/bin/sh\necho \"$@\" > {calls}\necho '_note_session_v5={VALUE}'\n")
    monkeypatch.setattr(bridge, "SECRET", secret)
    header, fingerprint = bridge.read_cookie()
    assert header == f"_note_session_v5={VALUE}" and len(fingerprint) == 12
    assert calls.read_text().split() == ["get", "NOTE_SESSION", "-p", "hermes", "--scope", "note-session"]
    assert bridge.mask(f"x {VALUE} y") == "x … y"


@pytest.mark.parametrize("value, message", [(None, "no note session"), ("not a cookie!", "not a _note_session_v5")])
def test_a_missing_or_malformed_cookie_is_a_setup_problem(tmp_path, monkeypatch, value, message):
    monkeypatch.setattr(bridge, "SECRET", fake_secret(tmp_path / "secret", value))
    reply = run({"op": "me"})
    assert reply["ok"] is False and reply["kind"] == "setup" and message in reply["error"] and reply["requests"] == 0


def test_check_reads_the_cookie_but_never_note(net):
    routes, sent = net
    reply = run({"op": "check"})
    assert reply["ok"] is True and reply["requests"] == 0 and not sent


def test_me_drops_the_email_address(net):
    reply = run({"op": "me"})
    assert reply["data"] == {"id": 7, "urlname": "writer", "nickname": "W"}
    assert "example.com" not in json.dumps(reply)


def test_drafts_ask_who_is_signed_in_first(net):
    routes, sent = net
    routes["/api/v2/note_list/contents"] = (200, {"data": {"notes": [], "isLastPage": True}})
    reply = run({"op": "drafts", "page": 2, "limit": 5})
    assert reply["ok"] is True and reply["requests"] == 2 and reply["data"]["me"]["urlname"] == "writer"
    assert sent[1].full_url.endswith("?limit=5&page=2&status=draft&without_magazines=true")
    assert sent[0].get_header("Cookie") == f"_note_session_v5={VALUE}"


def test_a_401_is_a_refusal(net):
    routes, _ = net
    routes["/api/v2/current_user"] = (401, {"data": "認証に失敗しました"})
    reply = run({"op": "drafts"})
    assert reply["ok"] is False and reply["kind"] == "refused" and reply["requests"] == 1


def test_an_auth_error_in_a_200_is_a_refusal(net):
    routes, _ = net
    routes["/api/v1/stats/pv"] = (200, {"error": {"code": "auth", "message": "not_login"}})
    assert run({"op": "stats"})["kind"] == "refused"


def test_a_remembered_refusal_is_answered_without_note(net):
    _, sent = net
    fingerprint = run({"op": "check"})["fingerprint"]
    reply = run({"op": "me", "refused": fingerprint})
    assert reply["kind"] == "refused" and reply["requests"] == 0 and not sent


def test_an_error_inside_a_2xx_is_a_failure(net):
    routes, _ = net
    routes["/api/v1/text_notes"] = (201, {"error": {"code": "invalid", "message": "だめです"}})
    reply = run({"op": "create", "title": "T"})
    assert reply["ok"] is False and reply["kind"] == "rejected" and "だめです" in reply["error"]


def test_writes_carry_the_editor_origin_and_only_known_fields(net):
    routes, sent = net
    routes["/api/v1/text_notes/draft_save"] = (201, {"data": {"result": True, "updated_at": "t"}})
    reply = run({"op": "save", "id": 5, "title": "T", "body": "<p>x</p>", "length": 1})
    assert reply["ok"] is True
    request = sent[0]
    assert request.full_url.endswith("/api/v1/text_notes/draft_save?id=5&is_temp_saved=true")
    assert request.get_header("Origin") == "https://editor.note.com"
    assert json.loads(request.data) == {"name": "T", "body": "<p>x</p>", "body_length": 1, "index": False,
                                        "is_lead_form": False}


def test_an_unconfirmed_save_is_uncertain(net):
    routes, _ = net
    routes["/api/v1/text_notes/draft_save"] = (201, {"data": {"result": False}})
    assert run({"op": "save", "id": 5, "title": "T", "body": "", "length": 0})["kind"] == "uncertain"


@pytest.mark.parametrize("req", [
    {"op": "draft", "key": "../current_user"},
    {"op": "save", "id": "5", "title": "T", "body": "x"},
    {"op": "presign", "filename": "../../x.png"},
    {"op": "stats", "period": "forever"},
    {"op": "publish"},
])
def test_arguments_are_checked_before_any_request(net, req):
    _, sent = net
    reply = run(req)
    assert reply["ok"] is False and not sent


def test_the_cover_must_be_a_staged_copy(net, tmp_path):
    routes, sent = net
    routes["/api/v1/image_upload/note_eyecatch"] = (201, {"data": {"url": "https://assets.st-note.com/c.png"}})
    outside = tmp_path / "x.png"
    outside.write_bytes(b"\x89PNG")
    assert "staged copy" in run({"op": "eyecatch", "id": 5, "path": str(outside), "mime": "image/png"})["error"]
    staged = tmp_path / "outbox" / "abc" / "00.png"
    staged.parent.mkdir(parents=True)
    staged.write_bytes(b"\x89PNGdata")
    reply = run({"op": "eyecatch", "id": 5, "path": str(staged), "mime": "image/png"})
    assert reply["ok"] is True and reply["data"]["url"].endswith("c.png")
    body = sent[-1].data
    for field in (b'name="note_id"\r\n\r\n5', b'name="width"\r\n\r\n1280', b'name="height"\r\n\r\n670',
                  b'filename="cover.png"\r\nContent-Type: image/png\r\n\r\n\x89PNGdata'):
        assert field in body


def test_a_redirect_is_not_followed(tmp_path, monkeypatch):
    with pytest.raises(bridge.Failure, match="redirect"):
        bridge._NoteOnly().redirect_request(None, None, 302, "Found", {}, "https://evil.example/")


def test_the_bridge_process_answers_one_json_line(tmp_path):
    home = tmp_path / "home"
    fake_secret(home / ".config" / "bin" / "secret")
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8"}
    proc = subprocess.run([sys.executable, "-I", str(ROOT / "bridge.py")], input=json.dumps({"op": "check"}),
                          capture_output=True, text=True, env=env, timeout=30)
    reply = json.loads(proc.stdout)
    assert reply["ok"] is True and reply["requests"] == 0 and VALUE not in proc.stdout + proc.stderr
    os.remove(home / ".config" / "bin" / "secret")
    proc = subprocess.run([sys.executable, "-I", str(ROOT / "bridge.py")], input="[]", capture_output=True,
                          text=True, env=env, timeout=30)
    assert json.loads(proc.stdout)["ok"] is False


def test_errors_lose_the_cookie_and_e_mail_addresses_before_they_are_clipped(net):
    routes, _ = net
    long_reflection = "x" * 250 + VALUE + " for someone@example.co.jp"
    routes["/api/v1/text_notes"] = (500, {"message": long_reflection})
    reply = run({"op": "create", "title": "T"})
    assert VALUE not in json.dumps(reply) and "example.co.jp" not in json.dumps(reply)
    routes["/api/v2/current_user"] = (401, {"message": VALUE[:20] + " owner a.b@c.example"})
    reply = run({"op": "me"})
    assert reply["kind"] == "refused" and "c.example" not in reply["error"]


def test_a_session_change_after_the_card_sends_nothing(net):
    _, sent = net
    reply = run({"op": "save", "id": 5, "title": "T", "body": "", "length": 0, "expect": "000000000000"})
    assert reply["kind"] == "account" and reply["requests"] == 0 and not sent


def test_a_broken_or_unreadable_answer_to_a_write_is_not_a_rejection(net, monkeypatch):
    routes, sent = net
    import http.client

    def broken(request, timeout):
        sent.append(request)
        raise http.client.IncompleteRead(b"partial")
    monkeypatch.setattr(bridge._OPENER, "open", broken)
    reply = run({"op": "save", "id": 5, "title": "T", "body": "", "length": 0})
    assert reply["kind"] == "network" and reply["requests"] == 1


def test_a_2xx_without_json_is_uncertain(net, monkeypatch):
    _, sent = net

    class Raw(Reply):
        def __init__(self):
            io.BytesIO.__init__(self, b"<html>oops</html>")
            self.status = 200
    monkeypatch.setattr(bridge._OPENER, "open", lambda request, timeout: sent.append(request) or Raw())
    assert run({"op": "save", "id": 5, "title": "T", "body": "", "length": 0})["kind"] == "uncertain"


def test_requests_inside_one_operation_keep_the_gap(net, monkeypatch):
    routes, _ = net
    routes["/api/v2/note_list/contents"] = (200, {"data": {"notes": []}})
    slept = []
    monkeypatch.setattr(bridge.time, "sleep", slept.append)
    assert run({"op": "drafts", "gap": 2})["ok"] is True
    assert len(slept) == 1 and 0 < slept[0] <= 2


def test_draft_content_with_addresses_round_trips_through_the_bridge_output(net, tmp_path, capsys, monkeypatch):
    routes, _ = net
    body = ('<p name="u" id="u">Contact editor@example.com or '
            '<a href="mailto:editor@example.com" target="_blank" rel="nofollow noopener">mail</a></p>')
    routes["/api/v3/notes/n0123456789ab"] = (200, {"data": {"is_my_note": True, "user": {"email": "me@x.example"},
                                                            "note_draft": {"body": body}}})
    request = json.dumps({"op": "draft", "key": "n0123456789ab", "deadline": 30})
    monkeypatch.setattr(sys, "stdin", io.StringIO(request))
    source = (ROOT / "bridge.py").read_text(encoding="utf-8")
    entry = source[source.index('if __name__ == "__main__":'):]
    exec(compile(entry.replace('if __name__ == "__main__":', "if True:"), "bridge-entry", "exec"), vars(bridge))
    reply = json.loads(capsys.readouterr().out)
    assert reply["data"]["note_draft"]["body"] == body          # content untouched
    assert "email" not in reply["data"]["user"]                   # the account's address field is gone
