#!/usr/bin/env python3
"""Offline music score rendering, track packaging, editing and musical estimates.

Only numpy and ffmpeg/ffprobe are required. No network, model installation,
generation, speech recognition or listening verification is performed here.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
import tempfile
import wave

try:
    import numpy as np
except ImportError:
    np = None

RATE = 48000
MAX_SECONDS = 600
MAX_BYTES = 128 * 1024 * 1024
TEXT_BYTES = 2 * 1024 * 1024
COLORS = ("sine", "triangle", "pulse", "fm-bell", "noise")
ORDER = ("trim", "repeat-crossfade-to-length", "fades", "gain", "optional-two-pass-lufs", "pcm16")
PITCH_CLASSES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


class DependencyError(RuntimeError):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"nonfinite JSON: {value}")

    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    json.dumps(result, allow_nan=False)
    return result


def numeric(value, low, high, label, integer=False):
    if (type(value) not in ((int,) if integer else (int, float))
            or not low <= value <= high or not math.isfinite(value)):
        raise ValueError(f"{label} must be a finite {'integer' if integer else 'number'} in [{low}, {high}]")
    return value


def number(low, high, integer=False):
    def parse(value):
        try:
            if isinstance(value, bool):
                raise ValueError
            return numeric(int(value) if integer else float(value), low, high, "argument", integer)
        except (ValueError, TypeError, OverflowError):
            raise argparse.ArgumentTypeError(f"expected finite {'integer' if integer else 'number'} in [{low}, {high}]") from None
    return parse


def slug(value):
    if not isinstance(value, str) or len(value) > 80 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
        raise ValueError("slug/id must be 1..80 lowercase ASCII letters/digits separated by hyphens")
    return value


def keys(obj, required, optional, label):
    if not isinstance(obj, dict) or not required <= obj.keys() or obj.keys() - required - optional:
        raise ValueError(f"{label}: required keys {sorted(required)}, optional keys {sorted(optional)}; unknown keys refused")


def validate_score(score):
    """Validate the authoritative v1 schema without modifying it; return score.

    Timing is in quarter-note beats, including 6/8. Endpoints use Python's
    nearest-sample round (ties to even); notes must retain at least two samples.
    """
    keys(score, {"version", "duration_seconds", "bpm", "meter", "key", "tracks"}, {"seed"}, "score")
    numeric(score["version"], 1, 1, "version", True)
    seconds = numeric(score["duration_seconds"], 1, 60, "duration_seconds")
    bpm = numeric(score["bpm"], 40, 240, "bpm")
    numeric(score.get("seed", 0), 0, 2**32 - 1, "seed", True)
    if score["meter"] not in ("4/4", "3/4", "6/8"):
        raise ValueError("meter must be 4/4, 3/4 or 6/8 (quarter-beat timing in all meters)")
    if not isinstance(score["key"], str) or not score["key"].strip() or len(score["key"]) > 40:
        raise ValueError("key must be nonempty text <=40 characters; it is a label, not a pitch constraint")
    tracks = score["tracks"]
    if not isinstance(tracks, list) or len(tracks) > 8:
        raise ValueError("tracks must be an array of at most 8 tracks")
    ids, events = set(), 0
    for track in tracks:
        keys(track, {"id", "instrument", "notes"}, {"gain_db", "pan"}, "track")
        ident = slug(track["id"])
        if ident in ids:
            raise ValueError("track ids must be unique")
        ids.add(ident)
        if track["instrument"] not in COLORS:
            raise ValueError(f"instrument must be a supported synthetic color: {COLORS}")
        numeric(track.get("gain_db", -12), -60, 0, "track gain_db")
        numeric(track.get("pan", 0), -1, 1, "pan")
        if not isinstance(track["notes"], list):
            raise ValueError("notes must be an array")
        events += len(track["notes"])
        if events > 2048:
            raise ValueError("score exceeds 2048 note events")
        for note in track["notes"]:
            keys(note, {"pitch", "start", "duration"}, {"velocity"}, "note")
            numeric(note["pitch"], 24, 96, "pitch", True)
            start = numeric(note["start"], 0, 240, "note start")
            duration = numeric(note["duration"], 0, 240, "note duration")
            numeric(note.get("velocity", .8), 0, 1, "velocity")
            end = (start + duration) * 60 / bpm
            if duration <= 0 or end > seconds:
                raise ValueError("note duration must be positive and the complete envelope must fit declared duration")
            a, b = round(start * 60 / bpm * RATE), round(end * RATE)
            if b - a < 2 or b > round(seconds * RATE):
                raise ValueError("note must occupy at least two samples and fit after timing quantization")
    return score


def render_score(score):
    validate_score(score)
    output = np.zeros((round(score["duration_seconds"] * RATE), 2), dtype=np.float64)
    rng = np.random.Generator(np.random.PCG64(score.get("seed", 0)))
    timing = []
    for track in score["tracks"]:
        pan = (track.get("pan", 0) + 1) * math.pi / 4
        gains = np.array([math.cos(pan), math.sin(pan)]) * 10 ** (track.get("gain_db", -12) / 20)
        for index, note in enumerate(track["notes"]):
            a = round(note["start"] * 60 / score["bpm"] * RATE)
            b = round((note["start"] + note["duration"]) * 60 / score["bpm"] * RATE)
            n = b - a
            frequency = 440 * 2 ** ((note["pitch"] - 69) / 12)
            kind = track["instrument"]
            if kind == "sine":
                partials = [(frequency, 1.)]
            elif kind in ("triangle", "pulse"):
                partials = [(frequency * k, (8 / math.pi**2 * (-1)**((k - 1) // 2) / k**2
                             if kind == "triangle" else 4 / math.pi / k))
                            for k in range(1, 32, 2) if frequency * k < RATE / 2]
            elif kind == "fm-bell":
                # Finite FM sidebands (index 1, modulator ratio 2.71), not a
                # naive phase modulator whose infinite sidebands would alias.
                partials = []
                for k in range(-6, 7):
                    order = abs(k)
                    coefficient = sum((-1)**j * .5**(2 * j + order)
                                      / (math.factorial(j) * math.factorial(j + order)) for j in range(12))
                    coefficient *= (-1)**order if k < 0 else 1
                    f = frequency * (1 + k * 2.71)
                    if 0 < abs(f) < RATE / 2:
                        partials.append((f, coefficient / 2.))
            else:
                partials = []
            attack, release = min(240, n // 2), min(480, n // 2)
            for lo in range(0, n, 65536):
                hi = min(n, lo + 65536)
                positions = np.arange(lo, hi, dtype=np.float64)
                if kind == "noise":
                    signal = rng.uniform(-1, 1, hi - lo)
                else:
                    signal = np.zeros(hi - lo)
                    for f, coefficient in partials:
                        signal += coefficient * np.sin(2 * math.pi * f / RATE * positions)
                envelope = np.minimum(positions / max(1, attack - 1), 1)
                envelope *= np.minimum((n - 1 - positions) / max(1, release - 1), 1)
                if kind == "fm-bell":
                    envelope *= np.exp(-4 * positions / n)
                signal *= envelope * note.get("velocity", .8)
                output[a + lo:a + hi] += signal[:, None] * gains
            timing.append({"track_id": track["id"], "note_index": index, "pitch": note["pitch"],
                           "start_frame": a, "end_frame_exclusive": b,
                           "start_seconds": a / RATE, "end_seconds": b / RATE})
    return output, {"notes": timing, "timing_units": "quarter-note beats in every meter",
                    "quantization": "48 kHz nearest sample; ties to even; end exclusive",
                    "envelope": "linear attack <=5ms and release <=10ms inside note duration; FM exponential decay inside envelope",
                    "synthesis": "sine; triangle/pulse odd partials 1..31 below Nyquist; finite FM sidebands; PCG64 uniform noise",
                    "level_policy": "equal-power pan; fixed Fourier/FM coefficients; no mix normalization or limiter",
                    "scope": "synthetic colors only; no acoustic-instrument realism"}


def local_bytes(name, limit=MAX_BYTES):
    path = Path(name).expanduser().absolute()
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError(f"input must be a regular local file <={limit} bytes; devices and symlinks refused")
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise ValueError(f"input exceeds {limit} bytes")
    return path, raw


def run(args, data=None):
    try:
        return subprocess.run([str(a) for a in args], input=data, capture_output=True, check=True, timeout=120)
    except FileNotFoundError as exc:
        raise DependencyError(f"required tool missing: {args[0]}") from exc


def audio_format(raw):
    # Force a standalone demuxer BEFORE probing. Playlists, concat, containers
    # with external references and protocol-looking text never reach autodetect.
    if raw[:4] in (b"RIFF", b"RF64") and raw[8:12] == b"WAVE":
        return "wav"
    if raw.startswith(b"fLaC"):
        return "flac"
    if raw.startswith(b"OggS"):
        return "ogg"
    if raw[:4] == b"FORM" and raw[8:12] in (b"AIFF", b"AIFC"):
        return "aiff"
    if raw.startswith(b"ID3") or (len(raw) >= 2 and raw[0] == 255 and raw[1] & 224 == 224):
        return "mp3"
    raise ValueError("unsupported local audio signature; only WAV, FLAC, Ogg, MP3 and AIFF; no playlists/references")


def decode(path, raw):
    fmt = audio_format(raw)
    info = strict_json(run(["ffprobe", "-v", "error", "-protocol_whitelist", "file",
                            "-format_whitelist", fmt, "-f", fmt, "-show_streams", "-of", "json", path]).stdout)
    streams = info.get("streams", [])
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    if len(audio) != 1:
        raise ValueError("input must contain exactly one audio stream")
    stream = audio[0]
    channels, rate = int(stream.get("channels", 0)), int(stream.get("sample_rate", 0))
    if channels not in (1, 2) or not 1 <= rate <= 384000:
        raise ValueError("input must be mono/stereo at a native rate of 1..384000 Hz")
    # Both time AND byte caps apply to the resampled output, independent of the
    # container's duration/sample-rate claims. The extra 10ms detects overrun.
    cap = math.ceil((MAX_SECONDS + .01) * RATE) * channels * 4
    decoded = run(["ffmpeg", "-nostdin", "-v", "info", "-xerror", "-protocol_whitelist", "file",
                   "-format_whitelist", fmt, "-f", fmt, "-i", path, "-map", f"0:{stream['index']}",
                   "-af", "aformat=sample_fmts=dbl,astats=metadata=0:reset=0,aresample=48000",
                   "-t", "600.01", "-fs", cap, "-ar", RATE, "-ac", channels,
                   "-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"])
    samples = np.frombuffer(decoded.stdout, dtype="<f4").reshape(-1, channels)
    if not len(samples) or len(samples) > MAX_SECONDS * RATE:
        raise ValueError("decoded duration must be positive and <=600 seconds; no silent truncation")
    if not np.isfinite(samples).all():
        raise ValueError("decoded audio contains nonfinite samples")
    log = decoded.stderr.decode("utf-8", errors="replace")
    counts = re.findall(r"Number of samples: (\d+)", log)
    if not counts:
        raise DependencyError("native pre-resampling frame-count evidence unavailable")
    native_frames = int(counts[-1])
    if native_frames > MAX_SECONDS * rate:
        raise ValueError("native decoded duration exceeds 600 seconds; no sub-sample overrun is discarded")
    native_peaks = [float(x) for x in re.findall(r"Peak level dB: (\S+)", log)]
    if not native_peaks:
        raise DependencyError("native pre-resampling peak evidence unavailable")
    for label in ("NaNs", "Infs"):
        if any(float(x) for x in re.findall(rf"Number of {label}: (\S+)", log)):
            raise ValueError("native audio contains nonfinite samples")
    finite_peaks = [v for v in native_peaks if math.isfinite(v)]
    native_peak = max(finite_peaks) if finite_peaks else None
    integer = re.match(r"pcm_[su](8|16|24|32|64)", stream.get("codec_name", ""))
    bits = int(integer[1]) if integer else int(stream.get("bits_per_raw_sample", 0) or 0) if fmt == "flac" else 0
    threshold = 20 * math.log10(1 - 2 ** (1 - bits)) if 1 < bits < 64 else 0.
    clipped = native_peak is not None and native_peak >= threshold - .0000005
    native = {"sample_rate": rate, "channels": channels, "codec": stream.get("codec_name"),
              "decoded_frames": native_frames, "decoded_duration_seconds": native_frames / rate,
              "container": fmt, "stream": stream, "sample_peak_dbfs": native_peak,
              "clipping_detected": clipped, "peak_method": "ffmpeg astats before resampling; rounded to 0.000001 dB",
              "measurements_rate_note": "native metadata/peak above; all decoded PCM measurements are at 48000 Hz"}
    return samples, native


def measure(samples, codec="pcm_f32le"):
    peak = float(np.max(np.abs(samples)))
    duration = len(samples) / RATE
    threshold = 32767 / 32768 if codec == "pcm_s16le" else 1.
    clipped = (samples >= threshold) | (samples <= -1)
    over = (samples > 1) | (samples < -1)
    padding = max(0., .4 - duration)
    log = run(["ffmpeg", "-nostdin", "-v", "info", "-f", "f32le", "-ar", RATE,
               "-ac", samples.shape[1], "-i", "pipe:0", "-af",
               f"apad=pad_dur={padding},loudnorm=print_format=json", "-f", "null", "-"],
              samples.astype("<f4").tobytes()).stderr.decode("utf-8", errors="replace")
    matches = re.findall(r"\{[^{}]*\}", log)
    if not matches:
        raise DependencyError("ffmpeg loudnorm measurement unavailable")
    evidence = strict_json(matches[-1])

    def finite(key):
        value = float(evidence[key])
        return value if math.isfinite(value) else None

    lufs = finite("input_i") if peak and duration >= .4 else None
    true_peak = finite("input_tp") if peak else None
    silence = peak <= 1e-3
    failures = []
    if clipped.any():
        failures.append("full-scale or out-of-range samples detected before/following quantization")
    if true_peak is not None and true_peak >= 0:
        failures.append("true peak reaches/exceeds 0 dBTP")
    warnings = (["silence or very low signal (peak <=-60 dBFS)"] if silence else [])
    if lufs is None:
        warnings.append("integrated LUFS unavailable for silence/short/ungated material")
    return {"status": "FAIL" if failures else "WARN" if warnings else "PASS", "failures": failures,
            "warnings": warnings, "frames": len(samples), "duration_seconds": duration,
            "sample_rate": RATE, "channels": samples.shape[1], "codec": codec,
            "pcm_sha256": digest(samples.astype("<f4").tobytes()),
            "pcm_hash_format": "interleaved f32le decoded samples at 48000 Hz and reported channels",
            "sample_peak_dbfs": 20 * math.log10(peak) if peak else None,
            "clipping_count": int(clipped.sum()), "out_of_range_count": int(over.sum()),
            "clipping_count_per_channel": clipped.sum(axis=0).tolist(), "silence": silence,
            "integrated_lufs": lufs, "true_peak_dbtp": true_peak, "loudnorm_evidence": evidence,
            "true_peak_measurement_padding_seconds": padding,
            "dc_offset_per_channel": samples.mean(axis=0, dtype=np.float64).tolist(),
            "boundary_sample_delta_per_channel": (samples[0].astype(float) - samples[-1]).tolist(),
            "seamless_loop": "unverified", "auditory_quality": "unverified"}


def trim(samples, start, end):
    end = len(samples) / RATE if end is None else end
    if not 0 <= start < end <= len(samples) / RATE:
        raise ValueError("trim requires 0 <= start < end <= decoded source duration")
    a, b = round(start * RATE), round(end * RATE)
    if b <= a:
        raise ValueError("trim contains no samples after quantization")
    return samples[a:b], {"start_frame": a, "end_frame_exclusive": b,
                          "start_seconds": a / RATE, "end_seconds": b / RATE}


def repeat_seams(samples, segment, cross, stage):
    """Measure only actual repeat boundaries, without scanning every repeat."""
    length = segment["end_frame_exclusive"] - segment["start_frame"]
    step = length - cross
    total = max(0, (len(samples) - length + step - 1) // step)
    seams = []
    for index in range(1, min(total, 1024) + 1):
        offset = index * step
        seam = {"repeat_index": index, "offset_frame": offset, "offset_seconds": offset / RATE,
                "delta_per_channel": (samples[offset].astype(float) - samples[offset - 1]).tolist(),
                "crossfade_start": None, "crossfade_end_exclusive": None}
        if cross:
            for name, frame in (("crossfade_start", offset), ("crossfade_end_exclusive", offset + cross)):
                seam[name] = {"frame": frame, "time_seconds": frame / RATE,
                              "delta_per_channel": (samples[frame].astype(float) - samples[frame - 1]).tolist()}
        seams.append(seam)
    return {"stage": stage, "total_count": total, "reported_count": len(seams),
            "omitted_count": total - len(seams), "limit": 1024, "seams": seams,
            "coordinates": "output-relative frames/seconds; original trim bounds remain in source_segment",
            "method": "sample[frame] minus sample[frame-1] per channel; crossfade end is exclusive; first 1024 repeats only",
            "verification": "NOT seamless-loop verification"}


def edit(samples, args):
    samples, segment = trim(samples, args.start, args.end)
    length = len(samples)
    target = length if args.loop_seconds is None else round(args.loop_seconds * RATE)
    cross = round(args.crossfade_ms * RATE / 1000)
    if args.crossfade_ms and args.loop_seconds is None:
        raise ValueError("crossfade requires --loop-seconds")
    if args.loop_seconds is not None and (args.loop_seconds < length / RATE or target < length):
        raise ValueError("loop target cannot be shorter than trimmed source; trim separately")
    if target < 1 or target > MAX_SECONDS * RATE:
        raise ValueError("edited output must be positive and <=600 seconds")
    if cross >= length:
        raise ValueError("repeat source length minus crossfade must be positive (no zero-step repeat)")
    if cross and target == length:
        raise ValueError("crossfade requires actual repetition beyond trimmed source length")
    repeat_work = math.ceil(max(0, target - length) / (length - cross)) * length
    if repeat_work > 128_000_000:
        raise ValueError("repeat/crossfade exceeds bounded DSP work (128 million source frames); use a shorter crossfade")
    if max(args.fade_in_ms, args.fade_out_ms) / 1000 > target / RATE:
        raise ValueError("fade cannot exceed edited duration")
    output = np.zeros((target, samples.shape[1]), dtype=np.float64)
    output[:length] = samples
    filled = length
    while filled < target:
        offset = filled - cross
        n = min(length, target - offset)
        overlap = min(cross, n)
        if overlap:
            weights = np.linspace(0., 1., cross)[:overlap, None]
            output[offset:offset + overlap] *= 1 - weights
            output[offset:offset + overlap] += samples[:overlap] * weights
        output[offset + overlap:offset + n] = samples[overlap:n]
        filled = offset + n
    for ms, reverse in ((args.fade_in_ms, False), (args.fade_out_ms, True)):
        n = round(ms * RATE / 1000)
        if n:
            view = output[::-1] if reverse else output
            view[:n] *= np.linspace(0., 1., n)[:, None]
    output *= 10 ** (args.gain_db / 20)
    return output, {"order": ORDER, "source_segment": segment, "loop_frames": target,
                    "crossfade_frames": cross, "crossfade_curve": "linear complementary weights",
                    "gain_db": args.gain_db, "target_lufs": args.target_lufs,
                    "seams": repeat_seams(output, segment, cross, "post_fades_gain_float64"),
                    "pitch_tempo": "unchanged; repeats only, no time stretch or mixing different files"}


def normalize(samples, target, measured):
    evidence = measured["loudnorm_evidence"]
    if measured["integrated_lufs"] is None or any(not math.isfinite(float(evidence[k]))
            for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")):
        return samples, "LUFS normalization unavailable for silence/short/ungated material"
    # The first measurement must use the requested target, not loudnorm's default.
    first = run(["ffmpeg", "-nostdin", "-v", "info", "-f", "f32le", "-ar", RATE,
                 "-ac", samples.shape[1], "-i", "pipe:0", "-af",
                 f"loudnorm=I={target}:TP=-1:LRA=11:print_format=json", "-f", "null", "-"],
                samples.astype("<f4").tobytes())
    evidence = strict_json(re.findall(r"\{[^{}]*\}", first.stderr.decode())[-1])
    fields = {"measured_I": "input_i", "measured_TP": "input_tp", "measured_LRA": "input_lra",
              "measured_thresh": "input_thresh", "offset": "target_offset"}
    controls = ":".join(f"{key}={evidence[value]}" for key, value in fields.items())
    result = run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-f", "f32le", "-ar", RATE,
                  "-ac", samples.shape[1], "-i", "pipe:0", "-af",
                  f"loudnorm=I={target}:TP=-1:LRA=11:{controls}:linear=true,aresample=48000",
                  "-t", "600.01", "-fs", math.ceil(600.01 * RATE) * samples.shape[1] * 4,
                  "-ar", RATE, "-f", "f32le", "pipe:1"], samples.astype("<f4").tobytes())
    output = np.frombuffer(result.stdout, dtype="<f4").reshape(-1, samples.shape[1])
    if len(output) != len(samples) or not np.isfinite(output).all():
        raise ValueError("normalization changed frame count or produced nonfinite PCM")
    return output, {"method": "ffmpeg two-pass loudnorm; linear when feasible, dynamic limiter otherwise",
                    "target_i": target, "target_tp": -1, "target_lra": 11, "first_pass": evidence}


def musical_analysis(samples, offset=0., focus="overview"):
    """Bounded, channelwise STFT; never form a cancellation-prone mono sum."""
    fft, hop, batch = 4096, 480, 64
    frequencies = np.fft.rfftfreq(fft, 1 / RATE)
    selected = (frequencies >= 65) & (frequencies <= 2100)
    bins = np.rint(69 + 12 * np.log2(frequencies[selected] / 440)).astype(int) % 12
    window = np.hanning(fft)
    count = max(1, math.ceil(len(samples) / hop))
    chroma = np.zeros((count, 12))
    rms, centroid, flux, flatness = (np.zeros(count) for _ in range(4))
    previous = np.zeros(fft // 2 + 1)
    for begin in range(0, count, batch):
        end = min(count, begin + batch)
        frames = np.zeros((end - begin, fft, samples.shape[1]))
        for j, frame in enumerate(range(begin, end)):
            start = frame * hop
            chunk = samples[start:min(len(samples), start + fft)]
            frames[j, :len(chunk)] = chunk
            rms[frame] = np.sqrt(np.mean(chunk.astype(np.float64)**2))
        power = (np.abs(np.fft.rfft(frames * window[None, :, None], axis=1))**2).mean(axis=2)
        band_power = power[:, selected]
        flatness[begin:end] = np.exp(np.log(np.maximum(band_power, 1e-20)).mean(axis=1)) / np.maximum(band_power.mean(axis=1), 1e-20)
        magnitude = np.sqrt(power)
        total = magnitude.sum(axis=1)
        centroid[begin:end] = (magnitude * frequencies).sum(axis=1) / np.maximum(total, 1e-20)
        for pc in range(12):
            chroma[begin:end, pc] = power[:, selected][:, bins == pc].sum(axis=1)
        difference = np.diff(np.vstack((previous, magnitude)), axis=0)
        flux[begin:end] = np.maximum(difference, 0).sum(axis=1) / np.maximum(total, 1e-20)
        previous = magnitude[-1]
    active = rms > 1e-3
    distribution = chroma[active].sum(axis=0) if active.any() else np.zeros(12)
    distribution /= max(float(distribution.sum()), 1e-20)
    pitch_method = "4096-sample Hann STFT, 10ms hop; channelwise power averaged, 65..2100Hz bins folded to nearest equal-tempered pitch class"
    keys_found = []
    if active.any() and distribution.sum() and np.std(distribution) > .015:
        profiles = {"major": [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88],
                    "minor": [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]}
        candidates = []
        for mode, profile in profiles.items():
            for root in range(12):
                correlation = float(np.corrcoef(distribution, np.roll(profile, root))[0, 1])
                candidates.append({"key": f"{PITCH_CLASSES[root]} {mode}", "root": root, "mode": mode,
                                   "similarity": correlation})
        candidates.sort(key=lambda item: -item["similarity"])
        if candidates[0]["similarity"] >= .3:
            keys_found = candidates[:4]
            best = candidates[0]
            relative = ((best["root"] + 9) % 12, "minor") if best["mode"] == "major" else ((best["root"] + 3) % 12, "major")
            mate = next(c for c in candidates if (c["root"], c["mode"]) == relative)
            if mate not in keys_found:
                keys_found.append(mate)
            for candidate in keys_found:
                candidate["relative_of_top"] = candidate is mate
    key_report = {"status": "estimate" if keys_found else "unavailable", "candidates": keys_found,
                  "confidence": (max(0., keys_found[0]["similarity"] - keys_found[1]["similarity"])
                                 if keys_found else 0.),
                  "confidence_definition": "top-minus-runner-up profile correlation; not a calibrated probability",
                  "ambiguity": "relative major/minor and modal alternatives remain ambiguous; pitch histogram cannot establish tonal center",
                  "method": pitch_method + "; Krumhansl major/minor profile correlation",
                  "limits": "harmonics, sparse tones, detuning, percussion and key changes confound estimates; silence/flat evidence gives no key"}
    # Ignore the first frame's artificial zero-to-signal onset and final partial
    # windows; autocorrelation searches only 40..240 BPM, bounded to 150 lags.
    onset = flux.copy()
    # Do not magnify steady-tone FFT leakage/quantization noise into a beat.
    onset[onset < .03] = 0
    onset[0] = 0
    onset[-min(9, len(onset)):] = 0
    onset[~active] = 0
    if onset.max() > 0:
        onset /= onset.max()
    peaks = np.flatnonzero((onset[1:-1] > onset[:-2]) & (onset[1:-1] >= onset[2:]) & (onset[1:-1] > .2)) + 1
    sparse = []
    for peak in peaks:
        if not sparse or peak - sparse[-1] >= 15:
            sparse.append(int(peak))
        elif onset[peak] > onset[sparse[-1]]:
            sparse[-1] = int(peak)
    correlations = []
    if len(sparse) >= 4:
        for lag in range(25, min(151, len(onset) // 3)):
            left, right = onset[:-lag], onset[lag:]
            corr = float(np.dot(left, right) / max(math.sqrt(float(np.dot(left, left) * np.dot(right, right))), 1e-20))
            correlations.append((corr, lag))
    tempo, beats = [], []
    stability = 0.
    if correlations:
        strength, lag = max(correlations, key=lambda pair: pair[0] - pair[1] * .0001)
        if strength >= .35:
            bpm = 6000 / lag
            tempo = [{"bpm": bpm, "relation": "autocorrelation candidate", "strength": strength}]
            for factor, label in ((.5, "half-time ambiguity"), (2., "double-time ambiguity")):
                if 40 <= bpm * factor <= 240:
                    tempo.append({"bpm": bpm * factor, "relation": label, "strength": None})
            anchor = sparse[int(np.argmax(onset[sparse]))]
            errors = np.abs((np.array(sparse) - anchor + lag / 2) % lag - lag / 2)
            stability = float(np.mean(errors <= max(3, lag * .12)))
            if strength >= .5 and stability >= .8:
                phase = anchor % lag
                grid = np.arange(phase, len(onset), lag)
                # Candidate grid only where an onset supports it, not invented
                # beats across silence or extrapolated full-track certainty.
                beats = [offset + float(frame * hop / RATE) for frame in grid
                         if min(abs(np.array(sparse) - frame)) <= max(3, lag * .12)]
    windows, chord_windows = [], []
    triads = [(root, quality, (np.array(intervals) + root) % 12)
              for root in range(12) for quality, intervals in (("major", (0, 4, 7)), ("minor", (0, 3, 7)))]
    for a in range(0, count, 200):
        b = min(count, a + 200)
        energy = float(np.sqrt(np.mean(rms[a:b]**2)))
        weights = rms[a:b]**2
        brightness = float(np.average(centroid[a:b], weights=weights)) if weights.sum() else None
        pc = chroma[a:b].sum(axis=0)
        pc /= max(float(pc.sum()), 1e-20)
        windows.append({"start_seconds": offset + a * hop / RATE,
                        "end_seconds": offset + min(len(samples) / RATE, b * hop / RATE),
                        "rms_dbfs": 20 * math.log10(energy) if energy else None,
                        "spectral_centroid_hz": brightness,
                        "onset_activity": float(onset[a:b].mean()), "pitch_class_distribution": pc.tolist()})
        concentration = float(np.sort(pc)[-3:].sum())
        noise_flatness = float(np.average(flatness[a:b], weights=weights)) if weights.sum() else 1.
        chord_candidates = []
        reason = "silence_or_low_energy"
        if energy > 1e-3:
            reason = "diffuse_noise_like_or_sparse_pitch_evidence"
            if concentration >= .55 and noise_flatness < .3 and np.count_nonzero(pc >= .08) >= 3:
                norm = float(np.linalg.norm(pc)) * math.sqrt(3)
                chord_candidates = [{"chord": f"{PITCH_CLASSES[root]} {quality}",
                                     "root": PITCH_CLASSES[root], "quality": quality,
                                     "similarity": min(1., float(pc[tones].sum()) / norm)}
                                    for root, quality, tones in triads]
                chord_candidates.sort(key=lambda item: -item["similarity"])
                if chord_candidates[0]["similarity"] >= .7:
                    chord_candidates = chord_candidates[:3]
                    reason = None
                else:
                    chord_candidates = []
                    reason = "weak_triad_overlap"
        chord_windows.append({"start_seconds": windows[-1]["start_seconds"],
                              "end_seconds": windows[-1]["end_seconds"],
                              "status": "estimate" if chord_candidates else "unavailable",
                              "unavailable_reason": reason, "candidates": chord_candidates,
                              "top_three_pitch_class_mass": concentration, "spectral_flatness": noise_flatness})
    boundaries = []
    for previous, current in zip(windows, windows[1:]):
        delta_db = abs((current["rms_dbfs"] if current["rms_dbfs"] is not None else -120)
                       - (previous["rms_dbfs"] if previous["rms_dbfs"] is not None else -120))
        old, new = np.array(previous["pitch_class_distribution"]), np.array(current["pitch_class_distribution"])
        distance = float(1 - np.dot(old, new) / max(float(np.linalg.norm(old) * np.linalg.norm(new)), 1e-20)) if old.any() or new.any() else 0.
        delta_hz = abs((current["spectral_centroid_hz"] or 0) - (previous["spectral_centroid_hz"] or 0))
        if delta_db >= 6 or distance >= .3 or delta_hz >= 800:
            boundaries.append({"time_seconds": current["start_seconds"], "rms_change_db": delta_db,
                               "chroma_cosine_distance": distance, "centroid_change_hz": delta_hz})
    return {"focus": focus, "focus_use": "verbatim instruction for AudioCreator summary; all estimates returned",
            "segment": {"start_seconds": offset, "end_seconds": offset + len(samples) / RATE},
            "silence": not bool(active.any()),
            "silence_method": "no STFT frame RMS above -60 dBFS; low activity, not proof of digital silence",
            "tempo": {"status": "estimate" if tempo else "unavailable", "candidates": tempo,
                      "method": "positive channelwise spectral flux / spectral magnitude, >=0.03 activity gate; normalized onset autocorrelation, 40..240 BPM",
                      "limits": "half/double-time ambiguity; sparse, irregular or weak onsets yield no tempo; no meter inference"},
            "beats": {"status": "estimate" if beats else "unavailable", "times_seconds": beats,
                      "stability": stability, "method": "onset-supported grid at strongest tempo; >=0.5 autocorrelation and >=80% onset alignment",
                      "limits": "candidate beat locations at 10ms resolution with STFT lookahead bias <=85ms; not downbeats or verified performance timing"},
            "pitch_classes": {"labels": PITCH_CLASSES, "distribution": distribution.tolist(),
                              "method": pitch_method, "limits": "not note transcription; overtones and spectral leakage contribute"},
            "key": key_report,
            "chords": {"status": "estimate" if any(w["candidates"] for w in chord_windows) else "unavailable",
                       "windows": chord_windows,
                       "method": pitch_method + "; each 2s window compared with 24 equal-weight major/minor triad templates; top 3 cosine overlaps",
                       "similarity_definition": "cosine overlap in [0,1], not calibrated confidence or a chord-name verdict",
                       "gates": "RMS >-60 dBFS; top-three pitch-class mass >=0.55; >=3 pitch classes with mass >=0.08; energy-weighted spectral flatness <0.3; best overlap >=0.7",
                       "limits": "triad estimates only, not pitch-perfect transcription; inversions, extensions and transitions are not transcribed; harmonics and detuning confound results; 2s windows include up to 85ms STFT lookahead"},
            "activity": {"windows": windows, "method": "2s windows of RMS, spectral centroid, normalized onset flux and chroma",
                         "limits": "numeric energy/brightness descriptors only; windowed estimates, not named timbres, moods or instruments"},
            "structure": {"candidate_boundaries": boundaries,
                          "method": "adjacent 2s windows: >=6dB RMS change, >=0.3 chroma cosine distance or >=800Hz centroid change",
                          "limits": "candidate numeric changes only; no semantic verse/chorus labels; boundaries have 2s resolution"},
            "unverified": ["instrument identity", "genre", "vocal presence or absence", "performance quality", "auditory quality", "semantic song sections"],
            "memory_bound": {"stft_batch_frames": batch, "fft_samples": fft, "hop_samples": hop}}


def write_wav(path, samples):
    if not np.isfinite(samples).all() or np.any(samples > 1) or np.any(samples < -1):
        raise ValueError("refusing PCM16 quantization of nonfinite/out-of-range samples")
    # Only the +1 endpoint/nearest integer saturation is representational; the
    # caller records full-scale failure and never hides an over-range mix here.
    pcm = np.minimum(np.rint(samples * 32768), 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(samples.shape[1])
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(pcm.tobytes())
    return pcm.astype(np.float32) / 32768


def publish(temp, out):
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        fn = libc.renamex_np
        fn.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint)
        code = fn(os.fsencode(temp), os.fsencode(out), 4)
    elif sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        fn = libc.renameat2
        fn.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
        code = fn(-100, os.fsencode(temp), -100, os.fsencode(out), 1)
    else:
        raise DependencyError("atomic exclusive bundles require macOS or Linux renameat2")
    if code:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(out))


def load_approved(path, sha):
    helper = Path(__file__).resolve().with_name("music_plan.py")
    spec = importlib.util.spec_from_file_location("_music_media_plan", helper)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.load_approved(path, sha, "create")


def parser():
    p = Parser(description=__doc__, allow_abbrev=False)
    subs = p.add_subparsers(dest="operation", required=True)
    for operation in ("create", "track", "edit", "analyze"):
        child = subs.add_parser(operation, allow_abbrev=False)
        if operation == "create":
            child.add_argument("--approved-plan", required=True)
            child.add_argument("--approval-sha256", required=True)
        else:
            child.add_argument("source")
        if operation != "analyze":
            child.add_argument("--out", required=True)
            child.add_argument("--slug", default="music")
        if operation == "track":
            child.add_argument("--take-file")
            child.add_argument("--prompt-file")
        if operation in ("edit", "analyze"):
            child.add_argument("--start", type=number(0, 600), default=0.)
            child.add_argument("--end", type=number(0, 600))
        if operation == "analyze":
            child.add_argument("--focus", default="overview")
        if operation == "edit":
            child.add_argument("--loop-seconds", type=number(1 / RATE, 600))
            for name in ("crossfade-ms", "fade-in-ms", "fade-out-ms"):
                child.add_argument(f"--{name}", type=number(0, 600000, True), default=0)
            child.add_argument("--gain-db", type=number(-60, 24), default=0.)
            child.add_argument("--target-lufs", type=number(-70, -5))
    return p


def execute(args):
    if np is None:
        raise DependencyError("numpy is required; use the Hermes venv Python")
    out = None
    if args.operation != "analyze":
        slug(args.slug)
        out = Path(args.out).expanduser().absolute()
        if out.exists() or out.is_symlink() or not out.parent.is_dir():
            raise ValueError("out must be a NEW directory, not a symlink, with an existing parent")
        out = out.parent.resolve() / out.name
    elif len(args.focus) > 8000:
        raise ValueError("focus must be <=8000 characters")
    approval, score_raw, score, render, evidence, prompt, evidence_raw = None, None, None, None, {}, None, None
    prompt_check = {"status": "not_provided", "fields": []}
    if args.operation == "create":
        if not re.fullmatch(r"[0-9a-f]{64}", args.approval_sha256):
            raise ValueError("approval-sha256 must be a lowercase SHA-256")
        approval = load_approved(args.approved_plan, args.approval_sha256)
        if approval.get("approval_sha256") != args.approval_sha256:
            raise ValueError("approval helper returned a mismatched approval hash")
        if not isinstance(approval.get("artifact_text"), str):
            raise ValueError("approved manifest must contain exact score JSON artifact_text")
        score_raw = approval["artifact_text"].encode("utf-8")
        if len(score_raw) > TEXT_BYTES:
            raise ValueError("score exceeds 2 MiB")
        score = validate_score(strict_json(score_raw))
        if strict_json(json.dumps(approval, allow_nan=False)) != load_approved(args.approved_plan, args.approval_sha256):
            raise ValueError("approved plan changed during validation")
    if args.operation == "track":
        if args.take_file:
            _, evidence_raw = local_bytes(args.take_file, TEXT_BYTES)
            evidence = strict_json(evidence_raw)
            if not isinstance(evidence, dict):
                raise ValueError("take-file must contain a JSON object")
        if args.prompt_file:
            _, prompt = local_bytes(args.prompt_file, TEXT_BYTES)
            text = prompt.decode("utf-8")
            request = evidence.get("request", {})
            fields = [field for field in ("text", "prompt") if isinstance(request, dict) and field in request]
            for field in fields:
                if not isinstance(request[field], str) or request[field] != text:
                    raise ValueError(f"prompt-file must match receipt request.{field} exactly, including whitespace")
            prompt_check = {"status": "PASS" if fields else "unavailable", "fields": [f"request.{field}" for field in fields],
                            "method": "exact UTF-8 text equality; no whitespace or newline normalization",
                            "limits": "unavailable means no receipt prompt was supplied; attached text is not verified generation provenance"}
    versions = {"python": platform.python_version(), "platform": platform.platform(), "numpy": np.__version__,
                "ffmpeg": run(["ffmpeg", "-version"]).stdout.decode().splitlines()[0],
                "ffprobe": run(["ffprobe", "-version"]).stdout.decode().splitlines()[0]}
    renderer_hash = digest(Path(__file__).read_bytes())
    environment_hash = digest(json.dumps(versions, sort_keys=True).encode())
    with tempfile.TemporaryDirectory(prefix=".music-work-", dir=out.parent if out else None) as directory:
        work = Path(directory)
        source, raw = None, None
        if args.operation == "create":
            samples, render = render_score(score)
        else:
            source_path, raw = local_bytes(args.source)
            frozen = work / "input"
            frozen.write_bytes(raw)
            samples, native = decode(frozen, raw)
            source = {"path": str(source_path), "sha256": digest(raw), "bytes": len(raw),
                      "native": native, "measure": measure(samples)}
            if native["clipping_detected"]:
                source["measure"]["failures"].append("native source clipping/full-scale detected before resampling")
                source["measure"]["status"] = "FAIL"
        if args.operation == "analyze":
            selected, segment = trim(samples, args.start, args.end)
            measured = measure(selected) if segment["start_frame"] or len(selected) != len(samples) else source["measure"]
            return {"schema_version": 1, "operation": "analyze", "status": source["measure"]["status"],
                    "source": source, "measure": measured,
                    "analysis": musical_analysis(selected, segment["start_seconds"], args.focus),
                    "versions": versions, "renderer_sha256": renderer_hash,
                    "environment_sha256": environment_hash, "auditory_quality": "unverified"}
        edits, failures = None, []
        if source and source["measure"]["status"] == "FAIL":
            failures.append("source failed clipping/peak checks; processing cannot erase source failure")
        duration_check = None
        if args.operation == "track":
            requested_values = []
            for scope, field_names in ((evidence, ("requested_seconds", "duration_seconds", "seconds")),
                                       (evidence.get("settings", {}), ("duration_seconds", "seconds")),
                                       (evidence.get("request", {}), ("duration_seconds", "duration"))):
                if isinstance(scope, dict):
                    for field in field_names:
                        if field in scope:
                            requested_values.append(numeric(scope[field], 1, 60, "take requested seconds"))
            if requested_values:
                requested = requested_values[0]
                if any(value != requested for value in requested_values):
                    raise ValueError("take evidence contains conflicting requested durations")
                tolerance = .25
                actual = len(samples) / RATE
                valid = 1 - tolerance <= actual <= 60 + tolerance and abs(actual - requested) <= tolerance
                duration_check = {"requested_seconds": requested, "actual_seconds": actual,
                                  "tolerance_seconds": tolerance, "status": "PASS" if valid else "FAIL"}
                if not valid:
                    failures.append("generated take duration misses requested seconds by >0.25 seconds or 1..60s range with tolerance")
            claimed_hashes = [evidence[key] for key in ("source_sha256", "raw_sha256") if key in evidence]
            if isinstance(evidence.get("raw_wav"), dict) and "sha256_file" in evidence["raw_wav"]:
                claimed_hashes.append(evidence["raw_wav"]["sha256_file"])
            if any(value != source["sha256"] for value in claimed_hashes):
                failures.append("take source/raw SHA-256 does not match frozen source")
        if args.operation == "edit":
            samples, edits = edit(samples, args)
        pre = measure(samples)
        if pre["status"] == "FAIL":
            failures.append("pre-quantization candidate failed clipping/peak checks")
        if args.operation == "edit" and args.target_lufs is not None:
            edits["normalization_input_measure"] = pre
            if pre["out_of_range_count"]:
                edits["normalization"] = "refused: out-of-range pre-normalization candidate"
            else:
                samples, edits["normalization"] = normalize(samples, args.target_lufs, pre)
                if isinstance(edits["normalization"], str):
                    failures.append(edits["normalization"])
                else:
                    pre = measure(samples)
        if edits is not None:
            edits["pre_quantization_seams"] = repeat_seams(samples, edits["source_segment"], edits["crossfade_frames"], "pre_quantization_after_optional_normalization")
            edits["seams"] = edits["pre_quantization_seams"]
        bundle = work / "bundle"
        bundle.mkdir()
        if raw is not None:
            (bundle / "source.original").write_bytes(raw)
        if score_raw is not None:
            (bundle / "score.json").write_bytes(score_raw)
            (bundle / "approval.json").write_text(json.dumps(approval, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        if prompt is not None:
            (bundle / "prompt.txt").write_bytes(prompt)
        if evidence_raw is not None:
            (bundle / "source.take.json").write_bytes(evidence_raw)
        master = bundle / f"music_{args.slug}.wav"
        if np.any(samples > 1) or np.any(samples < -1) or not np.isfinite(samples).all():
            # Preserve exact failed float candidate and diagnostics, NOT a clipped
            # PCM16 master that could be mistaken for a valid delivery.
            (bundle / "candidate.f32le").write_bytes(samples.astype("<f4").tobytes())
            measured = measure(samples)
            failures.append("PCM16 delivery refused: out-of-range candidate retained as diagnostic f32le")
            master = None
        else:
            final = write_wav(master, samples)
            measured = measure(final, "pcm_s16le")
            if edits is not None:
                edits["seams"] = repeat_seams(final, edits["source_segment"], edits["crossfade_frames"], "delivered_pcm16")
        if args.operation == "edit" and args.target_lufs is not None:
            lufs, peak = measured["integrated_lufs"], measured["true_peak_dbtp"]
            if lufs is None or abs(lufs - args.target_lufs) > .5 + 1e-9 or peak is None or peak > -.9 + 1e-9:
                failures.append("quantized final misses requested LUFS tolerance 0.5 or true peak ceiling -0.9 dBTP")
        if measured["status"] == "FAIL":
            failures.append("final candidate failed measured clipping/peak checks")
        warnings = measured["warnings"]
        status = "FAIL" if failures else "WARN" if warnings else "PASS"
        controls = {k: v for k, v in vars(args).items() if k not in ("out", "source", "operation", "take_file", "prompt_file")}
        take = {"schema_version": 1, "operation": args.operation, "status": status, "failures": failures,
                "warnings": warnings, "controls": controls, "source": source, "evidence": evidence,
                "evidence_provided": evidence_raw is not None, "duration_check": duration_check,
                "prompt_sha256": digest(prompt) if prompt is not None else None,
                "prompt_check": prompt_check,
                "evidence_sha256": digest(evidence_raw) if evidence_raw is not None else None,
                "approval_sha256": args.approval_sha256 if approval else None,
                "score_sha256": digest(score_raw) if score_raw is not None else None,
                "renderer_sha256": renderer_hash, "environment_sha256": environment_hash, "versions": versions,
                "render": render, "edit": edits, "pre_quantization_measure": pre, "measure": measured,
                "pcm_sha256": measured["pcm_sha256"], "diagnostic_candidate": status == "FAIL",
                "auditory_quality": "unverified"}
        if score is not None:
            take["score"] = score
            take["seed"] = score.get("seed", 0)
            take["determinism"] = "same score bytes and renderer/environment produce repeat PCM; no cross-environment bit identity claim"
        sidecar = bundle / f"music_{args.slug}.take.json"
        sidecar.write_text(json.dumps(take, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        files = sorted(path.name for path in bundle.iterdir())
        publish(bundle, out)
        return {**take, "out": str(out), "master": str(out / master.name) if master else None,
                "files": [str(out / name) for name in files]}


def main(argv=None):
    try:
        result = execute(parser().parse_args(argv))
        code = 1 if result["status"] == "FAIL" else 0
    except (DependencyError, OSError, ValueError, TypeError, OverflowError, RecursionError, subprocess.SubprocessError) as exc:
        message = str(exc)
        if isinstance(exc, subprocess.CalledProcessError):
            message += ": " + exc.stderr.decode("utf-8", errors="replace")[-3000:]
        result = {"status": "FAIL", "error": message,
                  "error_type": "dependency" if isinstance(exc, DependencyError) else "input_or_processing",
                  "auditory_quality": "unverified"}
        code = 2
    print("RESULT: " + json.dumps(result, allow_nan=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
