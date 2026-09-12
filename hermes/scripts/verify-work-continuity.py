#!/usr/bin/env python3
"""Continuity verification across the public/private/runtime hermes-agent
triad: checks candidate pairing, then runs the original validator, then
scoped public/private/runtime test suites in order, failing fast on the
first problem. Every stage is a read-only check or an existing
validator/test invocation; this script never installs, links, restarts,
cleans up, or downloads anything.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

PUBLIC_ROOT = Path(__file__).resolve().parents[2]
HERMES_ROOT = PUBLIC_ROOT / "hermes"
STAGE_TIMEOUT = 600

PUBLIC_PYTEST_FILES = (
    "hermes/scripts/tests/test_card.py",
    "hermes/scripts/tests/test_card_authored.py",
    "hermes/plugins/specialist-call/tests/test_plugin.py",
    "hermes/plugins/opencode/tests/test_plugin.py",
    "hermes/scripts/tests/test_hands_routing_continuity.py",
    "hermes/scripts/tests/test_creator_references.py",
    "hermes/scripts/tests/test_hands_instruction_context.py",
    "hermes/scripts/tests/test_creator_entry_contract.py",
    "hermes/scripts/tests/test_creator_entry_runtime.py",
    "hermes/scripts/tests/test_assistant_entry_runtime.py",
    "hermes/scripts/tests/test_ad_routing.py",
    "hermes/scripts/tests/test_creative_client_references.py",
    "hermes/scripts/tests/test_engineer_pipeline.py",
    "hermes/scripts/tests/test_engineer_entry_runtime.py",
    "hermes/scripts/tests/test_marketer_pipeline.py",
    "hermes/scripts/tests/test_marketer_entry_runtime.py",
    "hermes/scripts/tests/test_marketer_browser_lease.py",
    "hermes/scripts/tests/test_writer_leaves.py",
    "hermes/scripts/tests/test_writer_cleanup.py",
    "hermes/scripts/tests/test_writer_entry_runtime.py",
    "hermes/scripts/tests/test_writer_post.py",
    "hermes/scripts/tests/test_writer_article.py",
    "hermes/scripts/tests/test_writer_document.py",
    "hermes/scripts/tests/test_writer_message.py",
    "hermes/scripts/tests/test_writer_copy.py",
    "hermes/scripts/tests/test_writer_script.py",
    "hermes/scripts/tests/test_searcher_pipeline.py",
    "hermes/scripts/tests/test_searcher_entry_runtime.py",
    "hermes/scripts/tests/test_validate_profile_skills.py",
    "hermes/scripts/tests/test_work_continuity.py",
    "hermes/scripts/tests/test_researcher_entries.py",
    "hermes/scripts/tests/test_audio_creator_routing.py",
    "hermes/plugins/image_gen/image-fallback/tests/test_plugin.py",
)

RUNTIME_PYTEST_FILES = (
    "tests/gateway/test_watch_notification_multiplex_route.py",
    "tests/gateway/test_multiplex_profile_authz.py",
    "tests/gateway/test_multiplex_toolsets_profile_isolation.py",
    "tests/tools/test_browser_real_profile_binary.py",
    "tests/tools/test_browser_real_profile_session_scope.py",
    "tests/tools/test_browser_real_profile_cookie_merge.py",
    "tests/tools/test_browser_real_profile_user_agent.py",
    "tests/tools/test_browser_real_profile_session_restore.py",
)

PRIVATE_TESTS = "hermes/profiles/assistant/skills/assistant-pipeline/tests"


class ContinuityError(RuntimeError):
    """A descriptive, non-recoverable pre-flight failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContinuityError(message)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", required=True, type=Path, help="existing trusted hermes-agent checkout")
    parser.add_argument("--private", required=True, type=Path, help="paired private overlay root")
    return parser.parse_args(argv)


def check_runtime(runtime: Path) -> Path:
    """Returns the provisioned interpreter; fails descriptively if absent."""
    python = runtime / "venv" / "bin" / "python"
    require(python.is_file(), f"--runtime python not found: {python}")
    return python


def check_candidate_pairing(private: Path) -> None:
    """Public assistant-pipeline/desks must be real symlinks resolving under
    the passed --private root, AND the real Path.home()/.config/private must
    resolve to that SAME root -- never soften the original validator's own
    symlink checks, just refuse an unpaired candidate here."""
    private = private.resolve()
    for name in ("assistant-pipeline", "desks"):
        link = HERMES_ROOT / "profiles/assistant/skills" / name
        require(link.is_symlink(), f"{link} must be a real symlink into the private overlay")
        target = link.resolve()
        require(target.is_dir(), f"missing private pipeline directory: {target}")
        require(target.is_relative_to(private), f"{link} resolves to {target}, not under --private {private}")
    home_private = (Path.home() / ".config" / "private").resolve()
    require(
        home_private == private,
        f"Path.home()/.config/private resolves to {home_private}, not the passed --private "
        f"{private}; unpaired candidate",
    )


def check_files_exist(root: Path, relative_paths: tuple[str, ...]) -> None:
    for rel in relative_paths:
        require((root / rel).is_file(), f"declared test file missing under {root}: {rel}")


def build_env(runtime: Path, python: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("CARD_SMOKE_DIR", "CARD_AUTHORED_SMOKE_DIR")}
    env.update(
        PYTHONPATH=str(runtime),
        PYTHONDONTWRITEBYTECODE="1",
        UV_PYTHON=str(python),
        UV_OFFLINE="1",
        HERMES_PUBLIC_ROOT=str(PUBLIC_ROOT),
    )
    return env


def build_plan(runtime: Path, private: Path, python: Path) -> list[dict]:
    """Pure: the ordered stage list, no side effects. Each stage is
    {name, argv, cwd, env}. Testable directly; never invoked at import."""
    env = build_env(runtime, python)
    env["HERMES_PRIVATE_ROOT"] = str(private)
    return [
        dict(
            name="validate-profile-skills --all --strict-git",
            argv=[str(python), str(HERMES_ROOT / "scripts/validate-profile-skills.py"), "--all", "--strict-git"],
            cwd=HERMES_ROOT, env=env,
        ),
        dict(
            name="public pytest",
            argv=[str(python), "-m", "pytest", *PUBLIC_PYTEST_FILES, "-q", "--import-mode=importlib", "-p", "no:cacheprovider"],
            cwd=PUBLIC_ROOT, env=env,
        ),
        dict(
            name="private assistant unittest",
            argv=[str(python), "-m", "unittest", "discover", "-s", str(private / PRIVATE_TESTS)],
            cwd=private, env=env,
        ),
        dict(
            name="runtime pytest",
            argv=[str(python), "-m", "pytest", *RUNTIME_PYTEST_FILES, "-q", "--import-mode=importlib", "-p", "no:cacheprovider"],
            cwd=runtime, env=env,
        ),
    ]


def run_plan(plan: list[dict]) -> None:
    for stage in plan:
        print(f"== {stage['name']} ==", flush=True)
        subprocess.run(stage["argv"], cwd=stage["cwd"], env=stage["env"], check=True, timeout=STAGE_TIMEOUT)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.runtime, args.private = args.runtime.resolve(), args.private.resolve()
    python = check_runtime(args.runtime)
    check_files_exist(PUBLIC_ROOT, PUBLIC_PYTEST_FILES)
    check_files_exist(args.runtime, RUNTIME_PYTEST_FILES)
    check_candidate_pairing(args.private)
    require(any((args.private / PRIVATE_TESTS).glob("test_*.py")), "paired Assistant tests are missing")
    plan = build_plan(args.runtime, args.private, python)
    run_plan(plan)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
