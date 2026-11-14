"""mandate_ledger: the use ledger of a mandate is counted, anchored and fails closed the same way for every
plugin."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import threading
import time

import pytest

if "hermes_mandate_ledger" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "hermes_mandate_ledger",
        Path(__file__).resolve().parents[1] / "mandate_ledger.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["hermes_mandate_ledger"] = module
    spec.loader.exec_module(module)
mandate_ledger = sys.modules["hermes_mandate_ledger"]
mandate_store = mandate_ledger.mandate_store

KEY = bytes(range(32))
KIND = "demo-use"
WINDOW = 3600
LIMIT = 3
USED_UP = mandate_ledger.UsedUp(LIMIT)
STORE = mandate_store.Store(state="demo-access", key_prefix="DEMO_MANDATE_KEY_", scope="demo-access",
                            mac_kind="demo-mandate", key_note="demo-access mandate MAC key", error=OSError)
M1, M2 = "m1a2b3c4d", "m5e6f7a8b"


@pytest.fixture
def home(tmp_path):
    return tmp_path / "profile"


@pytest.fixture
def folder(home):
    path = home / STORE.state
    path.mkdir(parents=True)
    return path


def ledger(home) -> Path:
    return home / STORE.state / "uses.jsonl"


def rows(home) -> list[dict]:
    return [json.loads(line) for line in ledger(home).read_text().splitlines()]


def count(home, mandate_id=M1, now=None, secret=KEY, kind=KIND):
    return mandate_ledger.count(STORE, home, secret, kind, mandate_id, time.time() if now is None else now,
                                WINDOW, USED_UP)


def anchor(home, mandate_id=M1, at=None, secret=KEY, kind=KIND):
    mandate_ledger.anchor(STORE, home, secret, kind, mandate_id, int(time.time()) if at is None else at)


def take(home, fits=lambda used: None if used < LIMIT else "used up", mandate_id=M1, now=None, **kwargs):
    return mandate_ledger.take(STORE, home, KEY, KIND, mandate_id, time.time() if now is None else now,
                               WINDOW, USED_UP, fits, **kwargs)


def put(home, *entries) -> None:
    ledger(home).write_text("".join(json.dumps(entry) + "\n" for entry in entries))


def is_used_up(value) -> bool:
    return value is USED_UP and isinstance(value, mandate_ledger.UsedUp) and value == LIMIT


# --- counting -------------------------------------------------------------------------------------

def test_an_anchored_mandate_counts_its_uses(home, folder):
    anchor(home)
    assert count(home) == 0
    now = time.time()
    assert take(home, now=now) is None and take(home, now=now) is None
    assert count(home, now=now) == 2
    opening, first, second = rows(home)
    assert set(opening) == {"mandate", "time", "open", "mac"} and opening["open"] is True
    assert set(first) == set(second) == {"mandate", "time", "mac"} and first["time"] == int(now)
    assert first["mac"] == mandate_store.mac(KEY, KIND, {"mandate": M1, "time": int(now)})
    assert opening["mac"] == mandate_store.mac(KEY, KIND, {"mandate": M1, "time": opening["time"], "open": True})


def test_the_ledger_is_one_file_of_the_state_dir_made_private(home, folder):
    anchor(home)
    assert ledger(home).name == "uses.jsonl"
    assert stat.S_IMODE(os.stat(ledger(home)).st_mode) == 0o600


def test_a_use_of_another_mandate_or_another_kind_counts_for_nothing(home, folder):
    anchor(home)
    anchor(home, M2)
    now = int(time.time())
    assert take(home, mandate_id=M2, now=now) is None
    other_kind = {"mandate": M1, "time": now}
    with open(ledger(home), "a") as handle:
        handle.write(json.dumps({**other_kind, "mac": mandate_store.mac(KEY, "other-use", other_kind)}) + "\n")
    assert count(home, M1, now) == 0
    assert count(home, M2, now) == 1


def test_rows_that_are_not_authentic_count_for_nothing(home, folder):
    anchor(home)
    now = int(time.time())
    use = {"mandate": M1, "time": now}
    older = {"mandate": M1, "time": now - 5}
    extra = {"mandate": M1, "time": now, "note": "x"}
    flag = {"mandate": M1, "time": True}
    raw = [{**use, "mac": "0" * 64},                                                        # a bad MAC
           {**use, "mac": mandate_store.mac(b"\x01" * 32, KIND, use)},                      # another key
           {**older, "time": now, "mac": mandate_store.mac(KEY, KIND, older)},              # a changed time
           {**extra, "mac": mandate_store.mac(KEY, KIND, extra)},                           # a key too many
           {**flag, "mac": mandate_store.mac(KEY, KIND, flag)}]                             # a bool time
    with open(ledger(home), "a") as handle:
        for entry in raw:
            handle.write(json.dumps(entry) + "\n")
        handle.write("not json\n[1, 2]\n\n")
    assert count(home, now=now) == 0


def test_a_torn_last_line_is_skipped_and_the_valid_rows_still_count(home, folder):
    anchor(home)
    assert take(home) is None
    with open(ledger(home), "a") as handle:
        handle.write('{"mandate": "' + M1)
    assert count(home) == 1


def test_a_use_leaves_the_count_when_the_window_passes(home, folder):
    anchor(home)
    at = 1_000_000
    assert [take(home, now=at) for _ in range(LIMIT)] == [None] * LIMIT
    assert take(home, now=at + WINDOW - 1) == "used up"
    assert count(home, now=at + WINDOW - 1) == LIMIT
    assert count(home, now=at + WINDOW) == 0
    assert take(home, now=at + WINDOW) is None


# --- the ledger fails closed ----------------------------------------------------------------------

def test_without_a_key_everything_is_used_up(home, folder):
    anchor(home)
    assert is_used_up(count(home, secret=None))


def test_a_mandate_without_an_opening_row_is_used_up(home, folder):
    assert is_used_up(count(home))          # no ledger yet
    ledger(home).write_text("")
    assert is_used_up(count(home))          # emptied
    anchor(home, M2)
    assert is_used_up(count(home))          # another mandate's opening row anchors only that one
    assert count(home, M2) == 0


def test_a_deleted_or_emptied_ledger_blocks_instead_of_resetting_the_count(home, folder):
    anchor(home)
    assert take(home) is None
    ledger(home).write_text("")
    assert is_used_up(count(home))
    ledger(home).unlink()
    assert is_used_up(count(home))


def test_forged_opening_rows_do_not_anchor(home, folder):
    now = int(time.time())

    def opening(mandate_id, key=KEY, **over):
        body = {"mandate": mandate_id, "time": now, "open": True, **over}
        return {**body, "mac": mandate_store.mac(key, KIND, body)}

    bare = {"mandate": M1, "time": now}
    other_kind = {"mandate": M1, "time": now, "open": True}
    put(home,
        {"mandate": M1, "time": now, "open": True, "mac": "0" * 64},
        opening(M1, key=b"\x01" * 32),
        opening(M2),                                                       # another mandate's own
        opening(M1, extra="x"),
        {**opening(M1), "open": False},                                    # a flag the MAC does not cover
        {**opening(M1), "time": now + 1},                                  # a time the MAC does not cover
        {**bare, "mac": mandate_store.mac(KEY, KIND, bare)},               # a use row is not an opening
        {**opening(M1), "open": 1},
        {**other_kind, "mac": mandate_store.mac(KEY, "other-use", other_kind)})   # another kind's
    assert is_used_up(count(home, now=now))


def test_a_ledger_that_is_a_link_blocks_and_nothing_is_written_through_it(home, folder, tmp_path):
    anchor(home)
    copy = tmp_path / "copy.jsonl"
    copy.write_text(ledger(home).read_text())
    ledger(home).unlink()
    ledger(home).symlink_to(copy)
    assert is_used_up(count(home))
    assert take(home) == "used up" and copy.read_text().count("\n") == 1
    with pytest.raises(OSError):
        anchor(home, M2)
    assert copy.read_text().count("\n") == 1 and ledger(home).is_symlink()


def test_a_dangling_link_is_not_followed_to_create_a_file(home, folder, tmp_path):
    ledger(home).symlink_to(tmp_path / "elsewhere.jsonl")
    with pytest.raises(OSError):
        anchor(home)
    assert not (tmp_path / "elsewhere.jsonl").exists()


def test_a_ledger_that_is_not_a_plain_file_of_this_user_blocks(home, folder, monkeypatch):
    anchor(home)
    original = ledger(home).read_text()
    real_getuid = os.getuid
    monkeypatch.setattr(os, "getuid", lambda: real_getuid() + 1)   # the file is now another user's
    assert is_used_up(count(home))
    with pytest.raises(OSError, match="not a plain file of this user"):
        anchor(home, M2)
    monkeypatch.setattr(os, "getuid", real_getuid)
    assert ledger(home).read_text() == original
    ledger(home).unlink()
    ledger(home).mkdir()   # a directory
    assert is_used_up(count(home))
    ledger(home).rmdir()
    os.mkfifo(ledger(home))   # a pipe: never opened for reading to block on
    assert is_used_up(count(home))


def test_an_unreadable_ledger_blocks(home, folder):
    anchor(home)
    ledger(home).chmod(0)
    try:
        assert is_used_up(count(home))
    finally:
        ledger(home).chmod(0o600)


# --- take -----------------------------------------------------------------------------------------

def test_take_writes_nothing_when_the_use_does_not_fit(home, folder):
    anchor(home)
    before = ledger(home).read_text()
    assert take(home, fits=lambda used: "no") == "no"
    assert ledger(home).read_text() == before


def test_take_hands_fits_a_count_that_is_told_from_a_real_one(home, folder):
    seen = []
    anchor(home)
    assert take(home, fits=lambda used: seen.append(used)) is None
    ledger(home).unlink()
    assert take(home, fits=lambda used: seen.append(used) or "used up") == "used up"
    assert seen[0] == 0 and not isinstance(seen[0], mandate_ledger.UsedUp)
    assert is_used_up(seen[1])
    assert not ledger(home).exists()


def test_take_writes_through_the_writer_it_is_given(home, folder):
    anchor(home)
    written = []
    assert take(home, write=written.append) is None
    row, = written
    assert set(row) == {"mandate", "time", "mac"} and len(rows(home)) == 1   # only the opening row is on disk


def test_a_row_that_cannot_be_written_is_an_error_not_a_count(home, folder):
    anchor(home)

    def fail(entry):
        raise OSError("disk full")

    with pytest.raises(OSError, match="disk full"):
        take(home, write=fail)
    assert count(home) == 0


def test_take_counts_a_weight_as_that_many_identical_rows_in_one_write(home, folder, monkeypatch):
    anchor(home)
    now = time.time()
    writes = []
    real = os.write
    monkeypatch.setattr(os, "write", lambda fd, data: writes.append(bytes(data)) or real(fd, data))
    fits = lambda used: None if used + 2 <= LIMIT else "full"   # noqa: E731 - the caller's closure knows the weight
    assert take(home, fits=fits, now=now, weight=2) is None
    assert count(home, now=now) == 2 and len(rows(home)) == 3
    first, second = rows(home)[1:]
    assert first == second and set(first) == {"mandate", "time", "mac"}
    assert first["mac"] == mandate_store.mac(KEY, KIND, {"mandate": M1, "time": int(now)})
    assert len(writes) == 1 and writes[0].count(b"\n") == 2


def test_take_refuses_a_weight_that_does_not_fit_and_writes_nothing(home, folder):
    anchor(home)
    now = time.time()
    assert take(home, now=now, weight=2) is None
    before = ledger(home).read_text()
    fits = lambda used: None if used + 2 <= LIMIT else "full"   # noqa: E731
    assert take(home, fits=fits, now=now, weight=2) == "full"
    assert ledger(home).read_text() == before and count(home, now=now) == 2
    assert take(home, fits=lambda used: None if used + 1 <= LIMIT else "full", now=now) is None


def test_a_weight_is_a_whole_number_of_at_least_one(home, folder):
    anchor(home)
    for bad in (0, -1, True, 1.5, "2", None):
        with pytest.raises(ValueError, match="weight"):
            take(home, weight=bad)
    assert count(home) == 0


def test_take_hands_each_row_of_a_weight_to_the_writer_it_is_given(home, folder):
    anchor(home)
    written = []
    assert take(home, write=written.append, weight=3) is None
    assert len(written) == 3 and written[0] == written[1] == written[2] and len(rows(home)) == 1


def test_threads_racing_the_last_slots_win_exactly_the_limit_times(home, folder):
    anchor(home)
    now = time.time()
    gate = threading.Barrier(10)
    results = []

    def go():
        gate.wait()
        with mandate_store.locked(STORE, home):
            results.append(take(home, now=now))

    threads = [threading.Thread(target=go) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(results) == 10 and results.count(None) == LIMIT
    assert count(home, now=now) == LIMIT and len(rows(home)) == 1 + LIMIT
