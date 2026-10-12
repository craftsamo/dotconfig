"""audit-motion-vocabulary.py: routing, shape, tell and wording checks."""

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

HEADER = "| Name | Feel | For | Looks like | The tell | Built with |\n| --- | --- | --- | --- | --- | --- |\n"
CORE = (
    "# Motion and component vocabulary\n\n## More names\n\n| Deciding | Open |\n| --- | --- |\n"
    '| a scrolling page | `skill_view(name="video-creator-pipeline", file_path="references/motion-vocabulary-scroll.md")` |\n\n'
    "## Text animations\n\n" + HEADER +
    "| count-up（カウントアップ） | snappy | text | a number climbs | the units digit races ahead — vs `sticky`: that holds still | tween an object |\n"
)
SCROLL = (
    "# Scroll-driven motion vocabulary\n\nA dictionary, not a rulebook.\n\n## Scroll-driven page\n\n" + HEADER +
    "| sticky（スティッキー） | heavy | UI | a block stays put while the page moves | it holds until its container ends | the page container moves on the timeline |\n"
)


def write(root: Path, name: str, text: str) -> None:
    path = root / AUDIT.VOCAB_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class AuditMotionVocabularyTest(unittest.TestCase):
    def test_repository_vocabulary_passes(self) -> None:
        report = AUDIT.audit(REPO_ROOT, None, [])
        self.assertEqual([], report["errors"])
        self.assertGreater(report["entries"], 800)

    def test_clean_fixture_passes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "motion-vocabulary.md", CORE)
            write(root, "motion-vocabulary-scroll.md", SCROLL)
            self.assertEqual(0, AUDIT.main(["--root", str(root)]))

    def test_each_breakage_is_reported(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            broken = SCROLL + (
                "| parallax（パララックス） | smooth | UI | layers drift | the far layer lags 3 steps | layers move |\n"
                "| marquee（マーキー） | smooth | UI | a band runs | too fast and it blurs | `Math.random` offsets |\n"
                "| snap | snappy | UI | sections lock |\n"
                "| pin（ピン） | heavy | UI | a panel pins | it holds — vs `missing entry`: none | pinned layer |\n"
            )
            write(root, "motion-vocabulary.md", CORE)
            write(root, "motion-vocabulary-scroll.md", broken)
            write(root, "motion-vocabulary-orphan.md", "# Orphan\n")
            errors = "\n".join(AUDIT.audit(root, None, [])["errors"])
            for expected in ("digit in The tell of parallax", "caution or advice in The tell of marquee",
                             "live, non-seekable build in marquee", "4 cells under a 6-cell header",
                             "unknown entry `missing entry`", "does not route motion-vocabulary-orphan.md"):
                self.assertIn(expected, errors)
            self.assertEqual(1, AUDIT.main(["--root", str(root)]))

    def test_source_wording_is_reported(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "motion-vocabulary.md", CORE)
            write(root, "motion-vocabulary-scroll.md", SCROLL)
            source = root / "source.txt"
            source.write_text("Here a block stays put while the page moves past it.", encoding="utf-8")
            errors = AUDIT.audit(root, None, [source])["errors"]
            self.assertTrue(any("shares wording with the source" in e for e in errors), errors)

    def test_web_catalog_must_match_vocabulary_names_and_aliases(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "motion-vocabulary.md", CORE)
            write(root, "motion-vocabulary-scroll.md", SCROLL)
            web = root / "web"
            web.mkdir()
            (web / "scroll.md").write_text(
                "| Name | Trigger | Web build |\n| --- | --- | --- |\n"
                "| sticky（スティッキー、追従） | scroll | `position: sticky` |\n"
                "| hover lift（ホバーリフト） | hover | transform |\n", encoding="utf-8")
            errors = "\n".join(AUDIT.audit(root, web, [])["errors"])
            self.assertIn("alias 追従 of `sticky` is missing", errors)
            self.assertIn("`hover lift` is not a motion vocabulary entry", errors)

    def test_invalid_invocation_returns_two(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertEqual(2, AUDIT.main(["--root", tmp]))
            write(Path(tmp), "motion-vocabulary.md", CORE)
            self.assertEqual(2, AUDIT.main(["--root", tmp, "--source", str(Path(tmp) / "absent.txt")]))


if __name__ == "__main__":
    unittest.main()
