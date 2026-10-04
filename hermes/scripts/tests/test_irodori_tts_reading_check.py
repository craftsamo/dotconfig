from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

HERMES_DIR = Path(__file__).resolve().parents[2]
CHECK_PATH = HERMES_DIR / "scripts" / "irodori_tts_reading_check.py"
CORPUS_PATH = HERMES_DIR / "scripts" / "irodori_tts_reading_corpus.tsv"
READING_PATH = HERMES_DIR / "plugins" / "tts" / "irodori-tts" / "reading.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CHECK = load_module("irodori_tts_reading_check_test", CHECK_PATH)


class PronunciationKeyTest(unittest.TestCase):
    """Both sides reduce to how the words sound, never to how they are spelled."""

    def test_asr_katakana_matches_written_reading(self) -> None:
        self.assertEqual(
            CHECK.pronunciation_key("きょうわいちにちじゅう"),
            CHECK.pronunciation_key("キョーワイチニチジュー"),
        )

    def test_spelling_only_differences_are_lenient(self) -> None:
        key = CHECK.pronunciation_key
        self.assertEqual(key("ほんを"), key("ホンオ"))
        self.assertEqual(key("せんせい"), key("センセー"))
        self.assertEqual(key("とうきょう"), key("トーキョー"))

    def test_ha_and_he_are_not_folded(self) -> None:
        key = CHECK.pronunciation_key
        self.assertNotEqual(key("はし"), key("ワシ"))
        self.assertNotEqual(key("へや"), key("エヤ"))

    def test_a_different_reading_still_differs(self) -> None:
        key = CHECK.pronunciation_key
        self.assertNotEqual(key("なまもの"), key("セーブツ"))
        self.assertNotEqual(key("ひとけ"), key("ニンキ"))

    def test_punctuation_and_latin_are_ignored(self) -> None:
        self.assertEqual("あい", CHECK.pronunciation_key("ア、イ。OK"))


class ScoringTest(unittest.TestCase):
    def test_edit_distance(self) -> None:
        self.assertEqual(0, CHECK.edit_distance("あいう", "あいう"))
        self.assertEqual(1, CHECK.edit_distance("あいう", "あう"))
        self.assertEqual(3, CHECK.edit_distance("", "あいう"))

    def test_summary_is_per_category(self) -> None:
        rows = [
            {"category": "number", "edits": 1, "expected_len": 10},
            {"category": "number", "edits": 0, "expected_len": 10},
            {"category": "kanji", "edits": 0, "expected_len": 5},
        ]
        summary = CHECK.summarise(rows)
        self.assertAlmostEqual(1 / 25, summary["overall"]["cer"])
        self.assertEqual({"cer": 0.05, "bad": 1, "n": 2}, summary["categories"]["number"])

    def test_option_values_are_json(self) -> None:
        self.assertEqual(("cfg_scale_text", 4.0), CHECK.parse_option("cfg_scale_text=4.0"))
        self.assertEqual(("decode_mode", "x"), CHECK.parse_option("decode_mode=x"))


class CorpusTest(unittest.TestCase):
    def test_tracked_corpus_parses_with_a_reading_per_line(self) -> None:
        cases = CHECK.load_corpus(CORPUS_PATH)
        self.assertGreaterEqual(len(cases), 50)
        self.assertEqual(
            {"kanji", "number", "latin", "symbol", "mixed"}, {c.category for c in cases}
        )
        for case in cases:
            with self.subTest(text=case.text):
                self.assertTrue(case.expected, "every tracked line carries its reading")
                self.assertEqual(case.expected, case.expected.strip())

    def test_topic_particles_are_written_as_heard(self) -> None:
        # A text whose は is a particle must not expect ハ: the ASR writes ワ.
        for case in CHECK.load_corpus(CORPUS_PATH):
            with self.subTest(text=case.text):
                self.assertNotRegex(case.expected, "(きょう|かいぎ|きおん|かかく)は")

    def test_escaped_newline_becomes_a_line_break(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.tsv"
            path.write_text("# c\nmixed\tA\\nB\tえー\n", encoding="utf-8")
            self.assertEqual("A\nB", CHECK.load_corpus(path)[0].text)


class LegacyLexiconTest(unittest.TestCase):
    def test_reproduces_the_old_miss_next_to_japanese(self) -> None:
        reading = load_module("irodori_reading_for_check_test", READING_PATH)
        terms = {"GitHub": "ギットハブ"}
        old = (terms, CHECK.legacy_lexicon(terms))
        new = (terms, reading.compile_lexicon(terms))
        self.assertEqual("GitHubに", reading.apply_lexicon("GitHubに", old))
        self.assertEqual("ギットハブに", reading.apply_lexicon("GitHubに", new))


if __name__ == "__main__":
    unittest.main()
