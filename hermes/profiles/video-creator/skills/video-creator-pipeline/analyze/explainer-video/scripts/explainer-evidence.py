#!/usr/bin/env python3
"""Local evidence for reviewing one explainer video (<= 600 s). Never uploads or judges.

    overview <source> <out> [--fps 1] [--cut-threshold 0.3]
        stills every 1/fps s plus 0.5 s steps around detected cuts, 3x3 contact
        sheets (time label bottom-right) and evidence.json
    window   <source> <out> --start S [--duration 2] [--step 0.3]
        dense re-sample of at most 4 s / 16 frames, with one sheet
    detail   <source> <out> --at T [--crop X0 Y0 X1 Y1] [--scale 2]
        one native frame and, optionally, an enlarged crop of it
    measure  <frame> --box X0 Y0 X1 Y1 [--ink bright|dark] [--threshold 60]
        text line heights in the box by pixel row projection, also as px at 1080p

Every <out> must be new; a fresh directory per look keeps each image a new file.
Prints RESULT: <JSON>.
"""

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageOps

HELPER = Path(__file__).resolve().parents[3] / "scripts/clip-media.py"
SPEC = importlib.util.spec_from_file_location("explainer_clip_media", HELPER)
MEDIA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MEDIA)

MAX_SECONDS = 600
MAX_CUTS = 40  # at most 160 extra stills; more cuts are thinned evenly and disclosed
TILE = (640, 360)
LABEL_H = 28
CUT_TIME = re.compile(r"pts_time:([0-9.]+)")


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def clock(seconds):
    minutes, rest = divmod(round(seconds, 1), 60)
    return f"{int(minutes)}:{rest:04.1f}"


def new_output(path):
    out = Path(path).expanduser().absolute()
    if ".." in out.parts or any(p.is_symlink() for p in (out, *out.parents)):
        raise ValueError("output traversal/symlinks forbidden")
    if out.exists() or not out.parent.is_dir():
        raise ValueError("output must be new, with an existing parent directory")
    return out


def checked_source(path):
    source = Path(path).expanduser().resolve(strict=True)
    info = MEDIA.probe(source)
    if info["duration"] > MAX_SECONDS:
        raise ValueError(f"source is longer than {MAX_SECONDS} s; ask for a segment")
    w, h = info["display_width"], info["display_height"]
    if max(w, h) > 4096 or w * h > 9_000_000:
        raise ValueError("source dimensions exceed bounded native review; request a proxy")
    return source, info


def grab(info, at, dest):
    MEDIA.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{at:.3f}", "-i", info["path"],
               "-map", f"0:{info['video_index']}", "-frames:v", "1",
               "-vf", f"scale={info['display_width']}:{info['display_height']},setsar=1", dest])
    if not Path(dest).is_file():
        raise ValueError(f"no frame decoded at {at:.3f} s")


def last_time(info):
    return max(0.0, info["duration"] - max(1 / info["fps"], 0.05))


def sheets(frames, temp, prefix):
    """3x3 sheets; the label sits bottom-right so header areas stay visible."""
    out = []
    for page in range(math.ceil(len(frames) / 9)):
        tiles = frames[page * 9:(page + 1) * 9]
        cols = min(3, len(tiles))
        rows = math.ceil(len(tiles) / 3)
        sheet = Image.new("RGB", (TILE[0] * cols, (TILE[1] + LABEL_H) * rows), "#202020")
        draw = ImageDraw.Draw(sheet)
        for i, (at, path) in enumerate(tiles):
            with Image.open(path) as picture:
                small = ImageOps.contain(picture.convert("RGB"), TILE)
            x, y = (i % 3) * TILE[0], (i // 3) * (TILE[1] + LABEL_H)
            sheet.paste(small, (x + (TILE[0] - small.width) // 2, y))
            label = clock(at)
            draw.text((x + TILE[0] - 8 - 7 * len(label), y + TILE[1] + 8), label, fill="white")
        name = f"{prefix}-{page:02}.png"
        sheet.save(temp / name)
        out.append({"file": name, "from": tiles[0][0], "to": tiles[-1][0]})
    return out


def detect_cuts(info, threshold):
    result = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "info", "-i", info["path"], "-map", f"0:{info['video_index']}",
         "-vf", f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
        capture_output=True, text=True, check=True)
    return sorted({round(float(m.group(1)), 3) for m in CUT_TIME.finditer(result.stderr)})


def publish(temp, out, manifest):
    (temp / "evidence.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    out.mkdir()
    for item in temp.iterdir():
        item.rename(out / item.name)


def overview(args):
    source, info = checked_source(args.source)
    out = new_output(args.output)
    if not 0.2 <= args.fps <= 2:
        raise ValueError("fps must be 0.2..2")
    source_hash = sha256(source)
    end = last_time(info)
    with tempfile.TemporaryDirectory(prefix=".explainer-evidence-", dir=out.parent) as tmp:
        temp = Path(tmp)
        (temp / "f").mkdir()
        MEDIA.run(["ffmpeg", "-nostdin", "-v", "error", "-i", info["path"],
                   "-map", f"0:{info['video_index']}",
                   "-vf", f"fps={args.fps},scale={info['display_width']}:{info['display_height']},setsar=1",
                   "-start_number", "0", temp / "f" / "s%04d.png"])
        regular = []
        for path in sorted((temp / "f").glob("s*.png")):
            at = int(path.stem[1:]) / args.fps
            if at <= end + 1 / args.fps:
                regular.append((round(min(at, end), 3), path))
        cuts = detect_cuts(info, args.cut_threshold)
        sampled = cuts
        if len(cuts) > MAX_CUTS:
            step = len(cuts) / MAX_CUTS
            sampled = [cuts[int(i * step)] for i in range(MAX_CUTS)]
        near = []
        (temp / "c").mkdir()
        taken = [at for at, _ in regular]
        for cut in sampled:
            for offset in (-1.0, -0.5, 0.5, 1.0):
                at = round(min(max(cut + offset, 0.0), end), 3)
                if any(abs(at - t) < 0.2 for t in taken):
                    continue
                dest = temp / "c" / f"c{at:08.3f}.png"
                grab(info, at, dest)
                taken.append(at)
                near.append((at, dest))
        regular_sheets = sheets(regular, temp, "sheet")
        cut_sheets = sheets(sorted(near), temp, "cuts") if near else []
        if sha256(source) != source_hash:
            raise ValueError("source changed during extraction; no evidence published")
        manifest = {
            "version": 1, "source": str(source), "source_sha256": source_hash, "probe": info,
            "fps": args.fps,
            "frames": [{"seconds": at, "file": str(p.relative_to(temp))} for at, p in regular],
            "cuts": cuts,
            "cuts_sampled": sampled if sampled is not cuts else None,
            "cut_frames": [{"seconds": at, "file": str(p.relative_to(temp))} for at, p in sorted(near)],
            "sheets": regular_sheets, "cut_sheets": cut_sheets,
            "coverage": "sampled stills, not continuous playback; times are seek positions",
            "audio": "not reviewed here",
            "remote_calls": 0, "media_generation": 0,
        }
        publish(temp, out, manifest)
    return {"evidence": str(out / "evidence.json"), "frames": len(regular), "cuts": len(cuts),
            "cuts_with_stills": len(sampled), "cut_frames": len(near),
            "sheets": len(regular_sheets) + len(cut_sheets)}


def window(args):
    source, info = checked_source(args.source)
    out = new_output(args.output)
    end = last_time(info)
    if not (0 <= args.start <= end and 0 < args.duration <= 4 and 0.1 <= args.step <= 1):
        raise ValueError("window must start inside the source, last at most 4 s, step 0.1..1 s")
    count = int(args.duration / args.step) + 1
    if count > 16:
        raise ValueError("a window holds at most 16 frames; shorten it or widen the step")
    times = sorted({round(min(args.start + i * args.step, end), 3) for i in range(count)})
    with tempfile.TemporaryDirectory(prefix=".explainer-window-", dir=out.parent) as tmp:
        temp = Path(tmp)
        frames = []
        for at in times:
            dest = temp / f"w{at:08.3f}.png"
            grab(info, at, dest)
            frames.append((at, dest))
        made = sheets(frames, temp, "window")
        publish(temp, out, {"version": 1, "source": str(source), "mode": "window",
                            "frames": [{"seconds": at, "file": p.name} for at, p in frames],
                            "sheets": made})
    return {"evidence": str(out / "evidence.json"), "frames": len(times), "sheets": len(made)}


def detail(args):
    source, info = checked_source(args.source)
    out = new_output(args.output)
    if not 0 <= args.at <= last_time(info):
        raise ValueError("detail time must select a decodable frame inside the source")
    with tempfile.TemporaryDirectory(prefix=".explainer-detail-", dir=out.parent) as tmp:
        temp = Path(tmp)
        frame = temp / f"d{args.at:08.3f}.png"
        grab(info, args.at, frame)
        files = [frame.name]
        if args.crop:
            x0, y0, x1, y1 = args.crop
            with Image.open(frame) as picture:
                if not (0 <= x0 < x1 <= picture.width and 0 <= y0 < y1 <= picture.height):
                    raise ValueError("crop must lie inside the frame")
                if not 1 <= args.scale <= 4:
                    raise ValueError("scale must be 1..4")
                crop = picture.crop((x0, y0, x1, y1))
                crop = crop.resize((crop.width * args.scale, crop.height * args.scale), Image.LANCZOS)
                name = f"d{args.at:08.3f}-crop-{x0}-{y0}-{x1}-{y1}.png"
                crop.save(temp / name)
                files.append(name)
        publish(temp, out, {"version": 1, "source": str(source), "mode": "detail",
                            "seconds": args.at, "crop": args.crop, "files": files})
    return {"evidence": str(out / "evidence.json"), "files": [str(out / f) for f in files]}


def measure(args):
    frame = Path(args.frame).expanduser().resolve(strict=True)
    if "-crop-" in frame.name:
        raise ValueError("measure a native frame, not an enlarged crop: heights scale with the frame")
    with Image.open(frame) as picture:
        gray = picture.convert("L")
        x0, y0, x1, y1 = args.box
        if not (0 <= x0 < x1 <= gray.width and 0 <= y0 < y1 <= gray.height):
            raise ValueError("box must lie inside the frame")
        box = gray.crop((x0, y0, x1, y1))
        frame_height = gray.height
    width, height = box.size
    pixels = box.load()
    border = sorted([pixels[x, 0] for x in range(width)] + [pixels[x, height - 1] for x in range(width)]
                    + [pixels[0, y] for y in range(height)] + [pixels[width - 1, y] for y in range(height)])
    background = border[len(border) // 2]
    minimum = max(2, width // 100)
    ink_rows = []
    for y in range(height):
        count = 0
        for x in range(width):
            value = pixels[x, y]
            if (value - background if args.ink == "bright" else background - value) > args.threshold:
                count += 1
        ink_rows.append(count >= minimum)
    lines, start = [], None
    for y, ink in enumerate(ink_rows + [False]):
        if ink and start is None:
            start = y
        elif not ink and start is not None:
            lines.append({"top": y0 + start, "bottom": y0 + y - 1, "height_px": y - start,
                          "height_at_1080p": round((y - start) * 1080 / frame_height, 1)})
            start = None
    return {"frame": str(frame), "box": args.box, "ink": args.ink, "background_luma": background,
            "frame_height": frame_height, "lines": lines,
            "note": "row projection of the box; separate overlapping lines with a tighter box"}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("overview")
    p.add_argument("source")
    p.add_argument("output")
    p.add_argument("--fps", type=float, default=1.0)
    p.add_argument("--cut-threshold", type=float, default=0.3)
    p.set_defaults(func=overview)
    p = sub.add_parser("window")
    p.add_argument("source")
    p.add_argument("output")
    p.add_argument("--start", type=float, required=True)
    p.add_argument("--duration", type=float, default=2.0)
    p.add_argument("--step", type=float, default=0.3)
    p.set_defaults(func=window)
    p = sub.add_parser("detail")
    p.add_argument("source")
    p.add_argument("output")
    p.add_argument("--at", type=float, required=True)
    p.add_argument("--crop", type=int, nargs=4, metavar=("X0", "Y0", "X1", "Y1"))
    p.add_argument("--scale", type=int, default=2)
    p.set_defaults(func=detail)
    p = sub.add_parser("measure")
    p.add_argument("frame")
    p.add_argument("--box", type=int, nargs=4, metavar=("X0", "Y0", "X1", "Y1"), required=True)
    p.add_argument("--ink", choices=("bright", "dark"), default="bright")
    p.add_argument("--threshold", type=int, default=60)
    p.set_defaults(func=measure)
    args = parser.parse_args()
    try:
        print("RESULT: " + json.dumps(args.func(args), ensure_ascii=False))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"explainer-evidence: {exc}\n")


if __name__ == "__main__":
    main()
