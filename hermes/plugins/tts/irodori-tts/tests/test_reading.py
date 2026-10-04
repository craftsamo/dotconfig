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


def prepare(text: str, lex=NO_LEXICON, frontend: bool = True, numerals: str = "kana") -> str:
    # Most cases pin the kana style: its output is the reading itself.
    return R.prepare_text(text, lexicon=lex, frontend=frontend, numerals=numerals)


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

    def test_lexicon_runs_before_numbers_and_symbols(self) -> None:
        lex = lexicon(Web3="ウェブスリー", **{"RFC-9110": "アールエフシー"})
        self.assertEqual("ウェブスリーの話", prepare("Web3の話", lex))
        self.assertEqual("アールエフシーを読む", prepare("RFC-9110を読む", lex))

    def test_file_loader_ignores_anything_but_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lexicon.json"
            path.write_text('{"_comment": "x", "terms": {"API": "エーピーアイ", "": "x"}}')
            self.assertEqual({"API": "エーピーアイ"}, R.read_lexicon(path))

    def test_env_override_locates_the_lexicon(self) -> None:
        with patch.dict(os.environ, {R.LEXICON_ENV: "~/lex.json"}):
            self.assertEqual(Path("~/lex.json").expanduser(), R.lexicon_path())


class CleanerEnglishTest(unittest.TestCase):
    """What hermes-agent's shared cleaner inserts, mapped back to Japanese."""

    CASES = {
        "湿度は70 percentです。": "湿度はななじゅっパーセントです。",
        "気温は25 degreesCで": "気温はにじゅうごどで",
        "気温は-5 degreesCから": "気温はマイナスごどから",
        "気温は11 to 17 degrees Celsius": "気温はじゅういちからじゅうななど",
        "今日は70 degreesFです": "今日は華氏ななじゅうどです",
        "約500 kilometresあります": "約ごひゃくキロメートルあります",
        "価格は20 dollars、": "価格はにじゅうドル、",
        "10 about 20人": "じゅうからにじゅうにん",
        "about 100人": "約ひゃくにん",
        "設定 to 保存の順": "設定、保存の順",
        "研究 and 開発": "研究アンド開発",
        "今日の予定, 10時：定例会議. 15時：資料作成.": "今日の予定、じゅうじ、定例会議。じゅうごじ、資料作成。",
        # A line that already ended in Japanese punctuation gets no second stop.
        "晴れますか？. 傘はいりますか？.": "晴れますか？傘はいりますか？",
        "これでいい？. うん、大丈夫！.": "これでいい？うん、大丈夫！",
        "晴れです。. 雨ですか？.": "晴れです。雨ですか？",
        "そうか…. ": "そうか…",
    }

    def test_inserted_english_becomes_japanese(self) -> None:
        for given, expected in self.CASES.items():
            with self.subTest(given=given):
                self.assertEqual(expected, prepare(given))

    def test_real_english_is_left_alone(self) -> None:
        for text in ("Tom and Jerry", "R and D部門", "go to bed", "about it"):
            with self.subTest(text=text):
                self.assertEqual(text, R.undo_cleaner_english(text))

    def test_against_the_real_cleaner(self) -> None:
        try:
            from tools.tts_text_normalize import prepare_spoken_text
        except ImportError:
            self.skipTest("hermes-agent checkout not on PYTHONPATH")
        # If upstream rewords an expansion, this is where it shows up.
        for raw, expected in {
            "気温は25°Cで、湿度は70%です。": "気温はにじゅうごどで、湿度はななじゅっパーセントです。",
            "価格は$20です。": "価格はにじゅうドルです。",
            "10~20人です。": "じゅうからにじゅうにんです。",
            "設定→保存": "設定、保存",
            "明日は晴れますか？\n傘はいりますか？": "明日は晴れますか？傘はいりますか？",
            "晴れです。\n雨ですか？": "晴れです。雨ですか？",
            "「行くの？」\nうん。": "「行くの？」。うん。",
        }.items():
            with self.subTest(raw=raw):
                self.assertEqual(expected, prepare(prepare_spoken_text(raw, max_chars=None)))


class SymbolTest(unittest.TestCase):
    CASES = {
        "東京〜大阪間": "東京から大阪間",
        "約3〜5分": "約さんからごふん",
        "10-20人": "じゅうからにじゅうにん",
        "03-1234-5678": "ゼロさん、いちにさんよん、ごろくななはち",
        "2026/10/03": "にせんにじゅうろくねんじゅうがつみっか",
        "2026-10-03": "にせんにじゅうろくねんじゅうがつみっか",
        "14:30に": "じゅうよじさんじゅっぷんに",
        "12:00に": "じゅうにじに",
        "¥1,500": "せんごひゃくえん",
        "次のステップ：データ": "次のステップ、データ",
    }

    def test_symbols_are_spelled_out(self) -> None:
        for given, expected in self.CASES.items():
            with self.subTest(given=given):
                self.assertEqual(expected, prepare(given))

    def test_drawn_out_vowel_keeps_its_wave(self) -> None:
        for text in ("ありがと〜！", "ヤッホ〜元気？", "すご〜い"):
            with self.subTest(text=text):
                self.assertEqual(text, prepare(text))

    def test_wave_after_kanji_opens_a_range_into_katakana(self) -> None:
        self.assertEqual("東京からニューヨーク", prepare("東京〜ニューヨーク"))

    def test_ratio_is_not_a_clock_time(self) -> None:
        self.assertEqual("ろくじゅうよん:きゅう", prepare("64:9"))


class NumberTest(unittest.TestCase):
    CASES = {
        "3月5日の10時30分": "さんがついつかのじゅうじさんじゅっぷん",
        "4月14日": "しがつじゅうよっか",
        "4月1日": "しがつついたち",
        "1日2回": "いちにちにかい",
        "3日間": "みっかかん",
        "9時4分": "くじよんぷん",
        "4人と1人と2人": "よにんとひとりとふたり",
        "1本、3本、6本": "いっぽん、さんぼん、ろっぽん",
        "8件": "はっけん",
        "1ヶ月": "いっかげつ",
        "3階": "さんがい",
        "20歳": "はたち",
        "3分の1": "さんぶんのいち",
        "1,234,567人": "ひゃくにじゅうさんまんよんせんごひゃくろくじゅうななにん",
        "1.5GB": "いちてんごギガバイト",
        "2.5倍": "にてんごばい",
        "Python 3.12": "Python さんてんいちに",
        "v2.10.1": "バージョンにてんいちゼロてんいち",
        "3時間": "さんじかん",
        "１０％": "じゅっパーセント",
        "300円": "さんびゃくえん",
        "100本": "ひゃっぽん",
        "1000本": "せんぼん",
        "100分": "ひゃっぷん",
        "300本": "さんびゃっぽん",
        "600回": "ろっぴゃっかい",
        "800個": "はっぴゃっこ",
        "1000個": "せんこ",
        "10000分": "いちまんぷん",
        "3000杯": "さんぜんばい",
        "12万円": "じゅうにまんえん",
        "1億2000万円": "いちおくにせんまんえん",
        "1.5万人": "いちまんごせんにん",
        "3兆円": "さんちょうえん",
    }

    def test_numbers_become_kana(self) -> None:
        for given, expected in self.CASES.items():
            with self.subTest(given=given):
                self.assertEqual(expected, prepare(given))

    def test_digits_inside_names_are_left_alone(self) -> None:
        for text in (
            "iPhone15", "PR#123", "H2O", "GPT-4", "x-1",
            "550e8400-e29b-41d4-a716-446655440000",
        ):
            with self.subTest(text=text):
                self.assertEqual(text, prepare(text))

    def test_overlong_scaled_number_is_left_as_written(self) -> None:
        text = "9" * 400 + "万円"
        self.assertEqual(text, prepare(text))

    def test_large_numbers(self) -> None:
        self.assertEqual("いちおくにせんまん", R.number_to_kana(120_000_000))
        self.assertEqual("いっちょう", R.number_to_kana(10**12))


class KanjiNumeralTest(unittest.TestCase):
    CASES = {
        "会議は3月5日の10時30分から": "会議は三月五日の十時三十分から",
        "1,234,567人": "百二十三万四千五百六十七人",
        "12万円": "十二万円",
        "4月1日": "四月ついたち",
        "1日2回": "一日二回",
        "70 percentです": "七十パーセントです",
        "1.5GB": "一点五ギガバイト",
        "-5 degreesC": "マイナス五度",
        "3分の1": "三分の一",
        "2026/10/03": "二千二十六年十月三日",
        "v2.10.1": "バージョンにてんいちゼロてんいち",
        "10000": "一万",
        "1000万": "千万",
    }

    def test_numbers_become_kanji_numerals(self) -> None:
        for given, expected in self.CASES.items():
            with self.subTest(given=given):
                self.assertEqual(expected, prepare(given, numerals="kanji"))

    def test_names_keep_their_digits(self) -> None:
        for text in ("iPhone15", "GPT-4", "PR#123"):
            with self.subTest(text=text):
                self.assertEqual(text, prepare(text, numerals="kanji"))


class DigitNumeralTest(unittest.TestCase):
    CASES = {
        "会議は3月5日の10時30分から": "会議は3月5日の10時30分から",
        "1,234,567人": "123万4567人",
        "70 percentです": "70パーセントです",
        "1.5GB": "1.5ギガバイト",
        "14:30に": "14時30分に",
        "v2.10.1": "バージョンにてんいちゼロてんいち",
    }

    def test_only_misread_forms_are_rewritten(self) -> None:
        for given, expected in self.CASES.items():
            with self.subTest(given=given):
                self.assertEqual(expected, prepare(given, numerals="digits"))


class ListLeftoverTest(unittest.TestCase):
    def test_colon_before_a_list_leaves_no_stray_stop(self) -> None:
        self.assertEqual("結果、成功。失敗。", R.japanese_symbols(
            R.undo_cleaner_english("結果：. 成功. 失敗.")
        ))


class ToggleTest(unittest.TestCase):
    def test_unknown_numeral_style_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            R.expand_numbers("3", "roman")

    def test_frontend_off_is_lexicon_only(self) -> None:
        lex = lexicon(API="エーピーアイ")
        self.assertEqual("APIは70 percent", prepare("APIは70 percent", NO_LEXICON, frontend=False))
        self.assertEqual("エーピーアイは3月", prepare("APIは3月", lex, frontend=False))


if __name__ == "__main__":
    unittest.main()
