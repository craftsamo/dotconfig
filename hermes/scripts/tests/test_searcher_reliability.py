"""Contracts for the Searcher reliability failures found in real transcripts.

Each ``xfail(strict=True)`` marks a known gap that a later phase fixes: the case
fails today, and the moment the fix lands it reports XPASS, which fails the suite
until the marker is removed. Fixtures are neutral; no real brief is used.

Structural contracts only: they pin what the instructions and handoff say, not
how a model behaves. Behavior is measured with ``audit-searcher-sessions.py``.
"""

from __future__ import annotations

import importlib.util
import re
import time
from pathlib import Path

import pytest


HERMES = Path(__file__).resolve().parents[2]
PIPELINE = HERMES / "profiles/searcher/skills/searcher-pipeline"
PLUGIN = HERMES / "plugins/orchestration/specialist-call/__init__.py"

spec = importlib.util.spec_from_file_location("specialist_call_reliability", PLUGIN)
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)

HANDOFF_BASE = {"conversation_id": "a" * 32, "job_id": "b" * 32, "initial_job_id": "b" * 32,
                "initial_request": "survey", "requester_profile": "assistant"}


def flat(path: Path) -> str:
    return " ".join(path.read_text().split())


def handoff(target: str, minutes: int = 90) -> str:
    data = {**HANDOFF_BASE, "target": target, "deadline": time.time() + minutes * 60}
    return plugin._handoff(data, "survey")


def test_engineer_handoff_keeps_the_committed_checkpoint_rule():
    text = handoff("engineer")
    assert "committed checkpoint" in text and "Turn budget" in text


def test_searcher_handoff_does_not_ask_for_a_git_commit():
    text = handoff("searcher")
    assert "Turn budget" in text
    assert "committed checkpoint" not in text and "task branch" not in text


def test_searcher_handoff_still_states_the_remaining_minutes():
    assert re.search(r"~(89|90) min from now", handoff("searcher"))


def searcher_prompt() -> str:
    import hermes_yaml as yaml
    config = yaml.safe_load((HERMES / "profiles/searcher/config.yaml").read_text())
    return " ".join(config["agent"]["system_prompt"].split())


def test_kernel_and_prompt_say_reading_is_allowed_while_writing_is_not():
    kernel = flat(PIPELINE / "SKILL.md")
    assert "x_search is allowed" in kernel and "never a reason to skip a platform" in kernel
    assert "No write-actions on social platforms" in kernel
    prompt = searcher_prompt()
    assert "Reading is allowed" in prompt and "never a reason to skip it" in prompt
    assert "Never write to a social platform" in prompt
    assert "Social platforms are read-only" not in prompt


@pytest.mark.xfail(strict=True, reason="Build has no stop-reason rule: a run stopped after about 30 seconds "
                                       "against a 89 minute budget, with nothing saved")
def test_build_distinguishes_budget_exhaustion_from_an_early_stop():
    text = flat(PIPELINE / "build-searcher/SKILL.md")
    assert "Turn budget" in text and "durable path" in text
