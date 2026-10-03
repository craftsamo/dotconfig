"""Tests for the terms mode: term inventory, counts, gloss hints and context."""

import unittest

from japanese_writing import helpers
from japanese_writing.test_outline import fake_morphology
from japanese_writing.test_structure import BLOCK_SCOPES

terms = helpers.module("rules.terms")


def run(text, morph=None):
    return helpers.run(terms, text, morph or helpers.unavailable_morphology())


def inventory(text, morph=None):
    return [(t["term"], t["kind"], t["line"], t["count"]) for t in run(text, morph)["terms"]]


def find(report, term):
    return next(t for t in report["terms"] if t["term"] == term)


class TermScopeTests(unittest.TestCase):
    def test_block_scopes(self):
        report = run(BLOCK_SCOPES)
        names = [t["term"] for t in report["terms"]]
        self.assertEqual(names.count("API"), 1)
        for hidden in ("FRONT", "CODE", "COMMENT", "QUOTE", "INDENT", "TABLE"):
            self.assertNotIn(hidden, names)
        api = find(report, "API")
        self.assertEqual((api["line"], api["column"], api["count"], api["kind"]), (22, 7, 6, "acronym"))

    def test_inline_exclusions_and_original_columns(self):
        text = (
            "`CODE` [API](https://URL.test/a(b)) ![IMAGE](DEST) ``X ` Y`` "
            "<https://AUTO> API <!-- HIDDEN --> **ok**"
        )
        report = run(text)
        self.assertEqual([(t["term"], t["count"]) for t in report["terms"]], [("API", 2)])
        self.assertEqual(report["terms"][0]["column"], text.index("API") + 1)

    def test_comments_do_not_leak_fences_and_code_does_not_open_comments(self):
        self.assertEqual(
            [(t, line) for t, _, line, _ in inventory("<!--\n````\n-->\nAPI\n\n```\n<!--\n```\nHTTP")],
            [("API", 4), ("HTTP", 9)],
        )
        self.assertEqual([t[0] for t in inventory("`<!--` API\nHTTP")], ["API", "HTTP"])
        text = "    <!--\n    - FAKE\n\nAPI\n\n- item\n\n      CODE\n\nHTTP"
        self.assertEqual([t[0] for t in inventory(text)], ["API", "HTTP"])

    def test_reference_links_images_and_escapes(self):
        text = "[API][ref] ![IMAGE][ref] API\n\n[ref]: https://HIDDEN\n\n***\n\n\\*\\*not bold\\*\\* __yes__"
        self.assertEqual([(t[0], t[3]) for t in inventory(text)], [("API", 2)])

    def test_only_physical_newlines_advance_line_numbers(self):
        for separator in ("\u2028", "\u2029", "\f", "\v", "\x85"):
            for newline in ("\n", "\r\n", "\r"):
                with self.subTest(separator=repr(separator), newline=repr(newline)):
                    text = "あ" * 5 + separator + "あ" * 5 + "。" + newline + "API"
                    self.assertEqual(run(text)["terms"][0]["line"], 2)

    def test_count_is_non_overlapping_and_ignores_code(self):
        text = (
            "APIを使う。`API` は数えない。\n\n- API の一覧\n\n```\nAPI\n```\n\n"
            "| API | x |\n|---|---|\n| API | y |"
        )
        self.assertEqual(inventory(text), [("API", "acronym", 1, 2)])
        self.assertEqual(find(run("データデータ。データ"), "データデータ")["count"], 1)

    def test_sorted_by_first_occurrence(self):
        text = "# HTTP の話\n\nRESTとAPI。\n\n- JSON"
        found = [(t[0], t[2]) for t in inventory(text)]
        self.assertEqual(found, [("HTTP", 1), ("REST", 3), ("API", 3), ("JSON", 5)])


class TermFallbackTests(unittest.TestCase):
    def test_katakana_regex_without_sudachi(self):
        report = run("コンピューターとデータとペン。東京")
        found = [(t["term"], t["kind"]) for t in report["terms"]]
        self.assertEqual(found, [("コンピューター", "katakana"), ("データ", "katakana")])
        self.assertEqual(report["executed"], ["term_inventory"])
        expected = [{"check": "proper_noun_inventory", "reason": "missing_or_version_mismatch"}]
        self.assertEqual(report["unverified"], expected)
        self.assertEqual(report["status"], "partial")

    def test_long_term_is_clipped(self):
        report = run("カ" * 300)
        self.assertEqual(len(report["terms"][0]["term"]), 240)
        self.assertEqual(report["truncation"]["term_clipped"], 1)
        self.assertEqual(report["truncation"]["excerpt_clipped"], 1)
        self.assertTrue(report["truncation"]["applied"])


class GlossAndContextTests(unittest.TestCase):
    def test_parenthesis_right_after_term(self):
        text = "API（Application Programming Interface）を使う。\n\nHTTP (HyperText) も使う。\n\nJSON を使う。"
        report = run(text)
        self.assertTrue(find(report, "API")["has_gloss_hint"])
        self.assertTrue(find(report, "HTTP")["has_gloss_hint"])
        self.assertFalse(find(report, "JSON")["has_gloss_hint"])

    def test_link_destination_is_not_a_gloss(self):
        self.assertFalse(find(run("[API](https://example.test) を使う。"), "API")["has_gloss_hint"])

    def test_markers_on_same_or_adjacent_candidate_rows(self):
        self.assertTrue(find(run("RESTとは設計の考え方だ。"), "REST")["has_gloss_hint"])
        self.assertTrue(find(run("HTTPを使う。\nこれを通信規約と呼ぶ。"), "HTTP")["has_gloss_hint"])
        self.assertTrue(find(run("前置き、つまり要約。\nJSONを返す。"), "JSON")["has_gloss_hint"])
        self.assertFalse(find(run("HTTPを使う。\n\nこれを通信規約と呼ぶ。"), "HTTP")["has_gloss_hint"])
        self.assertFalse(find(run("HTTPを使う。\n> これを通信規約と呼ぶ。"), "HTTP")["has_gloss_hint"])
        far = "API" + "あ" * 90 + "という。"
        self.assertFalse(find(run(far), "API")["has_gloss_hint"])

    def test_context_is_raw_window_around_first_occurrence(self):
        text = "い" * 100 + "`x` API を使う" + "う" * 100
        context = find(run(text), "API")["context"]
        start = text.index("API")
        self.assertEqual(context, text[start - 80:start + 3 + 80])
        self.assertIn("`x`", context)
        self.assertEqual(find(run("  前置き API。  "), "API")["context"], "前置き API。")


class TermMorphologyTests(unittest.TestCase):
    LEXICON = {
        "東京": ("名詞", "固有名詞"), "で": ("助詞", "格助詞"), "Python": ("名詞", "普通名詞"),
        "と": ("助詞", "格助詞"), "サーバ": ("名詞", "普通名詞"), "ー": ("名詞", "普通名詞"),
        "ペン": ("名詞", "固有名詞"), "X": ("名詞", "普通名詞"),
    }

    def test_walk_registers_katakana_runs_and_proper_nouns(self):
        report = run("東京でPythonとサーバーとペンとX。", fake_morphology(self.LEXICON))
        self.assertEqual(
            [(t["term"], t["kind"], t["column"]) for t in report["terms"]],
            [("東京", "proper_noun", 1), ("Python", "proper_noun", 4), ("サーバー", "katakana", 11)],
        )
        self.assertEqual(report["executed"], ["term_inventory", "proper_noun_inventory"])
        self.assertEqual(report["status"], "ok")

    def test_oversized_segment_is_unverified_and_falls_back(self):
        text = "あ" * 14000 + "コンピューター\nHTTP"
        report = run(text, fake_morphology(self.LEXICON))
        note = {"check": "proper_noun_inventory", "reason": "segment_exceeds_40000_utf8_bytes", "line": 1}
        self.assertIn(note, report["unverified"])
        self.assertEqual([t["term"] for t in report["terms"]], ["コンピューター", "HTTP"])
        self.assertEqual(report["status"], "partial")

    @unittest.skipUnless(helpers.MORPH_AVAILABLE, "pinned Sudachi environment not provisioned")
    def test_real_morphology(self):
        report = helpers.run(terms, "# 東京の会議\n\nGitHubとPythonでコンピューターを使う。APIも使う。")
        found = {t["term"]: t["kind"] for t in report["terms"]}
        self.assertEqual(found["東京"], "proper_noun")
        self.assertEqual(found["GitHub"], "proper_noun")
        self.assertEqual(found["Python"], "proper_noun")
        self.assertEqual(found["コンピューター"], "katakana")
        self.assertEqual(found["API"], "acronym")
        self.assertEqual(find(report, "東京")["column"], 3)
        self.assertEqual(report["unverified"], [])
        self.assertEqual(report["status"], "ok")


if __name__ == "__main__":
    unittest.main()
