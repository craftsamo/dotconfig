#!/usr/bin/env python3
"""Freeze supplied explainer inputs and approved authored HTML; never synthesize media."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import wave
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
CREATE = HERE.parents[1]
sys.path.insert(0, str(CREATE / "tour/scripts"))
sys.path.insert(0, str(HERE.parents[2] / "scripts"))
from tour import VENDOR, command, digest, fresh as _fresh, hf, identifier, image, load, local as _local, number, require, text, write
from authored import Markup as _Markup, source_files
import mix_audio

_mc_spec = importlib.util.spec_from_file_location("explainer_motion_canvas", HERE / "motion_canvas.py")
mc = importlib.util.module_from_spec(_mc_spec)
_mc_spec.loader.exec_module(mc)

# Reuse the exact-copy parser only, not the ad's schema or rendering dispatch.
_spec = importlib.util.spec_from_file_location("explainer_copy", CREATE / "ad/scripts/ad-render.py")
_copy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_copy)

SIZES = {"16:9": (1280, 720), "9:16": (720, 1280)}
FPS = 30
RESERVED = {"plan.json", "proposal.md", "integrity.json", "approved-proposal.md"}
MOUTH_TRACK = "assets/mouth-track.js"
VENDOR_FILES = ("gsap.min.js", "GSAP-LICENSE.txt", "gsap-provenance.json")
MEDIA_ATTRS = {"id", "class", "src", "style", "preload", "data-start", "data-duration",
               "data-track-index", "data-media-start", "data-volume", "muted", "playsinline"}


def local(value, suffixes):
    require(".." not in Path(value).parts, "parent traversal forbidden")
    return _local(value, suffixes)


def fresh(value):
    require(".." not in Path(value).parts, "output parent traversal forbidden")
    return _fresh(value)


class Markup(_Markup):
    def __init__(self):
        super().__init__()
        self.elements = {}

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        attributes = dict(attrs)
        if "id" in attributes:
            self.elements[attributes["id"]] = attributes


def asset_name(value):
    require(isinstance(value, str) and re.fullmatch(r"assets/[a-zA-Z0-9_./-]+", value)
            and ".." not in Path(value).parts and "//" not in value,
            "asset must be a relative path under assets/")
    require(Path(value).as_posix() == value, "noncanonical asset path")
    return value


def model(raw):
    required = {"version", "topic", "audience", "learning_goal", "theme", "style", "direction",
                "renderer", "duration", "aspect", "character", "audio", "units", "copy",
                "samples", "assets", "pending", "must_keep"}
    require(isinstance(raw, dict) and set(raw) == required, "spec has missing or unknown fields")
    require(type(raw["version"]) is int and raw["version"] in (1, 2), "version must be 1 (HyperFrames) or 2 (Motion Canvas)")
    for name in ("topic", "audience", "learning_goal", "theme", "style", "direction"):
        text(raw[name], name, 4000)
    text(raw["must_keep"], "must_keep", 4000, empty=True)
    require(raw["renderer"] in ("hyperframes", "motion-canvas"), "unknown renderer")
    require(raw["aspect"] in SIZES, "aspect must be 16:9 or 9:16")
    duration = number(raw["duration"], 1, 180, "duration")
    require(isinstance(raw["assets"], dict) and len(raw["assets"]) <= 160, "at most 160 assets")
    for name, sha in raw["assets"].items():
        asset_name(name)
        require(isinstance(sha, str) and re.fullmatch(r"[a-f0-9]{64}", sha), "asset SHA-256 required")
    pending = raw["pending"]
    require(isinstance(pending, list) and len(pending) <= 30, "pending must be a bounded list")
    for item in pending:
        text(item, "pending dependency and producing role", 2000)
    missing = list(pending)
    if raw["renderer"] == "motion-canvas":
        if raw["version"] == 1:
            missing.append("Legacy Motion Canvas discussion-only plan; issue a new version 2 proposal, never reuse its approval")
        else:
            require(abs(duration * FPS - round(duration * FPS)) < 1e-7, "Motion Canvas duration must end on a frame boundary")
    else:
        require(raw["version"] == 1, "HyperFrames retains version 1")

    def reference(value, label, needed=False):
        if value is None:
            if needed:
                missing.append(label)
            return
        asset_name(value)
        require(value in raw["assets"], f"{label} must name a supplied hashed asset, not a future path")

    char = raw["character"]
    require(isinstance(char, dict) and set(char) == {"framing", "performance", "lip_sync", "body",
            "video", "mouths", "cues", "sync"}, "invalid character fields")
    require(char["framing"] in ("none", "bust", "full"), "invalid framing")
    require(char["performance"] in ("still", "puppet", "animated"), "invalid performance")
    require(char["lip_sync"] in ("off", "cues", "baked"), "invalid lip_sync")
    require(isinstance(char["mouths"], dict) and len(char["mouths"]) <= 16, "mouths must be a bounded map")
    if char["framing"] == "none":
        require(char["performance"] == "still" and char["lip_sync"] == "off"
                and not char["mouths"] and all(char[k] is None for k in ("body", "video", "cues", "sync")),
                "no-character mode cannot retain character performance/assets")
    elif char["performance"] == "animated":
        require(char["body"] is None and not char["mouths"] and char["cues"] is None
                and char["lip_sync"] in ("off", "baked"), "animated uses supplied video, not a rig or sprite cues")
        reference(char["video"], "finished character video", True)
    else:
        require(char["video"] is None and char["lip_sync"] != "baked", "still/puppet uses images")
        reference(char["body"], "approved character body image", True)
    if char["lip_sync"] == "cues":
        reference(char["cues"], "reviewed mouth cues", True)
        if "rest" not in char["mouths"] or len(char["mouths"]) < 2:
            missing.append("aligned mouth images including rest and at least one speaking shape")
        require(char["sync"] is None, "cue mode cannot retain baked sync metadata")
    else:
        require(not char["mouths"] and char["cues"] is None, "unused mouth cues/images")
    if char["lip_sync"] == "baked":
        reference(char["sync"], "character video sync receipt", True)
    else:
        require(char["sync"] is None, "sync receipt is only for baked lip_sync")
    for name, path in char["mouths"].items():
        identifier(name)
        reference(path, "mouth image", True)

    audio = raw["audio"]
    require(isinstance(audio, dict) and set(audio) == {"mode", "master", "script", "receipt", "captions", "timing"},
            "invalid audio fields")
    require(audio["mode"] in ("none", "speech", "mix"), "audio mode must be none, speech or mix")
    if audio["mode"] == "none":
        require(all(audio[k] is None for k in ("master", "script", "receipt", "captions", "timing")),
                "silent mode cannot retain audio inputs")
        require(char["lip_sync"] == "off", "lip_sync requires narration")
    else:
        reference(audio["master"], "finished audio master", True)
        reference(audio["script"], "approved spoken script", True)
    if audio["mode"] == "mix":
        reference(audio["receipt"], "finished Mix receipt", True)
        reference(audio["captions"], "Mix captions")
        reference(audio["timing"], "Mix timing")
    else:
        require(all(audio[k] is None for k in ("receipt", "captions", "timing")), "Mix metadata outside mix mode")

    units = raw["units"]
    require(isinstance(units, list) and 1 <= len(units) <= 24, "1..24 explanation units required")
    previous, ids = 0, set()
    for unit in units:
        require(isinstance(unit, dict) and set(unit) == {"id", "start", "end", "goal", "narration", "before", "change", "after"},
                "invalid explanation unit")
        identifier(unit["id"])
        require(unit["id"] not in ids, "duplicate unit id")
        ids.add(unit["id"])
        start = number(unit["start"], 0, duration, "unit start")
        end = number(unit["end"], start, duration, "unit end")
        require(start == previous and end > start, "units must cover the timeline without gaps/overlap")
        previous = end
        for key in ("goal", "before", "change", "after"):
            text(unit[key], key, 2000)
        text(unit["narration"], "unit narration", 600, empty=audio["mode"] == "none" or audio["script"] is None)
        if audio["mode"] == "none":
            require(not unit["narration"], "silent output cannot silently drop narrated units")
    require(previous == duration, "units must cover the full duration")
    require(isinstance(raw["copy"], list) and 1 <= len(raw["copy"]) <= 160, "1..160 exact copy rows required")
    ids = set()
    for row in raw["copy"]:
        require(isinstance(row, dict) and set(row) == {"id", "text", "start", "end"}, "invalid copy row")
        identifier(row["id"])
        require(row["id"] not in ids, "duplicate copy id")
        ids.add(row["id"])
        text(row["text"], "copy text", 2000)
        start = number(row["start"], 0, duration, "copy start")
        require(number(row["end"], start, duration, "copy end") > start, "copy needs a positive hold")
    samples = raw["samples"]
    require(isinstance(samples, list) and 3 <= len(samples) <= 80, "3..80 proof samples required")
    previous = -1
    for sample in samples:
        require(isinstance(sample, dict) and set(sample) == {"at", "expect"}, "invalid proof sample")
        at = number(sample["at"], 0, duration - 1 / FPS, "sample time")
        require(at > previous, "samples must be ordered and unique")
        previous = at
        text(sample["expect"], "sample expectation", 2000)
    require(samples[0]["at"] == 0 and abs(samples[-1]["at"] - (duration - 1 / FPS)) < 1e-8,
            "first and last visible frame samples required")
    for interval in [*units, *raw["copy"]]:
        require(any(interval["start"] < s["at"] < interval["end"] for s in samples), "sample inside every unit/copy hold")
    if raw["renderer"] == "motion-canvas" and raw["version"] == 2:
        require(all(abs(sample["at"] * FPS - round(sample["at"] * FPS)) < 1e-7 for sample in samples),
                "Motion Canvas sample times must identify exact frames")
        mc.sample_frames(raw)
    return raw, missing


def wav_duration(path):
    with wave.open(str(local(str(path), {".wav"})), "rb") as wav:
        require(wav.getcomptype() == "NONE" and wav.getsampwidth() == 2 and wav.getframerate() == 48000
                and wav.getnchannels() in (1, 2), "audio must be 48 kHz mono/stereo PCM16 WAV")
        return number(wav.getnframes() / 48000, .01, 180, "audio duration")


def input_check(root, plan):
    for name, sha in plan["assets"].items():
        path = local(str(root / name), {Path(name).suffix})
        require(digest(path) == sha, f"asset changed: {name}")
        if path.suffix in (".png", ".jpg", ".jpeg", ".webp"):
            image(path)
        elif path.suffix == ".wav":
            wav_duration(path)
    audio, char = plan["audio"], plan["character"]
    if audio["master"]:
        require(abs(wav_duration(root / audio["master"]) - plan["duration"]) <= 1 / FPS,
                "master duration must match the planned timeline; finish/pad through AudioCreator first")
    if audio["script"]:
        script = local(str(root / audio["script"]), {".txt"}).read_text(encoding="utf-8")
        # Unit boundaries may have paragraph breaks; whitespace inside spoken
        # words must not disappear ("check the" is not "checkthe").
        units = [r"\s+".join(re.escape(word) for word in unit["narration"].split()) for unit in plan["units"]]
        require(re.fullmatch(r"\s*".join(units), script.strip()) is not None,
                "unit narration must preserve the supplied script exactly")
    if audio["mode"] == "mix" and audio["master"] and audio["receipt"]:
        mix_audio.validate_staged_delivery(root / audio["master"], root / audio["receipt"],
            root / audio["captions"] if audio["captions"] else None,
            root / audio["timing"] if audio["timing"] else None, duration_seconds=plan["duration"])
        captions = load(root / audio["captions"])["captions"] if audio["captions"] else []
        declared = {row["id"]: row for row in plan["copy"] if row["id"].startswith("mix-caption-")}
        expected = {f"mix-caption-{i}": {"id": f"mix-caption-{i}", "text": cue["text"],
                    "start": cue["start"], "end": cue["end"]} for i, cue in enumerate(captions, 1)}
        require(declared == expected, "Mix caption copy ledger must match supplied captions before approval")
    if char["body"]:
        image(local(str(root / char["body"]), {".png", ".jpg", ".jpeg", ".webp"}))
    if char["mouths"]:
        sizes = {image(local(str(root / path), {".png"})) for path in char["mouths"].values()}
        require(len(sizes) == 1, "mouth images must share one aligned canvas size")
    if char["video"]:
        path = local(str(root / char["video"]), {".mp4"})
        info = json.loads(command(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-f", "mov",
                                   "-show_streams", "-of", "json", str(path)]))
        videos = [s for s in info["streams"] if s["codec_type"] == "video"]
        require(len(videos) == 1 and videos[0]["codec_name"] == "h264", "character video must be H.264 MP4")
        video = videos[0]
        require(32 <= video["width"] <= 4096 and 32 <= video["height"] <= 4096, "character video dimensions")
        require(float(video.get("duration", 0)) >= plan["duration"] - 1 / FPS, "character video too short")
        require(not any(s.get("rotation", 0) for s in video.get("side_data_list", [])), "rotated video must be prepared first")
    if char["sync"] and audio["master"] and char["video"]:
        sync = load(local(str(root / char["sync"]), {".json"}))
        require(sync == {"master_sha256": plan["assets"][audio["master"]],
                         "video_sha256": plan["assets"][char["video"]]}, "baked sync receipt mismatch")
    if char["cues"] and audio["master"] and "rest" in char["mouths"]:
        mouth_track(root, plan)


def mouth_track(root, plan):
    """Compile supplied reviewed cues, never infer mouth shapes from text or mixed audio."""
    char = plan["character"]
    cues = load(local(str(root / char["cues"]), {".json"}))
    require(isinstance(cues, dict) and set(cues) == {"version", "master_sha256", "voice", "voice_sha256", "offset", "events"},
            "invalid mouth cue fields")
    require(type(cues["version"]) is int and cues["version"] == 1, "mouth cue version")
    require(cues["master_sha256"] == plan["assets"][plan["audio"]["master"]], "mouth cues name a different master")
    voice = asset_name(cues["voice"])
    require(voice in plan["assets"] and cues["voice_sha256"] == plan["assets"][voice], "mouth cues voice hash mismatch")
    duration = wav_duration(root / voice)
    offset = number(cues["offset"], 0, plan["duration"], "voice offset")
    require(offset + duration <= plan["duration"] + 1 / FPS, "voice cue outside timeline")
    require(isinstance(cues["events"], list) and 1 <= len(cues["events"]) <= 4000, "1..4000 supplied mouth events required")
    # HyperFrames coalesces inline body scripts after external scripts. Loading
    # this asset must only declare a function; the scene supplies its own timeline.
    code = ['"use strict";', 'function addExplainerMouthTrack(tl) {']
    boundaries = {}
    previous = 0
    for event in cues["events"]:
        require(isinstance(event, dict) and set(event) == {"start", "end", "mouth"}, "invalid mouth event")
        start = number(event["start"], 0, duration, "mouth start")
        end = number(event["end"], start, duration, "mouth end")
        require(start >= previous and end > start and event["mouth"] in char["mouths"], "overlapping/unknown mouth event")
        previous = end
        boundaries[offset + start] = event["mouth"]
        boundaries[offset + end] = "rest"
    # One write per target/property/time: GSAP visits coincident sets in reverse
    # order on backward seeks. At adjacent cues, the next start wins over rest.
    for at, state in sorted(boundaries.items()):
        for name in char["mouths"]:
            code.append(f'tl.set("#character-mouth-{name}", {{opacity: {int(name == state)}}}, {at!r});')
    return "\n".join([*code, "}", ""])


def propose(args):
    raw = load(local(args.spec, {".json"}))
    require(isinstance(raw, dict) and isinstance(raw.get("assets"), dict), "spec assets must map staged names to local files")
    sources = {asset_name(name): local(path, {Path(name).suffix}) for name, path in raw["assets"].items()}
    require(MOUTH_TRACK not in sources, "mouth-track.js is generated only from approved supplied cues")
    for name in VENDOR_FILES:
        require("assets/" + name not in sources, "GSAP is supplied by this leaf, not replaced by caller")
        if raw.get("renderer") == "hyperframes":
            sources["assets/" + name] = VENDOR / name
    raw["assets"] = {name: digest(path) for name, path in sources.items()}
    plan, missing = model(raw)
    if plan["renderer"] == "motion-canvas" and plan["version"] == 2:
        try:
            mc.identity()
        except (ValueError, OSError, subprocess.SubprocessError):
            plan["pending"].append("Motion Canvas runtime needs maintainer provisioning/repair; no automatic install")
            plan, missing = model(plan)
    out = fresh(args.out)
    require(re.fullmatch(r"proposal-v[1-9][0-9]*", out.name), "use a new numbered proposal-vN directory")
    out.mkdir()
    for name, path in sources.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    input_check(out, plan)
    if not missing and plan["renderer"] == "hyperframes" and plan["character"]["lip_sync"] == "cues":
        track = out / MOUTH_TRACK
        track.write_text(mouth_track(out, plan), encoding="utf-8")
        plan["assets"][MOUTH_TRACK] = digest(track)
    model(plan)
    project_files(out, plan)
    write(out / "plan.json", plan)
    status = "pending-inputs" if missing else "awaiting-approval"
    description = (f"# Explainer video proposal\n\nStatus: {status}\n"
        f"plan_sha256: {digest(out / 'plan.json')}\n\n"
        "This proposal binds the complete plan and staged assets below. Hashes bind bytes, not approver identity.\n\n"
        + "```json\n" + json.dumps(plan, ensure_ascii=False, indent=2) + "\n```\n\n"
        + ("Missing: " + "; ".join(missing) if missing else "Ready for Creator-relayed client approval; no video rendered.") + "\n")
    (out / "proposal.md").write_text(description, encoding="utf-8")
    return {"status": status, "proposal": str(out / "proposal.md"), "approval_sha256": digest(out / "proposal.md"),
            "can_render": not missing, "missing": missing, "media_generation": 0}


def approved_proposal(path, sha):
    path = local(path, {".md"})
    require(path.name == "proposal.md" and re.fullmatch(r"proposal-v[1-9][0-9]*", path.parent.name), "numbered proposal required")
    require(digest(path) == sha, "approved proposal hash mismatch")
    document = path.read_text(encoding="utf-8")
    plan_path = local(str(path.parent / "plan.json"), {".json"})
    require(re.findall(r"^plan_sha256: ([a-f0-9]{64})$", document, re.M) == [digest(plan_path)], "proposal plan hash mismatch")
    plan, missing = model(load(plan_path))
    require(not missing, "pending-inputs proposal cannot authorize production")
    require("Status: awaiting-approval\n" in document, "proposal is not executable")
    input_check(path.parent, plan)
    if plan["renderer"] == "hyperframes" and plan["character"]["lip_sync"] == "cues":
        require(plan["assets"].get(MOUTH_TRACK) == digest(path.parent / MOUTH_TRACK)
                and (path.parent / MOUTH_TRACK).read_text() == mouth_track(path.parent, plan), "mouth track changed")
    return path, plan


def markup_check(root, plan):
    code = local(str(root / "index.html"), {".html"}).read_text(encoding="utf-8")
    markup = Markup()
    markup.feed(code)
    require(len(markup.ids) == len(set(markup.ids)), "duplicate HTML ids")
    require(len(markup.roots) == 1, "one standalone composition root required")
    attrs = markup.roots[0]
    width, height = SIZES[plan["aspect"]]
    require(all(attrs.get(k) == v for k, v in {"id": "root", "data-composition-id": "explainer", "data-start": "0",
            "data-width": str(width), "data-height": str(height), "data-fps": str(FPS)}.items()), "root contract mismatch")
    require(float(attrs.get("data-duration", "nan")) == plan["duration"], "root duration mismatch")
    require("assets/gsap.min.js" in markup.assets and "__timelines" in code, "local GSAP/registered timeline required")
    for path in root.rglob("*"):
        name = path.relative_to(root).as_posix()
        if name.startswith(".hyperframes/") or name == "assets/gsap.min.js" or path.suffix not in (".html", ".css", ".js"):
            continue
        content = path.read_text(encoding="utf-8")
        if path.suffix == ".html":
            parsed = Markup()
            parsed.feed(content)
            content = "\n".join(parsed.code)
        require(not re.search(r"\b(fetch|XMLHttpRequest|WebSocket|EventSource|setTimeout|setInterval|requestAnimationFrame|Date)\s*\(|"
                              r"Math\.random|Date\.now|performance\.now|@import|\.(play|pause|load)\s*\(|"
                              r"\.(currentTime|playbackRate|volume|muted)\s*=|\bvolume\s*:", content), "network/clocks/media control forbidden")
        markup.assets.extend(re.findall(r"url\(\s*['\"]?([^) '\"]+)", content))
    for name in markup.assets:
        require(asset_name(name) in plan["assets"], "unapproved asset reference")
    _copy.copy_check(root, plan)
    for row in plan["copy"]:
        attrs = markup.elements[row["id"]]
        if "data-start" not in attrs and "data-duration" not in attrs:
            require(row["start"] == 0 and row["end"] == plan["duration"], "partial copy hold requires timed clip markup")
        else:
            require("clip" in attrs.get("class", "").split()
                    and float(attrs.get("data-start", "nan")) == row["start"]
                    and float(attrs.get("data-duration", "nan")) == row["end"] - row["start"], "copy timing differs from approved hold")
    audio = plan["audio"]
    media = {attrs.get("id"): (tag, attrs) for tag, attrs in markup.media}
    audios = [(tag, attrs) for tag, attrs in markup.media if tag == "audio"]
    require(len(audios) == (0 if audio["mode"] == "none" else 1), "only the approved master may play")
    for tag, attrs in markup.media:
        if tag == "img":
            continue
        require(set(attrs) <= MEDIA_ATTRS and attrs.get("id"), "unsupported media attributes")
        require(attrs.get("data-start") == "0" and float(attrs.get("data-duration", "nan")) == plan["duration"], "media timing mismatch")
        require(float(attrs.get("data-media-start", "0")) == 0 and attrs.get("data-volume", "1") == "1", "retiming/gain forbidden")
        if tag == "audio":
            require(attrs.get("src") == audio["master"] and "muted" not in attrs, "audio master mismatch")
        else:
            require(attrs.get("id") == "character-body" and attrs.get("src") == plan["character"]["video"]
                    and "muted" in attrs, "only the supplied muted character video is supported")
    char = plan["character"]
    if char["framing"] != "none":
        tag, attrs = media.get("character-body", (None, {}))
        require(tag == ("video" if char["performance"] == "animated" else "img")
                and attrs.get("src") == (char["video"] or char["body"]), "character-body placement missing/mismatched")
    else:
        require("character-body" not in markup.ids, "no-character mode must not add a presenter")
    if char["lip_sync"] == "cues":
        calls = list(re.finditer(r"\baddExplainerMouthTrack\s*\(\s*tl\s*\)", code))
        require(markup.assets.count(MOUTH_TRACK) == 1 and len(calls) == 1
                and code.find(MOUTH_TRACK) < calls[0].start(),
                "load the mouth track declaration before one synchronous addExplainerMouthTrack(tl) call")
        cues = load(root / char["cues"])
        first = cues["events"][0]
        initial = first["mouth"] if cues["offset"] + first["start"] == 0 else "rest"
        for name, path in char["mouths"].items():
            tag, attrs = media.get("character-mouth-" + name, (None, {}))
            require(tag == "img" and attrs.get("src") == path, "mouth image missing/mismatched")
            expected = "1" if name == initial else "0"
            require(re.search(r"(?:^|;)\s*opacity\s*:\s*" + expected + r"\s*(?:;|$)", attrs.get("style", "")),
                    f"mouth initial opacity must be inline: {initial}=1, others=0")
        require((root / MOUTH_TRACK).read_text() == mouth_track(root, plan), "mouth track differs from frozen cues")
    if audio["mode"] == "mix":
        mix_audio.check_caption_markup(root / "index.html", root / audio["captions"] if audio["captions"] else None)


def freeze(args):
    proposal, plan = approved_proposal(args.approved_plan, args.approval_sha256)
    source = Path(args.source)
    files = project_files(source, plan)
    require(not RESERVED & set(files), "reserved source filename")
    require({name: sha for name, sha in files.items() if name.startswith("assets/")} == plan["assets"], "source assets differ from approved inputs")
    input_check(source, plan)
    scene_check(source, plan)
    out = fresh(args.project)
    require(not out.is_relative_to(source) and not out.is_relative_to(proposal.parent), "project must be separate from source/proposal")
    out.mkdir()
    for name in files:
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
    require(project_files(source, plan) == files and project_files(out, plan) == files, "source changed while freezing")
    write(out / "plan.json", plan)
    shutil.copyfile(proposal, out / "approved-proposal.md")
    write(out / "integrity.json", project_files(out, plan))
    return {"project": str(out), "rendered_mp4": False}


def project_model(value):
    root = Path(value)
    plan, missing = model(load(local(str(root / "plan.json"), {".json"})))
    files = project_files(root, plan)
    expected = load(local(str(root / "integrity.json"), {".json"}))
    require({name: sha for name, sha in files.items() if name != "integrity.json"} == expected, "project changed since freeze")
    require(not missing, "project is not executable")
    input_check(root, plan)
    scene_check(root, plan)
    return root, plan


def runtime_identity():
    binary = shutil.which("hyperframes")
    require(binary, "HyperFrames CLI missing; maintainer provisioning required, no automatic install")
    return {"path": str(Path(binary).resolve()), "version": command([binary, "--version"]).strip()}


def selected_runtime(plan):
    return mc.identity() if plan["renderer"] == "motion-canvas" else runtime_identity()


def project_files(root, plan):
    return mc.source_files(root) if plan["renderer"] == "motion-canvas" else source_files(root, version=3)


def scene_check(root, plan):
    if plan["renderer"] == "motion-canvas":
        mc.source_check(root, plan)
    else:
        markup_check(root, plan)


def check(root, plan, out):
    times = [sample["at"] for sample in plan["samples"]]
    hf(root, ["check", "--json", "--at", ",".join(map(str, times))], out / "check.json")
    result = load(out / "check.json")
    contrast = result.get("contrast", {})
    require(result.get("ok") and contrast.get("enabled") and contrast.get("checked", 0) > 0, "check/contrast audit failed or skipped")
    return times


def snapshot(args):
    root, plan = project_model(args.project)
    out = fresh(args.out)
    require(not out.is_relative_to(root), "preview must be outside project")
    out.mkdir()
    runtime = selected_runtime(plan)
    times = [sample["at"] for sample in plan["samples"]]
    if plan["renderer"] == "motion-canvas":
        mc.snapshot(root, plan, out)
    else:
        check(root, plan, out)
        hf(root, ["snapshot", "--at", ",".join(map(str, times)), "--no-end", "--describe", "false", "-o", str(out / "frames")], out / "snapshot.log")
    frames = sorted((out / "frames").glob("*.png"))
    require(len(frames) == len(times) and all(image(frame) == SIZES[plan["aspect"]] for frame in frames), "preview frames count/dimensions")
    project_model(str(root))
    require(runtime == selected_runtime(plan), "runtime changed during preview")
    write(out / "preview.json", {"project": str(root), "integrity": digest(root / "integrity.json"), "runtime": runtime,
        "times": times, "frames": {frame.name: digest(frame) for frame in frames}, "check": digest(out / "check.json")})
    return {"preview": str(out), "preview_sha256": digest(out / "preview.json"), "rendered_mp4": False}


def render(args):
    root, plan = project_model(args.project)
    preview = local(str(Path(args.approved_preview) / "preview.json"), {".json"})
    require(digest(preview) == args.approval_sha256, "approved preview hash mismatch")
    data = load(preview)
    require(data["project"] == str(root) and data["integrity"] == digest(root / "integrity.json"), "preview belongs to another project")
    require(data["runtime"] == selected_runtime(plan), "runtime changed since preview; new preview approval required")
    require(data["times"] == [sample["at"] for sample in plan["samples"]], "preview times changed")
    require(len(data["frames"]) == len(data["times"]), "preview frame count mismatch")
    for name, sha in data["frames"].items():
        require(Path(name).name == name and digest(local(str(preview.parent / "frames" / name), {".png"})) == sha, "preview frame changed")
    require(digest(local(str(preview.parent / "check.json"), {".json"})) == data["check"], "preview check changed")
    out = fresh(args.out)
    require(not out.is_relative_to(root) and not out.is_relative_to(preview.parent), "final must be separate")
    out.mkdir()
    times = [sample["at"] for sample in plan["samples"]]
    movie = out / "explainer.mp4"
    if plan["renderer"] == "motion-canvas":
        mc.render(root, plan, out, preview.parent)
    else:
        check(root, plan, out)
        hf(root, ["render", "--output", str(movie), "--fps", str(FPS), "--workers", "1", "--strict", "--no-best-effort", "--quiet"], out / "render.log")
    info = json.loads(command(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(movie)]))
    videos = [s for s in info["streams"] if s["codec_type"] == "video"]
    require(len(videos) == 1, "one final video stream required")
    video = videos[0]
    require((video["width"], video["height"]) == SIZES[plan["aspect"]] and video["codec_name"] == "h264"
            and video["pix_fmt"] == "yuv420p" and Fraction(video["avg_frame_rate"]) == FPS, "final video format mismatch")
    require(abs(float(info["format"]["duration"]) - plan["duration"]) <= .1, "final duration mismatch")
    audios = [s for s in info["streams"] if s["codec_type"] == "audio"]
    require(len(audios) == (0 if plan["audio"]["mode"] == "none" else 1), "final audio stream mismatch")
    audio_metrics = None
    if audios:
        audio_metrics = mix_audio.measure_audio(movie)
        require(audio_metrics["input_tp"] is not None and audio_metrics["input_tp"] < 0, "final audio silent/unmeasured/clipping")
        require(abs(float(audios[0].get("duration", "nan")) - plan["duration"]) <= .1, "final audio duration mismatch")
        if plan["audio"]["mode"] == "mix":
            receipt = load(root / plan["audio"]["receipt"])
            mix_audio.check_final_audio(audio_metrics, receipt, info["streams"], plan["duration"])
    command(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(movie), "-f", "null", "-"], timeout=600)
    (out / "review").mkdir()
    for i, at in enumerate(times):
        command(["ffmpeg", "-nostdin", "-v", "error", "-n", "-ss", str(at), "-i", str(movie), "-frames:v", "1", str(out / "review" / f"{i:02}.png")])
    frames = sorted((out / "review").glob("*.png"))
    require(len(frames) == len(times) and all(image(frame) == SIZES[plan["aspect"]] for frame in frames),
            "review frame extraction incomplete or dimensions mismatch")
    shutil.copyfile(out / "review/00.png", out / "poster.png")
    project_model(str(root))
    require(data["runtime"] == selected_runtime(plan), "runtime changed during render")
    result = {"mp4": str(movie), "decoded": True, "duration": float(info["format"]["duration"]),
              "width": video["width"], "height": video["height"], "fps": FPS, "audio": audio_metrics,
              "semantic_review": "pending", "lip_sync": "unverified" if plan["character"]["lip_sync"] != "off" else "not-requested",
              "temporal_review": "sampled only", "listening": "unverified", "media_generation": 0}
    result["renderer"] = plan["renderer"]
    result["contrast"] = load(out / "check.json").get("contrast", {"enabled": False, "reason": "not reported"})
    write(out / "qa.json", result)
    (out / "qa.md").write_text("# Explainer QA\n\nFull decode and structural checks passed.\n"
        "Learning outcome, factual accuracy, character fidelity, speech/viseme quality and listening remain unverified.\n"
        "Compare decoded frames to every unit and approved sample; append findings and optional-reference gaps.\n"
        + ("Contrast was not automatically checked; visual contrast/readability review is required.\n"
           if not result["contrast"].get("enabled") else ""), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    p = subs.add_parser("propose")
    p.add_argument("--spec", required=True)
    p.add_argument("--out", required=True)
    p = subs.add_parser("freeze")
    for name in ("approved-plan", "approval-sha256", "source", "project"):
        p.add_argument("--" + name, required=True)
    for name in ("snapshot", "render"):
        p = subs.add_parser(name)
        p.add_argument("--project", required=True)
        p.add_argument("--out", required=True)
        if name == "render":
            p.add_argument("--approved-preview", required=True)
            p.add_argument("--approval-sha256", required=True)
    args = parser.parse_args()
    try:
        result = globals()[args.command](args)
        print("RESULT: " + json.dumps(result, ensure_ascii=True))
    except (ValueError, KeyError, TypeError, OSError, wave.Error, subprocess.SubprocessError) as error:
        print("RESULT: " + json.dumps({"status": "FAIL", "error": str(error), "evidence": getattr(error, "evidence", None)}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
