"""media-inspect engine: probe a local media file and pull stills or a contact
sheet into scratch space. Stdlib only; ffprobe/ffmpeg do the media work.

Reads the input, never modifies it, and writes only under the scratch root
(the OS temporary directory), so nothing lands in a deliverable or a
``deliver:`` directory.
"""

from __future__ import annotations

import json
import math
import re
import secrets
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ACTIONS = ("probe", "frames", "sheet")
MAX_FRAMES = 12
MAX_TILES = 24
DEFAULT_TILES = 9
DEFAULT_COLUMNS = 3
DEFAULT_WIDTH = 480
MAX_WIDTH = 1280
TIMEOUT = 120
_URL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


class MediaError(ValueError):
    """A refusal or failure reported to the caller as an error message."""


def scratch_root() -> Path:
    return Path(tempfile.gettempdir()) / "hermes-media-inspect"


def _tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise MediaError(f"{name} is not installed")
    return path


def _source(raw) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise MediaError("path is required")
    if _URL.match(raw.strip()):
        raise MediaError("path must be a local file; URLs are never fetched")
    path = Path(raw.strip()).expanduser()
    if not path.is_file():
        raise MediaError(f"no such file: {path}")
    return path.resolve()


def _run(argv: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(argv, capture_output=True, text=True, timeout=TIMEOUT,
                            stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        tail = (result.stderr or "").strip().splitlines()[-1:] or ["unknown error"]
        raise MediaError(f"{Path(argv[0]).name} failed: {tail[0]}")
    return result


def _rate(value) -> float | None:
    if not isinstance(value, str) or "/" not in value:
        return None
    num, _, den = value.partition("/")
    try:
        num, den = float(num), float(den)
    except ValueError:
        return None
    return round(num / den, 3) if den else None


def probe(path: Path) -> dict:
    raw = json.loads(_run([_tool("ffprobe"), "-v", "error", "-show_format", "-show_streams",
                           "-of", "json", str(path)]).stdout or "{}")
    fmt = raw.get("format") or {}
    streams = []
    for stream in raw.get("streams") or []:
        kind = stream.get("codec_type")
        item = {"index": stream.get("index"), "type": kind, "codec": stream.get("codec_name")}
        if kind == "video":
            item.update(width=stream.get("width"), height=stream.get("height"),
                        fps=_rate(stream.get("avg_frame_rate")) or _rate(stream.get("r_frame_rate")),
                        frames=int(stream["nb_frames"]) if str(stream.get("nb_frames", "")).isdigit() else None)
        elif kind == "audio":
            item.update(sample_rate=int(stream["sample_rate"]) if str(stream.get("sample_rate", "")).isdigit() else None,
                        channels=stream.get("channels"))
        streams.append(item)
    duration = fmt.get("duration")
    return {"path": str(path), "format": fmt.get("format_name"),
            "duration": round(float(duration), 3) if duration not in (None, "N/A") else None,
            "size_bytes": int(fmt["size"]) if str(fmt.get("size", "")).isdigit() else path.stat().st_size,
            "streams": streams}


def _video(info: dict) -> dict:
    video = next((s for s in info["streams"] if s["type"] == "video"), None)
    if video is None:
        raise MediaError("the file has no video or image stream")
    return video


def _out_dir(profile: str) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = scratch_root() / (profile or "unknown") / f"{stamp}-{secrets.token_hex(3)}"
    out.mkdir(parents=True, exist_ok=False)
    return out


def _times(args: dict, info: dict, limit: int) -> list[float]:
    times, frames = args.get("times"), args.get("frames")
    if times is not None and frames is not None:
        raise MediaError("give times or frames, not both")
    duration = info.get("duration")
    if frames is not None:
        fps = _video(info).get("fps")
        if not fps:
            raise MediaError("frame numbers need a known frame rate; give times instead")
        if not isinstance(frames, list) or not all(isinstance(n, int) and n >= 0 for n in frames):
            raise MediaError("frames must be a list of non-negative integers")
        times = [n / fps for n in frames]
    if times is None:
        return []
    if not isinstance(times, list) or not times or not all(isinstance(t, (int, float)) and t >= 0 for t in times):
        raise MediaError("times must be a non-empty list of non-negative seconds")
    if len(times) > limit:
        raise MediaError(f"at most {limit} positions per call")
    if duration is not None and any(t > duration for t in times):
        raise MediaError(f"a position is past the end ({duration} s)")
    return [round(float(t), 3) for t in times]


def _grab(source: Path, at: float, target: Path, width: int | None, still: bool) -> None:
    argv = [_tool("ffmpeg"), "-v", "error", "-y"]
    if not still:
        argv += ["-ss", f"{at:.3f}"]
    argv += ["-i", str(source), "-frames:v", "1"]
    if width:
        argv += ["-vf", f"scale={width}:-2"]
    _run(argv + [str(target)])


def frames(path: Path, args: dict, profile: str) -> dict:
    info = probe(path)
    video = _video(info)
    times = _times(args, info, MAX_FRAMES)
    if not times:
        raise MediaError("frames needs times or frames")
    still = info.get("duration") in (None, 0) or not video.get("fps")
    out = _out_dir(profile)
    shots = []
    for i, at in enumerate(times, 1):
        target = out / f"frame-{i:02d}-{at:08.3f}s.png"
        _grab(path, at, target, None, still)
        shots.append({"time": at, "path": str(target)})
    return {"path": str(path), "dir": str(out), "frames": shots}


def sheet(path: Path, args: dict, profile: str) -> dict:
    info = probe(path)
    _video(info)
    duration = info.get("duration")
    times = _times(args, info, MAX_TILES)
    if not times:
        count = args.get("count", DEFAULT_TILES)
        if not isinstance(count, int) or not 1 <= count <= MAX_TILES:
            raise MediaError(f"count must be 1..{MAX_TILES}")
        if not duration:
            raise MediaError("a sheet of evenly spaced positions needs a duration; give times")
        step = duration / count
        times = [round(step * i + step / 2, 3) for i in range(count)]
    columns = args.get("columns", DEFAULT_COLUMNS)
    width = args.get("width", DEFAULT_WIDTH)
    if not isinstance(columns, int) or not 1 <= columns <= 8:
        raise MediaError("columns must be 1..8")
    if not isinstance(width, int) or not 64 <= width <= MAX_WIDTH:
        raise MediaError(f"width must be 64..{MAX_WIDTH}")
    out = _out_dir(profile)
    tiles = []
    for i, at in enumerate(times, 1):
        target = out / f"tile-{i:02d}.png"
        _grab(path, at, target, width, False)
        tiles.append(target)
    rows = math.ceil(len(tiles) / columns)
    sheet_path = out / "sheet.png"
    argv = [_tool("ffmpeg"), "-v", "error", "-y"]
    for tile in tiles:
        argv += ["-i", str(tile)]
    if len(tiles) == 1:
        shutil.copyfile(tiles[0], sheet_path)
    else:
        # Same-width tiles; pad each row to the widest grid cell so xstack can place them.
        layout = "|".join(
            f"{'+'.join(['w0'] * (i % columns)) or '0'}_{'+'.join(['h0'] * (i // columns)) or '0'}"
            for i in range(len(tiles)))
        inputs = "".join(f"[{i}:v]" for i in range(len(tiles)))
        _run(argv + ["-filter_complex", f"{inputs}xstack=inputs={len(tiles)}:layout={layout}:fill=black",
                     str(sheet_path)])
    grid = [{"tile": i + 1, "row": i // columns + 1, "column": i % columns + 1, "time": t}
            for i, t in enumerate(times)]
    return {"path": str(path), "dir": str(out), "sheet": str(sheet_path), "columns": columns,
            "rows": rows, "tiles": grid}


def run(args: dict, profile: str, allowed: tuple[str, ...] = ACTIONS) -> dict:
    if not isinstance(args, dict):
        raise MediaError("arguments must be an object")
    action = args.get("action")
    if action not in ACTIONS:
        raise MediaError(f"action must be one of {', '.join(ACTIONS)}")
    if action not in allowed:
        raise MediaError(f"{action} is not offered to this profile")
    source = _source(args.get("path"))
    if action == "probe":
        return probe(source)
    if action == "frames":
        return frames(source, args, profile)
    return sheet(source, args, profile)


def cleanup(older_than_days: float = 7, now: float | None = None) -> int:
    """Remove scratch runs older than the cutoff; returns how many went."""
    root = scratch_root()
    if not root.is_dir():
        return 0
    cutoff = (now or time.time()) - older_than_days * 86400
    removed = 0
    for profile_dir in root.iterdir():
        if not profile_dir.is_dir() or profile_dir.is_symlink():
            continue
        for run_dir in profile_dir.iterdir():
            if run_dir.is_dir() and not run_dir.is_symlink() and run_dir.stat().st_mtime < cutoff:
                shutil.rmtree(run_dir, ignore_errors=True)
                removed += 1
    return removed

