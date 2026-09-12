"""Tests for verify-work-continuity.py's pure planning/checking functions.
Never invokes the module's own CLI (main/run_plan) for real; subprocess.run
is always monkeypatched here, and no full pipeline run happens in this file.

Five behavioral cases below cannot be proven by any unit assertion and
explicitly require live agent/evidence acceptance at cutover instead:

- centered-design: a claimed "centered" authored layout must be checked
  against the actual rendered PNG, not inferred from its source CSS.
- original-goal-vs-metaphor: a follow-up specialist turn must be checked
  to still serve the FIRST request's literal goal, not a plausible-sounding
  reinterpretation of it.
- agent-choice-vs-human: a "DECISION:"-style label in a relayed handoff
  must be checked to trace to an actual human approval, not an agent's own
  unapproved choice wearing the same label.
- stopped-process-vs-effects: a reconciled "interrupted" conversation's
  actual side effects (files written, calls made) must be checked before
  treating "the process stopped" as "nothing happened".
- latest-saved-version: a resumed/continued turn must be checked against
  the artifact actually persisted on disk, never assumed to be whichever
  version was most recently discussed.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "verify-work-continuity.py"
SPEC = importlib.util.spec_from_file_location("verify_work_continuity", SCRIPT)
assert SPEC and SPEC.loader
V = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V)

REAL_PUBLIC_ROOT = SCRIPT.resolve().parents[2]


class CommandPlanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = Path("/fake/runtime")
        self.private = Path("/fake/private")
        self.python = self.runtime / "venv/bin/python"

    def test_exact_scopes_no_dot_no_forbidden(self) -> None:
        plan = V.build_plan(self.runtime, self.private, self.python)
        self.assertEqual(4, len(plan))
        names = [stage["name"] for stage in plan]
        self.assertEqual(
            ["validate-profile-skills --all --strict-git", "public pytest",
             "private assistant unittest", "runtime pytest"],
            names,
        )
        public_stage = plan[1]
        runtime_stage = plan[3]
        self.assertEqual(list(V.PUBLIC_PYTEST_FILES), [
            a for a in public_stage["argv"] if a.startswith("hermes/")
        ])
        self.assertEqual(list(V.RUNTIME_PYTEST_FILES), [
            a for a in runtime_stage["argv"] if a.startswith("tests/")
        ])
        for stage in plan:
            self.assertNotIn(".", stage["argv"])
        private_stage = plan[2]["argv"]
        self.assertEqual(str(self.private / V.PRIVATE_TESTS), private_stage[-1])
        self.assertNotIn("test_assistant*.py", private_stage)

    def test_checkout_names_are_not_a_command_policy(self) -> None:
        plan = V.build_plan(Path("/tmp/download-cache/runtime"), Path("/tmp/restart-review/private"), self.python)
        self.assertEqual(4, len(plan))

    def test_env_prefix_and_smoke_vars_stripped(self) -> None:
        with patch.dict("os.environ", {"CARD_SMOKE_DIR": "/x", "CARD_AUTHORED_SMOKE_DIR": "/y"}):
            env = V.build_env(self.runtime, self.python)
        self.assertNotIn("CARD_SMOKE_DIR", env)
        self.assertNotIn("CARD_AUTHORED_SMOKE_DIR", env)
        self.assertEqual(str(self.runtime), env["PYTHONPATH"])
        self.assertEqual("1", env["PYTHONDONTWRITEBYTECODE"])
        self.assertEqual(str(self.python), env["UV_PYTHON"])
        self.assertEqual("1", env["UV_OFFLINE"])
        self.assertEqual(str(V.PUBLIC_ROOT), env["HERMES_PUBLIC_ROOT"])


class PreflightFailureTest(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.private = root / "private"
        hermes = root / "public/hermes"
        for name in ("assistant-pipeline", "desks"):
            rel = Path("profiles/assistant/skills") / name
            target = self.private / "hermes" / rel
            target.mkdir(parents=True)
            link = hermes / rel
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(target)
        self.home = root / "home"
        (self.home / ".config").mkdir(parents=True)
        (self.home / ".config/private").symlink_to(self.private)
        for patcher in (patch.object(V, "HERMES_ROOT", hermes),
                        patch.object(Path, "home", return_value=self.home)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_runtime_absent_fails_descriptively(self) -> None:
        with self.assertRaisesRegex(V.ContinuityError, "python not found"):
            V.check_runtime(Path("/definitely/not/a/real/runtime"))

    def test_candidate_pair_mismatch_fails_descriptively(self) -> None:
        # Correct overlay links, but the home boundary selects a different pair.
        with patch.object(Path, "home", return_value=Path("/fake/home/for/mismatch")):
            with self.assertRaisesRegex(V.ContinuityError, "unpaired candidate"):
                V.check_candidate_pairing(self.private)

    def test_candidate_pair_matches_in_isolation(self) -> None:
        V.check_candidate_pairing(self.private)

    def test_missing_overlay_link_is_still_rejected(self) -> None:
        (V.HERMES_ROOT / "profiles/assistant/skills/desks").unlink()
        with self.assertRaisesRegex(V.ContinuityError, "must be a real symlink"):
            V.check_candidate_pairing(self.private)

    def test_candidate_pair_wrong_private_root_fails_descriptively(self) -> None:
        with self.assertRaisesRegex(V.ContinuityError, "not under --private"):
            V.check_candidate_pairing(Path("/some/other/private/root"))

    def test_missing_declared_public_file_fails(self) -> None:
        with self.assertRaisesRegex(V.ContinuityError, "declared test file missing"):
            V.check_files_exist(REAL_PUBLIC_ROOT, ("hermes/scripts/tests/test_does_not_exist_at_all.py",))


class MockedRunPropagationTest(unittest.TestCase):
    def test_first_stage_failure_stops_remaining_stages(self) -> None:
        plan = V.build_plan(Path("/fake/runtime"), Path("/fake/private"), Path("/fake/runtime/venv/bin/python"))
        calls = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            raise __import__("subprocess").CalledProcessError(1, argv)

        with patch.object(V.subprocess, "run", side_effect=fake_run):
            with self.assertRaises(V.subprocess.CalledProcessError):
                V.run_plan(plan)
        self.assertEqual(1, len(calls))  # never reached stage 2, 3 or 4


class DeclaredFilesReallyExistTest(unittest.TestCase):
    """Guards against a fabricated file name in either list: real existence,
    not a git-subject/commit-message presence check."""

    def test_public_pytest_files_exist_on_disk(self) -> None:
        for rel in V.PUBLIC_PYTEST_FILES:
            self.assertTrue((REAL_PUBLIC_ROOT / rel).is_file(), rel)

    def test_runtime_pytest_files_exist_on_disk(self) -> None:
        import hermes_constants
        runtime = Path(hermes_constants.__file__).resolve().parent
        for rel in V.RUNTIME_PYTEST_FILES:
            self.assertTrue((runtime / rel).is_file(), rel)


class PerProfileHandoffContractTest(unittest.TestCase):
    """Static text check only: every root's operating contract must
    distinguish a runtime specialist handoff (agent-authored) from direct
    human approval, and must not otherwise claim extra production rights
    from that attribution. This does NOT prove an LLM actually honours it
    at runtime -- see the module docstring for the live-acceptance cases
    that check does need. assistant/default are delegated to the private
    overlay's own tests (not duplicated here); their entry only confirms
    the delegation, not the private text itself."""

    PUBLIC_ROOTS = (
        "creator", "engineer", "marketer", "writer", "researcher", "searcher",
        "image-creator", "video-creator", "audio-creator", "ui-review", "ux-persona",
    )

    def test_public_roots_mention_agent_vs_human_handoff_distinction(self) -> None:
        for profile in self.PUBLIC_ROOTS:
            with self.subTest(profile=profile):
                path = REAL_PUBLIC_ROOT / f"hermes/profiles/{profile}/skills/{profile}-pipeline/SKILL.md"
                self.assertTrue(path.is_file(), path)
                text = " ".join(path.read_text(encoding="utf-8").split())
                self.assertRegex(
                    text,
                    r"specialist (handoff|header).{0,300}?\bagent\b.{0,300}?\b(?:not|never)\b.{0,60}?\bhuman\b",
                    f"{profile}: no agent-vs-human handoff distinction found",
                )

if __name__ == "__main__":
    unittest.main()
