from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .assistant_entry_fixtures import CARDS, build_assistant_tree, entry_text


SCRIPT = Path(__file__).resolve().parents[1] / "validate-profile-skills.py"
SPEC = importlib.util.spec_from_file_location("validate_profile_skills", SCRIPT)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class AssistantPipelineTreeTest(unittest.TestCase):
    def test_repository_tree_is_valid(self) -> None:
        if not VALIDATOR.ASSISTANT_PIPELINE.is_dir():
            self.skipTest("deployment-only: repository private overlay is absent")
        errors: list[str] = []
        refs, catalog = VALIDATOR.validate_assistant_pipeline(errors)
        self.assertEqual([], errors)
        self.assertGreater(refs, 0)
        self.assertGreater(len(catalog), 0)
        for name, assignee in catalog.items():
            self.assertIn(assignee, VALIDATOR.WORKER_PROFILES, name)


class SandboxTreeTest(unittest.TestCase):
    """Structural rules verified against a synthetic tree."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._original = VALIDATOR.ASSISTANT_PIPELINE
        VALIDATOR.ASSISTANT_PIPELINE = self.root

    def tearDown(self) -> None:
        VALIDATOR.ASSISTANT_PIPELINE = self._original
        self._tmp.cleanup()

    def write(self, rel: str, text: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def build_minimal_tree(self) -> None:
        build_assistant_tree(self.write, VALIDATOR)

    def validate(self) -> list[str]:
        errors: list[str] = []
        VALIDATOR.validate_assistant_pipeline(errors)
        return errors

    def test_minimal_tree_passes(self) -> None:
        self.build_minimal_tree()
        self.assertEqual([], self.validate())

    def test_ignores_incidental_dotfiles_without_hiding_skills(self) -> None:
        self.build_minimal_tree()
        for path in (
            ".DS_Store", "references/.DS_Store", "references/plan/.DS_Store",
            "references/.editor/state", "plan-assistant-creative/.SKILL.md.swp",
            "plan-assistant-creative/references/.DS_Store",
            "plan-assistant-creative/references/legacy/.DS_Store",
        ):
            self.write(path, "editor metadata\n")
        self.assertEqual([], self.validate())
        self.write(".editor/SKILL.md", "---\nname: hidden-skill\n---\n")
        self.assertTrue(any("unexpected skill root" in e for e in self.validate()))

    def test_rejects_symlinked_entry_before_reading_its_target(self) -> None:
        self.build_minimal_tree()
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        target = Path(outside.name) / "entry"
        entry = self.root / "qa-assistant-search"
        entry.rename(target)
        entry.symlink_to(target)
        self.assertEqual(
            ["assistant pipeline must not contain symlinks: qa-assistant-search"],
            self.validate(),
        )

    def test_rejects_symlinks_in_references_and_hidden_directories(self) -> None:
        self.build_minimal_tree()
        for rel in (".editor", "plan-assistant-writing/references/linked.md"):
            with self.subTest(path=rel):
                path = self.root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.symlink_to(self.root / "SKILL.md")
                self.assertTrue(any("must not contain symlinks" in e for e in self.validate()))
                path.unlink()

    def test_rejects_unknown_mode_dir(self) -> None:
        self.build_minimal_tree()
        self.write("references/deploy/index.md", "# nope\n")
        errors = self.validate()
        self.assertTrue(any("unexpected shared reference" in e for e in errors), errors)

    def test_rejects_capability_dir_in_chat(self) -> None:
        self.build_minimal_tree()
        self.write("chat-assistant/references/creative/index.md", "# nope\n")
        errors = self.validate()
        self.assertTrue(any("no nesting below entry references" in e for e in errors), errors)

    def test_rejects_unrouted_leaf(self) -> None:
        self.build_minimal_tree()
        self.write("execute-assistant-creative/references/pixel-art.md", "# pixel\n")
        errors = self.validate()
        self.assertTrue(any("does not route references/pixel-art.md" in e for e in errors), errors)

    def test_accepts_valid_card_units(self) -> None:
        self.build_minimal_tree()
        self.assertEqual([], self.validate())
        errors: list[str] = []
        _, catalog = VALIDATOR.validate_assistant_pipeline(errors)
        self.assertEqual({unit: who for cards in CARDS.values() for unit, who in cards.items()}, catalog)
        self.assertEqual(catalog, VALIDATOR.collect_card_catalog())

    def test_rejects_card_unit_with_unknown_assignee(self) -> None:
        self.build_minimal_tree()
        self.write(
            "execute-assistant-creative/SKILL.md",
            "---\n"
            "card_units:\n"
            "  - name: anchored-image-batch\n"
            "    assignee: assistant\n"
            "    required_inputs: [approved-style-anchor]\n"
            "    unit_cap: \"one batch\"\n"
            "    runtime_cap: 1800\n"
            "---\n# creative\n",
        )
        errors = self.validate()
        self.assertTrue(
            any("assignee must be a worker profile" in e for e in errors), errors
        )

    def test_rejects_card_unit_without_runtime_cap(self) -> None:
        self.build_minimal_tree()
        self.write(
            "execute-assistant-creative/SKILL.md",
            "---\n"
            "card_units:\n"
            "  - name: anchored-image-batch\n"
            "    required_inputs: [anchor]\n"
            "    unit_cap: \"one batch\"\n"
            "---\n# creative\n",
        )
        errors = self.validate()
        self.assertTrue(any("runtime_cap" in e for e in errors), errors)

    def test_rejects_duplicate_card_unit_names(self) -> None:
        self.build_minimal_tree()
        unit = (
            "card_units:\n"
            "  - name: same-unit\n"
            "    required_inputs: [spec]\n"
            "    unit_cap: \"one\"\n"
            "    runtime_cap: 900\n"
        )
        self.write(
            "execute-assistant-creative/SKILL.md", f"---\n{unit}---\n# a\n"
        )
        self.write(
            "execute-assistant-search/SKILL.md", f"---\n{unit}---\n# b\n"
        )
        errors = self.validate()
        self.assertTrue(any("duplicate card unit" in e for e in errors), errors)

    def test_rejects_card_units_outside_execute(self) -> None:
        self.build_minimal_tree()
        self.write(
            "plan-assistant-creative/SKILL.md",
            "---\n"
            "card_units:\n"
            "  - name: sneaky-unit\n"
            "    required_inputs: [spec]\n"
            "    unit_cap: \"one\"\n"
            "    runtime_cap: 900\n"
            "---\n# plan\n",
        )
        errors = self.validate()
        self.assertTrue(any("only legal on creative/search Execute SKILL.md" in e for e in errors), errors)

    def test_rejects_missing_qa_contract(self) -> None:
        self.build_minimal_tree()
        (self.root / "qa-assistant-writing/references/prose.md").unlink()
        errors = self.validate()
        self.assertTrue(
            any("qa-assistant-writing/references/prose.md" in e for e in errors), errors
        )


    def test_exhaustive_entry_allowlist(self) -> None:
        self.build_minimal_tree()
        self.assertEqual(19, len(VALIDATOR.ASSISTANT_ENTRIES))
        for name in VALIDATOR.ASSISTANT_ENTRIES:
            with self.subTest(name=name):
                skill = self.root / name / "SKILL.md"
                text = skill.read_text()
                skill.unlink()
                self.assertTrue(any(f"missing assistant entry skill: {name}/" in e for e in self.validate()))
                skill.write_text(text)

    def test_rejects_extra_skill_roots_even_in_fixtures(self) -> None:
        self.build_minimal_tree()
        for rel in (
            "plan-assistant-unknown/SKILL.md",
            "tests/fixtures/SKILL.md",
            "references/plan/SKILL.md",
            "plan-assistant-writing/references/fixtures/SKILL.md",
            "execute-assistant-creative/references/legacy/tests/SKILL.md",
        ):
            with self.subTest(rel=rel):
                self.write(rel, "---\nname: unexpected\n---\n")
                self.assertTrue(any("unexpected skill root" in e and rel in e for e in self.validate()))

    def test_root_tests_allow_python_and_cache_but_not_skills(self) -> None:
        self.build_minimal_tree()
        self.write("tests/test_pipeline.py", "def test_pipeline():\n    assert True\n")
        self.write("tests/__pycache__/test_pipeline.cpython-311.pyc", "cache fixture")
        self.assertEqual([], self.validate())
        self.write("tests/fixtures/SKILL.md", "---\nname: unexpected\n---\n")
        errors = self.validate()
        self.assertTrue(any("unexpected skill root" in e and "tests/fixtures/SKILL.md" in e for e in errors))

    def test_rejects_old_layout(self) -> None:
        self.build_minimal_tree()
        for rel in ("references/chat/index.md", "references/plan/engineering/index.md",
                    "plan-assistant-writing/references/index.md"):
            self.write(rel, "# Old index\n")
        errors = self.validate()
        self.assertTrue(any("unexpected shared reference: references/chat" in e for e in errors))
        self.assertTrue(any("unexpected shared reference: references/plan/engineering" in e for e in errors))
        self.assertTrue(any("entry index must be promoted" in e for e in errors))

    def test_entry_metadata_is_required(self) -> None:
        self.build_minimal_tree()
        original = entry_text("plan-assistant-engineering")
        for old, new, diagnostic in (
            ("name: plan-assistant-engineering", "name: wrong", "frontmatter name"),
            ("version: 1.0.0", "version: ''", "version must be a nonempty string"),
            ("category: assistant-pipeline", "category: orchestration", "category must be assistant-pipeline"),
            ("Plan engineering entry.", "General engineering plan.", "description must frontload"),
        ):
            with self.subTest(diagnostic=diagnostic):
                self.assertIn(old, original)
                self.write("plan-assistant-engineering/SKILL.md", original.replace(old, new))
                self.assertTrue(any(diagnostic in e for e in self.validate()))

    def test_entry_version_is_not_pinned_to_initial_release(self) -> None:
        self.build_minimal_tree()
        original = entry_text("plan-assistant-engineering")
        for version in ("1.0.1", "2.0.0", "3.0.0-beta.1"):
            with self.subTest(version=version):
                self.write("plan-assistant-engineering/SKILL.md", original.replace("version: 1.0.0", f"version: {version}"))
                self.assertEqual([], self.validate())

    def test_read_before_work_dependencies_cannot_be_removed(self) -> None:
        self.build_minimal_tree()
        original = entry_text("plan-assistant-engineering")
        for token in (
            'skill_view(name="assistant-pipeline")',
            'skill_view(name="assistant-pipeline", file_path="references/plan/index.md")',
            "<ReadBeforeWork>", "full body", "Reuse", "not a past summary", "unchanged",
            "read_file", "stop", "${HERMES_SKILL_DIR}/../SKILL.md",
            "${HERMES_SKILL_DIR}/../references/plan/index.md",
        ):
            with self.subTest(token=token):
                self.assertIn(token, original)
                self.write("plan-assistant-engineering/SKILL.md", original.replace(token, ""))
                self.assertTrue(self.validate(), token)

    def test_portable_fallbacks_pass_without_hardcoded_home(self) -> None:
        self.build_minimal_tree()
        for name, (mode, _) in VALIDATOR.ASSISTANT_ENTRIES.items():
            text = (self.root / name / "SKILL.md").read_text()
            self.assertIn("${HERMES_SKILL_DIR}/../SKILL.md", text)
            self.assertNotIn("~/.hermes", text)
            if mode != "chat":
                self.assertIn(f"${{HERMES_SKILL_DIR}}/../references/{mode}/index.md", text)
        self.assertEqual([], self.validate())

    def test_hardcoded_home_does_not_replace_portable_fallback(self) -> None:
        self.build_minimal_tree()
        text = entry_text("plan-assistant-engineering").replace(
            "${HERMES_SKILL_DIR}/../",
            "~/.hermes/profiles/assistant/skills/assistant-pipeline/",
        )
        self.write("plan-assistant-engineering/SKILL.md", text)
        errors = self.validate()
        self.assertTrue(any("missing canonical fallback ${HERMES_SKILL_DIR}/../SKILL.md" in e for e in errors))
        self.assertTrue(any("missing canonical fallback ${HERMES_SKILL_DIR}/../references/plan/index.md" in e for e in errors))

    def test_chat_requires_kernel_without_shared_chat_mode(self) -> None:
        self.build_minimal_tree()
        self.assertFalse((self.root / "references/chat").exists())
        path = self.root / "chat-assistant/SKILL.md"
        path.write_text(path.read_text().replace('skill_view(name="assistant-pipeline")', ""))
        self.assertTrue(any("missing dependency" in e and "chat-assistant" in e for e in self.validate()))

    def test_missing_chat_and_shared_files(self) -> None:
        self.build_minimal_tree()
        (self.root / "chat-assistant/references/lookups.md").unlink()
        (self.root / "references/execute/scheduled.md").unlink()
        errors = self.validate()
        self.assertTrue(any("missing chat reference" in e for e in errors))
        self.assertTrue(any("missing shared mode file" in e for e in errors))

    def test_shared_indexes_route_six_entries_without_loading_them(self) -> None:
        self.build_minimal_tree()
        for mode, prefix in (("plan", "plan"), ("execute", "execute"), ("quality-assurance", "qa")):
            path = self.root / "references" / mode / "index.md"
            original = path.read_text()
            name = f"{prefix}-assistant-writing"
            with self.subTest(mode=mode):
                path.write_text(original.replace(name, ""))
                self.assertTrue(any(f"shared {mode} index does not route {name}" in e for e in self.validate()))
                for call in (
                    f'skill_view(name="{name}")',
                    f'skill_view(name="assistant-pipeline", file_path="{name}/SKILL.md")',
                ):
                    path.write_text(original + "\n" + call)
                    self.assertTrue(any("must not recursively load" in e for e in self.validate()))
                path.write_text(original + f"\n[entry](../../{name}/SKILL.md)")
                self.assertEqual([], self.validate())

    def test_catalog_is_closed_and_assignees_cannot_drift(self) -> None:
        self.build_minimal_tree()
        original = entry_text("execute-assistant-creative")
        for old, new in (("deterministic-render", "new-unit"), ("assignee: creator", "assignee: writer")):
            self.write("execute-assistant-creative/SKILL.md", original.replace(old, new))
            self.assertTrue(any("entry card catalog must be" in e for e in self.validate()))

    def test_chat_and_creative_reference_floors(self) -> None:
        self.build_minimal_tree()
        self.write("chat-assistant/references/extra.md", "# Extra\n")
        (self.root / "execute-assistant-creative/references/legacy/index.md").unlink()
        errors = self.validate()
        self.assertTrue(any("unexpected chat reference" in e for e in errors))
        self.assertTrue(any("missing creative legacy index" in e for e in errors))

    def test_catalog_ignores_and_validator_rejects_other_declarations(self) -> None:
        self.build_minimal_tree()
        expected = VALIDATOR.collect_card_catalog()
        for rel in (
            "SKILL.md", "plan-assistant-writing/SKILL.md", "execute-assistant-research/SKILL.md",
            "references/execute/index.md", "execute-assistant-search/references/lookup.md",
            "execute-assistant-creative/references/legacy/nested/hidden.md", "docs/cards.md",
        ):
            with self.subTest(rel=rel):
                path = self.root / rel
                original = path.read_text() if path.is_file() else None
                self.write(rel, "---\ncard_units:\n- name: sneaky-unit\n  assignee: engineer\n---\n")
                self.assertEqual(expected, VALIDATOR.collect_card_catalog())
                self.assertTrue(any("card_units are only legal" in e and rel in e for e in self.validate()))
                if original is not None:
                    path.write_text(original)
                else:
                    path.unlink()

    def test_markdown_links_are_confined_in_every_domain(self) -> None:
        self.build_minimal_tree()
        for cap in VALIDATOR.EXPECTED_CAPABILITIES:
            rel = f"plan-assistant-{cap}/SKILL.md"
            original = (self.root / rel).read_text()
            for link, diagnostic in (("references/missing.md", "link is broken"),
                                     ("../../outside.md", "link escapes the pipeline")):
                with self.subTest(cap=cap, link=link):
                    self.write(rel, original + f"\n[bad]({link})\n")
                    self.assertTrue(any(diagnostic in e and rel in e for e in self.validate()))
            self.write(rel, original + '\n`skill_view(name="writer-pipeline", file_path="references/consultation.md")`\n'
                       + '```sh\ncommand --output OUTPUT/report.md\n```\n')
        self.assertEqual([], self.validate())


class AssistantAlignmentIsolationTest(unittest.TestCase):
    def test_mapping_alignments_use_call_time_pipeline(self) -> None:
        for capability in ("writing", "research", "search"):
            with self.subTest(capability=capability), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                plan = root / f"plan-assistant-{capability}" / "references"
                qa = root / f"qa-assistant-{capability}" / "references"
                plan.mkdir(parents=True)
                qa.mkdir(parents=True)
                (plan / "synthetic.md").write_text("QA `synthetic-contract`\n")
                (qa / "synthetic-contract.md").write_text("# Contract\n")
                # Entry bodies are not type leaves or QA contracts.
                (plan.parent / "SKILL.md").write_text("# Entry, not a mapped leaf\n")
                (qa.parent / "SKILL.md").write_text("# Entry, not an unclaimed contract\n")
                with mock.patch.object(VALIDATOR, "ASSISTANT_PIPELINE", root):
                    validate = getattr(VALIDATOR, f"validate_{capability}_alignment")
                    errors = []
                    validate(errors)
                    self.assertEqual([], errors)
                    (plan / "synthetic.md").write_text("QA `missing-contract`\n")
                    validate(errors)
                    self.assertTrue(any("names missing QA contract" in e for e in errors), errors)
                    self.assertTrue(any("claimed by no plan leaf" in e for e in errors), errors)

    def test_engineering_uses_call_time_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "plan-assistant-engineering/references"
            qa = root / "qa-assistant-engineering/references"
            plan.mkdir(parents=True)
            qa.mkdir(parents=True)
            (plan / "synthetic.md").write_text("# Client guide\n")
            (plan.parent / "SKILL.md").write_text("# Entry\n")
            (qa / "inspection.md").write_text("| Archetype | Acceptance |\n| synthetic | works |\n")
            with mock.patch.object(VALIDATOR, "ASSISTANT_PIPELINE", root):
                errors = []
                VALIDATOR.validate_engineering_alignment(errors)
                self.assertEqual([], errors)
                (qa / "inspection.md").write_text("| orphan | wrong |\n")
                VALIDATOR.validate_engineering_alignment(errors)
                self.assertTrue(any("misses plan archetype: synthetic" in e for e in errors), errors)
                self.assertTrue(any("row has no plan leaf: orphan" in e for e in errors), errors)

    def test_entry_helper_explicit_and_call_time_roots(self) -> None:
        with mock.patch.object(VALIDATOR, "ASSISTANT_PIPELINE", Path("candidate")):
            self.assertEqual(Path("candidate/qa-assistant-writing"),
                             VALIDATOR.assistant_entry_dir("quality-assurance", "writing"))
            self.assertEqual(Path("explicit/chat-assistant"),
                             VALIDATOR.assistant_entry_dir("chat", pipeline=Path("explicit")))
            with self.assertRaises(ValueError):
                VALIDATOR.assistant_entry_dir("plan", "unknown")


class PairedCandidateStructureTest(unittest.TestCase):
    def test_absent_private_candidate_environment_skips(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
            VALIDATOR, "validate_assistant_pipeline"
        ) as validate:
            with self.assertRaisesRegex(unittest.SkipTest, "requires explicit HERMES_PRIVATE_ROOT"):
                self.test_paired_candidate_structure()
            validate.assert_not_called()

    def test_invalid_private_candidate_environment_fails_without_live_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for value, message in (
                ("", "HERMES_PRIVATE_ROOT must not be empty"),
                ("   ", "HERMES_PRIVATE_ROOT must not be empty"),
                (str(Path(tmp) / "nonexistent"), "candidate pipeline missing"),
            ):
                with self.subTest(value=value), mock.patch.dict(
                    os.environ, {"HERMES_PRIVATE_ROOT": value}
                ), mock.patch.object(VALIDATOR, "validate_assistant_pipeline") as validate:
                    with self.assertRaisesRegex(AssertionError, message):
                        self.test_paired_candidate_structure()
                    validate.assert_not_called()

    def test_paired_candidate_structure(self) -> None:
        private_root = os.environ.get("HERMES_PRIVATE_ROOT")
        if private_root is None:
            self.skipTest("opt-in paired-candidate check requires explicit HERMES_PRIVATE_ROOT")
        self.assertTrue(private_root.strip(), "HERMES_PRIVATE_ROOT must not be empty")
        pipeline = Path(private_root) / "hermes/profiles/assistant/skills/assistant-pipeline"
        self.assertTrue(pipeline.is_dir(), f"candidate pipeline missing: {pipeline}")
        public = SCRIPT.parents[1]
        with mock.patch.object(VALIDATOR, "ASSISTANT_PIPELINE", pipeline), mock.patch.object(
            VALIDATOR, "HERMES_ROOT", public
        ):
            errors = []
            refs, catalog = VALIDATOR.validate_assistant_pipeline(errors)
            for capability in ("creative", "engineering", "writing", "research", "search"):
                getattr(VALIDATOR, f"validate_{capability}_alignment")(errors)
            for profile in VALIDATOR.WORKER_PROFILES:
                kernel = public / "profiles" / profile / "skills" / f"{profile}-pipeline/SKILL.md"
                self.assertTrue(kernel.is_file(), f"public worker kernel missing: {kernel}")
                VALIDATOR.validate_worker_card_gate(profile, catalog, errors)
            hands_leaves = {}
            for profile in VALIDATOR.HANDS_PROFILES:
                hands_pipeline = public / "profiles" / profile / "skills" / f"{profile}-pipeline"
                self.assertTrue(hands_pipeline.is_dir(), f"public hands pipeline missing: {hands_pipeline}")
                hands_leaves[profile] = VALIDATOR.validate_hands_leaves(hands_pipeline, profile, errors)
            VALIDATOR.validate_hands_subjects(hands_leaves, errors)
            VALIDATOR.validate_hands_routing(hands_leaves, errors)
            self.assertGreater(refs, 0)
            self.assertEqual({unit: who for cards in CARDS.values() for unit, who in cards.items()}, catalog)
            self.assertEqual(catalog, VALIDATOR.collect_card_catalog())
            self.assertEqual([], errors, "\n".join(errors))


class ContinuityCandidateEnvironmentTest(unittest.TestCase):
    def test_continuity_plan_selects_explicit_private_candidate(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "verify_work_continuity_candidate", SCRIPT.with_name("verify-work-continuity.py")
        )
        assert spec and spec.loader
        continuity = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(continuity)
        private = Path("/candidate/private")
        runtime = Path("/candidate/runtime")
        for inherited in ({}, {"HERMES_PRIVATE_ROOT": "/wrong/private"}):
            with self.subTest(inherited=inherited), mock.patch.dict(os.environ, inherited, clear=True):
                plan = continuity.build_plan(runtime, private, runtime / "venv/bin/python")
                for stage in plan:
                    self.assertEqual(str(private), stage["env"]["HERMES_PRIVATE_ROOT"])
                    self.assertEqual(str(SCRIPT.parents[2]), stage["env"]["HERMES_PUBLIC_ROOT"])


class GitBoundaryOverlayTest(unittest.TestCase):
    """Managed dirs provided by the private overlay are sanctioned symlinks."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.overlay = root / "private"
        (self.overlay / "skills" / "desks").mkdir(parents=True)
        (root / "elsewhere" / "desks").mkdir(parents=True)
        self.overlay_link = root / "overlay-link"
        self.overlay_link.symlink_to(self.overlay / "skills" / "desks")
        self.foreign_link = root / "foreign-link"
        self.foreign_link.symlink_to(root / "elsewhere" / "desks")
        self._original = VALIDATOR.PRIVATE_OVERLAY
        VALIDATOR.PRIVATE_OVERLAY = self.overlay
        # A real, gitignored path inside the repo keeps the learned probe green.
        self.learned = (
            VALIDATOR.HERMES_ROOT / "profiles" / "assistant" / "skills" / "learned"
        )

    def tearDown(self) -> None:
        VALIDATOR.PRIVATE_OVERLAY = self._original
        self._tmp.cleanup()

    def test_accepts_symlink_into_private_overlay(self) -> None:
        errors: list[str] = []
        VALIDATOR.validate_git_boundary([self.overlay_link], self.learned, errors)
        self.assertEqual([], errors)

    def test_rejects_symlink_outside_private_overlay(self) -> None:
        errors: list[str] = []
        VALIDATOR.validate_git_boundary([self.foreign_link], self.learned, errors)
        self.assertTrue(
            any("symlink outside the private overlay" in e for e in errors), errors
        )

    def test_rejects_dangling_overlay_symlink(self) -> None:
        dangling = Path(self._tmp.name) / "dangling-link"
        dangling.symlink_to(self.overlay / "skills" / "missing")
        errors: list[str] = []
        VALIDATOR.validate_git_boundary([dangling], self.learned, errors)
        self.assertTrue(errors, "dangling overlay symlink must be reported")


class AssistantMessagingConfigTest(unittest.TestCase):
    def write_config(self, text: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "config.yaml"
        path.write_text(text, encoding="utf-8")
        return path

    def test_accepts_matching_discord_front_door(self) -> None:
        config = self.write_config(
            "platform_toolsets:\n"
            "  telegram: [web, terminal, no_mcp]\n"
            "  discord: [web, terminal, no_mcp]\n"
            "discord:\n"
            "  require_mention: true\n"
            "  allowed_channels: ['123']\n"
            "  auto_thread: true\n"
            "  channel_skill_bindings:\n"
            "    - id: '123'\n"
            "      skills: [assistant-pipeline]\n"
            "    - id: 'dm-1'\n"
            "      skills: [assistant-pipeline]\n"
            "  channel_prompts:\n"
            "    '123': Discord formatting\n"
            "    'dm-1': Discord DM formatting\n"
            "telegram:\n"
            "  channel_skill_bindings:\n"
            "    - id: 'tg-1'\n"
            "      skills: [assistant-pipeline]\n"
            "  channel_prompts:\n"
            "    'tg-1': Telegram formatting\n"
            "platforms:\n"
            "  telegram:\n"
            "    extra:\n"
            "      dm_topics:\n"
            "        - chat_id: 'tg-1'\n"
        )
        errors: list[str] = []
        VALIDATOR.validate_assistant_messaging_config(config, errors)
        self.assertEqual([], errors)

    def test_rejects_discord_permission_drift(self) -> None:
        config = self.write_config(
            "platform_toolsets:\n"
            "  telegram: [web, terminal]\n"
            "  discord: [web]\n"
            "discord:\n"
            "  require_mention: true\n"
            "  allowed_channels: ['123']\n"
            "  auto_thread: true\n"
            "  channel_skill_bindings:\n"
            "    - id: '123'\n"
            "      skill: assistant-pipeline\n"
            "  channel_prompts:\n"
            "    '123': Discord formatting\n"
        )
        errors: list[str] = []
        VALIDATOR.validate_assistant_messaging_config(config, errors)
        self.assertTrue(any("must match Telegram" in error for error in errors))

    def test_rejects_missing_discord_pipeline_binding(self) -> None:
        config = self.write_config(
            "platform_toolsets:\n"
            "  telegram: [web]\n"
            "  discord: [web]\n"
            "discord:\n"
            "  require_mention: true\n"
            "  allowed_channels: ['123']\n"
            "  auto_thread: true\n"
        )
        errors: list[str] = []
        VALIDATOR.validate_assistant_messaging_config(config, errors)
        self.assertTrue(any("bind assistant-pipeline" in error for error in errors))

    def test_rejects_unbound_allowlisted_discord_channel(self) -> None:
        config = self.write_config(
            "platform_toolsets:\n"
            "  telegram: [web]\n"
            "  discord: [web]\n"
            "discord:\n"
            "  require_mention: true\n"
            "  allowed_channels: ['123', '456']\n"
            "  auto_thread: true\n"
            "  channel_skill_bindings:\n"
            "    - id: '123'\n"
            "      skill: assistant-pipeline\n"
            "  channel_prompts:\n"
            "    '123': Discord formatting\n"
        )
        errors: list[str] = []
        VALIDATOR.validate_assistant_messaging_config(config, errors)
        self.assertTrue(any("channel 456 must bind" in error for error in errors))
        self.assertTrue(any("channel 456 must have" in error for error in errors))

    def test_rejects_blank_discord_channel_prompt(self) -> None:
        config = self.write_config(
            "platform_toolsets:\n"
            "  telegram: [web]\n"
            "  discord: [web]\n"
            "discord:\n"
            "  require_mention: true\n"
            "  allowed_channels: ['123']\n"
            "  auto_thread: true\n"
            "  channel_skill_bindings:\n"
            "    - id: '123'\n"
            "      skill: assistant-pipeline\n"
            "  channel_prompts:\n"
            "    '123': '   '\n"
        )
        errors: list[str] = []
        VALIDATOR.validate_assistant_messaging_config(config, errors)
        self.assertTrue(any("channel 123 must have" in error for error in errors))

    def test_rejects_missing_discord_dm_binding(self) -> None:
        config = self.write_config(
            "platform_toolsets:\n"
            "  telegram: [web]\n"
            "  discord: [web]\n"
            "discord:\n"
            "  require_mention: true\n"
            "  allowed_channels: ['123']\n"
            "  auto_thread: true\n"
            "  channel_skill_bindings:\n"
            "    - id: '123'\n"
            "      skill: assistant-pipeline\n"
            "  channel_prompts:\n"
            "    '123': Discord formatting\n"
        )
        errors: list[str] = []
        VALIDATOR.validate_assistant_messaging_config(config, errors)
        self.assertTrue(any("bind at least one DM" in error for error in errors))

    def test_rejects_missing_telegram_front_door(self) -> None:
        config = self.write_config(
            "platform_toolsets:\n"
            "  telegram: [web]\n"
            "  discord: [web]\n"
            "discord:\n"
            "  require_mention: true\n"
            "  allowed_channels: ['123']\n"
            "  auto_thread: true\n"
            "  channel_skill_bindings:\n"
            "    - id: '123'\n"
            "      skill: assistant-pipeline\n"
            "    - id: 'dm-1'\n"
            "      skill: assistant-pipeline\n"
            "  channel_prompts:\n"
            "    '123': Discord formatting\n"
            "    'dm-1': Discord DM formatting\n"
            "platforms:\n"
            "  telegram:\n"
            "    extra:\n"
            "      dm_topics:\n"
            "        - chat_id: 'tg-1'\n"
        )
        errors: list[str] = []
        VALIDATOR.validate_assistant_messaging_config(config, errors)
        self.assertTrue(any("Telegram chat tg-1 must bind" in error for error in errors))
        self.assertTrue(any("Telegram chat tg-1 must have" in error for error in errors))


class LearnedPlacementTest(unittest.TestCase):
    """skills.create_dir owns where runtime-authored skills land."""

    def write_config(self, text: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "config.yaml"
        path.write_text(text, encoding="utf-8")
        return path

    def test_accepts_learned_create_dir(self) -> None:
        config = self.write_config(
            "skills:\n"
            "  external_dirs: []\n"
            "  create_dir: skills/learned\n"
            "plugins:\n"
            "  enabled: [skill-topology, kanban-worker-mutation-guard]\n"
        )
        errors: list[str] = []
        VALIDATOR.validate_plugin_enabled("researcher", config, errors)
        self.assertEqual([], errors)

    def test_rejects_missing_or_foreign_create_dir(self) -> None:
        for skills_block in ("skills:\n  external_dirs: []\n", "skills:\n  create_dir: skills\n", ""):
            with self.subTest(skills_block=skills_block):
                config = self.write_config(
                    f"{skills_block}plugins:\n  enabled: [skill-topology, kanban-worker-mutation-guard]\n"
                )
                errors: list[str] = []
                VALIDATOR.validate_plugin_enabled("researcher", config, errors)
                self.assertTrue(
                    any("skills.create_dir must be 'skills/learned'" in error for error in errors),
                    errors,
                )

    def test_learned_skills_may_nest_one_category(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        learned = Path(directory.name) / "learned"
        for rel in ("flat", "research/nested"):
            skill = learned / rel / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                f"---\nname: {skill.parent.name}\ndescription: x\n---\n", encoding="utf-8"
            )
        errors: list[str] = []
        found, roots = VALIDATOR.validate_learned_skills(learned, errors)
        self.assertEqual([], errors)
        self.assertEqual({"flat", "nested"}, set(found))
        self.assertEqual(
            {("learned", "flat", "SKILL.md"), ("learned", "research", "nested", "SKILL.md")},
            roots,
        )
        VALIDATOR.validate_allowed_skill_roots(learned.parent, roots, errors)
        self.assertEqual([], errors)


class HandsLeafTest(unittest.TestCase):
    """Creator hands v3: `<verb>/<subject>/SKILL.md` leaves with a form."""

    LEAF = (
        "---\n"
        "name: {name}\n"
        "description: One icon drawn by a model.\n"
        "metadata:\n"
        "  hermes:\n"
        "    category: hands\n"
        "    hands: {hands}\n"
        "    cost: {cost}\n"
        "    output: icon.png\n"
        "    form:\n"
        "{form}"
        "---\n<Procedure>\n</Procedure>\n"
    )
    FORM = (
        "      what_for: {{required: true}}\n"
        "      style: {{required: true, options: [pixel], other: true}}\n"
        "      note: {{required: false}}\n"
    )

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "image-creator-pipeline"
        self.root.mkdir()
        (self.root / "SKILL.md").write_text(
            "---\nname: image-creator-pipeline\nmetadata:\n  hermes:\n"
            "    category: hands\n---\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def leaf(
        self,
        rel: str,
        name: str,
        *,
        hands: str = "image-creator",
        cost: str = "metered",
        form: str = FORM,
        styles: tuple[str, ...] = ("pixel",),
    ) -> Path:
        leaf_dir = self.root / rel
        leaf_dir.mkdir(parents=True, exist_ok=True)
        for style in styles:
            style_path = leaf_dir / "references" / "styles" / f"{style}.md"
            style_path.parent.mkdir(parents=True, exist_ok=True)
            style_path.write_text("# style\n", encoding="utf-8")
        path = leaf_dir / "SKILL.md"
        path.write_text(
            self.LEAF.format(name=name, hands=hands, cost=cost, form=form.format()),
            encoding="utf-8",
        )
        return path

    def validate(self) -> tuple[dict[str, Path], list[str]]:
        errors: list[str] = []
        leaves = VALIDATOR.validate_hands_leaves(self.root, "image-creator", errors)
        return leaves, errors

    def test_valid_leaf_passes(self) -> None:
        self.leaf("generate/icon", "generate-icon")
        leaves, errors = self.validate()
        self.assertEqual([], errors)
        self.assertEqual(["generate-icon"], sorted(leaves))

    def test_root_support_dirs_are_not_leaves(self) -> None:
        self.leaf("generate/icon", "generate-icon")
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "helper.sh").write_text("#!/bin/sh\n")
        _, errors = self.validate()
        self.assertEqual([], errors)

    def test_rejects_unknown_verb(self) -> None:
        self.leaf("render/icon", "render-icon")
        _, errors = self.validate()
        self.assertTrue(any("hands verb must be one of" in e for e in errors), errors)

    def test_rejects_leaf_at_wrong_depth(self) -> None:
        self.leaf("generate/icon/app", "generate-icon-app")
        _, errors = self.validate()
        self.assertTrue(any("<verb>/<subject>/SKILL.md" in e for e in errors), errors)

    def test_rejects_name_path_mismatch(self) -> None:
        self.leaf("generate/icon", "generate-logo")
        _, errors = self.validate()
        self.assertTrue(
            any("frontmatter name must be generate-icon" in e for e in errors), errors
        )

    def test_rejects_wrong_hands_and_cost(self) -> None:
        self.leaf("generate/icon", "generate-icon", hands="video-creator", cost="cheap")
        _, errors = self.validate()
        self.assertTrue(any("hands must be image-creator" in e for e in errors), errors)
        self.assertTrue(any("cost must be one of" in e for e in errors), errors)

    def test_rejects_form_without_note_or_required_flag(self) -> None:
        form = "      what_for: {{label: x}}\n"
        self.leaf("generate/icon", "generate-icon", form=form, styles=())
        _, errors = self.validate()
        self.assertTrue(any("carry a `note` field" in e for e in errors), errors)
        self.assertTrue(any("must set required" in e for e in errors), errors)

    def test_rejects_unbacked_style_option(self) -> None:
        self.leaf("generate/icon", "generate-icon", styles=())
        _, errors = self.validate()
        self.assertTrue(
            any("no references/styles/pixel.md" in e for e in errors), errors
        )

    def test_rejects_unknown_field_type(self) -> None:
        form = (
            "      what_for: {{required: true, type: blob}}\n"
            "      note: {{required: false}}\n"
        )
        self.leaf("generate/icon", "generate-icon", form=form, styles=())
        _, errors = self.validate()
        self.assertTrue(any("unknown type 'blob'" in e for e in errors), errors)

    def test_reference_backed_options_require_files(self) -> None:
        form = (
            "      contents: {{required: true, options: [buttons, panels]}}\n"
            "      note: {{required: false}}\n"
        )
        path = self.leaf("generate/kit", "generate-kit", form=form, styles=())
        refs = path.parent / "references" / "contents"
        refs.mkdir(parents=True)
        (refs / "buttons.md").write_text("# buttons\n")
        _, errors = self.validate()
        self.assertEqual(1, len(errors), errors)
        self.assertIn("no references/contents/panels.md", errors[0])
        (refs / "panels.md").write_text("# panels\n")
        self.assertEqual([], self.validate()[1])

    def test_options_without_reference_directory_remain_valid(self) -> None:
        form = (
            "      pack: {{required: true, options: [custom]}}\n"
            "      note: {{required: false}}\n"
        )
        self.leaf("generate/kit", "generate-kit", form=form, styles=())
        self.assertEqual([], self.validate()[1])

    def test_reference_options_cannot_escape_directory(self) -> None:
        form = (
            "      style: {{required: true, options: ['../outside']}}\n"
            "      note: {{required: false}}\n"
        )
        self.leaf("generate/kit", "generate-kit", form=form, styles=())
        self.assertTrue(any("reference option must be a slug" in e for e in self.validate()[1]))

    def test_subjects_unique_across_hands(self) -> None:
        errors: list[str] = []
        VALIDATOR.validate_hands_subjects(
            {
                "image-creator": {"edit-fit": Path("a")},
                "video-creator": {"edit-fit": Path("b"), "generate-clip": Path("c")},
            },
            errors,
        )
        self.assertEqual(1, len(errors), errors)
        self.assertIn("subject fit is owned by both image-creator and video-creator", errors[0])

    def test_audio_creator_generate_speech_leaf_passes(self) -> None:
        """audio-creator's generate-speech: a required script file, an
        optional voice, cost free, note optional."""
        form = (
            "      script: {{required: true, type: file}}\n"
            "      voice: {{required: false}}\n"
            "      note: {{required: false}}\n"
        )
        self.leaf(
            "generate/speech",
            "generate-speech",
            hands="audio-creator",
            cost="free",
            form=form,
            styles=(),
        )
        errors: list[str] = []
        leaves = VALIDATOR.validate_hands_leaves(self.root, "audio-creator", errors)
        self.assertEqual([], errors)
        self.assertEqual(["generate-speech"], sorted(leaves))


class EndToEndTest(unittest.TestCase):
    def test_all_profiles_pass(self) -> None:
        if not VALIDATOR.ASSISTANT_PIPELINE.is_dir():
            self.skipTest("deployment-only: repository private overlay is absent")
        # Invoke via sys.executable, not the script's `uv run --script` shebang:
        # this pins the actual provisioned interpreter running the test itself,
        # instead of letting uv/mise resolve one under a possibly-faked HOME.
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--all"],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("PASS:", result.stdout)
        self.assertIn("assistant-pipeline=", result.stdout)


if __name__ == "__main__":
    unittest.main()
