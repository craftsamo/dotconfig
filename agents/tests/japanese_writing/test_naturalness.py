"""Tests for the naturalness mode: surface patterns, lanes, genres and statistics."""

from collections import Counter
import unittest

from japanese_writing import helpers

naturalness = helpers.module("rules.naturalness")
MORPH_AVAILABLE = helpers.MORPH_AVAILABLE

FILLER = "今日は川沿いを歩いた。"
VARIED = "雨。駅まで歩くと二十分ほどかかった。帰りは友人の車に乗せてもらい、途中で古い喫茶店に寄った。眠い。窓の外では、昼過ぎから降りだした雨がまだ続いていた。"


def run(text, morph=None, finish=True, **options):
    if morph is None:
        morph = helpers.unavailable_morphology()
    return helpers.run(naturalness, text, morph, finish, **options)


def counts(report):
    return Counter(f["rule_id"] for f in report["findings"])


def findings(report, rule):
    return [f for f in report["findings"] if f["rule_id"] == rule]


def stats(report):
    return report["stats"]["naturalness"]


class LaneTests(unittest.TestCase):
    def test_scored_rules_are_the_default_lane_only(self):
        self.assertEqual(len(naturalness.SCORED_RULES), 14)
        self.assertEqual(len(naturalness.EXPERIMENTAL_RULES), 9)
        self.assertFalse(naturalness.SCORED_RULES & naturalness.EXPERIMENTAL_RULES)
        self.assertIn("high_bold_density", naturalness.EXPERIMENTAL_RULES)
        self.assertNotIn("high_length_autocorrelation", naturalness.SCORED_RULES)

    def test_removed_detectors_are_absent(self):
        rules = naturalness.SCORED_RULES | naturalness.EXPERIMENTAL_RULES
        self.assertNotIn("nested_attributive", rules)
        self.assertNotIn("doubled_conjunctive_ga", rules)

    def test_unverified_without_morphology_keeps_pattern_rules(self):
        report = run("結論として、この案を採ります。")
        unverified = {note["check"] for note in report["unverified"]}
        self.assertIn("nominal_ending", unverified)
        self.assertIn("low_specificity", unverified)
        self.assertNotIn("repeated_syntax_template", unverified)
        self.assertIn("forbidden_phrase", report["executed"])
        self.assertEqual(counts(report)["forbidden_phrase"], 1)
        self.assertEqual(report["status"], "partial")
        self.assertIsNone(stats(report)["rhythm"])

    def test_experimental_morphology_rules_are_unverified_only_on_request(self):
        report = run("本文です。", experimental=True)
        unverified = {note["check"] for note in report["unverified"]}
        self.assertIn("repeated_syntax_template", unverified)
        self.assertIn("high_length_autocorrelation", unverified)


class SurfacePatternTests(unittest.TestCase):
    def test_forbidden_phrase_warn_and_weak_info(self):
        report = run("結論として、この案を採ります。\n\nさて、次の話です。")
        severities = sorted(f["severity"] for f in findings(report, "forbidden_phrase"))
        self.assertEqual(severities, ["info", "warn"])
        first = findings(report, "forbidden_phrase")[0]
        self.assertTrue(first["reason"].endswith(" (expression.md X1)"))
        self.assertEqual(first["column"], 1)

    def test_forbidden_phrase_once_per_line_and_prose_only(self):
        report = run("総じて良い。総じて安い。\n\n- 結論として、採ります。\n\n結論は明日出します。")
        self.assertEqual(counts(report)["forbidden_phrase"], 1)

    def test_translationese(self):
        self.assertEqual(counts(run("この装置は水を運搬することができる。"))["translationese"], 1)
        self.assertEqual(counts(run("この装置は水を運べる。"))["translationese"], 0)

    def test_antithesis_severity_follows_rate_and_genre(self):
        hits = "量ではなく質だ。\n値段ではなく味だ。\n速さではなく正確さだ。\n"
        self.assertEqual({f["severity"] for f in findings(run(hits), "antithesis_repetition")}, {"critical"})
        warn_text = hits + FILLER * 77
        self.assertEqual({f["severity"] for f in findings(run(warn_text), "antithesis_repetition")}, {"critical"})
        self.assertEqual({f["severity"] for f in findings(run(warn_text, genre="tech"), "antithesis_repetition")},
                         {"warn"})
        info_text = hits + FILLER * 160
        self.assertEqual({f["severity"] for f in findings(run(info_text), "antithesis_repetition")}, {"info"})
        report = run(hits)
        self.assertEqual(len(findings(report, "antithesis_repetition")), 3)
        self.assertEqual(findings(report, "antithesis_repetition")[0]["related_lines"], [1, 2, 3])

    def test_antithesis_below_three_hits_is_silent(self):
        self.assertEqual(counts(run("量ではなく質だ。\n値段ではなく味だ。"))["antithesis_repetition"], 0)

    def test_low_sentence_variance(self):
        uniform = "".join(["今日は川沿いを歩いた。", "明日は山の上に登る。", "昨日は家で本を読んだ。",
                           "朝は駅前で人と会った。", "夜は台所で鍋を煮た。"])
        self.assertEqual(counts(run(uniform))["low_sentence_variance"], 1)
        self.assertEqual(counts(run(VARIED))["low_sentence_variance"], 0)

    def test_inanimate_subject_regex(self):
        self.assertGreaterEqual(counts(run("それは大きな変化をもたらす。"))["english_syntax_inanimate_subject"], 1)
        self.assertEqual(counts(run("彼は大きな変化を起こした。"))["english_syntax_inanimate_subject"], 0)

    def test_cleft_because_is_experimental(self):
        text = "それは組織の問題である。なぜなら誰も決めないからだ。"
        self.assertEqual(counts(run(text))["english_syntax_cleft_because"], 0)
        report = run(text, experimental=True)
        self.assertEqual(counts(report)["english_syntax_cleft_because"], 1)
        self.assertEqual(findings(report, "english_syntax_cleft_because")[0]["severity"], "warn")
        self.assertEqual(counts(run("彼は来ない。なぜなら雨だからだ。", experimental=True))["english_syntax_cleft_because"], 0)


class ParagraphTests(unittest.TestCase):
    def test_paragraph_lead_conjunction_prefers_longest(self):
        text = "一方で、費用は増えた。\n\nしかし、効果も出た。\n\n結果は来月まとめる。"
        report = run(text, experimental=True)
        found = findings(report, "paragraph_lead_conjunction")
        self.assertEqual(len(found), 2)
        self.assertIn("「一方で」", found[0]["reason"])
        self.assertEqual(found[0]["related_lines"], [1, 3])
        self.assertEqual(counts(run(text))["paragraph_lead_conjunction"], 0)

    def test_paragraph_lead_conjunction_below_ratio(self):
        text = "しかし、効果は出た。\n\n費用は増えた。\n\n人も増えた。\n\n結果は来月まとめる。"
        self.assertEqual(counts(run(text, experimental=True))["paragraph_lead_conjunction"], 0)

    def test_uniform_paragraph_structure(self):
        uniform = "\n\n".join(["雨が降った。傘を差した。"] * 4)
        found = findings(run(uniform), "uniform_paragraph_structure")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["line"], 1)
        varied = "\n\n".join(["雨が降った。", "傘を差した。駅へ急いだ。", "雨。風。雷。寒い。", "帰った。"])
        self.assertEqual(counts(run(varied))["uniform_paragraph_structure"], 0)
        self.assertEqual(stats(run(varied))["paragraph_sentence_counts"], [1, 2, 4, 1])


class StructuralTests(unittest.TestCase):
    BOLD = "**一つ目**と**二つ目**と**三つ目**を見る。"

    def test_bold_density_and_code_fences(self):
        self.assertEqual(counts(run(self.BOLD, experimental=True))["high_bold_density"], 1)
        self.assertEqual(counts(run(self.BOLD))["high_bold_density"], 0)
        fenced = "```\n" + self.BOLD + "\n```\n本文です。"
        self.assertEqual(counts(run(fenced, experimental=True))["high_bold_density"], 0)

    def test_bullet_ratio(self):
        text = "\n".join(["- 項目"] * 4 + ["", "本文です。"] * 6)
        report = run(text, experimental=True)
        self.assertEqual(counts(report)["high_bullet_ratio"], 1)
        self.assertEqual(findings(report, "high_bullet_ratio")[0]["related_lines"], [1, 2, 3, 4])
        prose = "\n\n".join(["本文です。"] * 10)
        self.assertEqual(counts(run(prose, experimental=True))["high_bullet_ratio"], 0)

    def test_boilerplate_heading_and_numbered_phase_with_full_width_zero(self):
        text = "## まとめ\n\nステップ０で準備し、ステップ１で書き、ステップ２で見直す。\n\n## 手順の背景\n"
        report = run(text, experimental=True)
        self.assertEqual(counts(report)["boilerplate_heading"], 1)
        self.assertEqual(counts(report)["numbered_phase_structure"], 1)
        self.assertEqual(stats(report)["structural"]["numbered_phase_hit_count"], 3)

    def test_emoji_density(self):
        self.assertEqual(counts(run("完了です✅確認済み✅公開済み✅", experimental=True))["high_emoji_symbol_density"], 1)
        self.assertEqual(counts(run("完了です✅", experimental=True))["high_emoji_symbol_density"], 0)

    def test_business_disables_formatting_rules_even_when_experimental(self):
        text = "## まとめ\n\n" + self.BOLD + "ステップ1、ステップ2、ステップ3。完了✅確認✅公開✅"
        report = run(text, experimental=True, genre="business")
        found = counts(report)
        for rule in ("high_bold_density", "boilerplate_heading", "numbered_phase_structure"):
            self.assertEqual(found[rule], 0, rule)
        self.assertEqual(found["high_emoji_symbol_density"], 1)
        self.assertNotIn("high_bold_density", report["executed"])


@unittest.skipUnless(MORPH_AVAILABLE, "SudachiPy with the pinned dictionary is not installed")
class MorphologyTests(unittest.TestCase):
    def run_morph(self, text, **options):
        return run(text, helpers.morphology.load(True), **options)

    def test_nominal_ending_absence_by_genre(self):
        sentence = "彼は朝早くから駅まで歩いて行った。"
        long_text = "\n\n".join([sentence * 4] * 35)
        report = self.run_morph(long_text)
        self.assertEqual(counts(report)["nominal_ending"], 1)
        self.assertEqual(findings(report, "nominal_ending")[0]["line"], 69)
        mid_text = "\n\n".join([sentence * 4] * 25)
        self.assertEqual(counts(self.run_morph(mid_text))["nominal_ending"], 0)
        self.assertEqual(counts(self.run_morph(mid_text, genre="essay"))["nominal_ending"], 1)
        with_noun = long_text + "\n\n最後は雨。"
        self.assertEqual(counts(self.run_morph(with_noun))["nominal_ending"], 0)

    def test_translationese_morph(self):
        report = self.run_morph("私たちは問題を解決することができる。")
        self.assertEqual(counts(report)["translationese_morph"], 1)
        self.assertEqual(findings(report, "translationese_morph")[0]["excerpt"], "問題を解決することができる")
        self.assertEqual(counts(self.run_morph("私たちは問題を解決できる。"))["translationese_morph"], 0)

    def test_inanimate_subject_morph_includes_noun_plus_suru(self):
        self.assertEqual(counts(self.run_morph("この事実は大きな変化をもたらす。"))["inanimate_subject_morph"], 1)
        self.assertEqual(counts(self.run_morph("それは作業時間の短縮を意味する。"))["inanimate_subject_morph"], 1)
        self.assertEqual(counts(self.run_morph("これは体制の課題を浮き彫りにする。"))["inanimate_subject_morph"], 1)
        self.assertEqual(counts(self.run_morph("彼は大きな変化をもたらす。"))["inanimate_subject_morph"], 0)

    def test_low_burstiness(self):
        uniform = "".join(["今日は川沿いを歩いた。", "明日は山の上に登る。", "昨日は家で本を読んだ。",
                           "朝は駅前で人と会った。", "夜は台所で鍋を煮た。", "昼は公園で弁当を食べた。"])
        report = self.run_morph(uniform)
        self.assertEqual(counts(report)["low_burstiness"], 1)
        self.assertLess(stats(report)["rhythm"]["burstiness"], -0.24)
        self.assertEqual(counts(self.run_morph(VARIED + "寒い。"))["low_burstiness"], 0)

    def test_high_length_autocorrelation_is_experimental(self):
        text = "".join(["雨。", "冷たい風。", "駅まで歩いた。", "家に帰って本を読んだ。",
                        "昼過ぎから降りだした雨が夜になっても続いていた。",
                        "古い喫茶店の窓から、濡れた石畳を行き交う人の傘をしばらく眺めていた。",
                        "昼過ぎから降りだした雨が夜まで続いていた。",
                        "家に帰って本を読んだ。", "駅まで歩いた。", "霧。"])
        report = self.run_morph(text, experimental=True)
        self.assertGreater(stats(report)["rhythm"]["length_autocorrelation_lag1"], 0.6)
        self.assertEqual(counts(report)["high_length_autocorrelation"], 1)
        self.assertEqual(counts(self.run_morph(text))["high_length_autocorrelation"], 0)

    def test_repeated_sentence_lead_and_syntax_template(self):
        verbs = ["駅へ行った。", "本を読んだ。", "窓を開けた。", "水を飲んだ。", "空を見た。", "手紙を書いた。"]
        text = "".join("私は朝に" + verb for verb in verbs)
        report = self.run_morph(text, experimental=True)
        self.assertEqual(counts(report)["repeated_sentence_lead"], 6)
        self.assertEqual(counts(report)["repeated_syntax_template"], 6)
        self.assertEqual(counts(self.run_morph(text, genre="tech"))["repeated_sentence_lead"], 0)
        self.assertEqual(counts(self.run_morph(text))["repeated_syntax_template"], 0)

    def test_lexical_diversity(self):
        repetitive = "\n\n".join(["私はその日も駅まで歩いた。私はその日も本を読んだ。"] * 180)
        report = self.run_morph(repetitive, finish=False)
        self.assertEqual(counts(report)["low_lexical_diversity_ttr"], 1)
        self.assertEqual(counts(report)["low_lexical_diversity_mtld"], 1)
        short = self.run_morph("\n\n".join(["私はその日も駅まで歩いた。"] * 20))
        self.assertTrue(stats(short)["lexical_diversity"]["skipped_too_short"])
        self.assertEqual(counts(short)["low_lexical_diversity_ttr"], 0)

    def test_low_specificity(self):
        vague = ("組織の問題と課題の背景には、価値の変化や状況の変化といった要素があり、その本質や意義を"
                 "考える視点と姿勢が重要性を持つ。こうした傾向と特徴の側面には、概念の存在と可能性の問題がある。")
        report = self.run_morph(vague)
        self.assertEqual(counts(report)["low_specificity"], 1)
        concrete = ("2024年4月に札幌の田中さんが3人のチームで実験し、たとえば12回の試行で9回成功した。"
                    "翌月は東京の佐藤さんが同じ装置で5回試し、4回成功したと報告した。結果は社内の会議で共有された。")
        self.assertEqual(counts(self.run_morph(concrete))["low_specificity"], 0)
        self.assertEqual(stats(self.run_morph(concrete))["low_specificity"]["paragraphs_evaluated"], 1)


if __name__ == "__main__":
    unittest.main()
