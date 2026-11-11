"""mandate_store: shared storage, authentication, isolation and the on-disk format and MAC contract."""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

import pytest

spec = importlib.util.spec_from_file_location(
    "hermes_mandate_store",
    Path(__file__).resolve().parents[1] / "mandate_store.py",
)
mandate_store = importlib.util.module_from_spec(spec)
sys.modules["hermes_mandate_store"] = mandate_store
spec.loader.exec_module(mandate_store)

KEY = bytes(range(32))
FIELDS = {"boards": [], "repos": [{"id": "R_app", "name": "me/app", "tier": "own"}], "parent": None,
          "classes": ["routine"], "purpose": "Run the release"}


class StoreError(Exception):
    pass


EXAMPLE = mandate_store.Store(state="example-access", key_prefix="EXAMPLE_MANDATE_KEY_", scope="example-access",
                              mac_kind="example-mandate", key_note="example-access mandate MAC key", error=StoreError)
SEND = mandate_store.Store(state="send-access", key_prefix="SEND_MANDATE_KEY_", scope="send-access",
                           mac_kind="send-mandate", key_note="send-access mandate MAC key", error=StoreError,
                           id_prefix="s")


def fake_cli(path: Path, keyfile: Path, log: Path | None = None) -> Path:
    """A secret CLI over one key file: ``get`` prints it, ``show`` says it exists, ``set --stdin`` stores it."""
    record = f"echo \"$@\" >> {log}\n" if log else ""
    path.write_text(
        f"#!/bin/sh\n{record}"
        f"[ \"$1\" = get ] && [ -f {keyfile} ] && cat {keyfile} && exit 0\n"
        f"[ \"$1\" = show ] && [ -f {keyfile} ] && exit 0\n"
        f"[ \"$1\" = set ] && [ ! -f {keyfile} ] && cat > {keyfile} && exit 0\n"
        "exit 1\n")
    path.chmod(0o755)
    return path


@pytest.fixture
def keyfile(tmp_path, monkeypatch):
    keyfile = tmp_path / "keyfile"
    monkeypatch.setattr(mandate_store, "SECRET", fake_cli(tmp_path / "secret", keyfile))
    return keyfile


@pytest.fixture
def home(tmp_path):
    return tmp_path / "profile"


def with_key(keyfile: Path, key: bytes = KEY) -> None:
    keyfile.write_text(key.hex() + "\n")


def future(seconds: int = 3600) -> int:
    return int(time.time()) + seconds


def mandate_path(store, home, mandate_id):
    return Path(home) / store.state / "mandates" / f"{mandate_id}.json"


def test_a_mandate_is_made_listed_and_revoked(keyfile, home):
    with_key(keyfile)
    body = mandate_store.create(EXAMPLE, home, FIELDS, future())
    assert [m["id"] for m in mandate_store.active(EXAMPLE, home)] == [body["id"]]
    assert {k: body[k] for k in FIELDS} == FIELDS
    assert mandate_store.revoke(EXAMPLE, home, body["id"]) == {"revoked": body["id"]}
    assert mandate_store.active(EXAMPLE, home) == []
    assert mandate_store.revoke(EXAMPLE, home, body["id"]) == {"revoked": body["id"], "note": "it was not in force"}
    events = (home / "example-access" / "mandates.jsonl").read_text().splitlines()
    assert [json.loads(line)["event"] for line in events] == ["made", "revoked"]


def test_the_first_mandate_makes_the_key_in_the_keychain(keyfile, home):
    assert mandate_store.key(EXAMPLE, home) is None
    body = mandate_store.create(EXAMPLE, home, FIELDS, future())
    assert re.fullmatch(r"[0-9a-f]{64}", keyfile.read_text().strip())
    assert [m["id"] for m in mandate_store.active(EXAMPLE, home)] == [body["id"]]


def test_a_mandate_ends_when_its_card_said(keyfile, home):
    with_key(keyfile)
    end = future(600)
    mandate_store.create(EXAMPLE, home, FIELDS, end)
    assert mandate_store.active(EXAMPLE, home, now=end - 1)
    assert mandate_store.active(EXAMPLE, home, now=end) == []


def test_a_mandate_whose_end_has_passed_is_refused(keyfile, home):
    with_key(keyfile)
    with pytest.raises(StoreError, match="already passed"):
        mandate_store.create(EXAMPLE, home, FIELDS, 1)
    assert mandate_store.active(EXAMPLE, home) == []
    assert not (home / "example-access" / "mandates").exists()


def test_a_mandate_cannot_outlast_the_ceiling(keyfile, home):
    with_key(keyfile)
    ceiling = EXAMPLE.max_days * mandate_store.DAY
    with pytest.raises(StoreError, match="at most 30 days"):
        mandate_store.create(EXAMPLE, home, FIELDS, future(ceiling + 3600))
    assert mandate_store.active(EXAMPLE, home) == []
    assert mandate_store.create(EXAMPLE, home, FIELDS, future(ceiling - 60))["expires"]


def test_an_edited_mandate_is_not_in_force(keyfile, home):
    with_key(keyfile)
    body = mandate_store.create(EXAMPLE, home, FIELDS, future())
    path = mandate_path(EXAMPLE, home, body["id"])
    edited = json.loads(path.read_text())
    edited["classes"] = ["create", "routine"]
    path.write_text(json.dumps(edited))
    assert mandate_store.active(EXAMPLE, home) == []


def test_a_mandate_file_under_another_id_is_not_in_force(keyfile, home):
    with_key(keyfile)
    body = mandate_store.create(EXAMPLE, home, FIELDS, future())
    other = "m00000000"
    mandate_path(EXAMPLE, home, other).write_text(mandate_path(EXAMPLE, home, body["id"]).read_text())
    head = json.loads((home / "example-access" / "head.json").read_text())
    head["active"] = [other]
    head["mac"] = mandate_store.mac(KEY, "example-mandate-head", head)
    (home / "example-access" / "head.json").write_text(json.dumps(head))
    assert mandate_store.active(EXAMPLE, home) == []


def test_an_edited_head_puts_nothing_in_force(keyfile, home):
    with_key(keyfile)
    mandate_store.create(EXAMPLE, home, FIELDS, future())
    head = home / "example-access" / "head.json"
    data = json.loads(head.read_text())
    data["active"].append("m00000000")
    head.write_text(json.dumps(data))
    assert mandate_store.active(EXAMPLE, home) == []


def test_history_is_not_authoritative(keyfile, home):
    with_key(keyfile)
    body = mandate_store.create(EXAMPLE, home, FIELDS, future())
    mandate_store.revoke(EXAMPLE, home, body["id"])
    with open(home / "example-access" / "mandates.jsonl", "a") as handle:
        handle.write(json.dumps({"event": "made", "mandate": body["id"], "time": int(time.time())}) + "\n")
    assert mandate_store.active(EXAMPLE, home) == []
    (home / "example-access" / "mandates.jsonl").unlink()
    assert mandate_store.active(EXAMPLE, home) == []


def test_without_a_key_nothing_is_in_force(keyfile, home):
    with_key(keyfile)
    mandate_store.create(EXAMPLE, home, FIELDS, future())
    keyfile.unlink()
    assert mandate_store.active(EXAMPLE, home) == []
    assert mandate_store.revoke(EXAMPLE, home, "m00000000") == {
        "revoked": "m00000000", "note": "no mandate key: none was in force"}


def test_a_replaced_key_puts_nothing_in_force(keyfile, home):
    with_key(keyfile)
    mandate_store.create(EXAMPLE, home, FIELDS, future())
    with_key(keyfile, bytes(reversed(range(32))))
    assert mandate_store.active(EXAMPLE, home) == []


@pytest.mark.parametrize("stored", ["short", "AB" * 32, "zz" * 32, "ab" * 33])
def test_the_key_is_64_hex_characters(keyfile, stored):
    keyfile.write_text(stored)
    assert mandate_store.key(EXAMPLE, "x") is None


def test_the_key_is_read_every_time(keyfile, home):
    with_key(keyfile)
    assert mandate_store.key(EXAMPLE, home) == KEY
    keyfile.unlink()
    assert mandate_store.key(EXAMPLE, home) is None
    with_key(keyfile, b"\x01" * 32)
    assert mandate_store.key(EXAMPLE, home) == b"\x01" * 32


def test_a_key_present_but_unreadable_is_never_written_over(tmp_path, monkeypatch, home):
    calls = tmp_path / "calls"
    cli = tmp_path / "secret"
    cli.write_text(f"#!/bin/sh\necho \"$1\" >> {calls}\n[ \"$1\" = show ] && exit 0\nexit 1\n")
    cli.chmod(0o755)
    monkeypatch.setattr(mandate_store, "SECRET", cli)
    assert mandate_store.key(EXAMPLE, home, create=True) is None
    with pytest.raises(StoreError, match="could not be read; nothing was made"):
        mandate_store.create(EXAMPLE, home, FIELDS, future())
    assert "set" not in calls.read_text().split()
    assert not (home / "example-access" / "mandates").exists()


def test_a_missing_secret_cli_leaves_no_key(tmp_path, monkeypatch, home):
    monkeypatch.setattr(mandate_store, "SECRET", tmp_path / "absent")
    assert mandate_store.key(EXAMPLE, home) is None
    with pytest.raises(StoreError, match="could not be read; nothing was made"):
        mandate_store.create(EXAMPLE, home, FIELDS, future())
    with pytest.raises(StoreError, match="the secret CLI is missing"):
        mandate_store.call_secret(EXAMPLE, home, "get")


def test_the_cli_is_asked_for_the_stores_item_and_scope(tmp_path, monkeypatch):
    log = tmp_path / "log"
    keyfile = tmp_path / "keyfile"
    monkeypatch.setattr(mandate_store, "SECRET", fake_cli(tmp_path / "secret", keyfile, log))
    mandate_store.key(SEND, tmp_path / "Work Profile")
    assert log.read_text().split() == ["get", "SEND_MANDATE_KEY_WORK_PROFILE", "-p", "hermes",
                                       "--scope", "send-access"]
    assert mandate_store.vault_name(EXAMPLE, Path.home() / ".hermes") == "EXAMPLE_MANDATE_KEY_DEFAULT"
    assert mandate_store.vault_name(EXAMPLE, "/") == "EXAMPLE_MANDATE_KEY_DEFAULT"


def test_the_key_is_stored_with_its_note(tmp_path, monkeypatch, home):
    log = tmp_path / "log"
    keyfile = tmp_path / "keyfile"
    monkeypatch.setattr(mandate_store, "SECRET", fake_cli(tmp_path / "secret", keyfile, log))
    mandate_store.create(SEND, home, FIELDS, future())
    stored = [line for line in log.read_text().splitlines() if line.startswith("set ")]
    assert stored == ["set SEND_MANDATE_KEY_PROFILE -p hermes --scope send-access -D key -j "
                      "send-access mandate MAC key --stdin"]


def test_two_stores_do_not_see_each_other(keyfile, home):
    with_key(keyfile)
    a = mandate_store.create(EXAMPLE, home, FIELDS, future())
    b = mandate_store.create(SEND, home, FIELDS, future())
    assert a["id"].startswith("m") and b["id"].startswith("s")
    assert [m["id"] for m in mandate_store.active(EXAMPLE, home)] == [a["id"]]
    assert [m["id"] for m in mandate_store.active(SEND, home)] == [b["id"]]
    with pytest.raises(StoreError, match="an id like s1a2b3c4d"):
        mandate_store.revoke(SEND, home, a["id"])


def test_a_body_made_for_one_kind_does_not_verify_as_another(keyfile, home):
    with_key(keyfile)
    body = mandate_store.create(EXAMPLE, home, FIELDS, future())
    # The same file and head under the send store's directory, same key: only the kind differs.
    (home / "send-access" / "mandates").mkdir(parents=True)
    mandate_path(SEND, home, body["id"]).write_text(mandate_path(EXAMPLE, home, body["id"]).read_text())
    (home / "send-access" / "head.json").write_text((home / "example-access" / "head.json").read_text())
    assert mandate_store.load(SEND, home, KEY, body["id"]) is None
    assert mandate_store.active_ids(SEND, home, KEY) == []
    assert mandate_store.load(EXAMPLE, home, KEY, body["id"]) == body
    assert mandate_store.mac(KEY, "example-mandate", body) != mandate_store.mac(KEY, "send-mandate", body)


@pytest.mark.parametrize("bad", [None, 7, "", "m1a2b3c4", "m1a2b3c4de", "M1a2b3c4d", "s1a2b3c4d", "mg1a2b3c4", "x" * 9])
def test_a_revoke_needs_an_id_of_the_stores_shape(keyfile, home, bad):
    assert not mandate_store.valid_id(EXAMPLE, bad)
    with pytest.raises(StoreError, match="an id like m1a2b3c4d"):
        mandate_store.revoke(EXAMPLE, home, bad)


def test_an_id_is_its_prefix_and_eight_hex_digits(keyfile, home):
    with_key(keyfile)
    for store, prefix in ((EXAMPLE, "m"), (SEND, "s")):
        body = mandate_store.create(store, home, FIELDS, future())
        assert re.fullmatch(prefix + "[0-9a-f]{8}", body["id"])
        assert mandate_store.valid_id(store, body["id"])


def test_files_are_private(keyfile, home):
    with_key(keyfile)
    body = mandate_store.create(EXAMPLE, home, FIELDS, future())
    folder = home / "example-access"

    def mode(path):
        return stat.S_IMODE(os.stat(path).st_mode)

    assert mode(folder) == 0o700 and mode(folder / "mandates") == 0o700
    assert mode(mandate_path(EXAMPLE, home, body["id"])) == 0o600
    assert mode(folder / "head.json") == 0o600
    assert not [p for p in folder.rglob(".*.tmp")]


def test_the_head_lists_the_sorted_ids_and_is_signed(keyfile, home):
    with_key(keyfile)
    ids = [mandate_store.create(EXAMPLE, home, FIELDS, future())["id"] for _ in range(3)]
    head = json.loads((home / "example-access" / "head.json").read_text())
    assert head["active"] == sorted(ids) and set(head) == {"active", "time", "mac"}
    assert head["mac"] == mandate_store.mac(KEY, "example-mandate-head", head)


def format_mac(secret: bytes, kind: str, body: dict) -> str:
    """An independent implementation of the on-disk MAC contract."""
    text = json.dumps({"kind": kind, **{k: v for k, v in body.items() if k != "mac"}}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False)
    return hmac.new(secret, text.encode("utf-8"), hashlib.sha256).hexdigest()


def format_write(home: Path, ids: list[str], bodies: list[dict]) -> None:
    """The on-disk format: each mandate, the head and the history."""
    folder = home / "example-access"
    (folder / "mandates").mkdir(parents=True)
    for body in bodies:
        (folder / "mandates" / f"{body['id']}.json").write_text(json.dumps(body, ensure_ascii=False, indent=1))
    head = {"active": sorted(set(ids)), "time": int(time.time())}
    head["mac"] = format_mac(KEY, "example-mandate-head", head)
    (folder / "head.json").write_text(json.dumps(head, ensure_ascii=False, indent=1))
    with open(folder / "mandates.jsonl", "a", encoding="utf-8") as handle:
        for body in bodies:
            handle.write(json.dumps({"event": "made", "mandate": body["id"], "time": int(time.time())}) + "\n")


def format_body(mandate_id: str, purpose: str = "Run the release") -> dict:
    body = {"id": mandate_id, "created": int(time.time()), "expires": future(),
            "boards": [], "repos": [{"id": "R_app", "name": "me/app", "tier": "own"}], "parent": None,
            "classes": ["create", "routine"], "purpose": purpose}
    body["mac"] = format_mac(KEY, "example-mandate", body)
    return body


def test_mandates_written_in_the_on_disk_format_are_in_force(keyfile, home):
    with_key(keyfile)
    bodies = [format_body("m1a2b3c4d"), format_body("mdeadbeef", purpose="Ünïcode — 目的")]
    format_write(home, [b["id"] for b in bodies], bodies)
    assert mandate_store.active(EXAMPLE, home) == bodies
    assert mandate_store.revoke(EXAMPLE, home, "mdeadbeef") == {"revoked": "mdeadbeef"}
    assert [m["id"] for m in mandate_store.active(EXAMPLE, home)] == ["m1a2b3c4d"]


def test_a_created_mandate_matches_the_on_disk_format_and_mac(keyfile, home):
    with_key(keyfile)
    body = mandate_store.create(EXAMPLE, home, {**FIELDS, "purpose": "Ünïcode — 目的"}, future())
    stored = json.loads(mandate_path(EXAMPLE, home, body["id"]).read_text())
    assert stored == body and list(stored)[:3] == ["id", "created", "expires"]
    assert stored["mac"] == format_mac(KEY, "example-mandate", stored)
    head = json.loads((home / "example-access" / "head.json").read_text())
    assert head["active"] == [body["id"]]
    assert head["mac"] == format_mac(KEY, "example-mandate-head", head)
    assert re.fullmatch(r"m[0-9a-f]{8}", body["id"])
    history = json.loads((home / "example-access" / "mandates.jsonl").read_text())
    assert history["event"] == "made" and history["mandate"] == body["id"]
