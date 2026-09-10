#!/usr/bin/env python3
"""Deterministic speech audio helper: track / edit / analyze.

Requires ffmpeg/ffprobe on PATH; ASR uses faster_whisper's local 'base'
model (never downloaded here — a missing cache is an actionable failure).
Stdlib + optional faster_whisper only. Prints RESULT: <JSON> to stdout;
never overwrites a source or an existing/symlinked output directory.

No production test seam: the test suite exercises this module by importing
it directly and monkeypatching load_asr_model() with a fake WhisperModel,
never via an environment variable.
"""

from __future__ import annotations

import argparse
import array
import difflib
import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
import unicodedata
import wave
from pathlib import Path

SAMPLE_RATE = 48000
SUBPROCESS_TIMEOUT = 300
MAX_MEDIA_SECONDS = 600
TRACK_SCRIPT_MAX_CHARS = 600
EDIT_SCRIPT_MAX_CHARS = 10000
SILENCE_THRESHOLD_DB = -45
SILENCE_MIN_DURATION = 0.2
CAPTION_MAX_CHARS = 42
SIDECAR_DURATION_TOLERANCE = 0.15
CPS_BANDS = {"ja": (4, 11), "en": (8, 20)}
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Fixed application order regardless of --operations argument order.
OPERATION_ORDER = ("concat", "trim", "speed", "normalize", "convert")
MAX_EDIT_SOURCES = 64


class DependencyError(RuntimeError):
    """Missing external tool, missing ASR model cache, or missing input."""


def run(args, timeout=SUBPROCESS_TIMEOUT, binary=False):
    try:
        return subprocess.run(
            [str(a) for a in args], check=True, capture_output=True,
            text=not binary, timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise DependencyError(f"required tool not found: {args[0]}") from exc


def run_pipe(args, input_bytes, timeout=SUBPROCESS_TIMEOUT):
    try:
        return subprocess.run(
            [str(a) for a in args], input=input_bytes, check=True,
            capture_output=True, timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise DependencyError(f"required tool not found: {args[0]}") from exc


# --------------------------------------------------------------------------
# Path / argument validation
# --------------------------------------------------------------------------

def resolve_source(path):
    p = Path(path).expanduser().resolve(strict=True)
    if not p.is_file():
        raise ValueError(f"source must be a local regular file: {path}")
    return p


def fresh_output_dir(path):
    out = Path(path).expanduser().absolute()
    if out.exists() or out.is_symlink():
        raise ValueError("output directory must not exist; use a new bundle directory")
    return out


def ensure_parent_exists(out):
    """Require the bundle's parent directory to already exist; never create
    arbitrary parent directories on the caller's behalf."""
    if not out.parent.is_dir():
        raise ValueError(f"output parent directory does not exist: {out.parent}")


def validate_slug(slug):
    if not SLUG_RE.match(slug or ""):
        raise ValueError("slug must match [a-z0-9]+(-[a-z0-9]+)*")
    return slug


def read_script_file(path, max_chars):
    p = Path(path).expanduser().resolve(strict=True)
    if not p.is_file():
        raise ValueError("script-file must be a regular file")
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("script-file must be nonblank")
    if len(text) > max_chars:
        raise ValueError(f"script-file exceeds {max_chars} Unicode characters")
    return text


def load_take_file(path):
    p = Path(path).expanduser().resolve(strict=True)
    if not p.is_file():
        raise ValueError("take-file must be a regular JSON file")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"take-file is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("take-file must contain a JSON object")
    return data


def build_take_json(take, operation, sources, output_pcm_sha256, source_pcm_hashes, lineage):
    take = take or {}
    return {
        "voice": take.get("voice"), "engine": take.get("engine"),
        "seed": take.get("seed"), "style": take.get("style"),
        "evidence_provided": bool(take),
        "evidence": take,  # the full raw take-file object, verbatim, not just the cherry-picked fields above
        "operation": operation,
        "source": [str(s) for s in sources],
        "pcm_sha256": output_pcm_sha256,  # hash of the actual produced output, not a source
        "source_pcm_sha256": source_pcm_hashes,
        "lineage": lineage,
    }


# --------------------------------------------------------------------------
# ffprobe / decode / measure
# --------------------------------------------------------------------------

def probe(path):
    data = json.loads(run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path,
    ]).stdout)
    audios = [s for s in data["streams"] if s.get("codec_type") == "audio"]
    if not audios:
        raise ValueError("source has no audio stream")
    audio = audios[0]
    duration = float(audio.get("duration", data["format"].get("duration", 0)))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("source must have a measurable positive duration")
    if duration > MAX_MEDIA_SECONDS:
        raise ValueError(f"source exceeds the {MAX_MEDIA_SECONDS}s media cap")
    return {
        "path": str(path), "codec": audio["codec_name"],
        "sample_rate": int(audio.get("sample_rate", 0) or 0),
        "channels": int(audio.get("channels", 0) or 0),
        "duration": duration, "audio_index": audio["index"],
    }


def decode_pcm(path, audio_index, max_seconds=None):
    """Decode the selected audio stream once, fully, to mono 48k s16le PCM.

    When max_seconds is given, ffmpeg's own decode is capped to a small
    margin beyond it: without this, a file whose declared (probed) duration
    understates its real content would still get fully buffered into memory
    before any length check ever ran. Hitting that margin means the real
    content is at least that long, so it is rejected outright rather than
    silently accepted as if the truncated buffer were the whole file.
    """
    args = [
        "ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", path,
        "-map", f"0:{audio_index}", "-ac", "1", "-ar", str(SAMPLE_RATE),
    ]
    if max_seconds is not None:
        args += ["-t", f"{max_seconds + 0.01:.2f}"]
    args += ["-f", "s16le", "-acodec", "pcm_s16le", "pipe:1"]
    proc = run(args, binary=True)
    pcm = proc.stdout
    samples = array.array("h")
    samples.frombytes(pcm)
    if sys.byteorder == "big":
        samples.byteswap()
    if max_seconds is not None and (len(samples) / SAMPLE_RATE) > max_seconds:
        raise ValueError(f"source exceeds the {max_seconds}s media cap")
    return pcm, samples


def parse_silence(text, duration):
    starts = [float(m) for m in re.findall(r"silence_start:\s*(-?[\d.]+)", text)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*(-?[\d.]+)\s*\|", text)]
    intervals = list(zip(starts, ends))
    if len(starts) > len(ends):
        intervals.append((starts[-1], duration))  # ran silent to EOF, no matching silence_end
    if not intervals:
        return 0.0, 0.0
    leading = intervals[0][1] if intervals[0][0] <= 0.05 else 0.0
    trailing = duration - intervals[-1][0] if intervals[-1][1] >= duration - 0.05 else 0.0
    return max(0.0, min(leading, duration)), max(0.0, min(trailing, duration))


def parse_loudnorm(text):
    match = re.search(r"\{[^{}]*\}", text)
    if not match:
        raise ValueError("loudnorm measurement produced no JSON summary")
    data = json.loads(match.group(0))

    def num(key):
        try:
            value = float(data[key])
        except (KeyError, ValueError, TypeError):
            return None
        return value if math.isfinite(value) else None

    return num("input_i"), num("input_tp"), num("input_lra"), num("input_thresh"), num("target_offset")


def measure_filters(path):
    sil_text = run([
        "ffmpeg", "-hide_banner", "-nostdin", "-i", path,
        "-af", f"silencedetect=noise={SILENCE_THRESHOLD_DB}dB:d={SILENCE_MIN_DURATION}",
        "-f", "null", "-",
    ]).stderr
    loud_text = run([
        "ffmpeg", "-hide_banner", "-nostdin", "-i", path,
        "-af", "loudnorm=I=-16:TP=-1:LRA=11:print_format=json",
        "-f", "null", "-",
    ]).stderr
    return sil_text, loud_text


def _measure_common(pcm, samples, filters_path, codec, sample_rate, channels):
    if not samples:
        raise ValueError("decoded audio is empty")
    duration = len(samples) / SAMPLE_RATE
    mn, mx = min(samples), max(samples)
    peak = max(abs(mn), abs(mx))
    clipped = sum(1 for s in samples if abs(s) >= 32767)
    sample_peak_db = 20 * math.log10(peak / 32768) if peak > 0 else None
    all_silent = peak == 0
    sil_text, loud_text = measure_filters(filters_path)
    leading, trailing = parse_silence(sil_text, duration)
    integrated_lufs, true_peak_db, _lra, _thresh, _offset = parse_loudnorm(loud_text)
    if all_silent:
        leading = trailing = duration
    return {
        "codec": codec, "sample_rate": sample_rate, "channels": channels,
        "duration": round(duration, 3), "integrated_lufs": integrated_lufs,
        "true_peak_db": true_peak_db, "sample_peak_db": sample_peak_db,
        "clipped_samples": clipped, "leading_silence": round(leading, 3),
        "trailing_silence": round(trailing, 3),
        "pcm_sha256": hashlib.sha256(pcm).hexdigest(), "all_silent": all_silent,
    }


def decode_and_measure(path):
    """Decode a source file once; return (master measurement, pcm bytes,
    input measurement). The master measurement always reflects the actual
    decoded 48k mono output, never the source file's own codec/rate/channels
    metadata; the input measurement preserves that source metadata
    separately."""
    info = probe(path)
    pcm, _samples = decode_pcm(info["path"], info["audio_index"], MAX_MEDIA_SECONDS)
    measured = measure_pcm_bytes(pcm)
    if info["channels"] and info["channels"] != 1:
        measured["downmix_note"] = (
            "integrated_lufs/true_peak_db/silence reflect the decoded mono master; "
            "the original multichannel input may differ slightly"
        )
    input_measure = {
        "path": info["path"], "codec": info["codec"],
        "sample_rate": info["sample_rate"], "channels": info["channels"],
        "duration": round(info["duration"], 3),
    }
    return measured, pcm, input_measure


def measure_output_file(path):
    """Decode+measure an already-written output file (a published master or
    an encoded derivative), reporting that file's own actual codec/format."""
    info = probe(path)
    pcm, samples = decode_pcm(info["path"], info["audio_index"])
    return _measure_common(pcm, samples, info["path"], info["codec"], info["sample_rate"], info["channels"])


def measure_pcm_bytes(pcm):
    """Measure an in-memory mono 48k s16le PCM buffer (mid-pipeline state)."""
    samples = array.array("h")
    samples.frombytes(pcm)
    if sys.byteorder == "big":
        samples.byteswap()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        write_wav(tmp_path, pcm)
        return _measure_common(pcm, samples, tmp_path, "pcm_s16le", SAMPLE_RATE, 1)
    finally:
        tmp_path.unlink(missing_ok=True)


def silence_bounds(pcm):
    """Leading/trailing silence of an in-memory PCM buffer."""
    duration = (len(pcm) // 2) / SAMPLE_RATE
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        write_wav(tmp_path, pcm)
        sil_text = run([
            "ffmpeg", "-hide_banner", "-nostdin", "-i", tmp_path,
            "-af", f"silencedetect=noise={SILENCE_THRESHOLD_DB}dB:d={SILENCE_MIN_DURATION}",
            "-f", "null", "-",
        ]).stderr
        return parse_silence(sil_text, duration)
    finally:
        tmp_path.unlink(missing_ok=True)


def write_wav(path, pcm):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)


# --------------------------------------------------------------------------
# Audio transforms (concat / trim / speed / normalize / convert)
# --------------------------------------------------------------------------

def concat_pcm(pcm_list, gap_ms):
    gap_samples = int(round(SAMPLE_RATE * gap_ms / 1000))
    silence = b"\x00\x00" * gap_samples
    parts = []
    for i, pcm in enumerate(pcm_list):
        parts.append(pcm)
        if i < len(pcm_list) - 1:
            parts.append(silence)
    return b"".join(parts)


def trim_pcm(pcm, leading_seconds, trailing_seconds):
    lead_bytes = int(round(leading_seconds * SAMPLE_RATE)) * 2
    trail_bytes = int(round(trailing_seconds * SAMPLE_RATE)) * 2
    end = len(pcm) - trail_bytes
    if end <= lead_bytes:
        return pcm
    return pcm[lead_bytes:end]


def atempo_chain(factor):
    filters = []
    remaining = factor
    if remaining > 2.0:
        while remaining > 2.0 + 1e-9:
            filters.append("atempo=2.0")
            remaining /= 2.0
    elif remaining < 0.5:
        while remaining < 0.5 - 1e-9:
            filters.append("atempo=0.5")
            remaining /= 0.5
    filters.append(f"atempo={remaining:.6f}")
    return ",".join(filters)


def apply_speed(pcm, speed):
    if speed == 1.0:
        return pcm
    chain = atempo_chain(speed)
    proc = run_pipe([
        "ffmpeg", "-nostdin", "-v", "error", "-f", "s16le", "-ar", str(SAMPLE_RATE),
        "-ac", "1", "-i", "pipe:0", "-af", chain, "-f", "s16le", "-ar", str(SAMPLE_RATE),
        "-ac", "1", "-acodec", "pcm_s16le", "pipe:1",
    ], pcm)
    return proc.stdout


def loudnorm_of_pcm(pcm, target_lufs):
    """First pass of two-pass loudnorm: measure at the SAME target that will be
    applied in the second pass (linear-mode accuracy depends on measuring at
    the actual requested target, not a fixed one)."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        write_wav(tmp_path, pcm)
        loud_text = run([
            "ffmpeg", "-hide_banner", "-nostdin", "-i", tmp_path,
            "-af", f"loudnorm=I={target_lufs}:TP=-1:LRA=11:print_format=json", "-f", "null", "-",
        ]).stderr
        return parse_loudnorm(loud_text)
    finally:
        tmp_path.unlink(missing_ok=True)


def normalize_pcm(pcm, target_lufs):
    measured_i, measured_tp, measured_lra, measured_thresh, target_offset = loudnorm_of_pcm(pcm, target_lufs)
    if None in (measured_i, measured_tp, measured_lra, measured_thresh):
        raise ValueError(
            "audio is silent or has no finite loudness measurement; refusing to normalize"
        )
    offset_part = f":offset={target_offset}" if target_offset is not None else ""
    filt = (
        f"loudnorm=I={target_lufs}:TP=-1:LRA=11:measured_I={measured_i}:"
        f"measured_TP={measured_tp}:measured_LRA={measured_lra}:"
        f"measured_thresh={measured_thresh}{offset_part}:linear=true:print_format=summary"
    )
    proc = run_pipe([
        "ffmpeg", "-nostdin", "-v", "error", "-f", "s16le", "-ar", str(SAMPLE_RATE),
        "-ac", "1", "-i", "pipe:0", "-af", filt, "-f", "s16le", "-ar", str(SAMPLE_RATE),
        "-ac", "1", "-acodec", "pcm_s16le", "pipe:1",
    ], pcm)
    return proc.stdout


def encode_derivative(pcm, fmt, out_path):
    if fmt == "ogg":
        codec_args = ["-c:a", "libopus", "-b:a", "96k"]
    elif fmt == "mp3":
        codec_args = ["-c:a", "libmp3lame", "-q:a", "4"]
    else:
        raise ValueError("convert format must be ogg or mp3 (wav is already the master)")
    run_pipe([
        "ffmpeg", "-nostdin", "-v", "error", "-f", "s16le", "-ar", str(SAMPLE_RATE),
        "-ac", "1", "-i", "pipe:0", *codec_args, out_path,
    ], pcm)


# --------------------------------------------------------------------------
# ASR
# --------------------------------------------------------------------------

def load_asr_model():
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise DependencyError("faster_whisper is not installed") from exc
    try:
        return WhisperModel("base", device="cpu", compute_type="int8", local_files_only=True)
    except Exception as exc:
        raise DependencyError(
            "ASR model cache for 'base' is missing; run once with network access to "
            f"populate it: {exc}"
        ) from exc


def transcribe(path, duration, language=None):
    """Run the real ASR model and return clamped, ordered words/segments/transcript."""
    model = load_asr_model()
    segs, info = model.transcribe(
        str(path), language=language, beam_size=5, word_timestamps=True,
    )
    segments, words = [], []
    for seg in segs:
        for w in (seg.words or []):
            words.append({"start": w.start, "end": w.end, "word": w.word,
                          "p": getattr(w, "probability", None)})
        segments.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
    detected_language = info.language

    clean_words = []
    prev_end = 0.0
    for w in words:
        try:
            start = float(w["start"])
            end = float(w["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (math.isfinite(start) and math.isfinite(end)):
            continue
        start = max(0.0, min(start, duration))
        end = max(start, min(end, duration))
        start = max(start, prev_end)
        end = max(end, start)
        start_r, end_r = round(start, 3), round(end, 3)
        if end_r <= start_r:
            continue  # zero/negative-duration after clamping+rounding: drop rather than emit a phantom timestamp
        clean_words.append({"start": start_r, "end": end_r, "word": str(w["word"]), "p": w["p"]})
        prev_end = end  # unrounded, so rounding error does not compound across words

    clean_segments = []
    prev_end = 0.0
    for seg in segments:
        try:
            start = float(seg["start"])
            end = float(seg["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (math.isfinite(start) and math.isfinite(end)):
            continue
        start = max(0.0, min(start, duration))
        end = max(start, min(end, duration))
        # Same monotonic clamp as words: ASR segments are not guaranteed
        # non-overlapping, and an overlapping/out-of-order segment surviving
        # into a published sidecar would fail strict interval validation the
        # next time that sidecar is loaded for reuse.
        start = max(start, prev_end)
        end = max(end, start)
        start_r, end_r = round(start, 3), round(end, 3)
        if end_r <= start_r:
            continue
        clean_segments.append({"start": start_r, "end": end_r, "text": str(seg["text"])})
        prev_end = end

    transcript = re.sub(r"\s+", " ", " ".join(s["text"] for s in clean_segments)).strip()
    if not transcript:
        transcript = " ".join(w["word"].strip() for w in clean_words if w["word"].strip())

    return {
        "segments": clean_segments, "words": clean_words,
        "language": detected_language, "transcript": transcript,
    }


# --------------------------------------------------------------------------
# Readback / captions / SRT
# --------------------------------------------------------------------------

def normalize_for_readback(text):
    nfkc = unicodedata.normalize("NFKC", text or "").casefold()
    return "".join(ch for ch in nfkc if unicodedata.category(ch)[0] not in "PSZC")


def _non_latin_letters(text):
    return "".join(ch for ch in text if ch.isalpha() and ord(ch) > 127)


def script_coverage(script, transcript):
    """Diagnostic only: of the non-Latin-script characters in the script, how
    many are also present in matching blocks in the transcript. This is a
    coverage measure against the transcript, not the script's own composition
    (a script that is 100% non-Latin but wholly mistranscribed scores 0)."""
    script_nonlatin = _non_latin_letters(script)
    if not script_nonlatin:
        return 0.0
    transcript_nonlatin = _non_latin_letters(transcript)
    matcher = difflib.SequenceMatcher(None, script_nonlatin, transcript_nonlatin)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return matched / len(script_nonlatin)


def readback_compare(script, transcript, words_nonempty):
    norm_script = normalize_for_readback(script)
    norm_transcript = normalize_for_readback(transcript)
    if norm_script or norm_transcript:
        ratio = difflib.SequenceMatcher(None, norm_script, norm_transcript).ratio()
    else:
        ratio = 0.0
    coverage = script_coverage(norm_script, norm_transcript)
    if not words_nonempty:
        status = "FAIL"
    elif not norm_script or not norm_transcript:
        status = "FAIL"
    elif norm_script == norm_transcript:
        status = "PASS"
    elif ratio >= 0.85:
        # Never claim exact fidelity from ratio/coverage alone (that's PASS's job).
        status = "WARN"
    else:
        status = "FAIL"
    return {
        "script_match": status,
        "similarity_ratio": round(ratio, 4),
        "non_latin_coverage": round(coverage, 4),
        "perceptual_quality": "unverified",
        "note": "text (STT) match only; not a listening, identity, or performance verification",
    }


def cps_warning(language, transcript_chars, duration):
    if duration <= 0:
        return None
    cps = transcript_chars / duration
    band = CPS_BANDS.get((language or "")[:2].lower())
    if band is None:
        return {"cps": round(cps, 2), "band": None, "status": "unverified language"}
    lo, hi = band
    return {"cps": round(cps, 2), "band": list(band), "status": "ok" if lo <= cps <= hi else "warning"}


def chunk_text(text, max_chars=CAPTION_MAX_CHARS):
    sentences = [s.strip() for s in re.split(r"(?<=[.!?\u3002\uff01\uff1f\n])\s*", text.strip()) if s.strip()]
    if not sentences and text.strip():
        sentences = [text.strip()]
    chunks = []
    for sentence in sentences:
        s = sentence
        while len(s) > max_chars:
            cut = s.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            chunks.append(s[:cut].strip())
            s = s[cut:].strip()
        if s:
            chunks.append(s)
    return chunks


def build_char_timeline(words):
    """(char_offset, time) breakpoints along words joined with single spaces.

    Whisper word tokens often carry a leading (sometimes trailing) space
    artifact (e.g. " hello"); stripped here purely for char-offset counting
    so the mapping lines up with the actual chunked caption/transcript text
    (which never has that artifact). The word's own text is never modified
    -- this function only ever returns offsets/times, never word text."""
    breakpoints = [(0, 0.0)]
    offset = 0
    for w in words:
        text = w["word"].strip()
        breakpoints.append((offset, w["start"]))
        offset += len(text)
        breakpoints.append((offset, w["end"]))
        offset += 1  # joining space
    total = max(offset - 1, 0)
    return breakpoints, total


def interpolate_char_time(breakpoints, char_offset):
    if not breakpoints:
        return 0.0
    if char_offset <= breakpoints[0][0]:
        return breakpoints[0][1]
    for (o1, t1), (o2, t2) in zip(breakpoints, breakpoints[1:]):
        if o1 <= char_offset <= o2:
            return t1 if o2 == o1 else t1 + (char_offset - o1) / (o2 - o1) * (t2 - t1)
    return breakpoints[-1][1]


def captions_from_text(text, words, duration, source):
    text = (text or "").strip()
    chunks = chunk_text(text)
    if not chunks:
        return []
    total_chars = sum(len(c) for c in chunks)
    breakpoints, transcript_chars = (build_char_timeline(words) if words else (None, 0))
    captions = []
    cursor = 0
    for chunk in chunks:
        start_frac = cursor / total_chars
        end_frac = (cursor + len(chunk)) / total_chars
        if breakpoints and transcript_chars:
            start = interpolate_char_time(breakpoints, start_frac * transcript_chars)
            end = interpolate_char_time(breakpoints, end_frac * transcript_chars)
        else:
            start = start_frac * duration
            end = end_frac * duration
        captions.append({"start": start, "end": end, "text": chunk})
        cursor += len(chunk)
    fixed = []
    prev_end = 0.0
    for cap in captions:
        start = max(cap["start"], prev_end)
        end = max(cap["end"], start + 0.01)
        end = min(end, duration)
        start = min(start, end)
        fixed.append({
            "start": round(start, 3), "end": round(end, 3), "text": cap["text"],
            "estimated": True, "source": source,
        })
        prev_end = end
    return fixed


def srt_timestamp(t):
    ms = max(0, round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def captions_to_srt(captions):
    lines = []
    for i, cap in enumerate(captions, 1):
        lines.append(str(i))
        lines.append(f"{srt_timestamp(cap['start'])} --> {srt_timestamp(cap['end'])}")
        lines.append(cap["text"])
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n" if captions else ""


# --------------------------------------------------------------------------
# Sidecar validation / combination (edit)
# --------------------------------------------------------------------------

def _validate_sidecar_intervals(sidecar_path, items, text_key, duration):
    if not isinstance(items, list):
        raise ValueError(f"sidecar {sidecar_path} intervals must be a list")
    prev_end = 0.0
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get(text_key), str):
            raise ValueError(f"sidecar {sidecar_path} has missing or invalid {text_key}")
        try:
            start, end = float(item["start"]), float(item["end"])
        except (TypeError, KeyError, ValueError) as exc:
            raise ValueError(f"sidecar {sidecar_path} has a non-numeric {text_key} interval") from exc
        if not (math.isfinite(start) and math.isfinite(end)):
            raise ValueError(f"sidecar {sidecar_path} has a non-finite {text_key} interval")
        if start < 0 or end <= start or end > duration + 0.001:
            raise ValueError(f"sidecar {sidecar_path} has a {text_key} interval out of range")
        if start < prev_end - 0.001:
            raise ValueError(f"sidecar {sidecar_path} has {text_key}s out of order")
        if text_key in item and not isinstance(item[text_key], str):
            raise ValueError(f"sidecar {sidecar_path} has a non-string {text_key} text")
        prev_end = end


def load_valid_sidecar(source, measured):
    """Load and strictly validate a source's .words.json sidecar.

    A MISSING sidecar is not an error: it falls back to (None ->) real ASR.
    An EXISTING but malformed/stale sidecar is always an error: silently
    falling back on a sidecar that claims to describe this audio but does
    not would risk publishing captions/words that do not match the master.
    """
    sidecar_path = source.parent / f"{source.stem}.words.json"
    if not sidecar_path.is_file():
        return None
    try:
        data = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"sidecar {sidecar_path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or "words" not in data or "duration" not in data:
        raise ValueError(f"sidecar {sidecar_path} is missing required fields")
    if data.get("file") != source.name:
        # <stem>.words.json is looked up by stem, so it is shared by every
        # same-stem sibling (e.g. a .ogg/.mp3 derivative published next to
        # its .wav master). A sidecar that names a DIFFERENT file just isn't
        # THIS file's sidecar -- that's not malformed/stale, it's simply
        # absent for this source, so fall back to ASR instead of raising.
        return None
    if data.get("script") is not None and not isinstance(data["script"], str):
        raise ValueError(f"sidecar {sidecar_path} script must be text or null")
    try:
        duration = float(data["duration"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"sidecar {sidecar_path} has a non-numeric duration") from exc
    if not math.isfinite(duration) or abs(duration - measured["duration"]) > SIDECAR_DURATION_TOLERANCE:
        raise ValueError(f"sidecar {sidecar_path} duration does not match the decoded source")
    recorded_hash = data.get("pcm_sha256")
    if recorded_hash and recorded_hash != measured["pcm_sha256"]:
        raise ValueError(f"sidecar {sidecar_path} pcm_sha256 does not match the decoded source")
    # Validate intervals against the ACTUAL decoded duration (not the
    # declared "duration" field, which is itself only checked to within
    # SIDECAR_DURATION_TOLERANCE of the truth): otherwise a word/segment/
    # caption could end up to ~0.15s past the real audio boundary and still
    # pass, which would then spill into the next source's region once
    # combine_sidecar_timelines() offsets it by the real (precise) duration.
    _validate_sidecar_intervals(sidecar_path, data.get("words") or [], "word", measured["duration"])
    _validate_sidecar_intervals(sidecar_path, data.get("segments") or [], "text", measured["duration"])
    _validate_sidecar_intervals(sidecar_path, data.get("captions") or [], "text", measured["duration"])
    return data


def combine_sidecar_timelines(sidecars, durations, gap_seconds):
    """durations must be the unrounded, exactly-decoded per-source durations
    (not the rounded measurement field) so concat offsets do not accumulate
    rounding drift across many sources."""
    words, segments, captions, transcripts, scripts, languages = [], [], [], [], [], []
    cursor = 0.0
    for sidecar, duration in zip(sidecars, durations):
        offset = cursor
        for w in sidecar.get("words") or []:
            words.append({**w, "start": round(w["start"] + offset, 3), "end": round(w["end"] + offset, 3)})
        for seg in sidecar.get("segments") or []:
            segments.append({"start": round(seg["start"] + offset, 3), "end": round(seg["end"] + offset, 3), "text": seg["text"]})
        for cap in sidecar.get("captions") or []:
            captions.append({**cap, "start": round(cap["start"] + offset, 3), "end": round(cap["end"] + offset, 3)})
        if sidecar.get("transcript"):
            transcripts.append(sidecar["transcript"])
        scripts.append(sidecar.get("script"))
        languages.append(sidecar.get("language"))
        cursor += duration + gap_seconds
    language = languages[0] if languages and all(l == languages[0] for l in languages) else None
    script = "\n".join(scripts) if scripts and all(scripts) else None
    return {
        "words": words, "segments": segments, "captions": captions,
        "transcript": " ".join(transcripts), "script": script, "language": language,
    }


# --------------------------------------------------------------------------
# CLI: track
# --------------------------------------------------------------------------

def _publish(out, temp_dir):
    """Exclusively publish the built bundle from temp_dir into out. out must not
    already exist (fresh_output_dir enforces that). If any rename fails
    partway through, every already-moved file is moved back into temp_dir and
    the (now-empty) out directory is removed, so a failure never leaves a
    partial bundle behind and never touches anything that pre-existed."""
    files = sorted(p.name for p in temp_dir.iterdir())
    out.mkdir()
    moved = []
    try:
        for name in files:
            (temp_dir / name).rename(out / name)
            moved.append(name)
    except OSError:
        for name in moved:
            (out / name).rename(temp_dir / name)
        out.rmdir()
        raise
    return files


def track(args):
    validate_slug(args.slug)
    out = fresh_output_dir(args.out)
    ensure_parent_exists(out)
    source = resolve_source(args.source)
    script = read_script_file(args.script_file, TRACK_SCRIPT_MAX_CHARS) if args.script_file else None
    take = load_take_file(args.take_file) if args.take_file else None

    measured, pcm, input_measure = decode_and_measure(source)
    # ASR runs on the actual decoded master (mono 48k), not the original
    # source file, so a multichannel/foreign-rate source is heard the same
    # way the published master will be heard.
    asr = _transcribe_pcm(pcm, measured["duration"], args.language)
    words_nonempty = bool(asr["words"])

    if script:
        readback = readback_compare(script, asr["transcript"], words_nonempty)
        captions = captions_from_text(script, asr["words"], measured["duration"], "script")
    else:
        readback = None
        captions = captions_from_text(asr["transcript"], asr["words"], measured["duration"], "transcript")

    cps = cps_warning(asr["language"], len(asr["transcript"]), measured["duration"])

    with tempfile.TemporaryDirectory(prefix=".speech-track-", dir=out.parent) as temp:
        temp = Path(temp)
        wav_name = f"speech_{args.slug}.wav"
        wav_path = temp / wav_name
        write_wav(wav_path, pcm)
        derivatives = {"wav": measure_output_file(wav_path)}
        voice_message_file = None
        if args.voice_message:
            ogg_name = f"speech_{args.slug}.ogg"
            ogg_path = temp / ogg_name
            encode_derivative(pcm, "ogg", ogg_path)
            derivatives["ogg"] = measure_output_file(ogg_path)
            voice_message_file = ogg_name
        words_json = {
            "file": wav_name, "duration": measured["duration"], "language": asr["language"],
            "script": script, "transcript": asr["transcript"], "segments": asr["segments"],
            "words": asr["words"], "captions": captions, "alignment": "estimated-from-asr",
            "readback": readback, "pcm_sha256": measured["pcm_sha256"], "cps": cps,
            "voice_message": bool(args.voice_message), "voice_message_file": voice_message_file,
            "input_measure": input_measure, "derivatives": derivatives,
        }
        (temp / f"speech_{args.slug}.words.json").write_text(
            json.dumps(words_json, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8",
        )
        (temp / f"speech_{args.slug}.srt").write_text(captions_to_srt(captions), encoding="utf-8")
        if script:
            (temp / f"speech_{args.slug}.script.txt").write_text(script + "\n", encoding="utf-8")
        take_json = build_take_json(
            take, "track", [source], measured["pcm_sha256"], [measured["pcm_sha256"]], [],
        )
        (temp / f"speech_{args.slug}.take.json").write_text(
            json.dumps(take_json, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8",
        )
        files = _publish(out, temp)

    status = readback["script_match"] if readback else "unverified"
    return {
        "bundle": str(out), "files": [str(out / f) for f in files], "measure": measured,
        "input_measure": input_measure, "derivatives": derivatives,
        "readback": readback, "status": status, "language": asr["language"], "cps": cps,
    }


# --------------------------------------------------------------------------
# CLI: edit
# --------------------------------------------------------------------------

def parse_operations(raw):
    if not raw or not raw.strip():
        raise ValueError("--operations is required and must not be empty")
    ops = [o.strip() for o in raw.split(",")]
    if any(not o for o in ops):
        raise ValueError("operations must not contain empty entries")
    if len(ops) != len(set(ops)):
        raise ValueError("operations must not contain duplicates")
    unknown = [o for o in ops if o not in OPERATION_ORDER]
    if unknown:
        raise ValueError(f"unknown operations: {', '.join(unknown)}")
    return set(ops)


def validate_edit_args(args, ops):
    if args.target_lufs is not None and (not math.isfinite(args.target_lufs) or not (-36 <= args.target_lufs <= -5)):
        raise ValueError("target-lufs must be finite and between -36 and -5")
    if args.gap_ms is not None and (not math.isfinite(args.gap_ms) or not (0 <= args.gap_ms <= 10000)):
        raise ValueError("gap-ms must be finite and between 0 and 10000")
    if args.speed is not None and (not math.isfinite(args.speed) or not (0.25 <= args.speed <= 4)):
        raise ValueError("speed must be finite and between 0.25 and 4")
    if "speed" not in ops and args.speed is not None and args.speed != 1.0:
        raise ValueError("--speed requires the speed operation")
    if "concat" not in ops and args.gap_ms is not None:
        raise ValueError("--gap-ms requires the concat operation")
    if "normalize" not in ops and args.target_lufs is not None:
        raise ValueError("--target-lufs requires the normalize operation")
    if args.format is not None and "convert" not in ops:
        raise ValueError("--format requires the convert operation")
    if "convert" in ops and args.format is None:
        raise ValueError("the convert operation requires --format")


def edit(args):
    ops = parse_operations(args.operations)
    validate_slug(args.slug)
    out = fresh_output_dir(args.out)
    ensure_parent_exists(out)
    sources = [resolve_source(s) for s in args.sources]
    if not sources:
        raise ValueError("at least one source is required")
    if len(sources) > MAX_EDIT_SOURCES:
        raise ValueError(f"at most {MAX_EDIT_SOURCES} sources are supported")
    if len(sources) > 1 and "concat" not in ops:
        raise ValueError("multiple sources require --operations to include concat")
    validate_edit_args(args, ops)
    script = read_script_file(args.script_file, EDIT_SCRIPT_MAX_CHARS) if args.script_file else None

    measured_list, pcm_list = [], []
    total_seconds = 0.0
    for src in sources:
        total_seconds += probe(src)["duration"]
        if total_seconds > MAX_MEDIA_SECONDS:
            raise ValueError(f"aggregate input exceeds the {MAX_MEDIA_SECONDS}s media cap")
        m, pcm, _input_measure = decode_and_measure(src)
        measured_list.append(m)
        pcm_list.append(pcm)

    gap_ms = args.gap_ms if args.gap_ms is not None else 200
    joined_duration = sum(len(p) / (2 * SAMPLE_RATE) for p in pcm_list)
    if "concat" in ops:
        joined_duration += gap_ms / 1000 * (len(sources) - 1)
    if joined_duration > MAX_MEDIA_SECONDS:
        raise ValueError(f"concat including gaps exceeds the {MAX_MEDIA_SECONDS}s media cap")
    timing_changed = bool({"trim", "speed"} & ops)
    sidecars = [load_valid_sidecar(src, m) for src, m in zip(sources, measured_list)]
    reuse_sidecars = (not timing_changed) and all(sidecars)

    # Fixed pipeline order: concat -> trim -> speed -> normalize -> convert.
    pcm = concat_pcm(pcm_list, gap_ms) if "concat" in ops else pcm_list[0]
    if "trim" in ops:
        leading, trailing = silence_bounds(pcm)
        pcm = trim_pcm(pcm, leading, trailing)
    if "speed" in ops:
        speed = args.speed or 1.0
        # Check the effective (post-trim, if trimmed) output duration against
        # the cap BEFORE running atempo: a slow-down factor on a long buffer
        # would otherwise only be caught after the (potentially very slow)
        # atempo pass had already run to completion.
        effective_seconds = (len(pcm) // 2) / SAMPLE_RATE / speed
        if effective_seconds > MAX_MEDIA_SECONDS:
            raise ValueError(f"post-speed output would exceed the {MAX_MEDIA_SECONDS}s media cap")
        pcm = apply_speed(pcm, speed)
    if "normalize" in ops:
        pcm = normalize_pcm(pcm, args.target_lufs if args.target_lufs is not None else -16)

    final_measured = measure_pcm_bytes(pcm)
    if final_measured["duration"] > MAX_MEDIA_SECONDS:
        raise ValueError(f"output exceeds the {MAX_MEDIA_SECONDS}s media cap")

    if reuse_sidecars:
        # Unrounded per-source durations, not the rounded measurement field,
        # so concat offsets do not accumulate rounding drift.
        precise_durations = [(len(p) // 2) / SAMPLE_RATE for p in pcm_list]
        combined = combine_sidecar_timelines(
            sidecars, precise_durations, gap_ms / 1000.0 if "concat" in ops else 0.0,
        )
        language, transcript = combined["language"], combined["transcript"]
        segments, words = combined["segments"], combined["words"]
        if script:
            # An explicit new script invalidates the inherited captions (they
            # were built against the OLD script's text); rebuild them against
            # the new script using the reused word timeline instead of just
            # re-bounding the stale ones to the final duration.
            script_used = script
            captions = captions_from_text(script_used, words, final_measured["duration"], "script")
        else:
            script_used = combined["script"]
            captions = combined["captions"]
            for cap in captions:  # bound to the actual final master duration
                cap["end"] = min(cap["end"], final_measured["duration"])
                cap["start"] = min(cap["start"], cap["end"])
    else:
        asr = _transcribe_pcm(pcm, final_measured["duration"], args.language)
        words, segments, transcript, language = asr["words"], asr["segments"], asr["transcript"], asr["language"]
        if script:
            script_used = script
        elif sidecars and all(s and s.get("script") for s in sidecars):
            script_used = "\n".join(s["script"] for s in sidecars)
        else:
            script_used = None
        captions = captions_from_text(
            script_used or transcript, words, final_measured["duration"],
            "script" if script_used else "transcript",
        )

    readback = readback_compare(script_used, transcript, bool(words)) if script_used else None
    cps = cps_warning(language, len(transcript), final_measured["duration"])

    with tempfile.TemporaryDirectory(prefix=".speech-edit-", dir=out.parent) as temp:
        temp = Path(temp)
        wav_name = f"speech_{args.slug}.wav"
        wav_path = temp / wav_name
        write_wav(wav_path, pcm)
        derivatives = {"wav": measure_output_file(wav_path)}
        if "convert" in ops and args.format != "wav":
            deriv_path = temp / f"speech_{args.slug}.{args.format}"
            encode_derivative(pcm, args.format, deriv_path)
            derivatives[args.format] = measure_output_file(deriv_path)
        words_json = {
            "file": wav_name, "duration": final_measured["duration"], "language": language,
            "script": script_used, "transcript": transcript, "segments": segments, "words": words,
            "captions": captions, "alignment": "estimated-from-asr", "readback": readback,
            "pcm_sha256": final_measured["pcm_sha256"], "cps": cps, "operations": sorted(ops, key=OPERATION_ORDER.index),
            "derivatives": derivatives,
        }
        (temp / f"speech_{args.slug}.words.json").write_text(
            json.dumps(words_json, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8",
        )
        (temp / f"speech_{args.slug}.srt").write_text(captions_to_srt(captions), encoding="utf-8")
        if script_used:
            (temp / f"speech_{args.slug}.script.txt").write_text(script_used + "\n", encoding="utf-8")
        lineage = [str(s) for s in sources]
        take_json = build_take_json(
            None, "edit", sources, final_measured["pcm_sha256"],
            [m["pcm_sha256"] for m in measured_list], lineage,
        )
        (temp / f"speech_{args.slug}.take.json").write_text(
            json.dumps(take_json, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8",
        )
        files = _publish(out, temp)

    status = readback["script_match"] if readback else "unverified"
    return {
        "bundle": str(out), "files": [str(out / f) for f in files],
        "operations": sorted(ops, key=OPERATION_ORDER.index), "measure": final_measured,
        "derivatives": derivatives,
        "readback": readback, "status": status, "language": language, "cps": cps,
        "sources": [str(s) for s in sources], "sidecars_reused": reuse_sidecars,
    }


def _transcribe_pcm(pcm, duration, language):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        write_wav(tmp_path, pcm)
        return transcribe(tmp_path, duration, language)
    finally:
        tmp_path.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# CLI: analyze
# --------------------------------------------------------------------------

def analyze(args):
    source = resolve_source(args.source)
    script = read_script_file(args.script_file, EDIT_SCRIPT_MAX_CHARS) if args.script_file else None
    measured, pcm, input_measure = decode_and_measure(source)
    asr = _transcribe_pcm(pcm, measured["duration"], args.language)
    words_nonempty = bool(asr["words"])
    readback = readback_compare(script, asr["transcript"], words_nonempty) if script else None
    cps = cps_warning(asr["language"], len(asr["transcript"]), measured["duration"])
    return {
        "source": str(source), "measure": measured, "input_measure": input_measure,
        "language": asr["language"],
        "transcript": asr["transcript"], "segments": asr["segments"], "words": asr["words"],
        "script": script, "readback": readback, "cps": cps, "perceptual_quality": "unverified",
    }


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    p_track = commands.add_parser("track", help="decode+transcribe a source into a speech bundle")
    p_track.add_argument("source")
    p_track.add_argument("--script-file", required=True)
    p_track.add_argument("--out", required=True)
    p_track.add_argument("--slug", default="speech")
    p_track.add_argument("--language")
    p_track.add_argument("--take-file")
    p_track.add_argument("--voice-message", action="store_true")

    p_edit = commands.add_parser("edit", help="concat/trim/speed/normalize/convert into a bundle")
    p_edit.add_argument("sources", nargs="+")
    p_edit.add_argument("--out", required=True)
    p_edit.add_argument("--slug", default="speech")
    p_edit.add_argument("--operations", required=True)
    p_edit.add_argument("--target-lufs", type=float)
    p_edit.add_argument("--gap-ms", type=float)
    p_edit.add_argument("--speed", type=float)
    p_edit.add_argument("--format", choices=("wav", "ogg", "mp3"))
    p_edit.add_argument("--script-file")
    p_edit.add_argument("--language")

    p_analyze = commands.add_parser("analyze", help="measure+transcribe a source, no deliverable")
    p_analyze.add_argument("source")
    p_analyze.add_argument("--script-file")
    p_analyze.add_argument("--language")

    args = parser.parse_args()
    try:
        if args.command == "track":
            result = track(args)
        elif args.command == "edit":
            result = edit(args)
        else:
            result = analyze(args)
    except DependencyError as exc:
        parser.exit(2, f"speech-media: {exc}\n")
        return
    except (ValueError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, ZeroDivisionError) as exc:
        if isinstance(exc, subprocess.CalledProcessError):
            stderr = exc.stderr
            detail = stderr.decode("utf-8", "replace") if isinstance(stderr, bytes) else (stderr or "")
            detail = detail[-3000:]
        else:
            detail = str(exc)
        parser.exit(1, f"speech-media: {detail}\n")
        return

    print("RESULT: " + json.dumps(result, ensure_ascii=True, allow_nan=False))
    if result.get("readback", {}) and result["readback"].get("script_match") == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
