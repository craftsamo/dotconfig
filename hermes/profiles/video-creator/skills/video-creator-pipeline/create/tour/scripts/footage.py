#!/usr/bin/env python3
"""Bounded local footage preparation; raw evidence never goes in the final bundle."""

import argparse
import hashlib
import json
from pathlib import Path

from tour import command, fresh, image, load, local, number, require, write

VIDEO = {".mp4", ".mov", ".webm", ".mkv"}
STILL = {".png", ".jpg", ".jpeg", ".webp"}


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def media_path(value):
    require(isinstance(value, str) and "://" not in value, "local media only")
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts, "absolute physical media path required")
    require(not any(p.is_symlink() for p in (path, *path.parents)), "media symlinks forbidden")
    require(path.is_file() and path.suffix.lower() in VIDEO | STILL, "unsupported local media")
    require(0 < path.stat().st_size <= 512_000_000, "raw media limit is 512 MB")
    return path


def probe(path, decode=False):
    if path.suffix.lower() in STILL:
        width, height = image(path)
        return {"kind": "image", "width": width, "height": height, "audio": False}
    data = json.loads(command(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
                               "-show_streams", "-show_format", "-of", "json", str(path)], timeout=180))
    videos = [s for s in data["streams"] if s["codec_type"] == "video"]
    require(len(videos) == 1, "exactly one video stream required")
    video = videos[0]
    require(not video.get("disposition", {}).get("attached_pic"), "cover art is not footage")
    width, height = video["width"], video["height"]
    require(32 <= width <= 4096 and 32 <= height <= 4096 and width * height <= 8_847_360,
            "footage exceeds pixel bounds")
    number(float(data["format"]["duration"]), .1, 300, "raw container duration")
    def stream_duration(stream):
        value = stream.get("duration")
        if value is None:
            parts = stream.get("tags", {}).get("DURATION", "").split(":")
            require(len(parts) == 3, "stream duration unknown; normalize local media before use")
            value = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        return number(float(value), .1, 300, "raw stream duration")
    duration = stream_duration(video)
    audios = [s for s in data["streams"] if s["codec_type"] == "audio"]
    require(len(audios) <= 1, "select one audio stream before supplying footage")
    require(not any(s.get("rotation", 0) for s in video.get("side_data_list", [])),
            "normalize rotation before supplying footage")
    if decode:
        command(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-protocol_whitelist", "file,pipe",
                 "-i", str(path), "-f", "null", "-"], timeout=360)
    return {"kind": "video", "width": width, "height": height, "duration": duration,
            "audio": bool(audios), "audio_duration": stream_duration(audios[0]) if audios else 0}


def prepare(manifest, output):
    raw = load(local(manifest, {".json"}))
    require(isinstance(raw, dict) and "clips" in raw and set(raw) <= {"clips", "capture_receipt"}, "source manifest needs clips and optional capture_receipt")
    clips = raw["clips"]
    require(isinstance(clips, list) and 1 <= len(clips) <= 20, "1..20 source clips required")
    validated = []
    for clip in clips:
        require(isinstance(clip, dict) and set(clip) == {"id", "path", "sha256", "source_start", "duration", "timeline_start", "audio"},
                "invalid source clip fields")
        from tour import identifier
        identifier(clip["id"])
        path = media_path(clip["path"])
        require(sha256(path) == clip["sha256"], "raw source hash changed")
        info = probe(path, decode=True)
        start = number(clip["source_start"], 0, 300, "source start")
        duration = number(clip["duration"], .1, 60, "clip duration")
        at = number(clip["timeline_start"], 0, 60 - duration, "timeline start")
        require(clip["audio"] in ("keep", "mute"), "explicit keep/mute audio policy required")
        require(clip["audio"] != "keep" or info["audio"], "keep requested but source has no audio")
        if clip["audio"] == "keep":
            require(start + duration <= info["audio_duration"] + .001, "kept audio source range exceeds stream")
        require(start + duration <= info.get("duration", duration) + .001, "source range exceeds media")
        if info["kind"] == "image":
            require(start == 0, "still source start must be zero")
        validated.append((clip, path, info, at))
    require(len({c[0]["id"] for c in validated}) == len(clips), "duplicate clip id")
    require(sum(p.stat().st_size for _, p, _, _ in validated) <= 1_024_000_000, "raw input budget exceeds 1 GB")
    out = fresh(output)
    out.mkdir(mode=0o700)
    records = []
    for clip, path, info, at in validated:
        dest = out / (clip["id"] + (".mp4" if info["kind"] == "video" else path.suffix.lower()))
        if info["kind"] == "video":
            cmd = ["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-n", "-protocol_whitelist", "file,pipe",
                   "-i", str(path), "-ss", str(clip["source_start"]), "-t", str(clip["duration"]),
                   "-map", "0:v:0", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
                   "-r", "30", "-map_metadata", "-1"]
            cmd += ["-map", "0:a:0", "-c:a", "aac"] if clip["audio"] == "keep" else ["-an"]
            command(cmd + ["-movflags", "+faststart", str(dest)], timeout=360)
            cooked = probe(dest, decode=True)
            require(abs(cooked["duration"] - clip["duration"]) < .1, "prepared duration mismatch")
        else:
            # Re-encode to remove EXIF/private metadata, not to replace moving footage.
            from PIL import Image
            with Image.open(path) as im:
                im.convert("RGB").save(dest)
        require(dest.stat().st_size <= 64_000_000, "prepared asset exceeds 64 MB")
        require(sha256(path) == clip["sha256"], "raw changed during preparation")
        records.append({**clip, "path": dest.name, "raw_sha256": clip["sha256"],
                        "sha256": sha256(dest), "kind": info["kind"], "media_start": 0})
    write(out / "media.json", {"version": 1, "clips": records})
    return {"media": str(out / "media.json"), "clips": len(records)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.manifest, args.out)))
