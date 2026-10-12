"""audit-motion-vocabulary.py: routing, shape, tell, build and wording checks."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPT = Path(__file__).resolve().parents[1] / "audit-motion-vocabulary.py"
REPO_ROOT = SCRIPT.parents[2]
SPEC = importlib.util.spec_from_file_location("audit_motion_vocabulary", SCRIPT)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)

NAMES = "| Name | Feel | For | Looks like | The tell |\n| --- | --- | --- | --- | --- |\n"
BUILDS = "| Name | Built with |\n| --- | --- |\n"
SKILL = (
    "---\nname: motion-vocabulary\n---\n\n| Deciding | Names | Video builds |\n| --- | --- | --- |\n"
    "| most films | [core.md](references/core.md) | [video/core.md](references/video/core.md) |\n"
    "| scroll | [scroll.md](references/scroll.md) | [video/scroll.md](references/video/scroll.md) |\n"
)
CORE = ("# Core\n\nA dictionary, not a rulebook.\n\n## Text animations\n\n" + NAMES +
        "| count-up（カウントアップ） | snappy | text | a number climbs | the units digit races ahead — vs `sticky`: that holds still |\n")
CORE_VIDEO = "# Core: video builds\n\n## Text animations\n\n" + BUILDS + "| count-up（カウントアップ） | tween an object |\n"
SCROLL = ("# Scroll\n\nA dictionary, not a rulebook.\n\n## Scroll-driven page\n\n" + NAMES +
          "| sticky（スティッキー） | heavy | UI | a block stays put while the page moves | it holds until its container ends |\n")
SCROLL_VIDEO = ("# Scroll: video builds\n\n## Scroll-driven page\n\n" + BUILDS +
                "| sticky（スティッキー） | the page container moves on the timeline |\n")


def build(root: Path, **extra: str) -> None:
    skill = root / AUDIT.SKILL_DIR
    files = {"SKILL.md": SKILL, "references/core.md": CORE, "references/video/core.md": CORE_VIDEO,
             "references/scroll.md": SCROLL, "references/video/scroll.md": SCROLL_VIDEO, **extra}
    for rel, text in files.items():
        path = skill / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


class AuditMotionVocabularyTest(unittest.TestCase):
    def test_repository_vocabulary_passes(self) -> None:
        report = AUDIT.audit(REPO_ROOT, [])
        self.assertEqual([], report["errors"])
        self.assertGreater(report["entries"], 800)

    def test_clean_fixture_passes(self) -> None:
        with TemporaryDirectory() as tmp:
            build(Path(tmp))
            self.assertEqual(0, AUDIT.main(["--root", tmp]))

    def test_each_breakage_is_reported(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            build(root, **{
                "references/scroll.md": SCROLL + (
                    "| parallax（パララックス） | smooth | UI | layers drift | the far layer lags 3 steps |\n"
                    "| marquee（マーキー） | smooth | UI | a band runs | too fast and it blurs |\n"
                    "| snap | snappy | UI |\n"
                    "| pin（ピン） | heavy | UI | a panel pins | it holds — vs `missing entry`: none |\n"),
                "references/video/scroll.md": SCROLL_VIDEO + (
                    "| marquee（マーキー） | `Math.random` offsets |\n"
                    "| hover lift（ホバーリフト） | transform |\n"),
                "references/orphan.md": "# Orphan\n",
            })
            errors = "\n".join(AUDIT.audit(root, [])["errors"])
            for expected in ("digit in The tell of parallax", "caution or advice in The tell of marquee",
                             "live, non-seekable build in marquee", "3 cells under a 5-cell header",
                             "unknown entry `missing entry`", "does not route references/orphan.md",
                             "`hover lift` is not an entry of scroll.md"):
                self.assertIn(expected, errors)
            self.assertEqual(1, AUDIT.main(["--root", tmp]))

    def test_source_wording_is_reported(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            build(root)
            source = root / "source.txt"
            source.write_text("Here a block stays put while the page moves past it.", encoding="utf-8")
            errors = AUDIT.audit(root, [source])["errors"]
            self.assertTrue(any("shares wording with the source" in e for e in errors), errors)

    def test_shared_easing_numbers_are_not_wording(self) -> None:
        curve = "ease cubic-bezier(0.34, 1.56, 0.64, 1) over 400 ms"
        self.assertEqual(set(), AUDIT.shingles(curve) & AUDIT.shingles("uses " + curve))

    def test_invalid_invocation_returns_two(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertEqual(2, AUDIT.main(["--root", tmp]))
            build(Path(tmp))
            self.assertEqual(2, AUDIT.main(["--root", tmp, "--source", str(Path(tmp) / "absent.txt")]))


if __name__ == "__main__":
    unittest.main()
