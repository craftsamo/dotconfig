#!/usr/bin/env python3
"""Freeze and verify an authored UI tour. Never generate its layout or actions.

tour.py remains the direct entry for persisted v1 screenshot projects. Only its
small IO/media primitives are reused here; no legacy model or renderer dispatch.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from fractions import Fraction
from html.parser import HTMLParser
from pathlib import Path

from tour import (CANVAS, VENDOR, command, digest, fresh, hf, image, load,
                  local, number, require, text, write)


def form_model(raw):
    require(isinstance(raw, dict), "form must be an object")
    allowed = {"what_for", "audience", "reference", "flow", "fidelity", "frame",
               "style", "background", "backdrop", "intro", "outro", "duration",
               "destination", "preview", "note", "screen_mode", "source", "target",
               "start_state", "approved_plan", "approval_sha256", "source_sha256"}
    require(set(raw) <= allowed, "unknown form field (v1 forms use tour.py)")
    form = {"fidelity": "faithful", "frame": "macos", "style": "flat",
            "background": "light", "intro": "title-reveal", "outro": "result-hold",
            "duration": 20, "destination": "landscape", "preview": "yes", **raw}
    for key in ("what_for", "audience"):
        text(form.get(key), key, 1000)
    for key in ("reference", "flow", "frame", "style", "background", "intro", "outro", "note"):
        if key in form:
            text(form[key], key, 4000)
    require(form["fidelity"] in ("faithful", "simplified"), "fidelity must be faithful or simplified")
    require(form["destination"] in CANVAS, "destination must be landscape or portrait")
    require(form["preview"] in ("yes", "no"), "preview must be yes or no")
    number(form["duration"], 1, 60, "duration")
    if "backdrop" in form:
        text(form["backdrop"], "backdrop path", 4000)
    mode = form.get("screen_mode", "recreate")
    require(mode in ("recreate", "supplied", "capture"), "screen_mode must be recreate, supplied or capture")
    for key in ("source", "target", "start_state", "approved_plan", "approval_sha256", "source_sha256"):
        if key in form:
            text(form[key], key, 4000)
    if mode == "supplied":
        require("source" in form and "source_sha256" in form and "target" not in form, "supplied needs source and source_sha256, not an operation target")
    if mode == "capture":
        require(all(k in form for k in ("target", "start_state", "source")), "capture needs target, start_state and planned source manifest path")
    if mode == "recreate":
        require("source" not in form and "target" not in form, "recreate uses reference, not source/target")
    # A custom direction is deliberately neither normalized nor classified.
    return form


def contract_model(raw, form):
    require(isinstance(raw, dict) and set(raw) == {"duration", "intro", "outro", "fidelity_note", "samples"},
            "contract needs duration, intro, outro, fidelity_note and samples")
    total = number(raw["duration"], 1, 60, "contract duration")
    require(total == form["duration"], "contract duration differs from approved form")
    text(raw["fidelity_note"], "fidelity_note", 4000)
    for key in ("intro", "outro"):
        beat = raw[key]
        require(isinstance(beat, dict) and set(beat) == {"direction", "start", "end", "description"}, "invalid opening/closing beat")
        require(beat["direction"] == form[key], f"{key}: direction changed; no silent fallback")
        start = number(beat["start"], 0, total, key + " start")
        end = number(beat["end"], start, total, key + " end")
        if form[key] == "none":
            require(start == end == (0 if key == "intro" else total) and beat["description"] == "",
                    "none must be explicit and have no beat")
        else:
            text(beat["description"], key + " concrete beat", 2000)
            require(end > start and (start == 0 if key == "intro" else end == total),
                    "intro/outro must occupy their actual boundary")
    require(raw["intro"]["end"] < raw["outro"]["start"], "leave time for the task between intro/outro")
    samples = raw["samples"]
    require(isinstance(samples, list) and 3 <= len(samples) <= 40, "3..40 proof samples required")
    previous = -1
    for sample in samples:
        require(isinstance(sample, dict) and set(sample) == {"at", "expect"}, "sample needs at and expect")
        at = number(sample["at"], 0, total - 1 / 30, "sample time")
        require(at > previous, "sample times must be unique and ordered")
        text(sample["expect"], "visible expectation", 2000)
        previous = at
    require(samples[0]["at"] == 0 and samples[-1]["at"] >= total - .1,
            "samples must include first and last visible frames")
    for key in ("intro", "outro"):
        beat = raw[key]
        if form[key] != "none":
            require(any(beat["start"] < s["at"] < beat["end"] for s in samples),
                    f"sample the {key} transition/hold")
    return raw


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.roots = []
        self.assets = []
        self.code = []
        self.code_tag = None
        self.media = []
        self.ids = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag in ("video", "audio", "img"):
            self.media.append((tag, attrs))
        if tag in ("script", "style"):
            self.code_tag = tag
        require(tag not in ("iframe", "object", "embed", "base", "form"), "active embeds/navigation forbidden")
        require(not any(k.startswith("on") for k in attrs), "event-driven authoring forbidden")
        require(not (tag == "meta" and attrs.get("http-equiv", "").lower() == "refresh"), "navigation forbidden")
        if "data-composition-id" in attrs:
            self.roots.append(attrs)
        for key in ("src", "href", "poster"):
            if key in attrs:
                self.assets.append(attrs[key])

    def handle_endtag(self, tag):
        if tag == self.code_tag:
            self.code_tag = None

    def handle_data(self, data):
        if self.code_tag:
            self.code.append(data)


def source_files(root, version=2):
    require(root.is_absolute() and root.is_dir(), "source/project directory must exist and be absolute")
    require(".." not in root.parts, "parent traversal forbidden")
    require(not any(p.is_symlink() for p in (root, *root.parents)), "symlink directory forbidden")
    files = {}
    for p in root.rglob("*"):
        require(not p.is_symlink(), "symlink in source/project forbidden")
        name = p.relative_to(root).as_posix()
        # HyperFrames owns only this cache, never authored inputs.
        if name.split("/")[0] == ".hyperframes":
            continue
        if p.is_dir():
            continue
        suffixes = {".html", ".css", ".js", ".json", ".md", ".txt", ".png", ".jpg", ".jpeg", ".webp", ".woff2", ".wav"}
        local(str(p), suffixes | ({".mp4"} if version == 3 else set()))
        files[name] = digest(p)
    payload = [n for n in files if n not in ("form.json", "contract.json", "integrity.json")]
    require(len(payload) <= 200 and sum((root / n).stat().st_size for n in payload) <= 128_000_000,
            "source bundle exceeds 200 files / 128 MB")
    return files


def markup_check(root, form):
    code = local(str(root / "index.html"), {".html"}).read_text(encoding="utf-8")
    markup = Markup()
    markup.feed(code)
    require(len(markup.roots) == 1, "one standalone composition root required")
    attrs = markup.roots[0]
    W, H = CANVAS[form["destination"]]
    require(attrs.get("data-composition-id") == "tour" and attrs.get("data-start") == "0", "root id tour and start 0 required")
    require((attrs.get("data-width"), attrs.get("data-height"), attrs.get("data-fps")) == (str(W), str(H), "30"), "root dimensions/fps mismatch")
    require(float(attrs.get("data-duration", "nan")) == form["duration"], "root duration mismatch")
    require("assets/gsap.min.js" in markup.assets and "__timelines" in code, "local GSAP and registered timeline required")
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
            match = re.search(r"\b(fetch|XMLHttpRequest|WebSocket|EventSource|setTimeout|setInterval|requestAnimationFrame|Date)\s*\(|Math\.random|Date\.now|performance\.now|@import", content)
            require(not match, f"{name}: network/clocks/unseekable animation forbidden: {match.group() if match else ''}")
            if form.get("screen_mode") in ("supplied", "capture"):
                require(not re.search(r"\.(play|pause|load)\s*\(|\.currentTime\s*=|\.playbackRate\s*=", content), "HyperFrames owns media playback/seeking")
                require(not re.search(r"\bvolume\s*:|\.(volume|muted)\s*=", content), "footage audio automation requires a separately approved finishing path")
            for url in re.findall(r"url\(\s*['\"]?([^)'\"]+)", content):
                markup.assets.append(url)
    for name in markup.assets:
        require(isinstance(name, str) and re.fullmatch(r"assets/[a-zA-Z0-9_./-]+", name)
                and ".." not in Path(name).parts, "assets must be local under assets/; no URL capture")
        local(str(root / name), {Path(name).suffix})
    require(digest(root / "assets/gsap.min.js") == load(VENDOR / "gsap-provenance.json")["sha256"], "GSAP vendor hash mismatch")
    if form.get("screen_mode") in ("supplied", "capture"):
        footage_check(root, form, markup)
    elif form.get("screen_mode") == "recreate":
        require(not any(t == "video" for t, _ in markup.media), "recreate cannot silently use supplied/captured footage")


def footage_check(root, form, markup):
    from footage import probe, sha256
    require(len(markup.ids) == len(set(markup.ids)), "duplicate element id")
    data = load(local(str(root / "assets/footage/media.json"), {".json"}))
    require(data.get("version") == 1 and isinstance(data.get("clips"), list) and data["clips"], "prepared footage manifest required")
    expected_media = set()
    expected_audio = set()
    for clip in data["clips"]:
        name = clip["path"]
        require(Path(name).name == name, "invalid prepared asset path")
        path = local(str(root / "assets/footage" / name), {".mp4", ".png", ".jpg", ".jpeg", ".webp"})
        require(sha256(path) == clip["sha256"], "prepared source hash mismatch")
        info = probe(path)
        require(info["kind"] == clip["kind"], "source kind mismatch")
        start = number(clip["timeline_start"], 0, form["duration"], "timeline start")
        duration = number(clip["duration"], .1, form["duration"] - start, "footage duration")
        require(clip["media_start"] == 0 and clip["audio"] in ("keep", "mute"), "invalid prepared media/audio policy")
        require(duration <= info.get("duration", duration) + .05, "prepared source range exceeds duration")
        src = "assets/footage/" + name
        tag = "video" if info["kind"] == "video" else "img"
        expected_media.add((tag, clip["id"]))
        matches = [a for t, a in markup.media if t == tag and a.get("id") == clip["id"]]
        require(len(matches) == 1, "footage must remain actual media, never screenshot substitution")
        def timing(attrs):
            require(set(attrs) <= {"id", "class", "src", "muted", "playsinline", "data-start", "data-duration",
                                  "data-media-start", "data-track-index", "style", "preload", "data-volume"},
                    "unsupported footage attributes (no autoplay, loop or retiming)")
            require(attrs.get("src") == src and float(attrs.get("data-start", "nan")) == start
                    and float(attrs.get("data-duration", "nan")) == duration, "source-to-timeline mapping mismatch")
            if tag == "video":
                require(float(attrs.get("data-media-start", "nan")) == 0, "prepared media start must be zero")
        timing(matches[0])
        if tag == "video":
            require("muted" in matches[0] and "playsinline" in matches[0], "video must be muted and inline")
            audio = [a for t, a in markup.media if t == "audio" and a.get("src") == src]
            require(len(audio) == (1 if clip["audio"] == "keep" else 0), "audio policy silently changed")
            if audio:
                expected_audio.add((audio[0].get("id"), src))
                require(info["audio"] and audio[0].get("id"), "kept audio needs stream and unique id")
                require("muted" not in audio[0] and float(audio[0].get("data-volume", "1")) == 1,
                        "keep must retain source audio at unity gain")
                timing(audio[0])
    require({(t, a.get("id")) for t, a in markup.media if t == "video"} ==
            {entry for entry in expected_media if entry[0] == "video"}, "unmapped video")
    require({(a.get("id"), a.get("src")) for t, a in markup.media if t == "audio" and a.get("src", "").endswith(".mp4")} == expected_audio,
            "unmapped footage audio")


def freeze(args):
    form = form_model(load(local(args.form, {".json"})))
    contract = contract_model(load(local(args.contract, {".json"})), form)
    source = Path(args.source)
    version = 3 if "screen_mode" in form else 2
    if version == 3:
        from approval import form_approval
        approval = form_approval(form)
        if form["screen_mode"] in ("supplied", "capture"):
            from footage import media_path, sha256
            source_manifest = local(form["source"], {".json"})
            manifest = load(source_manifest)
            if form["screen_mode"] == "supplied":
                require(digest(source_manifest) == form["source_sha256"], "supplied manifest changed since approval")
            else:
                receipt = load(local(manifest.get("capture_receipt"), {".json"}))
                require(receipt.get("status") == "complete" and receipt.get("approval_sha256") == approval.get("acquisition_sha256", form["approval_sha256"]), "completed approved capture receipt required")
                closed = load(local(str(Path(manifest["capture_receipt"]).parent / "closed.json"), {".json"}))
                require(closed.get("status") == "complete", "capture session cleanup not complete")
                require(all(c["path"] == receipt["raw"] and c["sha256"] == receipt["sha256"] for c in manifest["clips"]), "capture source differs from receipt")
            cooked = load(local(str(source / "assets/footage/media.json"), {".json"}))["clips"]
            require(len(cooked) == len(manifest["clips"]), "prepared clip count differs from source")
            for original, prepared in zip(manifest["clips"], cooked):
                require(sha256(media_path(original["path"])) == original["sha256"] == prepared["raw_sha256"], "raw source integrity mismatch")
                require(all(original[k] == prepared[k] for k in ("id", "source_start", "duration", "timeline_start", "audio")), "prepared source mapping differs from approved manifest")
    files = source_files(source, version)
    require(not {"integrity.json", "form.json", "contract.json"} & files.keys(), "reserved source filenames")
    markup_check(source, form)
    if "backdrop" in form:
        backdrop = local(form["backdrop"], {".png", ".jpg", ".jpeg", ".webp"})
        image(backdrop)
        require(digest(backdrop) in files.values(), "copy original backdrop into source assets before freeze")
    project = fresh(args.project)
    require(".." not in project.parts, "parent traversal forbidden")
    require(not project.is_relative_to(source), "project must be outside authoring source")
    project.mkdir()
    for name in files:
        dest = project / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, dest)
    write(project / "form.json", form)
    write(project / "contract.json", contract)
    write(project / "integrity.json", {"version": version, "files": source_files(project, version)})
    return {"project": str(project), "duration": form["duration"], "next": "snapshot"}


def project_model(value):
    project = Path(value)
    saved = load(local(str(project / "integrity.json"), {".json"}))
    require(isinstance(saved, dict) and saved.get("version") in (2, 3), "authored v2/v3 project required; v1 uses tour.py")
    actual = source_files(project, saved["version"])
    actual.pop("integrity.json")
    require(actual == saved.get("files"), "project changed since freeze; revise in fresh source/project")
    form = form_model(load(project / "form.json"))
    require(saved["version"] == 3 or "screen_mode" not in form, "v2 cannot reinterpret a screen mode")
    contract = contract_model(load(project / "contract.json"), form)
    markup_check(project, form)
    return project, form, contract


def output_dir(value, project):
    out = fresh(value)
    require(".." not in out.parts, "parent traversal forbidden")
    require(not out.is_relative_to(project), "output must be outside frozen project")
    return out


def check(project, contract, out):
    times = [s["at"] for s in contract["samples"]]
    hf(project, ["check", "--json", "--at", ",".join(map(str, times))], out / "check.json")
    result = load(out / "check.json")
    contrast = result.get("contrast", {})
    require(result.get("ok") and contrast.get("enabled") and contrast.get("checked", 0) > 0,
            "check/contrast audit failed or skipped")
    return times


def snapshot(args):
    project, form, contract = project_model(args.project)
    out = output_dir(args.out, project)
    out.mkdir()
    times = check(project, contract, out)
    hf(project, ["snapshot", "--at", ",".join(map(str, times)), "--no-end", "--describe", "false", "-o", str(out / "frames")], out / "snapshot.log")
    frames = sorted((out / "frames").glob("*.png"))
    require(len(frames) == len(times), "snapshot count mismatch")
    for frame in frames:
        require(image(frame) == CANVAS[form["destination"]], "snapshot dimensions mismatch")
    project_model(str(project))
    write(out / "preview.json", {"project": str(project), "integrity": digest(project / "integrity.json"),
                                "times": times, "frames": {p.name: digest(p) for p in frames},
                                "check": digest(out / "check.json")})
    return {"preview": str(out), "frames": len(frames), "rendered_mp4": False}


def approved_preview(value, project, contract):
    preview = local(str(Path(value) / "preview.json"), {".json"})
    data = load(preview)
    require(data.get("project") == str(project) and data.get("integrity") == digest(project / "integrity.json"), "approved preview belongs to another project")
    require(data.get("times") == [s["at"] for s in contract["samples"]], "approved sample times changed")
    frames = data.get("frames")
    require(isinstance(frames, dict) and len(frames) == len(contract["samples"]), "approved preview lacks proof frames")
    for name, expected in frames.items():
        require(Path(name).name == name, "invalid preview frame path")
        require(digest(local(str(preview.parent / "frames" / name), {".png"})) == expected, "approved preview frame changed")
    require(digest(local(str(preview.parent / "check.json"), {".json"})) == data.get("check"), "approved check changed")


def render(args):
    project, form, contract = project_model(args.project)
    require(form["preview"] == "no" or args.approved_preview, "preview=yes requires --approved-preview after client approval")
    if args.approved_preview:
        approved_preview(args.approved_preview, project, contract)
    out = output_dir(args.out, project)
    out.mkdir()
    times = check(project, contract, out)
    movie = out / "tour.mp4"
    hf(project, ["render", "--output", str(movie), "--fps", "30", "--workers", "1", "--strict", "--no-best-effort", "--quiet"], out / "render.log")
    info = json.loads(command(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(movie)]))
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    if form.get("screen_mode") in ("supplied", "capture"):
        clips = load(project / "assets/footage/media.json")["clips"]
        if any(c["audio"] == "keep" for c in clips):
            require(any(s["codec_type"] == "audio" for s in info["streams"]), "kept source audio missing in final render")
    require((video["width"], video["height"]) == CANVAS[form["destination"]], "render dimensions mismatch")
    require(video["codec_name"] == "h264" and video["pix_fmt"] == "yuv420p" and Fraction(video["avg_frame_rate"]) == 30, "render format mismatch")
    require(abs(float(info["format"]["duration"]) - form["duration"]) <= .1, "render duration mismatch")
    command(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(movie), "-f", "null", "-"], timeout=300)
    (out / "review").mkdir()
    for i, at in enumerate(times):
        command(["ffmpeg", "-nostdin", "-v", "error", "-n", "-ss", str(at), "-i", str(movie), "-frames:v", "1", str(out / "review" / f"{i:02}.png")])
    shutil.copyfile(out / "review" / f"{len(times)-1:02}.png", out / "poster.png")
    project_model(str(project))
    report = {"project": str(project), "mp4": str(movie), "decoded": True, "bytes": movie.stat().st_size,
              "duration": float(info["format"]["duration"]), "width": video["width"], "height": video["height"],
              "fps": 30, "samples": contract["samples"], "intro": contract["intro"], "outro": contract["outro"],
              "semantic_review": "pending visual comparison to approved form and sample expectations",
              "temporal_review": "sampled only", "media_generation": 0}
    write(out / "qa.json", report)
    (out / "qa.md").write_text("# Authored Tour QA\n\nLocal full decode passed. See check.json and qa.json.\nSemantic fidelity, pointer contact, Japanese text fit and transitions require visual review.\nSamples are not a complete temporal or listening verdict.\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    p = subs.add_parser("freeze")
    for key in ("form", "contract", "source", "project"):
        p.add_argument("--" + key, required=True)
    for name in ("snapshot", "render"):
        p = subs.add_parser(name)
        p.add_argument("--project", required=True)
        p.add_argument("--out", required=True)
        if name == "render":
            p.add_argument("--approved-preview")
    args = parser.parse_args()
    try:
        print("RESULT: " + json.dumps(globals()[args.command](args)))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"authored tour: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
