"""Tests for the reading-load mode: long sentences, kanji runs and parse-twice spots."""

from collections import Counter
import unittest

from japanese_writing import helpers

reading_load = helpers.module("rules.reading_load")
MORPH_AVAILABLE = helpers.MORPH_AVAILABLE

LONG = ("本研究では、地方自治体における情報システムの進捗と、各部署が抱えている運用上の課題と、"
        "住民サービスへの影響を、複数年度にわたる聞き取り調査と公開資料の詳しい比較分析によって明らかにした。")
LIST = ("調査の対象は北海道、青森県、岩手県、宮城県、秋田県の五道県で、いずれも人口減少と高齢化が"
        "同時に進み、公共交通の維持が難しくなっている地域として選んだ。")


def run(text, morph=None, **options):
    if morph is None:
        morph = helpers.unavailable_morphology()
    return helpers.run(reading_load, text, morph, **options)


def run_morph(text, **options):
    return run(text, helpers.morphology.load(True), **options)


def counts(report):
    return Counter(f["rule_id"] for f in report["findings"])


class PatternTests(unittest.TestCase):
    def test_sentence_too_long_by_genre(self):
        self.assertGreater(len(LONG) - 1, 90)
        self.assertLessEqual(len(LONG) - 1, 110)
        report = run(LONG)
        self.assertEqual(counts(report)["sentence_too_long"], 1)
        finding = report["findings"][0]
        self.assertEqual(finding["severity"], "info")
        self.assertEqual(len(finding["excerpt"]), 40)
        self.assertTrue(finding["reason"].endswith(" (readability.md B1)"))
        self.assertEqual(counts(run(LONG, genre="essay"))["sentence_too_long"], 0)

    def test_collapsed_whitespace_does_not_count(self):
        text = "詳しくは `" + "x" * 120 + "` を見る。"
        self.assertEqual(counts(run(text))["sentence_too_long"], 0)

    def test_kanji_run_without_morphology_is_flagged_unverified(self):
        report = run("システム更新計画策定支援業務を確認した。標準化推進を決めた。")
        self.assertEqual(counts(report)["kanji_run"], 1)
        self.assertEqual(report["findings"][0]["excerpt"], "更新計画策定支援業務")
        self.assertEqual(report["findings"][0]["column"], 5)
        unverified = {note["check"] for note in report["unverified"]}
        self.assertEqual(unverified, {"buried_list", "double_negative", "no_chain", "kanji_run_proper_noun_filter"})
        self.assertIn("sentence_too_long", report["executed"])
        self.assertEqual(report["status"], "partial")

    def test_prose_only(self):
        text = "- " + LONG + "\n\n# 更新計画策定支援業務\n"
        report = run(text)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["stats"]["reading-load"]["sentences"], 0)


@unittest.skipUnless(MORPH_AVAILABLE, "SudachiPy with the pinned dictionary is not installed")
class MorphologyTests(unittest.TestCase):
    def test_kanji_run_skips_proper_nouns(self):
        self.assertEqual(counts(run_morph("大阪府東大阪市役所に行った。"))["kanji_run"], 0)
        self.assertEqual(counts(run_morph("更新計画策定支援業務を確認した。"))["kanji_run"], 1)

    def test_buried_list(self):
        report = run_morph(LIST)
        found = [f for f in report["findings"] if f["rule_id"] == "buried_list"]
        self.assertEqual(len(found), 1)
        self.assertIn("5 個", found[0]["reason"])
        self.assertTrue(found[0]["excerpt"].startswith("調査の対象は北海道"))
        self.assertEqual(counts(run_morph("対象は北海道、青森県、岩手県、宮城県の四道県だ。"))["buried_list"], 0)

    def test_double_negative(self):
        report = run_morph("担当者が知らないわけではない。")
        self.assertEqual(counts(report)["double_negative"], 1)
        self.assertEqual(report["findings"][0]["excerpt"], "ないわけではない")
        for text in ("手続を始めなければならない。", "早く寝ないと眠れない。", "誰も来ない。"):
            self.assertEqual(counts(run_morph(text))["double_negative"], 0, text)

    def test_no_chain(self):
        report = run_morph("会議の資料の表紙の色を決めた。")
        self.assertEqual(counts(report)["no_chain"], 1)
        self.assertEqual(report["findings"][0]["excerpt"], "の資料の表紙の")
        self.assertEqual(counts(run_morph("会議の資料を読み、表紙の色を決めた。"))["no_chain"], 0)

    def test_stats(self):
        report = run_morph(LONG + "\n\n" + LIST)
        stats = report["stats"]["reading-load"]
        self.assertEqual(stats["sentences"], 2)
        self.assertEqual(stats["total"], len(report["findings"]))
        self.assertEqual(stats["genre"], "default")
        self.assertEqual(report["status"], "ok")


if __name__ == "__main__":
    unittest.main()
