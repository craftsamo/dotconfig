"""File sends: the checks, the snapshot shared by the approval and bind hooks, one message per file."""

import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import tarfile
import zipfile
import zlib

import pytest

TESTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("whatsapp_access_wa_tests_for_files", TESTS / "test_wa.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
wa, Fake, DM, GROUP = base.wa, base.Fake, base.DM, base.GROUP


def _png(seed=b"\x00") -> bytes:
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00" + seed)) + chunk(b"IEND", b""))


PNG, PNG2 = _png(), _png(b"\x01")
IDS = {"session_id": "s", "task_id": "t", "tool_call_id": "call-1"}


@pytest.fixture
def ws(tmp_path, monkeypatch):
    workspace = tmp_path / "Workspaces"
    workspace.mkdir()
    monkeypatch.setattr(wa, "SEND_ROOT", workspace)
    monkeypatch.setenv(wa.STATE_ENV, str(tmp_path / "state"))
    wa._PENDING.clear()
    return workspace


@pytest.fixture
def fake(monkeypatch):
    f = Fake()
    monkeypatch.setattr(wa, "run", f)
    return f


def put(ws, relative, data=PNG):
    path = ws / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def approved(args, ids=IDS):
    """Both hooks, as Hermes runs them; returns (card, rule key, the args the handler gets)."""
    card, key = wa.approval_request(args, ids=ids)
    binding = wa.outbox_binding(args, ids=ids)
    return card, key, {**args, **(binding or {})}


def send_args(**over):
    args = {"action": "send", "account": "work", "chat": DM, "files": ["trip/a.png"]}
    args.update(over)
    return args


def test_card_lists_every_file_and_the_caption(ws, fake):
    put(ws, "trip/a.png")
    put(ws, "b.png", PNG2)
    card, key, _ = approved(send_args(text="旅行の写真です", files=["trip/a.png", "b.png"]))
    assert "Files: 2 (" in card and "one message each; the text is the first one's caption" in card
    assert "- a.png (image/png, " in card and " in trip, sha256 " in card
    assert "- b.png (image/png, " in card and " in ~/Workspaces, sha256 " in card
    assert card.endswith("\n\n旅行の写真です") and key.startswith("whatsapp-access:send:")
    card, _, _ = approved(send_args(), ids={**IDS, "tool_call_id": "call-2"})
    assert card.endswith("\n\n(no caption)")


def test_one_message_per_file_caption_and_reply_on_the_first(ws, fake):
    put(ws, "trip/a.png")
    put(ws, "b.png", PNG2)
    _, _, args = approved(send_args(text="見てください", files=["trip/a.png", "b.png"], reply_to="3EB0ABCDEF"))
    result = wa.execute(args)
    assert result["ok"] is True and [f["status"] for f in result["files"]] == ["sent", "sent"]
    calls = fake.args_of(["send", "file"])
    first, second = calls[0]["args"], calls[1]["args"]
    assert first[first.index("--caption") + 1] == "見てください" and "--caption" not in second
    assert first[first.index("--reply-to") + 1] == "3EB0ABCDEF" and "--reply-to" not in second
    assert first[first.index("--filename") + 1] == "a.png" and second[second.index("--filename") + 1] == "b.png"
    assert [c["bytes"] for c in calls] == [PNG, PNG2]
    assert all(c["media_roots"] == wa.outbox() and c["write"] for c in calls)
    assert all(Path(c["args"][c["args"].index("--file") + 1]).is_relative_to(wa.outbox()) for c in calls)
    assert list(wa.outbox().iterdir()) == []                                  # copies are gone


def test_only_the_approved_bytes_go_out(ws, fake):
    path = put(ws, "trip/a.png")
    _, _, args = approved(send_args())
    path.write_bytes(PNG2)                                                     # changed after the card
    result = wa.execute(args)
    assert result["ok"] is True and fake.args_of(["send", "file"])[0]["bytes"] == PNG


def test_the_snapshot_is_used_once_and_only_through_the_hooks(ws, fake):
    put(ws, "trip/a.png")
    assert "not sent" in wa.execute(send_args())["error"]                     # no hooks, no snapshot
    _, _, args = approved(send_args())
    assert wa.execute(args)["ok"] is True
    again = wa.execute(args)
    assert again["ok"] is False and "already sent" in again["error"]
    with pytest.raises(wa.WhatsAppError, match="_outbox"):
        wa.approval_request({**send_args(), "_outbox": "0" * 32}, ids=IDS)
    with pytest.raises(wa.WhatsAppError, match="tool call id"):
        wa.approval_request(send_args(), ids={"tool_call_id": ""})


def test_a_changed_request_cannot_use_the_snapshot(ws, fake):
    put(ws, "trip/a.png")
    _, _, args = approved(send_args(text="one"))
    result = wa.execute({**args, "text": "two"})
    assert result["ok"] is False and "differ from what was approved" in result["error"]
    assert fake.args_of(["send", "file"]) == []


def test_concurrent_identical_calls_keep_their_own_snapshot(ws, fake):
    path = put(ws, "trip/a.png")
    _, key_a, args_a = approved(send_args(), ids={**IDS, "tool_call_id": "A"})
    path.write_bytes(PNG2)
    _, key_b, args_b = approved(send_args(), ids={**IDS, "tool_call_id": "B"})
    assert key_a != key_b and args_a["_outbox"] != args_b["_outbox"]
    wa.execute(args_a)
    assert fake.args_of(["send", "file"])[0]["bytes"] == PNG


def test_files_outside_the_workspace_are_refused(ws, fake, tmp_path):
    outside = tmp_path / "secret.png"
    outside.write_bytes(PNG)
    os.symlink(outside, ws / "link.png")
    for given in (str(outside), "link.png", "../secret.png"):
        with pytest.raises(wa.WhatsAppError, match="outside"):
            wa.approval_request(send_args(files=[given]), ids=IDS)


@pytest.mark.parametrize("relative, data, message", [
    (".ssh/notes.png", PNG, "keys or settings"),
    ("proj/.env", b"A=1", "keys or settings"),
    ("proj/server.pem", b"x", "keys or settings"),
    ("proj/credentials-backup.json", b"{}", "keys or settings"),
    ("proj/run.sh", b"\x00\x01\x02\x03binary" * 20, "archive or program"),   # not a script, whatever the name
    ("proj/tool.command", b"#!/bin/sh\necho hi\n", "archive or program"),
    ("proj/Tool.app", b"x", "archive or program"),
    ("proj/photo.jpg", b"PK\x03\x04" + b"\x00" * 64, "archive or program"),
    ("proj/late.txt", b"a" * 1_500_000 + b"-----BEGIN RSA PRIVATE KEY-----\nabc", "private key"),
    ("proj/empty.png", b"", "empty"),
])
def test_dangerous_files_are_refused(ws, fake, relative, data, message):
    put(ws, relative, data)
    with pytest.raises(wa.WhatsAppError, match=message):
        wa.approval_request(send_args(files=[relative]), ids=IDS)
    assert list(wa.outbox().iterdir()) == []                                  # nothing left behind


def make_zip(ws, relative, entries):
    path = ws / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return path


def test_zip_is_inspected_shown_on_the_card_and_sent(ws, fake):
    make_zip(ws, "trip/photos.zip", {"a.png": PNG, "notes/b.txt": b"hello"})
    card, _, args = approved(send_args(files=["trip/photos.zip"]))
    assert "- photos.zip (application/zip, " in card and ", 2 files inside (" in card and "unpacked)" in card
    result = wa.execute(args)
    assert result["ok"] is True and [f["file"] for f in result["files"]] == ["photos.zip"]
    call = fake.args_of(["send", "file"])[0]
    assert call["args"][call["args"].index("--filename") + 1] == "photos.zip"
    assert list(wa.outbox().iterdir()) == []


def test_tar_gz_is_sent(ws, fake):
    path = ws / "backup.tar.gz"
    with tarfile.open(path, "w:gz") as t:
        info = tarfile.TarInfo("a.png")
        info.size = len(PNG)
        t.addfile(info, io.BytesIO(PNG))
    card, _, args = approved(send_args(files=["backup.tar.gz"]))
    assert "backup.tar.gz (application/gzip" in card and ", 1 files inside (" in card
    assert wa.execute(args)["ok"] is True


@pytest.mark.parametrize("entries, message", [
    ({"a.png": PNG, ".env": b"A=1"}, "named like a key or secret"),
    ({"a.png": PNG, "proj/.ssh/id": b"x"}, "keys or settings"),
    ({"a.png": PNG, "setup.exe": b"x"}, "an archive or a program"),
    ({"a.png": PNG, "inner.zip": b"x"}, "an archive or a program"),
    ({"a.png": PNG, "../evil.txt": b"x"}, "not a plain relative path"),
    ({"a.png": PNG, "n.txt": b"-----BEGIN RSA PRIVATE KEY-----\nabc"}, "contains a private key"),
])
def test_zip_with_something_that_would_be_refused_alone_is_refused(ws, fake, entries, message):
    make_zip(ws, "bad.zip", entries)
    with pytest.raises(wa.WhatsAppError, match=f"archive 'bad.zip' is not sent: .*{message}"):
        wa.approval_request(send_args(files=["bad.zip"]), ids=IDS)
    assert list(wa.outbox().iterdir()) == [] and fake.args_of(["send", "file"]) == []


def test_scripts_are_sent_alone_and_inside_an_archive(ws, fake):
    make_zip(ws, "proj.zip", {"a.png": PNG, "run.sh": b"echo hi\n", "src/tool.py": b"print(1)\n"})
    card, _, args = approved(send_args(files=["proj.zip"]))
    assert ", 3 files inside (" in card and wa.execute(args)["ok"] is True
    for i, (name, body) in enumerate((("run.sh", b"#!/bin/sh\necho hi\n"), ("tool.py", b"print('hi')\n"),
                                      ("app.js", b"let a = 1;\n"), ("notes.txt", b"#!/bin/sh\necho hi\n"))):
        put(ws, name, body)
        card, _, args = approved(send_args(files=[name]), ids={**IDS, "tool_call_id": f"call-s{i}"})
        assert f"- {name} (" in card and wa.execute(args)["ok"] is True, name


@pytest.mark.parametrize("name, data", [
    ("tool.jar", b"PK\x03\x04" + b"\x00" * 64),
    ("app.apk", b"PK\x03\x04" + b"\x00" * 64),
    ("data.rar", b"Rar!\x1a\x07\x00" + b"\x00" * 64),
    ("data.7z", b"7z\xbc\xaf\x27\x1c" + b"\x00" * 64),
    ("data.gz", b"\x1f\x8b\x08\x00" + b"\x00" * 64),
    ("photo.jpg", b"PK\x03\x04" + b"\x00" * 64),
    ("really.zip", b"not an archive at all"),
])
def test_archives_the_inspection_does_not_cover_stay_refused(ws, fake, name, data):
    put(ws, name, data)
    with pytest.raises(wa.WhatsAppError, match="archive"):
        wa.approval_request(send_args(files=[name]), ids=IDS)
    assert list(wa.outbox().iterdir()) == []


def test_zip_changed_after_the_card_goes_out_as_approved(ws, fake):
    path = make_zip(ws, "a.zip", {"a.png": PNG})
    original = path.read_bytes()
    _, _, args = approved(send_args(files=["a.zip"]))
    make_zip(ws, "a.zip", {"a.png": PNG, "b.png": PNG2})
    assert wa.execute(args)["ok"] is True and fake.args_of(["send", "file"])[0]["bytes"] == original


def test_limits(ws, fake, monkeypatch):
    names = [f"f{i}.png" for i in range(11)]
    for name in names:
        put(ws, name)
    with pytest.raises(wa.WhatsAppError, match="at most 10"):
        wa.approval_request(send_args(files=names), ids=IDS)
    with pytest.raises(wa.WhatsAppError, match="twice"):
        wa.approval_request(send_args(files=["f0.png", "./f0.png"]), ids=IDS)
    with pytest.raises(wa.WhatsAppError, match="caption takes at most 1024"):
        wa.approval_request(send_args(files=["f0.png"], text="あ" * 1025), ids=IDS)
    monkeypatch.setattr(wa, "FILES_BYTES_MAX", len(PNG) + 1)
    with pytest.raises(wa.WhatsAppError, match="per send"):
        wa.approval_request(send_args(files=names[:2]), ids=IDS)


def test_too_many_files_for_one_card(ws, fake):
    names = [f"some/deeper/folder/a-rather-long-file-name-number-{i}.png" for i in range(8)]
    for name in names:
        put(ws, name)
    with pytest.raises(wa.WhatsAppError, match="fewer files"):
        wa.approval_request(send_args(files=names, text="hi"), ids=IDS)


def test_a_failure_stops_the_sequence_and_says_what_went_out(ws, fake):
    for name in ("a.png", "b.png", "c.png"):
        put(ws, name)
    real = fake.overrides

    def second_fails(args):
        if len(fake.args_of(["send", "file"])) == 2:
            raise wa.WhatsAppError("file too large (1 bytes); maximum size is 104857600 bytes", reported=True)
        return {"sent": True, "id": "3EBF", "file": {"media": "image"}}
    real["send file"] = second_fails
    _, _, args = approved(send_args(files=["a.png", "b.png", "c.png"]))
    result = wa.execute(args)
    assert result["ok"] is False and result["error"].startswith("partly sent: 1 of 3")
    assert [f["status"] for f in result["files"]] == ["sent", "not sent", "not sent"]
    assert len(fake.args_of(["send", "file"])) == 2                          # the third never tried


def test_an_unclear_failure_is_uncertain(ws, fake):
    put(ws, "a.png")
    put(ws, "b.png")
    fake.overrides["send file"] = TimeoutError("wacli did not answer within 180s")
    _, _, args = approved(send_args(files=["a.png", "b.png"]))
    result = wa.execute(args)
    assert result["error"].startswith("UNCERTAIN") and "files sent before it: 0 of 2" in result["error"]
    assert [f["status"] for f in result["files"]] == ["uncertain", "not sent"]
    fake.overrides["send file"] = wa.WhatsAppError("store is locked", reported=True)
    wa._PENDING.clear()
    _, _, args = approved(send_args(files=["a.png"]), ids={**IDS, "tool_call_id": "call-9"})
    assert wa.execute(args)["error"].startswith("not sent: store is locked")


def test_raw_output_is_never_read_as_a_refusal(ws, fake):
    put(ws, "trip/a.png")
    # an abnormal exit whose output carries a marker-looking text (say, an attachment's name)
    fake.overrides["send file"] = wa.WhatsAppError('… sent no such file or directory.txt {"success":true}')
    _, _, args = approved(send_args())
    assert wa.execute(args)["error"].startswith("UNCERTAIN")


def test_wacli_envelopes_are_trusted(monkeypatch, tmp_path):
    real = base._load("whatsapp_access_engine_envelope_test", base.ROOT / "wa.py")
    monkeypatch.setattr(real, "wacli_path", lambda: "/x/wacli")
    outputs = iter([base.Proc(1, "", '{"success":false,"data":null,"error":"file too large"}\n'),
                    base.Proc(1, "", "panic: no such file or directory\n"),
                    base.Proc(0, "not json no such file", "")])
    monkeypatch.setattr(real.subprocess, "run", lambda argv, **kw: next(outputs))
    for reported in (True, False, False):
        with pytest.raises(real.WhatsAppError) as info:
            real.run(["send", "file"], write=True)
        assert info.value.reported is reported
        assert real.file_not_dispatched(info.value) is reported


def test_an_expired_pairing_never_stages_again(ws, fake, monkeypatch):
    path = put(ws, "trip/a.png")
    clock = [1000.0]
    monkeypatch.setattr(wa.time, "time", lambda: clock[0])
    wa.approval_request(send_args(), ids=IDS)                 # card shows the original
    clock[0] += wa.PENDING_TTL + 1
    path.write_bytes(PNG2)
    assert wa.outbox_binding(send_args(), ids=IDS) is None    # no fresh copy of the changed file
    with pytest.raises(wa.WhatsAppError, match="expired"):
        wa.approval_request(send_args(), ids=IDS)
    assert "not sent" in wa.execute(send_args())["error"]


def test_audio_cannot_carry_a_caption(ws, fake):
    put(ws, "voice.mp3", b"ID3" + b"\x00" * 64)
    put(ws, "trip/a.png")
    with pytest.raises(wa.WhatsAppError, match="drops the caption"):
        wa.approval_request(send_args(files=["voice.mp3"], text="聞いて"), ids=IDS)
    card, _, _ = approved(send_args(files=["voice.mp3"]), ids={**IDS, "tool_call_id": "c2"})
    assert "voice.mp3" in card
    card, _, _ = approved(send_args(files=["trip/a.png", "voice.mp3"], text="聞いて"), ids={**IDS, "tool_call_id": "c3"})
    assert "the text is the first one's caption" in card


def test_the_deadline_stops_before_a_file_it_cannot_finish(ws, fake, monkeypatch):
    put(ws, "trip/a.png")
    monkeypatch.setattr(wa, "FILES_DEADLINE", 10)
    _, _, args = approved(send_args())
    result = wa.execute(args)
    assert result["error"].startswith("not sent: the send ran out of time") and fake.args_of(["send", "file"]) == []


def test_text_sends_and_their_rule_key_are_unchanged(fake, ws):
    plan = {"account": "work", "chat": DM, "text": "hi", "reply_to": "", "files": []}
    old = __import__("hashlib").sha256(json.dumps(["work", DM, "hi", ""], ensure_ascii=False)
                                       .encode("utf-8")).hexdigest()[:16]
    assert wa.rule_key(plan) == f"whatsapp-access:send:{old}"
    assert wa.outbox_binding({"action": "send", "account": "work", "chat": DM, "text": "hi"}, ids=IDS) is None
    assert wa.execute({"action": "send", "account": "work", "chat": DM, "text": "hi"})["ok"] is True


def test_run_restricts_media_roots(monkeypatch, tmp_path):
    real = base._load("whatsapp_access_engine_roots_test", base.ROOT / "wa.py")
    seen = {}

    def fake_run(argv, **kwargs):
        seen["env"] = kwargs["env"]
        return base.Proc(0, json.dumps({"success": True, "data": {}, "error": None}))
    monkeypatch.setattr(real.subprocess, "run", fake_run)
    monkeypatch.setattr(real, "wacli_path", lambda: "/x/wacli")
    monkeypatch.setenv("WACLI_MEDIA_ROOTS", "/")
    real.run(["send", "text"], write=True)
    assert "WACLI_MEDIA_ROOTS" not in seen["env"]
    real.run(["send", "file"], write=True, media_roots=tmp_path)
    assert seen["env"]["WACLI_MEDIA_ROOTS"] == str(tmp_path)


def test_bypass_covers_the_outbox():
    assert wa.bypass("read_file", {"path": "~/.local/state/hermes-whatsapp/outbox/x"}) == wa.BYPASS_MESSAGE
