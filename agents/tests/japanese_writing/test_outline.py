"""Tests for the outline mode: skeleton entries and heading statistics."""

from types import SimpleNamespace
import unittest

from japanese_writing import helpers
from japanese_writing.test_structure import BLOCK_SCOPES

outline = helpers.module("rules.outline")


class FakeTokenizer:
    """Greedy longest-match tokenizer over a small lexicon; other characters become nouns."""

    def __init__(self, lexicon):
        self.lexicon = lexicon

    def tokenize(self, text):
        tokens, cursor = [], 0
        while cursor < len(text):
            matches = [word for word in self.lexicon if text.startswith(word, cursor)]
            surface = max(matches, key=len, default=text[cursor])
            pos = self.lexicon.get(surface, ("空白",) if surface.isspace() else ("名詞", "普通名詞"))
            pos = tuple(pos) + ("*",) * (6 - len(pos))
            tokens.append(_token(surface, pos, cursor))
            cursor += len(surface)
        return tokens


def _token(surface, pos, begin):
    return SimpleNamespace(
        surface=lambda: surface, part_of_speech=lambda: pos, dictionary_form=lambda: surface,
        normalized_form=lambda: surface, reading_form=lambda: surface,
        begin=lambda: begin, end=lambda: begin + len(surface),
    )


def fake_morphology(lexicon):
    info = {"available": True, "reason": None, "packages": {}}
    return helpers.morphology.Morphology(FakeTokenizer(lexicon), info)


def run(text, morph=None):
    return helpers.run(outline, text, morph or helpers.unavailable_morphology())


def skeleton(text):
    return [(e["line"], e["kind"], e["level"], e["excerpt"]) for e in run(text)["outline"]]


class OutlineSkeletonTests(unittest.TestCase):
    def test_block_scopes(self):
        self.assertEqual(skeleton(BLOCK_SCOPES), [
            (22, "heading", 1, "まとめ API"),
            (24, "heading", 1, "タイトル API"),
            (27, "bullets", None, "(箇条書き 1 項目)"),
            (32, "lead", None, "本文 API **three**。"),
        ])

    def test_entry_shape(self):
        entries = run("## 見出し\n\n本文です。")["outline"]
        self.assertEqual(entries[0], {
            "kind": "heading", "level": 2, "line": 1, "column": 4, "excerpt": "見出し", "requires_context": True,
        })
        self.assertEqual(entries[1]["column"], 1)
        self.assertTrue(all(entry["requires_context"] for entry in entries))

    def test_setext_single_dash_and_atx_closing(self):
        self.assertEqual(skeleton("API\n-\n\n# C#\n\n## HTTP ##"), [
            (1, "heading", 2, "API"), (4, "heading", 1, "C#"), (6, "heading", 2, "HTTP"),
        ])

    def test_lead_is_first_sentence_of_each_paragraph(self):
        text = "一文目です。二文目です。\n同じ段落の二行目。\n\n保存しますか? 次へ進みます。\n\n句点のない段落"
        self.assertEqual(skeleton(text), [
            (1, "lead", None, "一文目です。"),
            (4, "lead", None, "保存しますか?"),
            (6, "lead", None, "句点のない段落"),
        ])

    def test_lead_keeps_inline_code_but_not_comments(self):
        entries = run("<!-- メモ --> `config` を読みます。続き。\n\n値は `x`")["outline"]
        found = [(e["column"], e["excerpt"]) for e in entries]
        self.assertEqual(found, [(13, "`config` を読みます。"), (1, "値は `x`")])

    def test_headings_and_lists_split_paragraphs(self):
        text = "前の段落。\n# 見出し\n後の段落。\n- 項目\n続きの行\n本文。"
        self.assertEqual(skeleton(text), [
            (1, "lead", None, "前の段落。"),
            (2, "heading", 1, "見出し"),
            (3, "lead", None, "後の段落。"),
            (4, "bullets", None, "(箇条書き 1 項目)"),
        ])

    def test_loose_list_is_one_block_and_marker_type_change_splits(self):
        text = "- 一\n\n- 二\n  続き\n\n  段落の続き\n\n1. 手順\n2. 手順\n\n本文。"
        self.assertEqual(skeleton(text), [
            (1, "bullets", None, "(箇条書き 2 項目)"),
            (8, "bullets", None, "(箇条書き 2 項目)"),
            (11, "lead", None, "本文。"),
        ])

    def test_excluded_blocks_produce_no_entries(self):
        text = "> 引用です。\n\n```\n# コード\n```\n\n    字下げのコード。\n\n| a | b |\n|---|---|\n| 表 | 値 |"
        self.assertEqual(run(text)["outline"], [])


class HeadingStatsTests(unittest.TestCase):
    def test_counts_lengths_templates_and_patterns(self):
        text = "# はじめに\n\n## 1. 背景\n\n## 【準備】\n\n## 設定とは？\n\n## 運用の工夫"
        report = run(text)
        stats = report["heading_stats"]
        self.assertEqual(stats["total_headings"], 5)
        self.assertEqual(stats["level_distribution"], {"1": 1, "2": 4})
        overall = stats["overall"]
        self.assertEqual(overall["count"], 5)
        self.assertEqual(overall["length_mean"], 4.6)
        self.assertGreater(overall["length_cv"], 0)
        self.assertEqual(overall["template_hits"], [
            {"line": 1, "text": "はじめに", "matched": "はじめに"},
            {"line": 3, "text": "1. 背景", "matched": "背景"},
        ])
        self.assertEqual(overall["structural_pattern_ratio"], 0.6)
        self.assertEqual(stats["by_level"]["1"]["length_cv"], 0.0)
        self.assertEqual(stats["by_level"]["2"]["count"], 4)

    def test_morphology_stats_are_null_and_unverified_without_sudachi(self):
        report = run("# 設定の手順\n\n本文。")
        overall = report["heading_stats"]["overall"]
        self.assertIsNone(overall["nominal_ending_ratio"])
        self.assertIsNone(overall["dominant_pos_signature_ratio"])
        expected = [{"check": "heading_morphology", "reason": "missing_or_version_mismatch"}]
        self.assertEqual(report["unverified"], expected)
        self.assertEqual(report["executed"], ["outline", "heading_stats"])
        self.assertEqual(report["status"], "partial")

    def test_no_headings_is_complete_without_sudachi(self):
        report = run("本文だけ。")
        self.assertEqual(report["heading_stats"]["total_headings"], 0)
        self.assertEqual(report["heading_stats"]["overall"]["nominal_ending_ratio"], 0.0)
        self.assertEqual(report["heading_stats"]["level_distribution"], {})
        self.assertEqual(report["unverified"], [])
        self.assertEqual(report["status"], "ok")

    def test_nominal_ending_and_signature_with_mocked_tokens(self):
        lexicon = {"の": ("助詞", "格助詞"), "を": ("助詞", "格助詞"), "する": ("動詞", "非自立可能"), "！": ("補助記号",)}
        report = run("# 設定の手順！\n\n# 導入の方法\n\n# 設定をする", fake_morphology(lexicon))
        overall = report["heading_stats"]["overall"]
        self.assertEqual(overall["nominal_ending_ratio"], round(2 / 3, 3))
        self.assertEqual(overall["dominant_pos_signature_ratio"], round(2 / 3, 3))
        self.assertIn("heading_morphology", report["executed"])
        self.assertEqual(report["unverified"], [])

    @unittest.skipUnless(helpers.MORPH_AVAILABLE, "pinned Sudachi environment not provisioned")
    def test_real_morphology(self):
        report = helpers.run(outline, "# 設定の手順\n\n# 導入の方法\n\n# 設定を変更する")
        overall = report["heading_stats"]["overall"]
        self.assertEqual(overall["nominal_ending_ratio"], round(2 / 3, 3))
        self.assertEqual(overall["dominant_pos_signature_ratio"], round(2 / 3, 3))
        self.assertEqual(report["status"], "ok")


if __name__ == "__main__":
    unittest.main()
