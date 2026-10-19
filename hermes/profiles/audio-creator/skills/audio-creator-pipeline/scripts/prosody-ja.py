#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11,<3.12"
# dependencies = [
#   "pyopenjtalk-plus==0.4.1.post9",
#   "librosa==0.11.0",
#   "torch==2.14.1",
#   "torchaudio==2.11.0",
#   "numpy==2.4.6",
#   "soundfile==0.14.0",
# ]
# ///
"""Japanese accent and delivery check of narrated audio against its timed script.

    prosody-ja.py analyze <wav> --captions <captions.txt> --out <result.json> [--lines <prosody.md>] [--accent] [--tension]
    prosody-ja.py prepare                      fetch the alignment model once (a maintainer step)

The captions are ``[m:ss] text`` lines: the words as written, each line's
start. For every line: the time of each mora from MMS forced alignment (the
morae and their expected accent from the pyopenjtalk dictionary's
full-context labels), the pitch of each mora (pyin, semitones) and its
level. Lines are grouped into speakers by their median pitch, and each
speaker's lines are compared with each other: morae per second, the pauses
at 、 and 。, the pitch range, and the vocal effort of the line's start (the
spectral tilt of its first 0.6 s, 1-4 kHz against 100-1000 Hz) against the
speaker's lines.

Every candidate is written as one ``m:ss | voice | <item>: … | … | confirm``
line, the item being one of the inspection catalog's delivery items:
``pace``, ``pause``, ``flat``, and with ``--tension`` the ``tension`` of a
line that starts with a pushed voice: its first 0.6 s much brighter than
the speaker's usual start (TENSION_TILT_ALONE dB of spectral tilt), or
brighter by TENSION_TILT dB in a line that also moves more than the
speaker's lines (pitch range TENSION_RANGE times the usual). On four
rounds of a listened series that named about 2.5 lines per episode and
four of the six delivery findings the listener had kept. With ``--accent``
the realized accent nucleus of every phrase (the first fall of FALL st that
stays down) is compared with the dictionary's and a difference becomes a
reading ``accent`` line; off by default because on the same four rounds it
named 720 phrases and only one of the three accent findings the listener
had kept. A word the dictionary spells letter by letter (Latin script) is
never checked. All measurements stay in the JSON whether or not a
candidate came of them.

The alignment model is read from the torch hub cache; ``analyze`` never
downloads it. ``prepare`` does, once per machine.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

SR = 16000
HOP = 160  # 10 ms
CAPTION = re.compile(r"^\[(\d+):(\d\d)\]\s*(.*)$")
PHONE_TO_ROMAJI = {"N": "n", "cl": "", "I": "i", "U": "u", "pau": "", "sil": ""}
PHONE_TO_KANA = {
    "a": "ア", "i": "イ", "u": "ウ", "e": "エ", "o": "オ", "N": "ン", "cl": "ッ", "I": "イ", "U": "ウ",
}
ROMAN_OK = re.compile(r"^[a-z]+$")
LATIN = re.compile(r"[A-Za-z]")
MODEL_URL = "https://dl.fbaipublicfiles.com/mms/torchaudio/ctc_alignment_mling_uroman/model.pt"

FALL = 2.0            # st: the first fall of at least this much, never recovered, is the nucleus
CLEAR_FALL = 3.0      # st: a fall that contradicts an expected level phrase
FINAL_LOWERING = 4.0  # st: a fall into the last mora smaller than this is phrase-final lowering
TOLERANCE = 1         # morae: alignment jitter moves a fall by about one mora
OCTAVE_FLOOR = 10.0   # st under the line's median: the bass under the voice, not the voice
MIN_MORAE = 6         # a line shorter than this (a jingle, a call) is not compared for pace
RATE_DEVIATION = 0.25  # of the speaker's median morae/s
FLAT_RATIO = 0.5      # of the speaker's median pitch range
LONG_PAUSE = 1.2      # s, inside a line
NO_PAUSE = 0.08       # s, at a 。 inside a line
SPEAKER_MERGE = 3.0   # st: pitch clusters closer than this are one speaker
ONSET = 0.6           # s: the start of a line whose vocal effort is compared
# A sudden push, two shapes: a start much brighter than the speaker's usual
# start (TENSION_TILT_ALONE dB of spectral tilt: the voice comes in loud or
# hard), or a start brighter by TENSION_TILT dB in a line that also moves more
# than the speaker's lines (pitch range TENSION_RANGE times the usual: the
# voice gets excited). On four listened rounds of one series (945 lines, six
# kept delivery findings) the pair names about 2.5 lines per episode and four
# of the six; on a fifth episode, two of the three the listener marked.
TENSION_TILT_ALONE = 8.0
TENSION_TILT = 6.0
TENSION_RANGE = 1.1


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(2)


# --- text side ---------------------------------------------------------------

def read_captions(path: str) -> list[dict]:
    lines = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        m = CAPTION.match(raw.strip())
        if m and m.group(3).strip():
            lines.append({"at": int(m.group(1)) * 60 + int(m.group(2)), "text": m.group(3).strip()})
    return lines


def morae_of(text: str) -> list[dict]:
    """Morae with accent-phrase index, mora index, expected nucleus flag, a
    pause-before flag, romaji for the aligner and the surface word they come
    from, from pyopenjtalk's full-context labels and its frontend."""
    import pyopenjtalk

    morae: list[dict] = []
    phrase = -1
    prev_a3 = None
    prev_was_pause = True
    cur = None
    for lab in pyopenjtalk.extract_fullcontext(text):
        ph = lab.split("-")[1].split("+")[0]
        if ph in ("sil", "pau"):
            prev_was_pause = True
            cur = None
            continue
        a1, a2, a3 = (int(x) for x in lab.split("/A:")[1].split("/B:")[0].split("+"))
        new_phrase = a2 == 1 and (cur is None or prev_was_pause or prev_a3 == 1)
        if new_phrase:
            phrase += 1
        if new_phrase or cur is None or cur["a2"] != a2:
            cur = {"phrase": phrase, "a1": a1, "a2": a2, "phones": [], "nucleus": a1 == 0,
                   "pause_before": prev_was_pause}
            morae.append(cur)
        cur["phones"].append(ph)
        prev_a3 = a3
        prev_was_pause = False
    for m in morae:
        m["romaji"] = "".join(PHONE_TO_ROMAJI.get(p, p) for p in m["phones"]).lower()
        m["surface"] = ""
        m["latin"] = False
        m["period_before"] = False
    # per mora: the surface word, whether the dictionary spelt it letter by
    # letter, and whether a 。 precedes it (the frontend lists punctuation as
    # words of no morae)
    words = []
    period = False
    for word in pyopenjtalk.run_frontend(text):
        size = int(word.get("mora_size") or 0)
        surface = unicodedata.normalize("NFKC", str(word.get("string", "")))
        if size == 0:
            period = period or "。" in surface
            continue
        words.append((surface, bool(LATIN.search(surface)), period))
        words.extend([(surface, bool(LATIN.search(surface)), False)] * (size - 1))
        period = False
    if len(words) == len(morae):
        for m, (surface, latin, period_before) in zip(morae, words):
            m["surface"], m["latin"], m["period_before"] = surface, latin, period_before
    return morae


def phrases_of(morae: list[dict]) -> list[list[dict]]:
    out: list[list[dict]] = []
    for m in morae:
        if not out or out[-1][0]["phrase"] != m["phrase"]:
            out.append([])
        out[-1].append(m)
    return out


def kana_of(phrase: list[dict], nucleus: int | None) -> str:
    """The phrase's pronunciation in katakana with ↓ after the nucleus mora;
    a level phrase gets no mark."""
    parts = []
    for i, m in enumerate(phrase, start=1):
        parts.append(mora_kana(m["phones"]))
        if nucleus == i and i < len(phrase):
            parts.append("↓")
    return "".join(parts)


KANA_ROWS = {  # consonant → kana for a, i, u, e, o
    "k": "カ キ ク ケ コ", "s": "サ スィ ス セ ソ", "t": "タ ティ トゥ テ ト", "n": "ナ ニ ヌ ネ ノ",
    "h": "ハ ヒ フ ヘ ホ", "m": "マ ミ ム メ モ", "y": "ヤ イ ユ イェ ヨ", "r": "ラ リ ル レ ロ",
    "w": "ワ ウィ ウ ウェ ウォ", "g": "ガ ギ グ ゲ ゴ", "z": "ザ ズィ ズ ゼ ゾ", "d": "ダ ディ ドゥ デ ド",
    "b": "バ ビ ブ ベ ボ", "p": "パ ピ プ ペ ポ", "j": "ジャ ジ ジュ ジェ ジョ", "sh": "シャ シ シュ シェ ショ",
    "ch": "チャ チ チュ チェ チョ", "ts": "ツァ ツィ ツ ツェ ツォ", "f": "ファ フィ フ フェ フォ",
    "v": "ヴァ ヴィ ヴ ヴェ ヴォ", "ky": "キャ キ キュ キェ キョ", "gy": "ギャ ギ ギュ ギェ ギョ",
    "ny": "ニャ ニ ニュ ニェ ニョ", "hy": "ヒャ ヒ ヒュ ヒェ ヒョ", "by": "ビャ ビ ビュ ビェ ビョ",
    "py": "ピャ ピ ピュ ピェ ピョ", "my": "ミャ ミ ミュ ミェ ミョ", "ry": "リャ リ リュ リェ リョ",
    "dy": "ヂャ ヂ ヂュ ヂェ ヂョ", "ty": "チャ チ チュ チェ チョ",
}
VOWEL_INDEX = {"a": 0, "i": 1, "u": 2, "e": 3, "o": 4}


def mora_kana(phones: list[str]) -> str:
    """Katakana for one mora's phonemes; an unknown pair stays in romaji."""
    if len(phones) == 1:
        return PHONE_TO_KANA.get(phones[0], phones[0])
    consonant, vowel = phones[0], phones[-1].lower()
    row = KANA_ROWS.get(consonant)
    if row is None or vowel not in VOWEL_INDEX:
        return "".join(phones)
    return row.split()[VOWEL_INDEX[vowel]]


# --- accent check ------------------------------------------------------------

def realized_nucleus(st: list[float | None]) -> tuple[int | None, float]:
    """1-based index of the mora after which pitch first falls by FALL st and
    stays down (never again within 1 st of that mora), with the size of that
    fall; (None, largest drop) for a level or rising phrase."""
    known = [(i, s) for i, s in enumerate(st) if s is not None]
    largest = 0.0
    for k, (i, s) in enumerate(known[:-1]):
        drop = s - known[k + 1][1]
        largest = max(largest, drop)
        if drop >= FALL and max(u for _, u in known[k + 1:]) <= s - 1.0:
            return i + 1, drop
    return None, largest


def check_phrase(phrase: list[dict]) -> dict | None:
    """The expected and realized accent of one phrase, or None when fewer
    than all-but-one morae have a pitch or the phrase is a single mora."""
    st = [m.get("st") for m in phrase]
    n = len(phrase)
    if n < 2 or sum(s is not None for s in st) < max(2, n - 1):
        return None
    surface = "".join(dict.fromkeys(m["surface"] for m in phrase if m["surface"]))
    if any(m.get("latin") for m in phrase):
        return {"surface": surface, "kana": kana_of(phrase, None), "skipped": "spelt letter by letter",
                "ok": True, "st": []}
    expected = next((m["a2"] for m in phrase if m["nucleus"]), None)
    flat_expected = expected in (None, n)
    got, drop = realized_nucleus(st)
    known = [s for s in st if s is not None]
    span = max(known) - min(known)
    if flat_expected:
        ok = got is None or drop < CLEAR_FALL or (got == n - 1 and drop < FINAL_LOWERING)
        expected_nucleus = None
    else:
        expected_nucleus = expected
        ok = (span < CLEAR_FALL) if got is None else abs(got - expected) <= TOLERANCE
    return {"surface": surface, "expected": kana_of(phrase, expected_nucleus), "heard": kana_of(phrase, got),
            "ok": ok, "st": [None if s is None else round(s, 1) for s in st], "drop": round(drop, 1),
            "span": round(span, 1)}


# --- audio side --------------------------------------------------------------

def model_cached() -> bool:
    import torch

    return (Path(torch.hub.get_dir()) / "checkpoints" / os.path.basename(MODEL_URL)).is_file()


class Aligner:
    def __init__(self) -> None:
        import torchaudio

        bundle = torchaudio.pipelines.MMS_FA
        self.model = bundle.get_model(with_star=False).eval()
        self.tokenizer = bundle.get_tokenizer()
        self.aligner = bundle.get_aligner()
        self.labels = set(bundle.get_labels())

    def align(self, wav, words: list[str]) -> list[tuple[float, float] | None]:
        """Start/end seconds per word; None for a word with nothing to align."""
        import torch

        keep = [i for i, w in enumerate(words) if w and ROMAN_OK.match(w) and all(c in self.labels for c in w)]
        out: list[tuple[float, float] | None] = [None] * len(words)
        if not keep or wav.shape[0] < SR // 4:
            return out
        with torch.inference_mode():
            emission, _ = self.model(torch.from_numpy(wav).float().unsqueeze(0))
            tokens = self.tokenizer([words[i] for i in keep])
            spans = self.aligner(emission[0], tokens)
        ratio = wav.shape[0] / emission.shape[1] / SR
        for i, span in zip(keep, spans):
            out[i] = (span[0].start * ratio, span[-1].end * ratio)
        return out


def pitch_track(wav):
    """Per 10 ms frame: pitch in semitones from 100 Hz (NaN unvoiced), level
    in dB, and spectral tilt in dB (1-4 kHz against 100-1000 Hz: the vocal
    effort, brighter when the voice pushes)."""
    import librosa
    import numpy as np

    f0, voiced, _ = librosa.pyin(wav, fmin=60.0, fmax=500.0, sr=SR, frame_length=1024, hop_length=HOP)
    st = np.where(voiced & np.isfinite(f0), 12 * np.log2(np.maximum(f0, 1e-6) / 100.0), np.nan)
    power = np.abs(librosa.stft(wav, n_fft=1024, hop_length=HOP)) ** 2
    freqs = librosa.fft_frequencies(sr=SR, n_fft=1024)
    low = power[(freqs >= 100) & (freqs < 1000)].sum(axis=0)
    high = power[(freqs >= 1000) & (freqs < 4000)].sum(axis=0)
    tilt = 10 * np.log10(high + 1e-9) - 10 * np.log10(low + 1e-9)
    rms = librosa.feature.rms(y=wav, frame_length=1024, hop_length=HOP)[0]
    return st, 20 * np.log10(np.maximum(rms, 1e-6)), tilt


def window_median(track, start: float, end: float) -> float | None:
    import numpy as np

    a = int(start * SR / HOP)
    seg = track[a:max(int(end * SR / HOP), a + 1)]
    if seg.size == 0 or np.all(np.isnan(seg)):
        return None
    return float(np.nanmedian(seg))


# --- speakers and delivery ---------------------------------------------------

def cluster_speakers(values: list[float], k: int = 3, merge: float = SPEAKER_MERGE) -> list[int]:
    """1-D k-means of line pitch medians, clusters closer than ``merge`` st
    joined, numbered from the lowest voice."""
    import numpy as np

    x = np.array(values, dtype=float)
    if len(x) <= k:
        order = np.argsort(x)
        return [int(np.where(order == i)[0][0]) for i in range(len(x))]
    centres = np.percentile(x, np.linspace(10, 90, k))
    for _ in range(50):
        labels = np.argmin(np.abs(x[:, None] - centres[None, :]), axis=1)
        new = np.array([x[labels == c].mean() if np.any(labels == c) else centres[c] for c in range(k)])
        if np.allclose(new, centres):
            break
        centres = new
    order = np.argsort(centres)
    rank = {int(c): r for r, c in enumerate(order)}
    labels = [rank[int(l)] for l in labels]
    sorted_centres = centres[order]
    canonical = list(range(k))
    for c in range(1, k):
        if sorted_centres[c] - sorted_centres[c - 1] < merge:
            canonical[c] = canonical[c - 1]
    ids = {v: i for i, v in enumerate(sorted(set(canonical)))}
    return [ids[canonical[l]] for l in labels]


def clock(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def delivery_findings(lines: list[dict], tension: bool = False) -> list[str]:
    """Pace, pause and flatness candidates, each line against its speaker's
    others; with ``tension`` also a start pushed harder than the speaker's."""
    import numpy as np

    out = []
    for speaker in sorted({r["speaker"] for r in lines if r.get("speaker") is not None}):
        mine = [r for r in lines if r.get("speaker") == speaker]
        med_rate = float(np.median([r["rate"] for r in mine]))
        ranges = [r["pitch_range"] for r in mine if r.get("pitch_range") is not None]
        med_range = float(np.median(ranges)) if ranges else None
        onsets = [r["onset_tilt"] for r in mine if r.get("onset_tilt") is not None]
        med_onset = float(np.median(onsets)) if onsets else None
        for r in mine:
            at = clock(r["at"])
            if tension and med_onset is not None and r.get("onset_tilt") is not None and r["morae"] >= MIN_MORAE:
                push = r["onset_tilt"] - med_onset
                moves = (r["pitch_range"] / med_range) if med_range and r.get("pitch_range") is not None else None
                if push >= TENSION_TILT_ALONE:
                    out.append(f"{at} | voice | tension: the start is {push:.1f} dB brighter than speaker {speaker}'s "
                               f"usual start | prosody-ja speaker {speaker} | confirm")
                elif push >= TENSION_TILT and moves is not None and moves >= TENSION_RANGE:
                    out.append(f"{at} | voice | tension: the start is {push:.1f} dB brighter than speaker {speaker}'s "
                               f"usual start and the line moves {moves:.2f}x the speaker's pitch range "
                               f"| prosody-ja speaker {speaker} | confirm")
            if r["morae"] >= MIN_MORAE and med_rate and abs(r["rate"] - med_rate) / med_rate > RATE_DEVIATION:
                out.append(f"{at} | voice | pace: {r['rate']} morae/s against speaker {speaker}'s {med_rate:.1f} "
                           f"| prosody-ja speaker {speaker} | confirm")
            if med_range and r.get("pitch_range") is not None and r["morae"] >= MIN_MORAE \
                    and r["pitch_range"] < FLAT_RATIO * med_range:
                out.append(f"{at} | voice | flat: pitch range {r['pitch_range']} st against speaker {speaker}'s "
                           f"{med_range:.1f} | prosody-ja speaker {speaker} | confirm")
            long = [p for p in r["pauses"] if p > LONG_PAUSE]
            if long:
                out.append(f"{at} | voice | pause: a pause of {max(long):.2f} s inside the line | prosody-ja | confirm")
            missing = [p for p in r["pauses_at_period"] if p < NO_PAUSE]
            if missing:
                out.append(f"{at} | voice | pause: no pause at a 。 inside the line ({min(missing):.2f} s) "
                           f"| prosody-ja | confirm")
    return out


def accent_findings(lines: list[dict]) -> list[str]:
    out = []
    for r in lines:
        for c in r["accent"]:
            if c.get("ok", True) or c.get("skipped"):
                continue
            word = f"「{c['surface']}」" if c["surface"] else ""
            out.append(f"{clock(r['at'])} | voice | accent: {word}{c['expected']} in the dictionary, heard {c['heard']} "
                       f"(st {c['st']}) | prosody-ja | confirm")
    return out


# --- commands ----------------------------------------------------------------

def analyze_line(cap: dict, end: float, wav, st_track, level_track, tilt_track, aligner: Aligner) -> dict:
    import numpy as np

    start = cap["at"]
    clip = wav[int(start * SR):int(end * SR)]
    morae = morae_of(cap["text"])
    spans = aligner.align(clip, [m["romaji"] for m in morae])
    for m, span in zip(morae, spans):
        if span is None:
            m["start"] = m["end"] = m["st"] = m["level"] = None
            continue
        m["start"], m["end"] = start + span[0], start + span[1]
        m["st"] = window_median(st_track, m["start"], m["end"])
        m["level"] = window_median(level_track, m["start"], m["end"])
    line_st = [m["st"] for m in morae if m.get("st") is not None]
    if line_st:
        floor = float(np.median(line_st)) - OCTAVE_FLOOR
        for m in morae:
            if m.get("st") is not None and m["st"] < floor:
                m["st"] = None
    checks = [c for c in (check_phrase(p) for p in phrases_of(morae)) if c]
    timed = [m for m in morae if m.get("start") is not None]
    line = {"at": start, "text": cap["text"], "morae": len(morae), "accent": checks}
    if not timed:
        line["unaligned"] = True
        return line
    speech_start, speech_end = timed[0]["start"], timed[-1]["end"]
    pauses, at_period = [], []
    for a, b in zip(timed, timed[1:]):
        if b["pause_before"] or b["period_before"]:
            gap = round(b["start"] - a["end"], 2)
            pauses.append(gap)
            if b["period_before"]:
                at_period.append(gap)
    sts = [m["st"] for m in timed if m["st"] is not None]
    levels = [m["level"] for m in timed if m["level"] is not None]
    first = [m for m in phrases_of(timed)[0]] if timed else []
    last = [m for m in phrases_of(timed)[-1]] if timed else []
    line.update({
        "speech_start": round(speech_start, 2), "speech_end": round(speech_end, 2),
        "rate": round(len(morae) / max(speech_end - speech_start, 0.1), 2),
        "pauses": pauses, "pauses_at_period": at_period,
        "pitch_median": round(float(np.median(sts)), 1) if sts else None,
        "pitch_range": round(float(np.percentile(sts, 90) - np.percentile(sts, 10)), 1) if len(sts) > 3 else None,
        "level_median": round(float(np.median(levels)), 1) if levels else None,
        "level_range": round(float(np.percentile(levels, 90) - np.percentile(levels, 10)), 1) if len(levels) > 3 else None,
        "onset_level": _median([m["level"] for m in first]),
        "onset_pitch": _median([m["st"] for m in first]),
        "tail_level": _median([m["level"] for m in last]),
        "tail_pitch": _median([m["st"] for m in last]),
        "onset_tilt": window_median(tilt_track, speech_start, speech_start + ONSET),
        "tilt_median": window_median(tilt_track, speech_start, speech_end),
        "first_phones": "".join(timed[0]["phones"]),
    })
    for key in ("onset_tilt", "tilt_median"):
        if line[key] is not None:
            line[key] = round(line[key], 1)
    return line


def _median(values) -> float | None:
    import numpy as np

    known = [v for v in values if v is not None]
    return round(float(np.median(known)), 1) if known else None


def cmd_analyze(args) -> int:
    import librosa
    import numpy as np
    import soundfile as sf

    if not model_cached():
        fail("the alignment model is not cached; a maintainer runs `prosody-ja.py prepare` once on this machine")
    captions = read_captions(args.captions)
    if not captions:
        fail(f"no `[m:ss] text` lines in {args.captions}")
    wav, sr = sf.read(args.wav, dtype="float32")
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    if sr != SR:
        wav = librosa.resample(wav, orig_sr=sr, target_sr=SR)
    duration = len(wav) / SR
    st_track, level_track, tilt_track = pitch_track(wav)
    aligner = Aligner()
    lines = []
    for idx, cap in enumerate(captions):
        end = captions[idx + 1]["at"] if idx + 1 < len(captions) else min(duration, cap["at"] + 15)
        lines.append(analyze_line(cap, end, wav, st_track, level_track, tilt_track, aligner))
    with_pitch = [r for r in lines if r.get("pitch_median") is not None]
    for r, speaker in zip(with_pitch, cluster_speakers([r["pitch_median"] for r in with_pitch])):
        r["speaker"] = speaker
    findings = delivery_findings(lines, tension=args.tension)
    if args.accent:
        findings += accent_findings(lines)
    phrases = sum(len(r["accent"]) for r in lines)
    skipped = sum(1 for r in lines for c in r["accent"] if c.get("skipped"))
    result = {"source": args.wav, "captions": args.captions, "duration": round(duration, 2),
              "lines": lines, "speakers": sorted({r["speaker"] for r in with_pitch}),
              "phrases": phrases, "phrases_skipped": skipped, "findings": findings,
              "note": "candidates for a person's ear: the dictionary accent is unreliable on loanwords and "
                      "compounds, and the speakers are pitch clusters, not identities"}
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if args.lines:
        Path(args.lines).write_text("\n".join(findings) + ("\n" if findings else ""), encoding="utf-8")
    print(json.dumps({"ok": True, "lines": len(lines), "unaligned": sum(1 for r in lines if r.get("unaligned")),
                      "speakers": len(result["speakers"]), "phrases": phrases, "phrases_skipped": skipped,
                      "findings": len(findings), "out": args.out, "lines_out": args.lines}, ensure_ascii=False))
    return 0


def cmd_prepare(args) -> int:
    import torchaudio

    torchaudio.pipelines.MMS_FA.get_model(with_star=False)
    print(json.dumps({"ok": model_cached()}))
    return 0 if model_cached() else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("analyze")
    p.add_argument("wav")
    p.add_argument("--captions", required=True, help="`[m:ss] text` lines, the words as written")
    p.add_argument("--out", required=True, help="the result JSON")
    p.add_argument("--lines", help="the candidate lines, one `m:ss | voice | item: … | … | confirm` per line")
    p.add_argument("--accent", action="store_true", help="also report phrases whose accent differs from the dictionary")
    p.add_argument("--tension", action="store_true", help="also report a start pushed harder than the speaker's lines (experimental)")
    p.set_defaults(func=cmd_analyze)
    p = sub.add_parser("prepare")
    p.set_defaults(func=cmd_prepare)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
