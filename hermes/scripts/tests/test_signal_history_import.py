"""signal-history-import: the one-off copy of signal-access' state into signal-tools' layout.

Every state here is built in a temporary directory with made-up identifiers; the old mirror is
created by signal-access' own schema code, so the test follows that schema if it ever changes.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import stat
import sys
import time
from pathlib import Path

import pytest

HERMES = Path(__file__).resolve().parents[2]
SCRIPT = HERMES / "scripts" / "signal-history-import.py"
STORE = HERMES / "plugins" / "messaging" / "signal-access" / "store.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve their annotations through sys.modules
    spec.loader.exec_module(module)
    return module


S = _load("signal_history_import", SCRIPT)
STORE_MODULE = _load("signal_access_store_for_import_test", STORE)

ACCOUNT = "00000000-0000-4000-8000-00000000000a"
OTHER_ACCOUNT = "00000000-0000-4000-8000-000000000002"
PEER = "00000000-0000-4000-8000-000000000003"
FRIEND = "00000000-0000-4000-8000-000000000004"
GROUP = "group:" + "abcdefghij" * 4 + "abc"
FAKE_NUMBER = "+15555550100"
TIMED = 3_000


def _write_accounts(base: Path, accounts: list[dict]) -> None:
    data = base / "signal-cli" / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "accounts.json").write_text(json.dumps({"accounts": accounts, "version": 2}), encoding="utf-8")


def _build_old_state(base: Path) -> None:
    """signal-cli data plus a mirror written through signal-access' own schema."""
    _write_accounts(base, [{"path": "100001", "number": FAKE_NUMBER, "uuid": ACCOUNT.upper()}])
    cli = base / "signal-cli"
    os.chmod(cli, 0o700)
    (cli / "data" / "100001").write_text('{"registered": true}', encoding="utf-8")
    (cli / "data" / "link").symlink_to("accounts.json")
    attachments = cli / "attachments"
    attachments.mkdir()
    (attachments / "att1").write_bytes(b"\x00\x01attachment")
    os.chmod(attachments / "att1", 0o640)
    os.chmod(attachments, 0o750)

    conn = STORE_MODULE.connect(base / "mirror.db", write=True)
    conn.executescript(
        f"""
        INSERT INTO chats (id, kind, name, last_ts, updated) VALUES ('{PEER}', 'person', 'Peer', 5000, NULL);
        INSERT INTO chats (id, kind, name, last_ts, updated) VALUES ('{FRIEND}', 'person', 'Friend', NULL, NULL);
        INSERT INTO chats (id, kind, name, members, member, last_ts, updated)
            VALUES ('{GROUP}', 'group', 'Team', '["{PEER}"]', 0, 4000, 7);
        INSERT INTO messages (chat, author, ts, from_me, body, edited, received, mentions)
            VALUES ('{PEER}', '{PEER}', 1000, 0, 'edited body', 2000, 1500, '[]');
        INSERT INTO edits (author, ts, rev_ts, body, mentions) VALUES ('{PEER}', 1000, 1000, 'first body', NULL);
        INSERT INTO messages (chat, author, ts, kind, expires_in, received)
            VALUES ('{PEER}', '{PEER}', 2500, 'timer', 60, 2500);
        INSERT INTO messages (chat, author, ts, from_me, body, received)
            VALUES ('{PEER}', '{ACCOUNT}', {TIMED}, 1, 'no received', NULL);
        INSERT INTO messages (chat, author, ts, body, received) VALUES ('{GROUP}', '{FRIEND}', 4000, 'hi', 4001);
        INSERT INTO reactions (author, ts, reactor, emoji, at) VALUES ('{PEER}', 1000, '{FRIEND}', 'x', 9);
        INSERT INTO reactions (author, ts, reactor, emoji, at) VALUES ('{PEER}', 1000, '{PEER}', NULL, 9);
        INSERT INTO reactions (author, ts, reactor, emoji, at) VALUES ('{PEER}', 2500, '{PEER}', '', 9);
        INSERT INTO reactions (author, ts, reactor, emoji, at) VALUES ('{PEER}', {TIMED}, '{PEER}', 'y', NULL);
        INSERT INTO contacts (uuid, number, name, blocked, updated) VALUES ('{PEER}', '+15555550101', 'Peer', 0, 8);
        INSERT INTO contacts (uuid, name, blocked, updated) VALUES ('{FRIEND}', 'Friend', 1, NULL);
        """
    )
    STORE_MODULE.set_meta(conn, uuid=ACCOUNT, account=FAKE_NUMBER, groups_stale=1)
    conn.close()


@pytest.fixture
def old(tmp_path: Path) -> Path:
    base = tmp_path / "old"
    _build_old_state(base)
    return base


@pytest.fixture
def excluded() -> list[Path]:
    return []


def run(old: Path, tmp_path: Path, excluded: list[Path], *extra: str, label: str | None = None,
        loaded: bool = False, live_root: Path | None = None) -> int:
    argv = ["--from", str(old), "--state-dir", str(tmp_path / "state")]
    if label is not None:
        argv.append(f"--label={label}")
    return S.main(
        argv + list(extra),
        live_root=live_root or SCRIPT.parent,
        agent_loaded=lambda: loaded,
        exclude_backup=excluded.append,
        environ={},
    )


def snapshot(root: Path) -> dict[str, tuple[int, bytes | str]]:
    """Every path under root with its mode and content (link target for a link)."""
    seen = {}
    for path in sorted(root.rglob("*")):
        rel = str(path.relative_to(root))
        if path.is_symlink():
            seen[rel] = (0, os.readlink(path))
        elif path.is_file():
            seen[rel] = (stat.S_IMODE(path.stat().st_mode), path.read_bytes())
        else:
            seen[rel] = (stat.S_IMODE(path.stat().st_mode), "")
    return seen


def rows(db: Path, sql: str) -> list[tuple]:
    conn = sqlite3.connect(db)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_import_writes_the_new_layout(old, tmp_path, excluded, capsys):
    before = int(time.time() * 1000)
    assert run(old, tmp_path, excluded) == 0
    after = int(time.time() * 1000)

    root = tmp_path / "state"
    target = root / "default"
    db = target / "mirror.sqlite"
    assert sorted(p.name for p in target.iterdir()) == ["mirror.sqlite", "signal-cli"]
    assert mode(root) == 0o700 and mode(target) == 0o700 and mode(db) == 0o600
    assert excluded == [root]

    conn = sqlite3.connect(db)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    finally:
        conn.close()
    assert not (target / "mirror.sqlite-wal").exists()

    counts = {t: rows(db, f"SELECT COUNT(*) FROM {t}")[0][0]
              for t in ("chats", "messages", "edits", "reactions", "deleted", "contacts", "meta")}
    assert counts == {"chats": 3, "messages": 4, "edits": 1, "reactions": 2, "deleted": 0,
                      "contacts": 2, "meta": 1}

    updated = dict(rows(db, "SELECT id, updated FROM chats"))
    assert updated[PEER] == 5000 and updated[GROUP] == 7
    assert before <= updated[FRIEND] <= after
    received = dict(rows(db, "SELECT ts, received FROM messages"))
    assert received[TIMED] == TIMED and received[1000] == 1500
    assert rows(db, "SELECT kind, expires_in FROM messages WHERE ts = 2500") == [("timer", 60)]
    assert rows(db, "SELECT edited, mentions FROM messages WHERE ts = 1000") == [(2000, "[]")]
    assert rows(db, "SELECT rev_ts, body FROM edits") == [(1000, "first body")]
    reactions = dict(rows(db, "SELECT emoji, at FROM reactions"))
    assert set(reactions) == {"x", "y"} and reactions["x"] == 9
    assert before <= reactions["y"] <= after
    contacts = dict(rows(db, "SELECT uuid, updated FROM contacts"))
    assert contacts[PEER] == 8 and before <= contacts[FRIEND] <= after
    assert rows(db, f"SELECT member FROM chats WHERE id = '{GROUP}'") == [(0,)]
    assert rows(db, "SELECT key, value FROM meta") == [("account_uuid", ACCOUNT)]

    out = capsys.readouterr().out
    assert "chats: 3" in out and "reactions: 2" in out and "reactions skipped (no emoji): 2" in out
    assert FAKE_NUMBER not in out and ACCOUNT not in out


def test_new_schema_is_exactly_the_ddl(old, tmp_path, excluded):
    assert run(old, tmp_path, excluded) == 0
    db = tmp_path / "state" / "default" / "mirror.sqlite"
    stored = {sql for (sql,) in rows(db, "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")}
    assert stored == set(S.DDL)
    tables = {n for (n,) in rows(db, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert tables == {"chats", "messages", "edits", "reactions", "deleted", "contacts", "meta"}
    indexes = {n for (n,) in rows(db, "SELECT name FROM sqlite_master WHERE type = 'index' "
                                       "AND name NOT LIKE 'sqlite_%'")}
    assert indexes == {"messages_chat", "messages_edited", "edits_rev", "contacts_number", "messages_ts"}


def test_signal_cli_is_copied_and_the_old_state_stays(old, tmp_path, excluded):
    cli_before = snapshot(old / "signal-cli")
    mirror_before = (old / "mirror.db").read_bytes()
    assert run(old, tmp_path, excluded) == 0

    copied = tmp_path / "state" / "default" / "signal-cli"
    assert snapshot(copied) == cli_before
    assert (copied / "data" / "link").is_symlink()
    assert mode(copied / "attachments") == 0o750 and mode(copied / "attachments" / "att1") == 0o640
    assert snapshot(old / "signal-cli") == cli_before
    assert (old / "mirror.db").read_bytes() == mirror_before


def test_old_mirror_without_mentions_columns_still_imports(old, tmp_path, excluded):
    conn = sqlite3.connect(old / "mirror.db")
    conn.execute("ALTER TABLE messages DROP COLUMN mentions")
    conn.execute("ALTER TABLE edits DROP COLUMN mentions")
    conn.commit()
    conn.close()
    assert run(old, tmp_path, excluded) == 0
    db = tmp_path / "state" / "default" / "mirror.sqlite"
    assert rows(db, "SELECT COUNT(*) FROM messages WHERE mentions IS NOT NULL") == [(0,)]
    assert rows(db, "SELECT COUNT(*) FROM messages") == [(4,)]


def test_label_selects_the_directory(old, tmp_path, excluded):
    assert run(old, tmp_path, excluded, label="work_1") == 0
    assert (tmp_path / "state" / "work_1" / "mirror.sqlite").is_file()
    assert not (tmp_path / "state" / "default").exists()


def test_dry_run_writes_nothing(old, tmp_path, excluded, capsys):
    old_before = snapshot(old)
    assert run(old, tmp_path, excluded, "--dry-run") == 0
    out = capsys.readouterr().out
    assert "dry run" in out and "messages: 4" in out and "reactions skipped (no emoji): 2" in out
    assert not (tmp_path / "state").exists()
    assert excluded == []
    after = snapshot(old)
    assert {k: v for k, v in after.items() if not k.startswith("mirror.db-")} == old_before


def _refused(code: int, tmp_path: Path, capsys, fragment: str) -> None:
    assert code == 2
    err = capsys.readouterr().err
    assert fragment in err and err.count("\n") == 1
    assert FAKE_NUMBER not in err and ACCOUNT not in err
    assert not (tmp_path / "state" / "default").exists()


def test_refuses_while_the_old_agent_is_loaded(old, tmp_path, excluded, capsys):
    _refused(run(old, tmp_path, excluded, loaded=True), tmp_path, capsys, "still loaded")


def test_refuses_outside_the_live_checkout(old, tmp_path, excluded, capsys):
    _refused(run(old, tmp_path, excluded, live_root=tmp_path / "live"), tmp_path, capsys,
             "never a task worktree")


def test_refuses_an_existing_target(old, tmp_path, excluded, capsys):
    (tmp_path / "state" / "default").mkdir(parents=True)
    assert run(old, tmp_path, excluded) == 2
    assert "already exists" in capsys.readouterr().err
    assert list((tmp_path / "state" / "default").iterdir()) == []


def test_refuses_a_symlink_as_target(old, tmp_path, excluded, capsys):
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "default").symlink_to(tmp_path / "elsewhere")
    assert run(old, tmp_path, excluded) == 2
    assert "already exists" in capsys.readouterr().err
    assert not (tmp_path / "elsewhere").exists()


@pytest.mark.parametrize("label", ["", "Upper", "-dash", "trailing_", "_lead", "a" * 25, "has space", "../x"])
def test_refuses_a_bad_label(old, tmp_path, excluded, capsys, label):
    code = run(old, tmp_path, excluded, label=label)
    assert code == 2
    assert "label" in capsys.readouterr().err
    assert not (tmp_path / "state").exists()


def test_refuses_a_mismatching_meta_uuid(old, tmp_path, excluded, capsys):
    conn = sqlite3.connect(old / "mirror.db")
    conn.execute("UPDATE meta SET value = ? WHERE key = 'uuid'", (OTHER_ACCOUNT,))
    conn.commit()
    conn.close()
    _refused(run(old, tmp_path, excluded), tmp_path, capsys, "different account")
    assert not (tmp_path / "state").exists()


def test_meta_uuid_is_compared_case_insensitively(old, tmp_path, excluded):
    conn = sqlite3.connect(old / "mirror.db")
    conn.execute("UPDATE meta SET value = ? WHERE key = 'uuid'", (ACCOUNT.upper(),))
    conn.commit()
    conn.close()
    assert run(old, tmp_path, excluded) == 0


@pytest.mark.parametrize("update, fragment", [
    ("UPDATE messages SET kind = 'bogus' WHERE ts = 1000", "messages=1"),
    ("UPDATE messages SET from_me = 2", "messages=4"),
    ("UPDATE chats SET kind = 'channel'", "chats=3"),
    ("UPDATE chats SET member = 5 WHERE id LIKE 'group:%'", "chats=1"),
    ("UPDATE contacts SET blocked = 7", "contacts=2"),
])
def test_refuses_rows_the_new_schema_would_reject(old, tmp_path, excluded, capsys, update, fragment):
    conn = sqlite3.connect(old / "mirror.db")
    conn.execute(update)
    conn.commit()
    conn.close()
    _refused(run(old, tmp_path, excluded), tmp_path, capsys, fragment)
    assert not (tmp_path / "state").exists()


def test_refuses_without_accounts_json(old, tmp_path, excluded, capsys):
    (old / "signal-cli" / "data" / "accounts.json").unlink()
    _refused(run(old, tmp_path, excluded), tmp_path, capsys, "no linked account")


@pytest.mark.parametrize("accounts", [
    [],
    [{"uuid": ACCOUNT}, {"uuid": OTHER_ACCOUNT}],
    [{"path": "1", "number": FAKE_NUMBER}],
    [{"uuid": "not-a-uuid"}],
])
def test_refuses_anything_but_one_account_with_a_uuid(old, tmp_path, excluded, capsys, accounts):
    _write_accounts(old, accounts)
    _refused(run(old, tmp_path, excluded), tmp_path, capsys, "account")


def test_refuses_without_the_old_mirror(old, tmp_path, excluded, capsys):
    (old / "mirror.db").unlink()
    _refused(run(old, tmp_path, excluded), tmp_path, capsys, "mirror.db is missing")


def test_failure_mid_copy_removes_the_label_directory(old, tmp_path, excluded, monkeypatch, capsys):
    real = S.copy_table
    calls = []

    def flaky(conn, spec, now):
        calls.append(spec.name)
        if len(calls) == 3:
            raise sqlite3.OperationalError("injected failure")
        real(conn, spec, now)

    monkeypatch.setattr(S, "copy_table", flaky)
    assert run(old, tmp_path, excluded) == 1
    assert calls == ["chats", "messages", "edits"]
    assert "failed" in capsys.readouterr().err
    assert (tmp_path / "state").is_dir()
    assert list((tmp_path / "state").iterdir()) == []
    assert excluded == []


def test_failure_while_copying_signal_cli_removes_the_label_directory(old, tmp_path, excluded, monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("injected failure")

    monkeypatch.setattr(S.shutil, "copytree", boom)
    assert run(old, tmp_path, excluded) == 1
    assert list((tmp_path / "state").iterdir()) == []


def test_state_root_follows_xdg_then_home(tmp_path):
    assert S.resolve_state_root("/explicit", {"XDG_STATE_HOME": "/xdg"}) == Path("/explicit")
    assert S.resolve_state_root(None, {"XDG_STATE_HOME": "/xdg"}) == Path("/xdg/signal-tools")
    assert S.resolve_state_root(None, {}) == Path.home() / ".local" / "state" / "signal-tools"
    assert S.resolve_state_root(None, {"XDG_STATE_HOME": ""}) == Path.home() / ".local" / "state" / "signal-tools"


def test_live_checkout_check_follows_links(tmp_path):
    live = tmp_path / "live"
    (live / "scripts").mkdir(parents=True)
    script = live / "scripts" / "x.py"
    script.write_text("", encoding="utf-8")
    alias = tmp_path / "alias"
    alias.symlink_to(live)
    assert S.in_live_checkout(script, alias)
    assert not S.in_live_checkout(script, tmp_path / "other")


def test_agent_probe_reads_the_launchctl_exit_status(monkeypatch):
    seen = []

    class Done:
        returncode = 0

    def fake(cmd, **kwargs):
        seen.append(cmd)
        return Done()

    monkeypatch.setattr(S.subprocess, "run", fake)
    assert S.agent_is_loaded() is True
    assert seen[0][:2] == ["launchctl", "print"] and seen[0][2].endswith("/" + S.OLD_AGENT)
    Done.returncode = 113
    assert S.agent_is_loaded() is False


def test_script_is_executable():
    assert os.access(SCRIPT, os.X_OK)
    assert SCRIPT.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3\n")
