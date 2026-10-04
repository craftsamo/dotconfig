from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# reading.py is stdlib-only by contract (the reading checker loads it outside
# Hermes), so it is loaded on its own here: a numpy import creeping in fails.
READING = Path(__file__).resolve().parents[1] / "reading.py"
SPEC = importlib.util.spec_from_file_location("irodori_tts_reading", READING)
assert SPEC and SPEC.loader
R = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = R
SPEC.loader.exec_module(R)

NO_LEXICON = ({}, None)


def lexicon(**terms: str):
    return terms, R.compile_lexicon(terms)


def prepare(text: str, lex=NO_LEXICON, frontend: bool = True) -> str:
    return R.apply_lexicon(text, lex)


class LexiconTest(unittest.TestCase):
    def test_latin_key_glued_to_japanese_matches(self) -> None:
        # Python's \b sees kana as a word character; this used to never fire.
        lex = lexicon(GitHub="ギットハブ")
        self.assertEqual("ギットハブにプッシュ", prepare("GitHubにプッシュ", lex))

    def test_latin_key_inside_a_longer_name_does_not_match(self) -> None:
        lex = lexicon(Gemini="ジェミニ")
        self.assertEqual("GeminiPro2", prepare("GeminiPro2", lex, frontend=False))

    def test_longest_key_wins(self) -> None:
        lex = lexicon(Claude="クロード", **{"Claude Code": "クロードコード"})
        self.assertEqual("クロードコードで", prepare("Claude Codeで", lex))

    def test_kanji_key_pins_a_reading(self) -> None:
        lex = lexicon(生物="なまもの")
        self.assertEqual("冷蔵庫のなまもの", prepare("冷蔵庫の生物", lex))

    def test_file_loader_ignores_anything_but_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lexicon.json"
            path.write_text('{"_comment": "x", "terms": {"API": "エーピーアイ", "": "x"}}')
            self.assertEqual({"API": "エーピーアイ"}, R.read_lexicon(path))

    def test_env_override_locates_the_lexicon(self) -> None:
        with patch.dict(os.environ, {R.LEXICON_ENV: "~/lex.json"}):
            self.assertEqual(Path("~/lex.json").expanduser(), R.lexicon_path())



if __name__ == "__main__":
    unittest.main()
