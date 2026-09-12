"""Structural checks, not an aesthetic or behavioral evaluation of the skills."""

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILLS = sorted((ROOT / "curated").glob("media-craft-*/SKILL.md"))
FIELDS = {"id", "request", "operation", "subjects", "expected", "must_not", "review_evidence"}
SUBJECTS = {
    "icon", "emoji", "mascot", "reimagine", "kit", "card",
    "clip", "tour", "ad", "explainer-video", "music-video",
    "speech", "sfx", "music", "mix",
}


class MediaCraftStructureTests(unittest.TestCase):
    def test_at_least_one_independently_discoverable_skill(self):
        self.assertTrue(SKILLS)

    def test_roots_and_conditional_resources(self):
        for root in SKILLS:
            with self.subTest(skill=root.parent.name):
                body = root.read_text()
                self.assertTrue(body.startswith("---\n"))
                frontmatter_end = body.index("\n---", 4) + 4
                self.assertLess(frontmatter_end, 3800)
                self.assertIn(f"name: {root.parent.name}\n", body[:frontmatter_end])
                self.assertEqual(list(root.parent.rglob("SKILL.md")), [root])
                links = set(re.findall(r"\]\((references/[^)#]+\.md)(?:#[^)]*)?\)", body))
                actual = {str(p.relative_to(root.parent)) for p in root.parent.rglob("*.md") if p != root}
                self.assertEqual(links, actual, "Each conditional resource must be reachable from its root")
                for link in links:
                    path = (root.parent / link).resolve()
                    self.assertTrue(path.is_relative_to(root.parent.resolve()))
                    self.assertTrue(path.read_text().strip())
                self.assertFalse((root.parent / "README.md").exists())
                self.assertFalse((root.parent / "scripts").exists(), "Portable craft does not own execution")

    def test_case_contracts(self):
        for root in SKILLS:
            path = ROOT / "tests" / f"{root.parent.name}-cases.json"
            with self.subTest(skill=root.parent.name):
                cases = json.loads(path.read_text())
                self.assertTrue(cases)
                self.assertEqual(len(cases), len({case["id"] for case in cases}))
                for case in cases:
                    self.assertEqual(set(case), FIELDS)
                    for key in ("id", "request", "operation"):
                        self.assertIsInstance(case[key], str)
                        self.assertTrue(case[key].strip())
                    for key in ("subjects", "expected", "must_not", "review_evidence"):
                        self.assertIsInstance(case[key], list)
                        self.assertTrue(case[key])
                        self.assertTrue(all(isinstance(item, str) and item.strip() for item in case[key]))
                    self.assertLessEqual(set(case["subjects"]), SUBJECTS)


if __name__ == "__main__":
    unittest.main()
