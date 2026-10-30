"""video-analyze-mimo — pin video analysis to config-driven backends.

The built-in ``video_analyze`` tool resolves through ``auxiliary.vision``. That
coupling is a problem here: pinning ``auxiliary.vision`` to a video-capable model
(needed because the main models — codex/copilot/deepseek — can't take video)
*also* forces image input through the aux describer, disabling the main model's
native image vision.

This plugin overrides ``video_analyze`` (``override=True``, same name/toolset) so
video understanding goes **directly** to the listed provider+model backends, and
to no other — bypassing ``auxiliary.vision`` entirely. With that decoupling, ``auxiliary.vision`` can stay ``auto`` and images
route natively to whichever main tier is active (codex/copilot/mimo), while video
always lands on a video-capable backend.

Backends are config-driven via a top-level ``video_analyze:`` section in
``config.yaml`` (preserved across Hermes' config rewrites because ``_deep_merge``
keeps user-only keys and ``save_config`` writes the full dict), tried in order
(``plugins/_shared/media_backends.py``)::

    video_analyze:
      backends:
        - {provider: openrouter, model: xiaomi/mimo-v2.5}

The single form (``provider`` / ``model``) still works, and OpenRouter /
xiaomi/mimo-v2.5 is the default when the section is absent. Credentials come
from the Keychain shim (``OPENROUTER_API_KEY``) or the backend's own login.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

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

_DEFAULT_BACKEND = ("openrouter", "xiaomi/mimo-v2.5")

# The question comes first: an answer that runs long is cut at its end, and the description is
# what can be spared.
_PROMPT = (
    "Watch the whole video. First answer the following question completely. Then briefly describe "
    "what happens in the video, including visual content, motion, audio cues, text overlays and "
    "scene transitions, with approximate timestamps.\n\nQuestion:\n{question}"
)


def _backends() -> list[tuple[str, str]]:
    """The ``video_analyze:`` backends of the active profile's config, in order."""
    return media_backends.configured_backends("video_analyze", _DEFAULT_BACKEND)


async def _video_analyze_mimo(args: Dict[str, Any], **_kw: Any) -> str:
    """Analyze a video on the first configured backend that answers."""
    from hermes_constants import get_hermes_dir
    from tools.registry import tool_error
    from tools.vision_tools import (
        _MAX_VIDEO_BASE64_BYTES,
        _detect_video_mime_type,
        _download_media,
        _validate_image_url_async,
        _video_to_base64_data_url,
    )
    from tools.website_policy import check_website_access

    video_url = args.get("video_url", "") or ""
    question = args.get("question", "") or ""
    full_prompt = _PROMPT.format(question=question)
    backends = _backends()

    temp_video_path = None
    should_cleanup = True
    try:
        resolved = video_url[len("file://"):] if video_url.startswith("file://") else video_url
        local_path = Path(os.path.expanduser(resolved))
        if local_path.is_file():
            temp_video_path = local_path
            should_cleanup = False
        elif await _validate_image_url_async(video_url):
            blocked = check_website_access(video_url)
            if blocked:
                return tool_error(blocked["message"], success=False)
            temp_dir = get_hermes_dir("cache/video", "temp_video_files")
            temp_video_path = temp_dir / f"temp_video_{uuid.uuid4()}.mp4"
            await _download_media(
                video_url, temp_video_path, 3,
                media_label="Video", accept="video/*,*/*;q=0.8",
                max_bytes=_MAX_VIDEO_BASE64_BYTES, timeout=60.0, retry_all=True)
            should_cleanup = True
        else:
            return tool_error(
                "Invalid video source. Provide an HTTP/HTTPS URL or a local file path.",
                success=False,
            )

        mime = _detect_video_mime_type(temp_video_path)
        if not mime:
            return tool_error(
                f"Unsupported video format: '{temp_video_path.suffix}'.", success=False
            )

        data_url = _video_to_base64_data_url(temp_video_path, mime_type=mime)
        if len(data_url) > _MAX_VIDEO_BASE64_BYTES:
            return tool_error(
                "Video too large for the API (max ~50 MB). Compress or trim and retry.",
                success=False,
            )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": full_prompt},
                    {"type": "video_url", "video_url": {"url": data_url}},
                ],
            }
        ]
        result = await media_backends.analyze(backends, messages,
                                              max_tokens=media_backends.configured_max_tokens("video_analyze"))
        reply = {"success": True, "analysis": result["analysis"],
                 "provider": result["provider"], "model": result["model"]}
        if result.get("truncated"):
            reply["truncated"] = True
            reply["note"] = media_backends.TRUNCATED_NOTE
        if result["failed"]:
            reply["failed_backends"] = result["failed"]
        return json.dumps(reply, indent=2, ensure_ascii=False)
    except media_backends.AllBackendsFailed as exc:
        logger.error("video-analyze-mimo: every backend failed: %s", exc)
        return json.dumps(
            {
                "success": False,
                "error": "No backend could analyze the video; nothing is known about its content.",
                "failed_backends": exc.failures,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as exc:  # noqa: BLE001 — surface as a tool result, never raise
        logger.error("video-analyze-mimo failed: %s", exc, exc_info=True)
        return json.dumps(
            {
                "success": False,
                "error": f"Error analyzing video: {exc}",
            },
            indent=2,
            ensure_ascii=False,
        )
    finally:
        if should_cleanup and temp_video_path and temp_video_path.exists():
            try:
                temp_video_path.unlink()
            except Exception as cleanup_error:  # noqa: BLE001
                logger.debug("video-analyze-mimo: temp cleanup failed: %s", cleanup_error)


def register(ctx) -> None:
    """Override the built-in video_analyze with the config-driven backend."""
    from tools.vision_tools import VIDEO_ANALYZE_SCHEMA

    ctx.register_tool(
        name="video_analyze",
        toolset="video",
        schema=VIDEO_ANALYZE_SCHEMA,
        handler=_video_analyze_mimo,
        is_async=True,
        requires_env=["OPENROUTER_API_KEY"],
        emoji="\U0001f3ac",
        override=True,
    )
    tool_preview.fixed("video_analyze", "analyze video")
