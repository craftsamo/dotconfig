"""Tests for the explainer-video-review technic's review.py (ledger, sheet, report check).

Fixtures are invented and language-neutral by default (English); Japanese
appears only where the `ja` sheet wording or caption rules are under test.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

HERMES_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    HERMES_ROOT / "profiles" / "assistant" / "skills" / "technic"
    / "explainer-video-review" / "scripts" / "review.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("explainer_review", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


review = load_module()


def finding(fid, episode, at, problem, status="keep", certainty="certain", quotes=(), aspect="text"):
    return {"id": fid, "episode": episode, "at": at, "aspect": aspect, "problem": problem,
            "evidence": "frame", "certainty": certainty, "quotes": list(quotes),
            "source": "video-creator", "status": status}


class ReviewScript(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.captions = self.dir / "ep1.en.txt"
        self.captions.write_text(
            "[0:00] What is a compiler?\n"
            "[0:12] Grace Hopper wrote the first one\n"
            "[1:02] It cost about 7.5 million dollars\n"
            "[1:30] The NASA team grew 13% a year\n",
            encoding="utf-8",
        )
        self.ledger = self.dir / "ledger.json"
        self.write({
            "job": "sample",
            "language": "en",
            "episodes": [{"label": "#1", "title": "One", "captions": str(self.captions)},
                         {"label": "#11", "title": "Eleven"}],
            "findings": [
                finding("F001", "#1", "1:15", "A label hides the unit of the value", quotes=["$4.2 trillion"]),
                finding("F002", "#11", "0:40", "The year is wrong"),
                finding("F003", "#1", "0:44", "May overstate the count", certainty="confirm", status="open",
                        aspect="content"),
                finding("F004", "all", "", "Energy jumps between segments", aspect="voice", quotes=["energy jumps"]),
            ],
            "listen": [],
        })

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, data):
        self.ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def data(self):
        return json.loads(self.ledger.read_text(encoding="utf-8"))

    def run_cli(self, *argv):
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = review.main(list(argv))
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def sheet(self):
        out = self.dir / "sheet.md"
        code, _, _ = self.run_cli("sheet", str(self.ledger), str(out))
        self.assertEqual(code, 0)
        return out.read_text(encoding="utf-8")

    def settle(self):
        data = self.data()
        for item in data["findings"]:
            if item["status"] == "open":
                item["status"] = "drop"
        for episode in data["episodes"]:
            episode["checked"] = ["text", "voice", "content", "thumbnail"]
        self.write(data)

    def check(self, text):
        report = self.dir / "report.md"
        report.write_text(text, encoding="utf-8")
        code, out, _ = self.run_cli("check", str(self.ledger), str(report))
        return code, json.loads(out)

    def test_script_strips_time_prefixes(self):
        out = self.dir / "script.txt"
        code, _, _ = self.run_cli("script", str(self.captions), str(out))
        self.assertEqual(code, 0)
        self.assertEqual(out.read_text(encoding="utf-8").splitlines()[1], "Grace Hopper wrote the first one")

    def test_validate_final_refuses_open_findings(self):
        code, out, _ = self.run_cli("validate", str(self.ledger))
        self.assertEqual(code, 0)
        code, out, _ = self.run_cli("validate", str(self.ledger), "--final")
        self.assertEqual(code, 1)
        self.assertIn("F003: still open", out)

    def test_validate_rejects_unknown_values(self):
        data = self.data()
        data["findings"].append(finding("F001", "#9", "late", "x", aspect="mood"))
        self.write(data)
        code, out, _ = self.run_cli("validate", str(self.ledger))
        self.assertEqual(code, 1)
        for message in ("duplicate finding id F001", "unknown episode '#9'", "aspect must be", "holds no m:ss time"):
            self.assertIn(message, out)

    def test_final_requires_the_checked_aspects(self):
        self.settle()
        data = self.data()
        del data["episodes"][1]["checked"]
        self.write(data)
        code, out, _ = self.run_cli("validate", str(self.ledger), "--final")
        self.assertEqual(code, 1)
        self.assertIn("episode #11: checked is not recorded", out)

    def test_listen_takes_each_caption_lines_own_time(self):
        terms = self.dir / "terms.txt"
        terms.write_text("#1\tcompiler\n", encoding="utf-8")
        code, _, _ = self.run_cli("listen", str(self.ledger), "--terms", str(terms))
        self.assertEqual(code, 0)
        listen = {(item["at"], item["term"]) for item in self.data()["listen"]}
        for expected in (("0:12", "Grace Hopper"), ("1:02", "7.5"), ("1:30", "NASA"), ("1:30", "13%"),
                         ("0:00", "compiler")):
            self.assertIn(expected, listen)
        self.assertNotIn(("0:00", "What"), listen)
        self.assertNotIn(("1:02", "It"), listen)
        before = len(self.data()["listen"])
        self.run_cli("listen", str(self.ledger), "--terms", str(terms))
        self.assertEqual(len(self.data()["listen"]), before)

    def test_listen_ignores_a_term_scoped_to_another_episode(self):
        terms = self.dir / "terms.txt"
        terms.write_text("#11\tcompiler\n", encoding="utf-8")
        self.run_cli("listen", str(self.ledger), "--terms", str(terms))
        self.assertNotIn("compiler", {item["term"] for item in self.data()["listen"]})

    def test_listen_uses_the_rules_of_the_episodes_language(self):
        captions = self.dir / "ep1.ja.txt"
        captions.write_text("[0:05] サンプル・テストさんの話\n[0:12] 売り上げは約三十倍、約120億円\n[0:20] APIを使う\n",
                            encoding="utf-8")
        data = self.data()
        data["episodes"][0].update({"captions": str(captions), "language": "ja-JP"})
        self.write(data)
        self.run_cli("listen", str(self.ledger))
        listen = {(item["at"], item["term"]) for item in self.data()["listen"]}
        for expected in (("0:05", "サンプル・テスト"), ("0:12", "約三十倍"), ("0:12", "約120億円"), ("0:20", "API")):
            self.assertIn(expected, listen)

    def test_sheet_separates_certain_from_confirm_and_hides_drops(self):
        data = self.data()
        data["findings"].append(finding("F005", "#1", "0:10", "A withdrawn finding", status="drop"))
        data["listen"] = [{"episode": "#1", "at": "0:12", "term": "Grace Hopper", "result": "heard as Grace Harper"}]
        self.write(data)
        sheet = self.sheet()
        self.assertIn("## Overall", sheet)
        self.assertIn("### Certain\n- 1:15  Text: A label hides the unit of the value", sheet)
        self.assertIn("### Needs your eyes or ears\n- [ ] 0:44  Content: May overstate the count", sheet)
        self.assertIn("- [x] 0:12  Grace Hopper  → heard as Grace Harper", sheet)
        self.assertNotIn("A withdrawn finding", sheet)

    def test_sheet_names_unchecked_aspects_instead_of_a_clean_bill(self):
        data = self.data()
        data["findings"] = [f for f in data["findings"] if f["episode"] != "#11"]
        data["episodes"][1]["checked"] = ["text", "content"]
        self.write(data)
        sheet = self.sheet()
        self.assertIn("## #11 Eleven\nChecked: Text, Content / Not checked: Voice, Thumbnail, Portrait\n"
                      "- No findings in the checked aspects", sheet)
        self.assertIn("## #1 One\nChecked aspects: not recorded", sheet)

    def test_sheet_speaks_the_readers_language_and_falls_back_to_english(self):
        data = self.data()
        data["sheet_language"] = "ja"
        self.write(data)
        self.assertIn("### 確実\n- 1:15　字：A label hides the unit of the value", self.sheet())
        data["sheet_language"] = "xx"
        self.write(data)
        self.assertIn("### Certain\n", self.sheet())

    def test_import_adds_hands_lines_once_with_quotes_and_new_ids(self):
        findings = self.dir / "findings.md"
        findings.write_text(
            "| m:ss | aspect | problem | evidence | certainty |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| 2:30 | text | A label hides \"$0.5 trillion\" | detail-1/d150.png | certain |\n"
            "- | portrait | The caption gives a different year | detail-2/d042.png | confirm\n"
            "1:00 | mood | not an aspect | x | certain\n",
            encoding="utf-8",
        )
        code, out, _ = self.run_cli("import", str(self.ledger), "#11", str(findings), "--source", "video-creator")
        self.assertEqual(code, 1)
        result = json.loads(out)
        self.assertEqual(result["added"], ["F005", "F006"])
        self.assertEqual(result["not_imported"], ["1:00 | mood | not an aspect | x | certain"])
        added = {f["id"]: f for f in self.data()["findings"]}
        self.assertEqual(added["F005"]["quotes"], ["$0.5 trillion"])
        self.assertEqual((added["F005"]["episode"], added["F005"]["status"], added["F005"]["source"]),
                         ("#11", "open", "video-creator"))
        self.assertEqual(added["F005"]["evidence"], str(self.dir.resolve() / "detail-1/d150.png"))
        self.assertEqual(added["F006"]["at"], "")
        code, out, _ = self.run_cli("import", str(self.ledger), "#11", str(findings), "--source", "video-creator")
        self.assertEqual(json.loads(out)["added"], [])

    def test_import_tolerates_case_trailing_dots_and_a_pipe_inside_the_problem(self):
        findings = self.dir / "findings.md"
        findings.write_text("0:12 | Text | \"A\" | \"B\" cards overlap | /abs/e.png | Certain.\n", encoding="utf-8")
        code, out, _ = self.run_cli("import", str(self.ledger), "#1", str(findings), "--source", "video-creator")
        self.assertEqual(code, 0, out)
        row = self.data()["findings"][-1]
        self.assertEqual((row["aspect"], row["certainty"], row["evidence"]), ("text", "certain", "/abs/e.png"))
        self.assertEqual(row["problem"], "\"A\" | \"B\" cards overlap")
        self.assertEqual(row["quotes"], ["A", "B"])

    def test_quotes_are_read_in_each_writing_systems_marks(self):
        self.assertEqual(review.quotes_in("“a” „b“ «c» 「d」 『e』 \"f\""), ["a", "b", "c", "d", "e", "f"])
        self.assertEqual(review.quotes_in("it's a plain apostrophe"), [])

    def test_import_refuses_an_unknown_episode_or_source(self):
        findings = self.dir / "findings.md"
        findings.write_text("0:01 | text | x | y | certain\n", encoding="utf-8")
        code, _, err = self.run_cli("import", str(self.ledger), "#9", str(findings), "--source", "video-creator")
        self.assertEqual(code, 2)
        self.assertIn("unknown episode", err)
        code, _, err = self.run_cli("import", str(self.ledger), "#1", str(findings), "--source", "someone")
        self.assertEqual(code, 2)

    def test_save_keeps_the_ledger_mode_and_leaves_no_temp_file(self):
        self.ledger.chmod(0o640)
        self.run_cli("listen", str(self.ledger))
        self.assertEqual(self.ledger.stat().st_mode & 0o777, 0o640)
        self.assertEqual([p.name for p in self.dir.glob(".ledger-*")], [])

    def test_check_passes_a_faithful_report(self):
        self.settle()
        code, result = self.check(
            "# Review\nOverall: energy jumps between segments.\n\n"
            "## #1\n- 1:15 the label hides the unit of \"$4.2 trillion\"\n\n"
            "## #11\n- ０:４０ the year is wrong\n"  # full-width digits normalise
        )
        self.assertEqual(code, 0, result)
        self.assertTrue(result["ok"])

    def test_check_ignores_an_overview_line_that_names_episodes(self):
        self.settle()
        code, result = self.check(
            "#11 and #1 were reviewed; energy jumps between segments.\n\n"
            "## #1\n- 1:15 \"$4.2 trillion\" loses its unit\n\n## #11\n- 0:40 the year is wrong\n"
        )
        self.assertEqual(code, 0, result)

    def test_check_reads_hour_stamps_and_ranges(self):
        self.settle()
        data = self.data()
        data["findings"] = [finding("F010", "#1", "1:02:03-1:02:09", "A finding in a long episode"),
                            finding("F011", "#11", "0:50-0:54", "The delivery shifts", aspect="voice")]
        self.write(data)
        code, result = self.check("## #1\n- 1:02:03 a finding\n## #11\n- 0:50-0:54 the delivery shifts\n")
        self.assertEqual(code, 0, result)

    def test_check_flags_misplaced_missing_and_invented_findings(self):
        self.settle()
        code, result = self.check("## #1\n- 0:40 the year is wrong\n- 3:10 a new finding\n\n## #11\n- 1:15 a hidden unit\n")
        self.assertEqual(code, 1)
        self.assertIn("F001 #1 1:15", result["missing_times"])
        self.assertIn("F002 #11 0:40", result["missing_times"])
        self.assertIn('F001 #1 "$4.2 trillion"', result["missing_quotes"])
        self.assertIn('F004 all "energy jumps"', result["missing_quotes"])
        self.assertEqual(result["unexpected_times"], ["3:10"])

    def test_check_does_not_mistake_episode_1_for_11(self):
        self.settle()
        data = self.data()
        data["findings"] = [f for f in data["findings"] if f["id"] == "F002"]
        self.write(data)
        code, result = self.check("## #11\n- 0:40 the year is wrong\n")
        self.assertEqual(code, 0, result)

    def test_check_refuses_an_unsettled_ledger(self):
        report = self.dir / "report.md"
        report.write_text("x\n", encoding="utf-8")
        code, _, err = self.run_cli("check", str(self.ledger), str(report))
        self.assertEqual(code, 2)
        self.assertIn("ledger is not final", err)


if __name__ == "__main__":
    unittest.main()
