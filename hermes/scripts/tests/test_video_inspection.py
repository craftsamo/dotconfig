"""Tests for the video-inspection technic's inspection.py (ledger, sheet, report check).

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
    / "video-inspection" / "scripts" / "inspection.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("video_inspection", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


review = load_module()
# The explainer catalog is the fixture's aspects; a test that wants other
# aspects writes its own ``aspects`` list.
CATALOG = json.loads((SCRIPT.parent.parent / "references" / "explainer.json").read_text(encoding="utf-8"))


def aspects(*ids):
    """A deep copy of the catalog's aspects, all of them or the named ones."""
    return [json.loads(json.dumps(a)) for a in CATALOG["aspects"] if not ids or a["id"] in ids]


def finding(fid, episode, at, problem, status="keep", certainty="certain", quotes=(), aspect="text"):
    return {"id": fid, "episode": episode, "at": at, "aspect": aspect, "problem": problem,
            "evidence": "frame", "certainty": certainty, "quotes": list(quotes),
            "source": "video-creator", "status": status}


class LedgerCase(unittest.TestCase):
    """A two-episode ledger with one caption file; the test classes below share it."""

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
        data.setdefault("aspects", aspects())
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

    def sheet(self, *flags):
        out = self.dir / "sheet.md"
        code, _, _ = self.run_cli("sheet", str(self.ledger), str(out), *flags)
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


class ReviewScript(LedgerCase):
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
        self.assertNotIn("Grace Hopper", sheet)  # the listen list is opt-in
        self.assertNotIn("A withdrawn finding", sheet)
        self.assertIn("- [x] 0:12  Grace Hopper  → heard as Grace Harper", self.sheet("--listen"))

    def test_sheet_links_times_to_the_video_and_shows_the_question_without_local_paths(self):
        data = self.data()
        data["episodes"][0]["video"] = "https://www.youtube.com/watch?v=abcdefghijk"
        data["findings"][2].update({"ask": "Is the count overstated?", "kind": "fact",
                                    "evidence": "/abs/job/01/visual/d0044.png; https://example.org/source"})
        data["findings"].append(finding("F005", "#1", "", "The title does not say which topic it is",
                                        certainty="confirm", status="open", aspect="thumbnail"))
        self.write(data)
        sheet = self.sheet()
        self.assertIn("## #1 [One](https://youtu.be/abcdefghijk)", sheet)
        self.assertIn("- [1:15](https://youtu.be/abcdefghijk?t=73)  Text: A label hides", sheet)
        self.assertIn("- [ ] [0:44](https://youtu.be/abcdefghijk?t=42)  Content: fact: Is the count overstated? "
                      "(evidence: https://example.org/source) `F003`", sheet)
        self.assertIn("- [ ] [Thumbnail](https://i.ytimg.com/vi/abcdefghijk/maxresdefault.jpg)  Thumbnail: "
                      "The title does not say", sheet)
        self.assertNotIn("/abs/job", sheet)
        self.assertIn("- 0:40  Text: The year is wrong", sheet)  # no video known for #11

    def test_validate_knows_the_new_fields(self):
        data = self.data()
        data["episodes"][0]["video"] = "not a video"
        data["findings"][0].update({"kind": "reading", "note": 3})
        data["findings"][1]["status"] = "recheck"
        data["findings"][2]["status"] = "hold"
        self.write(data)
        code, out, _ = self.run_cli("validate", str(self.ledger))
        self.assertEqual(code, 1)
        self.assertIn("episode #1: video must be a YouTube id or URL", out)
        self.assertIn("F001: kind 'reading' is not a kind of aspect 'text'", out)
        self.assertIn("F001: note must be a string", out)
        data["episodes"][0]["video"] = "abcdefghijk"
        data["findings"][0].update({"kind": "typo", "note": "fine"})
        self.write(data)
        code, out, _ = self.run_cli("validate", str(self.ledger), "--final")
        self.assertEqual(code, 1)
        self.assertIn("F002: still recheck", out)
        self.assertNotIn("F003", out)  # hold is settled

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

    def test_import_leaves_a_non_path_evidence_word_alone(self):
        findings = self.dir / "prosody.md"
        findings.write_text("0:41 | voice | pitch +7.0 st (ASR: a sample line) | prosody | confirm\n", encoding="utf-8")
        code, out, _ = self.run_cli("import", str(self.ledger), "#1", str(findings), "--source", "audio-creator")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.data()["findings"][-1]["evidence"], "prosody")

    def test_import_keeps_urls_and_resolves_each_relative_path(self):
        findings = self.dir / "findings.md"
        findings.write_text(
            "1:53 | content | The chip count is half | Vendor note 2024-03-18 https://example.org/a/b | confirm\n"
            "0:50 | text | Two frames | detail-1/a.png; window-4/w.png | certain\n",
            encoding="utf-8",
        )
        code, out, _ = self.run_cli("import", str(self.ledger), "#1", str(findings), "--source", "searcher")
        self.assertEqual(code, 0, out)
        rows = self.data()["findings"][-2:]
        self.assertEqual(rows[0]["evidence"], "Vendor note 2024-03-18 https://example.org/a/b")
        self.assertEqual(rows[1]["evidence"],
                         f"{self.dir.resolve() / 'detail-1/a.png'}; {self.dir.resolve() / 'window-4/w.png'}")

    def test_import_takes_a_kind_in_the_aspect_cell_or_as_a_flag(self):
        findings = self.dir / "speech.md"
        findings.write_text(
            "0:27 | unlabeled(pitch +3st) | numbers jump in level | ASR 27.2s | confirm\n"
            "1:04 | reading | \"A\" is not heard | ASR 64s | confirm\n",
            encoding="utf-8",
        )
        code, out, _ = self.run_cli("import", str(self.ledger), "#1", str(findings), "--source", "audio-creator")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["added"], ["F005"])
        self.assertEqual((self.data()["findings"][-1]["aspect"], self.data()["findings"][-1]["kind"]),
                         ("voice", "reading"))
        code, out, _ = self.run_cli("import", str(self.ledger), "#1", str(findings), "--source", "audio-creator",
                                    "--kind", "delivery")
        self.assertEqual(code, 0, out)
        row = self.data()["findings"][-1]
        self.assertEqual((row["at"], row["aspect"], row["kind"]), ("0:27", "voice", "delivery"))
        code, _, err = self.run_cli("import", str(self.ledger), "#1", str(findings), "--source", "audio-creator",
                                    "--kind", "typo", "--aspect", "voice")
        self.assertEqual(code, 2)
        self.assertIn("belongs to aspect text", err)

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


class SpeechTriage(LedgerCase):
    """Only value mismatches, unheard Latin terms and mid-line jumps survive."""

    def setUp(self):
        super().setUp()
        self.captions.write_text(
            "[0:00] Intro\n[0:16] ACME TV!\n[0:40] Only three stayed\n[0:46] What, only three?\n"
            "[0:58] Quiz: of the first 52 theorems, how many: 5 or 38?\n[1:06] Five, surely!\n"
            "[2:03] Today's point. And the forecast was always early.\n[2:12] One a day! Bye!\n",
            encoding="utf-8",
        )
        self.speech = self.dir / "speech"
        self.speech.mkdir()
        (self.speech / "findings.md").write_text(
            "format: aac 44100Hz\n"
            "0:22 | unlabeled | \"8 items\" heard as \"issue\" | ASR 22s | confirm\n"
            "0:27 | unlabeled | \"1, 2, 4, 8\" heard as \"12, 1, 2, 4, 8\" | ASR 27s | confirm\n"
            "0:16 | unlabeled | \"ACME TV\" heard as \"akmi tivi\" | ASR 16s | confirm\n"
            "1:04 | unlabeled | \"A\" heard as \"\" | ASR 64s | confirm\n"
            "1:34 | unlabeled | \"decimal\" heard as \"the cymbal\" | ASR 94s | confirm\n"
            "1:06 | unlabeled | 「五個」→ASR「ここ」 | ASR 66s | confirm\n"
            "1:32 | unlabeled | 「約2万3千倍」→ASR「2300倍」 | ASR 92s | confirm\n"
            "2:00 | unlabeled | 「約1040億個」→ASR「1枚に約1400個」 | ASR 120s | confirm\n"
            "0:18 | unlabeled | 「5G」 appears in the ASR text | ASR 18s | confirm\n"
            "1:07 | unlabeled | ASR only: 台本「」→ASR「8GBの」 | ASR 67s | confirm\n"
            "1:42 | unlabeled | 「一周」「約16周」→ASR「一週」「約16週」 | ASR 102s | confirm\n"
            "1:52 | unlabeled | 台本「千」→ASR「00」 | ASR 112s | confirm\n"
            "1:53 | unlabeled | extra words 「一つ2倍」: 台本「700億個なら、約140GB」→ASR「700億個一つ2倍約140GB」 | ASR 113s | confirm\n",
            encoding="utf-8",
        )
        (self.speech / "prosody.md").write_text(
            "reference median pitch 114 Hz\n"
            "0:16 | high(200Hz) | prosody jump candidate | pitch +15.0 st vs previous (ASR: ACME TV!) | confirm\n"
            "0:46 | high(225Hz) | prosody jump candidate | pitch +13.3 st vs previous, +11.0 st (vs median) | confirm\n"
            "0:52 | mid | prosody jump candidate | pitch +8.7 st (vs median) | confirm\n"
            "1:03 | low(93Hz) | prosody jump candidate | pitch -7.7 st、level -8.0 dB vs 直前 | confirm\n"
            "1:06 | low(74Hz) | prosody jump candidate | level -22.4 dB vs previous | confirm\n"
            "2:07 | low(88Hz) | prosody jump candidate | level -12.9 dB vs previous | confirm\n"
            "2:11 | high(189Hz) | prosody jump candidate | pitch +13.1 st vs previous | confirm\n",
            encoding="utf-8",
        )

    def test_numbers_read_digits_and_kanji_with_units(self):
        self.assertEqual(review.numbers_in("約1040億個"), {1.04e11})
        self.assertEqual(review.numbers_in("約2万3千倍"), {23000.0})
        self.assertEqual(review.numbers_in("五十二個の定理、1,400 per die"), {52.0, 1400.0})
        self.assertEqual(review.latin_terms("ACME TV, ChatGPT, decimal, A, mm"), {"acme", "tv", "chatgpt", "a"})

    def test_triage_keeps_value_mismatches_unheard_terms_and_mid_line_jumps(self):
        code, out, err = self.run_cli("triage-speech", str(self.ledger), "#1", str(self.speech))
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual(result["reading"], ["0:16", "1:04", "1:32", "2:00"])
        self.assertEqual(result["delivery"], ["1:03", "2:07"])
        self.assertEqual(result["dropped"], 20 - 6)
        kept = {f["at"]: f for f in self.data()["findings"] if f["source"] == "audio-creator"}
        self.assertEqual((kept["2:00"]["aspect"], kept["2:00"]["kind"], kept["2:00"]["certainty"],
                          kept["2:00"]["status"]), ("voice", "reading", "confirm", "open"))
        self.assertEqual(kept["2:07"]["kind"], "delivery")
        triage = (self.speech / "triage.md").read_text(encoding="utf-8")
        self.assertIn("1:03 | delivery | prosody jump candidate", triage)
        self.assertNotIn("0:46", triage)  # a jump at a caption line start is the next speaker
        self.assertNotIn("2:11", triage)  # the closing line
        self.assertNotIn("0:27", triage)  # every script number was heard

    def test_triage_ignore_list_weak_mode_and_jump_cap(self):
        ignore = self.dir / "ignore.txt"
        ignore.write_text("ACME\n", encoding="utf-8")
        code, out, _ = self.run_cli("triage-speech", str(self.ledger), "#1", str(self.speech),
                                    "--ignore", str(ignore), "--weak", "--max-jumps", "1")
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["reading"], ["0:22", "1:04", "1:06", "1:32", "2:00"])
        self.assertEqual(result["delivery"], ["2:07"])

    def test_triage_without_captions_keeps_jumps_by_size_only(self):
        data = self.data()
        del data["episodes"][0]["captions"]
        self.write(data)
        code, out, _ = self.run_cli("triage-speech", str(self.ledger), "#1", str(self.speech), "--max-jumps", "2")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["delivery"], ["0:46", "1:06"])


class Spreadsheet(LedgerCase):
    def setUp(self):
        super().setUp()
        data = self.data()
        data["episodes"][0]["video"] = "abcdefghijk"
        data["findings"][0]["kind"] = "overlap"
        data["findings"][1]["kind"] = "typo"
        data["findings"][2].update({"kind": "fact", "evidence": "/abs/d.png; https://example.org/src"})
        data["findings"][3]["kind"] = "delivery"
        data["findings"].append(finding("F005", "#11", "0:12", "=SUM(A1) starts like a formula",
                                        certainty="confirm", status="open"))
        data["findings"][-1]["kind"] = "typo"
        self.write(data)

    def export(self):
        out = self.dir / "export.json"
        code, text, err = self.run_cli("export", str(self.ledger), str(out))
        self.assertEqual(code, 0, err)
        return json.loads(out.read_text(encoding="utf-8"))

    def test_ask_draft_lists_open_questions_and_ask_import_stores_them(self):
        draft = self.dir / "asks.md"
        code, out, _ = self.run_cli("ask-draft", str(self.ledger), str(draft))
        self.assertEqual(code, 0)
        self.assertEqual(draft.read_text(encoding="utf-8"),
                         "F003 | May overstate the count\nF005 | =SUM(A1) starts like a formula\n")
        draft.write_text("F003 | Is the count overstated?\nF999 | nobody\n", encoding="utf-8")
        code, out, _ = self.run_cli("ask-import", str(self.ledger), str(draft))
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["stored"], ["F003"])
        self.assertEqual(self.data()["findings"][2]["ask"], "Is the count overstated?")

    def test_export_builds_the_findings_tab_with_links_options_and_a_summary(self):
        data = self.data()
        data["findings"][2]["ask"] = "Is the count overstated?"
        data["findings"][2]["note"] = "listen twice"
        self.write(data)
        out = self.export()
        tab = out["tabs"]["findings"]
        self.assertEqual(tab["title"], "Findings")
        self.assertEqual(tab["header"], ["ID", "Episode", "Time", "Kind", "Claim (YES = it is so)", "Evidence",
                                         "Answer", "Memo", "Reply"])
        rows = {row[0]: row for row in tab["rows"]}
        self.assertEqual([row[0] for row in tab["rows"]], ["F004", "F003", "F001", "F005", "F002"])
        self.assertEqual(rows["F003"], ["F003", "#1", '=HYPERLINK("https://youtu.be/abcdefghijk?t=42","0:44")',
                                        "Content: fact", "Is the count overstated?", "https://example.org/src",
                                        "", "listen twice", ""])  # unanswered: blank
        self.assertEqual(rows["F001"][6], "YES")  # a reproduced finding comes pre-answered
        self.assertEqual(rows["F004"][1:3], ["Overall", ""])
        self.assertEqual(rows["F005"][2], "0:12")  # no video for #11: plain text, a time stays a time
        self.assertEqual(rows["F005"][4], "'=SUM(A1) starts like a formula")
        self.assertEqual(out["judgments"], ["YES", "NO", "Can't tell"])
        self.assertEqual(out["columns"]["judgment"], "G")
        self.assertEqual(out["owner"], {"user": ["G", "H"], "assistant": ["I"]})
        self.assertEqual(out["format"], {"episodes": [
            {"episode": "Overall", "first_row": 2, "last_row": 2, "colour": "#FFFFFF"},
            {"episode": "#1", "first_row": 3, "last_row": 4, "colour": "#E6F4EA"},
            {"episode": "#11", "first_row": 5, "last_row": 6, "colour": "#FFFFFF"},
        ]})
        self.assertIn("Voice: reading", out["kinds"])
        self.assertNotIn("Voice", out["kinds"])  # a bare aspect is not an option
        self.assertEqual(rows["F004"][3], "Voice: delivery")

    def test_export_refuses_a_finding_without_a_kind_and_kinds_fills_them(self):
        data = self.data()
        del data["findings"][0]["kind"]
        data["findings"][3].pop("kind")
        data["findings"][3]["evidence"] = "level -12.9 dB vs previous"
        data["findings"].append(finding("F006", "#1", "0:20", "The ring hides the card's first letter",
                                        certainty="confirm", status="open"))
        data["findings"].append(finding("F007", "#1", "0:30", "Two fewer wave heights than the caption says",
                                        certainty="confirm", status="open", aspect="content"))
        data["findings"].append(finding("F008", "#1", "0:40", "Heard as something else", certainty="confirm",
                                        status="open", aspect="voice"))
        self.write(data)
        out = self.dir / "export.json"
        code, _, err = self.run_cli("export", str(self.ledger), str(out))
        self.assertEqual(code, 2)
        self.assertIn("without a kind (run `inspection.py kinds` first): F001, F004, F006, F007, F008", err)
        code, text, _ = self.run_cli("kinds", str(self.ledger))
        self.assertEqual(code, 0, text)
        self.assertEqual(json.loads(text)["inferred"],
                         {"F001": "overlap", "F004": "delivery", "F006": "overlap", "F007": "figure",
                          "F008": "reading"})
        code, _, _ = self.run_cli("export", str(self.ledger), str(out))
        self.assertEqual(code, 0)

    def test_export_builds_the_summary_tab(self):
        out = self.export()
        summary = out["tabs"]["summary"]
        self.assertEqual(summary["header"][:3], ["Episode", "Title", "Findings"])
        self.assertEqual(summary["rows"][0][:3], ["#1", '=HYPERLINK("https://youtu.be/abcdefghijk","One")',
                                                  "=COUNTIFS('Findings'!$B:$B,\"=#1\")"])
        self.assertEqual(summary["rows"][0][3], "=COUNTIFS('Findings'!$B:$B,\"=#1\",'Findings'!$G:$G,\"=YES\")")
        self.assertEqual(summary["rows"][0][6], "=COUNTIFS('Findings'!$B:$B,\"=#1\",'Findings'!$G:$G,\"=\")")
        self.assertEqual(summary["header"], ["Episode", "Title", "Findings", "YES", "NO", "Can't tell", "Unanswered"])
        self.assertEqual(summary["rows"][2][0], "Overall")
        self.assertEqual(summary["rows"][-1][:3], ["Total", "", "=SUM(C2:C4)"])

    def test_export_speaks_the_sheet_language(self):
        data = self.data()
        data["sheet_language"] = "ja"
        self.write(data)
        out = self.export()
        self.assertEqual(out["tabs"]["findings"]["title"], "所見")
        self.assertEqual(out["tabs"]["findings"]["header"][6], "判定")
        self.assertEqual(out["judgments"], ["YES", "NO", "確認不可"])
        self.assertEqual(out["tabs"]["findings"]["header"][4], "内容（YES＝その通り）")
        self.assertEqual(out["tabs"]["findings"]["rows"][1][3], "中身・事実")

    def test_readback_maps_answers_to_statuses_and_lists_rechecks(self):
        data = self.data()
        data["findings"][3]["status"] = "hold"  # F004: the assistant already gave up on it
        self.write(data)
        values = self.dir / "values.json"
        values.write_text(json.dumps({"values": [
            ["ID", "Episode", "Time", "Kind", "Claim (YES = it is so)", "Evidence", "Answer", "Memo", "Reply"],
            ["F001", "#1", "1:15", "Text", "...", "", "YES", "", ""],
            ["F003", "#1", "0:44", "Content: fact", "...", "", "Can't tell", "show me the source", ""],
            ["F002", "#11", "0:40", "Text", "...", "", "no", "", "answered earlier"],
            ["F005", "#11", "0:12", "Text", "...", "", "", "", ""],
            ["F004", "Overall", "", "Voice", "...", "", "確認不可", "", ""],
            ["F999", "#1", "", "", "", "", "YES", "", ""],
            ["F001", "#1", "", "", "", "", "maybe", "", ""],
        ]}, ensure_ascii=False), encoding="utf-8")
        code, out, _ = self.run_cli("readback", str(self.ledger), str(values))
        self.assertEqual(code, 1)
        result = json.loads(out)
        self.assertEqual(result["counts"], {"open": 0, "recheck": 1, "keep": 1, "drop": 1, "hold": 1})
        self.assertEqual(result["blank"], ["F005"])
        self.assertEqual(result["recheck"], [{"id": "F003", "episode": "#1", "at": "0:44", "note": "show me the source"}])
        self.assertEqual(result["unknown_ids"], ["F999"])
        self.assertEqual(result["unknown_judgments"], ["F001: maybe"])
        by_id = {f["id"]: f for f in self.data()["findings"]}
        self.assertEqual(by_id["F003"]["status"], "recheck")
        self.assertEqual(by_id["F002"]["status"], "drop")
        self.assertEqual(by_id["F002"]["reply"], "answered earlier")
        self.assertEqual(by_id["F004"]["status"], "hold")
        self.assertEqual(by_id["F005"]["status"], "open")
        self.assertEqual(by_id["F001"]["status"], "keep")  # the unknown judgment left the earlier one alone

    def test_readback_never_erases_a_memo_or_reply_with_a_blank_cell(self):
        data = self.data()
        data["findings"][0]["reply"] = "written after the export"
        self.write(data)
        values = self.dir / "values.json"
        values.write_text(json.dumps([["ID", "Answer", "Memo", "Reply"], ["F001", "YES", "", ""]]),
                          encoding="utf-8")
        code, _, _ = self.run_cli("readback", str(self.ledger), str(values))
        self.assertEqual(code, 0)
        self.assertEqual(self.data()["findings"][0]["reply"], "written after the export")

    def test_public_evidence_keeps_urls_and_measurements_only(self):
        self.assertEqual(review.public_evidence("/abs/a.png; detail-1/d.png; frames/d0044; a.pdf; ~/x; "
                                                "https://example.org/p?a=1;b=2; ASR 27.2s level +16.4 dB; 168px"),
                         "https://example.org/p?a=1;b=2; ASR 27.2s level +16.4 dB; 168px")
        self.assertEqual(review.criterion('#1 "two" 5*?~'), '=#1 ""two"" 5~*~?~~')
        self.assertEqual(review.video_id("https://example.org/?dev=abcdefghijk"), None)
        self.assertEqual(review.video_id("https://www.youtube.com/watch?v=abcdefghijk&t=3"), "abcdefghijk")

    def test_readback_refuses_a_sheet_without_ids(self):
        values = self.dir / "values.json"
        values.write_text(json.dumps([["Episode", "Answer"], ["#1", "YES"]]), encoding="utf-8")
        code, _, err = self.run_cli("readback", str(self.ledger), str(values))
        self.assertEqual(code, 2)
        self.assertIn("no id column", err)


class Aspects(LedgerCase):
    """The items a job looks for come from a genre catalog, live in the ledger,
    and drive import, kinds, focus and the sheet."""

    def test_every_catalog_beside_the_script_is_valid(self):
        catalogs = sorted((SCRIPT.parent.parent / "references").glob("*.json"))
        self.assertTrue(catalogs)
        for path in catalogs:
            with self.subTest(catalog=path.name):
                catalog = review.load_catalog(path.stem)
                self.assertEqual(catalog["genre"], path.stem)
                self.assertEqual(review.aspect_problems(catalog["aspects"]), [])
                for aspect in catalog["aspects"]:
                    self.assertIn("ja", aspect["label"], aspect["id"])
                    for kind in aspect.get("kinds") or []:
                        self.assertIn("ja", kind["label"], kind["id"])
                self.assertNotIn("overall", [a["id"] for a in catalog["aspects"]])
        code, out, _ = self.run_cli("genres")
        self.assertEqual(code, 0)
        self.assertIn("explainer", json.loads(out)["genres"])

    def test_aspect_problems_name_each_shape_error(self):
        broken = [
            {"id": "Text", "label": {"en": "x"}, "route": "video-creator", "items": []},
            {"id": "a", "label": {"ja": "字"}, "route": "nobody", "items": [{"id": "i"}]},
            {"id": "b", "label": {"en": "b"}, "route": "user",
             "kinds": [{"id": "k", "label": {"en": "k"}, "default": True, "hint": "(", "items": []},
                       {"id": "k", "label": {"en": "k"}, "default": True, "sources": ["x"],
                        "items": [{"id": "i", "look_for": "dup", "certainty": "maybe"}]}]},
            {"id": "overall", "label": {"en": "o"}, "route": "assistant", "items": []},
        ]
        errors = review.aspect_problems(broken)
        for expected in ("needs a lowercase id", "label needs at least an en wording", "route must be one of",
                         "look_for is empty", "hint is not a regex", "duplicate kind id k", "duplicate item id i",
                         "sources must list finding sources", "certainty must be certain or confirm",
                         "at most one default kind", "overall is built in"):
            self.assertTrue(any(expected in e for e in errors), (expected, errors))

    def test_validate_wants_aspects_and_checks_findings_against_them(self):
        data = self.data()
        del data["aspects"]
        self.ledger.write_text(json.dumps(data), encoding="utf-8")
        code, out, _ = self.run_cli("validate", str(self.ledger))
        self.assertEqual(code, 1)
        self.assertIn("inspection.py init", out)
        data["aspects"] = aspects("text", "content")  # no voice: F004 is now an unknown aspect
        data["findings"][0]["item"] = "hands"  # a content item on a text finding
        data["findings"][2].update({"kind": "fact", "item": "glitch"})  # a figure item on a fact finding
        self.write(data)
        code, out, _ = self.run_cli("validate", str(self.ledger))
        self.assertEqual(code, 1)
        self.assertIn("F004: aspect must be one of text, content, overall", out)
        self.assertIn("F001: item 'hands' is not an item of 'text'/None", out)
        self.assertIn("F003: item 'glitch' is not an item of 'content'/'fact'", out)
        self.assertIn("checked must list aspects from text, content", self.sheet_errors(data))

    def sheet_errors(self, data):
        data["episodes"][0]["checked"] = ["voice"]
        self.write(data)
        _, out, _ = self.run_cli("validate", str(self.ledger))
        return out

    def test_init_copies_the_chosen_aspects_and_never_overwrites(self):
        fresh = self.dir / "fresh.json"
        code, out, _ = self.run_cli("init", str(fresh), "--genre", "explainer", "--aspects", "text,thumbnail",
                                    "--job", "demo", "--language", "ja", "--sheet-language", "ja")
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out)["aspects"], ["text", "thumbnail"])
        data = json.loads(fresh.read_text(encoding="utf-8"))
        self.assertEqual((data["genre"], data["job"], data["language"], data["sheet_language"]),
                         ("explainer", "demo", "ja", "ja"))
        self.assertEqual([a["id"] for a in data["aspects"]], ["text", "thumbnail"])
        self.assertEqual((data["episodes"], data["findings"], data["listen"]), ([], [], []))
        code, _, err = self.run_cli("init", str(fresh), "--genre", "explainer")
        self.assertEqual(code, 2)
        self.assertIn("never overwrites", err)
        code, _, err = self.run_cli("init", str(self.dir / "x.json"), "--genre", "explainer", "--aspects", "mood")
        self.assertEqual(code, 2)
        self.assertIn("not in the explainer catalog: mood", err)
        code, _, err = self.run_cli("init", str(self.dir / "y.json"), "--genre", "sitcom")
        self.assertEqual(code, 2)
        self.assertIn("no catalog for genre 'sitcom'", err)

    def test_focus_lists_one_routes_items_with_their_path(self):
        out = self.dir / "focus.txt"
        code, text, _ = self.run_cli("focus", str(self.ledger), str(out), "--route", "video-creator")
        self.assertEqual(code, 0, text)
        lines = out.read_text(encoding="utf-8").splitlines()
        self.assertIn("content/figure/hands: a drawn hand with the wrong number of fingers or an impossible grip", lines)
        self.assertTrue(any(line.startswith("portrait/drawing: ") for line in lines))
        self.assertFalse(any(line.startswith(("voice/", "thumbnail/", "content/fact/")) for line in lines))
        self.assertFalse(any("likeness" in line for line in lines), "the user's item is not the hands'")
        code, text, _ = self.run_cli("focus", str(self.ledger), str(out), "--route", "user")
        self.assertEqual(code, 0, text)
        self.assertEqual(out.read_text(encoding="utf-8").splitlines(),
                         ["portrait/likeness: whether the portrait looks like the person; the user's call, "
                          "prepared with the reference photos beside each frame (confirm: needs the user's eyes or ears)"])
        code, text, _ = self.run_cli("focus", str(self.ledger), str(out), "--route", "researcher")
        self.assertEqual((code, json.loads(text)["items"]), (1, 0))
        code, _, err = self.run_cli("focus", str(self.ledger), str(out), "--route", "nobody")
        self.assertEqual(code, 2)

    def test_import_places_a_finding_by_its_item(self):
        findings = self.dir / "findings.md"
        findings.write_text(
            "0:10 | content | hands: the mascot's left hand has six fingers | d1.png | certain\n"
            "0:20 | pseudo-text | the whiteboard carries letter-like marks | d2.png | certain\n"
            "0:30 | portrait | likeness: looks like the CEO | d3.png | certain\n"
            "0:40 | text | hands: an item of another aspect | d4.png | certain\n"
            "0:50 | fact | glitch: an item of another kind | d5.png | certain\n",
            encoding="utf-8",
        )
        code, out, _ = self.run_cli("import", str(self.ledger), "#1", str(findings), "--source", "video-creator")
        self.assertEqual(code, 1)
        result = json.loads(out)
        self.assertEqual(result["added"], ["F005", "F006", "F007"])
        self.assertEqual(len(result["not_imported"]), 2)
        rows = {f["id"]: f for f in self.data()["findings"]}
        self.assertEqual((rows["F005"]["aspect"], rows["F005"]["kind"], rows["F005"]["item"]),
                         ("content", "figure", "hands"))
        self.assertEqual(rows["F005"]["problem"], "the mascot's left hand has six fingers")
        self.assertEqual((rows["F006"]["aspect"], rows["F006"]["kind"], rows["F006"]["item"]),
                         ("content", "figure", "pseudo-text"))
        self.assertEqual((rows["F007"]["aspect"], rows["F007"].get("kind"), rows["F007"]["item"],
                          rows["F007"]["certainty"]), ("portrait", None, "likeness", "confirm"))
        code, out, _ = self.run_cli("validate", str(self.ledger))
        self.assertEqual(code, 0, out)

    def test_kinds_follow_the_ledgers_sources_hints_and_default(self):
        data = self.data()
        data["findings"] = [
            finding("F001", "#1", "0:01", "the year is stated nowhere official", status="open", aspect="content"),
            finding("F002", "#1", "0:02", "the counter shows 3 then 2", status="open", aspect="content"),
            finding("F003", "#1", "0:03", "hard to follow", status="open", aspect="content"),
            finding("F004", "#1", "0:04", "anything at all", status="open", aspect="thumbnail"),
        ]
        data["findings"][0]["source"] = "researcher"
        data["findings"][2]["evidence"] = "note"  # the fixture's "frame" would read as a figure
        self.write(data)
        code, out, _ = self.run_cli("kinds", str(self.ledger))
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out)["inferred"], {"F001": "fact", "F002": "figure", "F003": "clarity"})
        data = self.data()
        data["aspects"].append({"id": "music", "label": {"en": "Music"}, "route": "audio-creator",
                                "kinds": [{"id": "loud", "label": {"en": "Music: loud"}, "hint": "loud",
                                           "items": []},
                                          {"id": "quiet", "label": {"en": "Music: quiet"}, "items": []}]})
        data["findings"].append(finding("F005", "#1", "0:05", "the bed is neither", status="open", aspect="music"))
        self.write(data)
        code, out, _ = self.run_cli("kinds", str(self.ledger))
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["unresolved"], ["F005"])  # no hint matched and no default

    def test_the_sheet_speaks_the_ledgers_labels(self):
        data = self.data()
        data["sheet_language"] = "ja"
        data["aspects"] = aspects("text", "voice") + [
            {"id": "music", "label": {"en": "Music", "ja": "音楽"}, "route": "audio-creator",
             "items": [{"id": "loud", "look_for": "the bed covers the voice"}]}]
        data["findings"] = [dict(finding("F001", "#1", "0:01", "too loud", aspect="music"), item="loud"),
                            dict(finding("F002", "#1", "0:02", "x", aspect="text"), kind="typo")]
        data["episodes"][0]["checked"] = ["text", "music"]
        self.write(data)
        out = self.dir / "export.json"
        code, _, err = self.run_cli("export", str(self.ledger), str(out))
        self.assertEqual(code, 0, err)
        export = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(export["kinds"], ["字・不一致", "字・かぶり", "字・誤字", "声・緩急", "声・読み", "音楽", "全体"])
        self.assertEqual(export["tabs"]["findings"]["rows"][0][3], "音楽")
        self.assertEqual(export["tabs"]["findings"]["rows"][1][3], "字・誤字")
        text = self.sheet()
        self.assertIn("確認した観点：字・音楽　／　未確認：声", text)
        self.assertIn("音楽：too loud", text)

    def test_upgrade_gives_an_old_ledger_the_catalog(self):
        data = self.data()
        del data["aspects"]
        data["findings"][0]["kind"] = "overlap"
        self.ledger.write_text(json.dumps(data), encoding="utf-8")
        code, out, _ = self.run_cli("upgrade", str(self.ledger), "--genre", "explainer")
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out)["findings"], 4)
        data = self.data()
        self.assertEqual(data["genre"], "explainer")
        self.assertEqual([a["id"] for a in data["aspects"]], ["text", "voice", "content", "thumbnail", "portrait"])
        code, _, _ = self.run_cli("validate", str(self.ledger))
        self.assertEqual(code, 0)
        code, _, err = self.run_cli("upgrade", str(self.ledger), "--genre", "explainer")
        self.assertEqual(code, 2)
        self.assertIn("already has aspects", err)
        data["findings"][0]["aspect"] = "mood"
        del data["aspects"]
        self.ledger.write_text(json.dumps(data), encoding="utf-8")
        code, _, err = self.run_cli("upgrade", str(self.ledger), "--genre", "explainer")
        self.assertEqual(code, 2)
        self.assertIn("do not fit the catalog", err)

    def test_ids_share_one_namespace(self):
        clash = aspects("text")
        clash[0]["kinds"][0]["items"].append({"id": "overlap", "look_for": "an item named like a kind"})
        self.assertTrue(any("duplicate kind id overlap" in e for e in review.aspect_problems(clash)))
        clash = aspects("text") + [{"id": "typo", "label": {"en": "x"}, "route": "user", "items": []}]
        self.assertTrue(any("duplicate aspect id typo" in e for e in review.aspect_problems(clash)))
        clash = aspects("thumbnail", "portrait")
        clash[1]["items"].append({"id": "topic", "look_for": "an item named like another aspect's item"})
        self.assertTrue(any("duplicate item id topic" in e for e in review.aspect_problems(clash)))

    def test_kinds_take_the_items_kind_first(self):
        data = self.data()
        data["findings"] = [dict(finding("F001", "#1", "0:01", "the counter is official", status="open",
                                         aspect="content"), item="hands")]
        data["findings"][0]["source"] = "researcher"  # sources would say fact; the item says figure
        self.write(data)
        code, out, _ = self.run_cli("kinds", str(self.ledger))
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out)["inferred"], {"F001": "figure"})
        self.assertEqual(review.problems(self.data(), final=False), [])

    def test_validate_keeps_a_confirm_item_from_being_certain(self):
        data = self.data()
        data["findings"].append(dict(finding("F005", "#1", "0:05", "looks like him", aspect="portrait"), item="likeness"))
        self.write(data)
        code, out, _ = self.run_cli("validate", str(self.ledger))
        self.assertEqual(code, 1)
        self.assertIn("F005: item 'likeness' needs the user's eyes or ears; certainty must be confirm", out)

    def test_triage_drops_an_item_of_the_other_kind(self):
        data = self.data()
        data["findings"] = []
        self.write(data)
        speech = self.dir / "speech"
        speech.mkdir()
        (speech / "findings.md").write_text("0:20 | voice | jump: 「1040億」→「1400億」 | ASR | confirm\n", encoding="utf-8")
        code, out, _ = self.run_cli("triage-speech", str(self.ledger), "#1", str(speech))
        self.assertEqual(code, 0, out)
        row = self.data()["findings"][-1]
        self.assertEqual((row["kind"], row.get("item")), ("reading", None))
        self.assertEqual(review.problems(self.data(), final=False), [])

    def test_triage_needs_the_voice_kinds(self):
        data = self.data()
        data["aspects"] = aspects("text")
        data["findings"] = []
        self.write(data)
        speech = self.dir / "speech"
        speech.mkdir()
        (speech / "findings.md").write_text("0:12 | voice | 「10」→「1」 | ASR | confirm\n", encoding="utf-8")
        code, _, err = self.run_cli("triage-speech", str(self.ledger), "#1", str(speech))
        self.assertEqual(code, 2)
        self.assertIn("no voice aspect with reading and delivery kinds", err)


if __name__ == "__main__":
    unittest.main()
