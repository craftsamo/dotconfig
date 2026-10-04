#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = [
#   "numpy",
#   "pykakasi>=2.3",
#   "torch>=2.4",
#   "transformers>=4.45,<5",
# ]
# ///
"""Round-trip reading check for the local Irodori-TTS server.

Each corpus sentence is turned into the text the provider would really send
(the shared Hermes TTS cleaner, then the plugin's own reading module), rendered
on the live server, transcribed and compared with the expected reading. The
score is a kana character error rate (Kana-CER).

The ASR is sbintuitions/kana-whisper (MIT), a Whisper large-v3-turbo fine-tune
that writes what it hears as katakana. That matters: an ordinary Whisper writes
kanji, and its language model writes 人気 whether the voice said ひとけ or
にんき, so a misread kanji is invisible. Kana output keeps the reading.

Corpus format (UTF-8, tab-separated, ``#`` starts a comment line, ``\\n`` in
the text is a line break):

    category <TAB> text <TAB> expected reading

Write the expected reading in kana as it is pronounced: particles は/へ as
わ/え, everything else in ordinary spelling (東京 as とうきょう). Both sides
are reduced to a pronunciation key before scoring -- を as お, ー and spelled
long vowels alike -- so the transcript's キョーワ and the corpus' きょうわ
agree. Several accepted readings are separated by ``|`` and the closest one
is scored. An empty column falls back to pykakasi's reading, which is wrong
often enough on numbers and context-dependent kanji that a written reading is
preferred.

Audio is scored after the provider's own WAV repair (``polish``), because
that is what a listener gets; ``--no-polish`` scores the raw server output.
Requests are paced the way the provider paces them (sentence-aligned chunks,
each with a duration cap); ``--no-pacing`` sends the text whole and leaves
length to the server's predictor, as the provider did before.

Findings are CANDIDATES: ASR can still mishear. Confirm by ear
(``--keep-audio DIR``) before acting on one; ``--from-audio DIR`` re-scores
kept renders without synthesizing again.

    hermes/scripts/irodori_tts_reading_check.py \\
        --file hermes/scripts/irodori_tts_reading_corpus.tsv --seeds 1,2,3 \\
        --json-out after.json --keep-audio after-wav
    hermes/scripts/irodori_tts_reading_check.py --compare baseline.json after.json
"""

from __future__ import annotations

import argparse
import difflib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_READING = _HERE.parent / "plugins" / "tts" / "irodori-tts" / "reading.py"
_KATA_TO_HIRA = {code: code - 0x60 for code in range(0x30A1, 0x30F7)}
_BUSY_RETRIES = 40
_BUSY_SLEEP_SECONDS = 15.0
_ASR_MODEL = "sbintuitions/kana-whisper"


@dataclass
class Case:
    category: str
    text: str
    expected: str


# --------------------------------------------------------------------------
# Pronunciation key
# --------------------------------------------------------------------------

_ROWS = {
    "a": "あかがさざただなはばぱまやらわぁゃゎ",
    "i": "いきぎしじちぢにひびぴみりぃ",
    "u": "うくぐすずつづぬふぶぷむゆるぅゅ",
    "e": "えけげせぜてでねへべぺめれぇ",
    "o": "おこごそぞとどのほぼぽもよろをぉょ",
}
_VOWEL_OF = {kana: vowel for vowel, row in _ROWS.items() for kana in row}
_VOWEL_KANA = {"a": "あ", "i": "い", "u": "う", "e": "え", "o": "お"}
# Only spellings that never change the sound. は/へ are NOT folded: the ASR
# writes the particle as ワ/エ and a lexical は as ハ, so folding them would let
# はし and わし score alike; corpus readings spell particles as heard instead.
_SAME_SOUND = str.maketrans({"を": "お", "ぢ": "じ", "づ": "ず"})


def pronunciation_key(text: str) -> str:
    """Reduce kana to how it sounds, identically for both sides.

    Lenient only where spelling and sound part (を/お, おう/おー, えい/えー);
    strict on everything a listener would hear as a different word.
    """
    kana = [
        ch for ch in text.translate(_KATA_TO_HIRA) if "ぁ" <= ch <= "ゖ" or ch == "ー"
    ]
    out: list[str] = []
    for ch in kana:
        ch = ch.translate(_SAME_SOUND)
        previous = _VOWEL_OF.get(out[-1]) if out else None
        if ch == "ー":
            if previous:
                out.append(_VOWEL_KANA[previous])
            continue
        if (previous, ch) in (("o", "う"), ("e", "い")):
            ch = "お" if previous == "o" else "え"
        out.append(ch)
    return "".join(out)


def edit_distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb))
            )
        previous = current
    return previous[-1]


def diff_spans(expected: str, heard: str, context: int = 2) -> list[dict[str, str]]:
    matcher = difflib.SequenceMatcher(a=expected, b=heard, autojunk=False)
    return [
        {
            "expected": expected[max(0, i1 - context) : i2 + context],
            "heard": heard[max(0, j1 - context) : j2 + context],
        }
        for tag, i1, i2, j1, j2 in matcher.get_opcodes()
        if tag != "equal"
    ]


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def hermes_agent_dir() -> Path:
    override = os.environ.get("HERMES_AGENT_DIR")
    if override:
        return Path(override).expanduser()
    try:
        root = subprocess.run(
            ["ghq", "root"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        root = str(Path.home() / "ghq")
    return Path(root) / "github.com" / "NousResearch" / "hermes-agent"


def load_cleaner():
    """The shared cleaner every Hermes TTS call runs before the provider."""
    path = hermes_agent_dir() / "tools" / "tts_text_normalize.py"
    return load_module("hermes_tts_text_normalize", path).prepare_spoken_text


def load_corpus(path: Path) -> list[Case]:
    cases: list[Case] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) < 2:
            raise SystemExit(f"{path}:{number}: need at least category and text")
        cases.append(
            Case(
                category=cols[0].strip(),
                text=cols[1].strip().replace("\\n", "\n"),
                expected=cols[2].strip() if len(cols) > 2 else "",
            )
        )
    return cases


def load_plugin():
    """The provider package itself, for its WAV repair and chunk joining. It
    imports Hermes' TTSProvider base class; a stand-in keeps this script
    independent of a Hermes runtime."""
    import types

    if "agent.tts_provider" not in sys.modules:
        agent = sys.modules.setdefault("agent", types.ModuleType("agent"))
        stub = types.ModuleType("agent.tts_provider")
        stub.TTSProvider = type("TTSProvider", (), {})
        agent.tts_provider = stub
        sys.modules["agent.tts_provider"] = stub
    plugin_dir = _READING.parent
    spec = importlib.util.spec_from_file_location(
        "irodori_tts_for_check", plugin_dir / "__init__.py",
        submodule_search_locations=[str(plugin_dir)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_polish(module):
    """The provider's own WAV repair, so trailing junk it would trim is not
    scored as a misreading."""

    def polish(wav: bytes) -> bytes:
        samples, rate = module._decode_wav(wav)
        cleaned, _ = module.polish(samples, rate)
        return module._encode_wav(cleaned, rate)

    return polish


def legacy_lexicon(terms: dict[str, str]):
    """Key matching as the provider did before reading.py: \\b fences, which
    Python's Unicode \\w made fail whenever a name touched Japanese."""
    if not terms:
        return None
    return re.compile(
        "|".join(
            (r"\b" if k[0].isascii() and k[0].isalnum() else "")
            + re.escape(k)
            + (r"\b" if k[-1].isascii() and k[-1].isalnum() else "")
            for k in sorted(terms, key=len, reverse=True)
        )
    )


# --------------------------------------------------------------------------
# Server and ASR
# --------------------------------------------------------------------------


def synthesize(server: str, text: str, voice: str | None, options: dict) -> bytes:
    payload: dict[str, object] = {"input": text, "model": "irodori-tts"}
    if voice:
        payload["voice"] = voice
    if options:
        payload["irodori"] = options
    request = urllib.request.Request(
        server.rstrip("/") + "/v1/audio/speech",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "audio/wav"},
        method="POST",
    )
    for attempt in range(_BUSY_RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            # The server renders one request at a time and Hermes shares it.
            if exc.code in (429, 503) and attempt < _BUSY_RETRIES - 1:
                exc.close()
                time.sleep(_BUSY_SLEEP_SECONDS)
                continue
            raise
    raise RuntimeError("synthesizer stayed busy")


def server_identity(server: str) -> dict:
    try:
        with urllib.request.urlopen(server.rstrip("/") + "/health", timeout=5) as resp:
            health = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - informational only
        return {"error": str(exc)}
    runtime = health.get("runtime", {})
    return {
        "checkpoint": health.get("model", {}).get("hf_checkpoint"),
        "snapshot": runtime.get("checkpoint"),
        "defaults": health.get("defaults"),
    }


def pcm16k(wav: bytes):
    """Decode to 16 kHz mono float32 with ffmpeg (no audio library needed)."""
    import numpy as np

    result = subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-i", "pipe:0",
         "-f", "f32le", "-ac", "1", "-ar", "16000", "pipe:1"],
        input=wav, capture_output=True, check=True,
    )
    return np.frombuffer(result.stdout, dtype=np.float32)


def load_asr(model_id: str, device: str):
    import torch
    from transformers import pipeline
    from transformers.utils import logging as hf_logging

    hf_logging.set_verbosity_error()

    if device == "auto":
        device = "mps" if torch.backends.mps.is_available() else "cpu"
    asr = pipeline(
        "automatic-speech-recognition",
        model=model_id,
        torch_dtype=torch.float32,
        device=device,
    )

    def transcribe(wav: bytes) -> str:
        result = asr(
            {"raw": pcm16k(wav), "sampling_rate": 16000},
            generate_kwargs={"language": "ja", "task": "transcribe"},
        )
        return str(result["text"]).strip()

    return transcribe


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def parse_option(raw: str) -> tuple[str, object]:
    key, sep, value = raw.partition("=")
    if not key or not sep:
        raise argparse.ArgumentTypeError(f"--option needs key=value, got {raw!r}")
    try:
        return key, json.loads(value)
    except json.JSONDecodeError:
        return key, value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--text", help="one sentence to check (expected via pykakasi)")
    mode.add_argument("--file", type=Path, help="corpus TSV (see module docstring)")
    mode.add_argument(
        "--compare", nargs="+", type=Path, metavar="JSON",
        help="summarise saved --json-out runs side by side and exit",
    )
    parser.add_argument("--server", default="http://127.0.0.1:10103")
    parser.add_argument("--voice", help="registered voice id (server default if omitted)")
    parser.add_argument("--seeds", default="1", help="comma-separated seeds, e.g. 1,2,3")
    parser.add_argument(
        "--option", action="append", type=parse_option, default=[], metavar="KEY=VALUE",
        help="extra irodori request option (JSON value), e.g. cfg_scale_text=4.0",
    )
    parser.add_argument(
        "--pipeline", choices=("chain", "raw"), default="chain",
        help="chain: shared cleaner + plugin reading module (default); raw: send as is",
    )
    parser.add_argument(
        "--no-frontend", action="store_true",
        help="skip the reading frontend (lexicon only), i.e. the old behaviour",
    )
    parser.add_argument(
        "--numerals", choices=("kanji", "digits", "kana"), default=None,
        help="numeral style for the reading frontend (default: the provider's)",
    )
    parser.add_argument(
        "--legacy-lexicon", action="store_true",
        help="match Latin lexicon keys the old way (they never fired next to "
        "Japanese); for baselines only",
    )
    parser.add_argument(
        "--lexicon", type=Path,
        help="lexicon JSON; default is the plugin's runtime lexicon if present",
    )
    parser.add_argument(
        "--no-pacing", action="store_true",
        help="send each sentence whole without the provider's chunking and "
        "duration cap (the server chunks and the predictor alone sets length)",
    )
    parser.add_argument(
        "--no-polish", action="store_true",
        help="score the raw server audio instead of the provider's repaired WAV",
    )
    parser.add_argument("--category", action="append", help="only run these categories")
    parser.add_argument("--asr-model", default=_ASR_MODEL)
    parser.add_argument("--asr-device", default="cpu", help="cpu, mps or auto")
    parser.add_argument("--json-out", type=Path, help="write the full report here")
    parser.add_argument("--keep-audio", type=Path, help="directory to keep the wavs")
    parser.add_argument(
        "--from-audio", type=Path, metavar="DIR",
        help="score wavs kept by an earlier --keep-audio run instead of synthesizing",
    )
    return parser


def summarise(results: list[dict]) -> dict:
    def stats(rows: list[dict]) -> dict:
        edits = sum(r["edits"] for r in rows)
        length = sum(r["expected_len"] for r in rows)
        return {
            "cer": edits / length if length else 0.0,
            "bad": sum(1 for r in rows if r["edits"]),
            "n": len(rows),
        }

    by_category: dict[str, list[dict]] = {}
    for row in results:
        by_category.setdefault(row["category"], []).append(row)
    return {
        "overall": stats(results),
        "categories": {name: stats(rows) for name, rows in sorted(by_category.items())},
    }


def compare(paths: list[Path]) -> int:
    runs = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    categories = sorted({c for run in runs for c in run["summary"]["categories"]})
    width = max([len(c) for c in categories] + [8])
    print("category".ljust(width) + "".join(f"  {p.stem[:18]:>18}" for p in paths))
    for category in categories + ["ALL"]:
        row = category.ljust(width)
        for run in runs:
            stats = (
                run["summary"]["overall"]
                if category == "ALL"
                else run["summary"]["categories"].get(category)
            )
            row += f"  {'-':>18}" if not stats else (
                f"  {stats['cer'] * 100:6.2f}% {stats['bad']:>3}/{stats['n']:<3}    "
            )
        print(row)
    print("\ncell = Kana-CER, then renders with any error / renders")
    return 0


def main() -> int:
    args = build_parser().parse_args()
    if args.compare:
        return compare(args.compare)

    cases = [Case("adhoc", args.text, "")] if args.text else load_corpus(args.file)
    numbered = list(enumerate(cases, 1))
    if args.category:
        numbered = [(i, c) for i, c in numbered if c.category in set(args.category)]
    if not numbered:
        print("no sentences to check", file=sys.stderr)
        return 2
    seeds = [int(seed) for seed in args.seeds.split(",") if seed.strip()]
    options = dict(args.option)

    reading = load_module("irodori_reading_for_check", _READING)
    terms: dict[str, str] = {}
    lexicon_file = args.lexicon or reading.lexicon_path()
    if lexicon_file.exists():
        terms = reading.read_lexicon(lexicon_file)
    lexicon = (terms, reading.compile_lexicon(terms))
    request_lexicon = (terms, legacy_lexicon(terms)) if args.legacy_lexicon else lexicon
    cleaner = load_cleaner() if args.pipeline == "chain" else None

    import pykakasi

    kks = pykakasi.kakasi()
    transcribe = load_asr(args.asr_model, args.asr_device)
    plugin = load_plugin()
    polish = None if args.no_polish else load_polish(plugin)
    paced = args.pipeline == "chain" and not args.no_pacing

    def render(text: str, seed: int) -> bytes:
        """What the provider would request: its chunks, caps and join."""
        if not paced:
            return synthesize(args.server, text, args.voice, {**options, "seed": seed})
        parts = [
            synthesize(
                args.server, chunk, args.voice,
                {
                    **plugin.request_options(chunk, caption="caption" in options),
                    **options,
                    "seed": seed,
                },
            )
            for chunk in plugin.split_for_speech(text)
        ]
        if len(parts) == 1:
            return parts[0]
        return plugin.IrodoriTTSProvider._join(parts, trim=not args.no_polish)
    if args.keep_audio:
        args.keep_audio.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    started = time.monotonic()
    for index, case in numbered:
        sent = cleaner(case.text, max_chars=None) if cleaner else case.text
        sent = reading.prepare_text(
            sent, lexicon=request_lexicon, frontend=not args.no_frontend,
            **({"numerals": args.numerals} if args.numerals else {}),
        )
        written = case.expected or "".join(
            item["hira"]
            for item in kks.convert(reading.prepare_text(case.text, lexicon=lexicon))
        )
        # "|" separates accepted readings (ごひゃくきろ|ごひゃっきろ); the
        # closest one is scored.
        alternatives = [pronunciation_key(alt) for alt in written.split("|") if alt.strip()]
        for seed in seeds:
            name = f"{index:03d}-{case.category}-s{seed}.wav"
            if args.from_audio:
                audio = (args.from_audio / name).read_bytes()
            else:
                audio = render(sent, seed)
            if args.keep_audio:
                (args.keep_audio / name).write_bytes(audio)
            heard_text = transcribe(polish(audio) if polish else audio)
            heard = pronunciation_key(heard_text)
            edits, expected = min(
                (edit_distance(alt, heard), alt) for alt in alternatives
            )
            row = {
                "index": index,
                "category": case.category,
                "seed": seed,
                "text": case.text,
                "sent": sent,
                "heard_text": heard_text,
                "expected": expected,
                "heard": heard,
                "edits": edits,
                "expected_len": len(expected),
                "spans": diff_spans(expected, heard) if edits else [],
            }
            results.append(row)
            print(
                f"{'OK' if not edits else '??'} [{index:03d} {case.category} s{seed}] "
                f"{case.text!r}  cer {edits / max(1, len(expected)):.1%}",
                flush=True,
            )
            if edits:
                print(f"     sent : {sent}")
                print(f"     heard: {heard_text}")
                for span in row["spans"][:4]:
                    print(f"     「{span['expected']}」→「{span['heard']}」")

    summary = summarise(results)
    report = {
        "server": server_identity(args.server),
        "asr_model": args.asr_model,
        "pipeline": args.pipeline,
        "frontend": not args.no_frontend,
        "numerals": args.numerals,
        "lexicon_terms": len(terms),
        "legacy_lexicon": args.legacy_lexicon,
        "polish": not args.no_polish,
        "pacing": paced,
        "options": options,
        "seeds": seeds,
        "from_audio": str(args.from_audio) if args.from_audio else None,
        "elapsed_s": round(time.monotonic() - started, 1),
        "summary": summary,
        "results": results,
    }
    if args.json_out:
        args.json_out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    overall = summary["overall"]
    print(f"\nKana-CER {overall['cer']:.2%}  ({overall['bad']}/{overall['n']} renders with errors)")
    for name, stats in summary["categories"].items():
        print(f"  {name:<10} {stats['cer']:6.2%}  {stats['bad']}/{stats['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
