"""Regression tests for create-ad / analyze-ad skill discovery.

The shared Hermes scanner (`tools.skills_tool._find_all_skills`) only reads
the first 4000 characters of each `SKILL.md` before calling
`_parse_frontmatter` (`agent.skill_utils.parse_frontmatter`, which searches
for the closing `\\n---\\n` fence). A closing fence that lands past that
4000-character budget makes the scan silently see an EMPTY frontmatter dict
instead of raising - discovery falls back to the parent name `ad`. Both `ad`
leaves must keep their closing fence comfortably inside that budget."""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from tools import skills_tool

HERMES_ROOT = Path(__file__).resolve().parents[2]
VIDEO_PIPELINE = HERMES_ROOT / "profiles" / "video-creator" / "skills" / "video-creator-pipeline"
CREATE_AD_DIR = VIDEO_PIPELINE / "create" / "ad"
ANALYZE_AD_DIR = VIDEO_PIPELINE / "analyze" / "ad"
CREATE_AD = CREATE_AD_DIR / "SKILL.md"
ANALYZE_AD = ANALYZE_AD_DIR / "SKILL.md"

# `_find_all_skills` truncates SKILL.md text to this many characters before
# searching for the closing frontmatter fence (tools/skills_tool.py); the
# fence must end comfortably inside it, hence the tighter guard budget.
FRONTMATTER_SCAN_BUDGET = 4000
CLOSING_FENCE_BUDGET = 3800


def _closing_fence_end(text: str) -> int:
    """Absolute offset right after the closing frontmatter fence, using the
    SAME pattern `agent.skill_utils.parse_frontmatter` searches with
    (matched against ``content[3:]``, so offset back by 3)."""
    match = re.search(r"\n---\s*\n", text[3:])
    assert match is not None, "no closing frontmatter fence found"
    return match.end() + 3


class ClosingFenceBudgetTest(unittest.TestCase):
    """Direct character-offset measurement against the real files, independent of
    the discovery scan below."""

    def test_create_ad_closing_fence_within_budget(self) -> None:
        end = _closing_fence_end(CREATE_AD.read_text(encoding="utf-8"))
        self.assertLessEqual(end, CLOSING_FENCE_BUDGET)
        self.assertLess(end, FRONTMATTER_SCAN_BUDGET)

    def test_analyze_ad_closing_fence_within_budget(self) -> None:
        end = _closing_fence_end(ANALYZE_AD.read_text(encoding="utf-8"))
        self.assertLessEqual(end, CLOSING_FENCE_BUDGET)
        self.assertLess(end, FRONTMATTER_SCAN_BUDGET)


class AdSkillDiscoveryTest(unittest.TestCase):
    """Exercise the real `_find_all_skills` scan against ONLY the real
    create/ad and analyze/ad directories, isolated from every other skill
    on disk (no other profile's skills leak in, no live config is read)."""

    def setUp(self) -> None:
        patchers = [
            patch.object(
                skills_tool, "_skill_search_dirs",
                return_value=([], [CREATE_AD_DIR, ANALYZE_AD_DIR], CREATE_AD_DIR),
            ),
            patch.object(skills_tool, "_get_disabled_skill_names", return_value=set()),
            patch.dict(skills_tool._SKILLS_CACHE, {}, clear=True),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_discovers_exactly_create_and_analyze_ad(self) -> None:
        results = skills_tool._find_all_skills()
        names = {item["name"] for item in results}
        self.assertEqual({"create-ad", "analyze-ad"}, names)
        self.assertNotIn("ad", names)
        for item in results:
            self.assertTrue(item["description"], f"{item['name']} has an empty description")

    def test_parsed_frontmatter_matches_full_metadata_for_both_leaves(self) -> None:
        for skill_md in (CREATE_AD, ANALYZE_AD):
            text = skill_md.read_text(encoding="utf-8")
            end = _closing_fence_end(text)
            self.assertLessEqual(end, CLOSING_FENCE_BUDGET, f"{skill_md} closing fence too far out")

            truncated_frontmatter, _ = skills_tool._parse_frontmatter(
                skills_tool._read_skill_text(skill_md)[:FRONTMATTER_SCAN_BUDGET]
            )
            full_yaml = text[3 : re.search(r"\n---\s*\n", text[3:]).start() + 3]
            full_frontmatter = yaml.safe_load(full_yaml)
            self.assertEqual(full_frontmatter, truncated_frontmatter)


if __name__ == "__main__":
    unittest.main()
