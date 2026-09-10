#!/usr/bin/env python3
"""Local screenshot walkthroughs. No capture, generation, uploads or runtime edits."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import wave
from fractions import Fraction
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
VENDOR = HERE.parent / "assets"
FRAMES = ("auto", "browser", "macos", "ios", "android", "none")
STYLES = {"flat": (0.80, 0), "glass": (0.65, 16), "outline": (0.90, 0)}
CANVAS = {"landscape": (1280, 720), "portrait": (720, 1280)}
Image.MAX_IMAGE_PIXELS = 16_000_000


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value, low, high, name):
    require(type(value) in (int, float) and math.isfinite(value), f"{name}: finite number required")
    require(low <= value <= high, f"{name}: must be within {low}..{high}")
    return value


def text(value, name, limit=80, empty=False):
    require(isinstance(value, str) and (empty or value.strip()) and len(value) <= limit,
            f"{name}: text required, maximum {limit} characters")
    require(not any(ord(c) < 32 for c in value), f"{name}: control characters forbidden")
    return value


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9-]{0,47}", value),
            "id/slug: use lowercase ASCII letters, digits and hyphens, starting with a letter (1-48)")
    return value


def local(value, suffixes):
    require(isinstance(value, str) and not any(c in value for c in ("\x00", "\n", "://")),
            "local path required")
    p = Path(value).expanduser()
    require(p.is_absolute(), "local path must be absolute")
    require(not any(part.is_symlink() for part in (p, *p.parents)), "symlink inputs/outputs forbidden")
    require(p.is_file() and p.suffix.lower() in suffixes, "missing local file or unsupported extension")
    require(p.stat().st_size <= 64_000_000, "input exceeds 64 MB")
    return p


def fresh(value):
    p = Path(value).expanduser()
    require(p.is_absolute() and p.parent.is_dir(), "output needs an existing absolute parent directory")
    require(not any(part.is_symlink() for part in (p, *p.parents)), "symlink inputs/outputs forbidden")
    require(not p.exists(), "output must not exist; existing evidence is never overwritten")
    return p


def load(path):
    require(path.stat().st_size <= 1_000_000, "JSON exceeds 1 MB")
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, f"duplicate JSON key: {k}")
            result[k] = v
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False, "nonfinite JSON number"))


def write(path, value):
    with path.open("x", encoding="utf-8") as f:
        f.write(json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, cwd=None, binary=False, timeout=180):
    env = {**os.environ, "DO_NOT_TRACK": "1", "HYPERFRAMES_TELEMETRY_DISABLED": "1"}
    proc = subprocess.run(args, cwd=cwd, env=env, capture_output=True,
                          text=not binary, timeout=timeout)
    if proc.returncode != 0:
        error = ValueError(f"{Path(args[0]).name} failed (exit {proc.returncode})")
        error.evidence = (proc.stdout + proc.stderr) if not binary else "binary command failed"
        raise error
    return proc.stdout


def image(path):
    with Image.open(path) as im:
        require(im.format in ("PNG", "JPEG", "WEBP") and getattr(im, "n_frames", 1) == 1,
                "only static PNG/JPEG/WebP images are supported")
        w, h = im.size
        require(32 <= w <= 8192 and 32 <= h <= 8192 and w * h <= 16_000_000,
                "image pixel bounds: sides 32..8192, at most 16 million pixels")
        require(im.getexif().get(274, 1) == 1, "apply EXIF rotation before supplying screenshot coordinates")
        im.load()
        return w, h


def rectangle(value, w, h):
    require(isinstance(value, list) and len(value) == 4, "target must be [x,y,width,height]")
    x, y, tw, th = [number(v, 0, 8192, "target") for v in value]
    require(tw > 0 and th > 0 and x + tw <= w and y + th <= h, "target outside image bounds")
    return [x, y, tw, th]


def ocr_candidates(tsv, anchor):
    lines = {}
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        if row.get("level") == "5" and (row.get("text") or "").strip():
            key = tuple(row[k] for k in ("page_num", "block_num", "par_num", "line_num"))
            lines.setdefault(key, []).append(row)
    matches, candidates = [], []
    needle = re.sub(r"\s+", "", anchor).casefold()
    for rows in lines.values():
        candidates.append(" ".join(r["text"] for r in rows))
        for start in range(len(rows)):
            joined = ""
            for end in range(start + 1, len(rows) + 1):
                joined += re.sub(r"\s+", "", rows[end - 1]["text"]).casefold()
                if len(joined) > len(needle):
                    break
                selected = rows[start:end]
                if joined != needle:
                    continue
                x = min(int(r["left"]) for r in selected)
                y = min(int(r["top"]) for r in selected)
                right = max(int(r["left"]) + int(r["width"]) for r in selected)
                bottom = max(int(r["top"]) + int(r["height"]) for r in selected)
                matches.append([x, y, right - x, bottom - y])
    return matches, candidates[:30]


def resolve_target(value, path, w, h):
    if isinstance(value, list):
        return rectangle(value, w, h), None
    require(isinstance(value, dict) and set(value) <= {"text", "language"},
            "target needs a rectangle or {text, language: eng|jpn|eng+jpn}")
    anchor = text(value.get("text"), "text anchor")
    lang = value.get("language", "jpn" if re.search(r"[\u3040-\u9fff]", anchor) else "eng")
    require(lang in ("eng", "jpn", "eng+jpn"), "OCR language must be eng, jpn or eng+jpn")
    require(shutil.which("tesseract"), "install tesseract or supply an explicit rectangle")
    languages = command(["tesseract", "--list-langs"]).splitlines()
    missing = set(lang.split("+")) - set(languages)
    require(not missing, f"OCR language missing: {sorted(missing)}; ask maintainer to install language data or supply rectangle; no automatic install")
    tsv = command(["tesseract", str(path), "stdout", "-l", lang, "tsv"])
    matches, candidates = ocr_candidates(tsv, anchor)
    require(len(matches) == 1, f"OCR anchor has {len(matches)} matches; candidates={candidates}; rectangles={matches}; supply explicit target")
    return rectangle(matches[0], w, h), tsv


def narration(path):
    # Force WAV decoding: a renamed playlist must never trigger ffmpeg networking.
    with wave.open(str(path), "rb") as wav:
        require(wav.getcomptype() == "NONE" and wav.getnchannels() in (1, 2), "track must be mono/stereo PCM WAV")
        number(wav.getframerate(), 8000, 192000, "WAV sample rate")
        number(wav.getnframes() / wav.getframerate(), .01, 58, "WAV duration")
    side = local(str(path.with_suffix(".words.json")), {".json"})
    data = load(side)
    require(isinstance(data, dict), "words sidecar must be an object")
    pcm = command(["ffmpeg", "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe", "-f", "wav", "-i", str(path), "-t", "61",
                   "-map", "0:a:0", "-ac", "1", "-ar", "48000", "-f", "s16le", "-"], binary=True)
    duration = len(pcm) / 96000
    number(duration, 0.01, 58, "track duration")
    require(data.get("file") == path.name, "words sidecar names a different WAV")
    require(abs(number(data.get("duration"), 0.01, 60, "sidecar duration") - duration) <= 0.15,
            "words sidecar duration mismatch")
    require(data.get("pcm_sha256") == hashlib.sha256(pcm).hexdigest(), "words sidecar PCM hash mismatch or missing")
    for field, key in (("words", "word"), ("captions", "text"), ("segments", "text")):
        items = data.get(field, [])
        require(isinstance(items, list), "sidecar intervals must be lists")
        previous = 0
        for item in items:
            require(isinstance(item, dict), "sidecar interval must be object")
            text(item.get(key), key, 600)
            start = number(item.get("start"), 0, duration, "interval start")
            end = number(item.get("end"), 0, duration, "interval end")
            require(start >= previous and end > start, "sidecar intervals overlap or are out of order")
            previous = end
    require(data.get("words") and data.get("captions"), "current audio-creator words and captions required")
    return duration, data, side


def geometry(w, h, W, H, frame, target=None, max_zoom=2):
    number(max_zoom, 1, 2, "max_zoom")
    bar = {"browser": 36, "macos": 30, "ios": 32, "android": 26, "none": 0}[frame]
    bottom = 20 if frame in ("ios", "android") else 0
    fit = min((W - 112) / w, (H - 224 - bar - bottom) / h)
    sw, sh = w * fit, h * fit
    require(sw >= 120 and sh >= 120, "screenshot aspect produces an unreadably narrow stage; crop input explicitly")
    left, top = (W - sw) / 2, (H - sh - bar - bottom) / 2 + bar
    result = {"stage": [left, top, sw, sh], "bar": bar, "bottom": bottom, "fit": fit}
    if target:
        x, y, tw, th = target
        scale = max(1, min(max_zoom, 1.3 / fit, sw * .75 / (tw * fit), sh * .65 / (th * fit)))
        cx, cy = (x + tw / 2) * fit, (y + th / 2) * fit
        tx = min(0, max(sw - sw * scale, sw / 2 - cx * scale))
        ty = min(0, max(sh - sh * scale, sh / 2 - cy * scale))
        result.update(punch=[scale, tx, ty], cursor=[left + cx * scale + tx, top + cy * scale + ty],
                      target_root=[left + x * fit * scale + tx, top + y * fit * scale + ty,
                                   tw * fit * scale, th * fit * scale])
    return result


def scaffold(args):
    form_path = local(args.form, {".json"})
    form = load(form_path)
    require(isinstance(form, dict), "form must be an object")
    require(set(form) <= {"task", "app", "steps", "frame", "style", "background", "backdrop", "accent", "destination", "preview", "slug", "note", "max_zoom"}, "unknown form field")
    max_zoom = number(form.get("max_zoom", 2), 1, 2, "max_zoom")
    text(form.get("task"), "task", 60)
    text(form.get("app", ""), "app", 40, True)
    text(form.get("note", ""), "note", 1000, True)
    slug = identifier(form.get("slug", "tour"))
    style = form.get("style")
    require(style in STYLES, "style must be flat, glass or outline")
    frame = form.get("frame", "auto")
    require(frame in FRAMES, "invalid frame")
    destination = form.get("destination", "landscape")
    require(destination in CANVAS, "destination must be landscape or portrait")
    require(form.get("preview", "yes") in ("yes", "no"), "preview must be yes or no")
    background = {"light": "#f2f4f8", "dark": "#101827"}.get(form.get("background", "light"), form.get("background"))
    accent = form.get("accent", "#265ee8")
    for color in (background, accent):
        require(isinstance(color, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", color), "colors must be six-digit hex")
    manifest_path = local(form.get("steps"), {".json"})
    manifest = load(manifest_path)
    require(isinstance(manifest, dict) and set(manifest) == {"steps"}, "manifest contains only steps; task/app belong in form")
    raw = manifest["steps"]
    require(isinstance(raw, list) and 2 <= len(raw) <= 16, "steps: 1-15 actions plus final done screen required")
    W, H = CANVAS[destination]
    steps, sources, evidence, used = [], {}, {}, set()
    total = 2.5
    for i, s in enumerate(raw):
        require(isinstance(s, dict) and set(s) <= {"id", "role", "image", "target", "action", "typed", "label", "duration", "track"}, "unknown or invalid step field")
        sid = identifier(s.get("id", f"s{i+1}"))
        require(sid not in used, "duplicate step id")
        used.add(sid)
        done = i == len(raw) - 1
        require(s.get("role", "step") == ("done" if done else "step"), "only the last step must have role done")
        src = local(s.get("image"), {".png", ".jpg", ".jpeg", ".webp"})
        w, h = image(src)
        sources[f"assets/screen-{sid}.png"] = src
        resolved_frame = ("browser" if w >= h else "ios") if frame == "auto" else frame
        if steps:
            require((w, h) == (steps[0]["iw"], steps[0]["ih"]), "all screenshots must have identical pixel dimensions")
        action = s.get("action", "none" if done else "click")
        require(action in ("click", "type", "none"), "invalid action")
        require(not done or (action == "none" and "target" not in s and "typed" not in s), "done screen has no action/target/typed")
        label = text(s.get("label", "Done" if done else None), "label", 48)
        typed = text(s.get("typed"), "typed", 80) if action == "type" else ""
        require(action == "type" or "typed" not in s, "typed only belongs to type action")
        target, tsv = (None, None) if done else resolve_target(s.get("target"), src, w, h)
        if tsv:
            evidence[f"{sid}.tsv"] = tsv
        floor = max(2, 1.4 + len(typed) * .06 + .5) if typed else 2
        captions = []
        audio = None
        if "track" in s:
            require("duration" not in s, "choose duration OR track, not both")
            audio = local(s["track"], {".wav"})
            dur, side, side_path = narration(audio)
            length = max(floor, dur + .8)
            sources[f"assets/audio-{sid}.wav"] = audio
            sources[f"assets/audio-{sid}.words.json"] = side_path
            captions = [{**c, "start": total + .3 + c["start"], "end": total + .3 + c["end"]} for c in side["captions"]]
        else:
            length = number(s.get("duration"), floor, 60, "step duration")
        geo = geometry(w, h, W, H, resolved_frame, target, max_zoom)
        steps.append({"id": sid, "role": "done" if done else "step", "image": f"assets/screen-{sid}.png", "image_hash": digest(src),
                      "iw": w, "ih": h, "target": target, "action": action, "label": label, "typed": typed,
                      "start": total, "length": length, "end": total + length, "geometry": geo,
                      "audio_duration": dur if audio else None, "captions": captions})
        total += length
    require(total <= 60, "tour must be at most 60 seconds including goal/done and narration padding")
    if form.get("backdrop"):
        backdrop = local(form["backdrop"], {".png", ".jpg", ".jpeg", ".webp"})
        image(backdrop)
        sources["assets/backdrop.png"] = backdrop
    project = fresh(args.project)
    for filename in ("gsap.min.js", "GSAP-LICENSE.txt", "gsap-provenance.json"):
        require((VENDOR / filename).is_file(), "maintainer must provide verified GSAP vendor assets")
    provenance = load(VENDOR / "gsap-provenance.json")
    require(digest(VENDOR / "gsap.min.js") == provenance["sha256"], "GSAP vendor hash mismatch")
    project.mkdir()
    (project / "assets").mkdir()
    (project / "sources").mkdir()
    (project / "evidence").mkdir()
    shutil.copyfile(form_path, project / "sources/form.json")
    shutil.copyfile(manifest_path, project / "sources/steps.json")
    for name, src in sources.items():
        original = project / "sources" / (Path(name).stem + src.suffix.lower())
        shutil.copyfile(src, original)
        if name.endswith(".png"):
            with Image.open(src) as im:
                base = Image.new("RGBA", im.size, background)
                Image.alpha_composite(base, im.convert("RGBA")).convert("RGB").save(project / name)
        else:
            shutil.copyfile(src, project / name)
    for name, content in evidence.items():
        (project / "evidence" / name).write_text(content, encoding="utf-8")
    for name in ("gsap.min.js", "GSAP-LICENSE.txt", "gsap-provenance.json"):
        shutil.copyfile(VENDOR / name, project / "assets" / name)
    model = {"version": 1, "slug": slug, "width": W, "height": H, "fps": 30, "total": total,
             "frame": resolved_frame, "style": style, "background": background, "accent": accent,
             "preview": form.get("preview", "yes"), "steps": steps}
    (project / "index.html").write_text(composition(form, model), encoding="utf-8")
    write(project / "tour.json", model)
    write(project / "integrity.json", {str(p.relative_to(project)): digest(p) for p in project.rglob("*") if p.is_file()})
    return {"project": str(project), "duration": total, "next": "snapshot", "media_generation": 0}


def js(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def composition(form, m):
    W, H = m["width"], m["height"]
    g = m["steps"][0]["geometry"]
    left, top, sw, sh = g["stage"]
    scrim, blur = STYLES[m["style"]]
    channels = [int(m["background"][i:i+2], 16) / 255 for i in (1, 3, 5)]
    luminance = sum(weight * (c / 12.92 if c <= .04045 else ((c+.055)/1.055)**2.4)
                    for c, weight in zip(channels, (.2126, .7152, .0722)))
    ink = "white" if form.get("backdrop") or luminance <= .179 else "black"
    if not form.get("backdrop"):
        scrim = 0
    mobile = m["frame"] in ("ios", "android")
    radius = 26 if mobile else (0 if m["frame"] == "none" else 14)
    chrome = {"browser": '<i></i><i></i><i></i><b></b>', "macos": '<i></i><i></i><i></i>',
              "ios": '<span class="notch"></span>', "android": '<span class="camera"></span>', "none": ""}[m["frame"]]
    body, beats = [], [f'tl.to({{}},{{duration:{m["total"]}}},0);', f'tl.set("#goal",{{opacity:0}},{m["steps"][0]["start"]});']
    retained = {}
    previous_hash = None
    for i, s in enumerate(m["steps"]):
        sid, start, end = s["id"], s["start"], s["end"]
        same = s["image_hash"] == previous_hash
        initial = m["steps"][i-1]["geometry"].get("punch", [1, 0, 0]) if same else [1, 0, 0]
        if not same or s["role"] == "done":
            retained = {}
        previous_hash = s["image_hash"]
        inner = ""
        # Preserve simulated typing only while the supplied screenshot stays the same.
        current = tuple(s["target"]) if s["typed"] else None
        for rect, value in retained.items():
            if rect != current:
                x, y, tw, th = [v * g["fit"] for v in rect]
                inner += f'<div class="typed" style="left:{x}px;top:{y}px;width:{tw}px;height:{th}px;font-size:{max(12, min(28, th*.6))}px">{html.escape(value)}</div>'
        if s["target"]:
            x, y, tw, th = [v * g["fit"] for v in s["target"]]
            inner += f'<div class="target" style="left:{x}px;top:{y}px;width:{tw}px;height:{th}px"></div>'
            if s["typed"]:
                inner += f'<div class="typed" style="left:{x}px;top:{y}px;width:{tw}px;height:{th}px;font-size:{max(12, min(28, th*.6))}px">' + ''.join(f'<span>{html.escape(c)}</span>' for c in s['typed']) + '</div>'
                retained[tuple(s["target"])] = s["typed"]
        body.append(f'<div id="screen-{sid}" class="screen" data-layout-allow-overflow="true"><img src="{s["image"]}" alt="">{inner}</div>')
        counter = f'{i+1:02d} / {len(m["steps"])-1:02d} &nbsp; ' if s["role"] != "done" else ''
        body.append(f'<div id="label-{sid}" class="label">{counter}{html.escape(s["label"])}</div>')
        beats += [f'tl.set("#screen-{sid},#label-{sid}",{{opacity:1}},{start});',
                  f'tl.set("#screen-{sid},#label-{sid}",{{opacity:0}},{end});']
        if s["target"]:
            scale, tx, ty = s["geometry"]["punch"]
            cx, cy = s["geometry"]["cursor"]
            beats.append(f'tl.fromTo("#screen-{sid}",{{scale:{initial[0]},x:{initial[1]},y:{initial[2]}}},{{scale:{scale},x:{tx},y:{ty},duration:.65,ease:"power2.inOut",immediateRender:false}},{start});')
            if not mobile:
                beats += [f'tl.set("#cursor",{{opacity:1}},{start});',
                          f'tl.to("#cursor",{{x:{cx},y:{cy},duration:.65,ease:"power2.inOut"}},{start});']
            if s["action"] != "none":
                click = start + .9 if s["action"] == "type" else end - .5
                beats += [f'tl.set("#ring",{{x:{cx},y:{cy},opacity:1,scale:.5}},{click});',
                          f'tl.to("#ring",{{scale:1.3,opacity:0,duration:.4}},{click});']
            if s["typed"]:
                beats.append(f'tl.to("#screen-{sid} .typed span",{{opacity:1,duration:.01,stagger:.06}},{start+1.2});')
        else:
            beats.append(f'tl.set("#cursor",{{opacity:0}},{start});')
    audio = ''.join(f'<audio id="audio-{s["id"]}" src="assets/audio-{s["id"]}.wav" data-start="{s["start"]+.3}" data-duration="{s["audio_duration"]}" data-track-index="2"></audio>' for s in m['steps'] if s['audio_duration'])
    screens = ''.join(b for b in body if 'class="screen"' in b)
    labels = ''.join(b for b in body if 'class="label"' in b)
    bg = '<img class="backdrop" src="assets/backdrop.png" alt="">' if form.get('backdrop') else ''
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width={W}">
<script src="assets/gsap.min.js"></script><style>
@font-face{{font-family:"Hiragino Sans";src:local("Hiragino Sans")}}
*{{box-sizing:border-box}}html,body{{margin:0;width:{W}px;height:{H}px}}
#root{{position:relative;width:{W}px;height:{H}px;overflow:hidden;background:{m['background']};font-family:Arial,"Hiragino Sans",sans-serif}}
.backdrop{{position:absolute;width:100%;height:100%;object-fit:cover;filter:blur({blur}px)}}
.scrim{{position:absolute;inset:0;background:rgba(0,0,0,{scrim})}}
.device{{position:absolute;left:{left}px;top:{top-g['bar']}px;width:{sw}px;height:{sh+g['bar']+g['bottom']}px;background:#18202e;border-radius:{radius}px;outline:{0 if m['frame']=='none' else 2}px solid {'#ffffff' if m['style']=='outline' else '#667085'};overflow:hidden}}
.bar{{height:{g['bar']}px;display:flex;align-items:center;gap:6px;padding:0 14px;position:relative}}
.bar i{{width:8px;height:8px;border-radius:50%;background:#94a3b8}}.bar b{{margin-left:20px;width:60%;height:16px;border-radius:4px;background:#344054}}
.notch{{position:absolute;left:40%;width:20%;height:14px;top:0;border-radius:0 0 10px 10px;background:#05080c}}
.camera{{position:absolute;left:calc(50% - 4px);width:8px;height:8px;border-radius:50%;background:#05080c}}
.home{{position:absolute;bottom:7px;left:38%;width:24%;height:4px;border-radius:4px;background:#94a3b8}}
.stage{{position:absolute;top:{g['bar']}px;left:0;width:{sw}px;height:{sh}px;overflow:hidden}}
.screen{{position:absolute;inset:0;opacity:0;transform-origin:0 0}}.screen img{{width:100%;height:100%;display:block}}
.target{{position:absolute;border:3px solid {m['accent']};box-shadow:0 0 0 1px #fff;border-radius:4px}}
.typed{{position:absolute;color:#111;background:white;overflow:hidden;white-space:pre;display:flex;align-items:center;padding:0 4px}}.typed span{{opacity:0;flex-shrink:0}}
.label{{position:absolute;left:56px;bottom:32px;width:{W-112}px;min-height:54px;padding:14px 20px;background:#101827;color:#fff;font-size:22px;line-height:1.3;opacity:0;border-left:5px solid {m['accent']};border-radius:{0 if m['style']=='outline' else 10}px}}
#heading{{position:absolute;left:56px;top:26px;width:{W-112}px;color:{ink};font-size:24px;line-height:1.2}}
#goal{{position:absolute;inset:0;background:#101827;color:white;display:flex;flex-direction:column;gap:24px;align-items:center;justify-content:center;padding:64px;z-index:10;font-size:40px;text-align:center}}
#goal-support{{font-size:24px}}
#cursor,#ring{{position:absolute;left:0;top:0;opacity:0;z-index:5;pointer-events:none}}
#cursor svg{{position:absolute;left:-3px;top:-3px;width:48px;height:60px}}
#ring div{{position:absolute;left:-18px;top:-18px;width:36px;height:36px;border:4px solid {m['accent']};border-radius:50%;box-shadow:0 0 0 2px white}}
</style></head><body><div id="root" data-composition-id="tour" data-start="0" data-width="{W}" data-height="{H}" data-duration="{m['total']}" data-fps="30">
{bg}<div class="scrim"></div><div id="heading" data-layout-allow-occlusion="true">{html.escape(form.get('app',''))}</div>
<div class="device"><div class="bar">{chrome}</div><div class="stage">{screens}</div>{'<div class="home"></div>' if mobile else ''}</div>{labels}
<div id="cursor"><svg viewBox="0 0 48 60"><path d="M3 3 L3 43 L14 33 L24 54 L34 49 L24 29 L41 29 Z" fill="white" stroke="#111" stroke-width="3"/></svg></div>
<div id="ring"><div></div></div><div id="goal"><div id="goal-title">{html.escape(form['task'])}</div>{'<div id="goal-support">' + html.escape(form['app']) + '</div>' if form.get('app') else ''}</div>{audio}</div>
<script>const tourData={js(m)};
window.__timelines ||= {{}};
const tl=gsap.timeline({{paused:true}});
tl.set("#cursor",{{x:{W/2},y:{H+64}}},0);
{''.join(beats)}
window.__timelines["tour"]=tl;
document.fonts.ready.then(()=>{{
for(const el of document.querySelectorAll('.typed,.label,#heading,#goal,#goal-title,#goal-support')){{
  if(el.scrollWidth>el.clientWidth+1||el.scrollHeight>el.clientHeight+1)
    throw new Error('Tour text exceeds rendering bounds: '+(el.id||el.className));
}}
const stage=document.querySelector('.device').getBoundingClientRect();
for(const el of document.querySelectorAll('.label')){{
  if(el.getBoundingClientRect().top<stage.bottom+8)
    throw new Error('Tour label overlaps device; shorten label');
}}
}});</script></body></html>'''


def project_model(value):
    project = Path(value).expanduser()
    local(str(project / "index.html"), {".html"})
    integrity = load(local(str(project / "integrity.json"), {".json"}))
    require(isinstance(integrity, dict) and {"index.html", "tour.json", "sources/form.json", "sources/steps.json", "assets/gsap.min.js"} <= set(integrity), "invalid project integrity record")
    for name, expected in integrity.items():
        require(not Path(name).is_absolute() and ".." not in Path(name).parts, "invalid integrity path")
        p = local(str(project / name), {Path(name).suffix})
        require(digest(p) == expected, "project changed since scaffold; revise in a fresh project, do not patch HTML")
    model = load(project / "tour.json")
    number(model["total"], .1, 60, "render duration")
    require((model["width"], model["height"]) in CANVAS.values() and model["fps"] == 30, "render bounds invalid")
    return project, model


def hf(project, args, evidence):
    binary = shutil.which("hyperframes")
    require(binary, "hyperframes CLI missing; ask maintainer to provision it")
    try:
        result = command([binary, *args], cwd=project, timeout=1800)
    except Exception as exc:
        evidence.write_text(getattr(exc, "evidence", str(exc)), encoding="utf-8")
        raise
    evidence.write_text(result, encoding="utf-8")


def snapshot(args):
    project, m = project_model(args.project)
    out = fresh(args.out)
    out.mkdir()
    times = [.75] + [s["end"] - .3 for s in m["steps"]]
    hf(project, ["lint", "--json"], out / "lint.json")
    hf(project, ["check", "--json", "--at", ",".join(map(str, times))], out / "check.json")
    contrast = load(out / "check.json").get("contrast", {})
    require(contrast.get("enabled") and contrast.get("checked", 0) > 0, "contrast audit skipped; inspect check.json")
    hf(project, ["snapshot", "--at", ",".join(map(str, times)), "--no-end", "--describe", "false", "-o", str(out / "frames")], out / "snapshot.log")
    files = sorted((out / "frames").glob("*.png"))
    require(len(files) == len(times), "snapshot count mismatch")
    for p in files:
        require(image(p) == (m["width"], m["height"]), "snapshot dimensions mismatch")
    write(out / "preview.json", {"project": str(project), "integrity": digest(project / "integrity.json"),
                                 "times": times, "frames": {str(p): digest(p) for p in files}})
    return {"preview": str(out), "frames": len(files), "rendered_mp4": False}


def render(args):
    project, m = project_model(args.project)
    if m["preview"] == "yes":
        require(args.approved_preview, "preview=yes requires --approved-preview after client approval")
    if args.approved_preview:
        approved = load(local(str(Path(args.approved_preview) / "preview.json"), {".json"}))
        require(approved["project"] == str(project) and approved["integrity"] == digest(project / "integrity.json"), "approved preview belongs to another project")
        require(isinstance(approved.get("frames"), dict) and len(approved["frames"]) == len(m["steps"])+1, "approved preview needs every step and goal frame")
        for name, expected in approved["frames"].items():
            require(digest(local(name, {".png"})) == expected, "approved preview frame changed")
    out = fresh(args.out)
    out.mkdir()
    hf(project, ["lint", "--json"], out / "lint.json")
    times = [.75] + [s["end"] - .3 for s in m["steps"]]
    hf(project, ["check", "--json", "--at", ",".join(map(str, times))], out / "check.json")
    checks = load(out / "check.json")
    contrast = checks.get("contrast", {})
    require(contrast.get("enabled") and contrast.get("checked", 0) > 0, "contrast audit skipped; inspect check.json")
    movie = out / f"tour_{m['slug']}.mp4"
    hf(project, ["render", "--output", str(movie), "--fps", "30", "--workers", "1", "--strict", "--no-best-effort", "--quiet"], out / "render.log")
    info = json.loads(command(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(movie)]))
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    require((video["width"], video["height"]) == (m["width"], m["height"]), "render dimensions mismatch")
    require(video["codec_name"] == "h264" and video["pix_fmt"] == "yuv420p", "render codec/pixel format mismatch")
    require(Fraction(video["avg_frame_rate"]) == m["fps"], "render fps mismatch")
    require(abs(float(info["format"]["duration"]) - m["total"]) <= .1, "render duration mismatch")
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
    require(has_audio == any(s["audio_duration"] for s in m["steps"]), "render audio presence mismatch")
    command(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(movie), "-f", "null", "-"], timeout=300)
    reviews = out / "review"
    reviews.mkdir()
    for s in m["steps"]:
        command(["ffmpeg", "-nostdin", "-v", "error", "-n", "-ss", str(s["end"]-.3), "-i", str(movie), "-frames:v", "1", str(reviews / f"{s['id']}.png")])
    shutil.copyfile(reviews / f"{m['steps'][0]['id']}.png", out / "poster.png")
    cues = [c for s in m["steps"] for c in (s["captions"] or [{"text": s["label"], "start": s["start"], "end": s["end"]}])]
    def stamp(t):
        ms = round(t * 1000)
        return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"
    (out / "tour.srt").write_text("\n".join(f"{i+1}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}\n" for i, c in enumerate(cues)), encoding="utf-8")
    report = {"project": str(project), "mp4": str(movie), "decoded": True, "bytes": movie.stat().st_size,
              "duration": float(info["format"]["duration"]), "width": video["width"], "height": video["height"], "fps": float(Fraction(video["avg_frame_rate"])),
              "audio": has_audio, "contrast": {"checked": contrast["checked"], "passed": contrast["passed"],
              "scope": "sampled authored text only; raster screenshot UI text unverified", "evidence": str(out / "check.json")},
              "cursor": "geometry computed; rendered placement needs visual review (not a white-pixel heuristic)",
              "temporal_review": "unverified", "speech_alignment": "estimated from supplied sidecar", "media_generation": 0}
    write(out / "qa.json", report)
    (out / "qa.md").write_text("# Tour QA\n\nFull decode and dimensions passed; see qa.json.\nSampled authored-text contrast: see check.json counts/findings.\nRaster UI text, target placement, text fit, pacing and audio listening: pending visual/listening review.\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("scaffold")
    build.add_argument("--form", required=True)
    build.add_argument("--project", required=True)
    for name in ("snapshot", "render"):
        p = commands.add_parser(name)
        p.add_argument("--project", required=True)
        p.add_argument("--out", required=True)
        if name == "render":
            p.add_argument("--approved-preview")
    args = parser.parse_args()
    try:
        print("RESULT: " + json.dumps(globals()[args.command](args)))
    except (ValueError, OSError, KeyError, TypeError, wave.Error, EOFError, Image.DecompressionBombError, subprocess.TimeoutExpired) as exc:
        print(f"tour: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
