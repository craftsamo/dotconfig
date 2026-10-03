"""CLI and report contract of inspect_text.py (schema v2), not a quality gate."""

import hashlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "curated/japanese-writing/scripts/inspect_text.py"
SPEC = importlib.util.spec_from_file_location("japanese_writing_entry", SCRIPT)
entry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(entry)
reporting = entry.reporting
morphology = sys.modules["inspector.morphology"]


def unavailable(needed):
    info = {"available": False, "reason": "missing_or_version_mismatch", "packages": {}}
    return morphology.Morphology(None, info)


class ContractTests(unittest.TestCase):
    def inspect(self, text, modes=None, **options):
        with patch.object(entry, "load_morphology", unavailable):
            return entry.inspect_text(text, modes, **options)

    def cli(self, payload, args=("--request",)):
        if not isinstance(payload, bytes):
            payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        result = subprocess.run([sys.executable, "-I", "-B", str(SCRIPT), *args], input=payload,
                                capture_output=True, timeout=60)
        self.assertEqual(result.stderr, b"")
        self.assertLess(len(result.stdout), reporting.MAX_OUTPUT)
        return result.returncode, json.loads(result.stdout), result.stdout

    def test_envelope_and_default_modes(self):
        report = self.inspect("本文です。")
        self.assertEqual(report["schema_version"], 2)
        self.assertEqual(report["inspector_version"], entry.reporting.VERSION)
        self.assertEqual(report["request"]["modes"], [m for m in entry.MODES if m != "revision"])
        self.assertEqual(report["request"]["genre"], "default")
        self.assertIsNone(report["original_sha256"])
        for key in ("executed", "unverified", "findings", "outline", "terms"):
            self.assertIsInstance(report[key], list)
        for key in ("structure", "truncation", "dependencies", "stats", "revision", "heading_stats"):
            self.assertIsInstance(report[key], dict)

    def test_findings_have_the_v2_shape_and_order(self):
        text = "これは**非常に重要**と言えるでしょう。\n\n" + "あ" * 95 + "。"
        report = self.inspect(text)
        self.assertTrue(report["findings"])
        for finding in report["findings"]:
            self.assertEqual(set(finding), {"mode", "rule_id", "severity", "line", "column", "excerpt",
                                            "reason", "related_lines", "requires_context"})
            self.assertIn(finding["severity"], ("info", "warn", "critical"))
            self.assertIn(finding["mode"], entry.MODES)
        keys = [(f["line"], f["column"]) for f in report["findings"]]
        self.assertEqual(keys, sorted(keys))

    def test_original_only_with_revision(self):
        report = self.inspect("新しい文です。", original="古い文です。")
        self.assertIn("revision", report["request"]["modes"])
        self.assertEqual(report["original_sha256"], hashlib.sha256("古い文です。".encode()).hexdigest())
        for modes, original in ((["revision"], None), (["terms"], "古い文です。")):
            with self.subTest(modes=modes), self.assertRaises(ValueError):
                entry.inspect_text("本文", modes, original=original)

    def test_argument_validation(self):
        for modes in (True, "terms", [True], [1], ["unknown"], ["terms", "terms"], {}):
            with self.subTest(modes=modes), self.assertRaises(ValueError):
                entry.inspect_text("text", modes)
        for text in (True, 12, [], None, "\ud800", "あ" * 43691):
            with self.subTest(text=str(text)[:20]), self.assertRaises(ValueError):
                entry.inspect_text(text)
        for options in ({"genre": "novel"}, {"experimental": 1}, {"stance": "勧め"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                entry.inspect_text("text", **options)
        report = self.inspect("API", [])
        self.assertEqual((report["status"], report["executed"], report["unverified"]), ("ok", [], []))

    def test_missing_morphology_is_partial_and_withholds_the_score(self):
        report = self.inspect("企業の部門の担当の資料です。" * 20)
        self.assertEqual(report["status"], "partial")
        self.assertTrue(report["unverified"])
        self.assertIsNone(report["score"]["value"])
        self.assertEqual(report["score"]["reason"], "naturalness_unverified")
        self.assertEqual(self.inspect("", ["structure", "notation"])["status"], "ok")

    def test_score_formula(self):
        finding = {"mode": "naturalness", "rule_id": "r", "severity": "warn"}
        result = entry.score.compute([finding] * 3 + [dict(finding, severity="critical")], 2000, {"r"}, True)
        self.assertEqual((result["value"], result["band"], result["deduction"]), (90.0, "natural", 10.0))
        self.assertEqual(entry.score.compute([finding] * 40, 500, {"r"}, True)["value"], 20.0)
        self.assertEqual(entry.score.compute([], 99, {"r"}, True)["reason"], "too_short")
        ignored = [dict(finding, rule_id="other"), dict(finding, mode="expression")]
        self.assertEqual(entry.score.compute(ignored, 1000, {"r"}, True)["value"], 100.0)

    @unittest.skipUnless(morphology.load(True).available, "pinned Sudachi not provisioned")
    def test_score_with_real_morphology(self):
        text = "結論として、この方法は非常に重要と言えるでしょう。" * 6
        report = entry.inspect_text(text, ["naturalness"])
        self.assertTrue(report["score"]["complete"])
        self.assertLess(report["score"]["value"], 100)
        self.assertGreater(report["score"]["counts"]["warn"], 0)

    def test_exact_dependency_versions_enforced(self):
        requirements = (SCRIPT.parent / "requirements.txt").read_text().splitlines()
        self.assertEqual({line for line in requirements if line and not line.startswith("#")},
                         {f"{name}=={version}" for name, version in morphology.PINS.items()})
        with patch.object(morphology.metadata, "version", return_value="0.0.0"):
            loaded = morphology.load(True)
        self.assertFalse(loaded.available)
        self.assertEqual(loaded.reason, "missing_or_version_mismatch")
        self.assertEqual(loaded.info["packages"]["SudachiPy"]["actual"], "0.0.0")

    def test_caps_counts_and_wire_budget(self):
        report = reporting.base("")
        report["status"] = "ok"
        for name, cap in reporting.CAPS.items():
            report[name] = [{"excerpt": "\x01" * 240, "term": "\U0001f600" * 240} for _ in range(cap + 5)]
        reporting.finish(report)
        self.assertLess(len(reporting.serialize(report)), reporting.MAX_OUTPUT)
        self.assertGreater(report["truncation"]["output_budget_dropped"], 0)
        for name in reporting.CAPS:
            counts = report["truncation"]["counts"][name]
            self.assertEqual(counts["returned"], len(report[name]))
            self.assertEqual(counts["total"], counts["returned"] + counts["omitted"])
        self.assertEqual(report["status"], "partial")

    def test_cli_hash_determinism_and_no_source_writes(self):
        root = SCRIPT.parent
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()}
        text = "# 日本語\r\nAPI とは何か。\n$(touch should-not-exist)\n"
        payload = {"text": text, "modes": ["outline", "structure", "notation"]}
        code, report, wire = self.cli(payload)
        self.assertEqual(code, 0)
        self.assertEqual(report["input_sha256"], hashlib.sha256(text.encode("utf-8")).hexdigest())
        self.assertEqual(wire, self.cli(payload)[2])
        self.assertIn("日本語".encode("utf-8"), wire)
        after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_cli_file_mode(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp, "draft.md")
            draft.write_text("新しい本文です。", encoding="utf-8")
            before = Path(tmp, "before.md")
            before.write_text("古い本文です。", encoding="utf-8")
            code, report, wire = self.cli(b"", ("--file", str(draft), "--original", str(before),
                                                "--modes", "revision,notation", "--stance", "explanation"))
            self.assertEqual(code, 0)
            self.assertEqual(report["request"]["modes"], ["notation", "revision"])
            self.assertEqual(report["request"]["stance"], "explanation")
            self.assertIn(b"\n  ", wire)
            code, report, _ = self.cli(b"", ("--file", str(Path(tmp, "missing.md"))))
            self.assertEqual((code, report["error"]["code"]), (1, "invalid_request"))

    def test_cli_malformed_requests(self):
        cases = [b"\xff", b"{", b"null", b"[]", b'{"text":"", "text":""}', b'{"text":NaN}',
                 b'{"text":"\\ud800"}', {}, {"text": True}, {"text": "", "other": 1},
                 {"text": "", "modes": None}, {"text": "", "modes": ["bad"]}, {"text": "", "genre": "x"},
                 {"text": "", "stance": None}, {"text": "", "original": "a", "modes": ["terms"]},
                 {"text": "a" * (entry.MAX_TEXT + 1)},
                 b" " * (entry.MAX_REQUEST + 1), b"[" * 2000]
        for payload in cases:
            with self.subTest(payload=str(payload)[:60]):
                code, report, _ = self.cli(payload)
                self.assertEqual(code, 1)
                self.assertEqual(report["status"], "error")
                self.assertEqual(report["error"]["code"], "invalid_request")
                self.assertEqual(report["executed"], [])
        self.assertEqual(self.cli({"text": ""}, args=())[0], 1)

    def test_maximum_request_accepted(self):
        payload = b'{"text":"", "modes":[]}'
        payload += b" " * (entry.MAX_REQUEST - len(payload))
        self.assertEqual(self.cli(payload)[0], 0)

    def test_runtime_error_is_not_a_success(self):
        stdin = SimpleNamespace(buffer=BytesIO(b'{"text":"API"}'))
        stdout = SimpleNamespace(buffer=BytesIO())
        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout), \
                patch.object(entry, "inspect_text", side_effect=RuntimeError("private detail")):
            code = entry.main(["--request"])
        wire = stdout.buffer.getvalue()
        report = json.loads(wire)
        self.assertEqual((code, report["status"], report["error"]["code"]), (1, "error", "runtime_failure"))
        self.assertNotIn(b"private detail", wire)
        self.assertEqual(report["input_sha256"], hashlib.sha256(b"API").hexdigest())


if __name__ == "__main__":
    unittest.main()
