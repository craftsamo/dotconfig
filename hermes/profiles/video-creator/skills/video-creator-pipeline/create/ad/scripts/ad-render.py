#!/usr/bin/env python3
"""Freeze and verify an authored ad. Never generate copy, claims or layout.

Reuses only tour.py's/authored.py's low-level primitives via an explicit,
absolute-path `sys.path` entry into the tour leaf's scripts directory. Neither
file is imported for its model/CLI dispatch, monkeypatched or modified.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import wave
from fractions import Fraction
from html.parser import HTMLParser
from pathlib import Path

from PIL import Image as PILImage

HERE = Path(__file__).resolve().parent
TOUR_SCRIPTS = (HERE.parents[1] / "tour" / "scripts").resolve()
PIPELINE_SCRIPTS = (HERE.parents[2] / "scripts").resolve()
sys.path.insert(0, str(TOUR_SCRIPTS))
sys.path.insert(0, str(PIPELINE_SCRIPTS))

from tour import (VENDOR, command, digest, fresh, hf, image, load, local,  # noqa: E402
                   number, require, text, write)
from authored import Markup, source_files  # noqa: E402
import mix_audio  # noqa: E402

ASPECT_SIZES = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}
DEFAULT_ASPECT = "9:16"
FPS = 30
COPY_ROLES = ("message", "claim", "cta", "support")
RESERVED = {"plan.json", "approved-plan.json", "integrity.json"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MEDIA_ATTRS = {"id", "class", "src", "muted", "playsinline", "data-start", "data-duration",
               "data-media-start", "data-track-index", "style", "preload", "data-volume"}


def plan_model(raw):
    require(isinstance(raw, dict), "plan must be an object")
    allowed = {"version", "product", "audience", "message", "cta", "theme", "style",
               "direction", "theme_detail", "claims", "note", "duration", "width",
               "height", "fps", "assets", "copy", "samples", "aspect", "mix"}
    require(set(raw) <= allowed, "unknown plan field")
    required = allowed - {"theme_detail", "claims", "note", "aspect", "mix"}
    require(required <= set(raw), "plan missing a required field")
    require(type(raw["version"]) is int and raw["version"] == 1, "plan version must be 1")
    for key in ("product", "audience", "theme", "style", "direction"):
        text(raw[key], key, 4000)
    for key in ("message", "cta"):
        # Capped identically to copy-row text: a message/cta the copy ledger
        # can never actually match would silently fail "has_message/has_cta"
        # with a confusing error, not a clear length rejection.
        text(raw[key], key, 2000)
    for key in ("theme_detail", "claims", "note"):
        if key in raw:
            text(raw[key], key, 4000, empty=True)
    duration = number(raw["duration"], 6, 30, "duration")
    aspect = raw.get("aspect", DEFAULT_ASPECT)
    require(isinstance(aspect, str) and aspect in ASPECT_SIZES,
            "aspect must be a known ratio: " + ", ".join(sorted(ASPECT_SIZES)))
    expected_w, expected_h = ASPECT_SIZES[aspect]
    for key, expected in (("width", expected_w), ("height", expected_h), ("fps", FPS)):
        require(type(raw[key]) is int and raw[key] == expected, f"{key} must be exactly {expected}")
    assets = raw["assets"]
    require(isinstance(assets, dict), "assets must be an object")
    for name, sha in assets.items():
        require(isinstance(name, str) and re.fullmatch(r"assets/[a-zA-Z0-9_./-]+", name)
                and ".." not in Path(name).parts, "asset path must be local under assets/")
        require(isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha), "asset sha256 required")

    if "mix" in raw:
        # An opt-in, already-approved Audio Mix master replaces every other
        # WAV placement (see hermes/AGENTS.md "audio_workflow"): the exact
        # staged asset paths named here are the ONLY audio this ad may ever
        # place, bound by hash through the ordinary asset map above - never
        # by the mutable original mix_bundle path.
        mix = raw["mix"]
        require(isinstance(mix, dict) and {"master", "receipt"} <= set(mix) <= {"master", "receipt",
                "captions", "timing"}, "mix requires at least master and receipt asset paths")
        for key in ("master", "receipt", "captions", "timing"):
            if key in mix:
                require(isinstance(mix[key], str) and mix[key] in assets,
                        f"mix.{key} must name a hashed entry in assets")
        require(mix["master"].lower().endswith(".wav"), "mix.master must be a .wav asset")
        require(mix["receipt"].lower().endswith(".json"), "mix.receipt must be a .json asset")
        for key in ("captions", "timing"):
            if key in mix:
                require(mix[key].lower().endswith(".json"), f"mix.{key} must be a .json asset")

    copy = raw["copy"]
    require(isinstance(copy, list) and copy, "at least one copy row required")
    ids, has_message, has_cta = set(), False, False
    for row in copy:
        require(isinstance(row, dict) and set(row) == {"id", "text", "role", "start", "end"},
                "invalid copy row")
        require(isinstance(row["id"], str) and re.fullmatch(r"[a-z][a-z0-9-]{0,47}", row["id"]),
                "copy id: lowercase slug required")
        require(row["id"] not in ids, "duplicate copy id")
        ids.add(row["id"])
        require(row["role"] in COPY_ROLES, "copy role must be message, claim, cta or support")
        text(row["text"], "copy text", 2000)
        start = number(row["start"], 0, duration, "copy start")
        end = number(row["end"], start, duration, "copy end")
        require(end > start, "copy hold must have positive duration")
        if row["role"] == "message" and row["text"] == raw["message"]:
            has_message = True
        if row["role"] == "cta":
            require(end - start >= 2, "CTA hold must be at least 2 readable seconds")
            if row["text"] == raw["cta"]:
                has_cta = True
        if row["role"] == "claim":
            require(raw.get("claims", "").strip(),
                    "claim role requires nonempty approved claims (not fact verification)")
    require(has_message, "copy must include a message row with the exact approved message text")
    require(has_cta, "copy must include a cta row with the exact approved cta text")

    last_frame = duration - 1 / FPS
    samples = raw["samples"]
    require(isinstance(samples, list) and 3 <= len(samples) <= 40, "3..40 proof samples required")
    previous = -1
    for sample in samples:
        require(isinstance(sample, dict) and set(sample) == {"at", "expect"},
                "sample needs at and expect")
        # A sample can only ever land on a representable frame, and the last
        # representable frame of a `duration`-second clip is duration-1/FPS,
        # never `duration` itself (there is no frame *at* the end boundary).
        at = number(sample["at"], 0, last_frame, "sample time")
        require(at > previous, "sample times must be unique and ordered")
        text(sample["expect"], "visible expectation", 2000)
        previous = at
    require(samples[0]["at"] == 0, "samples must include the first visible frame")
    require(samples[-1]["at"] >= last_frame - 1e-9,
            "samples must include the last visible frame (duration - 1/fps)")
    for row in copy:
        require(any(row["start"] < s["at"] < row["end"] for s in samples),
                f"sample required inside copy hold: {row['id']}")
    return {**raw, "duration": duration}


def _normalize_copy(value):
    return re.sub(r"\s+", " ", value).strip()


class CopyText(HTMLParser):
    """Extracts exact plain visible copy per declared id; flags any other
    visible text as a silent, undeclared addition. Nested spans are
    concatenated with only whitespace normalization, never reworded."""

    SKIP = ("script", "style", "title")
    # HTML5 void elements never have an end tag (real markup never sends one
    # for these); a start-tag-only push with no matching pop would otherwise
    # desync the covering-id stack for every sibling that follows.
    VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input",
                       "link", "meta", "param", "source", "track", "wbr"})

    def __init__(self, ids):
        super().__init__()
        self.ids = ids
        self.buffers = {i: [] for i in ids}
        self.stack = []
        self.skip_tag = None
        self.seen_ids = set()
        self.uncovered = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        eid = attrs.get("id")
        if eid is not None:
            require(eid not in self.seen_ids, f"duplicate id in source: {eid}")
            self.seen_ids.add(eid)
        if tag in self.SKIP and self.skip_tag is None:
            self.skip_tag = tag
        if tag in self.VOID:
            return
        active = self.stack[-1] if self.stack else None
        if eid in self.ids:
            require(active is None, f"copy id {eid} must not nest inside another copy id")
            active = eid
        self.stack.append(active)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag == self.skip_tag:
            self.skip_tag = None
        if tag in self.VOID:
            return
        if self.stack:
            self.stack.pop()

    def handle_data(self, data):
        if self.skip_tag:
            return
        active = self.stack[-1] if self.stack else None
        if active:
            self.buffers[active].append(data)
        elif data.strip():
            self.uncovered.append(data.strip())


def copy_check(root, plan):
    code = local(str(root / "index.html"), {".html"}).read_text(encoding="utf-8")
    ids = {row["id"] for row in plan["copy"]}
    texts = {row["id"]: row["text"] for row in plan["copy"]}
    parser = CopyText(ids)
    parser.feed(code)
    parser.close()
    require(not parser.stack, "unbalanced element nesting in source")
    missing = ids - parser.seen_ids
    require(not missing, f"copy ids missing from source: {sorted(missing)}")
    require(not parser.uncovered,
            f"visible text outside the declared copy ledger (no silent additions): {parser.uncovered[:3]}")
    for element_id, expected in texts.items():
        # Both sides go through the identical normalization so a plan author's
        # incidental whitespace formatting can never cause a false mismatch,
        # while runs of whitespace still separate words rather than vanishing.
        actual = _normalize_copy("".join(parser.buffers[element_id]))
        require(actual == _normalize_copy(expected),
                f"copy id {element_id} text mismatch: expected {expected!r}, found {actual!r}")


def _attr_float(attrs, key):
    value = attrs.get(key)
    require(value is not None, f"missing {key} attribute")
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"invalid {key} attribute")


def markup_check(root, plan):
    code = local(str(root / "index.html"), {".html"}).read_text(encoding="utf-8")
    markup = Markup()
    markup.feed(code)
    require(len(markup.roots) == 1, "one standalone composition root required")
    attrs = markup.roots[0]
    require(attrs.get("data-composition-id") == "ad" and attrs.get("data-start") == "0",
            "root id ad and start 0 required")
    require((attrs.get("data-width"), attrs.get("data-height"), attrs.get("data-fps"))
            == (str(plan["width"]), str(plan["height"]), str(FPS)), "root dimensions/fps mismatch")
    require(float(attrs.get("data-duration", "nan")) == plan["duration"], "root duration mismatch")
    require("assets/gsap.min.js" in markup.assets and "__timelines" in code,
            "local GSAP and registered timeline required")
    for p in root.rglob("*"):
        name = p.relative_to(root).as_posix()
        if name.split("/")[0] == ".hyperframes":
            continue
        if p.suffix in (".css", ".js", ".html") and name != "assets/gsap.min.js":
            content = p.read_text(encoding="utf-8")
            if p.suffix == ".html":
                parsed = Markup()
                parsed.feed(content)
                content = "\n".join(parsed.code)
            match = re.search(r"\b(fetch|XMLHttpRequest|WebSocket|EventSource|setTimeout|"
                               r"setInterval|requestAnimationFrame|Date)\s*\(|Math\.random|"
                               r"Date\.now|performance\.now|@import", content)
            require(not match, f"{name}: network/clocks/unseekable animation forbidden: "
                                f"{match.group() if match else ''}")
            require(not re.search(r"\.(play|pause|load)\s*\(|\.currentTime\s*=|\.playbackRate\s*=", content),
                    "HyperFrames owns media playback/seeking")
            require(not re.search(r"\bvolume\s*:|\.(volume|muted)\s*=", content),
                    "audio automation requires a separately approved finishing path")
            for url in re.findall(r"url\(\s*['\"]?([^)'\"]+)", content):
                markup.assets.append(url)
    for name in markup.assets:
        require(isinstance(name, str) and re.fullmatch(r"assets/[a-zA-Z0-9_./-]+", name)
                and ".." not in Path(name).parts, "assets must be local under assets/; no URL capture")
        asset_path = local(str(root / name), {Path(name).suffix})
        # A renamed non-image or an oversized/animated image must be caught
        # before it can ever reach a frozen project, not left to the render
        # step or a suffix-only guess.
        if Path(name).suffix.lower() in IMAGE_SUFFIXES:
            image(asset_path)
    require(digest(root / "assets/gsap.min.js") == load(VENDOR / "gsap-provenance.json")["sha256"],
            "GSAP vendor hash mismatch")
    _media_check(root, plan, markup)
    _mix_check(root, plan)


def _mix_check(root, plan):
    """When opted in, validate the STAGED Mix delivery (master/receipt and
    optional captions/timing) named by `plan["mix"]`, by delegating to Audio
    Mix's own `validate_delivery` through `mix_audio`. Never re-verifies the
    original full bundle here - that already happened at staging time."""
    mix = plan.get("mix")
    if mix is None:
        return
    master = local(str(root / mix["master"]), {".wav"})
    receipt = local(str(root / mix["receipt"]), {".json"})
    captions = local(str(root / mix["captions"]), {".json"}) if "captions" in mix else None
    timing = local(str(root / mix["timing"]), {".json"}) if "timing" in mix else None
    take = mix_audio.validate_staged_delivery(master, receipt, captions, timing,
                                               duration_seconds=plan["duration"])
    require(take["status"] in ("PASS", "WARN"), "staged Mix receipt is not deliverable (status FAIL)")


def _probe_video(path):
    """Direct ffprobe call via tour's `command`; no footage.py media plumbing."""
    info = json.loads(command(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                                "-of", "json", str(path)]))
    videos = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    require(len(videos) == 1, "video asset must contain exactly one video stream")
    video = videos[0]
    require(video.get("codec_name"), "video source must report an actual codec")
    width, height = int(video["width"]), int(video["height"])
    require(32 <= width <= 4096 and 32 <= height <= 4096 and width * height <= 9_000_000,
            "video exceeds pixel bounds (sides <=4096, area <=9,000,000)")
    duration = float(info.get("format", {}).get("duration", 0))
    return duration


def _media_check(root, plan, markup):
    media_ids, audio_placements, audio_track_attrs = set(), [], []
    for tag, media_attrs in markup.media:
        if tag not in ("video", "audio"):
            continue
        extra = set(media_attrs) - MEDIA_ATTRS
        require(not extra, f"unsupported {tag} attributes (no autoplay, loop or retiming): {sorted(extra)}")
        media_id = media_attrs.get("id")
        require(media_id, f"{tag} element requires a unique id")
        require(media_id not in media_ids, f"duplicate media id: {media_id}")
        media_ids.add(media_id)
        media_start = media_attrs.get("data-media-start")
        require(media_start is None or float(media_start) == 0, "prepared media start must be zero")
        start = number(_attr_float(media_attrs, "data-start"), 0, plan["duration"], f"{tag} start")
        length = number(_attr_float(media_attrs, "data-duration"), 0.01, plan["duration"], f"{tag} duration")
        require(start + length <= plan["duration"] + 1e-6, "media placement exceeds ad duration")
        src = media_attrs.get("src")
        require(isinstance(src, str) and src.startswith("assets/"), "media src must be local under assets/")
        path = local(str(root / src), {Path(src).suffix})
        if tag == "video":
            require(Path(src).suffix.lower() == ".mp4", "video assets must be mp4")
            require("muted" in media_attrs, "video must be muted")
            source_duration = _probe_video(path)
            require(source_duration + 1e-3 >= length, "video source duration does not cover its placement")
        else:
            require(Path(src).suffix.lower() == ".wav",
                    "audio assets must be a standalone finished WAV, not TTS/capture output")
            require("muted" not in media_attrs, "audio must not be muted")
            require(float(media_attrs.get("data-volume", "1")) == 1, "audio must play at unity volume")
            with wave.open(str(path), "rb") as w:
                require(w.getcomptype() == "NONE" and w.getnchannels() in (1, 2),
                        "audio must be mono/stereo PCM WAV")
                wav_length = w.getnframes() / w.getframerate()
            require(wav_length + 1e-3 >= length, "audio file duration does not cover its placement")
            mix = plan.get("mix")
            if mix is not None and src == mix["master"]:
                require(start == 0, "the Mix master must start at 0")
                require(abs(length - plan["duration"]) < 1e-6,
                        "the Mix master must span the ad's full duration")
            audio_placements.append(src)
            audio_track_attrs.append(media_attrs.get("data-track-index"))
    require(len(audio_placements) <= 16, "at most 16 audio tracks are supported in this version")
    require(len(set(audio_placements)) == len(audio_placements),
            "each WAV asset must be placed by exactly one <audio> element; a sound repeated at another "
            "time needs its own separately approved local asset copy, never the same src placed twice")
    wav_assets = {name for name in plan["assets"] if name.lower().endswith(".wav")}
    require(set(audio_placements) == wav_assets,
            "every declared WAV asset must be placed by exactly one <audio> element")
    mix = plan.get("mix")
    if mix is not None:
        # Mix mode plays only the approved master - never a stem alongside
        # it (see hermes/AGENTS.md "audio_workflow"). Video-in-video stays
        # muted regardless (checked above), so no other audio can hide there.
        require(wav_assets == {mix["master"]},
                "when mix is used, the Mix master is the only declared WAV asset")
        require(audio_placements == [mix["master"]],
                "when mix is used, the Mix master must be placed exactly once")
    if len(audio_placements) > 1 or mix is not None:
        indices = []
        for raw in audio_track_attrs:
            require(raw is not None,
                    "data-track-index is required on every <audio> element when more than one audio "
                    "track is placed")
            require(isinstance(raw, str) and re.fullmatch(r"[1-9][0-9]*", raw.strip()),
                    "data-track-index must be a positive integer")
            indices.append(int(raw))
        require(len(set(indices)) == len(indices),
                "data-track-index values must be distinct across placed audio tracks")


def freeze(args):
    plan_path = local(args.plan, {".json"})
    require(isinstance(args.approval_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", args.approval_sha256),
            "approval sha256 required")
    require(digest(plan_path) == args.approval_sha256, "plan changed since approval")
    plan = plan_model(load(plan_path))
    source = Path(args.source)
    before = source_files(source, version=3)
    require(not RESERVED & before.keys(), "reserved source filenames")
    asset_files = {n: h for n, h in before.items() if n.startswith("assets/")}
    require(asset_files == plan["assets"], "source assets differ from the approved plan's asset map")
    markup_check(source, plan)
    copy_check(source, plan)
    project = fresh(args.project)
    require(".." not in project.parts, "parent traversal forbidden")
    require(not project.is_relative_to(source), "project must be outside authoring source")
    project.mkdir()
    for name in before:
        dest = project / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, dest)
    # The copy itself must be byte-identical to what was validated, not just
    # "some file landed at that path" — a partial/interrupted copy or a
    # filesystem surprise must fail here, before anything is published.
    copied = source_files(project, version=3)
    require(copied == before, "copied project files do not match the validated source inventory")
    after = source_files(source, version=3)
    require(after == before, "source changed during freeze; revise in fresh source")
    write(project / "approved-plan.json", plan)
    # The frozen plan snapshot must be durably valid the moment it is
    # published, not merely at validation time: reload and re-run it through
    # plan_model to catch any serialization drift (float rounding, key
    # ordering, silent coercion) before integrity.json binds it as truth.
    republished = plan_model(load(project / "approved-plan.json"))
    require(republished == plan, "approved plan changed shape after serialization; refusing to publish")
    write(project / "integrity.json", {"version": 3, "files": source_files(project, 3)})
    return {"project": str(project), "duration": plan["duration"], "next": "snapshot"}


def project_model(value):
    project = Path(value)
    saved = load(local(str(project / "integrity.json"), {".json"}))
    require(isinstance(saved, dict) and saved.get("version") == 3, "frozen ad project required")
    actual = source_files(project, 3)
    actual.pop("integrity.json")
    require(actual == saved.get("files"), "project changed since freeze; revise in fresh source/project")
    plan = plan_model(load(project / "approved-plan.json"))
    markup_check(project, plan)
    copy_check(project, plan)
    return project, plan


def output_dir(value, *excluded):
    out = fresh(value)
    require(".." not in out.parts, "parent traversal forbidden")
    for path in excluded:
        require(not out.is_relative_to(path), "output must be outside source/project/preview")
    return out


def check(project, plan, out):
    times = [s["at"] for s in plan["samples"]]
    hf(project, ["check", "--json", "--at", ",".join(map(str, times))], out / "check.json")
    result = load(out / "check.json")
    contrast = result.get("contrast", {})
    require(result.get("ok") and contrast.get("enabled") and contrast.get("checked", 0) > 0,
            "check/contrast audit failed or skipped")
    return times


def runtime_identity():
    binary = shutil.which("hyperframes")
    require(binary, "hyperframes CLI missing; ask maintainer to provision it")
    return {"executable": str(Path(binary).resolve()),
            "version": command([binary, "--version"]).strip()}


def snapshot(args):
    project, plan = project_model(args.project)
    out = output_dir(args.out, project)
    out.mkdir()
    runtime = runtime_identity()
    times = check(project, plan, out)
    hf(project, ["snapshot", "--at", ",".join(map(str, times)), "--no-end", "--describe", "false",
                 "-o", str(out / "frames")], out / "snapshot.log")
    frames = sorted((out / "frames").glob("*.png"))
    require(len(frames) == len(times), "snapshot count mismatch")
    for frame in frames:
        require(image(frame) == (plan["width"], plan["height"]), "snapshot dimensions mismatch")
    project_model(str(project))
    require(runtime_identity() == runtime, "runtime changed during preview")
    preview = {"project": str(project), "integrity": digest(project / "integrity.json"), "runtime": runtime,
               "times": times, "frames": {p.name: digest(p) for p in frames},
               "check": digest(out / "check.json")}
    write(out / "preview.json", preview)
    return {"preview": str(out), "preview_sha256": digest(out / "preview.json"),
            "frames": len(frames), "rendered_mp4": False}


def approved_preview(value, project, plan, approval_sha256):
    preview_path = local(str(Path(value) / "preview.json"), {".json"})
    require(digest(preview_path) == approval_sha256, "approved preview hash mismatch")
    data = load(preview_path)
    require(data.get("runtime") == runtime_identity(), "runtime changed since preview; new preview approval required")
    require(data.get("project") == str(project) and data.get("integrity") == digest(project / "integrity.json"),
            "approved preview belongs to another project")
    require(data.get("times") == [s["at"] for s in plan["samples"]], "approved sample times changed")
    frames = data.get("frames")
    require(isinstance(frames, dict) and len(frames) == len(plan["samples"]),
            "approved preview lacks proof frames")
    for name, expected in frames.items():
        require(Path(name).name == name, "invalid preview frame path")
        require(digest(local(str(preview_path.parent / "frames" / name), {".png"})) == expected,
                "approved preview frame changed")
    require(digest(local(str(preview_path.parent / "check.json"), {".json"})) == data.get("check"),
            "approved check changed")


def measure_audio(path):
    """Direct ffmpeg `loudnorm` measurement pass over the final decoded mix.
    Only used when more than one declared WAV asset is placed: individually
    safe unity-volume sources can still clip once HyperFrames sums them.
    Measures only, never applies gain. A short/sparse SFX-style ad
    legitimately measures an unmeasurable (nonfinite) integrated loudness —
    that alone is not a defect, so `input_i` is reported as `None` with a
    warning rather than failing; only an undecodable, entirely blank/silent
    (nonfinite true peak) or clipping (true peak >=0 dBTP) result is
    rejected. A clipping rejection is evidence to reduce gain (e.g. a fresh
    edit-sfx pass) or revise the placement timing — never something this
    leaf corrects silently, and never a "ducking"/"mixing" capability this
    leaf does not have."""
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
    require(true_peak < 0,
            "final mixed audio true peak >=0 dBTP (multiple unity-volume sources may clip when summed); "
            "reduce gain (e.g. a fresh edit-sfx pass) or revise placement timing, never fixed here")
    return {"input_i": integrated, "input_tp": true_peak, "warnings": warnings}


def render(args):
    project, plan = project_model(args.project)
    require(args.approved_preview and args.approval_sha256,
            "render requires --approved-preview and --approval-sha256; no bypass")
    require(isinstance(args.approval_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", args.approval_sha256),
            "approval sha256 required")
    approved_preview(args.approved_preview, project, plan, args.approval_sha256)
    out = output_dir(args.out, project, Path(args.approved_preview))
    out.mkdir()
    times = check(project, plan, out)
    movie = out / "ad.mp4"
    hf(project, ["render", "--output", str(movie), "--fps", str(FPS), "--workers", "1",
                 "--strict", "--no-best-effort", "--quiet"], out / "render.log")
    info = json.loads(command(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                                "-of", "json", str(movie)]))
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    require((video["width"], video["height"]) == (plan["width"], plan["height"]), "render dimensions mismatch")
    require(video["codec_name"] == "h264" and video["pix_fmt"] == "yuv420p"
            and Fraction(video["avg_frame_rate"]) == FPS, "render codec/pixel-format/fps mismatch")
    require(abs(float(info["format"]["duration"]) - plan["duration"]) <= .1, "render duration mismatch")
    expects_audio = any(name.startswith("assets/") and name.endswith(".wav") for name in plan["assets"])
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
    require(has_audio == expects_audio, "render audio presence mismatch against approved plan")
    wav_assets = {name for name in plan["assets"] if name.lower().endswith(".wav")}
    mix = plan.get("mix")
    audio_measurement = None
    if len(wav_assets) > 1 or mix is not None:
        # Sources that were each individually safe at unity volume can still
        # clip once HyperFrames sums them; measure the actual decoded mix,
        # never trust the per-source checks alone. Absent for <=1 declared
        # WAV with no mix — never a present-but-None key on the legacy
        # single-audio/no-audio report shape. A single opt-in Mix WAV is
        # ALSO measured (not just multi-source ads): the master is the ad's
        # sole audio and its own re-encode into the final MP4 is worth a
        # fresh check, not an assumption from the Mix receipt alone.
        audio_measurement = measure_audio(movie)
        if mix is not None:
            # Check the approved ceiling, not the requested or input peak
            # presented as a measurement of the encoded result.
            receipt = mix_audio.load_json(local(str(project / mix["receipt"]), {".json"}))
            mix_audio.check_final_audio(audio_measurement, receipt, info["streams"], plan["duration"])
    command(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(movie), "-f", "null", "-"], timeout=300)
    (out / "review").mkdir()
    for i, at in enumerate(times):
        command(["ffmpeg", "-nostdin", "-v", "error", "-n", "-ss", str(at), "-i", str(movie),
                 "-frames:v", "1", str(out / "review" / f"{i:02}.png")])
    shutil.copyfile(out / "review" / f"{len(times)-1:02}.png", out / "poster.png")
    project_model(str(project))
    report = {"project": str(project), "mp4": str(movie), "decoded": True, "bytes": movie.stat().st_size,
              "duration": float(info["format"]["duration"]), "width": video["width"], "height": video["height"],
              "fps": FPS, "samples": plan["samples"],
              "semantic_review": "pending visual comparison to the approved plan and sample expectations",
              "temporal_review": "sampled only", "audio_listening": "unverified", "media_generation": 0}
    if audio_measurement is not None:
        report["audio_measurement"] = audio_measurement
    write(out / "qa.json", report)
    (out / "qa.md").write_text(
        "# Ad QA\n\nLocal full decode passed. See check.json and qa.json.\n"
        "Semantic fidelity, claim accuracy, CTA legibility, Japanese text fit and audio listening "
        "require visual/listening review.\nSamples are not a complete temporal or listening verdict.\n",
        encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    p = subs.add_parser("freeze")
    p.add_argument("--source", required=True)
    p.add_argument("--plan", required=True)
    p.add_argument("--approval-sha256", required=True)
    p.add_argument("--project", required=True)
    p = subs.add_parser("snapshot")
    p.add_argument("--project", required=True)
    p.add_argument("--out", required=True)
    p = subs.add_parser("render")
    p.add_argument("--project", required=True)
    p.add_argument("--approved-preview", required=True)
    p.add_argument("--approval-sha256", required=True)
    p.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        print("RESULT: " + json.dumps(globals()[args.command](args)))
    except (ValueError, OSError, KeyError, TypeError, wave.Error, EOFError,
            subprocess.TimeoutExpired, PILImage.DecompressionBombError) as exc:
        print(f"ad-render: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
