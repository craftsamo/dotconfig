"""video-analyze-mimo — pin video analysis to a config-driven backend.

The built-in ``video_analyze`` tool resolves through ``auxiliary.vision``. That
coupling is a problem here: pinning ``auxiliary.vision`` to a video-capable model
(needed because the main models — codex/copilot/deepseek — can't take video)
*also* forces image input through the aux describer, disabling the main model's
native image vision.

This plugin overrides ``video_analyze`` (``override=True``, same name/toolset) so
video understanding goes **directly** to an explicit provider+model via
``async_call_llm(provider=…, model=…)`` — bypassing ``auxiliary.vision``
entirely. With that decoupling, ``auxiliary.vision`` can stay ``auto`` and images
route natively to whichever main tier is active (codex/copilot/mimo), while video
always lands on a video-capable backend.

Backend is config-driven via a top-level ``video_analyze:`` section in
``config.yaml`` (preserved across Hermes' config rewrites because ``_deep_merge``
keeps user-only keys and ``save_config`` writes the full dict)::

    video_analyze:
      provider: openrouter
      model: xiaomi/mimo-v2.5      # e.g. minimax/minimax-m3

Defaults to OpenRouter / xiaomi/mimo-v2.5 when the section is absent. The chain
mirrors the build-a-hermes-plugin tool pattern; credentials come from the
Keychain shim (``OPENROUTER_API_KEY``).
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_DEFAULT_PROVIDER = "openrouter"
_DEFAULT_MODEL = "xiaomi/mimo-v2.5"

_PROMPT = (
    "Fully describe and explain everything happening in this video, including "
    "visual content, motion, audio cues, text overlays, and scene transitions. "
    "Then answer the following question:\n\n{question}"
)


def _resolve_backend() -> tuple[str, str]:
    """Read provider/model from config.yaml ``video_analyze:`` (with defaults)."""
    try:
        from hermes_cli.config import cfg_get, load_config

        cfg = load_config()
        provider = cfg_get(cfg, "video_analyze", "provider", default=_DEFAULT_PROVIDER)
        model = cfg_get(cfg, "video_analyze", "model", default=_DEFAULT_MODEL)
    except Exception as exc:  # noqa: BLE001 — never fail resolution
        logger.debug("video-analyze-mimo: config read failed (%s); using defaults", exc)
        provider, model = _DEFAULT_PROVIDER, _DEFAULT_MODEL
    return (str(provider or _DEFAULT_PROVIDER).strip(),
            str(model or _DEFAULT_MODEL).strip())


async def _video_analyze_mimo(args: Dict[str, Any], **_kw: Any) -> str:
    """Analyze a video via an explicit, config-driven provider+model."""
    from agent.auxiliary_client import async_call_llm, extract_content_or_reasoning
    from hermes_constants import get_hermes_dir
    from tools.registry import tool_error
    from tools.vision_tools import (
        _MAX_VIDEO_BASE64_BYTES,
        _detect_video_mime_type,
        _download_video,
        _validate_image_url_async,
        _video_to_base64_data_url,
    )
    from tools.website_policy import check_website_access

    video_url = args.get("video_url", "") or ""
    question = args.get("question", "") or ""
    full_prompt = _PROMPT.format(question=question)
    provider, model = _resolve_backend()

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
            await _download_video(video_url, temp_video_path)
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
        call_kwargs = dict(
            provider=provider,
            model=model,
            messages=messages,
            temperature=0.1,
            max_tokens=4000,
            timeout=180,
        )
        response = await async_call_llm(**call_kwargs)
        analysis = extract_content_or_reasoning(response)
        if not analysis:
            logger.warning("video-analyze-mimo: empty response, retrying once")
            response = await async_call_llm(**call_kwargs)
            analysis = extract_content_or_reasoning(response)

        return json.dumps(
            {
                "success": True,
                "analysis": analysis or "The video could not be analyzed.",
                "model": model,
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
                "analysis": (
                    "There was a problem analyzing the video "
                    f"(provider={provider}, model={model}). Error: {exc}"
                ),
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
