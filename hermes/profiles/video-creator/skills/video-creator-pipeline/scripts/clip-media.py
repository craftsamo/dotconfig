#!/usr/bin/env python3
"""Local clip measurement, bounded review frames, and non-destructive encoding.

Requires ffmpeg/ffprobe; frames also requires ImageMagick's magick. Stdlib only.
Prints RESULT: <JSON>; never overwrites a source, output, or review directory.
"""

import argparse
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def run(args):
    return subprocess.run(
        [str(arg) for arg in args], check=True, capture_output=True, text=True
    ).stdout


def probe(source):
    source = Path(source).expanduser().resolve(strict=True)
    if not source.is_file():
        raise ValueError("source must be a local file; localize tool URLs first")
    data = json.loads(run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", source
    ]))
    videos = [s for s in data["streams"] if s.get("codec_type") == "video"
              and not s.get("disposition", {}).get("attached_pic")]
    if not videos:
        raise ValueError("source has no video stream")
    video = videos[0]
    duration = float(video.get("duration", data["format"].get("duration", 0)))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("source must have a measurable positive duration")
    fps = float(Fraction(video.get("avg_frame_rate", "0/1")))
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("source must have a measurable frame rate")
    rotation = next((float(s["rotation"]) for s in video.get("side_data_list", [])
                     if "rotation" in s), float(video.get("tags", {}).get("rotate", 0)))
    sar = video.get("sample_aspect_ratio", "1:1")
    if sar in ("N/A", "0:1"):
        sar = "1:1"
    ratio = float(Fraction(sar.replace(":", "/")))
    width, height = round(video["width"] * ratio), video["height"]
    if round(rotation) % 180:
        width, height = height, width
    if width <= 0 or height <= 0:
        raise ValueError("invalid display dimensions")
    return {
        "path": str(source), "width": video["width"], "height": video["height"],
        "display_width": width, "display_height": height, "sar": sar,
        "rotation": rotation, "fps": fps, "duration": duration,
        "codec": video["codec_name"], "pix_fmt": video.get("pix_fmt"),
        "bytes": source.stat().st_size,
        "audio": any(s.get("codec_type") == "audio" for s in data["streams"]),
        "video_index": video["index"],
    }


def frames(args):
    info = probe(args.source)
    if info["duration"] > 60:
        raise ValueError("review one clip of at most 60 seconds; trim a segment first")
    out = Path(args.output).expanduser().absolute()
    if out.exists() or out.is_symlink():
        raise ValueError("review directory must not exist; use a new round directory")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".clip-frames-", dir=out.parent) as temp:
        temp = Path(temp)
        last = max(0, info["duration"] - max(1 / info["fps"], 0.05))
        times = [round(last * i / (args.count - 1), 6) for i in range(args.count)]
        files = []
        for i, at in enumerate(times):
            dest = temp / f"frame-{i + 1:02}.png"
            run(["ffmpeg", "-nostdin", "-v", "error", "-i", info["path"],
                 "-ss", at, "-map", f"0:{info['video_index']}", "-frames:v", "1",
                 "-vf", f"scale={info['display_width']}:{info['display_height']},setsar=1", dest])
            if not dest.is_file():
                raise ValueError(f"no frame decoded at {at}; review is incomplete")
            files.append(dest)
        run(["magick", *files, "-resize", "240x180", "-background", "#808080",
             "-gravity", "center", "-extent", "256x196", "+append", temp / "sheet.png"])
        result = {"source": info["path"], "times": times,
                  "frames": [str(out / f.name) for f in files],
                  "sheet": str(out / "sheet.png"), "coverage": "sampled, not exhaustive"}
        (temp / "frames.json").write_text(json.dumps(result, indent=2) + "\n")
        # Publish only the finished review set. Do not merge stale frames.
        out.mkdir()
        for item in temp.iterdir():
            item.rename(out / item.name)
    return result


def edit(args):
    info = probe(args.source)
    output = Path(args.output).expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("output exists; use a new filename (source is never overwritten)")
    fmt = args.format or output.suffix.lower().lstrip(".")
    if fmt not in ("mp4", "webm", "gif") or output.suffix.lower() != f".{fmt}":
        raise ValueError("output extension must match format: mp4, webm or gif")
    start, duration = 0.0, info["duration"]
    if args.trim:
        values = args.trim.split(":")
        if len(values) not in (1, 2):
            raise ValueError("trim is START[:DURATION] in seconds, not a timecode")
        start = float(values[0])
        duration = float(values[1]) if len(values) == 2 else info["duration"] - start
        if not all(math.isfinite(n) for n in (start, duration)):
            raise ValueError("trim must be finite")
        if start < 0 or start >= info["duration"] or duration <= 0:
            raise ValueError("trim must select a positive segment within the source")
        if start + duration > info["duration"] + 0.05:
            raise ValueError("trim end exceeds the source duration")
        duration = min(duration, info["duration"] - start)
    if duration > 60:
        raise ValueError("edit one clip of at most 60 seconds; specify --trim")
    if args.loop and fmt != "gif":
        raise ValueError("--loop is GIF playback metadata only; MP4/WebM loop in the player")
    if args.fps is not None and not 1 <= args.fps <= 60:
        raise ValueError("fps must be between 1 and 60")
    if args.max_bytes is not None and args.max_bytes <= 0:
        raise ValueError("max-bytes must be positive")
    w, h = info["display_width"], info["display_height"]
    vf = f"scale={w}:{h},setsar=1"
    if args.size:
        parts = args.size.lower().split("x")
        if len(parts) != 2:
            raise ValueError("size must be WIDTHxHEIGHT")
        w, h = map(int, parts)
        if min(w, h) < 2 or max(w, h) > 4096:
            raise ValueError("size edges must be between 2 and 4096")
        if fmt != "gif" and (w % 2 or h % 2):
            raise ValueError("exact MP4/WebM size must be even; do not silently drop a row")
        if args.fit == "cover":
            vf += f",scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
        else:
            vf += f",scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"
    elif fmt != "gif":
        # Preserve all pixels of odd-sized sources instead of scaling/cropping a row away.
        vf += ",pad=ceil(iw/2)*2:ceil(ih/2)*2:0:0:black"
    vf += ",setsar=1"
    if args.fps is not None or fmt == "gif":
        vf += f",fps={args.fps or 12}"
    if fmt == "gif" and w * h * duration * (args.fps or 12) > 80000000:
        raise ValueError("GIF palette buffer too large; choose smaller --size, --fps or --trim")
    audio = info["audio"] and not args.mute and fmt != "gif"
    common = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", info["path"],
              "-ss", start, "-t", duration, "-map", f"0:{info['video_index']}",
              "-map", "0:a:0?", "-map_metadata", "-1", "-sn", "-dn"]
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".clip-edit-", dir=output.parent) as temp:
        dest = Path(temp) / f"encoded.{fmt}"
        if fmt == "gif":
            palette = f"[0:{info['video_index']}]" + vf + ",split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a[out]"
            # Trim at the decoder: palettegen waits for EOF and buffers the selected
            # frames. Output-side -t would still read/buffer the entire source.
            run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", start,
                 "-t", duration, "-i", info["path"], "-filter_complex", palette,
                 "-map", "[out]", "-an", "-loop", "0" if args.loop else "-1", dest])
        else:
            codec = ["-c:v", "libx264", "-preset", "medium"] if fmt == "mp4" else ["-c:v", "libvpx-vp9"]
            codec += ["-pix_fmt", "yuv420p"]
            if fmt == "mp4":
                codec += ["-movflags", "+faststart"]
            acodec = ["-c:a", "aac" if fmt == "mp4" else "libopus", "-b:a", "96k"] if audio else ["-an"]
            if args.max_bytes:
                rate = int(args.max_bytes * 8 * 0.90 / duration) - (96000 if audio else 0)
                if rate < 16000:
                    raise ValueError("byte cap too small for this duration/audio; shorten or mute explicitly")
                log = str(Path(temp) / "pass")
                base = [*common, "-vf", vf, *codec, "-b:v", rate, "-passlogfile", log]
                run([*base, "-pass", "1", "-an", "-f", "null", os.devnull])
                run([*base, "-pass", "2", *acodec, dest])
            else:
                quality = ["-crf", "23"] if fmt == "mp4" else ["-crf", "32", "-b:v", "0"]
                run([*common, "-vf", vf, *codec, *quality, *acodec, dest])
        result = probe(dest)
        if args.max_bytes and result["bytes"] > args.max_bytes:
            raise ValueError(f"encoded {result['bytes']} bytes exceeds cap {args.max_bytes}; no output published")
        # Decode the complete selected video AND audio; ffprobe alone cannot prove a good render.
        run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", dest,
             "-map", "0:v:0", "-map", "0:a:0?", "-f", "null", os.devnull])
        os.link(dest, output)  # same-filesystem, exclusive publication; fails if output appeared meanwhile
        result.update(path=str(output), within_cap=True if args.max_bytes else None,
                      max_bytes=args.max_bytes, start=start,
                      requested_duration=duration, fit=args.fit if args.size else None,
                      loop_metadata=bool(args.loop),
                      decoded=True, audio_removed=info["audio"] and not audio)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    measure = commands.add_parser("probe", help="measure a local clip")
    measure.add_argument("source")
    review = commands.add_parser("frames", help="sample start/middle/end; review one <=60s clip")
    review.add_argument("source")
    review.add_argument("output", help="new review directory")
    review.add_argument("--count", type=int, choices=range(3, 10), default=3)
    encode = commands.add_parser("edit", help="trim/fit/encode a <=60s segment without overwriting")
    encode.add_argument("source")
    encode.add_argument("output")
    encode.add_argument("--size")
    encode.add_argument("--fit", choices=("contain", "cover"), default="contain")
    encode.add_argument("--trim")
    encode.add_argument("--format", choices=("mp4", "webm", "gif"))
    encode.add_argument("--fps", type=float)
    encode.add_argument("--mute", action="store_true")
    encode.add_argument("--loop", action="store_true", help="GIF playback loop, NOT seamless motion")
    encode.add_argument("--max-bytes", type=int)
    args = parser.parse_args()
    try:
        result = probe(args.source) if args.command == "probe" else frames(args) if args.command == "frames" else edit(args)
    except (ValueError, OSError, subprocess.CalledProcessError, ZeroDivisionError) as exc:
        detail = exc.stderr[-3000:] if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        parser.exit(1, f"clip-media: {detail}\n")
    print("RESULT: " + json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
