"""media-inspect — the media_inspect tool: probe a local media file and pull stills
or a contact sheet into scratch space.

The engine is ``media.py`` beside this file (stdlib + ffprobe/ffmpeg). Like the
social/ and messaging/ access plugins, one tool serves several profiles and
each profile is offered only its own action list, checked again by the
handler. It reads the input and writes only under the OS temporary directory,
never into a deliverable or a ``deliver:`` directory.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


def _load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


media = _load("hermes_media_inspect", Path(__file__).resolve().parent / "media.py")

TOOL = "media_inspect"
# The actions each profile's schema offers (checked again by the handler).
PROFILES = {"creator": media.ACTIONS, "assistant": media.ACTIONS}

DESCRIPTION = (
    "Inspect a local video, image or audio file without changing it. probe: format, duration, size and "
    "streams (resolution, fps, frame count, sample rate, channels). frames: up to "
    f"{media.MAX_FRAMES} stills at given times (seconds) or frame numbers. sheet: one contact sheet of up "
    f"to {media.MAX_TILES} tiles, evenly spaced (count) or at given times, with each tile's time. Stills and "
    "sheets are written to a fresh scratch directory under the OS temporary directory and returned as "
    "paths for vision; they are never deliverables and are never written next to the input or into a "
    "deliver: directory. Local paths only; URLs are never fetched. Native vision shows at most three "
    "images per step: look at a sheet first, then single frames.")


def schema_properties(actions) -> dict:
    properties = {
        "action": {"type": "string", "enum": list(actions)},
        "path": {"type": "string", "description": "Absolute local path of the media file"},
    }
    if set(actions) & {"frames", "sheet"}:
        properties.update({
            "times": {"type": "array", "items": {"type": "number"},
                      "description": "Positions in seconds (frames, or sheet instead of count)"},
            "frames": {"type": "array", "items": {"type": "integer"},
                       "description": "Frame numbers (frames or sheet; needs a known frame rate)"},
        })
    if "sheet" in actions:
        properties.update({
            "count": {"type": "integer", "description": f"sheet: evenly spaced tiles, 1..{media.MAX_TILES} "
                                                        f"(default {media.DEFAULT_TILES})"},
            "columns": {"type": "integer", "description": f"sheet: tiles per row, 1..8 (default {media.DEFAULT_COLUMNS})"},
            "width": {"type": "integer", "description": f"sheet: tile width in px, 64..{media.MAX_WIDTH} "
                                                        f"(default {media.DEFAULT_WIDTH})"},
        })
    return properties


def make_handler(profile: str):
    allowed = tuple(PROFILES[profile])

    def media_inspect(args, **kwargs):
        try:
            return json.dumps(media.run(args, profile, allowed), ensure_ascii=False)
        except media.MediaError as exc:
            return json.dumps({"error": f"{TOOL}: {exc}"}, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001 - surface any engine failure as a tool error
            return json.dumps({"error": f"{TOOL}: {type(exc).__name__}: {exc}"}, ensure_ascii=False)

    return media_inspect


def register(ctx):
    profile = ctx.profile_name
    if profile not in PROFILES:
        return
    media.cleanup()
    actions = PROFILES[profile]
    ctx.register_tool(name=TOOL, toolset=TOOL, handler=make_handler(profile), description=DESCRIPTION,
                      schema={"name": TOOL, "description": DESCRIPTION, "parameters": {
                          "type": "object", "properties": schema_properties(actions),
                          "required": ["action", "path"], "additionalProperties": False}})
