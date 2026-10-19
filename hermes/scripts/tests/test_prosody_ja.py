"""Tests for prosody-ja.py, the Japanese accent and delivery check of analyze-speech.

The script's heavy runtime (torch, librosa, pyopenjtalk) is imported lazily,
so its accent, speaker and delivery logic is tested here with synthetic morae
and lines; the dictionary tests run only where pyopenjtalk is importable, and
the numpy-dependent ones skip without numpy, as the other suites do.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import hermes_yaml as yaml

HERMES_ROOT = Path(__file__).resolve().parents[2]
PIPELINE = HERMES_ROOT / "profiles" / "audio-creator" / "skills" / "audio-creator-pipeline"
SCRIPT = PIPELINE / "scripts" / "prosody-ja.py"

try:
    import numpy  # noqa: F401
    HAVE_NUMPY = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_NUMPY = False

try:
    import pyopenjtalk  # noqa: F401
    HAVE_DICTIONARY = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_DICTIONARY = False


def load_module():
    spec = importlib.util.spec_from_file_location("prosody_ja", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prosody = load_module()


def mora(phones, a2, nucleus=False, st=None, surface="", latin=False, phrase=0):
    return {"phrase": phrase, "a2": a2, "nucleus": nucleus, "phones": phones, "st": st, "surface": surface,
            "latin": latin, "pause_before": False, "period_before": False}


def phrase(kana_phones, nucleus_at, sts, surface="", latin=False):
    return [mora(p, i + 1, nucleus=(i + 1 == nucleus_at), st=s, surface=surface, latin=latin)
            for i, (p, s) in enumerate(zip(kana_phones, sts))]


ICHIBAN = [["i"], ["ch", "i"], ["b", "a"], ["N"]]


class Nucleus(unittest.TestCase):
    def test_first_lasting_fall_is_the_nucleus(self):
        self.assertEqual(prosody.realized_nucleus([2.0, 10.0, 12.0, 4.0, 3.0]), (3, 8.0))
        self.assertEqual(prosody.realized_nucleus([10.0, 4.0, 3.0]), (1, 6.0))

    def test_a_fall_that_recovers_is_not_one(self):
        got, largest = prosody.realized_nucleus([5.0, 2.0, 6.0, 7.0])
        self.assertIsNone(got)
        self.assertEqual(largest, 3.0)

    def test_level_and_rising_phrases_have_none(self):
        self.assertEqual(prosody.realized_nucleus([3.0, 5.0, 6.0, 6.5])[0], None)
        self.assertEqual(prosody.realized_nucleus([None, 4.0, 4.5, None])[0], None)


class PhraseCheck(unittest.TestCase):
    def test_level_word_read_level_is_fine(self):
        result = prosody.check_phrase(phrase(ICHIBAN, None, [2.0, 8.0, 9.0, 8.5], "一番"))
        self.assertTrue(result["ok"])
        self.assertEqual((result["expected"], result["heard"]), ("イチバン", "イチバン"))

    def test_accented_word_read_level_is_a_candidate(self):
        result = prosody.check_phrase(phrase(ICHIBAN, 2, [2.2, 10.0, 12.9, 12.4], "一番"))
        self.assertFalse(result["ok"])
        self.assertEqual((result["expected"], result["heard"]), ("イチ↓バン", "イチバン"))

    def test_level_word_with_a_clear_fall_is_a_candidate(self):
        result = prosody.check_phrase(phrase([["a"], ["N"], ["sh", "i"], ["N"]], None, [10.9, 11.5, 0.9, 1.7], "安心"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["heard"], "アン↓シン")

    def test_a_fall_one_mora_off_is_alignment_jitter(self):
        self.assertTrue(prosody.check_phrase(phrase(ICHIBAN, 2, [2.0, 10.0, 11.0, 3.0]))["ok"])

    def test_final_lowering_of_a_level_word_is_fine(self):
        self.assertTrue(prosody.check_phrase(phrase(ICHIBAN, None, [4.4, 5.2, 4.9, 3.2]))["ok"])
        self.assertFalse(prosody.check_phrase(phrase(ICHIBAN, None, [4.4, 5.2, 9.0, 3.2]))["ok"])

    def test_a_level_reading_of_an_accented_word_needs_a_span_to_say_so(self):
        self.assertTrue(prosody.check_phrase(phrase(ICHIBAN, 2, [4.0, 5.0, 5.5, 5.0]))["ok"])  # too level to tell

    def test_latin_words_are_skipped_and_short_phrases_unchecked(self):
        result = prosody.check_phrase(phrase([["o"], ["o"], ["p", "i"]], None, [1.0, 9.0, 2.0], "OpenAI", latin=True))
        self.assertTrue(result["ok"])
        self.assertIn("letter by letter", result["skipped"])
        self.assertIsNone(prosody.check_phrase(phrase([["a"]], None, [1.0])))
        self.assertIsNone(prosody.check_phrase(phrase(ICHIBAN, 2, [None, None, 3.0, 4.0])))


class Kana(unittest.TestCase):
    def test_mora_kana_covers_the_rows_the_dictionary_uses(self):
        for phones, kana in ((["sh", "i"], "シ"), (["ky", "o"], "キョ"), (["N"], "ン"), (["cl"], "ッ"),
                             (["w", "i"], "ウィ"), (["ts", "u"], "ツ"), (["f", "a"], "ファ"), (["k", "U"], "ク"),
                             (["a"], "ア")):
            self.assertEqual(prosody.mora_kana(phones), kana, phones)

    def test_kana_of_marks_the_nucleus_but_never_a_final_one(self):
        morae = phrase(ICHIBAN, 2, [0, 0, 0, 0])
        self.assertEqual(prosody.kana_of(morae, 2), "イチ↓バン")
        self.assertEqual(prosody.kana_of(morae, 4), "イチバン")
        self.assertEqual(prosody.kana_of(morae, None), "イチバン")


@unittest.skipUnless(HAVE_NUMPY, "numpy is not installed")
class Speakers(unittest.TestCase):
    def test_three_voices_cluster_from_the_lowest(self):
        labels = prosody.cluster_speakers([20.0, 2.0, 3.0, 11.0, 21.0, 4.0, 10.0])
        self.assertEqual(labels, [2, 0, 0, 1, 2, 0, 1])

    def test_close_clusters_are_one_speaker(self):
        self.assertEqual(set(prosody.cluster_speakers([2.0, 3.0, 4.0, 4.5, 5.0, 3.5])), {0})

    def test_few_lines_are_ranked(self):
        self.assertEqual(prosody.cluster_speakers([9.0, 2.0]), [1, 0])


def line(at, rate, pitch_range, speaker=0, morae=10, pauses=(), at_period=()):
    return {"at": at, "text": "x", "morae": morae, "rate": rate, "pitch_range": pitch_range, "speaker": speaker,
            "pauses": list(pauses), "pauses_at_period": list(at_period), "accent": []}


@unittest.skipUnless(HAVE_NUMPY, "numpy is not installed")
class Delivery(unittest.TestCase):
    def test_each_line_is_compared_with_its_own_speaker(self):
        lines = [line(0, 6.0, 10.0), line(10, 6.5, 11.0), line(20, 3.7, 11.0), line(30, 9.0, 4.0),
                 line(40, 15.0, 9.0, speaker=1, morae=7), line(50, 14.0, 9.5, speaker=1), line(60, 13.5, 10.0, speaker=1)]
        found = prosody.delivery_findings(lines)
        self.assertEqual(found, [
            "0:20 | voice | pace: 3.7 morae/s against speaker 0's 6.2 | prosody-ja speaker 0 | confirm",
            "0:30 | voice | pace: 9.0 morae/s against speaker 0's 6.2 | prosody-ja speaker 0 | confirm",
            "0:30 | voice | flat: pitch range 4.0 st against speaker 0's 10.5 | prosody-ja speaker 0 | confirm",
        ])

    def test_short_lines_are_not_compared_for_pace(self):
        lines = [line(0, 6.0, 10.0), line(10, 6.0, 10.0), line(20, 15.0, 10.0, morae=4)]
        self.assertEqual(prosody.delivery_findings(lines), [])

    def test_pauses_inside_a_line(self):
        lines = [line(0, 6.0, 10.0, pauses=[0.3, 1.5]), line(10, 6.0, 10.0, pauses=[0.04], at_period=[0.04])]
        self.assertEqual(prosody.delivery_findings(lines), [
            "0:00 | voice | pause: a pause of 1.50 s inside the line | prosody-ja | confirm",
            "0:10 | voice | pause: no pause at a 。 inside the line (0.04 s) | prosody-ja | confirm",
        ])


class AccentLines(unittest.TestCase):
    def test_lines_name_the_word_the_patterns_and_the_pitches(self):
        lines = [{"at": 45, "accent": [
            {"surface": "一番", "expected": "イチ↓バン", "heard": "イチバン", "ok": False, "st": [2.2, 10.0, 12.9, 12.4]},
            {"surface": "会社", "expected": "カイシャ", "heard": "カイシャ", "ok": True, "st": [1, 2, 2]},
            {"surface": "OpenAI", "kana": "オオピイ", "skipped": "spelt letter by letter", "ok": True, "st": []},
        ]}]
        self.assertEqual(prosody.accent_findings(lines), [
            "0:45 | voice | accent: 「一番」イチ↓バン in the dictionary, heard イチバン (st [2.2, 10.0, 12.9, 12.4]) "
            "| prosody-ja | confirm"])


class Captions(unittest.TestCase):
    def test_captions_keep_their_second_and_drop_blank_lines(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "captions.txt"
            path.write_text("[0:00] はじめに\n\n[1:05]\n[1:10] 終わり\nno time\n", encoding="utf-8")
            self.assertEqual(prosody.read_captions(str(path)),
                             [{"at": 0, "text": "はじめに"}, {"at": 70, "text": "終わり"}])


@unittest.skipUnless(HAVE_DICTIONARY, "pyopenjtalk is not installed")
class Dictionary(unittest.TestCase):
    def test_morae_carry_the_accent_the_surface_and_the_period(self):
        morae = prosody.morae_of("一番。安心")
        self.assertEqual([m["kana"] if "kana" in m else "".join(m["phones"]) for m in morae][:4], ["i", "chi", "ba", "N"])
        self.assertEqual([m["nucleus"] for m in morae[:4]], [False, True, False, False])
        self.assertEqual(morae[0]["surface"], "一番")
        self.assertTrue(morae[4]["period_before"])
        self.assertTrue(all(not m["latin"] for m in morae))

    def test_latin_words_are_flagged(self):
        morae = prosody.morae_of("OpenAIは")
        self.assertTrue(morae[0]["latin"])
        self.assertFalse(morae[-1]["latin"])


class LeafContract(unittest.TestCase):
    def test_leaf_takes_captions_and_runs_the_check_under_uv(self):
        text = (PIPELINE / "analyze" / "speech" / "SKILL.md").read_text()
        meta = yaml.safe_load(text.split("---", 2)[1])
        self.assertEqual(meta["metadata"]["hermes"]["form"]["captions"]["type"], "file")
        flat = " ".join(text.split())
        for rule in ('uv run "${HERMES_SKILL_DIR}/../../scripts/prosody-ja.py" analyze',
                     "quote them as they are, never reworded", "the dictionary accent is unreliable",
                     "never a download inside the job", "`prosody.md` copied under a named `deliver`"):
            self.assertIn(rule, flat)
        self.assertTrue(SCRIPT.is_file())
        head = SCRIPT.read_text().splitlines()[:12]
        self.assertEqual(head[0], "#!/usr/bin/env -S uv run --script")
        self.assertTrue(any("torchaudio==" in l for l in head), "dependencies are pinned")


if __name__ == "__main__":
    unittest.main()
