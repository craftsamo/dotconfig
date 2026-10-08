"""Mechanical readiness checks before a run: one read-only call instead of several.

It reports what a run would otherwise discover by failing: an unreachable or
unmeasured service, a role whose agent or model cannot run, a worktree another
session is using. A healthy answer is one line; otherwise only the findings.
Nothing is recorded and nothing is written.
"""

from __future__ import annotations

import contextlib
import subprocess

MEASURED_VERSION = "2.0.23"
PHASES = ("plan", "build")


def _issue(level, what):
    return {"level": level, "what": what}


def _roles(settings, caller, directory, lookup_agent, models, api, config):
    issues = []
    where = api.location(directory)
    for name, role in sorted(settings["roles"].items()):
        info = {}
        try:
            info = lookup_agent(role["agent"], where)
            if info.get("mode") not in ("primary", "all"):
                raise ValueError(f"OpenCode agent {role['agent']} is not a primary agent")
            models.engine(role, {}, info, directory, caller)
        except Exception as exc:
            refused = "your own model" in str(exc)
            alternate = role.get("alternate")
            hint = f" (alternate: {alternate})" if refused and alternate else ""
            issues.append(_issue("warn" if refused else "error", f"role {name}: {exc}{hint}"))
        if role.get("alternate"):
            try:
                models.engine({**role, "model": role["alternate"]}, {}, info, directory, caller)
            except Exception as exc:
                issues.append(_issue("warn", f"role {name} alternate: {exc}"))
    return issues


def _worktree(directory, phase, policy, turn):
    issues = []
    writing = phase == "build"
    try:
        branch, _ = policy.branch(directory, writing)
    except ValueError as exc:
        return [_issue("error", str(exc))], None
    if writing:
        try:
            running = turn.running_in(directory, policy.same_dir)
            if running:
                issues.append(_issue("error", f"a session is already running in this worktree: {', '.join(running)}"))
        except Exception as exc:
            issues.append(_issue("warn", f"could not check for running sessions: {exc}"))
        with contextlib.suppress(Exception):
            # No fsmonitor hook: a status read must not run repository-configured code.
            status = subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", directory, "status", "--porcelain"],
                                    capture_output=True, text=True, timeout=15)
            changed = len([line for line in status.stdout.splitlines() if line.strip()])
            if changed:
                issues.append(_issue("warn", f"{changed} uncommitted path(s) already in the worktree"))
    return issues, branch


def check(*, settings, caller, args, lookup_agent, api, config, models, policy, turn):
    """The findings for `args` (directory, phase, output_dir)."""
    unknown = set(args) - {"directory", "phase", "output_dir"}
    if unknown:
        raise ValueError("Unexpected arguments: " + ", ".join(sorted(unknown)))
    phase = args.get("phase", "plan")
    if phase not in PHASES:
        raise ValueError("phase must be plan or build")
    directory = policy.worktree(args.get("directory"))
    issues = []
    try:
        info = turn.call("get", "/api/info")
        version = info.get("version") if isinstance(info, dict) else None
    except (api.ApiError, api.Unavailable) as exc:
        return {"ok": False, "issues": [_issue("error", f"OpenCode service unreachable: {exc}")]}
    if version != MEASURED_VERSION:
        issues.append(_issue("warn", f"OpenCode {version}; this plugin was measured on {MEASURED_VERSION}"))
    issues += _roles(settings, caller, directory, lookup_agent, models, api, config)
    found, branch = _worktree(directory, phase, policy, turn)
    issues += found
    if args.get("output_dir") is not None:
        try:
            policy.output_dir(args["output_dir"])
        except ValueError as exc:
            issues.append(_issue("error", str(exc)))
    ok = not any(item["level"] == "error" for item in issues)
    if issues:
        return {"ok": ok, "issues": issues}
    return {"ok": True, "summary": f"ready: OpenCode {version}, roles {', '.join(sorted(settings['roles']))}, "
                                   f"branch {branch}, {phase}"}
