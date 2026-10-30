"""audio-analyze — whole-recording audio analysis on config-driven backends.

``audio_analyze`` sends one recording, whole, to an audio-capable model and returns its answer:
what is said (and by how many voices), tone, music and other sounds, with no local transcription
or splitting first. The recording leaves the machine, so the tool is for a request that asked for
it; local analysis (Whisper, the speech and music leaves) stays the default where privacy matters.

Backends come from a top-level ``audio_analyze:`` section of ``config.yaml``, tried in order
(``plugins/_shared/media_backends.py``)::

    audio_analyze:
      backends:
        - {provider: openrouter, model: google/gemini-3.8-flash}

OpenRouter's Gemini Flash is the default when the section is absent.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _shared(name, filename):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[2] / "_shared" / filename)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


tool_preview = _shared("hermes_tool_preview", "tool_preview.py")
media_backends = _shared("hermes_media_backends", "media_backends.py")

_DEFAULT_BACKEND = ("openrouter", "google/gemini-3.8-flash")
# The recording rides inline in one request, base64 (a third larger), and Gemini takes about
# 20 MB per request: 14 MiB stays under it with the prompt; a longer recording is trimmed or
# re-encoded first.
MAX_AUDIO_BYTES = 14 * 1024 * 1024
# input_audio formats every backend here takes; an .opus file is Ogg Opus. WebM and other
# containers are re-encoded first.
FORMATS = {".wav": "wav", ".mp3": "mp3", ".m4a": "m4a", ".aac": "aac", ".ogg": "ogg", ".oga": "ogg",
           ".opus": "ogg", ".flac": "flac", ".aiff": "aiff", ".aif": "aiff"}

_PROMPT = (
    "Listen to the whole recording. Describe what is said (who speaks and how many voices, in the "
    "language spoken), the tone, and any music or other sounds, with approximate timestamps. Then "
    "answer the following question:\n\n{question}"
)

AUDIO_ANALYZE_SCHEMA = {
    "name": "audio_analyze",
    "description": (
        "Send one audio recording, whole, to an external audio-capable model and return its answer: "
        "speech (with speakers and timestamps), tone, music and other sounds. Use it when the user "
        "asked for the recording to be analyzed this way; it leaves this machine. Accepts a local "
        "file path or an http(s) URL of wav, mp3, m4a, aac, ogg, opus, flac or aiff, up to "
        "14 MB; trim or re-encode a longer recording (or another format, such as webm) first."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "audio_url": {"type": "string", "description": "Local file path, file:// URL or http(s) URL of the recording."},
            "question": {"type": "string", "description": "What to find out about the recording."},
        },
        "required": ["audio_url", "question"],
    },
}


def _backends() -> list[tuple[str, str]]:
    """The ``audio_analyze:`` backends of the active profile's config, in order."""
    return media_backends.configured_backends("audio_analyze", _DEFAULT_BACKEND)


def _error(message: str, **extra: Any) -> str:
    return json.dumps({"success": False, "error": message, **extra}, indent=2, ensure_ascii=False)


async def _materialize(source: str) -> tuple[Path, bool]:
    """``(path, downloaded)`` for a local file or an http(s) URL; raises ``ValueError`` otherwise."""
    local = Path(os.path.expanduser(source.removeprefix("file://")))
    if local.is_file():
        return local, False
    if not source.startswith(("http://", "https://")):
        raise ValueError("Invalid audio source. Provide an HTTP/HTTPS URL or a local file path.")
    from hermes_constants import get_hermes_dir
    from tools.vision_tools import _download_media, _validate_image_url_async
    from tools.website_policy import check_website_access

    if not await _validate_image_url_async(source):
        raise ValueError("Invalid audio source. Provide an HTTP/HTTPS URL or a local file path.")
    if blocked := check_website_access(source):
        raise ValueError(blocked["message"])
    suffix = Path(urlparse(source).path).suffix.lower()
    if suffix not in FORMATS:
        raise ValueError(f"Unsupported audio format: '{suffix or 'none'}'. Use a URL ending in a supported "
                         "extension, or download the file first.")
    path = get_hermes_dir("cache/audio", "temp_audio_files") / f"temp_audio_{uuid.uuid4()}{suffix}"
    await _download_media(source, path, 3, media_label="Audio", accept="audio/*,*/*;q=0.8",
                          max_bytes=MAX_AUDIO_BYTES, timeout=60.0, retry_all=True)
    return path, True


async def _audio_analyze(args: Dict[str, Any], **_kw: Any) -> str:
    """Analyze one recording on the first configured backend that answers."""
    source = str(args.get("audio_url") or "").strip()
    question = str(args.get("question") or "").strip()
    if not question:
        return _error("Say what to find out about the recording (question).")
    path, downloaded = None, False
    try:
        try:
            path, downloaded = await _materialize(source)
        except ValueError as exc:
            return _error(str(exc))
        fmt = FORMATS.get(path.suffix.lower())
        if not fmt:
            return _error(f"Unsupported audio format: '{path.suffix or 'none'}'.")
        size = path.stat().st_size
        if size > MAX_AUDIO_BYTES:
            return _error(f"Recording too large ({size // (1024 * 1024)} MB; max 14 MB). Trim or re-encode it first.")
        messages = [{"role": "user", "content": [
            {"type": "text", "text": _PROMPT.format(question=question)},
            {"type": "input_audio", "input_audio": {"data": base64.b64encode(path.read_bytes()).decode("ascii"),
                                                    "format": fmt}},
        ]}]
        result = await media_backends.analyze(_backends(), messages)
        reply = {"success": True, "analysis": result["analysis"],
                 "provider": result["provider"], "model": result["model"]}
        if result["failed"]:
            reply["failed_backends"] = result["failed"]
        return json.dumps(reply, indent=2, ensure_ascii=False)
    except media_backends.AllBackendsFailed as exc:
        logger.error("audio-analyze: every backend failed: %s", exc)
        return _error("No backend could analyze the recording; nothing is known about its content.",
                      failed_backends=exc.failures)
    except Exception as exc:  # noqa: BLE001 - surface as a tool result, never raise
        logger.error("audio-analyze failed: %s", exc, exc_info=True)
        return _error(f"Error analyzing audio: {exc}")
    finally:
        if downloaded and path is not None:
            path.unlink(missing_ok=True)


def register(ctx) -> None:
    ctx.register_tool(
        name="audio_analyze",
        toolset="audio_analyze",
        schema=AUDIO_ANALYZE_SCHEMA,
        handler=_audio_analyze,
        is_async=True,
        emoji="\U0001f3a7",
    )
    tool_preview.fixed("audio_analyze", "analyze audio")
