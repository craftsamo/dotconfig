#!/usr/bin/env python3
"""VideoCreator's audio-timing/Mix-consumption helper.

Two independent jobs live here:

1. `timing --spec-file JSON --out NEWDIR` - a PRELIMINARY, narrow freeze of
   an exact cue-timing JSON. It never decodes, generates or synthesizes
   audio, never approves a mix plan, and never invents a control it was not
   given. The frozen JSON is the SAME shape Audio Mix's `create-mix`/
   `edit-mix` optional `timing` form field consumes verbatim.
2. `validate_staged_delivery` / `verify_full_bundle` - thin, read-only
   wrappers around Audio Mix's OWN `validate_delivery`/`verify_bundle`
   (`audio-creator-pipeline/scripts/mix-media.py`), loaded dynamically by
   absolute path via `importlib`. This module never reimplements Mix's
   hash/format/receipt checks - it only calls them, then adds the one cross-
   check that is exclusively VideoCreator's business: that a staged
   `timing.json` used to author a video actually matches what the delivered
   Mix receipt recorded, and that its duration matches the finished video.

Kept import-safe: the `timing` half is stdlib-only. Loading Audio Mix's own
module pulls in its dependencies (which themselves tolerate a missing numpy
for pure validation, per `mix-media.py`/`music-media.py`), so validation here
never requires numpy either.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from html.parser import HTMLParser

MAX_CUES = 32
MAX_DURATION_SECONDS = 600
SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

HERE = Path(__file__).resolve().parent
MIX_MEDIA_PATH = (HERE.parents[3] / "audio-creator" / "skills" / "audio-creator-pipeline"
                   / "scripts" / "mix-media.py")
_mix_media_module = None


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _finite_number(value, name):
    # `bool` is a subclass of `int` in Python, but `type(True) is bool`, not
    # `int` - this check therefore already rejects True/False, never just
    # coincidentally accepting them as 1/0.
    require(type(value) in (int, float) and math.isfinite(value),
            f"{name}: finite number required (no booleans)")
    return value


def number(value, low, high, name):
    _finite_number(value, name)
    require(low <= value <= high, f"{name}: must be within {low}..{high}")
    return value


def positive(value, name):
    _finite_number(value, name)
    require(value > 0, f"{name}: must be greater than zero")
    return value


def slug(value, name):
    require(isinstance(value, str) and 1 <= len(value) <= 80 and SLUG_RE.fullmatch(value),
            f"{name}: slug requires 1-80 lowercase ASCII letters/digits with single hyphens")
    return value


def local_json_file(value):
    require(isinstance(value, str) and not any(c in value for c in ("\x00", "\n", "://")),
            "spec-file: local path required")
    path = Path(value).expanduser()
    require(path.is_absolute(), "spec-file: must be an absolute path")
    require(not any(part.is_symlink() for part in (path, *path.parents)),
            "spec-file: symlink inputs/outputs forbidden")
    require(path.is_file() and path.suffix.lower() == ".json",
            "spec-file: missing local file or not .json")
    require(path.stat().st_size <= 1_000_000, "spec-file: exceeds 1 MB")
    return path


def fresh_dir(value):
    path = Path(value).expanduser()
    require(path.is_absolute() and path.parent.is_dir(),
            "out: needs an existing absolute parent directory")
    require(not any(part.is_symlink() for part in (path, *path.parents)),
            "out: symlink inputs/outputs forbidden")
    require(not path.exists(), "out: must not exist; existing timing evidence is never overwritten")
    return path


def load_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=lambda token: require(False, f"nonfinite JSON number: {token}"),
    )


def validate_timing_spec(raw):
    """Validate the shared timing-spec shape in place; returns it unchanged.

    {"version": 1, "duration_seconds": 1..600,
     "cues": [{"id": slug, "source": slug, "start": >=0,
               "source_start": >=0, "duration": >0}, ...<=32, unique id]}

    Every field is required exactly as given - no defaults are invented and
    no out-of-range value is silently clamped. This is the full contract;
    nothing here ever authors placement, gain, envelope or fade - that stays
    with Audio Mix's create-mix/edit-mix authoring.
    """
    require(isinstance(raw, dict) and set(raw) == {"version", "duration_seconds", "cues"},
            "timing spec must be an object with exactly version, duration_seconds, cues")
    require(type(raw["version"]) is int and raw["version"] == 1, "timing spec version must be 1")
    duration_seconds = number(raw["duration_seconds"], 1, MAX_DURATION_SECONDS, "duration_seconds")
    cues = raw["cues"]
    require(isinstance(cues, list) and 1 <= len(cues) <= MAX_CUES,
            f"cues: 1..{MAX_CUES} entries required")
    seen_ids = set()
    for cue in cues:
        require(isinstance(cue, dict)
                and set(cue) == {"id", "source", "start", "source_start", "duration"},
                "cue must be an object with exactly id, source, start, source_start, duration")
        cue_id = slug(cue["id"], "cue id")
        require(cue_id not in seen_ids, f"duplicate cue id: {cue_id}")
        seen_ids.add(cue_id)
        slug(cue["source"], "cue source")
        start = number(cue["start"], 0, duration_seconds, "cue start")
        source_start = number(cue["source_start"], 0, MAX_DURATION_SECONDS, "cue source_start")
        duration = positive(cue["duration"], "cue duration")
        require(start + duration <= duration_seconds + 1e-9,
                f"cue {cue_id}: start+duration must fit fully inside duration_seconds")
        require(source_start + duration <= MAX_DURATION_SECONDS + 1e-9, "cue exceeds source duration bound")
        require(round(duration * 48000) > 0 and round(start * 48000) + round(duration * 48000)
                <= round(duration_seconds * 48000), "cue does not fit after sample quantization")
    return raw


def timing(args):
    spec_path = local_json_file(args.spec_file)
    raw = load_json(spec_path)
    validated = validate_timing_spec(raw)
    out = fresh_dir(args.out)
    out.mkdir()
    frozen_path = out / "timing.json"
    with frozen_path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(validated, ensure_ascii=True, indent=2, allow_nan=False) + "\n")
    sha256 = hashlib.sha256(frozen_path.read_bytes()).hexdigest()
    return {
        "status": "timing-only",
        "timing": str(frozen_path),
        "sha256": sha256,
        "duration_seconds": validated["duration_seconds"],
        "cues": len(validated["cues"]),
        "note": "preliminary timing freeze only; no plan approval, no audio synthesis",
    }


def load_mix_media():
    """Dynamically import Audio Mix's own `mix-media.py` by absolute path -
    a cross-profile, read-only dependency. Never edited, monkeypatched or
    reimplemented here; only its exact `validate_delivery`/`verify_bundle`
    are ever called. Cached after the first successful load."""
    global _mix_media_module
    if _mix_media_module is None:
        require(MIX_MEDIA_PATH.is_file(),
                "Audio Mix helper (mix-media.py) not found; Audio Mix must be installed "
                f"at {MIX_MEDIA_PATH}")
        spec = importlib.util.spec_from_file_location("_video_creator_mix_media", MIX_MEDIA_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _mix_media_module = module
    return _mix_media_module


def validate_staged_delivery(master, receipt_path, captions_path=None, timing_path=None,
                              duration_seconds=None):
    """Validate a STAGED SUBSET of a Mix delivery: just the master WAV, its
    `mix.take.json` receipt, and optionally `captions.json`/`timing.json` -
    never the full physical bundle (`sources/`, `proposal.md`, `mix.json`).
    This is the canonical path for `create-ad`/`create-tour`'s opt-in mix
    consumption (see hermes/AGENTS.md "audio_workflow"): those leaves copy
    only these files into their own frozen source, and bind them by hash
    through the SAME asset/source-file map every other input already goes
    through - never by the original (mutable) `mix_bundle` path.

    The master/receipt/caption checks are entirely Audio Mix's own
    `validate_delivery` (unmodified, called by reference); the only check
    OWNED here is the timing<->receipt<->video-duration cross-check, because
    that binding is exclusively a video-authoring concern.

    Returns the receipt (`mix.take.json`, i.e. Mix's "take") unchanged.
    """
    mm = load_mix_media()
    take = mm.validate_delivery(master, receipt_path, captions_path)
    if duration_seconds is not None:
        require(take["master"]["frames"] == round(duration_seconds * 48000),
                "Mix master duration does not match this video's total duration")
    require(("timing.json" in take["files"]) == (timing_path is not None),
            "Mix timing evidence must not be dropped; receipt records no timing.json for an invented input")
    if timing_path is not None:
        raw_timing = mm.read(timing_path)
        files = take.get("files") or {}
        require("timing.json" in files,
                "staged mix_timing supplied but the Mix receipt records no timing.json")
        require(mm.digest(raw_timing) == files["timing.json"],
                "staged mix_timing hash does not match the Mix receipt's timing.json")
        # `mm.media` is mix-media.py's own loaded `music-media.py` submodule -
        # its `strict_json`/`keys` primitives, reused by reference, never
        # reimplemented here.
        timing_doc = mm.media.strict_json(raw_timing)
        mm.media.keys(timing_doc, {"version", "duration_seconds", "cues"}, set(), "timing")
        validate_timing_spec(timing_doc)
        if duration_seconds is not None:
            require(timing_doc["duration_seconds"] == duration_seconds,
                    "Mix timing duration does not match this video's total duration")
    return take


def verify_full_bundle(bundle):
    """Verify a COMPLETE physical Mix bundle directory by delegating
    entirely to Audio Mix's own `verify_bundle` - no local reimplementation
    of its source/spec/manifest checks. Used only for an initial staging
    check against an externally supplied `mix_bundle` path (see
    hermes/AGENTS.md "audio_workflow"); the formal, approved video form
    always binds the STAGED subset afterward via `validate_staged_delivery`,
    never this mutable bundle path."""
    media = load_mix_media()
    return media.verify_bundle(bundle)


def check_caption_markup(index, captions_path):
    """Bind authored caption text/timing to the separately verified Mix sidecar."""
    captions = load_json(captions_path)["captions"] if captions_path else []

    class Captions(HTMLParser):
        def __init__(self):
            super().__init__()
            self.depth = 0
            self.current = None
            self.items = {}

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag in ("br", "img", "meta", "link", "input", "hr", "source"):
                if self.current and tag == "br":
                    self.items[self.current][1].append(" ")
                return
            self.depth += 1
            ident = attrs.get("id", "")
            if ident.startswith("mix-caption-"):
                require(self.current is None and ident not in self.items, "duplicate/nested Mix caption element")
                self.current = ident
                self.items[ident] = (attrs, [], self.depth)

        def handle_endtag(self, tag):
            if self.current and self.items[self.current][2] == self.depth:
                self.current = None
            self.depth -= 1

        def handle_data(self, text):
            if self.current:
                self.items[self.current][1].append(text)

    parser = Captions()
    parser.feed(index.read_text(encoding="utf-8"))
    require(set(parser.items) == {f"mix-caption-{i}" for i in range(1, len(captions) + 1)},
            "Mix caption elements must match the sidecar exactly")
    for i, cue in enumerate(captions, 1):
        attrs, parts, _ = parser.items[f"mix-caption-{i}"]
        require("clip" in attrs.get("class", "").split(), "Mix captions require timed clip elements")
        require(" ".join("".join(parts).split()) == " ".join(cue["text"].split()), "Mix caption text changed")
        require(abs(float(attrs.get("data-start", "nan")) - cue["start"]) < 1e-6
                and abs(float(attrs.get("data-duration", "nan")) - (cue["end"] - cue["start"])) < 1e-6,
                "Mix caption placement changed")


def check_final_audio(measured, receipt, streams, duration):
    tracks = [s for s in streams if s.get("codec_type") == "audio"]
    require(len(tracks) == 1, "final Mix requires exactly one audio stream")
    actual = float(tracks[0].get("duration", "nan"))
    require(math.isfinite(actual) and abs(actual - duration) <= .1, "final Mix audio duration mismatch")
    ceiling = receipt["output_policy"]["true_peak_dbtp"]
    peak = measured["input_tp"]
    require(peak < 0 and peak <= ceiling + .2, "final Mix true peak exceeds approved ceiling (0.2 dB encoding tolerance)")
    measured["approved_true_peak_dbtp"] = ceiling
    measured["audio_duration_seconds"] = actual
    return measured


def measure_audio(path):
    """Measure (never alter) the decoded audio track of a local media file
    via one ffmpeg `loudnorm` pass. Shared by create-ad/create-tour's final
    render QA when an opt-in Mix master is the sole/added audio - this is a
    fresh measurement of the ACTUAL final render, never a copy of the Mix
    receipt's own numbers presented as if newly measured."""
    proc = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "info", "-xerror", "-i", str(path),
         "-map", "0:a:0", "-af", "loudnorm=print_format=json", "-f", "null", "-"],
        capture_output=True, text=True, timeout=300)
    require(proc.returncode == 0, "final audio decode/measurement failed (no audio stream or decode error)")
    match = re.search(r"\{[^{}]*\}", proc.stdout + proc.stderr)
    require(match, "audio measurement produced no JSON summary")
    data = json.loads(match.group(0))

    def num(key):
        try:
            value = float(data[key])
        except (KeyError, ValueError, TypeError):
            return None
        return value

    integrated, true_peak = num("input_i"), num("input_tp")
    require(true_peak is not None and math.isfinite(true_peak),
            "audio measurement missing/nonfinite true peak (no audio, decode failure, or entirely "
            "blank/silent)")
    warnings = []
    if integrated is None or not math.isfinite(integrated):
        integrated = None
        warnings.append("integrated loudness unmeasurable (short/sparse audio); true peak was still checked")
    return {"input_i": integrated, "input_tp": true_peak, "warnings": warnings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    sub = subs.add_parser("timing")
    sub.add_argument("--spec-file", required=True)
    sub.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        print("RESULT: " + json.dumps(globals()[args.command](args)))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"mix-audio: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
