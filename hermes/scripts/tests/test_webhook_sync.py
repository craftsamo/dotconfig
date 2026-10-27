"""webhook-sync: manifests under every profile's webhook.d/ are the only source of the tracked
routes in the root home's webhook_subscriptions.json.

Runs against the runtime's own subscriptions reader and writer (``hermes_cli.webhook``) routed
into a temporary root, so the file shape the gateway hot-reloads is the one proven here.
"""

from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "webhook-sync.py"
SPEC = importlib.util.spec_from_file_location("webhook_sync", SCRIPT)
assert SPEC and SPEC.loader
S = importlib.util.module_from_spec(SPEC)
sys.modules["webhook_sync"] = S
SPEC.loader.exec_module(S)

pytest.importorskip("hermes_cli.webhook")

NOTIFY = {"mode": "notify", "events": ["push"], "prompt": "push on {repository.full_name}", "deliver": "telegram"}
AGENT = {"mode": "agent", "events": ["pull_request"], "prompt": "Review {pull_request.html_url}.",
         "skills": ["review"], "deliver": "telegram", "mirror_to_session": True}
JOB = {"mode": "job", "events": ["dependabot_alert"],
       "filters": [{"field": "alert.security_advisory.severity", "in": ["high", "critical"]}],
       "cron_job": "fix", "prompt": "Alert {alert.html_url}"}


def write_route(root: Path, profile: str, name: str, spec: dict, *, filter_script: str | None = None,
                filter_name: str = "filter.sh", executable: bool = True, link_from: Path | None = None) -> Path:
    """A route directory of ``profile``; ``link_from`` makes webhook.d/<name> a link into that
    directory (the shape install.sh gives a repository route)."""
    home = root / "profiles" / profile
    target = (link_from / name) if link_from else (home / S.MANIFEST_DIR / name)
    target.mkdir(parents=True)
    (target / S.MANIFEST_FILE).write_text(S.yaml.safe_dump(spec), encoding="utf-8")
    if filter_script is not None:
        script = target / filter_name
        script.write_text(filter_script, encoding="utf-8")
        if executable:
            script.chmod(0o755)
    if link_from:
        (home / S.MANIFEST_DIR).mkdir(parents=True, exist_ok=True)
        (home / S.MANIFEST_DIR / name).symlink_to(target)
    return target


def write_cron(root: Path, profile: str, name: str) -> Path:
    directory = root / "profiles" / profile / S.CRON_MANIFEST_DIR / name
    directory.mkdir(parents=True)
    (directory / "job.yaml").write_text("schedule: 0 0 29 2 *\nmode: prompt\nprompt: p\n", encoding="utf-8")
    return directory


@pytest.fixture
def root(tmp_path: Path) -> Path:
    r = tmp_path / "hermes"
    for profile in ("assistant", "writer"):
        (r / "profiles" / profile / "scripts").mkdir(parents=True)
        (r / "profiles" / profile / S.MANIFEST_DIR).mkdir()
    write_cron(r, "assistant", "fix")
    return r


def records(root: Path) -> dict:
    path = root / S.SUBSCRIPTIONS_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def sync(root: Path, **kw):
    kw.setdefault("check", False)
    kw.setdefault("prune", False)
    return S.sync_root(root, **kw)


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def test_each_mode_derives_the_runtime_route_shape(root: Path):
    write_route(root, "assistant", "gh-push", NOTIFY)
    write_route(root, "assistant", "gh-pr", AGENT)
    write_route(root, "assistant", "gh-alert", JOB)
    plan, done = sync(root)
    assert not plan.failed(), plan
    assert done == ["created gh-alert (assistant, local)", "created gh-pr (assistant, local)",
                    "created gh-push (assistant, local)"]
    r = records(root)
    assert r["gh-push"]["deliver_only"] is True and r["gh-push"]["deliver"] == "telegram"
    assert r["gh-push"]["prompt"] == "push on {repository.full_name}" and r["gh-push"]["events"] == ["push"]
    assert r["gh-push"]["cron_job"] is None and r["gh-push"]["profile"] == "assistant" and r["gh-push"]["enabled"]
    assert r["gh-pr"]["deliver_only"] is False and r["gh-pr"]["skills"] == ["review"]
    assert r["gh-pr"]["mirror_to_session"] is True
    assert r["gh-alert"]["cron_job"] == "fix" and r["gh-alert"]["deliver"] == "log"
    assert r["gh-alert"]["filters"] == JOB["filters"]
    for name in ("gh-push", "gh-pr", "gh-alert"):
        assert r[name][S.MARKER]["manifest"] == name and r[name][S.MARKER]["source"] == "local"
        assert r[name][S.MARKER]["profile"] == "assistant" and "secret" not in r[name]
    assert (root / S.SUBSCRIPTIONS_FILE).stat().st_mode & 0o777 == 0o600


def test_the_runtime_accepts_every_derived_record(root: Path):
    """The gateway's own route checks (startup validation and the per-POST dynamic-route gate)
    take each derived record, marker included, under a global secret; a re-pin that changes
    the route shape or starts refusing unknown keys fails here, not at the first POST."""
    from gateway.config import Platform, PlatformConfig
    from gateway.platforms.webhook import WebhookAdapter
    write_route(root, "assistant", "gh-push", NOTIFY)
    write_route(root, "assistant", "gh-pr", {**AGENT, "coalesce": {"key": "pull_request.number", "window_seconds": 30}})
    write_route(root, "assistant", "gh-alert", JOB)
    sync(root)
    adapter = WebhookAdapter(PlatformConfig(enabled=True, extra={"host": "127.0.0.1", "port": 1, "secret": "global-secret"}))
    assert adapter.platform == Platform.WEBHOOK
    for name, record in records(root).items():
        adapter._validate_route(name, record)
        assert adapter._dynamic_route_allowed(name, record), name


def test_a_second_sync_changes_nothing(root: Path):
    write_route(root, "assistant", "gh-push", NOTIFY)
    sync(root)
    plan, done = sync(root)
    assert done == [] and not plan.pending()
    plan, done = sync(root, check=True)
    assert done is None and not plan.pending()


@pytest.mark.parametrize("spec,message", [
    ({"mode": "notify", "deliver": "telegram"}, "`prompt`"),
    ({"mode": "notify", "prompt": "p"}, "real `deliver`"),
    ({"mode": "notify", "prompt": "p", "deliver": "log"}, "real `deliver`"),
    ({"mode": "notify", "prompt": "p", "deliver": "telegram", "skills": ["x"]}, "drop `skills`"),
    ({"mode": "agent"}, "`prompt` or `skills`"),
    ({"mode": "agent", "prompt": "p", "cron_job": "fix"}, "belongs to mode job"),
    ({"mode": "job"}, "needs `cron_job`"),
    ({"mode": "job", "cron_job": "nope"}, "not a cron.d/ directory"),
    ({"mode": "job", "cron_job": "fix", "deliver": "telegram"}, "whose own skills, delivery"),
    ({"mode": "watch", "prompt": "p"}, "`mode` must be one of"),
    ({"mode": "agent", "prompt": "p", "secret": "s"}, "unknown key(s) secret"),
    ({"mode": "agent", "prompt": "p", "deliver_extra": {"chat": "1"}}, "takes chat_id"),
    ({"mode": "agent", "prompt": "p", "deliver_extra": {"chat_id": True}}, "strings or integers"),
    ({"mode": "agent", "prompt": "p", "filters": "x"}, "`filters` must be"),
    ({"mode": "agent", "prompt": "p", "events": "push"}, "`events` must be a list"),
])
def test_a_manifest_the_runtime_would_refuse_fails_by_name(root: Path, spec, message):
    write_route(root, "assistant", "bad", spec)
    routes, errors = S.load_routes(root / "profiles" / "assistant", "assistant")
    assert routes == [] and len(errors) == 1 and errors[0].startswith("assistant/bad:") and message in errors[0], errors


def test_deliver_extra_is_kept_as_strings(root: Path):
    write_route(root, "assistant", "r", {**NOTIFY, "deliver_extra": {"chat_id": 123, "thread_id": "7"}})
    sync(root)
    assert records(root)["r"]["deliver_extra"] == {"chat_id": "123", "thread_id": "7"}


# ---------------------------------------------------------------------------
# Filter scripts and their wrappers
# ---------------------------------------------------------------------------

def test_a_filter_script_is_reached_through_a_wrapper_that_passes_stdin_and_stdout(root: Path, tmp_path: Path):
    write_route(root, "assistant", "gh-pr", AGENT, link_from=tmp_path / "repo",
                filter_script='#!/bin/sh\nread body; printf "%s|%s" "$HERMES_HOME" "$body"\n')
    plan, _done = sync(root)
    assert plan.wrappers == ["wrapper scripts/webhook/gh-pr.sh"]
    assert records(root)["gh-pr"]["script"] == "webhook/gh-pr.sh"
    wrapper = root / "profiles" / "assistant" / "scripts" / "webhook" / "gh-pr.sh"
    assert wrapper.stat().st_mode & stat.S_IXUSR
    text = wrapper.read_text()
    assert 'exec "$HERMES_HOME/webhook.d/gh-pr/filter.sh" "$@"' in text and str(tmp_path / "repo") not in text
    out = subprocess.run([str(wrapper)], input='{"a":1}\n', capture_output=True, text=True,
                         env={"PATH": "/usr/bin:/bin"}, check=True).stdout
    home_seen, body = out.split("|")
    assert Path(home_seen).resolve() == (root / "profiles" / "assistant").resolve() and body == '{"a":1}'


def test_a_filter_must_be_executable_and_only_one_may_exist(root: Path):
    write_route(root, "assistant", "a", AGENT, filter_script="#!/bin/sh\ncat\n", executable=False)
    write_route(root, "assistant", "b", AGENT, filter_script="#!/bin/sh\ncat\n")
    (root / "profiles" / "assistant" / S.MANIFEST_DIR / "b" / "filter.py").write_text("print(1)\n")
    (root / "profiles" / "assistant" / S.MANIFEST_DIR / "b" / "filter.py").chmod(0o755)
    _routes, errors = S.load_routes(root / "profiles" / "assistant", "assistant")
    assert sorted(e.split(":")[0] for e in errors) == ["assistant/a", "assistant/b"]
    assert "chmod +x" in errors[0] and "not both" in errors[1]


def test_dropping_the_filter_drops_the_wrapper(root: Path):
    d = write_route(root, "assistant", "gh-pr", AGENT, filter_script="#!/bin/sh\ncat\n")
    sync(root)
    (d / "filter.sh").unlink()
    plan, done = sync(root)
    assert done == ["updated gh-pr: script"] and plan.wrappers == ["drop wrapper scripts/webhook/gh-pr.sh"]
    assert records(root)["gh-pr"]["script"] is None
    assert not (root / "profiles" / "assistant" / "scripts" / "webhook" / "gh-pr.sh").exists()


# ---------------------------------------------------------------------------
# Drift, pause, orphans
# ---------------------------------------------------------------------------

def test_an_edit_is_applied_and_check_reports_it_first(root: Path):
    d = write_route(root, "assistant", "gh-push", NOTIFY)
    sync(root)
    (d / S.MANIFEST_FILE).write_text(S.yaml.safe_dump({**NOTIFY, "events": ["push", "create"],
                                                       "deliver": "discord"}), encoding="utf-8")
    plan, done = sync(root, check=True)
    assert done is None and [u for _r, u in plan.update] == [{"events": ["push", "create"], "deliver": "discord"}]
    assert records(root)["gh-push"]["deliver"] == "telegram"  # --check wrote nothing
    plan, done = sync(root)
    assert done == ["updated gh-push: deliver, events"]
    assert records(root)["gh-push"]["events"] == ["push", "create"]


def test_paused_writes_enabled_false_and_dropping_it_enables_again(root: Path):
    d = write_route(root, "assistant", "gh-push", {**NOTIFY, "paused": True})
    sync(root)
    assert records(root)["gh-push"]["enabled"] is False
    (d / S.MANIFEST_FILE).write_text(S.yaml.safe_dump(NOTIFY), encoding="utf-8")
    _plan, done = sync(root)
    assert done == ["updated gh-push: enabled"] and records(root)["gh-push"]["enabled"] is True


def test_a_removed_manifest_disables_its_route_and_a_returning_one_enables_it(root: Path, tmp_path: Path):
    d = write_route(root, "assistant", "gh-push", NOTIFY)
    sync(root)
    d.rename(tmp_path / "parked")
    plan, done = sync(root)
    assert done == ["disabled orphan gh-push: manifest removed"]
    r = records(root)["gh-push"]
    assert r["enabled"] is False and r[S.MARKER]["reason"] == S.ORPHAN_REASON
    plan, done = sync(root)
    assert done == [] and not plan.pending()
    (tmp_path / "parked").rename(d)
    _plan, done = sync(root)
    assert done == ["updated gh-push: enabled"]
    r = records(root)["gh-push"]
    assert r["enabled"] is True and "reason" not in r[S.MARKER]


def test_prune_removes_orphans_and_never_an_unmanaged_route(root: Path, tmp_path: Path):
    d = write_route(root, "assistant", "gh-push", NOTIFY)
    sync(root)
    S.mutate_records(root, lambda subs: subs.__setitem__("mine", {"prompt": "x", "secret": "s", "deliver": "log"}))
    d.rename(tmp_path / "parked")
    _plan, done = sync(root, prune=True)
    assert done == ["removed orphan gh-push"]
    assert set(records(root)) == {"mine"}


def test_a_broken_manifest_is_reported_and_its_route_left_alone(root: Path):
    d = write_route(root, "assistant", "gh-push", NOTIFY)
    sync(root)
    (d / S.MANIFEST_FILE).write_text("mode: [", encoding="utf-8")
    plan, done = sync(root)
    assert plan.errors and plan.errors[0].startswith("assistant/gh-push:") and done == []
    assert plan.orphan_disable == [] and records(root)["gh-push"]["enabled"] is True


# ---------------------------------------------------------------------------
# Conflicts, adoption, sources
# ---------------------------------------------------------------------------

def test_an_unmanaged_route_of_the_same_name_is_a_conflict_until_adopted(root: Path):
    S.mutate_records(root, lambda subs: subs.__setitem__("gh-push", {
        "description": "Agent-created subscription: gh-push", "events": [], "secret": "s", "prompt": "old",
        "deliver": "log", "profile": "default", "created_at": "2026-01-01T00:00:00Z"}))
    write_route(root, "assistant", "gh-push", NOTIFY)
    plan, done = sync(root)
    assert done == [] and "webhook-sync adopt assistant gh-push" in plan.conflicts[0]
    assert records(root)["gh-push"]["prompt"] == "old"
    assert S.adopt(root, "assistant", "gh-push").startswith("adopted gh-push (assistant, local)")
    with pytest.raises(S.ManifestError, match="already managed"):
        S.adopt(root, "assistant", "gh-push")
    _plan, done = sync(root)
    assert done == ["updated gh-push: deliver, deliver_only, events, prompt"]
    r = records(root)["gh-push"]
    # The runtime's own fields survive the adoption; the secret is the route's, untouched.
    assert r["profile"] == "assistant" and r["secret"] == "s" and r["created_at"] == "2026-01-01T00:00:00Z"


def test_two_profiles_may_not_track_one_route_name(root: Path):
    write_route(root, "assistant", "gh-push", NOTIFY)
    write_route(root, "writer", "gh-push", NOTIFY)
    plan, done = sync(root)
    assert done == [] and "tracked by both assistant and writer" in plan.conflicts[0]
    assert records(root) == {}


def test_a_linked_manifest_is_repo_and_a_moved_one_is_restamped(root: Path, tmp_path: Path):
    write_route(root, "assistant", "gh-push", NOTIFY, link_from=tmp_path / "repo")
    sync(root)
    assert records(root)["gh-push"][S.MARKER]["source"] == "repo"
    link = root / "profiles" / "assistant" / S.MANIFEST_DIR / "gh-push"
    link.unlink()
    (tmp_path / "repo" / "gh-push").rename(link)
    _plan, done = sync(root)
    assert done == ["restamped gh-push as assistant/local"]
    link.rename(root / "profiles" / "writer" / S.MANIFEST_DIR / "gh-push")
    _plan, done = sync(root)
    assert done == ["updated gh-push: profile", "restamped gh-push as writer/local"]
    assert records(root)["gh-push"]["profile"] == "writer"


# ---------------------------------------------------------------------------
# Local manifests
# ---------------------------------------------------------------------------

def test_write_local_and_remove_local(root: Path):
    home = root / "profiles" / "assistant"
    d = S.write_local(home, "mine", AGENT, ("filter.py", "import sys; sys.stdout.write(sys.stdin.read())\n"))
    assert (d / "filter.py").stat().st_mode & stat.S_IXUSR and not d.is_symlink()
    with pytest.raises(S.ManifestError, match="already exists"):
        S.write_local(home, "mine", AGENT, None)
    with pytest.raises(S.ManifestError, match="`prompt` or `skills`"):
        S.write_local(home, "broken", {"mode": "agent"}, None)
    assert not (home / S.MANIFEST_DIR / "broken").exists()
    sync(root)
    assert records(root)["mine"]["script"] == "webhook/mine.sh"
    S.remove_local(home, "mine")
    _plan, done = sync(root)
    assert done == ["disabled orphan mine: manifest removed"]
    assert not (home / "scripts" / "webhook" / "mine.sh").exists()


def test_the_cli_round_trip(root: Path, capsys):
    write_route(root, "assistant", "gh-push", NOTIFY)
    assert S.main(["--root", str(root), "--check"]) == 1
    assert "would create gh-push (assistant, local)" in capsys.readouterr().out
    assert S.main(["--root", str(root)]) == 0
    assert "created gh-push" in capsys.readouterr().out
    assert S.main(["--root", str(root), "--check"]) == 0
    assert capsys.readouterr().out.strip() == "in sync"
    assert S.main(["--root", str(root), "validate"]) == 0
    assert "ok assistant/gh-push (notify, local)" in capsys.readouterr().out
