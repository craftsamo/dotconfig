"""cron-sync: manifests under cron.d/ are the only source of a profile's tracked cron jobs.

Runs against the real runtime cron API (``cron.jobs``) routed into a temporary profile home, so
the marker round-trip and the invariants Hermes enforces at create/update are proven on the
runtime that will run the jobs, not on a stub.
"""

from __future__ import annotations

import importlib.util
import io
import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "cron-sync.py"
SPEC = importlib.util.spec_from_file_location("cron_sync", SCRIPT)
assert SPEC and SPEC.loader
S = importlib.util.module_from_spec(SPEC)
sys.modules["cron_sync"] = S  # dataclasses resolve their annotations through sys.modules
SPEC.loader.exec_module(S)

jobs_api = pytest.importorskip("cron.jobs")


def write_job(root: Path, name: str, spec: dict, run: str | None = "#!/bin/sh\necho hi\n",
              *, executable: bool = True, link_from: Path | None = None) -> Path:
    """A manifest directory; ``link_from`` makes cron.d/<name> a link into that directory
    (the shape install.sh gives a repository job)."""
    target = (link_from / name) if link_from else (root / S.MANIFEST_DIR / name)
    target.mkdir(parents=True)
    (target / S.MANIFEST_FILE).write_text(S.yaml.safe_dump(spec), encoding="utf-8")
    if run is not None:
        script = target / S.RUN_SCRIPT
        script.write_text(run, encoding="utf-8")
        if executable:
            script.chmod(0o755)
    if link_from:
        (root / S.MANIFEST_DIR).mkdir(parents=True, exist_ok=True)
        (root / S.MANIFEST_DIR / name).symlink_to(target)
    return target


@pytest.fixture
def home(tmp_path: Path) -> Path:
    h = tmp_path / "profiles" / "assistant"
    (h / "scripts").mkdir(parents=True)
    (h / S.MANIFEST_DIR).mkdir()
    return h


def jobs_of(home: Path) -> list[dict]:
    with jobs_api.use_cron_store(home):
        return jobs_api.load_jobs()


def job(home: Path, name: str) -> dict:
    found = [j for j in jobs_of(home) if j.get(S.MARKER, {}).get("manifest") == name]
    assert len(found) == 1, found
    return found[0]


def sync(home: Path, **kw):
    kw.setdefault("check", False)
    kw.setdefault("prune", False)
    return S.sync_home(home, **kw)


# ---------------------------------------------------------------------------
# Manifest validation
# ---------------------------------------------------------------------------

def test_each_mode_loads_and_maps_to_the_runtime_fields(home: Path):
    write_job(home, "snap", {"schedule": "0 */6 * * *", "mode": "no_agent", "deliver": "telegram"})
    write_job(home, "watch", {"schedule": "*/15 * * * *", "mode": "monitor", "prompt": "Report.",
                              "skills": ["watcher:interpret"]})
    write_job(home, "page", {"schedule": "1h", "mode": "monitor", "prompt": "Report.",
                             "monitor_url": "https://example.com/status"}, run=None)
    write_job(home, "digest", {"schedule": "every monday 9am", "mode": "prompt", "skills": ["digest"]})
    manifests, errors = S.load_manifests(home)
    assert errors == []
    by = {m.name: m.definition() for m in manifests}
    assert by["snap"]["no_agent"] and by["snap"]["script"] == "cron/snap.sh" and by["snap"]["deliver"] == "telegram"
    assert by["watch"]["monitor_script"] == "cron/watch.sh" and by["watch"]["script"] is None
    assert by["watch"]["skills"] == ["watcher:interpret"] and by["watch"]["prompt"] == "Report."
    assert by["page"]["monitor_url"] == "https://example.com/status" and by["page"]["monitor_script"] is None
    assert by["digest"]["script"] == "cron/digest.sh" and not by["digest"]["no_agent"]
    assert all(m.source == "local" for m in manifests)


@pytest.mark.parametrize("name,spec,run,executable,message", [
    ("Bad Name", {"schedule": "1h", "mode": "no_agent"}, "x", True, "directory name"),
    ("a", {"mode": "no_agent"}, "x", True, "`schedule` is required"),
    ("a", {"schedule": "1h", "mode": "weird"}, "x", True, "`mode` must be one of"),
    ("a", {"schedule": "1h", "mode": "no_agent"}, None, True, "needs run.sh"),
    ("a", {"schedule": "1h", "mode": "no_agent", "prompt": "p"}, "x", True, "runs no model"),
    ("a", {"schedule": "1h", "mode": "prompt"}, "x", True, "needs `prompt` or `skills`"),
    ("a", {"schedule": "1h", "mode": "monitor", "prompt": "p"}, None, True, "exactly one of"),
    ("a", {"schedule": "1h", "mode": "monitor", "prompt": "p", "monitor_url": "https://x"}, "x", True, "exactly one of"),
    ("a", {"schedule": "1h", "mode": "monitor", "prompt": "p", "monitor_url": "ftp://x"}, None, True, "http(s)"),
    ("a", {"schedule": "1h", "mode": "prompt", "prompt": "p", "monitor_url": "https://x"}, None, True, "belongs to mode monitor"),
    ("a", {"schedule": "1h", "mode": "no_agent", "extra": 1}, "x", True, "unknown key"),
    ("a", {"schedule": "in 30m", "mode": "no_agent"}, "x", True, "relative one-shot"),
    ("a", {"schedule": "1h", "mode": "no_agent"}, "x", False, "must be executable"),
    ("a", {"schedule": "1h", "mode": "no_agent", "repeat": 0}, "x", True, "positive integer"),
    ("a", {"schedule": "1h", "mode": "no_agent", "paused": "yes"}, "x", True, "true or false"),
    ("a", {"schedule": "1h", "mode": "prompt", "skills": "digest"}, None, True, "list of non-empty"),
])
def test_a_broken_manifest_fails_by_name(home: Path, name, spec, run, executable, message):
    write_job(home, name, spec, run, executable=executable)
    _manifests, errors = S.load_manifests(home)
    assert len(errors) == 1 and errors[0].startswith(f"{name}:") and message in errors[0], errors


def test_a_broken_manifest_blocks_neither_the_others_nor_its_own_job(home: Path):
    write_job(home, "good", {"schedule": "1h", "mode": "no_agent"})
    write_job(home, "bad", {"schedule": "1h", "mode": "no_agent"})
    sync(home)
    assert {j["name"] for j in jobs_of(home)} == {"good", "bad"}
    (home / S.MANIFEST_DIR / "bad" / S.MANIFEST_FILE).write_text("mode: [", encoding="utf-8")
    plan, done = sync(home)
    assert plan.errors and plan.errors[0].startswith("bad:")
    assert plan.orphan_pause == [] and job(home, "bad")["enabled"]


# ---------------------------------------------------------------------------
# Create, wrappers, idempotence
# ---------------------------------------------------------------------------

def test_sync_creates_marked_jobs_and_executable_wrappers_at_the_real_script(home: Path):
    run = write_job(home, "snap", {"schedule": "0 */6 * * *", "mode": "no_agent", "deliver": "telegram"})
    plan, done = sync(home)
    assert done == [f"created snap ({job(home, 'snap')['id']}, local)"]
    j = job(home, "snap")
    assert j["no_agent"] and j["script"] == "cron/snap.sh" and j["deliver"] == "telegram"
    assert j[S.MARKER]["manifest"] == "snap" and j[S.MARKER]["source"] == "local" and j[S.MARKER]["synced_at"]
    assert j["enabled"] and j["next_run_at"]
    wrapper = home / "scripts" / "cron" / "snap.sh"
    assert wrapper.stat().st_mode & stat.S_IXUSR
    text = wrapper.read_text()
    # Reached through the manifest's path under the home, never a checkout path baked in.
    assert 'exec "$HERMES_HOME/cron.d/snap/run.sh" "$@"' in text and "do not edit" in text
    assert str(run) not in text
    # The wrapper names the owning profile for the script it execs.
    assert 'HERMES_HOME="$(cd "$(dirname "$0")/../.." && pwd)"' in text and "export HERMES_HOME" in text


def test_the_wrapper_hands_the_script_its_profile_home(home: Path, tmp_path: Path):
    write_job(home, "who", {"schedule": "1h", "mode": "no_agent"},
              run='#!/bin/sh\nprintf "%s\\n%s" "$HERMES_HOME" "$(cd "$(dirname "$0")" && pwd -P)"\n',
              link_from=tmp_path / "repo")
    sync(home)
    out = subprocess.run([str(home / "scripts" / "cron" / "who.sh")], capture_output=True, text=True,
                         env={"PATH": "/usr/bin:/bin"}, check=True).stdout.splitlines()
    assert Path(out[0]).resolve() == home.resolve()
    assert Path(out[1]) == (tmp_path / "repo" / "who").resolve()  # pwd -P still finds the checkout


def test_a_second_sync_changes_nothing_and_check_reports_in_sync(home: Path, capsys):
    write_job(home, "snap", {"schedule": "0 */6 * * *", "mode": "no_agent"})
    sync(home)
    before = jobs_of(home)
    plan, done = sync(home)
    assert done == [] and plan.wrappers == [] and not plan.pending()
    assert jobs_of(home) == before
    assert S.main(["--home", str(home), "--check"]) == 0
    assert "in sync" in capsys.readouterr().out


def test_check_writes_nothing_and_exits_nonzero_when_pending(home: Path, capsys):
    write_job(home, "snap", {"schedule": "0 */6 * * *", "mode": "no_agent"})
    assert S.main(["--home", str(home), "--check"]) == 1
    out = capsys.readouterr().out
    assert "would create snap (local)" in out and "would write wrapper" in out
    assert jobs_of(home) == [] and not (home / "scripts" / "cron").exists()


def test_a_monitor_manifest_sets_monitor_script_and_a_url_one_sets_monitor_url(home: Path):
    write_job(home, "watch", {"schedule": "15m", "mode": "monitor", "prompt": "Report."})
    write_job(home, "page", {"schedule": "1h", "mode": "monitor", "prompt": "Report.",
                             "monitor_url": "https://example.com/status"}, run=None)
    sync(home)
    assert job(home, "watch")["monitor_script"] == "cron/watch.sh" and not job(home, "watch")["script"]
    assert job(home, "page")["monitor_url"] == "https://example.com/status"
    assert not (home / "scripts" / "cron" / "page.sh").exists()


# ---------------------------------------------------------------------------
# The manifest is the truth
# ---------------------------------------------------------------------------

def test_an_edited_manifest_updates_only_the_definition(home: Path):
    write_job(home, "snap", {"schedule": "0 */6 * * *", "mode": "no_agent"})
    sync(home)
    first = job(home, "snap")
    (home / S.MANIFEST_DIR / "snap" / S.MANIFEST_FILE).write_text(
        S.yaml.safe_dump({"schedule": "0 */3 * * *", "mode": "no_agent", "deliver": "telegram"}),
        encoding="utf-8")
    plan, done = sync(home)
    assert done == ["updated snap: deliver, schedule"]
    after = job(home, "snap")
    assert after["id"] == first["id"] and after["created_at"] == first["created_at"]
    assert after["schedule"]["expr"] == "0 */3 * * *" and after["deliver"] == "telegram"


def test_an_out_of_band_edit_is_reverted(home: Path):
    write_job(home, "snap", {"schedule": "0 */6 * * *", "mode": "no_agent"})
    sync(home)
    with jobs_api.use_cron_store(home):
        jobs_api.update_job(job(home, "snap")["id"], {"schedule": "0 9 * * *", "deliver": "discord"})
    plan, done = sync(home)
    assert done == ["updated snap: deliver, schedule"]
    assert job(home, "snap")["schedule"]["expr"] == "0 */6 * * *"


def test_a_one_shot_manifest_does_not_update_forever(home: Path):
    write_job(home, "once", {"schedule": "2099-01-01T09:00:00", "mode": "no_agent"})
    sync(home)
    assert job(home, "once")["repeat"]["times"] == 1
    plan, done = sync(home)
    assert done == []


def test_the_marker_survives_the_runtime_update_path(home: Path):
    """A continuity check: ``managed`` is not a field the runtime knows, so an upstream that
    started dropping unknown keys on update would silently orphan every tracked job."""
    write_job(home, "snap", {"schedule": "1h", "mode": "no_agent"})
    sync(home)
    j = job(home, "snap")
    with jobs_api.use_cron_store(home):
        jobs_api.update_job(j["id"], {"schedule": "2h"})
        jobs_api.pause_job(j["id"], "by hand")
        jobs_api.resume_job(j["id"])
        jobs_api.trigger_job(j["id"])
    assert job(home, "snap")[S.MARKER] == j[S.MARKER]


# ---------------------------------------------------------------------------
# Pause, orphans, prune
# ---------------------------------------------------------------------------

def test_paused_in_the_manifest_is_honoured_both_ways(home: Path):
    write_job(home, "snap", {"schedule": "1h", "mode": "no_agent", "paused": True})
    sync(home)
    j = job(home, "snap")
    assert not j["enabled"] and j["paused_reason"] == S.MANIFEST_PAUSE_REASON and j["next_run_at"] is None
    (home / S.MANIFEST_DIR / "snap" / S.MANIFEST_FILE).write_text(
        S.yaml.safe_dump({"schedule": "1h", "mode": "no_agent", "paused": False}), encoding="utf-8")
    plan, done = sync(home)
    assert done == ["resumed snap"] and job(home, "snap")["enabled"]


def test_dropping_paused_from_the_manifest_lifts_the_pause_the_sync_made(home: Path):
    write_job(home, "snap", {"schedule": "1h", "mode": "no_agent", "paused": True})
    sync(home)
    (home / S.MANIFEST_DIR / "snap" / S.MANIFEST_FILE).write_text(
        S.yaml.safe_dump({"schedule": "1h", "mode": "no_agent"}), encoding="utf-8")
    plan, done = sync(home)
    assert done == ["resumed snap"] and job(home, "snap")["enabled"]


def test_two_jobs_with_one_marker_are_a_conflict_left_to_a_person(home: Path):
    write_job(home, "snap", {"schedule": "1h", "mode": "no_agent"})
    sync(home)
    with jobs_api.use_cron_store(home):
        twin = jobs_api.create_job(None, "1h", name="snap", script="x.sh", no_agent=True)
        jobs_api.update_job(twin["id"], {S.MARKER: {"manifest": "snap", "source": "local", "synced_at": "x"}})
    plan, done = sync(home)
    assert plan.conflicts and "2 jobs carry its marker" in plan.conflicts[0]
    assert done == [] and plan.orphan_pause == [] and len(jobs_of(home)) == 2


def test_a_hand_pause_is_kept_unless_the_manifest_says_otherwise(home: Path):
    write_job(home, "snap", {"schedule": "1h", "mode": "no_agent"})
    sync(home)
    with jobs_api.use_cron_store(home):
        jobs_api.pause_job(job(home, "snap")["id"], "investigating")
    plan, done = sync(home)
    assert done == [] and not job(home, "snap")["enabled"]


def test_a_removed_manifest_pauses_its_job_and_a_restored_one_resumes_it(home: Path, tmp_path: Path):
    write_job(home, "snap", {"schedule": "1h", "mode": "no_agent"})
    sync(home)
    directory = home / S.MANIFEST_DIR / "snap"
    parked = tmp_path / "parked"
    directory.rename(parked)
    plan, done = sync(home)
    j = job(home, "snap")
    assert done == [f"paused orphan snap ({j['id']}): manifest removed"]
    assert not j["enabled"] and j["paused_reason"] == S.ORPHAN_REASON
    assert plan.wrappers == ["drop wrapper scripts/cron/snap.sh"]
    assert not (home / "scripts" / "cron" / "snap.sh").exists()
    plan, done = sync(home)
    assert done == []  # already paused as an orphan: nothing to repeat
    parked.rename(directory)
    plan, done = sync(home)
    assert done == ["resumed snap"] and job(home, "snap")["enabled"]
    assert (home / "scripts" / "cron" / "snap.sh").exists()


def test_prune_removes_orphans_and_their_output(home: Path, tmp_path: Path):
    write_job(home, "snap", {"schedule": "1h", "mode": "no_agent"})
    sync(home)
    j = job(home, "snap")
    (home / S.MANIFEST_DIR / "snap").rename(tmp_path / "parked")
    plan, done = sync(home, prune=True)
    assert done == [f"removed orphan snap ({j['id']})"]
    assert jobs_of(home) == []


# ---------------------------------------------------------------------------
# Unmanaged jobs, conflicts, adoption
# ---------------------------------------------------------------------------

def test_unmanaged_jobs_are_never_touched(home: Path):
    with jobs_api.use_cron_store(home):
        own = jobs_api.create_job("remind me", "1h", name="reminder")
    write_job(home, "snap", {"schedule": "1h", "mode": "no_agent"})
    plan, done = sync(home)
    assert len(done) == 1
    with jobs_api.use_cron_store(home):
        assert jobs_api.get_job(own["id"]) == own
    plan, done = sync(home, prune=True)
    with jobs_api.use_cron_store(home):
        assert jobs_api.get_job(own["id"]) == own


def test_a_same_named_unmanaged_job_is_a_conflict_until_adopted(home: Path):
    with jobs_api.use_cron_store(home):
        old = jobs_api.create_job(None, "0 */6 * * *", name="snap", script="x-snapshot.sh", no_agent=True)
    write_job(home, "snap", {"schedule": "0 */6 * * *", "mode": "no_agent", "deliver": "telegram"})
    plan, done = sync(home)
    assert plan.conflicts and "cron-sync adopt snap" in plan.conflicts[0]
    assert done == [] and len(jobs_of(home)) == 1 and S.MARKER not in jobs_of(home)[0]
    assert S.adopt(home, "snap").startswith(f"adopted snap ({old['id']}, local)")
    plan, done = sync(home)
    assert done == ["updated snap: deliver, script"]
    j = job(home, "snap")
    assert j["id"] == old["id"] and j["script"] == "cron/snap.sh" and j["deliver"] == "telegram"
    with pytest.raises(S.ManifestError, match="already managed"):
        S.adopt(home, "snap")


def test_adopt_refuses_an_ambiguous_name(home: Path):
    with jobs_api.use_cron_store(home):
        jobs_api.create_job("a", "1h", name="snap")
        jobs_api.create_job("b", "1h", name="snap")
    write_job(home, "snap", {"schedule": "1h", "mode": "prompt", "prompt": "a"}, run=None)
    with pytest.raises(S.ManifestError, match="2 unmanaged"):
        S.adopt(home, "snap")


# ---------------------------------------------------------------------------
# Source: repository link vs local directory
# ---------------------------------------------------------------------------

def test_a_linked_manifest_is_repo_and_a_moved_one_is_restamped(home: Path, tmp_path: Path):
    repo = tmp_path / "repo" / "cron.d"
    write_job(home, "snap", {"schedule": "1h", "mode": "no_agent"}, link_from=repo)
    sync(home)
    assert job(home, "snap")[S.MARKER]["source"] == "repo"
    wrapper = (home / "scripts" / "cron" / "snap.sh").read_text()
    assert str(repo) not in wrapper  # the checkout is reached through the link, never named
    # Promotion in reverse: the link becomes a real directory (a local copy).
    link = home / S.MANIFEST_DIR / "snap"
    link.unlink()
    write_job(home, "snap", {"schedule": "1h", "mode": "no_agent"})
    plan, done = sync(home)
    assert done == ["restamped snap as local"]
    assert job(home, "snap")[S.MARKER]["source"] == "local"


# ---------------------------------------------------------------------------
# Local manifests: add, remove, prune-completed
# ---------------------------------------------------------------------------

def test_write_local_validates_before_leaving_anything_behind(home: Path):
    with pytest.raises(S.ManifestError, match="needs run.sh"):
        S.write_local(home, "job", {"schedule": "1h", "mode": "no_agent"}, None)
    assert not (home / S.MANIFEST_DIR / "job").exists()
    directory = S.write_local(home, "job", {"schedule": "1h", "mode": "no_agent"}, "#!/bin/sh\necho x\n")
    assert (directory / S.RUN_SCRIPT).stat().st_mode & stat.S_IXUSR
    assert S.yaml.safe_load((directory / S.MANIFEST_FILE).read_text()) == {"schedule": "1h", "mode": "no_agent"}
    with pytest.raises(S.ManifestError, match="already exists"):
        S.write_local(home, "job", {"schedule": "1h", "mode": "no_agent"}, "x")
    sync(home)
    assert job(home, "job")[S.MARKER]["source"] == "local"
    S.remove_local(home, "job")
    plan, done = sync(home)
    assert done[0].startswith("paused orphan job")


def test_thread_title_names_the_thread_a_continuable_delivery_opens(home: Path):
    """A field the runtime learns from a local patch, so it is set through update_job (any key)
    and a stock runtime merely carries it."""
    write_job(home, "fix", {"schedule": "0 0 29 2 *", "mode": "prompt", "prompt": "Fix it.",
                            "attach_to_session": True, "thread_title": "  Dependency\nfix "})
    sync(home)
    assert job(home, "fix")["thread_title"] == "Dependency fix"
    (home / S.MANIFEST_DIR / "fix" / S.MANIFEST_FILE).write_text(S.yaml.safe_dump({
        "schedule": "0 0 29 2 *", "mode": "prompt", "prompt": "Fix it.", "attach_to_session": True}),
        encoding="utf-8")
    _plan, done = sync(home)
    assert done == ["updated fix: thread_title"] and job(home, "fix").get("thread_title") is None
    write_job(home, "snap", {"schedule": "1h", "mode": "no_agent", "thread_title": "x"})
    _manifests, errors = S.load_manifests(home)
    assert len(errors) == 1 and "thread_title" in errors[0]


def test_a_local_manifest_carries_the_conversation_and_the_agent_fields(home: Path):
    write_job(home, "gate", {
        "schedule": "*/15 * * * *", "mode": "prompt", "prompt": "Follow the gate report.",
        "deliver": "origin", "attach_to_session": True, "enabled_toolsets": ["skills"],
        "context_from": ["self"],
        "origin": {"platform": "telegram", "chat_id": "-100", "thread_id": "7", "chat_name": None},
    })
    sync(home)
    j = job(home, "gate")
    assert j["origin"] == {"platform": "telegram", "chat_id": "-100", "thread_id": "7", "chat_name": None}
    assert j["deliver"] == "origin" and j["attach_to_session"] is True
    assert j["enabled_toolsets"] == ["skills"] and j["context_from"] == ["self"]
    plan, done = sync(home)
    assert done == []
    (home / S.MANIFEST_DIR / "gate" / S.MANIFEST_FILE).write_text(S.yaml.safe_dump({
        "schedule": "*/15 * * * *", "mode": "prompt", "prompt": "Follow the gate report.",
        "deliver": "origin", "enabled_toolsets": [], "origin": {"platform": "telegram", "chat_id": "-100"},
    }), encoding="utf-8")
    plan, done = sync(home)
    assert done == ["updated gate: attach_to_session, context_from, enabled_toolsets"]
    assert job(home, "gate")["enabled_toolsets"] == []  # an explicit zero-tool allowlist survives


@pytest.mark.parametrize("spec,message", [
    ({"schedule": "1h", "mode": "no_agent", "enabled_toolsets": ["x"]}, "runs no model"),
    ({"schedule": "1h", "mode": "prompt", "prompt": "p", "origin": {"platform": "telegram"}}, "`origin` must be"),
    ({"schedule": "1h", "mode": "prompt", "prompt": "p", "context_from": "self"}, "list of non-empty"),
    ({"schedule": "1h", "mode": "prompt", "prompt": "p", "attach_to_session": "yes"}, "true or false"),
])
def test_the_agent_fields_are_checked(home: Path, spec, message):
    write_job(home, "a", spec)
    _manifests, errors = S.load_manifests(home)
    assert len(errors) == 1 and message in errors[0], errors


def test_drop_local_removes_the_directory_and_only_its_job(home: Path, tmp_path: Path):
    write_job(home, "mine", {"schedule": "1h", "mode": "no_agent"})
    write_job(home, "other", {"schedule": "1h", "mode": "no_agent"})
    sync(home)
    (home / S.MANIFEST_DIR / "other").rename(tmp_path / "parked")  # an orphan that must stay
    mine_id = job(home, "mine")["id"]
    assert S.drop_local(home, "mine") == mine_id
    assert not (home / S.MANIFEST_DIR / "mine").exists()
    assert not (home / "scripts" / "cron" / "mine.sh").exists()
    assert [j["name"] for j in jobs_of(home)] == ["other"]


def test_remove_local_refuses_a_repository_job(home: Path, tmp_path: Path):
    write_job(home, "snap", {"schedule": "1h", "mode": "no_agent"}, link_from=tmp_path / "repo")
    with pytest.raises(S.ManifestError, match="repository job"):
        S.remove_local(home, "snap")
    assert (home / S.MANIFEST_DIR / "snap").is_symlink()


def test_prune_completed_drops_a_fired_local_one_shot_with_its_directory(home: Path, tmp_path: Path):
    write_job(home, "once", {"schedule": "2099-01-01T09:00:00", "mode": "no_agent"})
    write_job(home, "repo-once", {"schedule": "2099-01-01T09:00:00", "mode": "no_agent"},
              link_from=tmp_path / "repo")
    sync(home)
    once_id = job(home, "once")["id"]
    with jobs_api.use_cron_store(home):
        for name in ("once", "repo-once"):
            jobs_api.update_job(job(home, name)["id"], {"state": "completed", "enabled": False})
    assert S.prune_completed(home) == [f"pruned completed once ({once_id})"]
    assert not (home / S.MANIFEST_DIR / "once").exists()
    assert (home / S.MANIFEST_DIR / "repo-once").is_symlink()
    assert [j["name"] for j in jobs_of(home)] == ["repo-once"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_the_cli_walks_every_profile_with_a_cron_d(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_DIR", str(tmp_path))
    a = tmp_path / "profiles" / "assistant"
    b = tmp_path / "profiles" / "writer"
    (a / "scripts").mkdir(parents=True)
    (b / "scripts").mkdir(parents=True)
    write_job(a, "snap", {"schedule": "1h", "mode": "no_agent"})
    assert S.main([]) == 0
    out = capsys.readouterr().out
    assert "[assistant]" in out and "created snap" in out and "[writer]" not in out
    assert S.main(["validate"]) == 0
    assert "ok snap (no_agent, local)" in capsys.readouterr().out


def test_add_and_remove_from_the_cli(home: Path, monkeypatch, capsys, tmp_path: Path):
    script = tmp_path / "run.sh"
    script.write_text("#!/bin/sh\necho x\n")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"schedule": "1h", "mode": "no_agent"})))
    assert S.main(["--home", str(home), "add", "job", "--run-script", str(script)]) == 0
    assert (home / S.MANIFEST_DIR / "job" / S.RUN_SCRIPT).read_text() == "#!/bin/sh\necho x\n"
    assert S.main(["--home", str(home), "remove", "job"]) == 0
    assert not (home / S.MANIFEST_DIR / "job").exists()
    assert S.main(["--home", str(home), "remove", "job"]) == 1
    assert "no such local job" in capsys.readouterr().err
