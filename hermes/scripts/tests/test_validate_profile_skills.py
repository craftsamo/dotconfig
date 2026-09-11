from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "validate-profile-skills.py"
SPEC = importlib.util.spec_from_file_location("validate_profile_skills", SCRIPT)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class AssistantPipelineTreeTest(unittest.TestCase):
    def test_repository_tree_is_valid(self) -> None:
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
        self.write(
            "SKILL.md",
            "---\n"
            "name: assistant-pipeline\n"
            "metadata:\n  hermes:\n    category: orchestration\n"
            "---\n# skill\n",
        )
        self.write("references/chat/index.md", "workspace-ops.md cron.md lookups.md")
        self.write("references/chat/workspace-ops.md", "# ops\n")
        self.write("references/chat/cron.md", "# cron\n")
        self.write("references/chat/lookups.md", "# lookups\n")
        self.write("references/plan/index.md", "# plan\n")
        self.write(
            "references/execute/index.md",
            "resident-sessions.md kanban-lite.md scheduled.md",
        )
        self.write("references/execute/resident-sessions.md", "# sessions\n")
        self.write("references/execute/kanban-lite.md", "# kanban\n")
        self.write("references/execute/scheduled.md", "# scheduled\n")
        self.write("references/quality-assurance/index.md", "# qa\n")
        for capability, names in VALIDATOR.REQUIRED_QA_CONTRACTS.items():
            listing = " ".join(sorted(names))
            if capability in VALIDATOR.QA_CONTRACT_LEGACY_CAPABILITIES:
                self.write(
                    f"references/quality-assurance/{capability}/index.md",
                    "legacy/index.md",
                )
                self.write(
                    f"references/quality-assurance/{capability}/legacy/index.md",
                    listing,
                )
                for name in names:
                    self.write(
                        f"references/quality-assurance/{capability}/legacy/{name}",
                        "# c\n",
                    )
                continue
            self.write(
                f"references/quality-assurance/{capability}/index.md", listing
            )
            for name in names:
                self.write(
                    f"references/quality-assurance/{capability}/{name}", "# c\n"
                )

    def validate(self) -> list[str]:
        errors: list[str] = []
        VALIDATOR.validate_assistant_pipeline(errors)
        return errors

    def test_minimal_tree_passes(self) -> None:
        self.build_minimal_tree()
        self.assertEqual([], self.validate())

    def test_rejects_unknown_mode_dir(self) -> None:
        self.build_minimal_tree()
        self.write("references/deploy/index.md", "# nope\n")
        errors = self.validate()
        self.assertTrue(any("unexpected mode" in e for e in errors), errors)

    def test_rejects_capability_dir_in_chat(self) -> None:
        self.build_minimal_tree()
        self.write("references/chat/creative/index.md", "# nope\n")
        errors = self.validate()
        self.assertTrue(any("must stay flat" in e for e in errors), errors)

    def test_rejects_unrouted_leaf(self) -> None:
        self.build_minimal_tree()
        self.write(
            "references/execute/creative/index.md", "# creative\n"
        )
        self.write("references/execute/creative/pixel-art.md", "# pixel\n")
        errors = self.validate()
        self.assertTrue(any("does not route pixel-art.md" in e for e in errors), errors)

    def test_accepts_valid_card_units(self) -> None:
        self.build_minimal_tree()
        self.write(
            "references/execute/creative/index.md",
            "---\n"
            "card_units:\n"
            "  - name: anchored-image-batch\n"
            "    assignee: creator\n"
            "    required_inputs: [approved-style-anchor]\n"
            "    unit_cap: \"one batch\"\n"
            "    runtime_cap: 1800\n"
            "---\n# creative\n",
        )
        self.assertEqual([], self.validate())
        errors: list[str] = []
        _, catalog = VALIDATOR.validate_assistant_pipeline(errors)
        self.assertEqual({"anchored-image-batch": "creator"}, catalog)

    def test_rejects_card_unit_with_unknown_assignee(self) -> None:
        self.build_minimal_tree()
        self.write(
            "references/execute/creative/index.md",
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
            "references/execute/creative/index.md",
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
            "references/execute/creative/index.md", f"---\n{unit}---\n# a\n"
        )
        self.write(
            "references/execute/research/index.md", f"---\n{unit}---\n# b\n"
        )
        errors = self.validate()
        self.assertTrue(any("duplicate card unit" in e for e in errors), errors)

    def test_rejects_card_units_outside_execute(self) -> None:
        self.build_minimal_tree()
        self.write(
            "references/plan/creative/index.md",
            "---\n"
            "card_units:\n"
            "  - name: sneaky-unit\n"
            "    required_inputs: [spec]\n"
            "    unit_cap: \"one\"\n"
            "    runtime_cap: 900\n"
            "---\n# plan\n",
        )
        errors = self.validate()
        self.assertTrue(any("only legal under execute/" in e for e in errors), errors)

    def test_rejects_missing_qa_contract(self) -> None:
        self.build_minimal_tree()
        (self.root / "references/quality-assurance/writing/prose.md").unlink()
        errors = self.validate()
        self.assertTrue(
            any("quality-assurance/writing/prose.md" in e for e in errors), errors
        )


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
