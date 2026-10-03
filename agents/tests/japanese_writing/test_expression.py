"""Tests for the expression mode: formatting density, stock phrases, endings and stance."""

import unittest

from japanese_writing import helpers

expression = helpers.module("rules.expression")

FILLER = "この章では設定ファイルの書き方を順番に説明している。"


def run(text, stance=None):
    return helpers.run(expression, text, helpers.unavailable_morphology(), stance=stance)


def rules(report, rule_id=None):
    found = [(f["rule_id"], f["line"], f["excerpt"]) for f in report["findings"]]
    return [item for item in found if rule_id is None or item[0] == rule_id]


def prose(lines, per_line=5):
    return "\n\n".join(FILLER * per_line for _ in range(lines))


class DensityTests(unittest.TestCase):
    def test_excess_bold_fires_above_three_per_thousand(self):
        text = prose(3) + "\n\n**要点**と**注意**を確認している。\n"
        report = run(text)
        self.assertEqual(len(rules(report, "excess_bold")), 1)
        self.assertGreater(report["stats"]["expression"]["bold_per_1000"], 3.0)
        self.assertIn("目安は 1000 字あたり 3 以下", report["findings"][0]["reason"])

    def test_excess_bold_quiet_at_low_density_or_short_text(self):
        self.assertEqual(rules(run(prose(3) + "\n\n**要点**を確認している。\n"), "excess_bold"), [])
        self.assertEqual(rules(run("**短い**文に**太字**が**多い**。\n"), "excess_bold"), [])

    def test_excess_list(self):
        text = prose(3) + "\n\n- 一つ目の項目\n- 二つ目の項目\n"
        self.assertEqual(len(rules(run(text), "excess_list")), 1)
        quiet = prose(4) + "\n\n- 一つ目の項目\n"
        self.assertEqual(rules(run(quiet), "excess_list"), [])

    def test_stats(self):
        stats = run(prose(1))["stats"]["expression"]
        self.assertEqual(set(stats), {"char_count", "list_ratio", "bold_per_1000", "sentences"})
        self.assertEqual(stats["sentences"], 5)


class EndingTests(unittest.TestCase):
    def test_three_same_endings(self):
        report = run("今日は晴れです。明日は雨です。週末は曇りです。\n")
        found = rules(report, "sentence_end_repetition")
        self.assertEqual(found, [("sentence_end_repetition", 1, "週末は曇りです")])

    def test_runs_across_list_items(self):
        report = run("設定を保存します。\n\n- 画面を閉じます\n- 端末を再起動します\n")
        self.assertEqual(len(rules(report, "sentence_end_repetition")), 1)

    def test_varied_endings_are_quiet(self):
        report = run("今日は晴れです。雨が降ります。曇りです。\n")
        self.assertEqual(rules(report, "sentence_end_repetition"), [])

    def test_style_mix(self):
        text = "設定を開きます。項目を選びます。保存します。結果を確かめる。値が変わった。\n"
        found = rules(run(text), "ending_style_mix")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][2], "結果を確かめる")

    def test_single_minority_sentence_is_quiet(self):
        text = "設定を開きます。項目を選びます。保存します。終了します。値が変わった。\n"
        self.assertEqual(rules(run(text), "ending_style_mix"), [])


class StanceTests(unittest.TestCase):
    def test_advice_flags_action_but_not_passive(self):
        report = run("画面を開きましょう。ボタンを押します。設定は記録されます。\n", stance="advice")
        self.assertEqual([f[2] for f in rules(report, "stance_ending_conflict")], ["ボタンを押します"])

    def test_rule_flags_recommendation_and_evaluation(self):
        report = run("毎日保存します。週に一度は見直しましょう。手順の順番が大切です。\n", stance="rule")
        excerpts = [f[2] for f in rules(report, "stance_ending_conflict")]
        self.assertEqual(excerpts, ["週に一度は見直しましょう", "手順の順番が大切です"])

    def test_explanation_spares_the_closing_ask(self):
        closing = run("結果は三件でした。詳細は付録を見てください。\n", stance="explanation")
        self.assertEqual(rules(closing, "stance_ending_conflict"), [])
        middle = run("結果は三件でした。付録を見てください。差は小さいです。\n", stance="explanation")
        self.assertEqual(len(rules(middle, "stance_ending_conflict")), 1)

    def test_no_stance_no_check(self):
        report = run("画面を開きましょう。ボタンを押します。\n")
        self.assertEqual(rules(report, "stance_ending_conflict"), [])
        self.assertNotIn("stance_ending_conflict", report["executed"])

    def test_ending_kinds(self):
        kinds = {
            "削除されます。": "state", "ボタンを押します。": "action", "動いています。": "progressive",
            "見てください。": "request", "必要です。": "evaluation", "必要があります。": "obligation",
            "設定ファイル": "nominal", "書ける。": "plain", "(注)。": "",
        }
        for text, kind in kinds.items():
            self.assertEqual(expression.ending_kind(text), kind, text)


class BoldTests(unittest.TestCase):
    def suggestion(self, line):
        found = rules(run(line + "\n"), "bold_not_rendered")
        return found[0][2] if found else None

    def test_bracket_fix(self):
        self.assertEqual(self.suggestion("次に**「文書の立場」**を決めます。"),
                         "次に**「文書の立場」**を決めま → 次に「**文書の立場**」を決めま")

    def test_punctuation_fix(self):
        self.assertTrue(self.suggestion("これは**必須です。**詳しくは後述します。").endswith("これは**必須です**。詳しくは"))

    def test_space_fixes(self):
        self.assertTrue(self.suggestion("立場は**「勧め」か「決まり」**で決めます。")
                        .endswith("立場は **「勧め」か「決まり」** で決めま"))
        self.assertTrue(self.suggestion("これは** 太字 **です").endswith("これは**太字**です"))
        self.assertTrue(self.suggestion("a**`code`**b").endswith("a **`code`** b"))

    def test_severity_and_quiet_cases(self):
        report = run("次に**「立場」**を決めます。\n")
        self.assertEqual(report["findings"][0]["severity"], "critical")
        self.assertIn("notation.md N11", report["findings"][0]["reason"])
        self.assertIsNone(self.suggestion("これは**大事**な点です。"))
        self.assertIsNone(self.suggestion("コード `**「x」**` は対象外です。"))


class VocabularyTests(unittest.TestCase):
    def test_emoji_real_only(self):
        self.assertEqual(len(rules(run("完了しました🎉\n"), "emoji")), 1)
        self.assertEqual(len(rules(run("## 確認 ✅\n"), "emoji")), 1)
        self.assertEqual(rules(run("評価は☆★で、♪や✓✔も使う。\n"), "emoji"), [])

    def test_slop_reports_longest_match(self):
        found = rules(run("チームの肌感覚を大切にする。\n"), "slop_vocabulary")
        self.assertEqual([f[2] for f in found], ["肌感覚"])
        self.assertEqual(rules(run("チームの意見を大切にする。\n"), "slop_vocabulary"), [])

    def test_metaphor_dedup(self):
        found = rules(run("データが静かに壊れる。処理が静かに失敗する。\n"), "metaphor_verb")
        self.assertEqual([f[2] for f in found], ["データが静かに壊れ", "静かに失敗"])
        self.assertEqual(len(rules(run("データが静かに壊れる。\n"), "metaphor_verb")), 1)
        self.assertEqual(rules(run("処理が失敗したらログを確かめる。\n"), "metaphor_verb"), [])

    def test_meta_filler_positions(self):
        self.assertEqual(len(rules(run("- 重要なのは、手順を守ることです。\n"), "meta_filler")), 1)
        self.assertEqual(len(rules(run("前の文です。結論から言うと、不要です。\n"), "meta_filler")), 1)
        self.assertEqual(len(rules(run("これは設計の失敗に他なりません。\n"), "meta_filler")), 1)
        self.assertEqual(len(rules(run("ぜひ試してみてください。\n"), "meta_filler")), 1)
        self.assertEqual(rules(run("ここが重要なのは明らかだ。\n"), "meta_filler"), [])

    def test_dropped_rules_are_absent(self):
        text = "## 概要（詳細）\n\nGit の設定を変える。\n\n- 手順:\n- 準備：\n\nAではなくBを選ぶ。\n"
        report = run(text)
        dropped = {"unnatural_halfwidth_space", "trailing_colon", "redundant_bracket", "negative_parallelism"}
        self.assertFalse(dropped & {f["rule_id"] for f in report["findings"]})
        self.assertFalse(dropped & set(report["executed"]))
        self.assertEqual(rules(report, "slop_vocabulary") + rules(report, "meta_filler"), [])

    def test_code_is_ignored(self):
        report = run("```\n肌感覚 🎉 **「x」**\n```\n\n`肌感覚` を検索する。\n")
        self.assertEqual(rules(report), [])


if __name__ == "__main__":
    unittest.main()
