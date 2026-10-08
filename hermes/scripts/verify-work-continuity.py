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
    "hermes/plugins/orchestration/specialist-call/tests/test_plugin.py",
    "hermes/plugins/orchestration/opencode-v2/tests/test_plugin.py",
    "hermes/scripts/tests/test_hands_routing_continuity.py",
    "hermes/scripts/tests/test_creator_references.py",
    "hermes/scripts/tests/test_hands_instruction_context.py",
    "hermes/scripts/tests/test_creator_entry_contract.py",
    "hermes/scripts/tests/test_creator_entry_runtime.py",
    "hermes/scripts/tests/test_assistant_entry_runtime.py",
    "hermes/scripts/tests/test_ad_routing.py",
    "hermes/scripts/tests/test_creative_client_references.py",
    "hermes/scripts/tests/test_visual_design_contract.py",
    "hermes/scripts/tests/test_three_graphics.py",
    "hermes/scripts/tests/test_three_graphics_native.py",
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
    "hermes/scripts/tests/test_searcher_reliability.py",
    "hermes/scripts/tests/test_validate_profile_skills.py",
    "hermes/scripts/tests/test_work_continuity.py",
    "hermes/scripts/tests/test_researcher_entries.py",
    "hermes/scripts/tests/test_audio_creator_routing.py",
    "hermes/plugins/image_gen/image-fallback/tests/test_plugin.py",
)

# Local patches carried on the runtime's `local` branch, plus the upstream contracts they lean on.
RUNTIME_PYTEST_FILES = (
    "tests/gateway/test_completion_delivery.py",
    "tests/gateway/test_multiplex_profile_authz.py",
    "tests/gateway/test_multiplex_toolsets_profile_isolation.py",
    "tests/tools/test_browser_real_profile_binary.py",
    "tests/tools/test_browser_real_profile_session_scope.py",
    "tests/tools/test_browser_real_profile_cookie_merge.py",
    "tests/tools/test_browser_real_profile_user_agent.py",
    "tests/tools/test_browser_real_profile_session_restore.py",
    "tests/tools/test_browser_real_profile_stall.py",
    "tests/tools/test_browser_use_target_scope.py",
    "tests/agent/test_anthropic_thinking_disable.py",
    "tests/agent/test_anthropic_oauth_invoke_recovery.py",
    "tests/agent/test_anthropic_oauth_billing_header.py",
    "tests/gateway/test_dm_topics.py",
    "tests/gateway/test_auto_voice_reply_format.py",
    "tests/pm/test_runtime_journal_safety.py",
)

ASSISTANT_PIPELINE = "hermes/profiles/assistant/skills/assistant-pipeline"
ASSISTANT_TESTS = f"{ASSISTANT_PIPELINE}/tests"


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
    """Returns the runtime's PM test interpreter (pytest + its dependency set); fails
    descriptively if absent. PM owns the interpreter, so it is asked, never guessed."""
    resolver = PUBLIC_ROOT / "bin" / "hermes-python"
    env = {**os.environ, "HERMES_AGENT_DIR": str(runtime)}
    result = subprocess.run(
        [str(resolver), "--test", "-c", "import sys; print(sys.executable)"],
        env=env, capture_output=True, text=True, timeout=STAGE_TIMEOUT,
    )
    require(result.returncode == 0, f"--runtime has no test interpreter ({resolver} --test): {result.stderr.strip()}")
    python = Path(result.stdout.strip().splitlines()[-1])
    require(python.is_file(), f"--runtime python not found: {python}")
    return python


def check_candidate_pairing(private: Path) -> None:
    """The assistant-pipeline must be this checkout's own tracked directory,
    never a leftover link into an overlay, AND the real
    Path.home()/.config/private must resolve to the passed --private root,
    which still owns the Assistant's config and private technics -- never
    soften the validator's own checks, just refuse an unpaired candidate."""
    private = private.resolve()
    pipeline = HERMES_ROOT / "profiles/assistant/skills/assistant-pipeline"
    require(not pipeline.is_symlink(), f"{pipeline} must be a tracked directory, not a link")
    require(pipeline.is_dir(), f"missing assistant pipeline directory: {pipeline}")
    require(private.is_dir(), f"missing --private checkout: {private}")
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
            name="assistant unittest",
            argv=[str(python), "-m", "unittest", "discover", "-s", str(PUBLIC_ROOT / ASSISTANT_TESTS)],
            cwd=PUBLIC_ROOT, env=env,
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
    require(any((PUBLIC_ROOT / ASSISTANT_TESTS).glob("test_*.py")), "Assistant pipeline tests are missing")
    plan = build_plan(args.runtime, args.private, python)
    run_plan(plan)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
