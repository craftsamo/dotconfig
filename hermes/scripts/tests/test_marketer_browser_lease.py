"""browser-lease.py only serializes Marketer's own browser operations across
sessions/tasks: it never launches a browser, touches credentials, approves a
draft, or manipulates an account, and it proves nothing about browser
content. Exercised as a real subprocess so exit codes and stdout JSON are
verified exactly as a caller would see them, and so the concurrent-acquire
test exercises genuine cross-process flock contention, not thread timing."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / \
    "profiles/marketer/skills/marketer-pipeline/scripts/browser-lease.py"

LEASE_NAME = "marketing-browser-lease.json"
GUARD_NAME = "marketing-browser-lease.guard"

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_BLOCKED = 3
EXIT_WRONG_OWNER = 4
EXIT_UNTRUSTED = 5


def run(*args):
    proc = subprocess.run([sys.executable, str(SCRIPT), *args],
                           capture_output=True, text=True, timeout=20)
    assert proc.stderr == "", proc.stderr
    lines = proc.stdout.splitlines()
    assert len(lines) == 1, proc.stdout  # exactly one JSON line
    parsed = json.loads(lines[0])
    # Genuinely compact: re-serializing the parsed object the same way
    # reproduces the exact line, proving no extra whitespace was emitted.
    assert json.dumps(parsed, sort_keys=True, separators=(",", ":")) == lines[0]
    return proc.returncode, parsed


def acquire(home, owner):
    return run("acquire", "--owner", owner, "--home", str(home))


def status(home):
    return run("status", "--home", str(home))


def release(home, owner):
    return run("release", "--owner", owner, "--home", str(home))


@pytest.fixture
def home(tmp_path):
    d = tmp_path / "profiles/marketer"
    d.mkdir(parents=True)
    return d


def test_script_exists_and_is_the_only_new_file_in_this_location():
    assert SCRIPT.is_file()


def test_neutral_or_other_profile_home_is_refused(tmp_path):
    for directory in (tmp_path, tmp_path / "profiles/assistant"):
        directory.mkdir(parents=True, exist_ok=True)
        code, body = acquire(directory, "job")
        assert code == EXIT_USAGE
        assert body["state"] == "error"
        assert not (directory / GUARD_NAME).exists()


def test_extra_json_fields_cannot_override_result(home):
    (home / LEASE_NAME).write_text(json.dumps({"owner": "job", "created_at": "time",
                                              "command": "wrong", "state": "wrong", "resumed": False}))
    code, body = status(home)
    assert code == EXIT_OK
    assert body["command"] == "status" and body["state"] == "held"
    code, body = acquire(home, "job")
    assert code == EXIT_OK and body["resumed"] is True


# --- basic lifecycle ---------------------------------------------------

def test_status_is_free_before_any_acquire(home):
    code, body = status(home)
    assert (code, body) == (EXIT_OK, {"command": "status", "state": "free"})


def test_acquire_then_status_then_release(home):
    code, body = acquire(home, "task-a")
    assert code == EXIT_OK
    assert body["command"] == "acquire" and body["state"] == "held"
    assert body["owner"] == "task-a" and body["resumed"] is False
    assert isinstance(body["created_at"], str) and body["created_at"]

    code, body = status(home)
    assert code == EXIT_OK
    assert body == {"command": "status", "state": "held", "owner": "task-a",
                     "created_at": body["created_at"]}

    code, body = release(home, "task-a")
    assert (code, body) == (EXIT_OK, {"command": "release", "state": "released"})

    code, body = status(home)
    assert (code, body) == (EXIT_OK, {"command": "status", "state": "free"})


def test_same_owner_acquire_is_idempotent_and_resumes(home):
    code1, first = acquire(home, "task-a")
    code2, second = acquire(home, "task-a")
    assert code1 == EXIT_OK and code2 == EXIT_OK
    assert first["resumed"] is False
    assert second["resumed"] is True
    # Resuming never rewrites created_at -- same candidate, same timestamp.
    assert second["created_at"] == first["created_at"]
    assert second["owner"] == "task-a"


def test_different_owner_acquire_is_blocked_without_mutating_state(home):
    acquire(home, "task-a")
    code, body = acquire(home, "task-b")
    assert code == EXIT_BLOCKED
    assert body == {"command": "acquire", "state": "blocked", "owner": "task-a"}
    # The blocked attempt must not have touched the held lease at all.
    code, body = status(home)
    assert body["owner"] == "task-a"


def test_wrong_owner_release_is_refused_and_lease_survives(home):
    acquire(home, "task-a")
    code, body = release(home, "task-b")
    assert code == EXIT_WRONG_OWNER
    assert body == {"command": "release", "state": "held", "owner": "task-a"}
    code, body = status(home)
    assert (code, body["state"], body["owner"]) == (EXIT_OK, "held", "task-a")


def test_release_with_no_lease_is_a_safe_absent_not_an_error(home):
    code, body = release(home, "task-a")
    assert (code, body) == (EXIT_OK, {"command": "release", "state": "absent"})


def test_release_then_reacquire_by_a_new_owner_gets_a_fresh_timestamp(home):
    _, first = acquire(home, "task-a")
    release(home, "task-a")
    _, second = acquire(home, "task-b")
    assert second["owner"] == "task-b" and second["resumed"] is False
    # Not asserting inequality of created_at (a fast machine can tie at
    # one-second resolution); asserting ownership actually changed is enough.


# --- no automatic release / holds through uncertainty -------------------

def test_lease_file_persists_across_independent_invocations(home):
    """Each CLI call is a fresh, short-lived process -- there is no
    long-running daemon to accidentally clean up after itself. This proves
    the lease genuinely outlives any single process, matching the "no
    automatic release on exit" contract in the module docstring."""
    acquire(home, "task-a")
    assert (home / LEASE_NAME).is_file()
    for _ in range(3):
        code, body = status(home)
        assert (code, body["state"], body["owner"]) == (EXIT_OK, "held", "task-a")
    # Still held; nothing released it just by invoking status repeatedly.
    assert (home / LEASE_NAME).is_file()


# --- fail-closed on untrustworthy state ----------------------------------

def test_corrupt_lease_json_blocks_every_command_without_overwriting(home):
    lease = home / LEASE_NAME
    lease.write_text("not json{{{", encoding="utf-8")
    before = lease.read_bytes()

    for outcome in (status(home), acquire(home, "task-a"), release(home, "task-a")):
        code, body = outcome
        assert code == EXIT_UNTRUSTED
        assert body["state"] == "error" and "error" in body

    assert lease.read_bytes() == before  # never touched, never guessed


def test_lease_missing_required_fields_is_also_untrusted(home):
    lease = home / LEASE_NAME
    lease.write_text(json.dumps({"owner": "task-a"}), encoding="utf-8")  # no created_at
    code, body = status(home)
    assert code == EXIT_UNTRUSTED and body["state"] == "error"


def test_lease_owner_with_newline_in_payload_is_untrusted(home):
    lease = home / LEASE_NAME
    lease.write_text(json.dumps({"owner": "bad\nowner", "created_at": "x"}), encoding="utf-8")
    code, body = status(home)
    assert code == EXIT_UNTRUSTED and body["state"] == "error"


# --- symlinks: fail closed, never follow ---------------------------------

def test_lease_path_as_symlink_is_untrusted_on_acquire(home, tmp_path):
    target = tmp_path / "outside-lease-target.json"
    target.write_text(json.dumps({"owner": "victim", "created_at": "t"}), encoding="utf-8")
    os.symlink(target, home / LEASE_NAME)

    code, body = acquire(home, "task-a")
    assert code == EXIT_UNTRUSTED and body["state"] == "error"
    # The symlink itself is left exactly as it was; the target is untouched.
    assert (home / LEASE_NAME).is_symlink()
    assert json.loads(target.read_text()) == {"owner": "victim", "created_at": "t"}


def test_lease_path_as_symlink_is_untrusted_on_status_and_release(home, tmp_path):
    target = tmp_path / "outside-lease-target-2.json"
    target.write_text("{}", encoding="utf-8")
    os.symlink(target, home / LEASE_NAME)

    code, body = status(home)
    assert code == EXIT_UNTRUSTED and body["state"] == "error"
    code, body = release(home, "anyone")
    assert code == EXIT_UNTRUSTED and body["state"] == "error"
    assert (home / LEASE_NAME).is_symlink()  # never unlinked, never replaced


def test_guard_path_as_symlink_is_untrusted_and_blocks_everything(home, tmp_path):
    target = tmp_path / "outside-guard-target"
    target.write_text("", encoding="utf-8")
    os.symlink(target, home / GUARD_NAME)

    for outcome in (status(home), acquire(home, "task-a"), release(home, "task-a")):
        code, body = outcome
        assert code == EXIT_UNTRUSTED and body["state"] == "error"
    assert (home / GUARD_NAME).is_symlink()
    assert not (home / LEASE_NAME).exists()  # never even attempted


# --- --home validation -----------------------------------------------------

def test_missing_home_directory_is_a_usage_error(tmp_path):
    ghost = tmp_path / "does-not-exist"
    code, body = status(ghost)
    assert code == EXIT_USAGE and body["state"] == "error"
    assert not ghost.exists()  # never created as a side effect


def test_home_pointing_at_a_file_not_a_directory_is_a_usage_error(tmp_path):
    not_a_dir = tmp_path / "plain-file"
    not_a_dir.write_text("x", encoding="utf-8")
    code, body = status(not_a_dir)
    assert code == EXIT_USAGE and body["state"] == "error"


# --- --owner validation ------------------------------------------------

@pytest.mark.parametrize("bad_owner", ["", "x" * 257, "line\nbreak", "cr\rreturn"])
def test_invalid_owner_is_a_usage_error_and_never_touches_state(home, bad_owner):
    code, body = run("acquire", "--owner", bad_owner, "--home", str(home))
    assert code == EXIT_USAGE and body["state"] == "error"
    assert not (home / LEASE_NAME).exists()


def test_owner_at_the_256_char_boundary_is_accepted(home):
    owner = "x" * 256
    code, body = acquire(home, owner)
    assert code == EXIT_OK and body["owner"] == owner


# --- guard file discipline ----------------------------------------------

def test_guard_file_is_created_but_never_removed_across_a_full_cycle(home):
    acquire(home, "task-a")
    guard = home / GUARD_NAME
    assert guard.is_file()
    release(home, "task-a")
    assert guard.is_file()  # still there; only the lease itself is freed
    assert not (home / LEASE_NAME).exists()


def test_preexisting_guard_permissions_are_not_silently_reset(home):
    guard = home / GUARD_NAME
    guard.write_text("", encoding="utf-8")
    guard.chmod(0o644)
    before_mode = guard.stat().st_mode & 0o777
    assert before_mode == 0o644

    acquire(home, "task-a")

    after_mode = guard.stat().st_mode & 0o777
    assert after_mode == before_mode  # never chmod'd just for being opened


def test_lease_file_created_with_owner_only_permissions(home):
    acquire(home, "task-a")
    mode = (home / LEASE_NAME).stat().st_mode & 0o777
    assert mode == 0o600


# --- genuine cross-process concurrency: exactly one winner ---------------

def test_concurrent_different_owner_acquire_exactly_one_wins(home):
    procs = [
        subprocess.Popen([sys.executable, str(SCRIPT), "acquire",
                           "--owner", owner, "--home", str(home)],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for owner in ("racer-1", "racer-2")
    ]
    outcomes = []
    for proc in procs:
        out, err = proc.communicate(timeout=20)
        assert err == ""
        outcomes.append((proc.returncode, json.loads(out.strip())))

    codes = sorted(code for code, _ in outcomes)
    assert codes == [EXIT_OK, EXIT_BLOCKED]

    winner = next(body["owner"] for code, body in outcomes if code == EXIT_OK)
    blocked = next(body for code, body in outcomes if code == EXIT_BLOCKED)
    assert blocked["owner"] == winner  # the loser is told exactly who won

    code, body = status(home)
    assert (code, body["state"], body["owner"]) == (EXIT_OK, "held", winner)


def test_concurrent_same_owner_acquire_both_resume_cleanly(home):
    procs = [
        subprocess.Popen([sys.executable, str(SCRIPT), "acquire",
                           "--owner", "same-owner", "--home", str(home)],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(2)
    ]
    outcomes = []
    for proc in procs:
        out, err = proc.communicate(timeout=20)
        assert err == ""
        outcomes.append((proc.returncode, json.loads(out.strip())))

    assert all(code == EXIT_OK for code, _ in outcomes)
    assert all(body["owner"] == "same-owner" for _, body in outcomes)
    timestamps = {body["created_at"] for _, body in outcomes}
    assert len(timestamps) == 1  # one true creation event, not two
