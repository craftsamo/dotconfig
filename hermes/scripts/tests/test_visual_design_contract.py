"""Static consumer contracts; not true-3D integration or artistic validation."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2] / "profiles"


def text(path):
    return " ".join(path.read_text().split())


class VisualDesignContractTest(unittest.TestCase):
    def test_assistant_carries_complete_design_and_creator_does_not_bind_it(self):
        skill = text(ROOT / "assistant/skills/assistant-pipeline/execute-assistant-creative/SKILL.md")
        for phrase in ("carry the complete identified design (JSON, HTML timeline, receipt)",
                       "never add form keys", "claim unsupported Three.js or shader support",
                       "accept a silently flattened substitute",
                       "authored video gets intent only and the producer writes the storyboard"):
            self.assertIn(phrase, skill)
        kernel = text(ROOT / "creator/skills/creator-pipeline/SKILL.md")
        self.assertIn("Technique names (GSAP, Three.js, shaders) appear only where the selected leaf supports them",
                      kernel)
        self.assertIn("No storyboard, timeline, frame specification, layout or pixel size", kernel)
        self.assertIn("never propose an unsupported method", kernel)

    def test_hands_preserve_components_and_intermediate_motion(self):
        video = text(ROOT / "video-creator/skills/video-creator-pipeline/references/craft.md")
        image = text(ROOT / "image-creator/skills/image-creator-pipeline/references/craft.md")
        self.assertIn("before/during/after", video)
        self.assertIn("Do not postpone intermediate choreography", video)
        self.assertIn("exact proposal/preview approvals", video)
        self.assertIn("actual native/use-size pixels", image)
        self.assertIn("return that specific limitation to the Assistant", image)
        self.assertIn("budgets/approvals unchanged", image)


if __name__ == "__main__":
    unittest.main()
