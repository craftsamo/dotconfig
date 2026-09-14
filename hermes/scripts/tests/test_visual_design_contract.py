"""Static consumer contracts; not true-3D integration or artistic validation."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2] / "profiles"


def text(path):
    return " ".join(path.read_text().split())


class VisualDesignContractTest(unittest.TestCase):
    def test_creator_preserves_complete_design_and_actual_support(self):
        root = ROOT / "creator/skills/creator-pipeline"
        craft = text(root / "references/craft.md")
        for phrase in ("read the complete supplied design", "scene/event/component IDs",
                       "Three.js", "GLSL", "Anime.js", "GSAP", "conceptual roles",
                       "not consent, feasibility or quality"):
            self.assertIn(phrase, craft)
        self.assertIn("Missing required 3D or shader support is a named capability gap", craft)
        self.assertIn("never rewrite a frozen design", craft)
        self.assertIn("not another Creator/Assistant inspection", craft)
        for entry in ("plan-creator", "build-creator"):
            self.assertIn("design-preserving realization contract", text(root / entry / "SKILL.md"))

    def test_hands_preserve_components_and_intermediate_motion(self):
        video = text(ROOT / "video-creator/skills/video-creator-pipeline/references/craft.md")
        image = text(ROOT / "image-creator/skills/image-creator-pipeline/references/craft.md")
        self.assertIn("before/during/after", video)
        self.assertIn("Do not postpone intermediate choreography", video)
        self.assertIn("exact proposal/preview approvals", video)
        self.assertIn("actual native/use-size pixels", image)
        self.assertIn("return that specific limitation to Creator", image)
        self.assertIn("budgets/approvals unchanged", image)


if __name__ == "__main__":
    unittest.main()
