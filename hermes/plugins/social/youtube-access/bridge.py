"""youtube-access bridge: one yt-dlp read, run by the engine venv's interpreter (not Hermes').

The engine (``ya.py``) writes one JSON request to stdin and reads one JSON reply from stdout.
It only ever hands over an 11-character video id; the URL is built here, so yt-dlp never sees
another site or a playlist. No cookies and no login: public videos only. Deno (on PATH) solves
YouTube's player challenges through the yt-dlp-ejs package; ffmpeg merges video and audio.
Contract: docs/youtube-access.md.

    {"op": "transcript", "id": VIDEO_ID, "languages": [..]}
    {"op": "download", "id": VIDEO_ID, "kind": "video" | "audio", "max_height": N,
     "dir": ABSOLUTE_DIR, "max_bytes": N}
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
WARNINGS: list[str] = []
INFO_KEYS = ("id", "title", "channel", "channel_id", "uploader_id", "duration", "upload_date", "language",
             "view_count", "live_status")


class Refused(Exception):
    pass


class Logger:
    """yt-dlp's messages: warnings and errors are kept (short) for the reply, the rest dropped."""

    def debug(self, message):
        pass

    def info(self, message):
        pass

    def warning(self, message):
        WARNINGS.append(str(message)[:300])

    def error(self, message):
        WARNINGS.append(str(message)[:300])


def _url(video_id: str) -> str:
    if not isinstance(video_id, str) or not VIDEO_ID.match(video_id):
        raise Refused("not a video id")
    return f"https://www.youtube.com/watch?v={video_id}"


def _base() -> dict:
    return {"quiet": True, "no_warnings": False, "noprogress": True, "noplaylist": True, "logger": Logger(),
            "socket_timeout": 30, "retries": 3, "extractor_retries": 2, "color": {"stderr": "no_color"}}


def _info(info: dict) -> dict:
    return {key: info.get(key) for key in INFO_KEYS}


def _matches(key: str, wanted: str) -> bool:
    """'en' matches 'en', 'en-US' and 'en-orig'; 'en-US' only itself."""
    key, wanted = key.lower(), wanted.lower()
    return key == wanted or key.startswith(wanted + "-")


def pick_track(info: dict, languages: list[str]) -> tuple[str, str, list[dict]] | None:
    """(language key, kind, formats) of the best caption track: a manual track in a requested
    language, then the spoken language (manual, then speech recognition), then an automatic
    translation into a requested language, then any manual track. ``kind`` is manual, auto or
    translated."""
    manual = {k: v for k, v in (info.get("subtitles") or {}).items() if k != "live_chat" and v}
    auto = {k: v for k, v in (info.get("automatic_captions") or {}).items() if v}
    origs = [k for k in auto if k.endswith("-orig")]
    spoken = info.get("language") or (origs[0][:-5] if origs else None)
    for wanted in languages:
        for key in manual:
            if _matches(key, wanted):
                return key, "manual", manual[key]
    if spoken and (not languages or any(_matches(spoken, w) or _matches(w, spoken) for w in languages)):
        for key in manual:
            if _matches(key, spoken):
                return key, "manual", manual[key]
        for key in (f"{spoken}-orig", spoken):
            if key in auto:
                return key, "auto", auto[key]
    for wanted in languages:
        for key in auto:
            if not key.endswith("-orig") and _matches(key, wanted):
                return key, "translated", auto[key]
    if manual:
        key = next(iter(manual))
        return key, "manual", manual[key]
    for key in origs:
        return key, "auto", auto[key]
    return None


def events(data: dict) -> list[list]:
    """[[start ms, text], …] of a json3 caption document, empty lines dropped."""
    out = []
    for event in data.get("events") or []:
        text = "".join(seg.get("utf8", "") for seg in event.get("segs") or [])
        text = " ".join(text.split())
        if text:
            out.append([int(event.get("tStartMs") or 0), text])
    return out


def transcript(req: dict) -> dict:
    from yt_dlp import YoutubeDL
    languages = [str(x) for x in req.get("languages") or []]
    with YoutubeDL({**_base(), "skip_download": True}) as ydl:
        info = ydl.extract_info(_url(req["id"]), download=False)
        picked = pick_track(info, languages)
        if not picked:
            return {"ok": True, "data": {"info": _info(info), "track": None}}
        key, kind, formats = picked
        chosen = next((f for f in formats if f.get("ext") == "json3"), None)
        if not chosen:
            raise Refused(f"the {key} captions have no json3 form")
        data = json.loads(ydl.urlopen(chosen["url"]).read().decode("utf-8"))
        return {"ok": True, "data": {"info": _info(info), "track": {"language": key, "kind": kind,
                                                                     "events": events(data)}}}


def selected_size(info: dict) -> int | None:
    """Bytes of the formats yt-dlp selected (merged parts summed), exact or approximate; None when
    any part does not say."""
    parts = info.get("requested_formats") or [info]
    sizes = [p.get("filesize") or p.get("filesize_approx") for p in parts]
    return sum(sizes) if sizes and all(sizes) else None


def download(req: dict) -> dict:
    from yt_dlp import YoutubeDL
    folder = Path(req["dir"])
    if not folder.is_absolute():
        raise Refused("the download folder must be absolute")
    height = int(req.get("max_height") or 1080)
    if req.get("kind") == "audio":
        fmt = "bestaudio[ext=m4a]/bestaudio"
        options = {}
    else:
        fmt = (f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}][ext=mp4]"
               f"/bestvideo[height<={height}]+bestaudio/best[height<={height}]")
        options = {"merge_output_format": "mp4"}
    opts = {**_base(), **options, "format": fmt, "outtmpl": str(folder / "%(id)s.%(ext)s"),
            "max_filesize": int(req["max_bytes"]), "overwrites": False, "restrictfilenames": True,
            "writethumbnail": False, "writesubtitles": False}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(_url(req["id"]), download=False)
        if info.get("live_status") in ("is_live", "is_upcoming", "post_live"):
            raise Refused(f"the video is {info['live_status'].replace('_', ' ')}; only finished videos download")
        if info.get("duration") and req.get("max_seconds") and info["duration"] > int(req["max_seconds"]):
            raise Refused(f"the video runs {info['duration']} s, longer than the {req['max_seconds']} s limit")
        limit = int(req["max_bytes"])
        expected = selected_size(info)
        if expected and expected > limit:
            raise Refused(f"the selected streams come to about {expected // 1024 ** 2} MB, over the "
                          f"{limit // 1024 ** 2} MB limit; pick a lower max_height or kind=audio")
        folder.mkdir(parents=True, exist_ok=True)
        done = ydl.process_ie_result(info, download=True)
    files = []
    for item in done.get("requested_downloads") or []:
        path = Path(item.get("filepath") or "")
        if path.is_file():
            files.append({"path": str(path), "bytes": path.stat().st_size})
    if not files:
        raise Refused("nothing was downloaded (the file may exceed the size limit)")
    if sum(f["bytes"] for f in files) > limit:  # streamed formats are not capped while they download
        for f in files:
            Path(f["path"]).unlink(missing_ok=True)
        raise Refused(f"the download came to more than the {limit // 1024 ** 2} MB limit and was deleted")
    return {"ok": True, "data": {"info": _info(done), "files": files}}


def main(req: dict) -> dict:
    op = req.get("op")
    if op == "transcript":
        return transcript(req)
    if op == "download":
        return download(req)
    raise Refused(f"unknown op {op!r}")


if __name__ == "__main__":
    try:
        reply = main(json.loads(sys.stdin.read()))
    except Refused as exc:
        reply = {"ok": False, "kind": "refused", "error": str(exc)[:500]}
    except Exception as exc:  # reported to the engine, never a traceback on stdout
        reply = {"ok": False, "kind": "error", "error": f"{type(exc).__name__}: {exc}"[:500]}
    reply["warnings"] = WARNINGS[-10:]
    sys.stdout.write(json.dumps(reply, ensure_ascii=False, default=str))
