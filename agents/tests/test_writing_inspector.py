"""Stdlib contract tests for the advisory inspector, not a writing-quality gate."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "curated/japanese-writing/scripts/inspect_text.py"
SPEC = importlib.util.spec_from_file_location("writing_inspector", SCRIPT)
inspector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inspector)


def unavailable(needed):
    return None, {"available": False, "reason": "missing_or_version_mismatch", "packages": {}}


class InspectorTests(unittest.TestCase):
    def inspect(self, text, modes=None):
        with patch.object(inspector, "_morphology", unavailable):
            return inspector.inspect_text(text, modes)

    def cli(self, payload, args=None):
        if not isinstance(payload, bytes):
            payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), *(args if args is not None else ["--request"])], input=payload, capture_output=True, timeout=30)
        self.assertEqual(result.stderr, b"")
        self.assertLess(len(result.stdout), inspector.MAX_OUTPUT)
        return result.returncode, json.loads(result.stdout), result.stdout

    def test_plain_text_line_offsets_and_advisories(self):
        text = "短い文。\n\n前置き。国際情報処理技術研究所です。\n" + "あ" * 91 + "。"
        report = self.inspect(text, ["reading-load", "outline"])
        kanji = next(f for f in report["findings"] if f["rule_id"] == "kanji_run")
        self.assertEqual((kanji["line"], kanji["column"], kanji["excerpt"]), (3, 5, "国際情報処理技術研究所"))
        self.assertIn("retain proper nouns", kanji["reason"])
        length = next(f for f in report["findings"] if f["rule_id"] == "sentence_length")
        self.assertEqual(length["line"], 4)
        self.assertIn("91", length["reason"])
        self.assertTrue(all(f["requires_context"] for f in report["findings"]))
        self.assertEqual([o["line"] for o in report["outline"]], [1, 3])

    def test_block_scopes_and_real_structure(self):
        lines = [
            "---", "# FRONT **bold** API", "...",
            "   ````python", "# CODE **bold** API", "```", "~~~~", "```` not closing", "   `````",
            "<!--", "# COMMENT **bold** API", "-->",
            "> # QUOTE **bold** API", "lazy QUOTE **bold** API", "",
            "    # INDENT **bold** API", "",
            "Header | API", "--- | ---", "**TABLE** | API", "",
            "# まとめ API", "", "タイトル API", "===", "",
            "- リスト API **one**", "  続き API **two**", "", "  続き API", "",
            "本文 API **three**。",
        ]
        report = self.inspect("\n".join(lines))
        counts = report["structure"]["counts"]
        self.assertEqual(counts["headings"], 2)
        self.assertEqual(counts["summary_headings"], 1)
        self.assertEqual(counts["list_lines"], 1)
        self.assertEqual(counts["bold_spans"], 3)
        self.assertEqual(counts["eligible_lines"], 6)
        self.assertEqual(report["structure"]["proportions"]["list_lines"], {"numerator": 1, "denominator": 6, "denominator_name": "eligible_lines", "value": 1 / 6})
        api = next(t for t in report["terms"] if t["term"] == "API")
        self.assertEqual(api["count"], 6)
        self.assertEqual(api["line"], 22)
        self.assertEqual([o["line"] for o in report["outline"]], [22, 24, 32])
        self.assertNotIn("CODE", [t["term"] for t in report["terms"]])

    def test_only_physical_newlines_advance_line_numbers(self):
        for separator in ("\u2028", "\u2029", "\f", "\v", "\x85"):
            for newline in ("\n", "\r\n", "\r"):
                with self.subTest(separator=repr(separator), newline=repr(newline)):
                    text = "あ" * 50 + separator + "あ" * 50 + "。" + newline + "API"
                    report = self.inspect(text, ["reading-load", "terms"])
                    length = next(f for f in report["findings"] if f["rule_id"] == "sentence_length")
                    self.assertEqual(length["line"], 1)
                    self.assertIn("100", length["reason"])
                    self.assertEqual(report["terms"][0]["line"], 2)

    def test_reading_load_excludes_list_heading_table_quote_code(self):
        long = "漢" * 91
        for block in (f"# {long}", f"{long}\n---", f"- {long}\n  {long}", f"> {long}\n{long}", f"~~~\n{long}\n~~~", f"    {long}", f"{long}|x\n---|---\n{long}|x", f"<!-- {long} -->"):
            with self.subTest(block=block[:15]):
                self.assertEqual(self.inspect(block, ["reading-load"])["findings"], [])

    def test_inline_scope_and_original_offsets(self):
        text = "`CODE` [API](https://URL.test/a(b)) ![IMAGE](DEST) ``X ` Y`` <https://AUTO> API <!-- HIDDEN --> **ok**"
        report = self.inspect(text, ["terms", "structure"])
        self.assertEqual([(t["term"], t["count"]) for t in report["terms"]], [("API", 2)])
        self.assertEqual(report["terms"][0]["column"], text.index("API") + 1)
        self.assertEqual(report["structure"]["counts"]["bold_spans"], 1)
        long = "漢" * 100
        report = self.inspect(f"前 `{long}` 後。", ["reading-load"])
        self.assertEqual(report["findings"], [])

    def test_comments_do_not_leak_fences_and_code_does_not_open_comments(self):
        report = self.inspect("<!--\n````\n-->\nAPI\n\n```\n<!--\n```\nHTTP", ["terms"])
        self.assertEqual([(t["term"], t["line"]) for t in report["terms"]], [("API", 4), ("HTTP", 9)])
        report = self.inspect("`<!--` API\nHTTP", ["terms"])
        self.assertEqual([t["term"] for t in report["terms"]], ["API", "HTTP"])
        report = self.inspect("    <!--\n    - FAKE\n\nAPI\n\n- item\n\n      CODE\n\nHTTP", ["terms", "structure"])
        self.assertEqual([t["term"] for t in report["terms"]], ["API", "HTTP"])
        self.assertEqual(report["structure"]["counts"]["list_lines"], 1)

    def test_reference_links_images_escapes_and_thematic_breaks(self):
        text = "[API][ref] ![IMAGE][ref] API\n\n[ref]: https://HIDDEN\n\n***\n\n\\*\\*not bold\\*\\* __yes__"
        report = self.inspect(text, ["terms", "structure"])
        self.assertEqual([(t["term"], t["count"]) for t in report["terms"]], [("API", 2)])
        self.assertEqual(report["structure"]["counts"]["list_lines"], 0)
        self.assertEqual(report["structure"]["counts"]["bold_spans"], 1)

    def test_bold_inside_japanese_prose_and_list_contained_fence(self):
        report = self.inspect("これは**重要**です。***one*** __two__\n\n- ````python\n  # FAKE **bold**\n  ```\n  ````\n\nAPI", ["terms", "structure"])
        self.assertEqual(report["structure"]["counts"]["bold_spans"], 3)
        self.assertEqual(report["structure"]["counts"]["headings"], 0)
        self.assertEqual(report["structure"]["counts"]["list_lines"], 1)
        self.assertEqual([t["term"] for t in report["terms"]], ["API"])

    def test_setext_single_dash_and_atx_closing(self):
        report = self.inspect("API\n-\n\n# C#\n\n## HTTP ##", ["outline", "structure"])
        self.assertEqual([(o["line"], o["level"], o["excerpt"]) for o in report["outline"]], [(1, 2, "API"), (4, 1, "C#"), (6, 2, "HTTP ##")])
        self.assertEqual(report["structure"]["counts"]["headings"], 3)

    def test_mode_validation_and_empty_modes(self):
        for modes in (True, False, "terms", [True], [1], [None], ["unknown"], ["terms", "terms"], {}):
            with self.subTest(modes=modes), self.assertRaises(ValueError):
                inspector.inspect_text("text", modes)
        for text in (True, False, 12, [], None, "\ud800", "あ" * 43691):
            with self.subTest(text=str(text)[:20]), self.assertRaises(ValueError):
                inspector.inspect_text(text)
        report = self.inspect("API", [])
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["executed"], [])
        self.assertEqual(report["unverified"], [])
        self.assertEqual(report["terms"], [])
        self.assertEqual(report["structure"], {})

    def test_missing_morphology_is_partial_not_false_completion(self):
        report = self.inspect("企業の部門の担当の資料。できないわけではない。東京 API")
        self.assertEqual(report["status"], "partial")
        self.assertEqual({n["check"] for n in report["unverified"]}, {"no_particle_chain", "double_negative", "proper_noun_inventory"})
        self.assertFalse({"no_particle_chain", "double_negative"} & {f["rule_id"] for f in report["findings"]})
        self.assertNotIn("proper_noun_inventory", report["executed"])
        self.assertEqual(self.inspect("", ["outline", "structure"])["status"], "ok")

    def test_exact_dependency_versions_enforced(self):
        requirements = (SCRIPT.parent / "requirements.txt").read_text().splitlines()
        self.assertEqual(
            {line for line in requirements if line and not line.startswith("#")},
            {f"{name}=={version}" for name, version in inspector.PINS.items()},
        )
        with patch.object(inspector.metadata, "version", return_value="0.0.0"):
            tokenizer, info = inspector._morphology(True)
        self.assertIsNone(tokenizer)
        self.assertFalse(info["available"])
        self.assertEqual(info["reason"], "missing_or_version_mismatch")
        self.assertEqual(info["packages"]["SudachiPy"]["actual"], "0.0.0")
        self.assertEqual(info["packages"]["sudachidict_core"]["required"], "20260723")
        with patch.object(inspector.metadata, "version", side_effect=inspector.metadata.PackageNotFoundError):
            self.assertIsNone(inspector._morphology(True)[1]["packages"]["SudachiPy"]["actual"])

    def test_caps_counts_and_excerpt_clipping(self):
        text = "\n\n".join(f"API{i} " + "漢" * 100 for i in range(230))
        report = self.inspect(text)
        self.assertEqual(len(report["findings"]), 100)
        self.assertEqual(len(report["outline"]), 200)
        self.assertEqual(len(report["terms"]), 200)
        self.assertEqual(report["truncation"]["counts"]["findings"], {"total": 460, "returned": 100, "omitted": 360})
        self.assertEqual(report["truncation"]["counts"]["terms"]["omitted"], 30)
        self.assertTrue(report["truncation"]["applied"])
        clipped = self.inspect("カ" * 300, ["terms", "outline"])
        self.assertEqual(len(clipped["terms"][0]["term"]), 240)
        self.assertEqual(clipped["truncation"]["term_clipped"], 1)
        self.assertEqual(clipped["truncation"]["excerpt_clipped"], 2)
        self.assertEqual(clipped["status"], "partial")

    def test_wire_budget_counts_actual_bytes_and_escaping(self):
        report = inspector._base("")
        report["status"] = "ok"
        for name, cap in inspector.CAPS.items():
            report[name] = [{"excerpt": "\x01" * 240, "term": "\U0001f600" * 240} for _ in range(cap)]
        inspector._finish(report)
        self.assertLess(len(inspector._serialize(report)), inspector.MAX_OUTPUT)
        self.assertGreater(report["truncation"]["output_budget_dropped"], 0)
        for name in inspector.CAPS:
            counts = report["truncation"]["counts"][name]
            self.assertEqual(counts["returned"], len(report[name]))
            self.assertEqual(counts["total"], counts["returned"] + counts["omitted"])

    def test_no_cross_line_or_masked_kanji_matches(self):
        report = self.inspect("漢漢漢漢\n漢漢漢漢\n漢漢漢`x`漢漢漢", ["reading-load"])
        self.assertEqual(report["findings"], [])
        report = self.inspect("あ" * 90 + "。", ["reading-load"])
        self.assertEqual(report["findings"], [])
        report = self.inspect("**" + "あ" * 90 + "**。", ["reading-load"])
        self.assertEqual(report["findings"], [])
        report = self.inspect("**`CODE`** **prose <!-- hidden --> more**", ["structure"])
        self.assertEqual(report["structure"]["counts"]["bold_spans"], 2)

    def test_cli_utf8_hash_determinism_and_no_source_writes(self):
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SCRIPT.parent.iterdir() if p.is_file()}
        text = "# 日本語\r\nAPIとは。\n$(touch should-not-exist)\n"
        payload = {"text": text, "modes": ["outline", "structure"]}
        code, report, wire = self.cli(payload)
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["input_sha256"], hashlib.sha256(text.encode("utf-8")).hexdigest())
        self.assertEqual(wire, self.cli(payload)[2])
        self.assertEqual(report["schema_version"], 1)
        self.assertIn("日本語".encode("utf-8"), wire)
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SCRIPT.parent.iterdir() if p.is_file()})

    def test_cli_malformed_requests(self):
        cases = [b"\xff", b"{", b"null", b"true", b"[]", b'{"text":"", "text":""}', b'{"text":NaN}', b'{"text":"\\ud800"}', {}, {"text": True}, {"text": "", "other": 1}, {"text": "", "modes": None}, {"text": "", "modes": [False]}, {"text": "", "modes": ["bad"]}, {"text": "a" * (inspector.MAX_TEXT + 1)}, b" " * (inspector.MAX_REQUEST + 1), b"[" * 2000]
        for payload in cases:
            with self.subTest(payload=str(payload)[:60]):
                code, report, _ = self.cli(payload)
                self.assertNotEqual(code, 0)
                self.assertEqual(report["status"], "error")
                self.assertEqual(report["error"]["code"], "invalid_request")
                self.assertEqual(report["executed"], [])
        self.assertNotEqual(self.cli({"text": ""}, args=[])[0], 0)

    def test_maximum_text_and_request_accepted_without_truncation(self):
        text = "a" * inspector.MAX_TEXT
        report = self.inspect(text, [])
        self.assertEqual(report["input_sha256"], hashlib.sha256(text.encode()).hexdigest())
        payload = b'{"text":"", "modes":[]}'
        payload += b" " * (inspector.MAX_REQUEST - len(payload))
        self.assertEqual(self.cli(payload)[0], 0)

    def test_real_morphology_when_provisioned(self):
        tokenizer, info = inspector._morphology(True)
        if tokenizer is None:
            self.skipTest("Pinned Sudachi environment not provisioned: " + info["reason"])
        report = inspector.inspect_text("東京の会社の部門の担当の資料。できないわけではない。API", ["reading-load", "terms"])
        self.assertTrue(report["dependencies"]["available"])
        self.assertEqual(report["unverified"], [])
        rules = {f["rule_id"]: f for f in report["findings"]}
        self.assertIn("no_particle_chain", rules)
        self.assertIn("double_negative", rules)
        self.assertIn("Preserve modality", rules["double_negative"]["reason"])
        self.assertIn("東京", [t["term"] for t in report["terms"] if t["kind"] == "proper_noun"])

    def test_mocked_morphology_diagnostics_and_offsets(self):
        def tokenize(piece):
            tokens = []
            cursor = 0
            while cursor < len(piece):
                if piece.startswith("ない", cursor):
                    surface, pos = "ない", ("助動詞", "*")
                elif piece.startswith("東京", cursor):
                    surface, pos = "東京", ("名詞", "固有名詞")
                else:
                    surface = piece[cursor]
                    pos = ("助詞", "格助詞") if surface == "の" else ("名詞", "普通名詞")
                start, end = cursor, cursor + len(surface)
                tokens.append(SimpleNamespace(surface=lambda s=surface: s, dictionary_form=lambda s=surface: s, part_of_speech=lambda p=pos: p, begin=lambda n=start: n, end=lambda n=end: n))
                cursor = end
            return tokens

        tokenizer = SimpleNamespace(tokenize=tokenize)
        with patch.object(inspector, "_morphology", return_value=(tokenizer, {"available": True, "reason": None, "packages": {}})):
            report = inspector.inspect_text("# 東京\n\n甲の乙の丙の丁。ないわけではない。\n\n東京の乙の丙。", ["reading-load", "terms"])
            masked = inspector.inspect_text("甲の乙`x`の丙の丁。ない`x`ない。", ["reading-load"])
            huge = inspector.inspect_text("あ" * 14000, ["reading-load"])
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["unverified"], [])
        rules = {f["rule_id"]: f for f in report["findings"]}
        self.assertEqual((rules["no_particle_chain"]["line"], rules["no_particle_chain"]["column"], rules["no_particle_chain"]["excerpt"]), (3, 2, "の乙の丙の"))
        self.assertEqual(rules["double_negative"]["excerpt"], "ないわけではない")
        self.assertIn("Preserve modality", rules["double_negative"]["reason"])
        tokyo = next(t for t in report["terms"] if t["term"] == "東京")
        self.assertEqual((tokyo["line"], tokyo["column"], tokyo["count"]), (1, 3, 2))
        self.assertEqual(masked["findings"], [])
        self.assertEqual(huge["status"], "partial")
        self.assertEqual(huge["unverified"][0]["reason"], "segment_exceeds_40000_utf8_bytes")

    def test_cli_runtime_error_is_not_a_success(self):
        from io import BytesIO

        stdin = SimpleNamespace(buffer=BytesIO(b'{"text":"API"}'))
        stdout = SimpleNamespace(buffer=BytesIO())
        with patch.object(sys, "argv", [str(SCRIPT), "--request"]), patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout), patch.object(inspector, "inspect_text", side_effect=RuntimeError("private detail")):
            code = inspector.main()
        report = json.loads(stdout.buffer.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["error"]["code"], "runtime_failure")
        self.assertNotIn(b"private detail", stdout.buffer.getvalue())
        self.assertEqual(report["input_sha256"], hashlib.sha256(b"API").hexdigest())


if __name__ == "__main__":
    unittest.main()
