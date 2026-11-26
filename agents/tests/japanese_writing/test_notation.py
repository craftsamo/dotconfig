"""Tests for the notation mode (house notation rules, regex only)."""

import time
import unittest

from japanese_writing import helpers

notation = helpers.module("rules.notation")
catalog = helpers.module("catalog")

RULE_IDS = [rule["id"] for rule in catalog.load("notation")["rules"]]

POSITIVE = {
    "space_ja_alnum": "Gitの履歴を見る。",
    "space_between_fullwidth": "設定 を変更する。",
    "space_around_ja_punct": "設定を変更して 、閉じる。",
    "space_inside_brackets": "「 test 」と入力する。",
    "space_before_mark": "フォント :",
    "space_after_mark": "保存しますか?Excel で開く。",
    "paren_outer_space": "機能(ベータ) を使う。",
    "paren_style_mix": "機能（ベータ）と設定 (既定) を使う。",
    "space_around_slash": "オン / オフを切り替える。",
    "percent_degree_space": "角度は 45 ° です。",
    "number_unit_space": "重さは 3kg です。",
    "fullwidth_alnum": "ＯＳ を更新する。",
    "halfwidth_katakana": "ﾌｧｲﾙを開く。",
    "fullwidth_comma_period": "設定を開き，閉じる．",
    "fullwidth_symbol": "A＆B を比べる。",
    "ideographic_space": "設定を開く。\u3000次へ進む。",
    "dash": "結論—まず試す。",
    "straight_double_quote": "これを \"リボン\" と呼ぶ。",
    "long_vowel": "ユーザが使う。",
    "katakana_variant": "インタフェースを使う。",
    "ka_counter_katakana": "3ヶ月かかる。",
    "kanji_numeral_idiom": "もう1度試す。",
    "kana_preferred": "確認して下さい。",
    "formal_wording": "変更が可能です。",
    "superlative_claim": "完璧なソリューションです。",
    "redundant_each": "各ファイルごとに名前を変える。",
    "ambiguous_tekitou": "適当なオプションを選ぶ。",
    "intensifier": "非常に便利です。",
    "yoroshii_question": "続けてもよろしいですか?",
    "excessive_honorific": "使用なさらないでください。",
    "wagasha": "我が社の製品です。",
    "noun_wo_jikkou": "インストールを実行します。",
    "tachiageru": "PC を立ち上げる。",
    "inclusive_term": "ブラックリストに追加する。",
    "heading_polite_ending": "## 設定を変更します",
}

NEGATIVE = {
    "space_ja_alnum": "Git の履歴を見る。10月8日に第4版の7柱を1つ選ぶ。",
    "space_between_fullwidth": "ダイアログボックスを開く。",
    "space_around_ja_punct": "設定を変更して、Windows を閉じる。",
    "space_inside_brackets": "「test」と入力し、値は ( ) に入れる。",
    "space_before_mark": "フォント:",
    "space_after_mark": "保存しますか? Excel で開く。保存しますか？ 次へ進む。警告!(W)",
    "paren_outer_space": "機能（ベータ）を使う。",
    "paren_style_mix": "機能（ベータ）と設定（既定）を使う。保存(S) を押す。",
    "space_around_slash": "オン/オフを切り替える。3/14 に始める。",
    "percent_degree_space": "角度は 45° です。",
    "number_unit_space": "重さは 3 kg です。35mm レンズで撮る。",
    "fullwidth_alnum": "OS を更新する。",
    "halfwidth_katakana": "ファイルを開く。",
    "fullwidth_comma_period": "設定を開き、閉じる。",
    "fullwidth_symbol": "A&B を比べる。",
    "ideographic_space": "\u3000段落を字下げする。",
    "dash": "- [x] モジュールを追加する — #63\n\nA — B は英語の例だ。",
    "straight_double_quote": "これを “リボン” と呼ぶ。\"ribbon\" とも書く。",
    "long_vowel": "ユーザーとユーザビリティとプロセッサとメモリとサーバーレス。",
    "katakana_variant": "インターフェイスを使う。",
    "ka_counter_katakana": "3か月かかる。8コアで動く。",
    "kanji_numeral_idiom": "もう一度試す。",
    "kana_preferred": "確認してください。",
    "formal_wording": "変更できます。最新版の使用を推奨します。",
    "superlative_claim": "お勧めのソリューションです。",
    "redundant_each": "各ファイルの名前を変える。",
    "ambiguous_tekitou": "適切なオプションを選ぶ。",
    "intensifier": "便利です。大変な作業だ。",
    "yoroshii_question": "続けますか?",
    "excessive_honorific": "使用しないでください。",
    "wagasha": "当社の製品です。",
    "noun_wo_jikkou": "インストールします。",
    "tachiageru": "PC を起動する。",
    "inclusive_term": "拒否リストに追加する。",
    "heading_polite_ending": "## 設定の変更\n\n## 変更しますか?",
}

CLEAN_PROSE = (
    "`git status` を実行すると、作業ツリーの状態（変更ファイル・未追跡ファイル）が表示されます。"
    "容量は 100 MB、使用率は 50% です。10月8日〜30日の第3章を参照してください…"
)


def report(text):
    return helpers.run(notation, text)


def findings(text, rule_id=None):
    return [f for f in report(text)["findings"] if rule_id is None or f["rule_id"] == rule_id]


def rules(text):
    return {f["rule_id"] for f in findings(text)}


class RuleTableTests(unittest.TestCase):
    def test_every_rule_has_cases(self):
        self.assertEqual(set(POSITIVE), set(RULE_IDS))
        self.assertEqual(set(NEGATIVE), set(RULE_IDS))

    def test_positive_cases(self):
        for rule_id, text in POSITIVE.items():
            with self.subTest(rule_id):
                self.assertIn(rule_id, rules(text))

    def test_negative_cases(self):
        for rule_id, text in NEGATIVE.items():
            with self.subTest(rule_id):
                self.assertNotIn(rule_id, rules(text))

    def test_clean_house_paragraph(self):
        self.assertEqual(findings(CLEAN_PROSE), [])


class Assertions:
    def assertFlags(self, text, rule_id):
        self.assertIn(rule_id, rules(text), text)

    def assertClean(self, text):
        self.assertEqual(findings(text), [], text)


class SpecCaseTests(Assertions, unittest.TestCase):
    def test_inline_code_adjacency(self):
        self.assertFlags("`git status`を実行する。", "space_ja_alnum")
        self.assertFlags("コマンド`git status` を実行する。", "space_ja_alnum")
        self.assertClean("`git status` を実行する。")

    def test_code_adjacency_reported_on_the_japanese_side(self):
        (hit,) = findings("`git status`を実行する。", "space_ja_alnum")
        self.assertEqual(hit["column"], len("`git status`") + 1)

    def test_digits_with_japanese_counters_and_dates_are_not_flagged(self):
        self.assertClean("2026年10月8日に第4版の7柱から1枚を選ぶ。1分以上待つ。")
        self.assertClean("範囲は1〜2文、0〜99です。")
        self.assertClean("タスクバーとダイアログボックスとインラインコードを確認する。")

    def test_paren_consistency(self):
        self.assertClean("機能（ベータ）と設定（既定）を確認する。")
        self.assertClean("機能 (ベータ) と設定 (既定) を確認する。")
        self.assertFlags("機能（ベータ）と設定 (既定) を確認する。", "paren_style_mix")

    def test_link_text_checked_destination_masked(self):
        self.assertFlags("[Gitの使い方](https://example.com) を読む。", "space_ja_alnum")
        self.assertClean("[使い方](https://example.com/a(b)c) を読む。")

    def test_heading_closing_hashes(self):
        (hit,) = findings("## 設定を変更します ##", "heading_polite_ending")
        self.assertEqual(hit["column"], len("## 設定を変更し") + 1)

    def test_task_list_and_pr_reference_dash(self):
        self.assertClean("- [ ] 項目")
        self.assertClean("- [x] 転送モジュールを追加する — #63")

    def test_urls_masked(self):
        self.assertClean("詳細は <https://example.com/a?b=1&c=2> を参照してください。")
        self.assertClean("詳細は https://example.com/a?b=1 を参照してください。")

    def test_percent_and_degree(self):
        self.assertClean("使用率は 50% です。室温は 20℃ です。")
        self.assertFlags("使用率は 50 % です。", "percent_degree_space")

    def test_number_unit(self):
        self.assertFlags("容量は 100MB です。", "number_unit_space")
        self.assertClean("容量は 100 MB です。")

    def test_access_key_and_ui_brackets(self):
        self.assertClean("保存(S) をクリックします。[新規] をクリックします。")

    def test_question_mark_spacing(self):
        self.assertClean("更新しますか? 次へ進みます。")
        self.assertClean("更新しますか？ 次へ進みます。")
        self.assertFlags("更新しますか ?", "space_before_mark")


class BehaviorTests(Assertions, unittest.TestCase):
    def test_executed_and_stats(self):
        result = report(CLEAN_PROSE)
        self.assertTrue(set(RULE_IDS) <= set(result["executed"]))
        stats = result["stats"]["notation"]
        self.assertEqual(stats["rules_checked"], len(RULE_IDS))
        self.assertEqual(sum(stats["by_rule"].values()), 0)

    def test_suggestion_and_anchor_in_reason(self):
        (hit,) = findings("容量は 100MB です。", "number_unit_space")
        self.assertIn("100 MB", hit["reason"])
        self.assertTrue(hit["reason"].endswith(" (notation.md N2)"))
        self.assertEqual(hit["severity"], "info")

    def test_ka_counter_suggestion_preserves_counter(self):
        first, second = findings("3ヶ月と2ヶ所を見る。", "ka_counter_katakana")
        self.assertIn("3か月", first["reason"])
        self.assertIn("2か所", second["reason"])

    def test_no_duplicate_positions(self):
        text = "3ヶ月と5コと100MBと“ テスト ”。"
        keys = [(f["rule_id"], f["line"], f["column"]) for f in findings(text)]
        self.assertEqual(len(keys), len(set(keys)))

    def test_tables_and_code_blocks_skipped(self):
        self.assertClean("| 列 | 値 |\n| --- | --- |\n| Gitの履歴 | 100MB |")
        self.assertClean("```\nGitの履歴（100MB）\n```")

    def test_long_vowel_never_inside_longer_katakana_run(self):
        self.assertNotIn("long_vowel", rules("ユーザビリティとサーバサイドとメモリーカード。"))

    def test_long_vowel_suggestions(self):
        reasons = [f["reason"] for f in findings("コンピュータとメモリー。", "long_vowel")]
        self.assertEqual(len(reasons), 2)
        self.assertIn("コンピューター", reasons[0])
        self.assertIn("「メモリ」", reasons[1])

    def test_performance_on_large_document(self):
        paragraph = (
            "Gitの履歴を確認して下さい。容量は100MBで、使用率は 50 % です。"
            "ユーザがフォルダを開き、[新規] をクリックします。更新しますか?次へ\n\n"
        )
        text = paragraph * (131072 // len(paragraph.encode("utf-8")))
        start = time.perf_counter()
        report(text)
        self.assertLess(time.perf_counter() - start, 1.0)


if __name__ == "__main__":
    unittest.main()
