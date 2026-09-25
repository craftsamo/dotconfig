#!/usr/bin/env python3
"""create-master helper: join finished parts into one delivery master.

Deterministic and local. Never generates media, installs anything or touches
the network. Run with the Hermes venv Python when a Mix bundle is supplied
(its validation loads AudioCreator's own helper).

    master.py build --segments A.mp4,B.mp4 --out NEW_DIR [--slug SLUG]
        [--transition cut|dissolve] [--transition-seconds 0.5]
        [--audio TRACK.wav | --mix-bundle DIR]
        [--captions FILE.srt|captions.json] [--burn-captions yes|no]
        [--caption-position bottom|top]

The picture is joined with ffmpeg; captions, when burned in, are rendered by
the installed HyperFrames CLI as a transparent layer and composited on top,
so the picture itself never passes through the browser. Prints one
`RESULT: <json>` line; exits 1 with `master: <detail>` on failure. The
output directory is published only after every check passes.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
KERNEL = HERE.parents[2]
VENDOR = KERNEL / "create/tour/assets"
MAX_SEGMENTS = 24
MAX_SECONDS = 180.0
MAX_CUES = 400
MAX_CUE_CHARS = 200
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
ENV = {**os.environ, "DO_NOT_TRACK": "1", "HYPERFRAMES_TELEMETRY_DISABLED": "1"}


class Fail(Exception):
    pass


def require(ok, message):
    if not ok:
        raise Fail(message)


def run(cmd, cwd=None, timeout=1800):
    proc = subprocess.run([str(c) for c in cmd], cwd=cwd, env=ENV, capture_output=True, text=True,
                          timeout=timeout)
    return proc


def check(cmd, what, cwd=None, timeout=1800):
    proc = run(cmd, cwd=cwd, timeout=timeout)
    require(proc.returncode == 0, f"{what} failed: {(proc.stderr or proc.stdout)[-1500:]}")
    return proc.stdout


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def local_file(value: str, what: str) -> Path:
    require(value and "://" not in value, f"{what}: local path required, not a URL")
    path = Path(value).expanduser()
    require(path.is_absolute(), f"{what}: absolute path required: {value}")
    require(path.is_file(), f"{what}: file not found: {value}")
    return path.resolve()


def probe(path: Path) -> dict:
    info = json.loads(check(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
                            f"ffprobe {path.name}", timeout=120))
    videos = [s for s in info["streams"] if s.get("codec_type") == "video"
              and not s.get("disposition", {}).get("attached_pic")]
    audios = [s for s in info["streams"] if s.get("codec_type") == "audio"]
    video = videos[0] if videos else None
    if video:
        duration = float(video.get("duration") or info["format"].get("duration") or 0)
    else:
        duration = float((audios[0].get("duration") if audios else None) or info["format"].get("duration") or 0)
    return {"info": info, "video": video, "audio": audios, "duration": duration}


def segment(path: Path, index: int) -> dict:
    require(path.suffix.lower() in VIDEO_SUFFIXES, f"segment {index}: video file required ({path.name})")
    facts = probe(path)
    video = facts["video"]
    require(video, f"segment {index}: no video stream")
    rate = Fraction(video.get("avg_frame_rate") or "0/1")
    require(0 < rate <= 60, f"segment {index}: frame rate must be measurable and at most 60")
    sar = video.get("sample_aspect_ratio", "1:1")
    require(sar in ("1:1", "N/A", "0:1"), f"segment {index}: non-square pixels ({sar}); fit it with edit-clip first")
    rotation = next((float(s["rotation"]) for s in video.get("side_data_list", []) if "rotation" in s),
                    float(video.get("tags", {}).get("rotate", 0)))
    require(round(rotation) % 360 == 0, f"segment {index}: rotation metadata; re-encode it with edit-clip first")
    pix = video.get("pix_fmt") or ""
    require(not re.search(r"(p10|p12|p16)", pix) and video.get("color_transfer") not in ("smpte2084", "arib-std-b67"),
            f"segment {index}: HDR or high-bit-depth picture ({pix}); converting it would grade it - not supported")
    if video.get("duration"):
        duration = float(video["duration"])
    else:  # Matroska/WebM keep no stream duration; the container's may include longer audio
        counted = check(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                         "stream=nb_read_packets", "-of", "csv=p=0", path], f"count frames of segment {index}")
        duration = int(counted.strip().split(",")[0]) / float(rate)
    require(math.isfinite(duration) and duration > 0, f"segment {index}: no measurable duration")
    return {"path": str(path), "sha256": sha(path), "width": video["width"], "height": video["height"],
            "fps": str(rate), "duration": round(duration, 6), "had_audio": bool(facts["audio"])}


def srt_cues(text: str) -> list[dict]:
    stamp = r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})"
    cues = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        lines = [line for line in block.split("\n") if line.strip()]
        timing = next((i for i, line in enumerate(lines) if "-->" in line), None)
        require(timing is not None, "SRT block without a timing line")
        match = re.fullmatch(rf"\s*{stamp}\s*-->\s*{stamp}.*", lines[timing])
        require(match, f"bad SRT timing line: {lines[timing]}")
        g = [int(x) for x in match.groups()]
        start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        body = "\n".join(re.sub(r"<[^>]+>|\{\\[^}]*\}", "", line).strip() for line in lines[timing + 1:])
        cues.append({"start": start, "end": end, "text": body})
    return cues


def load_cues(path: Path) -> list[dict]:
    if path.suffix.lower() == ".srt":
        return srt_cues(path.read_text(encoding="utf-8-sig"))
    require(path.suffix.lower() == ".json", "captions must be .srt or a Mix captions.json")
    doc = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(doc, dict) and doc.get("kind") == "mix-captions" and isinstance(doc.get("captions"), list),
            "captions JSON must be a Mix captions.json (kind: mix-captions)")
    return [{"start": c["start"], "end": c["end"], "text": c["text"]} for c in doc["captions"]]


def check_cues(cues: list[dict], total: float, frame: float) -> list[dict]:
    require(1 <= len(cues) <= MAX_CUES, f"captions: 1..{MAX_CUES} cues required")
    clean, last = [], 0.0
    for i, cue in enumerate(cues, 1):
        require(all(isinstance(cue.get(k), (int, float)) and not isinstance(cue.get(k), bool)
                    for k in ("start", "end")) and isinstance(cue.get("text"), str),
                f"caption {i}: numeric start/end and text required")
        start, end = float(cue["start"]), float(cue["end"])
        lines = [" ".join(line.split()) for line in cue["text"].split("\n")]
        text = "\n".join(line for line in lines if line)
        require(math.isfinite(start) and math.isfinite(end) and 0 <= start < end,
                f"caption {i}: start must be >= 0 and before end")
        require(end <= total + frame, f"caption {i}: ends after the master ({end} > {total:.3f})")
        require(start >= last - 1e-6, f"caption {i}: overlaps or is out of order")
        require(1 <= len(text) <= MAX_CUE_CHARS, f"caption {i}: text must be 1..{MAX_CUE_CHARS} characters")
        start, end = round(start, 3), round(min(end, total), 3)
        require(end > start, f"caption {i}: starts at or after the end of the master")
        clean.append({"start": start, "end": end, "text": text})
        last = end
    return clean


def srt_text(cues: list[dict]) -> str:
    def stamp(seconds):
        ms = round(seconds * 1000)
        return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"
    return "\n".join(f"{i}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}\n" for i, c in enumerate(cues, 1))


def load_mix_audio():
    sys.path.insert(0, str(KERNEL / "scripts"))
    try:
        import mix_audio  # noqa: PLC0415 - optional, loads AudioCreator's own helper
    except Exception as exc:  # pragma: no cover - environment dependent
        raise Fail(f"Mix validation unavailable ({exc}); run with the Hermes venv Python") from exc
    return mix_audio


def mix_bundle(value: str) -> dict:
    bundle = Path(value).expanduser()
    require(bundle.is_absolute() and bundle.is_dir(), f"mix bundle: absolute directory required: {value}")
    mix_audio = load_mix_audio()
    try:
        verified = mix_audio.verify_full_bundle(bundle)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise Fail(f"mix bundle failed AudioCreator's verification: {exc}") from exc
    take = verified["take"]
    captions = bundle / "captions.json" if "captions.json" in take.get("files", {}) else None
    return {"master": Path(verified["master"]), "receipt": take, "captions": captions, "module": mix_audio,
            "bundle": bundle, "seconds": take["master"]["frames"] / take["master"]["sample_rate"]}


def stage_mix(mix: dict, work: Path) -> None:
    """Use byte copies of the verified bundle, re-validated, never its mutable paths."""
    staged = work / "mix"
    staged.mkdir()
    master = staged / mix["master"].name
    shutil.copyfile(mix["master"], master)
    shutil.copyfile(mix["bundle"] / "mix.take.json", staged / "mix.take.json")
    captions = None
    if mix["captions"]:
        captions = staged / "captions.json"
        shutil.copyfile(mix["captions"], captions)
    try:
        mix["module"].load_mix_media().validate_delivery(master, staged / "mix.take.json", captions)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise Fail(f"Mix bundle changed after verification: {exc}") from exc
    mix.update(master=master, captions=captions)


def picture_graph(segments: list[dict], transition: str, seconds: float, rate: str) -> tuple[str, float]:
    parts = [f"[{i}:v:0]setpts=PTS-STARTPTS,fps={rate},setsar=1,format=yuv420p,settb=AVTB[v{i}]" for i in range(len(segments))]
    durations = [s["duration"] for s in segments]
    if len(segments) == 1:
        return ";".join(parts) + ";[v0]null[pic]", durations[0]
    if transition == "cut":
        joined = "".join(f"[v{i}]" for i in range(len(segments)))
        return ";".join(parts) + f";{joined}concat=n={len(segments)}:v=1:a=0[pic]", sum(durations)
    chain, label, elapsed = [], "v0", durations[0]
    for i in range(1, len(segments)):
        offset = elapsed - seconds
        out = "pic" if i == len(segments) - 1 else f"x{i}"
        chain.append(f"[{label}][v{i}]xfade=transition=fade:duration={seconds}:offset={offset:.6f}[{out}]")
        label, elapsed = out, elapsed + durations[i] - seconds
    return ";".join(parts + chain), elapsed


CAPTION_PAGE = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>create-master captions</title>
<style>
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; width: {w}px; height: {h}px; background: transparent; }}
#root {{ position: relative; overflow: hidden; width: {w}px; height: {h}px; background: transparent; }}
.caption {{ position: absolute; left: 8%; right: 8%; {edge}: {margin}px; text-align: center;
  font-family: "Noto Sans JP", sans-serif; font-weight: 700; font-size: {size}px; line-height: 1.4;
  color: #ffffff; word-break: auto-phrase; overflow-wrap: anywhere; }}
.caption span {{ background: rgba(0, 0, 0, 0.62); padding: 0.1em 0.45em; border-radius: 0.2em;
  -webkit-box-decoration-break: clone; box-decoration-break: clone; }}
</style>
<script src="assets/gsap.min.js"></script>
</head>
<body>
<div id="root" data-composition-id="master" data-start="0" data-duration="{total}" data-width="{w}" data-height="{h}" data-fps="{fps}">
{cues}
</div>
<script>
const tl = gsap.timeline({{paused: true}});
tl.set({{}}, {{}}, {total});
window.__timelines = window.__timelines || {{}};
window.__timelines["master"] = tl;
</script>
</body>
</html>
"""


def caption_layer(work: Path, cues, width, height, total, rate, position) -> Path:
    binary = shutil.which("hyperframes")
    require(binary, "hyperframes CLI missing; burned-in captions need the maintainer-provisioned CLI")
    provenance = json.loads((VENDOR / "gsap-provenance.json").read_text(encoding="utf-8"))
    require(sha(VENDOR / "gsap.min.js") == provenance["sha256"], "GSAP vendor hash mismatch")
    project = work / "captions"
    (project / "assets").mkdir(parents=True)
    for name in ("gsap.min.js", "GSAP-LICENSE.txt", "gsap-provenance.json"):
        shutil.copyfile(VENDOR / name, project / "assets" / name)
    short = min(width, height)
    elements = "\n".join(
        f'<div id="mix-caption-{i}" class="caption clip" data-start="{c["start"]}" '
        f'data-duration="{round(c["end"] - c["start"], 3)}" data-track-index="1">'
        f'<span>{"<br>".join(html.escape(line) for line in c["text"].split(chr(10)))}</span></div>'
        for i, c in enumerate(cues, 1))
    fps_attr = f"{float(Fraction(rate)):.3f}".rstrip("0").rstrip(".")
    page = CAPTION_PAGE.format(w=width, h=height, total=round(total, 3), fps=fps_attr, cues=elements,
                               edge="bottom" if position == "bottom" else "top",
                               margin=round(height * (0.12 if position == "bottom" else 0.08)),
                               size=round(short * 0.05))
    (project / "index.html").write_text(page, encoding="utf-8")
    lint = run([binary, "lint", "--json"], cwd=project, timeout=300)
    try:
        verdict = json.loads(lint.stdout)
    except ValueError:
        verdict = {}
    require(verdict.get("ok") and verdict.get("errorCount") == 0,
            "caption layer lint failed: " + json.dumps(verdict.get("findings") or lint.stderr[-1500:])[:1500])
    layer = work / "captions.mov"
    fraction = Fraction(rate)
    cli_rate = str(fraction.numerator) if fraction.denominator == 1 else f"{fraction.numerator}/{fraction.denominator}"
    proc = run([binary, "render", "--output", layer, "--format", "mov", "--fps", cli_rate, "--quiet",
                "--strict", "--no-best-effort"], cwd=project)
    require(proc.returncode == 0 and layer.is_file(), f"caption layer render failed: {(proc.stderr or proc.stdout)[-1500:]}")
    return layer


def sheets(movie: Path, total: float, joins: list[float], out: Path) -> dict:
    rate = min(4.0, 64.0 / total)
    rows = max(1, math.ceil(total * rate / 8))
    check(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", movie, "-vf",
           f"fps={rate:.4f},scale=320:-2,tile=8x{rows}:padding=4:color=red", "-frames:v", "1", out / "sheet.png"],
          "contact sheet", timeout=600)
    join_files = []
    for k, at in enumerate(joins, 1):
        frames = []
        for n, t in enumerate((max(0.0, at - 0.25), at, min(total - 0.04, at + 0.25))):
            frame = out / f".join-{k}-{n}.png"
            check(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", movie, "-frames:v", "1",
                   "-vf", "scale=400:-2", frame], "join frame", timeout=120)
            frames.append(frame)
        target = out / f"join-{k}.png"
        inputs = [arg for f in frames for arg in ("-i", f)]
        check(["ffmpeg", "-nostdin", "-v", "error", "-y", *inputs, "-filter_complex", "[0:v][1:v][2:v]hstack=inputs=3",
               target], "join sheet", timeout=120)
        for f in frames:
            f.unlink()
        join_files.append({"at": round(at, 3), "sheet": target.name})
    return {"sheet": "sheet.png", "joins": join_files}


def build(args) -> dict:
    slug = args.slug or "master"
    require(SLUG.fullmatch(slug) and len(slug) <= 60, "slug: lowercase ASCII letters/digits with single hyphens")
    out = Path(args.out).expanduser()
    require(out.is_absolute() and out.parent.is_dir(), "out: needs an existing absolute parent directory")
    require(not out.exists() and not out.is_symlink(), f"out must be a new directory: {out}")
    paths = [p.strip() for p in args.segments.split(",") if p.strip()]
    require(1 <= len(paths) <= MAX_SEGMENTS, f"segments: 1..{MAX_SEGMENTS} local videos in play order")
    segments = [segment(local_file(p, f"segment {i}"), i) for i, p in enumerate(paths, 1)]
    first = segments[0]
    for i, s in enumerate(segments[1:], 2):
        require((s["width"], s["height"]) == (first["width"], first["height"]),
                f"segment {i} is {s['width']}x{s['height']}, not {first['width']}x{first['height']}; "
                "fit it with edit-clip first")
        require(abs(float(Fraction(s["fps"])) - float(Fraction(first["fps"]))) < 0.01,
                f"segment {i} runs at {float(Fraction(s['fps'])):.3f} fps, not {float(Fraction(first['fps'])):.3f}")
    require(first["width"] % 2 == 0 and first["height"] % 2 == 0, "segment dimensions must be even; fit with edit-clip")
    seconds = 0.0
    if args.transition == "dissolve":
        require(len(segments) > 1, "dissolve needs at least two segments")
        seconds = float(args.transition_seconds)
        require(0.1 <= seconds <= 2.0, "transition-seconds: 0.1..2.0")
        require(all(s["duration"] > 2 * seconds for s in segments),
                "every segment must last more than twice the dissolve")
    rate, frame = first["fps"], 1 / float(Fraction(first["fps"]))
    graph, total = picture_graph(segments, args.transition, seconds, rate)
    require(total <= MAX_SECONDS, f"master would last {total:.2f}s; at most {MAX_SECONDS:.0f}s")
    tolerance = frame + 1e-3

    require(not (args.audio and args.mix_bundle), "give either --audio or --mix-bundle, not both")
    audio = mix = None
    if args.audio:
        audio = local_file(args.audio, "audio")
        require(audio.suffix.lower() == ".wav", "audio: a finished WAV is required")
        facts = probe(audio)
        require(facts["audio"] and not facts["video"], "audio: file must hold audio only")
        require(abs(facts["duration"] - total) <= tolerance,
                f"audio lasts {facts['duration']:.3f}s but the picture lasts {total:.3f}s; "
                "have AudioCreator fit it (edit-music / edit-mix) - it is never cut or padded here")
    if args.mix_bundle:
        mix = mix_bundle(args.mix_bundle)
        audio = mix["master"]
        require(abs(mix["seconds"] - total) <= tolerance,
                f"Mix master lasts {mix['seconds']:.3f}s but the picture lasts {total:.3f}s")

    caption_path = local_file(args.captions, "captions") if args.captions else (mix or {}).get("captions")
    cues = check_cues(load_cues(caption_path), total, frame) if caption_path else []
    burn = (args.burn_captions or "yes") == "yes" if cues else False
    require(not (args.burn_captions == "yes" and not cues), "burn-captions: yes needs captions")

    inputs = {"segments": segments, "transition": args.transition, "transition_seconds": seconds or None,
              "audio": {"path": str(audio), "sha256": sha(audio), "mix_bundle": args.mix_bundle} if audio else None,
              "captions": {"path": str(caption_path), "sha256": sha(caption_path), "cues": len(cues),
                           "burned": burn, "position": args.caption_position} if cues else None}

    with tempfile.TemporaryDirectory(prefix=".master-", dir=out.parent) as temp:
        work = Path(temp)
        stage = work / "publish"
        stage.mkdir()
        if mix:
            stage_mix(mix, work)
            audio = mix["master"]
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y"]
        for s in segments:
            cmd += ["-i", s["path"]]
        video_out = "[pic]"
        if burn:  # one encode: the caption layer is composited inside the join graph
            layer = caption_layer(work, cues, first["width"], first["height"], total, rate, args.caption_position)
            cmd += ["-i", layer]
            graph += f";[pic][{len(segments)}:v]overlay=0:0:format=auto:eof_action=pass,format=yuv420p[v]"
            video_out = "[v]"
        if audio:
            cmd += ["-i", audio]
        movie = stage / f"master_{slug}.mp4"
        cmd += ["-filter_complex", graph, "-map", video_out, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-pix_fmt", "yuv420p", "-r", rate]
        if audio:
            cmd += ["-map", f"{len(segments) + (1 if burn else 0)}:a:0", "-c:a", "aac", "-b:a", "192k"]
        else:
            cmd += ["-an"]
        cmd += ["-t", f"{total:.6f}", "-map_metadata", "-1", "-movflags", "+faststart", movie]
        check(cmd, "join and encode")
        check(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", movie, "-map", "0:v:0", "-map", "0:a:0?",
               "-f", "null", os.devnull], "full decode")
        facts = probe(movie)
        video = facts["video"]
        measured = {"width": video["width"], "height": video["height"],
                    "fps": round(float(Fraction(video.get("avg_frame_rate") or "0/1")), 3),
                    "duration": round(facts["duration"], 3), "audio_streams": len(facts["audio"]),
                    "bytes": movie.stat().st_size}
        checks = {"canvas": (video["width"], video["height"]) == (first["width"], first["height"]),
                  "fps": abs(measured["fps"] - float(Fraction(rate))) < 0.01,
                  "duration": abs(facts["duration"] - total) <= tolerance + 0.05,
                  "audio_present": len(facts["audio"]) == (1 if audio else 0),
                  "decoded": True}
        level, audio_finding = None, None
        if audio:
            if mix:
                level = mix["module"].measure_audio(movie)
                try:
                    mix["module"].check_final_audio(level, mix["receipt"], facts["info"]["streams"], total)
                    checks["mix_audio_within_receipt"] = True
                except ValueError as exc:  # names the actual cause: stream count, duration or true peak
                    checks["mix_audio_within_receipt"] = False
                    audio_finding = str(exc)
            else:
                level = load_mix_audio().measure_audio(movie)
                checks["true_peak_below_0"] = level["input_tp"] < 0
        if cues:
            (stage / f"master_{slug}.srt").write_text(srt_text(cues), encoding="utf-8")
        joins, elapsed = [], 0.0
        for s in segments[:-1]:
            elapsed += s["duration"] - seconds
            joins.append(elapsed if not seconds else elapsed + seconds / 2)
        review = sheets(movie, total, joins, stage)
        status = "PASS" if all(checks.values()) else "FAIL"
        result = {"status": status, "movie": str(out / movie.name), "movie_sha256": sha(movie),
                  "captions_srt": str(out / f"master_{slug}.srt") if cues else None,
                  "total_seconds": round(total, 3), "inputs": inputs, "probe": measured, "loudness": level,
                  "checks": checks, "audio_finding": audio_finding, "review": {k: (str(out / v) if isinstance(v, str) else
                                                   [{**j, "sheet": str(out / j["sheet"])} for j in v])
                                               for k, v in review.items()},
                  "segment_audio_dropped": [i for i, s in enumerate(segments, 1) if s["had_audio"]],
                  "unverified": ["temporal review beyond sampled sheets", "listening", "caption reading speed"],
                  "media_generation": 0}
        (stage / "master.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        failed = {k: measured.get(k, audio_finding or level) for k, v in checks.items() if not v}
        require(status == "PASS", f"checks failed {json.dumps(failed, default=str)} (expected "
                f"{first['width']}x{first['height']}, {float(Fraction(rate)):.3f} fps, {total:.3f}s); nothing published")
        out.mkdir()  # exclusive: fails if the directory appeared meanwhile
        for item in stage.iterdir():
            item.rename(out / item.name)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--segments", required=True, help="comma-separated absolute video paths in play order")
    b.add_argument("--out", required=True)
    b.add_argument("--slug")
    b.add_argument("--transition", choices=("cut", "dissolve"), default="cut")
    b.add_argument("--transition-seconds", type=float, default=0.5)
    b.add_argument("--audio")
    b.add_argument("--mix-bundle")
    b.add_argument("--captions")
    b.add_argument("--burn-captions", choices=("yes", "no"))
    b.add_argument("--caption-position", choices=("bottom", "top"), default="bottom")
    args = ap.parse_args(argv)
    try:
        result = build(args)
    except (Fail, OSError, ValueError, KeyError, TypeError, ZeroDivisionError, RuntimeError,
            subprocess.TimeoutExpired) as exc:
        print(f"master: {exc}", file=sys.stderr)
        return 1
    print("RESULT: " + json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
