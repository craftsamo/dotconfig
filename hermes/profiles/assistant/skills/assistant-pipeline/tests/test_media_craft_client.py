"""Client-side craft contract; structural evidence, not a perceptual test."""

from pathlib import Path
import unittest

import hermes_yaml as yaml

from _pair import PUBLIC_ROOT, private_config

PIPELINE = Path(__file__).resolve().parents[1]


class MediaCraftClientTests(unittest.TestCase):
    def test_only_direction_is_added_to_client_discovery(self):
        config = yaml.safe_load(private_config().read_text())
        names = {Path(path).name for path in config["skills"]["external_dirs"]
                 if Path(path).name.startswith("media-craft-")}
        self.assertEqual(names, {"media-craft-direction"})
        pipelines = {Path(path).name for path in config["skills"]["external_dirs"]
                     if Path(path).name.endswith("-creator-pipeline")}
        self.assertEqual(pipelines, {"image-creator-pipeline", "video-creator-pipeline",
                                     "audio-creator-pipeline"})
        self.assertNotIn("media-craft-direction", config["skills"].get("disabled", []))

    def test_plan_and_qa_read_specific_direction_knowledge(self):
        for entry, reference in (
            ("plan-assistant-creative", "reference-interpretation.md"),
            ("qa-assistant-creative", "critique-revision.md"),
        ):
            text = (PIPELINE / entry / "SKILL.md").read_text()
            self.assertIn('skill_view(name="media-craft-direction")', text)
            self.assertIn(f"references/{reference}", text)
            self.assertIn("read_file", text)
            self.assertIn("current", text)
        execute = (PIPELINE / "execute-assistant-creative/SKILL.md").read_text()
        execute = " ".join(execute.split())
        self.assertIn("Never compute, refresh or invent a hash", execute)
        self.assertIn("An approved study is not an approved final", execute)

    def test_paired_public_skill_is_present(self):
        root = PUBLIC_ROOT / "agents/curated/media-craft-direction"
        self.assertTrue((root / "SKILL.md").is_file())
        for name in ("reference-interpretation", "direction-constraints", "critique-revision"):
            self.assertTrue((root / "references" / f"{name}.md").is_file())


if __name__ == "__main__":
    unittest.main()
