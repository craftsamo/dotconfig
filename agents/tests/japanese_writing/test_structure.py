"""Tests for the structure mode: formatting counts, proportions and density."""

import unittest

from japanese_writing import helpers

structure = helpers.module("rules.structure")

BLOCK_SCOPES = "\n".join([
    "---", "# FRONT **bold** API", "...",
    "   ````python", "# CODE **bold** API", "```", "~~~~", "```` not closing", "   `````",
    "<!--", "# COMMENT **bold** API", "-->",
    "> # QUOTE **bold** API", "lazy QUOTE **bold** API", "",
    "    # INDENT **bold** API", "",
    "Header | API", "--- | ---", "**TABLE** | API", "",
    "# まとめ API", "", "タイトル API", "===", "",
    "- リスト API **one**", "  続き API **two**", "", "  続き API", "",
    "本文 API **three**。",
])


def run(text):
    return helpers.run(structure, text, helpers.unavailable_morphology())


def counts(text):
    return run(text)["structure"]["counts"]


class StructureTests(unittest.TestCase):
    def test_block_scopes_exclude_front_matter_code_comments_quotes_and_tables(self):
        report = run(BLOCK_SCOPES)
        result = report["structure"]
        self.assertEqual(result["counts"]["headings"], 2)
        self.assertEqual(result["counts"]["summary_headings"], 1)
        self.assertEqual(result["counts"]["list_lines"], 1)
        self.assertEqual(result["counts"]["bold_spans"], 3)
        self.assertEqual(result["counts"]["bold_lines"], 3)
        self.assertEqual(result["counts"]["eligible_lines"], 6)
        self.assertEqual(
            result["proportions"]["list_lines"],
            {"numerator": 1, "denominator": 6, "denominator_name": "eligible_lines", "value": 1 / 6},
        )
        self.assertEqual(result["proportions"]["summary_headings"]["value"], 0.5)
        self.assertTrue(result["requires_context"])
        self.assertEqual(report["findings"], [])

    def test_density_uses_eligible_characters_and_lines(self):
        result = run("**強調**と本文。\n\n- 項目\n- 項目")["structure"]
        characters = result["counts"]["eligible_characters"]
        self.assertEqual(characters, len("**強調**と本文。") + 2 + 2)
        self.assertEqual(result["density"], {
            "bold_per_1000_chars": round(1 / characters * 1000, 2),
            "list_line_ratio": round(2 / 3, 3),
        })

    def test_empty_text_has_no_ratios(self):
        result = run("")["structure"]
        self.assertEqual(result["counts"]["eligible_lines"], 0)
        self.assertIsNone(result["proportions"]["bold_lines"]["value"])
        self.assertIsNone(result["proportions"]["summary_headings"]["value"])
        self.assertEqual(result["density"], {"bold_per_1000_chars": 0.0, "list_line_ratio": 0.0})

    def test_inline_exclusions_do_not_count_as_bold(self):
        text = (
            "`CODE` [API](https://URL.test/a(b)) ![IMAGE](DEST) ``X ` Y`` "
            "<https://AUTO> <!-- **x** --> **ok**"
        )
        self.assertEqual(counts(text)["bold_spans"], 1)
        self.assertEqual(counts("**`CODE`** **prose <!-- hidden --> more**")["bold_spans"], 2)

    def test_indented_code_and_comments_do_not_create_lists(self):
        result = counts("    <!--\n    - FAKE\n\nAPI\n\n- item\n\n      CODE\n\nHTTP")
        self.assertEqual(result["list_lines"], 1)
        self.assertEqual(result["eligible_lines"], 3)

    def test_reference_definitions_escapes_and_thematic_breaks(self):
        result = counts("[API][ref] API\n\n[ref]: https://HIDDEN\n\n***\n\n\\*\\*not bold\\*\\* __yes__")
        self.assertEqual(result["list_lines"], 0)
        self.assertEqual(result["bold_spans"], 1)
        self.assertEqual(result["eligible_lines"], 2)

    def test_bold_in_japanese_prose_and_list_contained_fence(self):
        text = "これは**重要**です。***one*** __two__\n\n- ````python\n  # FAKE **bold**\n  ```\n  ````\n\nAPI"
        result = counts(text)
        self.assertEqual(result["bold_spans"], 3)
        self.assertEqual(result["headings"], 0)
        self.assertEqual(result["list_lines"], 1)

    def test_setext_and_closing_hashes_are_headings(self):
        result = counts("API\n-\n\n# C#\n\n## まとめ ##")
        self.assertEqual(result["headings"], 3)
        self.assertEqual(result["summary_headings"], 1)

    def test_list_continuation_counts_as_eligible_but_not_list_line(self):
        result = counts("- 項目\n  続き\n継続行")
        self.assertEqual((result["eligible_lines"], result["list_lines"]), (3, 1))

    def test_runs_without_morphology(self):
        report = run("# 見出し\n\n本文。")
        self.assertFalse(structure.MORPHOLOGY)
        self.assertEqual(report["executed"], ["structure"])
        self.assertEqual(report["unverified"], [])
        self.assertEqual(report["status"], "ok")


if __name__ == "__main__":
    unittest.main()
