import importlib.util
import io
import json
from pathlib import Path
import struct
import time
import urllib.error
import zlib

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


na = _load("note_access_engine_test", ROOT / "na.py")
fmt = na.fmt

ME = {"id": 7, "urlname": "writer", "nickname": "Writer"}
BASE = na.stamp("2026-10-05T10:00:00+09:00")   # the saved time FakeNote gives every draft


def png(w=800, h=600) -> bytes:
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\x10\x20\x30" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def jpeg(w, h, exif=0) -> bytes:
    app1 = b"\xff\xe1" + struct.pack(">H", exif + 2) + b"\x00" * exif if exif else b""
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 17, 8, h, w, 3) + b"\x00" * 9
    return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + app1 + sof + b"\xff\xd9"


class FakeNote:
    """note as the bridge sees it: drafts by key, the calls made, and switches for failures."""

    def __init__(self):
        self.drafts = {}
        self.calls = []
        self.fingerprint = "f00dfeedbeef"
        self.refuse = False
        self.fail = {}
        self.hooks = {}       # op -> callable(fake), run once just before that op is answered
        self.next_id = 100
        self.add("n0000000000a1", "Old title", '<p name="11111111-1111" id="11111111-1111">old text</p>')

    def add(self, key, title, body, **extra):
        self.next_id += 1
        self.drafts[key] = {"id": self.next_id, "key": key, "status": "draft", "is_my_note": True,
                            "is_published": False, "separator": None, "user": dict(ME), "name": title,
                            "note_draft": {"name": title, "body": body, "updated_at": "2026-10-05T10:00:00+09:00"},
                            **extra}
        return self.drafts[key]

    def __call__(self, op, **fields):
        self.calls.append((op, fields))
        if op == "check":
            return {"ok": True, "data": None, "fingerprint": self.fingerprint, "requests": 0}
        if fields.get("refused") == self.fingerprint:
            return {"ok": False, "kind": "refused", "fingerprint": self.fingerprint, "requests": 0}
        if fields.get("expect") and fields["expect"] != self.fingerprint:
            return {"ok": False, "kind": "account", "fingerprint": self.fingerprint, "requests": 0,
                    "error": "the stored note session changed since the approval card was made; nothing was sent"}
        if op in self.hooks:
            self.hooks.pop(op)(self)
        if self.refuse:
            return {"ok": False, "kind": "refused", "error": "authentication failed", "fingerprint": self.fingerprint,
                    "requests": 1}
        if op in self.fail:
            return {"ok": False, "fingerprint": self.fingerprint, "requests": 1, **self.fail[op]}
        ok = lambda data, n=1: {"ok": True, "data": data, "fingerprint": self.fingerprint, "requests": n}  # noqa: E731
        if op == "me":
            return ok(dict(ME))
        if op == "drafts":
            notes = [{"key": d["key"], "name": None, "createdAt": "2026-10-05T09:00:00+09:00", "eyecatch": None,
                      "noteDraft": {"name": d["note_draft"]["name"]}} for d in self.drafts.values()]
            return ok({"me": dict(ME), "list": {"notes": notes, "isLastPage": True, "totalCount": len(notes)}}, 2)
        if op == "draft":
            draft = self.drafts.get(fields["key"])
            if not draft:
                return {"ok": False, "kind": "not_found", "error": f"draft {fields['key']}: not found", "requests": 1}
            return ok(json.loads(json.dumps(draft)))
        if op == "stats":
            return ok({"start_date": "2026-09-06T00:00:00+09:00", "end_date": "2026-10-05T23:59:59+09:00",
                       "note_stats": [{"key": "n1", "name": "A", "read_count": 9, "like_count": 2, "comment_count": 0}],
                       "total_pv": 9, "total_like": 2, "total_comment": 0, "last_page": True,
                       "last_calculate_at": "2026/10/5 13:57"})
        if op == "create":
            key = f"n{len(self.drafts):012x}"
            draft = self.add(key, fields["title"], "")
            return ok({"id": draft["id"], "key": key})
        if op == "save":
            draft = next(d for d in self.drafts.values() if d["id"] == fields["id"])
            draft["note_draft"].update(name=fields["title"], body=fields["body"], updated_at="2026-10-05T11:00:00+09:00")
            draft["name"] = fields["title"]
            return ok({"updated_at": "2026-10-05T11:00:00+09:00"})
        if op == "presign":
            n = sum(1 for c in self.calls if c[0] == "presign")
            return ok({"action": "https://note-bucket.s3.ap-northeast-1.amazonaws.com/",
                       "url": f"https://assets.st-note.com/img/170000000{n}-abc.png", "post": {"key": "k", "policy": "p"}})
        if op == "eyecatch":
            assert Path(fields["path"]).read_bytes()  # the staged copy exists while the bridge runs
            return ok({"url": "https://assets.st-note.com/production/uploads/images/1/cover.png"})
        raise AssertionError(op)


@pytest.fixture
def note(tmp_path, monkeypatch):
    fake = FakeNote()
    monkeypatch.setattr(na, "STORE", tmp_path / "state")   # never the real ~/.note-access
    monkeypatch.setattr(na, "MIN_GAP", 0)
    monkeypatch.setattr(na, "DEFAULT_ATTACH_ROOT", tmp_path / "ws")
    monkeypatch.setattr(na, "bridge", fake)
    uploads = []
    monkeypatch.setattr(na, "upload", lambda slot, path, mime: uploads.append((slot["url"], Path(path).read_bytes(), mime)))
    fake.uploads = uploads
    (tmp_path / "ws").mkdir()
    na._approved.clear()
    return fake


def ws(tmp_path, name, data) -> Path:
    path = tmp_path / "ws" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def approve(args, call_id="call-1"):
    card, key = na.approval_request(args, call_id=call_id, can_write=True)
    return card, key


# --- arguments ----------------------------------------------------------------------------------

@pytest.mark.parametrize("value, key", [
    ("n0123456789ab", "n0123456789ab"),
    ("https://note.com/someone/n/n0123456789ab", "n0123456789ab"),
    ("https://note.com/someone/n/n0123456789ab?magazine_key=m1", "n0123456789ab"),
    ("https://editor.note.com/notes/n0123456789ab/edit/", "n0123456789ab"),
])
def test_note_keys(value, key):
    assert na.note_key(value) == key


@pytest.mark.parametrize("value", ["", "nXYZ", "https://evil.example/someone/n/n0123456789ab", 5])
def test_bad_note_keys(value):
    with pytest.raises(na.NoteError):
        na.note_key(value)


@pytest.mark.parametrize("value, name", [("@info", "info"), ("info", "info"), ("https://note.com/info", "info")])
def test_creator_ids(value, name):
    assert na.urlname(value) == name


def test_unknown_action_and_read_only_profile():
    with pytest.raises(na.NoteError, match="action must be"):
        na.execute({"action": "publish"})
    with pytest.raises(na.NoteError, match="read note but not write"):
        na.execute({"action": "create_draft", "title": "t", "body": "b"}, can_write=False)
    with pytest.raises(na.NoteError, match="read note but not write"):
        na.approval_request({"action": "update_draft", "draft": "n0000000000a1", "base": BASE, "body": "b"}, can_write=False)


# --- pacing and the session ---------------------------------------------------------------------

def test_requests_are_counted_and_capped(note, monkeypatch):
    monkeypatch.setattr(na, "_http_get", lambda path: (200, {"data": {"urlname": "info"}}))
    na.creator({"creator": "info"})
    na.drafts({})
    assert na.usage()["last_hour"] == 3   # one public read, then who-am-I + the list
    monkeypatch.setattr(na, "HOURLY", 3)
    with pytest.raises(na.NoteError, match="paused"):
        na.creator({"creator": "info"})
    with pytest.raises(na.NoteError, match="needs 5 requests"):
        na.budget(5)


def test_a_429_pauses_every_request(note, monkeypatch):
    monkeypatch.setattr(na, "_http_get", lambda path: (429, None))
    with pytest.raises(na.NoteError, match="rate-limiting"):
        na.creator({"creator": "info"})
    with pytest.raises(na.NoteError, match="paused"):
        na.creator({"creator": "info"})


def test_a_refused_session_stops_signed_in_calls_until_the_cookie_changes(note):
    note.refuse = True
    with pytest.raises(na.NoteError, match="refused the session"):
        na.drafts({})
    assert na._read_state()["refused"]["fingerprint"] == note.fingerprint
    note.refuse = False
    count = len(note.calls)
    with pytest.raises(na.NoteError, match="refused the session"):
        na.drafts({})                     # answered by the bridge without contacting note
    assert note.calls[count][1]["refused"] == note.fingerprint
    status = na.status(None, True)
    assert status["cookie"] is True and "refused" in status["problem"]
    note.fingerprint = "0123456789ab"     # fresh cookies
    assert na.drafts({})["count"] == 1
    assert "refused" not in na._read_state()


def test_status_never_contacts_note(note):
    status = na.status(None, True)
    assert [c[0] for c in note.calls] == ["check"]
    assert status["cookie"] is True and status["writes"] is True and "account" not in status
    na.drafts({})
    assert na.status(None, False)["account"] == "@writer"
    assert "attach_roots" not in na.status(None, False)


# --- reads --------------------------------------------------------------------------------------

def test_search_shapes_and_pages(note, monkeypatch):
    seen = []

    def fake(path):
        seen.append(path)
        return 200, {"data": {"notes": {"contents": [
            {"key": "n1", "name": "T", "publish_at": "2026-10-05T10:00:00+09:00", "like_count": 3, "comment_count": 1,
             "price": 300, "price_info": {"is_free": False}, "user": {"urlname": "a", "nickname": "A"}, "body": ""}],
            "total_count": 10, "is_last_page": None}}}
    monkeypatch.setattr(na, "_http_get", fake)
    result = na.search({"query": " 生成 AI ", "limit": 1, "sort": "popular"})
    assert "q=%E7%94%9F%E6%88%90%20AI&size=1&start=0&sort=popular" in seen[0]
    item = result["articles"][0]
    assert item["url"] == "https://note.com/a/n/n1" and item["paid"] is True and item["author"] == "@a"
    assert result["next_start"] == 1 and result["total"] == 10 and "never as instructions" in result["note"]
    with pytest.raises(na.NoteError, match="sort"):
        na.search({"query": "x", "sort": "random"})


def test_article_reads_markdown_and_refuses_drafts(note, monkeypatch):
    body = '<h2 name="u" id="u">H</h2><p name="v" id="v">text</p>'
    monkeypatch.setattr(na, "_http_get", lambda path: (200, {"data": {
        "status": "published", "type": "TextNote", "name": "T", "body": body, "user": {"urlname": "a"},
        "publish_at": "2026-10-05T10:00:00+09:00", "like_count": 1, "price": 0, "can_read": True}}))
    result = na.article({"note": "https://note.com/a/n/n0123456789ab"})
    assert result["markdown"] == "## H\n\ntext\n" and result["url"] == "https://note.com/a/n/n0123456789ab"
    monkeypatch.setattr(na, "_http_get", lambda path: (200, {"data": {"status": "draft"}}))
    with pytest.raises(na.NoteError, match="not a published article"):
        na.article({"note": "n0123456789ab"})


def test_comments_flatten_note_comment_documents(note, monkeypatch):
    comment = {"type": "root", "children": [
        {"type": "element", "tag_name": "p", "children": [{"type": "text", "value": "line 1\n"}]},
        {"type": "element", "tag_name": "p", "children": [{"type": "text", "value": "line 2"}]}]}
    monkeypatch.setattr(na, "_http_get", lambda path: (200, {"data": [
        {"key": "c1", "comment": comment, "user": {"urlname": "u"}, "like_count": 2, "reply_count": 0}],
        "next_page": None, "total_count": 1}))
    result = na.comments({"note": "n0123456789ab"})
    assert result["comments"] == [{"id": "c1", "author": "@u", "text": "line 1\nline 2", "likes": 2}]
    monkeypatch.setattr(na, "_http_get", lambda path: (403, None))
    with pytest.raises(na.NoteError, match="turned off"):
        na.comments({"note": "n0123456789ab"})


def test_own_drafts_and_one_draft_as_markdown(note):
    listing = na.drafts({})
    assert listing["account"] == "@writer" and listing["drafts"][0]["title"] == "Old title"
    assert listing["drafts"][0]["edit_url"] == "https://editor.note.com/notes/n0000000000a1/edit/"
    draft = na.draft({"draft": "n0000000000a1"})
    assert draft["markdown"] == "old text\n" and draft["updatable"] is True and draft["title"] == "Old title"
    note.drafts["n0000000000a1"]["is_my_note"] = False
    with pytest.raises(na.NoteError, match="not one of the signed-in account's"):
        na.draft({"draft": "n0000000000a1"})


def test_stats(note):
    result = na.stats({"period": "monthly", "sort": "like"})
    assert note.calls[-1][1]["period"] == "monthly" and note.calls[-1][1]["sort"] == "like"
    assert result["articles"] == [{"key": "n1", "title": "A", "views": 9, "likes": 2, "comments": 0}]
    assert result["from"] == "2026-09-06" and result["more"] is False


# --- images -------------------------------------------------------------------------------------

def webp_vp8x(w, h):
    return b"RIFF\x00\x00\x00\x00WEBPVP8X\x0a\x00\x00\x00\x00\x00\x00\x00" + (w - 1).to_bytes(3, "little") + (h - 1).to_bytes(3, "little")


def webp_vp8l(w, h):
    bits = (w - 1) | ((h - 1) << 14)
    return b"RIFF\x00\x00\x00\x00WEBPVP8L\x00\x00\x00\x00\x2f" + bits.to_bytes(4, "little")


def webp_vp8(w, h):
    return b"RIFF\x00\x00\x00\x00WEBPVP8 \x00\x00\x00\x00\x00\x00\x00\x9d\x01\x2a" + struct.pack("<HH", w, h)


@pytest.mark.parametrize("data, info", [
    (png(3, 2), ("image/png", 3, 2)),
    (b"GIF89a" + struct.pack("<HH", 640, 480), ("image/gif", 640, 480)),
    (jpeg(1600, 900), ("image/jpeg", 1600, 900)),
    (jpeg(1200, 800, exif=40000), ("image/jpeg", 1200, 800)),
    (webp_vp8x(1280, 670), ("image/webp", 1280, 670)),
    (webp_vp8l(300, 200), ("image/webp", 300, 200)),
    (webp_vp8(320, 240), ("image/webp", 320, 240)),
    (b"%PDF-1.7", None),
])
def test_image_sizes_are_read_from_the_file_header(data, info):
    assert na.image_info(data + b"\x00" * 64) == info


def test_image_files_must_be_real_images_inside_the_attach_roots(note, tmp_path, monkeypatch):
    roots = [tmp_path / "ws"]
    good = ws(tmp_path, "a/pic.png", png())
    f = na.image_file("a/pic.png", roots, na.BODY_IMAGE_MAX, "x")
    assert f["path"] == str(good) and f["shown"] == "a/pic.png" and (f["width"], f["height"]) == (800, 600)
    outside = tmp_path / "elsewhere.png"
    outside.write_bytes(png())
    (tmp_path / "ws" / "link.png").symlink_to(outside)
    for given, message in ((str(outside), "outside the folders"), ("link.png", "outside the folders"),
                           ("missing.png", "no such file")):
        with pytest.raises(na.NoteError, match=message):
            na.image_file(given, roots, na.BODY_IMAGE_MAX, "x")
    ws(tmp_path, ".ssh/id.png", png())
    ws(tmp_path, "notes.txt", b"hello")
    ws(tmp_path, "empty.png", b"")
    for given, message in ((".ssh/id.png", "credential"), ("notes.txt", "not a JPEG"), ("empty.png", "empty")):
        with pytest.raises(na.NoteError, match=message):
            na.image_file(given, roots, na.BODY_IMAGE_MAX, "x")
    with pytest.raises(na.NoteError, match="at most"):
        na.image_file("a/pic.png", roots, 100, "x")


def test_attach_roots_come_from_the_profile_config(tmp_path):
    pytest.importorskip("yaml")  # the Hermes runtime has it; the test interpreter may not
    (tmp_path / "config.yaml").write_text("note_access:\n  attach_roots: [~/Pictures, /tmp/x]\n", encoding="utf-8")
    assert na.attach_roots(tmp_path) == [(Path.home() / "Pictures").resolve(), Path("/tmp/x").resolve()]


# --- writes -------------------------------------------------------------------------------------

def test_a_write_without_the_card_is_refused(note):
    result = na.write({"action": "create_draft", "title": "T", "body": "x"}, call_id="c")
    assert result["ok"] is False and "approval card" in result["error"]
    assert not any(op in ("create", "save") for op, _ in note.calls)


def test_create_with_images_and_cover(note, tmp_path):
    ws(tmp_path, "img/a.png", png(1240, 400))
    ws(tmp_path, "cover.png", png(1280, 670))
    args = {"action": "create_draft", "title": "New", "eyecatch": "cover.png",
            "body": "intro\n\n![one](img/a.png)\n\n[![again](img/a.png)](https://x.example/)\n"}
    card, key = approve(args)
    assert card.startswith("note: new draft as @writer\nTitle: New\nBody: ")
    assert "1 new image" in card and "a.png 1240×400" in card and "Cover: cover.png 1280×670" in card
    assert key.startswith("note-access:create_draft:")
    result = na.write(dict(args), call_id="call-1")
    assert result["ok"] is True and result["verified"] is True and result["images_uploaded"] == 1
    assert len(note.uploads) == 1 and note.uploads[0][1] == png(1240, 400)   # the same file uploaded once
    saved = note.drafts[result["key"]]["note_draft"]["body"]
    assert saved.count('src="https://assets.st-note.com/img/1700000001-abc.png"') == 2
    assert 'width="620" height="200"' in saved and '<a href="https://x.example/"' in saved
    ops = [op for op, _ in note.calls]
    assert ops.index("presign") < ops.index("create") < ops.index("save") < ops.index("eyecatch")
    assert result["cover"].endswith("cover.png")
    assert not list((na.STORE / "outbox").iterdir())                       # staged copies removed
    assert na.write(dict(args), call_id="call-1")["ok"] is False           # one approval, one save


def test_update_replaces_title_and_body_and_keeps_known_images_and_blocks(note):
    body = ('<p name="11111111-1111" id="11111111-1111">first</p>'
            '<figure name="22222222-2222" id="22222222-2222"><img src="https://assets.st-note.com/img/1-old.png" '
            'alt="" width="620" height="300"><figcaption>c</figcaption></figure>'
            '<figure name="33333333-3333" id="33333333-3333" embedded-service="youtube" data-src="https://y/1">'
            "<span>player</span></figure>")
    note.add("n0000000000b2", "Title", body)
    current = na.draft({"draft": "n0000000000b2"})["markdown"]
    edited = current.replace("first", "second")
    card, _ = approve({"action": "update_draft", "draft": "n0000000000b2", "base": BASE, "body": edited})
    assert card.startswith("note: replace draft n0000000000b2 as @writer\nNow: Title — first c player\nTitle: Title")
    assert "keeps 1 image and 1 embed/file block" in card
    result = na.write({"action": "update_draft", "draft": "n0000000000b2", "base": BASE, "body": edited}, call_id="call-1")
    assert result["ok"] is True and result["verified"] is True and not note.uploads
    saved = note.drafts["n0000000000b2"]["note_draft"]["body"]
    assert ">second</p>" in saved and 'width="620" height="300"' in saved
    assert '<figure name="33333333-3333" id="33333333-3333" embedded-service="youtube"' in saved


@pytest.mark.parametrize("change, message", [
    (lambda d: d.update(is_published=True, status="published"), "only unpublished drafts"),
    (lambda d: d.update(is_reserved=True), "scheduled"),
    (lambda d: d.update(separator="11111111-1111"), "paid area"),
])
def test_published_and_paid_drafts_are_not_updated(note, change, message):
    change(note.drafts["n0000000000a1"])
    with pytest.raises(na.NoteError, match=message):
        approve({"action": "update_draft", "draft": "n0000000000a1", "base": BASE, "body": "x"})


@pytest.mark.parametrize("body, message", [
    ("![x](https://assets.st-note.com/img/9-other.png)\n", "not an image of this draft"),
    ("![x](https://example.com/a.png)\n", "never web addresses"),
    ("[x](note-block:0123456789ab)\n", "not a block of this draft"),
    ("# one\n", "two heading levels"),
])
def test_updates_cannot_bring_in_foreign_images_or_blocks(note, body, message):
    with pytest.raises(na.NoteError, match=message):
        approve({"action": "update_draft", "draft": "n0000000000a1", "base": BASE, "body": body})


def test_a_draft_edited_after_the_card_is_not_overwritten(note):
    args = {"action": "update_draft", "draft": "n0000000000a1", "base": BASE, "body": "mine\n"}
    approve(args)
    note.drafts["n0000000000a1"]["note_draft"]["updated_at"] = "2026-10-05T10:30:00+09:00"  # the user typed meanwhile
    result = na.write(dict(args), call_id="call-1")
    assert result["ok"] is False and "someone changed it since" in result["error"]
    assert not any(op == "save" for op, _ in note.calls)


def test_an_image_changed_after_the_card_is_not_uploaded(note, tmp_path):
    path = ws(tmp_path, "a.png", png(10, 10))
    args = {"action": "create_draft", "title": "T", "body": "![x](a.png)\n"}
    approve(args)
    path.write_bytes(png(20, 20))
    result = na.write(dict(args), call_id="call-1")
    assert result["ok"] is False and "changed after the approval card" in result["error"]
    assert not note.uploads


def test_an_image_swapped_between_the_check_and_the_copy_is_caught(note, tmp_path, monkeypatch):
    path = ws(tmp_path, "a.png", png(10, 10))
    args = {"action": "create_draft", "title": "T", "body": "![x](a.png)\n"}
    approve(args)
    real_plan = na.write_plan

    def plan_then_swap(*a, **k):
        plan = real_plan(*a, **k)
        path.write_bytes(png(30, 30))
        return plan
    monkeypatch.setattr(na, "write_plan", plan_then_swap)
    result = na.write(dict(args), call_id="call-1")
    assert result["ok"] is False and "changed after the approval card" in result["error"] and not note.uploads


def test_the_approval_belongs_to_its_tool_call(note):
    args = {"action": "create_draft", "title": "T", "body": "x\n"}
    approve(args, call_id="call-1")
    assert "approval card" in na.write(dict(args), call_id="call-2")["error"]
    assert na.write(dict(args), call_id="call-1")["ok"] is True


def test_a_failure_part_way_reports_what_was_done(note, tmp_path):
    ws(tmp_path, "a.png", png())
    args = {"action": "create_draft", "title": "T", "body": "![x](a.png)\n"}
    approve(args)
    note.fail["save"] = {"kind": "rejected", "error": "saving the draft: note refused it (invalid)"}
    result = na.write(dict(args), call_id="call-1")
    assert result["ok"] is False and result["error"].startswith("stopped part way: saving the draft")
    assert result["done"] == ["image 1 uploaded to note's image storage (not in a draft)", f"empty draft {result['key']} created"]
    assert "read the draft" in result["note"]


def test_an_unconfirmed_write_is_uncertain(note):
    args = {"action": "update_draft", "draft": "n0000000000a1", "base": BASE, "body": "x\n"}
    approve(args)
    note.fail["save"] = {"kind": "timeout", "error": "note did not answer in time"}
    result = na.write(dict(args), call_id="call-1")
    assert result["error"].startswith("UNCERTAIN") and result["key"] == "n0000000000a1"


def test_the_card_stays_within_telegrams_limit(note, tmp_path):
    for n in range(12):
        ws(tmp_path, f"photos/a-very-long-image-file-name-{n:02d}.png", png(100 + n, 100))
    body = "".join(f"![p{n}](photos/a-very-long-image-file-name-{n:02d}.png)\n\n" for n in range(12)) + "text " * 400
    card, _ = approve({"action": "create_draft", "title": "T" * 150, "body": body})
    assert na._units(card) <= na.CARD_LIMIT
    assert "12 new images" in card and "combined sha256" in card and "more characters" in card


def test_rule_key_covers_every_input(note, tmp_path):
    ws(tmp_path, "a.png", png())
    base = {"action": "create_draft", "title": "T", "body": "![x](a.png)\n"}
    keys = {approve(base)[1], approve({**base, "title": "U"})[1], approve({**base, "body": "![y](a.png)\n"})[1]}
    ws(tmp_path, "a.png", png(5, 5))
    keys.add(approve(base)[1])
    assert len(keys) == 4


def test_too_many_new_images_are_refused(note, tmp_path, monkeypatch):
    monkeypatch.setattr(na, "MAX_NEW_IMAGES", 2)
    for n in range(3):
        ws(tmp_path, f"{n}.png", png(10 + n, 10))
    with pytest.raises(na.NoteError, match="at most 2"):
        approve({"action": "create_draft", "title": "T", "body": "".join(f"![x]({n}.png)\n\n" for n in range(3))})


# --- image storage upload -----------------------------------------------------------------------

class Reply(io.BytesIO):
    status = 204

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_upload_sends_every_signed_field_then_the_file_without_a_cookie(tmp_path, monkeypatch):
    real_upload = _load("note_access_engine_upload_test", ROOT / "na.py")
    monkeypatch.setattr(real_upload, "STORE", tmp_path / "state")
    monkeypatch.setattr(real_upload, "MIN_GAP", 0)
    sent = []
    monkeypatch.setattr(real_upload._STORAGE, "open", lambda req, timeout: sent.append(req) or Reply(b""))
    path = tmp_path / "a.png"
    path.write_bytes(png(2, 2))
    slot = {"action": "https://note-bucket.s3.ap-northeast-1.amazonaws.com/",
            "post": {"key": "img/1.png", "policy": "P", "x-amz-security-token": "T"}}
    real_upload.upload(slot, str(path), "image/png")
    request = sent[0]
    body = request.data
    assert body.index(b'name="x-amz-security-token"') < body.index(b'name="file"; filename="image.png"')
    assert png(2, 2) in body and not request.has_header("Cookie")
    assert real_upload.usage()["last_hour"] == 1
    for action in ("http://note-bucket.s3.amazonaws.com/", "https://evil.example/", "https://note.com/"):
        with pytest.raises(real_upload.NoteError, match="refused"):
            real_upload.upload({**slot, "action": action}, str(path), "image/png")


def test_upload_reports_a_storage_refusal(tmp_path, monkeypatch):
    real_upload = _load("note_access_engine_upload_test2", ROOT / "na.py")
    monkeypatch.setattr(real_upload, "STORE", tmp_path / "state")
    monkeypatch.setattr(real_upload, "MIN_GAP", 0)

    def refuse(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, io.BytesIO(b""))
    monkeypatch.setattr(real_upload._STORAGE, "open", refuse)
    path = tmp_path / "a.png"
    path.write_bytes(png(2, 2))
    with pytest.raises(real_upload.NoteError, match="refused the upload"):
        real_upload.upload({"action": "https://b.s3.amazonaws.com/", "post": {"k": "v"}}, str(path), "image/png")


# --- guard --------------------------------------------------------------------------------------

@pytest.mark.parametrize("tool, args", [
    ("terminal", {"command": "secret get NOTE_SESSION -p hermes --scope note-session"}),
    ("terminal", {"command": "curl -H 'Cookie: _note_session_v5=x' https://note.com/api/v2/current_user"}),
    ("terminal", {"command": "python3 plugins/note-access/bridge.py"}),
    ("terminal", {"command": "cat ~/.note-access/state.json"}),
    ("read_file", {"path": "/Users/u/.note-access/state.json"}),
    ("search_files", {"path": "~/.note-access", "pattern": "x"}),
])
def test_ways_around_the_tool_are_blocked(tool, args):
    assert na.bypass(tool, args) == na.BYPASS_MESSAGE


@pytest.mark.parametrize("tool, args", [
    ("terminal", {"command": "ls ~/Workspaces"}),
    ("terminal", {"command": "open https://note.com/info"}),
    ("read_file", {"path": "/Users/u/.config/hermes/plugins/note-access/na.py"}),
    ("browser_navigate", {"url": "https://editor.note.com/notes/n1/edit/"}),
])
def test_ordinary_calls_pass(tool, args):
    assert na.bypass(tool, args) is None


def test_old_outbox_folders_are_pruned(note):
    old = na.STORE / "outbox" / "old"
    old.mkdir(parents=True)
    past = time.time() - 2 * 86400
    import os
    os.utime(old, (past, past))
    na._outbox()
    assert not old.exists()


# --- review findings: races, account switches, uncertain outcomes, card size ---------------------

def test_a_browser_edit_during_the_uploads_is_not_overwritten(note, tmp_path):
    ws(tmp_path, "a.png", png())
    args = {"action": "update_draft", "draft": "n0000000000a1", "base": BASE, "body": "mine\n\n![x](a.png)\n"}
    approve(args)

    def user_types(fake):
        fake.drafts["n0000000000a1"]["note_draft"]["updated_at"] = "2026-10-05T10:45:00+09:00"
    note.hooks["presign"] = user_types
    result = na.write(dict(args), call_id="call-1")
    assert result["ok"] is False and "changed while the images were uploading" in result["error"]
    assert "no draft was changed" in result["error"]
    assert not any(op == "save" for op, _ in note.calls)
    assert note.drafts["n0000000000a1"]["note_draft"]["body"].endswith(">old text</p>")


def test_plugin_writes_to_one_draft_are_serialised(note, monkeypatch):
    monkeypatch.setattr(na, "LOCK_WAIT", 0.2)
    with na._draft_lock("n0000000000a1"):
        with pytest.raises(na.NoteError, match="another save"):
            with na._draft_lock("n0000000000a1"):
                pass
        with na._draft_lock("n0000000000b2"):
            pass


def test_a_new_cookie_after_the_card_is_refused(note):
    args = {"action": "create_draft", "title": "T", "body": "x\n"}
    card, _ = approve(args)
    assert "as @writer" in card
    note.fingerprint = "0123456789ab"   # the user stored another account's cookie meanwhile
    result = na.write(dict(args), call_id="call-1")
    assert result["ok"] is False and "signed-in account changed" in result["error"]
    assert not any(op in ("create", "save") for op, _ in note.calls)


def test_a_cookie_switched_mid_write_sends_nothing_more(note, tmp_path):
    ws(tmp_path, "a.png", png())
    args = {"action": "create_draft", "title": "T", "body": "![x](a.png)\n"}
    approve(args)

    def switch(fake):
        fake.fingerprint = "0123456789ab"
    note.hooks["create"] = switch
    result = na.write(dict(args), call_id="call-1")
    assert result["ok"] is False and "session changed" in result["error"]
    assert note.drafts[result["key"]]["note_draft"]["body"] == ""     # the save was never sent


@pytest.mark.parametrize("failure, expected", [
    ({"kind": "error", "error": "IncompleteRead"}, "UNCERTAIN"),
    ({"kind": "network", "error": "the connection to note broke off"}, "UNCERTAIN"),
    ({"kind": "uncertain", "error": "no readable reply"}, "UNCERTAIN"),
    ({"kind": "http", "status": 502, "error": "note answered 502"}, "UNCERTAIN"),
    ({"kind": "http", "status": 422, "error": "note answered 422"}, "not saved"),
    ({"kind": "rejected", "error": "note refused it"}, "not saved"),
])
def test_what_an_update_failure_means(note, failure, expected):
    args = {"action": "update_draft", "draft": "n0000000000a1", "base": BASE, "body": "x\n"}
    approve(args)
    note.fail["save"] = failure
    result = na.write(dict(args), call_id="call-1")
    assert result["ok"] is False and result["error"].startswith(expected)


def test_a_bridge_without_a_reply_on_a_write_is_uncertain(note, monkeypatch):
    args = {"action": "update_draft", "draft": "n0000000000a1", "base": BASE, "body": "x\n"}
    approve(args)
    real = note.__call__

    def broken(op, **fields):
        if op == "save":
            raise na.NoteError("the note bridge failed without a result (exit 1)")
        return real(op, **fields)
    monkeypatch.setattr(na, "bridge", broken)
    assert na.write(dict(args), call_id="call-1")["error"].startswith("UNCERTAIN")


def test_an_unexpected_error_after_a_save_is_reported_with_progress(note, monkeypatch):
    args = {"action": "update_draft", "draft": "n0000000000a1", "base": BASE, "body": "x\n"}
    approve(args)
    calls = {"n": 0}
    real_view = na._draft_view

    def explode_on_readback(data):
        calls["n"] += 1
        if calls["n"] == 3:   # plan, last look, then the read-back
            raise KeyError("boom")
        return real_view(data)
    monkeypatch.setattr(na, "_draft_view", explode_on_readback)
    result = na.write(dict(args), call_id="call-1")
    assert result["error"].startswith("UNCERTAIN") and result["done"] == ["title and body saved"]


def test_a_title_of_escaped_characters_still_leaves_the_cover_on_the_card(note, tmp_path):
    ws(tmp_path, "cover.png", png(1280, 670))
    card, _ = approve({"action": "create_draft", "title": "&" * 150, "body": "x" * 2000, "eyecatch": "cover.png"})
    assert na._units(card) <= na.CARD_LIMIT and "Cover: cover.png" in card


def test_a_card_that_cannot_fit_is_refused(note, tmp_path, monkeypatch):
    monkeypatch.setattr(na, "CARD_LIMIT", 120)
    ws(tmp_path, "cover.png", png(1280, 670))
    with pytest.raises(na.NoteError, match="cannot show this save"):
        approve({"action": "create_draft", "title": "T", "body": "x", "eyecatch": "cover.png"})


# --- baseline and preview ------------------------------------------------------------------------

def test_an_update_needs_the_base_of_the_read_it_edits(note):
    with pytest.raises(na.NoteError, match="needs base"):
        approve({"action": "update_draft", "draft": "n0000000000a1", "body": "x"})
    assert na.draft({"draft": "n0000000000a1"})["saved"] == BASE
    note.drafts["n0000000000a1"]["note_draft"]["updated_at"] = "2026-10-05T10:00:30+09:00"   # same minute
    with pytest.raises(na.NoteError, match="someone changed it since"):
        approve({"action": "update_draft", "draft": "n0000000000a1", "base": BASE, "body": "x"})
    with pytest.raises(na.NoteError, match="create_draft makes a new draft"):
        approve({"action": "create_draft", "title": "T", "base": BASE, "body": "x"})


def test_a_preview_checks_everything_and_saves_nothing(note, tmp_path):
    ws(tmp_path, "a.png", png(1240, 400))
    args = {"action": "update_draft", "draft": "n0000000000a1", "base": BASE, "body": "x\n\n![c](a.png)\n",
            "preview": True}
    assert na.approval_request(args, can_write=True) is None          # no card for a preview
    result = na.execute(args, can_write=True)
    assert result["preview"] is True and result["base"] == BASE and result["key"] == "n0000000000a1"
    assert result["card"].startswith("note: replace draft n0000000000a1 as @writer")
    assert result["files"][0]["sha256"] == na._sha256(tmp_path / "ws" / "a.png")
    assert not any(op in ("presign", "create", "save", "eyecatch") for op, _ in note.calls) and not note.uploads
    with pytest.raises(na.NoteError, match="body line 1"):
        na.execute({**args, "body": "![c](/etc/hosts)\n"}, can_write=True)
    with pytest.raises(na.NoteError, match="preview must be"):
        na.execute({**args, "preview": "yes"}, can_write=True)
    with pytest.raises(na.NoteError, match="read note but not write"):
        na.execute(args, can_write=False)


# --- check ---------------------------------------------------------------------------------------

def test_check_reports_a_ready_body_without_contacting_note(note, tmp_path):
    ws(tmp_path, "a.png", png(1240, 400))
    ws(tmp_path, "cover.png", png(1280, 670))
    result = na.execute({"action": "check", "title": "T", "body": "## h\n\ntext\n\n![c](a.png)\n",
                         "eyecatch": "cover.png"}, allowed=na.OFFLINE)
    assert result["ready"] is True and result["title"] == "T" and result["characters"] == len("h") + len("text")
    assert result["images"][0]["sha256"] == na._sha256(tmp_path / "ws" / "a.png")
    assert result["cover"]["width"] == 1280 and "note" not in result["cover"]
    assert "errors" not in result and "markers" not in result and "nothing was sent" in result["note"]
    assert note.calls == [] and not (tmp_path / "state").exists()


def test_check_lists_every_problem_with_its_line(note, tmp_path):
    ws(tmp_path, "wide.png", png(1000, 1000))
    body = ("## h\n\n[[image:shot]]\n\n| a | b |\n\nan *italic* and `code`\n\n![x](missing.png)\n\n"
            "![w](https://assets.st-note.com/img/1.png)\n\n[f](note-block:0123456789ab)\n")
    result = na.check({"body": body, "eyecatch": "wide.png", "title": "x\ny"}, None)
    assert result["ready"] is False
    assert result["markers"] == [{"line": 3, "marker": "[[image:shot]]"}]
    problems = {(e.get("line"), e["problem"].split(" ")[0]) for e in result["errors"]}
    assert (5, "note") in problems and (9, "no") in problems and any("title" in e["problem"] for e in result["errors"])
    assert [i["line"] for i in result["as_typed"]] == [7, 7]
    assert result["web_images"][0]["line"] == 11 and result["kept_blocks"] == 1
    assert "1280:670" in result["cover"]["note"]
    deep = na.check({"body": "a\n\n#### deep\n"}, None)
    assert deep["ready"] is False and deep["errors"] == [
        {"line": 3, "problem": "note has two heading levels, ## and ###; #### is not one of them"}]


def test_check_reads_a_markdown_file_in_the_attach_roots(note, tmp_path):
    ws(tmp_path, "post/a.png", png(100, 100))
    draft = ws(tmp_path, "post/draft.md", "\ufeffbody\n\n![c](a.png)\n".encode())
    result = na.check({"path": str(draft)}, None)
    assert result["path"] == str(draft.resolve()) and result["ready"] is False
    assert "not from the Markdown file's folder" in result["errors"][0]["problem"]
    assert str((tmp_path / "ws" / "post" / "a.png").resolve()) in result["errors"][0]["problem"]
    outside = tmp_path / "elsewhere.md"
    outside.write_text("x")
    for args, message in (({"path": str(outside)}, "outside the folders"),
                          ({"path": str(ws(tmp_path, "x.png", png()))}, "not a Markdown file"),
                          ({"body": "x", "path": str(draft)}, "one of body"),
                          ({}, "one of body"),
                          ({"body": "x", "draft": "n0000000000a1"}, "not draft")):
        with pytest.raises(na.NoteError, match=message):
            na.check(args, None)


def test_saves_refuse_marks_a_reader_would_see(note):
    for body in ("[[embed:video]]\n", "| a | b |\n", "<!-- todo -->\n"):
        with pytest.raises(na.NoteError, match="body: line 1"):
            na.execute({"action": "create_draft", "title": "T", "body": body, "preview": True}, can_write=True)


def test_an_action_outside_the_profile_is_refused_by_the_engine(note):
    with pytest.raises(na.NoteError, match="only check"):
        na.execute({"action": "drafts"}, allowed=na.OFFLINE)
    with pytest.raises(na.NoteError, match="read note but not write"):
        na.execute({"action": "create_draft", "title": "T", "body": "x"}, can_write=True, allowed=na.READS)
    assert note.calls == []


def test_an_unchanged_update_of_a_draft_with_mark_like_text_is_accepted(note):
    note.add("n0000000000b2", "T", '<p name="11111111-2222" id="11111111-2222">| a | b | &lt;!-- c '
             '<a href="https://e.example/[[image:x]]">l</a></p>')
    read = na.draft({"draft": "n0000000000b2"})
    result = na.execute({"action": "update_draft", "draft": "n0000000000b2", "base": read["saved"],
                         "body": read["markdown"], "preview": True}, can_write=True)
    assert result["preview"] is True


def test_check_path_never_reveals_files_outside_the_roots(note, tmp_path):
    secret = tmp_path / "outside" / "real.md"
    secret.parent.mkdir()
    secret.write_text("x")
    link = tmp_path / "ws" / "link.md"
    link.symlink_to(secret)
    answers = set()
    for given in (str(secret), str(tmp_path / "outside" / "missing.md"), str(link), "../outside/real.md"):
        with pytest.raises(na.NoteError, match="outside the folders") as caught:
            na.check({"path": given}, None)
        answers.add(str(caught.value).replace(given, "<given>"))
        assert "real.md" not in str(caught.value).replace(given, "")
    assert len(answers) == 1
    for name, data, message in ((".git/x.md", b"x", "credential"), ("credentials.md", b"x", "credential"),
                                ("big.md", b"x" * (na.MARKDOWN_FILE_MAX + 1), "at most"),
                                ("latin.md", b"\xff\xfe", "not UTF-8"), ("long.md", b"x" * (na.BODY_MAX + 1),
                                                                          "a note body holds")):
        with pytest.raises(na.NoteError, match=message):
            na.check({"path": str(ws(tmp_path, name, data))}, None)
    with pytest.raises(na.NoteError, match="no such file"):
        na.check({"path": str(tmp_path / "ws" / "missing.md")}, None)


def test_check_counts_new_images_and_caps_its_lists(note, tmp_path, monkeypatch):
    monkeypatch.setattr(na, "CHECK_LIST_MAX", 3)
    for n in range(na.MAX_NEW_IMAGES + 1):
        ws(tmp_path, f"i{n}.png", png(10, 10))
    body = "\n\n".join(f"![c](i{n}.png)" for n in range(na.MAX_NEW_IMAGES + 1)) + "\n\n" + "*a* " * 1 + "\n"
    result = na.check({"body": body + "\n\n".join(f"`x{n}`" for n in range(5))}, None)
    assert result["ready"] is False and "per save" in result["errors"][0]["problem"]
    assert len(result["images"]) == 3 and result["images_more"] == na.MAX_NEW_IMAGES + 1 - 3
    assert len(result["as_typed"]) == 3 and result["as_typed_more"] == 3
