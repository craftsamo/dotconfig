"""Structure of the shared motion-vocabulary skill.

Wording, references and tells are audited by
hermes/scripts/audit-motion-vocabulary.py; this file keeps the shape that
every reader (Hermes leaves, Creator, other CLIs) relies on.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "curated" / "motion-vocabulary"
REFS = SKILL / "references"
NAMES_HEADER = "| Name | Feel | For | Looks like | The tell |"
VIDEO_HEADER = "| Name | Built with |"


class MotionVocabularyTest(unittest.TestCase):
    def test_skill_routes_every_reference_file(self) -> None:
        body = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(body.startswith("---\nname: motion-vocabulary\n"))
        linked = set(re.findall(r"\]\(references/([a-z-]+(?:/[a-z-]+)?\.md)\)", body))
        present = {str(p.relative_to(REFS)) for p in REFS.rglob("*.md")}
        self.assertEqual(present, linked)

    def test_names_and_builds_keep_their_shapes(self) -> None:
        for path in sorted(REFS.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertIn("A dictionary, not a rulebook", text)
                header = "| Name | Feel | Looks like | The tell |" if path.name == "timing.md" else NAMES_HEADER
                self.assertIn(header, text)
                self.assertNotIn("| Built with |", text)
                self.assertLess(len(text.encode()), 60_000 if path.name == "core.md" else 45_000)
                self.assertTrue((REFS / "video" / path.name).is_file())
        for path in sorted((REFS / "video").glob("*.md")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=f"video/{path.name}"):
                self.assertIn(VIDEO_HEADER, text)
                self.assertIn("never a real input", text)
                self.assertLess(len(text.encode()), 25_000)

    def test_web_builds_keep_their_shape(self) -> None:
        self.assertIn("prefers-reduced-motion", (REFS / "web" / "building.md").read_text(encoding="utf-8"))
        for path in sorted((REFS / "web").glob("*.md")):
            if path.name == "building.md":
                continue
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=f"web/{path.name}"):
                self.assertTrue((REFS / path.name).is_file())
                self.assertIn("| Name | Trigger | Web build | Reduced motion |", text)
                self.assertLess(len(text.encode()), 48_000)

    def test_timing_defines_the_five_feel_words(self) -> None:
        timing = (REFS / "timing.md").read_text(encoding="utf-8")
        self.assertIn("## Feel", timing)
        for feel in ("なめらか", "きびきび", "やわらかい", "重い", "弾む"):
            self.assertIn(feel, timing)

    def test_names_stay_medium_neutral(self) -> None:
        for path in sorted(REFS.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertNotIn("skill_view(", text)
                self.assertNotIn("three-webgl2", text)
                self.assertNotIn("performed by the timeline", text)


if __name__ == "__main__":
    unittest.main()
