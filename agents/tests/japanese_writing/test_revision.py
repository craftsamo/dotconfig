"""Tests for the revision mode: original → rewrite comparison."""

import unittest

from japanese_writing import helpers

revision = helpers.module("rules.revision")


def run(original, text, stance=None):
    return helpers.run(revision, text, helpers.unavailable_morphology(), original=original, stance=stance)


def kinds(items):
    return [item["kind"] for item in items]


def findings(report, rule_id):
    return [f for f in report["findings"] if f["rule_id"] == rule_id]


class MarkerTests(unittest.TestCase):
    def test_request_becomes_invitation(self):
        report = run("設定ファイルを開いてください。\n", "設定ファイルを開きましょう。\n")
        markers = {m["kind"]: m for m in report["revision"]["markers"]}
        self.assertEqual((markers["request"]["original"], markers["request"]["rewrite"]), (1, 0))
        self.assertEqual(markers["invitation"]["rewrite_hits"], ["ましょう"])
        change = report["revision"]["endings"]["changes"][0]
        self.assertEqual((change["original_kind"], change["rewrite_kind"]), ("request", "recommendation"))
        self.assertEqual(findings(report, "marker_count_change"), [])

    def test_conjecture_change_is_a_finding(self):
        report = run("この値は正しい。\n", "この値は正しいかもしれない。\n")
        found = findings(report, "marker_count_change")
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0]["line"], found[0]["severity"]), (1, "info"))
        self.assertIn("revision.md R1", found[0]["reason"])

    def test_spans_record_added_text(self):
        report = run("手順を守る。\n", "手順を必ず守る。\n")
        span = report["revision"]["spans"][0]
        self.assertEqual((span["line"], span["added"], span["kinds"]), (1, "必ず", ["emphasis"]))


class WordTests(unittest.TestCase):
    def test_lost_and_new_words(self):
        report = run("サーバーを再起動して設定を反映する。\n", "サーバーを停止して設定を反映する。\n")
        self.assertEqual(report["revision"]["lost_words"], ["再起動"])
        self.assertEqual(report["revision"]["new_words"], ["停止"])
        lost = findings(report, "lost_content_word")[0]
        self.assertEqual((lost["line"], lost["column"]), (1, 6))
        self.assertEqual(findings(report, "new_content_word")[0]["excerpt"], "停止")

    def test_code_and_urls_are_not_words(self):
        report = run("手順を読む。\n", "手順を読む。`newcmd` と [資料](https://example.com/Guide) を見る。\n")
        self.assertNotIn("newcmd", report["revision"]["new_words"])
        self.assertNotIn("Guide", report["revision"]["new_words"])
        self.assertIn("資料", report["revision"]["new_words"])

    def test_positions_refer_to_rewrite(self):
        report = run("一行目。\n", "# 見出し\n\n一行目。追加情報を書く。\n")
        found = {f["excerpt"]: f["line"] for f in findings(report, "new_content_word")}
        self.assertEqual(found["追加情報"], 3)


class StructureTests(unittest.TestCase):
    def test_list_removed_and_paragraphs(self):
        original = "前置きの文。\n\n- 項目その一\n- 項目その二\n\n締めの文。\n"
        report = run(original, "前置きの文。項目その一と項目その二。締めの文。\n")
        notes = kinds(report["revision"]["structure"])
        self.assertEqual(notes, ["list_removed", "paragraphs_reduced", "sentences_changed"])

    def test_joined_lines_of_one_paragraph_are_not_reduced(self):
        report = run("一文目です。\n二文目です。\n", "一文目です。二文目です。\n")
        self.assertEqual(report["revision"]["structure"], [])


class LogicTests(unittest.TestCase):
    def test_candidates(self):
        text = "手順を書く。しかし例外もある。この点は後で扱う。設定も、別に管理する。注意点があります。\n"
        report = run("手順を書く。\n", text)
        self.assertEqual(
            kinds(report["revision"]["logic"]),
            ["leading_connective", "leading_demonstrative", "topic_mo", "preview_only"],
        )
        self.assertEqual(len(findings(report, "logic_candidate")), 4)

    def test_unchanged_sentences_list_but_do_not_report(self):
        report = run("しかし例外もある。\n", "しかし例外もある。\n")
        self.assertEqual(kinds(report["revision"]["logic"]), ["leading_connective"])
        self.assertEqual(findings(report, "logic_candidate"), [])


class EndingTests(unittest.TestCase):
    def test_stance_conflict(self):
        report = run("画面を開いてください。\n", "画面を開きます。\n", stance="advice")
        found = findings(report, "stance_ending_change")
        self.assertEqual(len(found), 1)
        self.assertIn("revision.md R3", found[0]["reason"])
        self.assertEqual(kinds(report["revision"]["endings"]["flags"]), ["action_in_advice"])
        self.assertEqual(report["revision"]["endings"]["original_flags"], [])
        self.assertEqual(report["revision"]["stance"], "advice")

    def test_passive_is_not_action(self):
        report = run("ファイルを削除します。\n", "ファイルは削除されます。\n", stance="advice")
        change = report["revision"]["endings"]["changes"][0]
        self.assertEqual((change["original_kind"], change["rewrite_kind"]), ("action", "state"))
        self.assertEqual(findings(report, "stance_ending_change"), [])

    def test_list_origin_kind(self):
        report = run("- 画面を開いてください\n", "画面を開きます。\n")
        self.assertEqual(report["revision"]["endings"]["changes"][0]["original_kind"], "request_in_list")


class CapTests(unittest.TestCase):
    def test_lists_and_findings_are_capped(self):
        words = "、".join(f"Word{n:03d}" for n in range(150))
        report = run("一覧を示す。\n", f"一覧を示す。{words}。\n")
        section = report["revision"]
        self.assertEqual(len(section["new_words"]), 100)
        self.assertEqual(section["omitted"]["new_words"], 50)
        stats = report["stats"]["revision"]
        self.assertEqual((stats["new_words"], stats["findings"], stats["findings_omitted"]), (150, 60, 90))
        self.assertEqual(len(report["findings"]), 60)

    def test_missing_original_is_unverified(self):
        state = helpers.inspection("本文。\n", helpers.unavailable_morphology())
        revision.run(state)
        self.assertIn("revision", [note["check"] for note in state.report["unverified"]])
        self.assertEqual(state.report["findings"], [])


if __name__ == "__main__":
    unittest.main()
