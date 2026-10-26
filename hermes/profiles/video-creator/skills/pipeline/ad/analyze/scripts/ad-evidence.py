#!/usr/bin/env python3
"""Bounded, local advertising review evidence. Never upload or judge a video."""

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile

from PIL import Image, ImageDraw, ImageOps

HELPER = Path(__file__).resolve().parents[3] / "scripts/clip-media.py"
SPEC = importlib.util.spec_from_file_location("ad_clip_media", HELPER)
MEDIA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MEDIA)


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def sample_times(info, mode, count=30, start=0, duration=2, at=0):
    total, fps = info["duration"], info["fps"]
    if not math.isfinite(total) or not 0 < total <= 60:
        raise ValueError("select a source segment of at most 60 seconds first")
    last = max(0, total - max(1 / fps, .05))
    if mode == "detail":
        if not math.isfinite(at) or not 0 <= at <= last:
            raise ValueError("detail time must select a decodable frame inside the source")
        return [at]
    limit = 16 if mode == "window" else 60
    if type(count) is not int or not 3 <= count <= limit:
        raise ValueError(f"count must be 3..{limit}")
    end = last
    if mode == "window":
        if not all(math.isfinite(v) for v in (start, duration)) or not (
            0 <= start < last and 0 < duration <= 3 and start + duration <= total
        ):
            raise ValueError("window must be within source and at most 3 seconds")
        end = min(start + duration, last)
    else:
        start = 0
    return [round(start + (end - start) * i / (count - 1), 6) for i in range(count)]


def collect(args):
    source = Path(args.source).expanduser().resolve(strict=True)
    out = Path(args.output).expanduser().absolute()
    if ".." in out.parts or any(p.is_symlink() for p in (out, *out.parents)):
        raise ValueError("output traversal/symlinks forbidden")
    if out.exists() or not out.parent.is_dir():
        raise ValueError("output must be new, with an existing absolute parent")
    if source.stat().st_size > 512_000_000:
        raise ValueError("source exceeds 512 MB")
    source_hash = sha256(source)
    info = MEDIA.probe(source)
    w, h = info["display_width"], info["display_height"]
    if max(w, h) > 4096 or w * h > 9_000_000:
        raise ValueError("source dimensions exceed bounded native review; request a proxy")
    times = sample_times(info, args.mode, args.count, args.start, args.duration, args.at)
    with tempfile.TemporaryDirectory(prefix=".ad-evidence-", dir=out.parent) as tmp:
        temp = Path(tmp)
        rows, thumbs = [], []
        for index, at in enumerate(times):
            name = f"frame-{index:02}-{at:09.3f}s.png"
            frame = temp / name
            MEDIA.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(source),
                       "-ss", str(at), "-map", f"0:{info['video_index']}",
                       "-frames:v", "1", "-vf", f"scale={w}:{h},setsar=1", str(frame)])
            with Image.open(frame) as picture:
                picture.load()
                thumb = Image.new("RGB", (240, 344), "#292929")
                small = ImageOps.contain(picture.convert("RGB"), (232, 310))
                thumb.paste(small, ((240 - small.width) // 2, (312 - small.height) // 2))
                ImageDraw.Draw(thumb).text((8, 320), f"{index:02}  seek {at:.3f}s", fill="white")
                thumbs.append(thumb)
            rows.append({"seek_seconds": at, "file": name, "sha256": sha256(frame)})
        sheets = []
        for page in range(math.ceil(len(thumbs) / 12)):
            tiles = thumbs[page * 12:(page + 1) * 12]
            sheet = Image.new("RGB", (240 * min(4, len(tiles)), 344 * math.ceil(len(tiles) / 4)), "#292929")
            for i, thumb in enumerate(tiles):
                sheet.paste(thumb, ((i % 4) * 240, (i // 4) * 344))
            name = f"sheet-{page:02}.png"
            sheet.save(temp / name)
            sheets.append({"file": name, "sha256": sha256(temp / name)})
        if sha256(source) != source_hash:
            raise ValueError("source changed during extraction; no evidence published")
        manifest = {
            "version": 1, "source": str(source), "source_sha256": source_hash,
            "probe": info, "mode": args.mode, "frames": rows, "sheets": sheets,
            "coverage": "sampled, not exhaustive; times are seek positions, not exact PTS",
            "audio": "presence measured only; listening/transcript/sync unverified",
            "remote_calls": 0, "media_generation": 0,
        }
        (temp / "evidence.json").write_text(json.dumps(manifest, indent=2) + "\n")
        # Reserve the final directory rather than merging into another job's evidence.
        out.mkdir()
        for item in temp.iterdir():
            item.rename(out / item.name)
    return {"evidence": str(out / "evidence.json"), "frames": len(rows), "sheets": len(sheets)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("overview", "window", "detail"))
    parser.add_argument("source")
    parser.add_argument("output")
    parser.add_argument("--count", type=int, default=None)
    parser.add_argument("--start", type=float, default=0)
    parser.add_argument("--duration", type=float, default=2)
    parser.add_argument("--at", type=float, default=0)
    args = parser.parse_args()
    if args.count is None:
        args.count = 8 if args.mode == "window" else 30
    try:
        print("RESULT: " + json.dumps(collect(args)))
    except (ValueError, OSError) as exc:
        parser.exit(1, f"ad-evidence: {exc}\n")


if __name__ == "__main__":
    main()
