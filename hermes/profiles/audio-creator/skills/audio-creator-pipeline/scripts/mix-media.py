#!/usr/bin/env python3
"""Approved, offline multi-source mixdown. No synthesis, ASR or listening claims.

The proposal binds frozen source bytes, timing and DSP controls, not the identity
of an approver. Creator must relay approval in the same work conversation.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import wave


_path = Path(__file__).with_name("music-media.py")
_loader = importlib.util.spec_from_file_location("_mix_audio_io", _path)
media = importlib.util.module_from_spec(_loader)
_loader.loader.exec_module(media)
np = media.np
RATE = 48000
MAX_TOTAL = 512 * 1024 * 1024
START, END = "<!-- MIX_MANIFEST\n", "\nMIX_MANIFEST -->"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path, limit=media.TEXT_BYTES):
    return media.local_bytes(path, limit)[1]


def load(path):
    return media.strict_json(read(path))


def dump(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def relative(value):
    require(isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9_./-]+", value)
            and not Path(value).is_absolute() and ".." not in Path(value).parts, "unsafe bundle-relative path")
    return value


def bundle_file(root, name):
    path = root / relative(name)
    require(not any(p.is_symlink() for p in (path, *path.parents)), "bundle symlinks forbidden")
    return path


def fresh(path):
    path = Path(path).expanduser().absolute()
    require(not path.exists() and not path.is_symlink() and path.parent.is_dir(),
            "out must be a NEW directory with an existing parent")
    return path.parent.resolve() / path.name


def number(value, low, high, label):
    return media.numeric(value, low, high, label)


def frame(value):
    return round(value * RATE)


def validate_spec(spec):
    media.keys(spec, {"version", "what_for", "direction", "duration_seconds", "channels",
                      "target_lufs", "true_peak_dbtp", "sources", "cues"},
               {"must_keep", "timing"}, "mix")
    require(type(spec["version"]) is int and spec["version"] == 1, "mix version must be 1")
    for field in ("what_for", "direction", "must_keep"):
        if field in spec:
            require(isinstance(spec[field], str) and 0 < len(spec[field].strip()) <= 8000, field + " must be nonblank text <=8000 characters")
    total = number(spec["duration_seconds"], 1, 600, "duration_seconds")
    require(type(spec["channels"]) is int and spec["channels"] in (1, 2), "channels must be 1 or 2")
    if spec["target_lufs"] is not None:
        number(spec["target_lufs"], -70, -5, "target_lufs")
    number(spec["true_peak_dbtp"], -9, -.1, "true_peak_dbtp")
    require(isinstance(spec["sources"], list) and 1 <= len(spec["sources"]) <= 16, "1..16 sources required")
    sources = {}
    for source in spec["sources"]:
        media.keys(source, {"id", "path", "role"}, {"words"}, "source")
        ident = media.slug(source["id"])
        require(ident not in sources, "duplicate source id")
        require(source["role"] in ("speech", "music", "sfx", "other"), "invalid source role")
        require("words" not in source or source["role"] == "speech", "words sidecar requires speech role")
        for field in ("path", "words"):
            if field in source:
                require(isinstance(source[field], str) and 0 < len(source[field]) <= 4096, "source path must be text")
        sources[ident] = source
    require(isinstance(spec["cues"], list) and 1 <= len(spec["cues"]) <= 32, "1..32 cues required")
    ids, used, work = set(), set(), 0
    for cue in spec["cues"]:
        media.keys(cue, {"id", "source", "start", "source_start", "duration", "gain_db", "fade_in", "fade_out", "envelope"}, set(), "cue")
        ident = media.slug(cue["id"])
        require(ident not in ids, "duplicate cue id")
        ids.add(ident)
        require(cue["source"] in sources, "unknown cue source")
        used.add(cue["source"])
        start = number(cue["start"], 0, total, "cue start")
        source_start = number(cue["source_start"], 0, 600, "source_start")
        duration = number(cue["duration"], 1 / RATE, total, "cue duration")
        require(start + duration <= total + 1e-9 and source_start + duration <= 600 + 1e-9, "cue extends beyond timeline/source bound")
        n = frame(duration)
        require(frame(start) + n <= frame(total), "cue exceeds timeline after sample quantization")
        work += n
        number(cue["gain_db"], -60, 24, "cue gain_db")
        number(cue["fade_in"], 0, duration, "fade_in")
        number(cue["fade_out"], 0, duration, "fade_out")
        envelope = cue["envelope"]
        require(isinstance(envelope, list) and len(envelope) <= 64, "envelope must be a list of <=64 points")
        previous = -1
        for point in envelope:
            media.keys(point, {"at", "gain_db"}, set(), "envelope point")
            position = frame(number(point["at"], 0, duration, "envelope at"))
            number(point["gain_db"], -60, 24, "envelope gain_db")
            require(position > previous, "envelope positions must increase after quantization")
            previous = position
        if envelope:
            require(len(envelope) >= 2 and envelope[0]["at"] == 0 and envelope[-1]["at"] == duration,
                    "envelope must span exactly 0..cue duration")
    require(used == set(sources), "unused sources are refused")
    require(work <= 256_000_000, "mix exceeds 256 million source-frame DSP work bound")
    if "timing" in spec:
        require(isinstance(spec["timing"], str) and spec["timing"], "timing must be a local file path")
    return spec


def validate_timing(timing, spec):
    media.keys(timing, {"version", "duration_seconds", "cues"}, set(), "timing")
    require(type(timing["version"]) is int and timing["version"] == 1, "timing version must be 1")
    number(timing["duration_seconds"], 1, 600, "timing duration")
    require(timing["duration_seconds"] == spec["duration_seconds"], "video timing duration changed")
    require(isinstance(timing["cues"], list) and 1 <= len(timing["cues"]) <= 32, "timing needs 1..32 cues")
    cues = {c["id"]: c for c in spec["cues"]}
    seen = set()
    for constraint in timing["cues"]:
        media.keys(constraint, {"id", "source", "start", "source_start", "duration"}, set(), "timing cue")
        ident = media.slug(constraint["id"])
        require(ident not in seen and ident in cues, "duplicate/unknown timing cue")
        seen.add(ident)
        for key in ("start", "source_start", "duration"):
            number(constraint[key], 0, 600, "timing " + key)
        require(all(cues[ident][k] == v for k, v in constraint.items()), "video cue timing changed; obtain a new proposal")
    return timing


def intervals(doc, duration):
    for key, text_key in (("words", "word"), ("captions", "text"), ("segments", "text")):
        values = doc.get(key)
        require(isinstance(values, list) and len(values) <= 10000, key + " must be a bounded list")
        previous = 0
        for item in values:
            require(isinstance(item, dict), "invalid timed text item")
            start = number(item.get("start"), 0, duration, key + " start")
            end = number(item.get("end"), 0, duration, key + " end")
            require(previous <= start < end, "timed text must be nonoverlapping, ordered and positive")
            require(isinstance(item.get(text_key), str) and 0 < len(item[text_key]) <= 8000, "invalid timed text")
            previous = end


def validate_words(path, source, info, original_name):
    doc = load(path)
    require(isinstance(doc, dict) and doc.get("file") == original_name, "speech sidecar file mismatch")
    duration = info["decoded_duration_seconds"]
    number(doc.get("duration"), 0, 600, "speech sidecar duration")
    require(abs(doc["duration"] - duration) <= .15, "speech sidecar duration mismatch")
    # This is the shipped speech hash convention, NOT music's f32le hash.
    pcm = media.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-protocol_whitelist", "file",
                     "-f", info["container"], "-i", source, "-map", "0:a:0", "-ar", RATE, "-ac", "1",
                     "-t", "600.01", "-f", "s16le", "pipe:1"]).stdout
    require(digest(pcm) == doc.get("pcm_sha256"), "speech sidecar PCM hash mismatch")
    intervals(doc, doc["duration"])
    require(doc["words"] and doc["captions"], "speech sidecar needs words and captions")
    return doc


def map_captions(spec, documents):
    result = {"version": 1, "kind": "mix-captions", "estimated": True, "sources": [], "cues": [],
              "words": [], "captions": [], "segments": [],
              "timing_note": "Inherited clean-speech timing, transformed to mix time; no ASR or listening on this mix."}
    spoken = []
    roles = {s["id"]: s["role"] for s in spec["sources"]}
    for cue in spec["cues"]:
        a, offset, n = frame(cue["start"]), frame(cue["source_start"]), frame(cue["duration"])
        if roles[cue["source"]] == "speech":
            spoken.append((a, a + n))
        doc = documents.get(cue["source"])
        if doc is None:
            continue
        result["cues"].append({"id": cue["id"], "source": cue["source"], "start_frame": a,
                               "source_start_frame": offset, "frames": n})
        for key, text_key in (("words", "word"), ("captions", "text"), ("segments", "text")):
            for item in doc[key]:
                lo, hi = frame(item["start"]), frame(item["end"])
                if hi <= offset or lo >= offset + n:
                    continue
                require(offset <= lo < hi <= offset + n, "cue trim crosses a word/caption/segment; pre-edit speech separately")
                result[key].append({"start": (a + lo - offset) / RATE, "end": (a + hi - offset) / RATE,
                                    text_key: item[text_key], "source": cue["source"], "cue": cue["id"]})
    if documents:
        spoken.sort()
        require(all(a[1] <= b[0] for a, b in zip(spoken, spoken[1:])), "overlapping speech cues need a separate subtitle decision")
        for key in ("words", "captions", "segments"):
            result[key].sort(key=lambda x: x["start"])
        intervals(result, frame(spec["duration_seconds"]) / RATE)
    return result if result["captions"] else None


def fingerprint():
    return {"mix-media.py": digest(read(__file__)), "music-media.py": digest(read(_path))}


def inspect_sources(root, spec, evidence):
    documents = {}
    for source in spec["sources"]:
        path = bundle_file(root, source["path"])
        samples, native = media.decode(path, read(path, media.MAX_BYTES))
        for cue in spec["cues"]:
            if cue["source"] == source["id"]:
                require(frame(cue["source_start"]) + frame(cue["duration"]) <= len(samples), "cue extends beyond decoded source")
        item = evidence[source["id"]]
        if "words" in source:
            documents[source["id"]] = validate_words(bundle_file(root, source["words"]), path, native, item["original_name"])
        del samples
    return documents


def propose(spec_file, description_file, out, previous=None):
    require(np is not None, "numpy required; use Hermes venv")
    spec = validate_spec(load(spec_file))
    description = read(description_file).decode("utf-8")
    require(description.strip() and "MIX_MANIFEST" not in description, "nonblank description without manifest markers required")
    prior = verify_bundle(previous) if previous else None
    out = fresh(out)
    with tempfile.TemporaryDirectory(prefix=".mix-proposal-", dir=out.parent) as directory:
        root = Path(directory) / "bundle"
        (root / "sources").mkdir(parents=True)
        evidence, files, total = {}, {}, 0
        for source in spec["sources"]:
            original = Path(source["path"]).expanduser().absolute()
            raw = read(original, media.MAX_BYTES)
            total += len(raw)
            require(total <= MAX_TOTAL, "sources exceed 512 MiB aggregate bound")
            media.audio_format(raw)
            ident = source["id"]
            source["path"] = f"sources/{ident}.audio"
            (root / source["path"]).write_bytes(raw)
            files[source["path"]] = digest(raw)
            item = {"original_path": str(original), "original_name": original.name, "sha256": digest(raw), "bytes": len(raw)}
            if "words" in source:
                raw_words = read(source["words"])
                source["words"] = f"sources/{ident}.words.json"
                (root / source["words"]).write_bytes(raw_words)
                files[source["words"]] = digest(raw_words)
                # A revision uses a frozen filename, while speech metadata still
                # names the original WAV. Preserve that verified origin.
                if prior:
                    old = prior["take"]["sources"].get(ident)
                    if old and old["sha256"] == item["sha256"]:
                        item["original_name"] = old["original_name"]
                item["words_sha256"] = digest(raw_words)
            evidence[ident] = item
            del raw
        if "timing" in spec:
            timing = read(spec["timing"])
            validate_timing(media.strict_json(timing), spec)
            spec["timing"] = "timing.json"
            (root / "timing.json").write_bytes(timing)
            files["timing.json"] = digest(timing)
        documents = inspect_sources(root, spec, evidence)
        map_captions(spec, documents)
        if prior:
            old, new = dict(prior["spec"]), dict(spec)
            for key in ("what_for", "direction", "must_keep"):
                old.pop(key, None)
                new.pop(key, None)
            require(old != new or any(prior["take"]["files"].get(k) != v for k, v in files.items()),
                    "no audio change requested; identical revision refused")
        (root / "mix.json").write_bytes(dump(spec))
        files["mix.json"] = digest(dump(spec))
        manifest = {"version": 1, "kind": "edit" if prior else "create", "files": files,
                    "sources": evidence, "renderer": fingerprint(),
                    "previous": {"bundle": str(Path(previous).resolve()), "master_sha256": prior["take"]["master"]["sha256"]} if prior else None}
        document = ("# Mix Proposal\n\n" + description.rstrip() + "\n\n## Exact Mix\n\n```json\n" +
                    dump(spec).decode() + "```\n\nApprove these exact bytes through Creator before rendering. "
                    "Hashes bind content, not approver identity. Listening remains unverified. "
                    "Channel conversion: stereo to mono uses an arithmetic mean; mono to stereo duplicates at unity. "
                    "Normalization, when requested, is measured constant gain only; an infeasible peak/ loudness pair fails, never invokes a limiter.\n\n" +
                    START + dump(manifest).decode().rstrip() + END + "\n").encode()
        require(len(document) <= media.TEXT_BYTES, "proposal exceeds document bound")
        (root / "proposal.md").write_bytes(document)
        media.publish(root, out)
    return {"status": "proposal-only", "kind": manifest["kind"], "approved_plan": str(out / "proposal.md"),
            "approval_sha256": digest(document), "audio_created": False, "spend": 0}


def load_approved(path, sha, kind=None, check_renderer=True):
    path = Path(path).expanduser().resolve()
    require(isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha), "exact lowercase approval SHA-256 required")
    raw = read(path)
    require(digest(raw) == sha, "proposal changed since approval")
    text = raw.decode("utf-8")
    require(text.count(START) == text.count(END) == 1, "one Mix manifest required")
    manifest = media.strict_json(text.split(START)[1].split(END)[0])
    media.keys(manifest, {"version", "kind", "files", "sources", "renderer", "previous"}, set(), "manifest")
    require(type(manifest["version"]) is int and manifest["version"] == 1
            and manifest["kind"] in ("create", "edit"), "unsupported Mix proposal")
    require(kind is None or manifest["kind"] == kind, "wrong Mix leaf for proposal")
    if check_renderer:
        require(manifest["renderer"] == fingerprint(), "renderer changed; propose and approve again")
    root = path.parent
    require(isinstance(manifest["files"], dict) and 1 <= len(manifest["files"]) <= 34, "invalid frozen file map")
    total, documents = 0, {}
    for name, expected in manifest["files"].items():
        raw_input = read(bundle_file(root, name), media.MAX_BYTES if name.endswith(".audio") else media.TEXT_BYTES)
        total += len(raw_input)
        require(total <= MAX_TOTAL + 34 * media.TEXT_BYTES, "frozen bundle exceeds bound")
        require(digest(raw_input) == expected, "frozen input changed: " + name)
        if name in ("mix.json", "timing.json"):
            documents[name] = raw_input
    spec = validate_spec(media.strict_json(documents["mix.json"]))
    expected = {"mix.json"}
    require(isinstance(manifest["sources"], dict) and set(manifest["sources"]) == {s["id"] for s in spec["sources"]}, "source evidence mismatch")
    for source in spec["sources"]:
        require(source["path"] == f"sources/{source['id']}.audio", "noncanonical frozen source path")
        expected.add(source["path"])
        evidence = manifest["sources"][source["id"]]
        require(evidence["sha256"] == manifest["files"][source["path"]], "source hash evidence mismatch")
        if "words" in source:
            require(source["words"] == f"sources/{source['id']}.words.json", "noncanonical words path")
            expected.add(source["words"])
            require(evidence.get("words_sha256") == manifest["files"][source["words"]], "words hash evidence mismatch")
    if "timing" in spec:
        require(spec["timing"] == "timing.json", "noncanonical timing path")
        validate_timing(media.strict_json(documents["timing.json"]), spec)
        expected.add("timing.json")
    require(expected == set(manifest["files"]), "unexpected/missing frozen artifacts")
    return spec, manifest, raw


def gain_curve(cue, lo, hi):
    positions = np.arange(lo, hi, dtype=np.float64)
    n = frame(cue["duration"])
    env = cue["envelope"]
    db = np.interp(positions, [frame(p["at"]) for p in env], [p["gain_db"] for p in env]) if env else np.zeros(hi - lo)
    gain = np.power(10., (db + cue["gain_db"]) / 20)
    attack, release = frame(cue["fade_in"]), frame(cue["fade_out"])
    if attack:
        gain *= np.minimum(positions / max(1, attack - 1), 1.)
    if release:
        gain *= np.minimum((n - 1 - positions) / max(1, release - 1), 1.)
    return gain


def normalize(samples, target, peak):
    if target is None:
        return samples, None
    first = media.run(["ffmpeg", "-nostdin", "-v", "info", "-f", "f32le", "-ar", RATE,
                       "-ac", samples.shape[1], "-i", "pipe:0", "-af",
                       f"loudnorm=I={target}:TP={peak}:LRA=11:print_format=json", "-f", "null", "-"],
                      samples.astype("<f4").tobytes()).stderr.decode()
    matches = re.findall(r"\{[^{}]*\}", first)
    require(matches, "normalization measurement missing")
    measured = media.strict_json(matches[-1])
    if not all(math.isfinite(float(measured[k])) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")):
        return samples, {"status": "FAIL", "reason": "normalization requires finite loudness evidence"}
    gain_db = target - float(measured["input_i"])
    evidence = {"status": "measured", "first_pass": measured, "gain_db": gain_db,
                "method": "measured constant gain followed by final measurement; no limiter"}
    # loudnorm's linear=true can silently fall back to a dynamic limiter.
    # Apply the scalar ourselves, preserving the approved envelopes exactly.
    if float(measured["input_tp"]) + gain_db > peak + .01:
        return samples, {**evidence, "status": "FAIL", "reason": "constant gain cannot meet both loudness and true-peak targets; revise the proposal"}
    return samples * 10 ** (gain_db / 20), evidence


def srt(captions):
    def stamp(seconds):
        ms = round(seconds * 1000)
        return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"
    return "\n".join(f"{i}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}\n"
                     for i, c in enumerate(captions, 1))


def render(approved_plan, approval_sha256, kind, out, slug="mix"):
    require(np is not None, "numpy required; use Hermes venv")
    media.slug(slug)
    spec, manifest, proposal = load_approved(approved_plan, approval_sha256, kind)
    origin = Path(approved_plan).expanduser().resolve().parent
    out = fresh(out)
    with tempfile.TemporaryDirectory(prefix=".mix-render-", dir=out.parent) as directory:
        root = Path(directory) / "bundle"
        (root / "sources").mkdir(parents=True)
        for name, expected in manifest["files"].items():
            raw = read(bundle_file(origin, name), media.MAX_BYTES if name.endswith(".audio") else media.TEXT_BYTES)
            require(digest(raw) == expected, "source changed during render staging")
            (root / name).write_bytes(raw)
        (root / "proposal.md").write_bytes(proposal)
        documents = inspect_sources(root, spec, manifest["sources"])
        captions = map_captions(spec, documents)
        output = np.zeros((frame(spec["duration_seconds"]), spec["channels"]), dtype=np.float32)
        failures, warnings, source_measures = [], [], {}
        for source in spec["sources"]:
            path = root / source["path"]
            samples, native = media.decode(path, read(path, media.MAX_BYTES))
            measured = media.measure(samples)
            conversion = "unchanged channels"
            loss_db = None
            if samples.shape[1] == 1 and spec["channels"] == 2:
                conversion = "mono to stereo: duplicate at unity"
            elif samples.shape[1] == 2 and spec["channels"] == 1:
                conversion = "stereo to mono: arithmetic mean"
                original_energy, mono_energy = 0., 0.
                for lo in range(0, len(samples), 65536):
                    block = samples[lo:lo + 65536].astype(np.float64)
                    original_energy += float(np.square(block).sum()) / 2
                    mono_energy += float(np.square(block.mean(axis=1)).sum())
                if original_energy:
                    loss_db = 10 * math.log10(mono_energy / original_energy) if mono_energy else None
                    if mono_energy < original_energy * 10 ** (-6 / 10):
                        warnings.append(source["id"] + ": stereo-to-mono fold loses >6 dB of energy; possible phase cancellation (not a listening verdict)")
            source_measures[source["id"]] = {"native": native, "measure": measured,
                                            "channel_conversion": conversion, "mono_fold_energy_delta_db": loss_db}
            if native["clipping_detected"] or measured["status"] == "FAIL":
                failures.append(source["id"] + ": source clipping/peak failure remains a defect after gain reduction")
            warnings.extend(source["id"] + ": " + w for w in measured["warnings"])
            if source["role"] == "speech" and "words" not in source:
                warnings.append(source["id"] + ": speech timing unavailable; no subtitles invented")
            for cue in spec["cues"]:
                if cue["source"] != source["id"]:
                    continue
                a, offset, n = frame(cue["start"]), frame(cue["source_start"]), frame(cue["duration"])
                for lo in range(0, n, 65536):
                    hi = min(n, lo + 65536)
                    selected = samples[offset + lo:offset + hi].astype(np.float64)
                    if selected.shape[1] == 2 and spec["channels"] == 1:
                        selected = selected.mean(axis=1, keepdims=True)
                    output[a + lo:a + hi] += selected * gain_curve(cue, lo, hi)[:, None]
            del samples
        pre = media.measure(output)
        if pre["out_of_range_count"] and spec["target_lufs"] is not None:
            warnings.append("floating-point sum exceeds full scale before approved constant-gain normalization; no integer clipping has occurred")
        output, normalization = normalize(output, spec["target_lufs"], spec["true_peak_dbtp"])
        if normalization and normalization["status"] == "FAIL":
            failures.append(normalization["reason"])
        master = root / f"mix_{slug}.wav"
        master_info = None
        if not np.isfinite(output).all() or np.any(np.abs(output) > 1):
            failures.append("PCM16 master refused: out-of-range candidate; revise approved gains/target")
            measured = media.measure(output)
        else:
            final = media.write_wav(master, output)
            measured = media.measure(final, "pcm_s16le")
            master_info = {"file": master.name, "sha256": digest(read(master, media.MAX_BYTES)),
                           "frames": len(final), "sample_rate": RATE, "channels": final.shape[1]}
        failures.extend(measured["failures"])
        if measured["silence"]:
            failures.append("silent/very low signal master is not a finished mix")
        peak, lufs = measured["true_peak_dbtp"], measured["integrated_lufs"]
        if peak is not None and peak > spec["true_peak_dbtp"] + .05:
            failures.append("measured true peak exceeds approved ceiling (0.05 dB measurement tolerance)")
        if spec["target_lufs"] is not None and (lufs is None or abs(lufs - spec["target_lufs"]) > .5):
            failures.append("measured LUFS misses approved target (0.5 LU tolerance)")
        warnings.extend(measured["warnings"])
        files = {**manifest["files"], "proposal.md": digest(proposal)}
        if captions and master_info:
            captions["master"] = master_info
            captions["sources"] = [{"id": s["id"], "file": s["path"], "words": s["words"],
                                     "audio_sha256": files[s["path"]], "words_sha256": files[s["words"]]}
                                    for s in spec["sources"] if "words" in s]
            (root / "captions.json").write_bytes(dump(captions))
            (root / f"mix_{slug}.srt").write_text(srt(captions["captions"]), encoding="utf-8")
            for name in ("captions.json", f"mix_{slug}.srt"):
                files[name] = digest(read(root / name))
        take = {"schema_version": 1, "kind": "mix", "operation": kind,
                "status": "FAIL" if failures else "WARN" if warnings else "PASS", "failures": failures,
                "warnings": warnings, "master": master_info, "files": files, "sources": manifest["sources"],
                "approval_sha256": approval_sha256, "previous": manifest["previous"],
                "renderer": fingerprint(), "versions": {"python": platform.python_version(), "numpy": np.__version__,
                  "ffmpeg": media.run(["ffmpeg", "-version"]).stdout.decode().splitlines()[0]},
                "pre_normalization_measure": pre, "normalization": normalization,
                "output_policy": {"target_lufs": spec["target_lufs"], "true_peak_dbtp": spec["true_peak_dbtp"]},
                "measure": measured, "source_measures": source_measures,
                "determinism": "same frozen inputs, controls and renderer/environment; compare decoded PCM, not cross-version identity",
                "auditory_quality": "unverified", "spend": 0}
        (root / "mix.take.json").write_bytes(dump(take))
        media.publish(root, out)
    return {**take, "out": str(out), "master_path": str(out / master.name) if master_info else None}


def validate_delivery(master, receipt_path, captions_path=None):
    """Validate staged playback/caption bytes, without requiring numpy or ASR.

    Full original-source validation is verify_bundle's job before staging.
    A receipt is integrity/provenance evidence, never caller authentication.
    """
    take = load(receipt_path)
    require(isinstance(take, dict) and take.get("schema_version") == 1 and take.get("kind") == "mix", "Mix receipt required")
    require(take.get("status") in ("PASS", "WARN") and not take.get("failures"), "failed Mix cannot be delivered")
    policy = take.get("output_policy")
    media.keys(policy, {"target_lufs", "true_peak_dbtp"}, set(), "Mix output policy")
    number(policy["true_peak_dbtp"], -9, -.1, "Mix true peak ceiling")
    if policy["target_lufs"] is not None:
        number(policy["target_lufs"], -70, -5, "Mix loudness target")
    info = take.get("master")
    media.keys(info, {"file", "sha256", "frames", "sample_rate", "channels"}, set(), "master evidence")
    require(Path(info["file"]).name == info["file"] == Path(master).name, "Mix master filename mismatch")
    raw = read(master, media.MAX_BYTES)
    require(digest(raw) == info["sha256"], "Mix master hash mismatch")
    import io
    with wave.open(io.BytesIO(raw), "rb") as handle:
        require(handle.getcomptype() == "NONE" and handle.getsampwidth() == 2 and handle.getframerate() == RATE,
                "Mix must be 48 kHz PCM16 WAV")
        require(handle.getnchannels() in (1, 2) and handle.getnchannels() == info["channels"]
                and handle.getnframes() == info["frames"] and info["sample_rate"] == RATE
                and 1 <= info["frames"] <= 600 * RATE, "Mix master format/frame evidence mismatch")
        require(len(handle.readframes(info["frames"] + 1)) == info["frames"] * info["channels"] * 2, "truncated Mix WAV")
    files = take.get("files")
    require(isinstance(files, dict), "Mix file evidence required")
    require(("captions.json" in files) == (captions_path is not None), "Mix captions must not be silently dropped or added")
    if captions_path is not None:
        raw_captions = read(captions_path)
        require(digest(raw_captions) == files["captions.json"], "Mix captions hash mismatch")
        doc = media.strict_json(raw_captions)
        require(doc.get("version") == 1 and doc.get("kind") == "mix-captions" and doc.get("estimated") is True
                and doc.get("master") == info, "Mix captions master/timing identity mismatch")
        intervals(doc, info["frames"] / RATE)
    return take


def verify_bundle(bundle):
    root = Path(bundle).expanduser().absolute()
    require(root.is_dir() and not any(p.is_symlink() for p in (root, *root.parents)), "physical Mix bundle directory required")
    take = load(root / "mix.take.json")
    require(isinstance(take, dict) and isinstance(take.get("master"), dict), "no delivered Mix master")
    master = bundle_file(root, take["master"]["file"])
    captions_path = root / "captions.json" if "captions.json" in take.get("files", {}) else None
    validate_delivery(master, root / "mix.take.json", captions_path)
    spec, manifest, _ = load_approved(root / "proposal.md", take["approval_sha256"], take["operation"], check_renderer=False)
    require(take["sources"] == manifest["sources"], "Mix source evidence differs from proposal")
    for name, expected in manifest["files"].items():
        require(take["files"].get(name) == expected, "Mix receipt differs from frozen input hashes")
    for name, expected in take["files"].items():
        require(digest(read(bundle_file(root, name), media.MAX_BYTES if name.endswith(".audio") else media.TEXT_BYTES)) == expected,
                "Mix bundle file changed: " + name)
    require(take["master"]["frames"] == frame(spec["duration_seconds"]) and take["master"]["channels"] == spec["channels"],
            "Mix master differs from approved duration/channels")
    require(take["output_policy"] == {k: spec[k] for k in ("target_lufs", "true_peak_dbtp")},
            "Mix output policy differs from approval")
    return {"spec": spec, "take": take, "master": str(master), "captions": load(captions_path) if captions_path else None}


def analyze(source, bundle=None):
    require(np is not None, "numpy required; use Hermes venv")
    verified = verify_bundle(bundle) if bundle else None
    raw = read(source, media.MAX_BYTES)
    if verified:
        require(digest(raw) == verified["take"]["master"]["sha256"], "analyzed source differs from Mix bundle")
    with tempfile.TemporaryDirectory(prefix="mix-analyze-") as directory:
        frozen = Path(directory) / "source"
        frozen.write_bytes(raw)
        samples, native = media.decode(frozen, raw)
        measured = media.measure(samples)
    if native["clipping_detected"]:
        measured["failures"].append("native clipping/full-scale detected")
        measured["status"] = "FAIL"
    return {"status": measured["status"], "source": str(source), "native": native, "measure": measured,
            "recorded_mix": verified["spec"] if verified else None,
            "limits": "No source separation or inferred voice/music balance; bundle settings are recorded evidence, not listening.",
            "auditory_quality": "unverified", "spend": 0}


def main(argv=None):
    p = media.Parser(description=__doc__, allow_abbrev=False)
    sub = p.add_subparsers(dest="command", required=True)
    proposal = sub.add_parser("propose", allow_abbrev=False)
    for name in ("spec-file", "description-file", "out"):
        proposal.add_argument("--" + name, required=True)
    proposal.add_argument("--previous")
    rendering = sub.add_parser("render", allow_abbrev=False)
    for name in ("approved-plan", "approval-sha256", "out"):
        rendering.add_argument("--" + name, required=True)
    rendering.add_argument("--kind", choices=("create", "edit"), required=True)
    rendering.add_argument("--slug", default="mix")
    analysis = sub.add_parser("analyze", allow_abbrev=False)
    analysis.add_argument("source")
    analysis.add_argument("--bundle")
    verification = sub.add_parser("verify", allow_abbrev=False)
    verification.add_argument("--bundle", required=True)
    try:
        args = vars(p.parse_args(argv))
        command = args.pop("command")
        if command == "verify":
            value = verify_bundle(**args)
            result = {"status": value["take"]["status"], "master": value["master"], "spec": value["spec"]}
        else:
            result = {"propose": propose, "render": render, "analyze": analyze}[command](**args)
        code = 1 if result["status"] == "FAIL" else 0
    except (ValueError, TypeError, KeyError, OSError, OverflowError, RecursionError, wave.Error,
            media.DependencyError, subprocess.SubprocessError) as exc:
        result, code = {"status": "FAIL", "error": str(exc), "auditory_quality": "unverified"}, 2
    print("RESULT: " + json.dumps(result, ensure_ascii=False, allow_nan=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
