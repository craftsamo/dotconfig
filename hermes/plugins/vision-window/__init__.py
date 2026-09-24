"""vision-window: say plainly which vision_analyze images the model did not get.

Hermes sends only the newest three image-bearing tool results with each request
(send-path eviction plus the Anthropic adapter's own cap). A step that asked for
29 images therefore showed three, while the other 26 results still said "Image
loaded into your context". The model saw no image, took it for a failed load and
asked again: 566-972 looks per 16 s video job, one frame opened up to 80 times.

This plugin rewrites the native vision result through ``transform_tool_result``
(no Hermes core change):

* the 4th and later image in the same step becomes a "not shown" text result, so
  the three that are shown are exactly the ones the model receives; and
* an image with byte-identical content already shown ``REPEAT_LIMIT`` times in
  the turn becomes a "not shown again" text result. A re-rendered file has new
  bytes and is shown normally.

Only images actually shown count towards the repeat limit.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from typing import Any

WINDOW = 3  # matches Hermes' _MAX_KEEP_TOOL_IMAGES
REPEAT_LIMIT = 3
_MAX_KEYS = 512

NOT_SHOWN = (
    "[Image not shown: {path}. Only {window} images can be shown to you per step, and "
    "this step already showed {window}. The file itself is fine. If you still need "
    "this image, request it again in your next step.]"
)
NOT_SHOWN_AGAIN = (
    "[Image not shown again: {path}. You have already been shown this exact image "
    "{count} times in this turn. Use what you already noted about it. Open it again "
    "only after the file changes.]"
)

_lock = threading.Lock()
_step_counts: "OrderedDict[tuple, int]" = OrderedDict()
_turn_views: "OrderedDict[tuple, dict]" = OrderedDict()


def _remember(store: OrderedDict, key: tuple, default):
    if key not in store:
        store[key] = default
        while len(store) > _MAX_KEYS:
            store.popitem(last=False)
    store.move_to_end(key)
    return store[key]


def _image_digest(result: Any) -> str | None:
    """SHA-256 of the image payload of a native multimodal result, else None."""
    if not isinstance(result, dict) or not result.get("_multimodal"):
        return None
    h, found = hashlib.sha256(), False
    for part in result.get("content") or []:
        if isinstance(part, dict) and part.get("type") in ("image_url", "image", "input_image"):
            image = part.get("image_url")
            url = image.get("url") if isinstance(image, dict) else image
            h.update(str(url if url is not None else part.get("source")).encode("utf-8", "replace"))
            found = True
    return h.hexdigest() if found else None


def _transform(tool_name: str = "", args: Any = None, result: Any = None, session_id: str = "",
               turn_id: str = "", api_request_id: str = "", tool_call_id: str = "", **_: Any):
    if tool_name != "vision_analyze":
        return None
    digest = _image_digest(result)
    if digest is None:
        return None
    path = str((args or {}).get("image_url", "")) if isinstance(args, dict) else ""
    turn = (session_id, turn_id)
    step = (session_id, turn_id, api_request_id or tool_call_id)
    with _lock:
        views = _remember(_turn_views, turn, {})
        seen = views.get(digest, 0)
        if seen >= REPEAT_LIMIT:
            return NOT_SHOWN_AGAIN.format(path=path, count=seen)
        shown = _remember(_step_counts, step, 0)
        if shown >= WINDOW:
            return NOT_SHOWN.format(path=path, window=WINDOW)
        _step_counts[step] = shown + 1
        views[digest] = seen + 1
    return None


def register(ctx: Any) -> None:
    ctx.register_hook("transform_tool_result", _transform)
