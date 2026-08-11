#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "faster-whisper>=1.1",
#   "pykakasi>=2.3",
# ]
# ///
"""Round-trip misreading detector for the local Qwen3-TTS server.

Synthesizes each sentence through the running server, transcribes the audio
with faster-whisper, converts both the source text and the transcript into
kana, and reports spans where the heard reading disagrees with the expected
reading. Each finding is a CANDIDATE misreading: ASR can mask real errors
(its language model may "correct" what it hears) and dictionary readings of
numbers or proper nouns can be wrong, so confirm by ear before adding an
entry to the voice's pronunciation lexicon.

Run with uv (dependencies resolve automatically):

    hermes/scripts/qwen3_tts_reading_check.py --text "締切は金曜日です。"
    hermes/scripts/qwen3_tts_reading_check.py --file corpus.txt --json
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_SENTENCE_PATTERN = re.compile(r"[^。！？!?\n]+(?:[。！？!?]+[」』）】]*)?")
_KATA_TO_HIRA = {code: code - 0x60 for code in range(0x30A1, 0x30F7)}
_KANA_PATTERN = re.compile(r"[ぁ-ゖー]")
_BUSY_RETRIES = 5
_BUSY_SLEEP_SECONDS = 3.0


@dataclass(frozen=True)
class Suspect:
    surface: str
    expected: str
    heard: str


def split_sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in _SENTENCE_PATTERN.findall(text)
        if sentence.strip()
    ]


def normalize_kana(text: str) -> str:
    """Katakana to hiragana, then keep only kana and the long-vowel mark."""
    return "".join(_KANA_PATTERN.findall(text.translate(_KATA_TO_HIRA)))


def apply_lexicon(text: str, lexicon: dict[str, str]) -> str:
    """Mirror the server's substitution: longest surface form first."""
    for surface in sorted(lexicon, key=len, reverse=True):
        text = text.replace(surface, lexicon[surface])
    return text


def load_number_expander():
    """Borrow expand_japanese_numbers from the server module next door.

    The server applies it after the lexicon for Japanese voices; the
    expected side must mirror that or every numeric sentence reports a
    false mismatch.
    """
    import importlib.util

    path = Path(__file__).resolve().parent / "qwen3_tts_server.py"
    spec = importlib.util.spec_from_file_location("qwen3_tts_server_for_check", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.expand_japanese_numbers


def find_suspects(
    tokens: list[tuple[str, str]], heard_kana: str
) -> tuple[list[Suspect], float]:
    """Align expected token readings against the heard kana.

    tokens are (surface, reading) pairs for one sentence. Returns the
    suspect spans widened to token boundaries plus the overall similarity.
    """
    expected = ""
    bounds: list[tuple[int, int, str]] = []
    for surface, reading in tokens:
        kana = normalize_kana(reading)
        if kana:
            bounds.append((len(expected), len(expected) + len(kana), surface))
            expected += kana

    matcher = difflib.SequenceMatcher(a=expected, b=heard_kana, autojunk=False)
    suspects: list[Suspect] = []
    seen: set[tuple[str, str]] = set()
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        overlapping = [
            entry
            for entry in bounds
            if entry[0] < max(i2, i1 + 1) and entry[1] > i1
        ]
        if not overlapping:
            continue
        start = min(entry[0] for entry in overlapping)
        end = max(entry[1] for entry in overlapping)
        surface = "".join(entry[2] for entry in overlapping)
        heard_start = max(0, j1 - (i1 - start))
        heard_end = min(len(heard_kana), j2 + (end - i2))
        suspect = Suspect(
            surface=surface,
            expected=expected[start:end],
            heard=heard_kana[heard_start:heard_end],
        )
        key = (suspect.surface, suspect.heard)
        if suspect.expected != suspect.heard and key not in seen:
            seen.add(key)
            suspects.append(suspect)
    return suspects, matcher.ratio()


def synthesize(server: str, text: str, voice: str | None) -> bytes:
    payload: dict[str, str] = {"input": text}
    if voice:
        payload["voice"] = voice
    request = urllib.request.Request(
        server.rstrip("/") + "/v1/audio/speech",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(_BUSY_RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 503 and attempt < _BUSY_RETRIES - 1:
                exc.close()
                time.sleep(_BUSY_SLEEP_SECONDS)
                continue
            raise
    raise RuntimeError("synthesizer stayed busy")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="text to check")
    source.add_argument("--file", type=Path, help="UTF-8 text file to check")
    parser.add_argument("--voice", help="registered voice id (default voice if omitted)")
    parser.add_argument(
        "--lexicon",
        type=Path,
        help="voice lexicon JSON; applied to the expected side so registered "
        "substitutions stop reporting as mismatches",
    )
    parser.add_argument("--server", default="http://127.0.0.1:10102")
    parser.add_argument("--asr-model", default="medium", help="faster-whisper model")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--keep-audio", type=Path, help="directory to keep synthesized wavs"
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    text = args.text if args.text else args.file.read_text(encoding="utf-8")
    sentences = split_sentences(text)
    if not sentences:
        print("no sentences found", file=sys.stderr)
        return 2
    lexicon: dict[str, str] = {}
    if args.lexicon:
        lexicon = json.loads(args.lexicon.read_text(encoding="utf-8"))

    import pykakasi
    from faster_whisper import WhisperModel

    kks = pykakasi.kakasi()
    asr = WhisperModel(args.asr_model, device="cpu", compute_type="int8")
    expand_numbers = load_number_expander()
    if args.keep_audio:
        args.keep_audio.mkdir(parents=True, exist_ok=True)

    report: list[dict[str, object]] = []
    for index, sentence in enumerate(sentences, start=1):
        audio = synthesize(args.server, sentence, args.voice)
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav") as handle:
            handle.write(audio)
            handle.flush()
            if args.keep_audio:
                (args.keep_audio / f"sentence-{index:03d}.wav").write_bytes(audio)
            segments, _ = asr.transcribe(
                handle.name, language="ja", beam_size=5, vad_filter=True
            )
            heard_text = "".join(segment.text for segment in segments)

        expected_source = expand_numbers(apply_lexicon(sentence, lexicon))
        tokens = [
            (item["orig"], item["hira"]) for item in kks.convert(expected_source)
        ]
        heard_kana = normalize_kana(
            "".join(
                item["hira"] for item in kks.convert(expand_numbers(heard_text))
            )
        )
        suspects, ratio = find_suspects(tokens, heard_kana)
        report.append(
            {
                "sentence": sentence,
                "heard": heard_text.strip(),
                "similarity": round(ratio, 3),
                "suspects": [
                    {
                        "surface": suspect.surface,
                        "expected": suspect.expected,
                        "heard": suspect.heard,
                    }
                    for suspect in suspects
                ],
            }
        )
        if not args.json:
            marker = "OK " if not suspects else "?? "
            print(f"{marker}[{index}] {sentence} (similarity {ratio:.3f})")
            for suspect in suspects:
                print(
                    f"     {suspect.surface}: expected "
                    f"「{suspect.expected}」 heard 「{suspect.heard}」"
                )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        candidates = {
            suspect["surface"]: suspect["expected"]
            for entry in report
            for suspect in entry["suspects"]
        }
        if candidates:
            print("\nlexicon candidates (confirm by ear before adding):")
            for surface, expected in candidates.items():
                print(f'  "{surface}": "{expected}"')
        else:
            print("\nno misreading candidates found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
