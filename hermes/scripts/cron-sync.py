#!/usr/bin/env python3
"""cron-sync — reconcile a profile's ``cron.d/`` manifests into Hermes' cron store.

A tracked cron job is a directory ``<HERMES_HOME>/cron.d/<name>/`` holding ``job.yaml``
(schedule, mode, prompt, skills, delivery) and, when the job runs a script, an executable
``run.sh``. The directory is a link into a repository (public or private) or a real directory
the profile wrote for itself; cron-sync treats both alike and records which it was. Hermes'
``jobs.json`` is only ever derived from these directories, never edited by hand:

  * every manifest has exactly one job carrying ``managed.manifest == <name>``; it is created
    when missing and its definition fields are rewritten when they differ from the manifest;
  * a managed job whose manifest is gone is paused with reason ``ORPHAN_REASON`` (removed only
    with ``--prune``), and resumed when the manifest returns;
  * a job without a ``managed`` marker is never touched; one that shares a manifest's name is
    reported as a conflict until ``adopt`` stamps the marker on it.

Hermes' scheduler runs only a script inside ``<HERMES_HOME>/scripts`` (real paths, no links),
so each ``run.sh`` is reached through a generated wrapper ``scripts/cron/<name>.sh``.

Run on ``hermes-python`` (the runtime's ``cron.jobs`` API does the writes under its lock).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

try:  # Hermes' own YAML reader (its runtime and test interpreter ship no PyYAML)
    import hermes_yaml as yaml
except ImportError:
    import yaml

MANIFEST_DIR = "cron.d"
MANIFEST_FILE = "job.yaml"
RUN_SCRIPT = "run.sh"
WRAPPER_DIR = "cron"
MARKER = "managed"
ORPHAN_REASON = "cron-sync: manifest removed"
MANIFEST_PAUSE_REASON = "cron-sync: paused by manifest"
OWN_PAUSE_REASONS = frozenset({ORPHAN_REASON, MANIFEST_PAUSE_REASON})
MODES = ("no_agent", "prompt", "monitor")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
KNOWN_KEYS = frozenset({
    "schedule", "mode", "prompt", "skills", "deliver", "failure_deliver", "repeat", "paused",
    "monitor_url", "workdir", "context_from", "enabled_toolsets", "attach_to_session", "origin",
})
# Keys only a profile's own (local) manifest may carry: they name the conversation the job was
# asked in, so a tracked manifest never holds them (test_cron_manifests refuses it).
LOCAL_ONLY_KEYS = frozenset({"origin"})
# The job-record fields a manifest owns; everything else (run state, counters, origin) is Hermes'.
DEFINITION_FIELDS = (
    "schedule", "no_agent", "script", "monitor_script", "monitor_url", "prompt", "skills",
    "deliver", "failure_deliver", "repeat", "workdir", "context_from", "enabled_toolsets",
    "attach_to_session",
)


class ManifestError(ValueError):
    """A manifest that cannot become a job; the message names the manifest and the reason."""


@dataclass
class Manifest:
    name: str
    path: Path
    source: str  # "repo" (the directory is a link) or "local" (a real directory)
    spec: dict[str, Any]
    run_script: Optional[Path]

    @property
    def mode(self) -> str:
        return self.spec["mode"]

    @property
    def paused(self) -> Optional[bool]:
        return self.spec.get("paused")

    def wrapper_name(self) -> str:
        return f"{WRAPPER_DIR}/{self.name}.sh"

    def definition(self) -> dict[str, Any]:
        """The job-record fields this manifest asks for (the comparison and update payload)."""
        script = self.wrapper_name() if self.run_script else None
        spec = self.spec
        return {
            "schedule": spec["schedule"],
            "no_agent": self.mode == "no_agent",
            "script": script if self.mode != "monitor" else None,
            "monitor_script": script if self.mode == "monitor" else None,
            "monitor_url": spec.get("monitor_url") if self.mode == "monitor" else None,
            "prompt": (spec.get("prompt") or "").strip(),
            "skills": list(spec.get("skills") or []),
            "deliver": spec.get("deliver") or "local",
            "failure_deliver": spec.get("failure_deliver"),
            "repeat": spec.get("repeat"),
            "workdir": spec.get("workdir"),
            "context_from": list(spec["context_from"]) if spec.get("context_from") else None,
            "enabled_toolsets": list(spec["enabled_toolsets"]) if spec.get("enabled_toolsets") is not None else None,
            "attach_to_session": spec.get("attach_to_session"),
        }


# ---------------------------------------------------------------------------
# Manifests
# ---------------------------------------------------------------------------

def _text(value: Any, key: str, name: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ManifestError(f"{name}: `{key}` must be a string")
    return value.strip() or None


def validate_spec(name: str, spec: Any, run_script: Optional[Path]) -> dict[str, Any]:
    """Check one manifest's shape against the invariants Hermes enforces at create time (and a
    few this layout adds), so a broken manifest fails here with its name rather than at the
    runtime's API with a job id. Returns the cleaned spec."""
    if not NAME_RE.match(name):
        raise ManifestError(f"{name}: directory name must match {NAME_RE.pattern}")
    if not isinstance(spec, dict):
        raise ManifestError(f"{name}: {MANIFEST_FILE} must be a mapping")
    unknown = sorted(set(spec) - KNOWN_KEYS)
    if unknown:
        raise ManifestError(f"{name}: unknown key(s) {', '.join(unknown)}")
    clean: dict[str, Any] = {}
    schedule = _text(spec.get("schedule"), "schedule", name)
    if not schedule:
        raise ManifestError(f"{name}: `schedule` is required")
    if schedule.lower().startswith("in "):
        raise ManifestError(
            f"{name}: relative one-shot schedules (`in 30m`) re-derive on every sync; use a timestamp")
    clean["schedule"] = schedule
    mode = spec.get("mode")
    if mode not in MODES:
        raise ManifestError(f"{name}: `mode` must be one of {', '.join(MODES)}")
    clean["mode"] = mode
    prompt = _text(spec.get("prompt"), "prompt", name)
    skills = spec.get("skills")
    if skills is not None:
        if not isinstance(skills, list) or not all(isinstance(s, str) and s.strip() for s in skills):
            raise ManifestError(f"{name}: `skills` must be a list of non-empty strings")
        skills = [s.strip() for s in skills]
    monitor_url = _text(spec.get("monitor_url"), "monitor_url", name)
    if mode == "no_agent":
        if run_script is None:
            raise ManifestError(f"{name}: mode no_agent needs {RUN_SCRIPT} (the script is the job)")
        if prompt or skills:
            raise ManifestError(f"{name}: mode no_agent runs no model; drop `prompt` and `skills`")
        if monitor_url:
            raise ManifestError(f"{name}: `monitor_url` belongs to mode monitor")
    else:
        if not prompt and not skills:
            raise ManifestError(f"{name}: mode {mode} needs `prompt` or `skills`")
        if mode == "monitor":
            if bool(run_script) == bool(monitor_url):
                raise ManifestError(
                    f"{name}: mode monitor needs exactly one of {RUN_SCRIPT} or `monitor_url`")
            if monitor_url and not monitor_url.lower().startswith(("http://", "https://")):
                raise ManifestError(f"{name}: `monitor_url` must be http(s)")
        elif monitor_url:
            raise ManifestError(f"{name}: `monitor_url` belongs to mode monitor")
    if run_script is not None and not run_script.stat().st_mode & stat.S_IXUSR:
        raise ManifestError(f"{name}: {RUN_SCRIPT} must be executable (chmod +x)")
    if prompt:
        clean["prompt"] = prompt
    if skills:
        clean["skills"] = skills
    if monitor_url:
        clean["monitor_url"] = monitor_url
    for key in ("deliver", "failure_deliver", "workdir"):
        value = _text(spec.get(key), key, name)
        if value:
            clean[key] = value
    repeat = spec.get("repeat")
    if repeat is not None:
        if not isinstance(repeat, int) or isinstance(repeat, bool) or repeat < 1:
            raise ManifestError(f"{name}: `repeat` must be a positive integer")
        clean["repeat"] = repeat
    for key in ("paused", "attach_to_session"):
        value = spec.get(key)
        if value is not None:
            if not isinstance(value, bool):
                raise ManifestError(f"{name}: `{key}` must be true or false")
            clean[key] = value
    for key in ("context_from", "enabled_toolsets"):
        value = spec.get(key)
        if value is not None:
            if not isinstance(value, list) or not all(isinstance(s, str) and s.strip() for s in value):
                raise ManifestError(f"{name}: `{key}` must be a list of non-empty strings")
            clean[key] = [s.strip() for s in value]  # [] is kept: an explicit zero-tool allowlist
    if mode == "no_agent" and (clean.get("context_from") or clean.get("enabled_toolsets") is not None
                               or clean.get("attach_to_session") is not None):
        raise ManifestError(
            f"{name}: mode no_agent runs no model; drop `context_from`, `enabled_toolsets`, `attach_to_session`")
    origin = spec.get("origin")
    if origin is not None:
        if not isinstance(origin, dict) or not origin.get("platform") or not origin.get("chat_id"):
            raise ManifestError(f"{name}: `origin` must be a mapping with `platform` and `chat_id`")
        clean["origin"] = {k: (None if v is None else str(v)) for k, v in origin.items()}
    return clean


def load_manifest(directory: Path) -> Manifest:
    name = directory.name
    manifest_file = directory / MANIFEST_FILE
    if not manifest_file.is_file():
        raise ManifestError(f"{name}: no {MANIFEST_FILE}")
    try:
        spec = yaml.safe_load(manifest_file.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ManifestError(f"{name}: {MANIFEST_FILE} is not valid YAML: {exc}") from exc
    run_script = directory / RUN_SCRIPT
    run = run_script.resolve() if run_script.is_file() else None
    clean = validate_spec(name, spec, run)
    source = "repo" if directory.is_symlink() else "local"
    return Manifest(name=name, path=directory, source=source, spec=clean, run_script=run)


def load_manifests(home: Path) -> tuple[list[Manifest], list[str]]:
    """Every manifest under ``<home>/cron.d``, plus the errors of the ones that cannot load (a
    broken manifest never blocks the others, and never pauses its job as an orphan)."""
    root = home / MANIFEST_DIR
    manifests: list[Manifest] = []
    errors: list[str] = []
    if not root.is_dir():
        return manifests, errors
    for child in sorted(root.iterdir()):
        if child.name.startswith("."):
            continue
        if not child.is_dir():
            errors.append(f"{child.name}: not a directory (every entry of {MANIFEST_DIR}/ is a job)")
            continue
        try:
            manifests.append(load_manifest(child))
        except ManifestError as exc:
            errors.append(str(exc))
    return manifests, errors


# ---------------------------------------------------------------------------
# Wrappers
# ---------------------------------------------------------------------------

def wrapper_text(name: str) -> str:
    """The wrapper lives at ``<home>/scripts/cron/<name>.sh``, so it is the one party that knows
    which profile owns the job: it names that home in ``HERMES_HOME`` for the script, whatever
    the gateway's own process environment says under multiplex, and reaches the script through
    the manifest's path under that home (a link for a repository job), so no checkout path is
    baked in and a moved checkout needs only the installer's relink."""
    return (
        "#!/bin/sh\n"
        f"# Generated by cron-sync from {MANIFEST_DIR}/{name}/{RUN_SCRIPT} — do not edit.\n"
        'HERMES_HOME="$(cd "$(dirname "$0")/../.." && pwd)"\n'
        "export HERMES_HOME\n"
        f'exec "$HERMES_HOME/{MANIFEST_DIR}/{name}/{RUN_SCRIPT}" "$@"\n'
    )


def sync_wrappers(home: Path, manifests: list[Manifest], write: bool) -> list[str]:
    """Write ``scripts/cron/<name>.sh`` for every manifest with a run script and drop the ones
    no manifest names any more. Returns the changes (made, or pending under --check)."""
    changes: list[str] = []
    wrapper_dir = home / "scripts" / WRAPPER_DIR
    wanted: dict[str, str] = {
        f"{m.name}.sh": wrapper_text(m.name) for m in manifests if m.run_script
    }
    for filename, text in wanted.items():
        path = wrapper_dir / filename
        if path.is_file() and path.read_text(encoding="utf-8") == text and path.stat().st_mode & stat.S_IXUSR:
            continue
        changes.append(f"wrapper {path.relative_to(home)}")
        if write:
            wrapper_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            path.chmod(0o755)
    if wrapper_dir.is_dir():
        for path in sorted(wrapper_dir.glob("*.sh")):
            if path.name in wanted:
                continue
            changes.append(f"drop wrapper {path.relative_to(home)}")
            if write:
                path.unlink()
    return changes


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------

@dataclass
class Plan:
    home: Path
    create: list[Manifest] = field(default_factory=list)
    update: list[tuple[Manifest, dict[str, Any], dict[str, Any]]] = field(default_factory=list)
    pause: list[tuple[Manifest, dict[str, Any]]] = field(default_factory=list)
    resume: list[tuple[Manifest, dict[str, Any]]] = field(default_factory=list)
    restamp: list[tuple[Manifest, dict[str, Any]]] = field(default_factory=list)
    orphan_pause: list[dict[str, Any]] = field(default_factory=list)
    orphan_remove: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    wrappers: list[str] = field(default_factory=list)

    def pending(self) -> bool:
        return bool(
            self.create or self.update or self.pause or self.resume or self.restamp
            or self.orphan_pause or self.orphan_remove or self.wrappers)

    def failed(self) -> bool:
        return bool(self.conflicts or self.errors)


def _runtime():
    """The runtime's cron API, imported late so a manifest-only command (``add``, ``validate``)
    needs no Hermes."""
    from cron import jobs  # hermes-agent on sys.path (hermes-python)
    return jobs


def _marker(manifest: Manifest, now: str) -> dict[str, str]:
    return {"manifest": manifest.name, "source": manifest.source, "synced_at": now}


def _stored_definition(job: dict[str, Any]) -> dict[str, Any]:
    """The job's current definition in the manifest's terms, so the two compare directly."""
    return {
        "schedule": job.get("schedule"),
        "no_agent": bool(job.get("no_agent")),
        "script": job.get("script") or None,
        "monitor_script": job.get("monitor_script") or None,
        "monitor_url": job.get("monitor_url") or None,
        "prompt": (job.get("prompt") or "").strip(),
        "skills": list(job.get("skills") or []),
        "deliver": job.get("deliver") or "local",
        "failure_deliver": job.get("failure_deliver") or None,
        "repeat": (job.get("repeat") or {}).get("times"),
        "workdir": job.get("workdir") or None,
        "context_from": list(job["context_from"]) if job.get("context_from") else None,
        "enabled_toolsets": list(job["enabled_toolsets"]) if job.get("enabled_toolsets") is not None else None,
        "attach_to_session": job.get("attach_to_session"),
    }


def _diff(manifest: Manifest, job: dict[str, Any], jobs_api) -> dict[str, Any]:
    """The update payload that brings ``job`` to the manifest: empty when nothing differs."""
    desired = manifest.definition()
    stored = _stored_definition(job)
    parsed = jobs_api.parse_schedule(desired["schedule"])
    if parsed.get("kind") == "once" and desired["repeat"] is None:
        desired["repeat"] = 1  # what create_job derives for a one-shot
    updates: dict[str, Any] = {}
    for key in DEFINITION_FIELDS:
        want, have = desired[key], stored[key]
        if key == "schedule":
            if parsed != have:
                updates[key] = want
        elif want != have:
            updates[key] = want
    return updates


def _is_paused(job: dict[str, Any]) -> bool:
    return not job.get("enabled", True)


def build_plan(home: Path, manifests: list[Manifest], errors: list[str], jobs: list[dict[str, Any]],
               jobs_api, *, prune: bool) -> Plan:
    plan = Plan(home=home, errors=list(errors))
    managed: dict[str, list[dict[str, Any]]] = {}
    for job in jobs:
        marker = job.get(MARKER)
        if isinstance(marker, dict) and marker.get("manifest"):
            managed.setdefault(str(marker["manifest"]), []).append(job)
    by_manifest: dict[str, dict[str, Any]] = {}
    for name, found in managed.items():
        if len(found) == 1:
            by_manifest[name] = found[0]
        else:  # two jobs claim one manifest (a crashed create, a doubled adopt): a person decides
            ids = ", ".join(j["id"] for j in found)
            plan.conflicts.append(
                f"{name}: {len(found)} jobs carry its marker ({ids}); remove all but one with `hermes cron remove`")
    unmanaged_by_name: dict[str, list[dict[str, Any]]] = {}
    for job in jobs:
        if not isinstance(job.get(MARKER), dict):
            unmanaged_by_name.setdefault(str(job.get("name") or ""), []).append(job)

    for manifest in manifests:
        if len(managed.get(manifest.name, ())) > 1:
            continue
        job = by_manifest.pop(manifest.name, None)
        if job is None:
            same_name = unmanaged_by_name.get(manifest.name)
            if same_name:
                ids = ", ".join(j["id"] for j in same_name)
                plan.conflicts.append(
                    f"{manifest.name}: an unmanaged job of that name exists ({ids}); "
                    f"`cron-sync adopt {manifest.name}` takes it over, or rename one of them")
                continue
            plan.create.append(manifest)
            continue
        updates = _diff(manifest, job, jobs_api)
        if updates:
            plan.update.append((manifest, job, updates))
        if job[MARKER].get("source") != manifest.source:
            plan.restamp.append((manifest, job))
        paused = _is_paused(job)
        if manifest.paused is True and not paused:
            plan.pause.append((manifest, job))
        elif manifest.paused is False and paused:
            plan.resume.append((manifest, job))
        elif manifest.paused is None and paused and job.get("paused_reason") in OWN_PAUSE_REASONS:
            plan.resume.append((manifest, job))  # a pause of the sync's own is the sync's to lift

    failed_names = {e.split(":", 1)[0] for e in errors}
    for name, job in by_manifest.items():
        if name in failed_names:
            continue  # a manifest that failed to load is not gone
        if prune:
            plan.orphan_remove.append(job)
        elif not (_is_paused(job) and job.get("paused_reason") == ORPHAN_REASON):
            plan.orphan_pause.append(job)
    return plan


def apply_plan(plan: Plan, jobs_api, now: str) -> list[str]:
    done: list[str] = []
    for manifest in plan.create:
        d = manifest.definition()
        kwargs: dict[str, Any] = dict(
            prompt=d["prompt"], schedule=d["schedule"], name=manifest.name, repeat=d["repeat"],
            deliver=d["deliver"], skills=d["skills"], script=d["script"], no_agent=d["no_agent"],
            monitor_script=d["monitor_script"], monitor_url=d["monitor_url"],
            failure_deliver=d["failure_deliver"], workdir=d["workdir"],
            context_from=d["context_from"], enabled_toolsets=d["enabled_toolsets"],
            attach_to_session=d["attach_to_session"], origin=manifest.spec.get("origin"),
        )
        if manifest.paused is True:
            kwargs.update(paused=True, paused_reason=MANIFEST_PAUSE_REASON)
        job = jobs_api.create_job(**kwargs)
        jobs_api.update_job(job["id"], {MARKER: _marker(manifest, now)})
        done.append(f"created {manifest.name} ({job['id']}, {manifest.source})")
    for manifest, job, updates in plan.update:
        jobs_api.update_job(job["id"], {**updates, MARKER: _marker(manifest, now)})
        done.append(f"updated {manifest.name}: {', '.join(sorted(updates))}")
    for manifest, job in plan.restamp:
        jobs_api.update_job(job["id"], {MARKER: _marker(manifest, now)})
        done.append(f"restamped {manifest.name} as {manifest.source}")
    for manifest, job in plan.pause:
        jobs_api.pause_job(job["id"], MANIFEST_PAUSE_REASON)
        done.append(f"paused {manifest.name} (manifest)")
    for manifest, job in plan.resume:
        jobs_api.resume_job(job["id"])
        done.append(f"resumed {manifest.name}")
    for job in plan.orphan_pause:
        jobs_api.pause_job(job["id"], ORPHAN_REASON)
        done.append(f"paused orphan {job['name']} ({job['id']}): manifest removed")
    for job in plan.orphan_remove:
        jobs_api.remove_job(job["id"])
        done.append(f"removed orphan {job['name']} ({job['id']})")
    return done


def render(plan: Plan, done: Optional[list[str]]) -> str:
    lines: list[str] = []
    lines.extend(f"ERROR manifest {e}" for e in plan.errors)
    lines.extend(f"CONFLICT {c}" for c in plan.conflicts)
    if done is not None:
        lines.extend(f"  {d}" for d in done)
        lines.extend(f"  {w}" for w in plan.wrappers)
        if not done and not plan.wrappers and not plan.failed():
            lines.append("  in sync")
        return "\n".join(lines)
    lines.extend(f"  would create {m.name} ({m.source})" for m in plan.create)
    lines.extend(f"  would update {m.name}: {', '.join(sorted(u))}" for m, _j, u in plan.update)
    lines.extend(f"  would restamp {m.name} as {m.source}" for m, _j in plan.restamp)
    lines.extend(f"  would pause {m.name} (manifest)" for m, _j in plan.pause)
    lines.extend(f"  would resume {m.name}" for m, _j in plan.resume)
    lines.extend(f"  would pause orphan {j['name']} ({j['id']})" for j in plan.orphan_pause)
    lines.extend(f"  would remove orphan {j['name']} ({j['id']})" for j in plan.orphan_remove)
    lines.extend(f"  would write {w}" for w in plan.wrappers)
    if not plan.pending() and not plan.failed():
        lines.append("  in sync")
    return "\n".join(lines)


def _with_home(home: Path, fn: Callable[[Any], Any]) -> Any:
    """Run ``fn(jobs_api)`` with the runtime pointed at ``home``: its cron store and the
    ``HERMES_HOME`` the rest of the runtime reads, without touching the process environment."""
    jobs_api = _runtime()
    from hermes_constants import reset_hermes_home_override, set_hermes_home_override
    token = set_hermes_home_override(home)
    try:
        with jobs_api.use_cron_store(home):
            return fn(jobs_api)
    finally:
        reset_hermes_home_override(token)


def sync_home(home: Path, *, check: bool, prune: bool) -> tuple[Plan, Optional[list[str]]]:
    """Reconcile one profile home. Under ``check`` nothing is written and the plan says what
    would be; otherwise the loadable manifests are applied even when another one failed (the
    failure is reported, and the exit status says so)."""
    home = home.expanduser().resolve()
    manifests, errors = load_manifests(home)

    def run(jobs_api):
        jobs = jobs_api.load_jobs()
        plan = build_plan(home, manifests, errors, jobs, jobs_api, prune=prune)
        plan.wrappers = sync_wrappers(home, manifests, write=not check)
        if check:
            return plan, None
        now = jobs_api._hermes_now().isoformat()
        return plan, apply_plan(plan, jobs_api, now)

    return _with_home(home, run)


def adopt(home: Path, name: str) -> str:
    """Stamp the unmanaged job named ``name`` as the manifest's job (then a sync brings its
    definition to the manifest). Refuses when the name is ambiguous or already managed."""
    home = home.expanduser().resolve()
    manifest = load_manifest(home / MANIFEST_DIR / name)

    def run(jobs_api):
        jobs = jobs_api.load_jobs()
        if any(isinstance(j.get(MARKER), dict) and j[MARKER].get("manifest") == name for j in jobs):
            raise ManifestError(f"{name}: already managed")
        candidates = [j for j in jobs if j.get("name") == name and not isinstance(j.get(MARKER), dict)]
        if len(candidates) != 1:
            raise ManifestError(f"{name}: {len(candidates)} unmanaged job(s) of that name; need exactly one")
        job = candidates[0]
        jobs_api.update_job(job["id"], {MARKER: _marker(manifest, jobs_api._hermes_now().isoformat())})
        return f"adopted {name} ({job['id']}, {manifest.source}); run a sync to apply the manifest"

    return _with_home(home, run)


def prune_completed(home: Path) -> list[str]:
    """Remove local one-shot jobs that have fired (state completed) together with their manifest
    directories: a throwaway job the profile wrote for itself is finished once it ran."""
    home = home.expanduser().resolve()

    def run(jobs_api):
        done: list[str] = []
        for job in jobs_api.load_jobs():
            marker = job.get(MARKER)
            if not isinstance(marker, dict) or marker.get("source") != "local":
                continue
            if job.get("state") != "completed":
                continue
            directory = home / MANIFEST_DIR / str(marker.get("manifest"))
            jobs_api.remove_job(job["id"])
            if directory.is_dir() and not directory.is_symlink():
                shutil.rmtree(directory)
            done.append(f"pruned completed {job['name']} ({job['id']})")
        return done

    return _with_home(home, run)


# ---------------------------------------------------------------------------
# Local manifests (the profile's own jobs)
# ---------------------------------------------------------------------------

def write_local(home: Path, name: str, spec: dict[str, Any], run_script: Optional[str]) -> Path:
    """Create ``<home>/cron.d/<name>/`` as a real directory; a manifest that fails validation
    leaves nothing behind. Refuses an existing entry."""
    home = home.expanduser().resolve()
    directory = home / MANIFEST_DIR / name
    if directory.exists() or directory.is_symlink():
        raise ManifestError(f"{name}: already exists in {MANIFEST_DIR}/")
    if not NAME_RE.match(name):
        raise ManifestError(f"{name}: directory name must match {NAME_RE.pattern}")
    if not isinstance(spec, dict):
        raise ManifestError(f"{name}: spec must be a mapping")
    directory.mkdir(parents=True)
    try:
        (directory / MANIFEST_FILE).write_text(
            yaml.safe_dump(spec, sort_keys=False, allow_unicode=True), encoding="utf-8")
        if run_script is not None:
            run = directory / RUN_SCRIPT
            run.write_text(run_script, encoding="utf-8")
            run.chmod(0o755)
        load_manifest(directory)
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    return directory


def remove_local(home: Path, name: str) -> Path:
    """Delete a local manifest directory (never a link: a repository's job is removed in the
    repository). The next sync pauses or prunes its job."""
    home = home.expanduser().resolve()
    directory = home / MANIFEST_DIR / name
    if directory.is_symlink():
        raise ManifestError(f"{name}: a repository job; remove it there and re-run install.sh")
    if not directory.is_dir():
        raise ManifestError(f"{name}: no such local job")
    shutil.rmtree(directory)
    return directory


def drop_local(home: Path, name: str) -> Optional[str]:
    """Remove a local job for good: its directory and its managed job (output included),
    without touching any other orphan. Returns the removed job's id, if it had one."""
    home = home.expanduser().resolve()
    remove_local(home, name)

    def run(jobs_api):
        for job in jobs_api.load_jobs():
            marker = job.get(MARKER)
            if isinstance(marker, dict) and marker.get("manifest") == name:
                jobs_api.remove_job(job["id"])
                return job["id"]
        return None

    job_id = _with_home(home, run)
    sync_wrappers(home, load_manifests(home)[0], write=True)
    return job_id


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def hermes_dir() -> Path:
    return Path(os.environ.get("HERMES_DIR") or "~/.hermes").expanduser()


def profile_homes(args: argparse.Namespace) -> list[Path]:
    if args.home:
        return [Path(args.home)]
    if args.profile:
        return [hermes_dir() / "profiles" / args.profile]
    root = hermes_dir() / "profiles"
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if (p / MANIFEST_DIR).is_dir())


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--profile", help="a profile under $HERMES_DIR/profiles (default: all with cron.d/)")
    scope.add_argument("--home", help="a HERMES_HOME directory")
    parser.add_argument("--check", action="store_true", help="sync: report what would change; write nothing")
    parser.add_argument("--prune", action="store_true", help="sync: remove orphan jobs instead of pausing them")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("sync", help="reconcile manifests into jobs.json (the default)")
    p_adopt = sub.add_parser("adopt", help="stamp an unmanaged job of the manifest's name as its job")
    p_adopt.add_argument("name")
    sub.add_parser("prune-completed", help="remove local one-shot jobs that have fired, with their directories")
    p_add = sub.add_parser("add", help="write a local manifest directory from a JSON spec on stdin")
    p_add.add_argument("name")
    p_add.add_argument("--run-script", help="file whose content becomes run.sh")
    p_remove = sub.add_parser("remove", help="delete a local manifest directory")
    p_remove.add_argument("name")
    sub.add_parser("validate", help="load every manifest and report errors; touches no job")
    args = parser.parse_args(argv)
    command = args.command or "sync"

    homes = profile_homes(args)
    if not homes:
        print("cron-sync: no profile with a cron.d/ directory", file=sys.stderr)
        return 0
    if command in ("adopt", "add", "remove") and not (args.profile or args.home):
        parser.error(f"{command} needs --profile or --home")
    rc = 0
    for home in homes:
        label = home.name
        try:
            if command == "sync":
                plan, done = sync_home(home, check=args.check, prune=args.prune)
                print(f"[{label}]\n{render(plan, done)}")
                if plan.failed() or (args.check and plan.pending()):
                    rc = 1
            elif command == "validate":
                manifests, errors = load_manifests(home.expanduser().resolve())
                print(f"[{label}]")
                for e in errors:
                    print(f"ERROR manifest {e}")
                for m in manifests:
                    print(f"  ok {m.name} ({m.mode}, {m.source})")
                if errors:
                    rc = 1
            elif command == "adopt":
                print(adopt(home, args.name))
            elif command == "prune-completed":
                for line in prune_completed(home):
                    print(f"  {line}")
            elif command == "add":
                spec = json.load(sys.stdin)
                run_script = Path(args.run_script).read_text(encoding="utf-8") if args.run_script else None
                print(f"  wrote {write_local(home, args.name, spec, run_script)}")
            elif command == "remove":
                print(f"  removed {remove_local(home, args.name)}")
        except ManifestError as exc:
            print(f"ERROR {exc}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
