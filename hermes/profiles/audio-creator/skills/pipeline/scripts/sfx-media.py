#!/usr/bin/env python3
"""Local SFX synthesis, packaging, editing and measurement; no ASR or listening QA.

Bundles contain a 48 kHz 16-bit WAV master, take evidence and optional MP3/Ogg Opus.
PCM hashes describe interleaved little-endian float32 decoded samples at the
reported rate/channels. Pad adds silence to BOTH ends; fades apply after padding.
Pitch uses asetrate + aresample, changing duration, not preserving tempo.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
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
MAX_SECONDS = 22
MAX_BYTES = 16 * 1024 * 1024
KINDS = ("click", "beep", "chime", "whoosh", "riser", "pop", "ui-tick", "noise-burst")
ORDER = ("trim", "pitch", "reverse", "pad", "fade", "peak-normalize", "convert")


class DependencyError(RuntimeError):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def number(low, high, integer=False):
    def parse(value):
        try:
            if isinstance(value, bool):
                raise ValueError
            result = int(value) if integer else float(value)
            if not math.isfinite(result) or not low <= result <= high:
                raise ValueError
            return result
        except (ValueError, TypeError, OverflowError):
            raise argparse.ArgumentTypeError(f"expected {'integer' if integer else 'finite number'} in [{low}, {high}]") from None
    return parse


def parser():
    p = Parser(description=__doc__, allow_abbrev=False)
    subs = p.add_subparsers(dest="operation", required=True)
    for op in ("synth", "track", "edit", "analyze"):
        s = subs.add_parser(op, allow_abbrev=False)
        if op != "synth":
            s.add_argument("source")
        if op != "analyze":
            s.add_argument("--out", required=True)
            s.add_argument("--slug", default="sfx")
        if op == "synth":
            s.add_argument("--kind", choices=KINDS, required=True)
            s.add_argument("--seconds", type=number(.01, 22), required=True)
            s.add_argument("--pitch", type=number(40, 8000), default=880.)
            s.add_argument("--seed", type=number(0, 2**32 - 1, True), default=0)
        if op == "track":
            s.add_argument("--take-file")
            s.add_argument("--prompt-file")
        if op == "edit":
            s.add_argument("--start", type=number(0, 22), default=0.)
            s.add_argument("--end", type=number(0, 22))
            s.add_argument("--pad-ms", type=number(0, 10000, True), default=0)
            s.add_argument("--fade-in-ms", type=number(0, 22000, True), default=0)
            s.add_argument("--fade-out-ms", type=number(0, 22000, True), default=0)
            s.add_argument("--pitch-semitones", type=number(-24, 24), default=0.)
            s.add_argument("--reverse", action="store_true")
            s.add_argument("--target-peak", type=number(-30, -1))
            s.add_argument("--format", choices=("wav", "mp3", "ogg"), default="wav")
    return p


def run(args, data=None):
    try:
        return subprocess.run([str(a) for a in args], input=data, capture_output=True,
                              check=True, timeout=120)
    except FileNotFoundError as exc:
        raise DependencyError(f"required tool missing: {args[0]}") from exc


def local_bytes(name):
    path = Path(name).expanduser().absolute()
    # Open once, reject devices/FIFOs/symlinks and bound the actual read as well
    # as stat. All downstream work uses this frozen copy, never the live source.
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            raise ValueError("source must be a regular local file <=16 MiB")
        data = f.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("source must be <=16 MiB")
    return path, data


def digest(data):
    return hashlib.sha256(data).hexdigest()


def reject_constant(value):
    raise ValueError(f"nonfinite JSON: {value}")


def decode(path):
    info = json.loads(run([
        "ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
        "-show_streams", "-of", "json", path,
    ]).stdout)
    audio = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    if len(audio) != 1:
        raise ValueError("source must contain exactly one audio stream")
    stream = audio[0]
    channels, rate = int(stream.get("channels", 0)), int(stream.get("sample_rate", 0))
    if channels not in (1, 2) or not 1 <= rate <= 384000:
        raise ValueError("source must be mono or stereo with sample rate 1..384000 Hz")
    pcm = run([
        "ffmpeg", "-nostdin", "-v", "error", "-xerror", "-protocol_whitelist", "file,pipe",
        "-i", path, "-map", f"0:{stream['index']}", "-t", "22.01",
        "-acodec", "pcm_f32le", "-f", "f32le", "pipe:1",
    ]).stdout
    samples = np.frombuffer(pcm, dtype="<f4").reshape(-1, channels).copy()
    if not len(samples) or len(samples) > MAX_SECONDS * rate:
        raise ValueError("decoded duration must be positive and <=22 seconds (no truncation)")
    if not np.isfinite(samples).all():
        raise ValueError("decoded PCM contains nonfinite samples")
    return samples, rate, stream["codec_name"]


def filter_pcm(samples, rate, filters):
    """Filter to 48 kHz f32le; the decode margin detects overflow, never crops it."""
    result = run([
        "ffmpeg", "-nostdin", "-v", "error", "-xerror", "-f", "f32le",
        "-ar", rate, "-ac", samples.shape[1], "-i", "pipe:0", "-af", filters,
        "-t", "22.01", "-ar", RATE, "-f", "f32le", "pipe:1",
    ], samples.astype("<f4").tobytes())
    output = np.frombuffer(result.stdout, dtype="<f4").reshape(-1, samples.shape[1]).copy()
    if not len(output) or len(output) > MAX_SECONDS * RATE or not np.isfinite(output).all():
        raise ValueError("actual edited duration must be positive and <=22 seconds")
    return output


def measure(samples, rate, codec):
    frames, channels = samples.shape
    duration = frames / rate
    amplitudes = np.max(np.abs(samples), axis=1)  # Never sum anti-phase channels.
    peak = float(amplitudes.max())
    active = np.flatnonzero(amplitudes > 10 ** (-60 / 20))
    onset = np.flatnonzero(amplitudes >= peak * .1) if peak else []
    integer_pcm = re.match(r"pcm_[su](8|16|24|32|64)", codec)
    limit = 1 - 2 ** (1 - int(integer_pcm[1])) if integer_pcm else 1.
    clipped = (samples >= limit) | (samples <= -1.)
    # Padding is only for a true-peak measurement on sub-400ms transients.
    # Do not present the padded signal's integrated loudness as the original's.
    padding = max(0., .4 - duration)
    log = run([
        "ffmpeg", "-nostdin", "-v", "info", "-xerror", "-f", "f32le", "-ar", rate,
        "-ac", channels, "-i", "pipe:0", "-af",
        f"apad=pad_dur={padding},loudnorm=print_format=json", "-f", "null", "-",
    ], samples.astype("<f4").tobytes()).stderr.decode("utf-8", errors="replace")
    matches = re.findall(r"\{[^{}]*\}", log)
    if not matches:
        raise DependencyError("ffmpeg loudnorm did not return measurement evidence")
    evidence = json.loads(matches[-1])

    def finite(key):
        value = float(evidence[key])
        return value if math.isfinite(value) else None

    lufs = finite("input_i") if duration >= .4 and peak else None
    true_peak = finite("input_tp") if peak else None
    failures = []
    warnings = []
    if not active.size:
        failures.append("silence: all samples at or below -60 dBFS")
    if clipped.any():
        failures.append("clipping: full-scale or out-of-range samples")
    if true_peak is not None and true_peak >= 0:
        failures.append("clipping: true peak reaches or exceeds 0 dBTP")
    if lufs is None:
        warnings.append("integrated LUFS unavailable for silence/short/ungated transient")
    if peak and true_peak is None:
        warnings.append("true peak unavailable")
    return {
        "status": "FAIL" if failures else "WARN" if warnings else "PASS",
        "failures": failures, "warnings": warnings,
        "frames": frames, "duration_seconds": duration, "channels": channels,
        "codec": codec, "sample_rate": rate,
        "pcm_sha256": digest(samples.astype("<f4").tobytes()),
        "pcm_hash_format": "interleaved f32le at reported sample_rate/channels",
        "clipping_count": int(clipped.sum()),
        "clipping_count_per_channel": clipped.sum(axis=0).tolist(),
        "sample_peak_dbfs": 20 * math.log10(peak) if peak else None,
        "true_peak_dbtp": true_peak, "integrated_lufs": lufs,
        "loudnorm_evidence": evidence, "true_peak_measurement_padding_seconds": padding,
        "silence_estimate": {"threshold_dbfs": -60,
                             "head_seconds": int(active[0]) / rate if active.size else duration,
                             "tail_seconds": (frames - 1 - int(active[-1])) / rate if active.size else duration},
        "dc_offset_per_channel": samples.mean(axis=0, dtype=np.float64).tolist(),
        "attack_estimate": {"threshold_relative_db": -20,
                            "threshold_to_peak_seconds": (int(amplitudes.argmax()) - int(onset[0])) / rate if peak else None},
        "boundary_sample_deltas": {
            "last_to_first_per_channel": (samples[0].astype(float) - samples[-1]).tolist(),
            "first_step_per_channel": (samples[min(1, frames - 1)].astype(float) - samples[0]).tolist(),
            "last_step_per_channel": (samples[-1].astype(float) - samples[max(0, frames - 2)]).tolist(),
            "verification": "NOT seamless-loop verification",
        },
        "auditory_quality": "unverified",
    }


def synth(args):
    count = round(args.seconds * RATE)
    t = np.arange(count, dtype=np.float64) / RATE
    u = np.linspace(0., 1., count)
    noise = np.random.Generator(np.random.PCG64(args.seed)).standard_normal(count)
    phase = 2 * np.pi * args.pitch * t
    edge = np.sin(np.pi / 2 * np.minimum(u / .04, 1)) ** 2
    edge *= np.sin(np.pi / 2 * np.minimum((1 - u) / .08, 1)) ** 2
    if args.kind == "beep":
        signal = np.sin(phase)
    elif args.kind in ("click", "ui-tick"):
        signal = (np.sin(phase) + noise * (.7 if args.kind == "click" else .12)) * np.exp(-u * 28)
    elif args.kind == "pop":
        signal = np.sin(2 * np.pi * args.pitch * (t - .4 * t * u)) * np.exp(-u * 9)
    elif args.kind == "chime":
        signal = sum(np.sin(phase * harmonic) * np.exp(-u * (3 + harmonic)) / harmonic
                     for harmonic in (1, 2, 3))
    elif args.kind == "whoosh":
        signal = np.empty(count)
        state = 0.
        alpha = 1 - math.exp(-2 * math.pi * args.pitch / RATE)
        for i, sample in enumerate(noise):
            state += alpha * (sample - state)
            signal[i] = state
        signal *= np.sin(np.pi * u) ** 2
    elif args.kind == "riser":
        signal = (np.sin(2 * np.pi * args.pitch * (.5 * t + .75 * t * u)) + .25 * noise) * u**1.5
    else:
        signal = noise * np.sin(np.pi * u) ** 2
    signal *= edge
    signal *= 10 ** (-6 / 20) / np.max(np.abs(signal))
    return signal.reshape(-1, 1)


def write_wav(path, samples, rate):
    pcm = np.clip(np.rint(samples * 32768), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as f:
        f.setnchannels(samples.shape[1])
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(pcm.tobytes())


def publish(temp, out):
    """Atomic no-replace directory rename, including an existing empty directory."""
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        fn = libc.renamex_np
        fn.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint)
        code = fn(os.fsencode(temp), os.fsencode(out), 4)  # RENAME_EXCL
    elif sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        fn = libc.renameat2
        fn.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
        code = fn(-100, os.fsencode(temp), -100, os.fsencode(out), 1)  # RENAME_NOREPLACE
    else:
        raise DependencyError("atomic no-replace directory publication requires macOS or Linux renameat2")
    if code:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(out))


def execute(args):
    if np is None:
        raise DependencyError("numpy is required; use the Hermes venv Python")
    out = None
    if args.operation != "analyze":
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.slug) or len(args.slug) > 80:
            raise ValueError("slug must be 1..80 lowercase letters/digits separated by hyphens")
        out = Path(args.out).expanduser().absolute()
        if out.exists() or out.is_symlink() or not out.parent.is_dir():
            raise ValueError("out must be a new directory, not a symlink, with an existing parent")
        out = out.parent.resolve() / out.name
    if args.operation == "edit" and not any((args.start, args.end is not None, args.pad_ms,
            args.fade_in_ms, args.fade_out_ms, args.pitch_semitones, args.reverse,
            args.target_peak is not None, args.format != "wav")):
        raise ValueError("edit requires at least one nondefault operation")
    versions = {"numpy": np.__version__, "ffmpeg": run(["ffmpeg", "-version"]).stdout.decode().splitlines()[0],
                "ffprobe": run(["ffprobe", "-version"]).stdout.decode().splitlines()[0]}
    evidence, prompt, source = {}, None, None
    if args.operation == "track":
        if args.take_file:
            _, raw = local_bytes(args.take_file)
            evidence = json.loads(raw.decode("utf-8"), parse_constant=reject_constant)
            if not isinstance(evidence, dict):
                raise ValueError("take-file must be a JSON object")
            json.dumps(evidence, allow_nan=False)
        if args.prompt_file:
            _, prompt = local_bytes(args.prompt_file)
            prompt.decode("utf-8")
    with tempfile.TemporaryDirectory(prefix=".sfx-work-", dir=out.parent if out else None) as work:
        work = Path(work)
        if args.operation == "synth":
            samples, rate = synth(args), RATE
        else:
            source_path, raw = local_bytes(args.source)
            frozen = work / "input"
            frozen.write_bytes(raw)
            samples, rate, codec = decode(frozen)
            source = {"path": str(source_path), "sha256": digest(raw), "bytes": len(raw),
                      "measure": measure(samples, rate, codec)}
            if args.operation == "analyze":
                return {"operation": "analyze", "status": source["measure"]["status"],
                         "source": source, "measure": source["measure"], "versions": versions,
                         "auditory_quality": "unverified"}
            # Keep native source evidence above; all delivery/edit samples are 48 kHz.
            if rate != RATE:
                samples = filter_pcm(samples, rate, f"aresample={RATE}")
                rate = RATE
        edits = None
        if args.operation == "edit":
            end = len(samples) / rate if args.end is None else args.end
            if not args.start < end <= len(samples) / rate:
                raise ValueError("trim must satisfy 0 <= start < end <= decoded duration")
            samples = samples[round(args.start * rate):round(end * rate)]
            if not len(samples):
                raise ValueError("trim contains no samples")
            pitch_rate = round(rate * 2 ** (args.pitch_semitones / 12))
            if pitch_rate < 1:
                raise ValueError("pitch would produce a sample rate below 1 Hz")
            predicted = len(samples) / pitch_rate + 2 * args.pad_ms / 1000
            if predicted > MAX_SECONDS:
                raise ValueError("edited duration exceeds 22 seconds; nothing was truncated")
            if max(args.fade_in_ms, args.fade_out_ms) / 1000 > predicted:
                raise ValueError("fade cannot exceed edited duration")
            if args.pitch_semitones:
                samples = filter_pcm(samples, rate, f"asetrate={pitch_rate},aresample={rate}")
            if args.reverse:
                samples = samples[::-1].copy()
            pad = round(args.pad_ms * rate / 1000)
            samples = np.pad(samples, ((pad, pad), (0, 0)))
            if len(samples) > MAX_SECONDS * rate:
                raise ValueError("actual edited duration exceeds 22 seconds")
            for ms, reverse in ((args.fade_in_ms, False), (args.fade_out_ms, True)):
                n = round(ms * rate / 1000)
                if n:
                    view = samples[::-1] if reverse else samples
                    view[:n] *= np.linspace(0., 1., n)[:, None]
            edits = {"order": ORDER, "pitch_method": "asetrate+aresample; duration changes; no tempo preservation",
                     "pitch_rate": pitch_rate, "pitch_duration_ratio": rate / pitch_rate,
                     "pad": "silence on both ends", "normalization": "true-peak gain, not LUFS"}
        bundle = work / "bundle"
        bundle.mkdir()
        master = bundle / f"sfx_{args.slug}.wav"
        gain = 0.
        if args.operation == "edit" and args.target_peak is not None:
            before = measure(samples, rate, "pcm_f32le")
            if before["true_peak_dbtp"] is not None:
                gain = args.target_peak - before["true_peak_dbtp"]
                samples = samples.astype(np.float64) * 10 ** (gain / 20)
            edits["normalization_input_measure"] = before
            edits["gain_db"] = gain
        write_wav(master, samples, rate)
        final, final_rate, codec = decode(master)
        measured = measure(final, final_rate, codec)
        if args.operation == "edit" and args.target_peak is not None:
            actual = measured["true_peak_dbtp"]
            if actual is None or abs(actual - args.target_peak) > .1 + 1e-9:
                measured["failures"].append("quantized final true peak misses requested target by >0.1 dB or is unavailable")
                measured["status"] = "FAIL"
        derivatives = {}
        if args.operation == "edit" and args.format != "wav":
            derivative = bundle / f"sfx_{args.slug}.{args.format}"
            encoding = ["-c:a", "libmp3lame", "-q:a", "2"] if args.format == "mp3" else ["-c:a", "libopus", "-b:a", "192k", "-ar", "48000"]
            run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-n",
                 "-protocol_whitelist", "file,pipe", "-i", master, *encoding, derivative])
            decoded, derivative_rate, derivative_codec = decode(derivative)
            dm = measure(decoded, derivative_rate, derivative_codec)
            if args.target_peak is not None:
                actual = dm["true_peak_dbtp"]
                if actual is None or abs(actual - args.target_peak) > .1 + 1e-9:
                    dm["status"] = "FAIL"
                    dm["failures"].append("derivative true peak misses requested target by >0.1 dB or is unavailable")
            derivatives[derivative.name] = dm
        statuses = [measured["status"], *(m["status"] for m in derivatives.values())]
        if args.operation == "track":
            statuses.append(source["measure"]["status"])
        status = "FAIL" if "FAIL" in statuses else "WARN" if "WARN" in statuses else "PASS"
        controls = {k: v for k, v in vars(args).items() if k not in ("out", "source", "take_file", "prompt_file", "operation")}
        take = {"recipe_version": 1, "operation": args.operation, "controls": controls,
                "seed": args.seed if args.operation == "synth" else evidence.get("seed"),
                "rng": "numpy.PCG64" if args.operation == "synth" else None,
                "versions": versions, "source": source, "evidence": evidence,
                "evidence_provided": bool(args.operation == "track" and args.take_file),
                "edit": edits, "pcm_sha256": measured["pcm_sha256"], "measure": measured,
                "derivatives": derivatives, "status": status, "auditory_quality": "unverified",
                "diagnostic_candidate": status == "FAIL"}
        if args.operation == "synth":
            take["determinism"] = "synth master decoded PCM repeats with the same recipe and environment; no claim for generated sources or derivatives"
        if prompt is not None:
            (bundle / "prompt.txt").write_bytes(prompt)
            take["prompt_sha256"] = digest(prompt)
        (bundle / f"sfx_{args.slug}.take.json").write_text(json.dumps(take, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        files = sorted(p.name for p in bundle.iterdir())
        publish(bundle, out)
        return {**take, "out": str(out), "master": str(out / master.name),
                "files": [str(out / name) for name in files]}


def main(argv=None):
    try:
        result = execute(parser().parse_args(argv))
        code = 1 if result["status"] == "FAIL" else 0
    except (DependencyError, OSError, ValueError, RecursionError, subprocess.SubprocessError) as exc:
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
