#!/usr/bin/env python3
"""webhook-sync — derive the gateway's webhook routes from every profile's ``webhook.d/``.

A tracked webhook route is a directory ``<HERMES_HOME>/webhook.d/<name>/`` of one profile,
holding ``route.yaml`` (what the route does when a signed POST arrives) and, when the payload is
filtered or reshaped first, an executable ``filter.sh`` or ``filter.py``. The directory is a link
into a repository or a real directory the profile wrote for itself; webhook-sync records which.

The runtime has one webhook listener, the root profile's, and reads its dynamic routes from the
root home's ``webhook_subscriptions.json`` (hot-reloaded on every POST, no restart). Every
profile's ``webhook.d/`` is derived into that one file, each record bound to its profile
(``POST /p/<profile>/webhooks/<name>``) and carrying ``managed.manifest == <name>``:

  * a record is created when missing and rewritten when it differs from its manifest;
  * a managed record whose manifest is gone is disabled (the runtime answers 403; removed only
    with ``--prune``) and enabled again when the manifest returns;
  * a record without a ``managed`` marker is never touched; one sharing a manifest's name is
    reported as a conflict until ``adopt`` stamps the marker on it.

A route carries no secret: every POST is checked against the gateway's global ``WEBHOOK_SECRET``
(a Keychain item the launcher injects), so a manifest holds nothing a repository must not.

Run on ``hermes-python`` (the runtime's own subscriptions writer takes its lock and publishes by
atomic rename). The shape shared with cron-sync is ``manifestlib``.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


def _load_sibling(name: str, filename: str):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent / filename)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


lib = _load_sibling("hermes_manifestlib", "manifestlib.py")
yaml = lib.yaml
ManifestError = lib.ManifestError
MARKER = lib.MARKER
NAME_RE = lib.NAME_RE

MANIFEST_DIR = "webhook.d"
MANIFEST_FILE = "route.yaml"
FILTER_SCRIPTS = ("filter.sh", "filter.py")
WRAPPER_DIR = "webhook"
CRON_MANIFEST_DIR = "cron.d"  # a `job` route names a job tracked beside it
SUBSCRIPTIONS_FILE = "webhook_subscriptions.json"
ORPHAN_REASON = "webhook-sync: manifest removed"
MODES = ("notify", "agent", "job")
KNOWN_KEYS = frozenset({
    "mode", "events", "filters", "prompt", "skills", "deliver", "deliver_extra", "cron_job",
    "mirror_to_session", "coalesce", "toolsets", "paused",
})
# The record fields a manifest owns, `enabled` included: a route is on unless its manifest says
# `paused` (a dashboard switch-off is undone by the next sync, as a hand edit of a cron job is).
# The runtime's own fields (description, created_at, a secret of its own) and the marker are
# left alone.
DEFINITION_FIELDS = (
    "profile", "events", "filters", "prompt", "skills", "deliver", "deliver_extra", "deliver_only",
    "cron_job", "script", "mirror_to_session", "coalesce", "toolsets", "enabled",
)


@dataclass
class Route:
    name: str
    path: Path
    profile: str
    source: str  # "repo" (the directory is a link) or "local" (a real directory)
    spec: dict[str, Any]
    filter_script: Optional[Path]

    @property
    def mode(self) -> str:
        return self.spec["mode"]

    @property
    def paused(self) -> bool:
        return bool(self.spec.get("paused"))

    def wrapper_name(self) -> str:
        return f"{WRAPPER_DIR}/{self.name}.sh"

    def definition(self) -> dict[str, Any]:
        """The record fields this manifest asks for, in the runtime's route shape. Optional
        fields are None when the manifest has none; ``record()`` leaves those out of the file,
        since the runtime reads a missing key with a default but trips over an explicit null
        (``deliver_extra: null`` reached ``.items()``)."""
        spec = self.spec
        return {
            "profile": self.profile,
            "events": list(spec.get("events") or []),
            "filters": spec.get("filters"),
            "prompt": spec.get("prompt") or "",
            "skills": list(spec.get("skills") or []),
            "deliver": spec.get("deliver") or "log",
            "deliver_extra": spec.get("deliver_extra"),
            "deliver_only": self.mode == "notify",
            "cron_job": spec.get("cron_job") if self.mode == "job" else None,
            "script": self.wrapper_name() if self.filter_script else None,
            "mirror_to_session": bool(spec.get("mirror_to_session")),
            "coalesce": spec.get("coalesce"),
            "toolsets": spec.get("toolsets"),
            "enabled": not self.paused,
        }

    def record(self) -> dict[str, Any]:
        """``definition()`` as written to the file: no key holds null."""
        return {k: v for k, v in self.definition().items() if v is not None}


# ---------------------------------------------------------------------------
# Manifests
# ---------------------------------------------------------------------------

def validate_spec(name: str, spec: Any, filter_script: Optional[Path], cron_names: frozenset[str]) -> dict[str, Any]:
    """Check one manifest against what the runtime's route handler and its own startup check
    accept, so a broken route fails here with its name rather than at the first POST (which
    the runtime answers with a log line and a 4xx). ``cron_names`` are the jobs tracked beside
    it, which a ``job`` route may name. Returns the cleaned spec."""
    lib.check_name(name)
    if not isinstance(spec, dict):
        raise ManifestError(f"{name}: {MANIFEST_FILE} must be a mapping")
    unknown = sorted(set(spec) - KNOWN_KEYS)
    if unknown:
        raise ManifestError(f"{name}: unknown key(s) {', '.join(unknown)}")
    mode = spec.get("mode")
    if mode not in MODES:
        raise ManifestError(f"{name}: `mode` must be one of {', '.join(MODES)}")
    clean: dict[str, Any] = {"mode": mode}
    events = lib.string_list(spec.get("events"), "events", name)
    if events:
        clean["events"] = events
    filters = spec.get("filters")
    if filters is not None:
        if not isinstance(filters, (list, dict)):
            raise ManifestError(f"{name}: `filters` must be a list of filter specs or one spec")
        clean["filters"] = filters
    prompt = lib.text_field(spec.get("prompt"), "prompt", name)
    skills = lib.string_list(spec.get("skills"), "skills", name)
    deliver = lib.text_field(spec.get("deliver"), "deliver", name)
    cron_job = lib.text_field(spec.get("cron_job"), "cron_job", name)
    mirror = lib.bool_field(spec.get("mirror_to_session"), "mirror_to_session", name)
    if mode == "notify":
        if not prompt:
            raise ManifestError(f"{name}: mode notify sends `prompt` as the message; it is required")
        if skills:
            raise ManifestError(f"{name}: mode notify runs no model; drop `skills`")
        if not deliver or deliver == "log":
            raise ManifestError(f"{name}: mode notify needs a real `deliver` target (telegram, discord, ...)")
        if cron_job:
            raise ManifestError(f"{name}: `cron_job` belongs to mode job")
    elif mode == "agent":
        if not prompt and not skills:
            raise ManifestError(f"{name}: mode agent needs `prompt` or `skills`")
        if cron_job:
            raise ManifestError(f"{name}: `cron_job` belongs to mode job")
    else:  # job
        if not cron_job:
            raise ManifestError(f"{name}: mode job needs `cron_job` (a {CRON_MANIFEST_DIR}/ name of this profile)")
        if cron_job not in cron_names:
            raise ManifestError(f"{name}: `cron_job` {cron_job} is not a {CRON_MANIFEST_DIR}/ directory of this profile")
        if skills or deliver or mirror is not None or spec.get("toolsets") is not None:
            raise ManifestError(
                f"{name}: mode job fires the job, whose own skills, delivery and tools apply; "
                "drop `skills`, `deliver`, `mirror_to_session`, `toolsets`")
    if prompt:
        clean["prompt"] = prompt
    if skills:
        clean["skills"] = skills
    if deliver:
        clean["deliver"] = deliver
    if cron_job:
        clean["cron_job"] = cron_job
    if mirror is not None:
        clean["mirror_to_session"] = mirror
    extra = spec.get("deliver_extra")
    if extra is not None:
        if not isinstance(extra, dict) or not extra or not all(
                isinstance(v, (str, int)) and not isinstance(v, bool) for v in extra.values()):
            raise ManifestError(f"{name}: `deliver_extra` must be a mapping of strings or integers")
        unknown_extra = sorted(set(extra) - {"chat_id", "thread_id", "message_thread_id"})
        if unknown_extra:
            raise ManifestError(f"{name}: `deliver_extra` takes chat_id, thread_id, message_thread_id; not {', '.join(unknown_extra)}")
        clean["deliver_extra"] = {k: str(v) for k, v in extra.items()}
    coalesce = spec.get("coalesce")
    if coalesce is not None:
        if not isinstance(coalesce, dict):
            raise ManifestError(f"{name}: `coalesce` must be a mapping")
        clean["coalesce"] = coalesce
    toolsets = lib.string_list(spec.get("toolsets"), "toolsets", name)
    if toolsets is not None:
        clean["toolsets"] = toolsets
    paused = lib.bool_field(spec.get("paused"), "paused", name)
    if paused is not None:
        clean["paused"] = paused
    return clean


def cron_manifest_names(home: Path) -> frozenset[str]:
    root = home / CRON_MANIFEST_DIR
    if not root.is_dir():
        return frozenset()
    return frozenset(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))


def load_route(directory: Path, profile: str, cron_names: frozenset[str]) -> Route:
    name = directory.name
    spec = lib.read_spec(directory, MANIFEST_FILE)
    scripts = [s for s in (lib.executable_script(directory, f) for f in FILTER_SCRIPTS) if s]
    if len(scripts) > 1:
        raise ManifestError(f"{name}: one filter script, {' or '.join(FILTER_SCRIPTS)}, not both")
    clean = validate_spec(name, spec, scripts[0] if scripts else None, cron_names)
    return Route(name=name, path=directory, profile=profile, source=lib.source_of(directory), spec=clean,
                 filter_script=scripts[0] if scripts else None)


def load_routes(home: Path, profile: str) -> tuple[list[Route], list[str]]:
    """Every route under ``<home>/webhook.d``, plus the errors of the ones that cannot load (a
    broken manifest never blocks the others, and never disables its record as an orphan)."""
    routes: list[Route] = []
    errors: list[str] = []
    cron_names = cron_manifest_names(home)
    for child, error in lib.iter_manifest_dirs(home / MANIFEST_DIR, "route"):
        if error:
            errors.append(f"{profile}/{error}")
            continue
        try:
            routes.append(load_route(child, profile, cron_names))
        except ManifestError as exc:
            errors.append(f"{profile}/{exc}")
    return routes, errors


# ---------------------------------------------------------------------------
# Wrappers
# ---------------------------------------------------------------------------

def wrapper_text(route: Route) -> str:
    """``scripts/webhook/<name>.sh`` of the route's profile: the runtime hands the payload on
    stdin and reads the verdict on stdout; the wrapper passes both through."""
    return lib.wrapper_text("webhook-sync", MANIFEST_DIR, route.name, route.filter_script.name)


def sync_wrappers(home: Path, routes: list[Route], broken: set[str], write: bool) -> list[str]:
    """Write a wrapper per route with a filter and drop the ones nothing names. A manifest that
    failed to load (``broken``) keeps whatever wrapper it has: its record is left as it was, and
    that record may still name the wrapper."""
    wanted = {f"{r.name}.sh": wrapper_text(r) for r in routes if r.filter_script}
    directory = home / "scripts" / WRAPPER_DIR
    for name in broken:
        existing = directory / f"{name}.sh"
        if existing.is_file() and existing.name not in wanted:
            wanted[existing.name] = existing.read_text(encoding="utf-8")
    return lib.sync_wrappers(home, WRAPPER_DIR, wanted, write)


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------

@dataclass
class Plan:
    create: list[Route] = field(default_factory=list)
    update: list[tuple[Route, dict[str, Any]]] = field(default_factory=list)
    restamp: list[Route] = field(default_factory=list)
    orphan_disable: list[str] = field(default_factory=list)
    orphan_remove: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    wrappers: list[str] = field(default_factory=list)

    def pending(self) -> bool:
        return bool(self.create or self.update or self.restamp or self.orphan_disable
                    or self.orphan_remove or self.wrappers)

    def failed(self) -> bool:
        return bool(self.conflicts or self.errors)


def _marker(route: Route, now: str) -> dict[str, str]:
    return {**lib.marker(route.name, route.source, now), "profile": route.profile}


def _stored_definition(record: dict[str, Any]) -> dict[str, Any]:
    """The record's current definition in the manifest's terms, so the two compare directly."""
    return {
        "profile": record.get("profile", "default"),
        "events": list(record.get("events") or []),
        "filters": record.get("filters"),
        "prompt": record.get("prompt") or "",
        "skills": list(record.get("skills") or []),
        "deliver": record.get("deliver") or "log",
        "deliver_extra": record.get("deliver_extra"),
        "deliver_only": bool(record.get("deliver_only")),
        "cron_job": record.get("cron_job") or None,
        "script": record.get("script") or None,
        "mirror_to_session": bool(record.get("mirror_to_session")),
        "coalesce": record.get("coalesce"),
        "toolsets": record.get("toolsets"),
        "enabled": record.get("enabled", True) is not False,
    }


def _diff(route: Route, record: dict[str, Any]) -> dict[str, Any]:
    desired, stored = route.definition(), _stored_definition(record)
    updates = {key: desired[key] for key in DEFINITION_FIELDS if desired[key] != stored[key]}
    # A key the record holds as null is drift too: the runtime trips over it, and the update
    # path removes it (apply_plan writes no null).
    updates.update({key: None for key in DEFINITION_FIELDS
                    if key in record and record[key] is None and desired[key] is None})
    return updates


def build_plan(routes: list[Route], errors: list[str], records: dict[str, dict[str, Any]], *,
               prune: bool) -> Plan:
    plan = Plan(errors=list(errors))
    managed: dict[str, list[str]] = {}
    for name, record in records.items():
        marker = lib.marker_of(record)
        if marker:
            managed.setdefault(str(marker["manifest"]), []).append(name)
    by_manifest: dict[str, str] = {}
    for manifest, names in managed.items():
        if len(names) == 1:
            by_manifest[manifest] = names[0]
        else:
            plan.conflicts.append(
                f"{manifest}: {len(names)} routes carry its marker ({', '.join(names)}); remove all but one")
    owners: dict[str, list[str]] = {}
    for route in routes:
        owners.setdefault(route.name, []).append(route.profile)
    for name, profiles in owners.items():
        if len(profiles) > 1:  # a route name is one URL: two profiles cannot both answer it
            plan.conflicts.append(
                f"{name}: tracked by both {' and '.join(profiles)}; rename one of them")
            by_manifest.pop(name, None)  # neither is applied, and the record is not an orphan
    for route in routes:
        if len(owners[route.name]) > 1 or len(managed.get(route.name, ())) > 1:
            continue
        key = by_manifest.pop(route.name, None)
        if key is None:
            record = records.get(route.name)
            if record is not None:  # an unmarked record of that name (hermes webhook subscribe)
                plan.conflicts.append(
                    f"{route.name}: an unmanaged route of that name exists; "
                    f"`webhook-sync adopt {route.profile} {route.name}` takes it over, or rename one of them")
                continue
            plan.create.append(route)
            continue
        record = records[key]
        updates = _diff(route, record)
        if updates:
            plan.update.append((route, updates))
        marker = record[MARKER]
        if marker.get("source") != route.source or marker.get("profile") != route.profile:
            plan.restamp.append(route)
    failed = _broken_names(errors)
    for manifest, key in by_manifest.items():
        if manifest in failed:
            continue  # a manifest that failed to load is not gone
        record = records[key]
        if prune:
            plan.orphan_remove.append(key)
        elif record.get("enabled", True) is not False or record[MARKER].get("reason") != ORPHAN_REASON:
            plan.orphan_disable.append(key)
    return plan


def apply_plan(plan: Plan, subscriptions: dict[str, dict[str, Any]], now: str) -> list[str]:
    done: list[str] = []
    for route in plan.create:
        subscriptions[route.name] = {**route.record(), MARKER: _marker(route, now)}
        done.append(f"created {route.name} ({route.profile}, {route.source})")
    for route, updates in plan.update:
        merged = {**subscriptions[route.name], **updates, MARKER: _marker(route, now)}
        subscriptions[route.name] = {k: v for k, v in merged.items() if v is not None}  # a cleared field goes, never null
        done.append(f"updated {route.name}: {', '.join(sorted(updates))}")
    for route in plan.restamp:
        subscriptions[route.name] = {**subscriptions[route.name], MARKER: _marker(route, now)}
        done.append(f"restamped {route.name} as {route.profile}/{route.source}")
    for key in plan.orphan_disable:
        record = subscriptions[key]
        subscriptions[key] = {**record, "enabled": False, MARKER: {**record[MARKER], "reason": ORPHAN_REASON}}
        done.append(f"disabled orphan {key}: manifest removed")
    for key in plan.orphan_remove:
        del subscriptions[key]
        done.append(f"removed orphan {key}")
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
    lines.extend(f"  would create {r.name} ({r.profile}, {r.source})" for r in plan.create)
    lines.extend(f"  would update {r.name}: {', '.join(sorted(u))}" for r, u in plan.update)
    lines.extend(f"  would restamp {r.name} as {r.profile}/{r.source}" for r in plan.restamp)
    lines.extend(f"  would disable orphan {k}" for k in plan.orphan_disable)
    lines.extend(f"  would remove orphan {k}" for k in plan.orphan_remove)
    lines.extend(f"  would write {w}" for w in plan.wrappers)
    if not plan.pending() and not plan.failed():
        lines.append("  in sync")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The runtime's subscriptions file (root home)
# ---------------------------------------------------------------------------

def _store():
    """The runtime's own reader and writer of ``webhook_subscriptions.json`` (its lock, its
    atomic rename, its 0600), imported late so manifest-only commands need no Hermes."""
    from hermes_cli import webhook
    return webhook


def load_records(root: Path) -> dict[str, dict[str, Any]]:
    store = _store()
    return lib.with_home(root, store._load_subscriptions)


def mutate_records(root: Path, fn) -> Any:
    store = _store()
    return lib.with_home(root, lambda: store._mutate_subscriptions(fn))


def _now() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def profile_dirs(root: Path) -> list[tuple[str, Path]]:
    """``(profile, home)`` for every profile under ``<root>/profiles`` with a ``webhook.d/``."""
    profiles = root / "profiles"
    if not profiles.is_dir():
        return []
    return sorted((p.name, p) for p in profiles.iterdir() if (p / MANIFEST_DIR).is_dir())


def load_all(root: Path, only: Optional[str] = None) -> tuple[list[Route], list[str], list[tuple[str, Path]]]:
    homes = [(n, h) for n, h in profile_dirs(root) if only is None or n == only]
    routes: list[Route] = []
    errors: list[str] = []
    for profile, home in homes:
        found, bad = load_routes(home, profile)
        routes.extend(found)
        errors.extend(bad)
    return routes, errors, homes


def _broken_names(errors: list[str]) -> set[str]:
    """The manifest names in a list of ``<profile>/<name>: …`` errors."""
    return {e.split(":", 1)[0].split("/", 1)[-1] for e in errors}


def sync_root(root: Path, *, check: bool, prune: bool) -> tuple[Plan, Optional[list[str]]]:
    """Reconcile every profile's ``webhook.d/`` into the root home's subscriptions. Under
    ``check`` nothing is written and the plan says what would be; otherwise the plan is built and
    applied under the writer's lock, on the records it just read, so a subscription made or
    removed meanwhile (``hermes webhook subscribe``, the dashboard) is neither clobbered nor
    indexed after it is gone."""
    root = root.expanduser().resolve()
    routes, errors, homes = load_all(root)
    broken = _broken_names(errors)
    wrappers: list[str] = []
    for profile, home in homes:
        wrappers.extend(sync_wrappers(home, [r for r in routes if r.profile == profile], broken, write=not check))
    if check:
        plan = build_plan(routes, errors, load_records(root), prune=prune)
        plan.wrappers = wrappers
        return plan, None
    now = _now()
    applied: dict[str, Any] = {}

    class _Unchanged(Exception):
        """Nothing to apply: leave the file as it is (a rewrite would make the listener re-read it)."""

    def run(subs: dict[str, dict[str, Any]]) -> list[str]:
        applied["plan"] = plan = build_plan(routes, errors, subs, prune=prune)
        if not (plan.create or plan.update or plan.restamp or plan.orphan_disable or plan.orphan_remove):
            raise _Unchanged
        return apply_plan(plan, subs, now)

    try:
        done = mutate_records(root, run)
    except _Unchanged:
        done = []
    plan = applied["plan"]
    plan.wrappers = wrappers
    return plan, done


def adopt(root: Path, profile: str, name: str) -> str:
    """Stamp the unmanaged route named ``name`` as the manifest's (then a sync brings its
    definition to the manifest). Refuses when the name is already managed."""
    root = root.expanduser().resolve()
    home = root / "profiles" / profile
    route = load_route(home / MANIFEST_DIR / name, profile, cron_manifest_names(home))

    def run(subs: dict[str, dict[str, Any]]) -> str:
        if any(lib.marker_of(r) and r[MARKER]["manifest"] == name for r in subs.values()):
            raise ManifestError(f"{name}: already managed")
        record = subs.get(name)
        if record is None:
            raise ManifestError(f"{name}: no unmanaged route of that name")
        subs[name] = {**record, "profile": profile, MARKER: _marker(route, _now())}
        return f"adopted {name} ({profile}, {route.source}); run a sync to apply the manifest"

    return mutate_records(root, run)


def write_local(home: Path, name: str, spec: dict[str, Any], filter_script: Optional[tuple[str, str]]) -> Path:
    """Create ``<home>/webhook.d/<name>/`` as a real directory; a manifest that fails validation
    leaves nothing behind. ``filter_script`` is ``(filename, text)``. Refuses an existing entry."""
    home = home.expanduser().resolve()
    directory = home / MANIFEST_DIR / name
    if directory.exists() or directory.is_symlink():
        raise ManifestError(f"{name}: already exists in {MANIFEST_DIR}/")
    lib.check_name(name)
    if not isinstance(spec, dict):
        raise ManifestError(f"{name}: spec must be a mapping")
    directory.mkdir(parents=True)
    try:
        (directory / MANIFEST_FILE).write_text(
            yaml.safe_dump(spec, sort_keys=False, allow_unicode=True), encoding="utf-8")
        if filter_script is not None:
            filename, text = filter_script
            if filename not in FILTER_SCRIPTS:
                raise ManifestError(f"{name}: a filter script is {' or '.join(FILTER_SCRIPTS)}")
            script = directory / filename
            script.write_text(text, encoding="utf-8")
            script.chmod(0o755)
        load_route(directory, home.name, cron_manifest_names(home))
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    return directory


def remove_local(home: Path, name: str) -> Path:
    """Delete a local manifest directory (never a link). The next sync disables or prunes its
    record."""
    home = home.expanduser().resolve()
    directory = home / MANIFEST_DIR / name
    if directory.is_symlink():
        raise ManifestError(f"{name}: a repository route; remove it there and re-run install.sh")
    if not directory.is_dir():
        raise ManifestError(f"{name}: no such local route")
    shutil.rmtree(directory)
    return directory


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--root", help="the root HERMES_HOME (default: $HERMES_DIR or ~/.hermes)")
    parser.add_argument("--check", action="store_true", help="sync: report what would change; write nothing")
    parser.add_argument("--prune", action="store_true", help="sync: remove orphan routes instead of disabling them")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("sync", help="derive the subscriptions from every profile's webhook.d/ (the default)")
    p_validate = sub.add_parser("validate", help="load every manifest and report errors; touches no record")
    p_validate.add_argument("--profile")
    p_adopt = sub.add_parser("adopt", help="stamp an unmanaged route of the manifest's name as its record")
    p_adopt.add_argument("profile")
    p_adopt.add_argument("name")
    p_add = sub.add_parser("add", help="write a local manifest directory from a JSON spec on stdin")
    p_add.add_argument("profile")
    p_add.add_argument("name")
    p_add.add_argument("--filter", help="file whose content becomes filter.sh or filter.py (by its suffix)")
    p_remove = sub.add_parser("remove", help="delete a local manifest directory")
    p_remove.add_argument("profile")
    p_remove.add_argument("name")
    args = parser.parse_args(argv)
    command = args.command or "sync"
    root = Path(args.root).expanduser() if args.root else lib.hermes_dir()

    try:
        if command == "sync":
            plan, done = sync_root(root, check=args.check, prune=args.prune)
            print(render(plan, done))
            return 1 if plan.failed() or (args.check and plan.pending()) else 0
        if command == "validate":
            routes, errors, homes = load_all(root.expanduser().resolve(), args.profile)
            if not homes:
                print(f"webhook-sync: no profile with a {MANIFEST_DIR}/ directory", file=sys.stderr)
                return 0
            for e in errors:
                print(f"ERROR manifest {e}")
            for r in routes:
                print(f"  ok {r.profile}/{r.name} ({r.mode}, {r.source})")
            return 1 if errors else 0
        home = root / "profiles" / args.profile
        if command == "adopt":
            print(adopt(root, args.profile, args.name))
        elif command == "add":
            spec = json.load(sys.stdin)
            script = None
            if args.filter:
                path = Path(args.filter)
                script = (f"filter{path.suffix}", path.read_text(encoding="utf-8"))
            print(f"  wrote {write_local(home, args.name, spec, script)}")
        elif command == "remove":
            print(f"  removed {remove_local(home, args.name)}")
    except ManifestError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
