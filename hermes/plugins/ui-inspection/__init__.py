"""Expose viewport capture, not arbitrary host Python or shell, to UI evaluators."""
import base64
import hashlib
import json
from pathlib import Path
import struct
import uuid


ROLES = {"ui-review", "ux-persona"}


def _capture(args, profile, **kwargs):
    from hermes_constants import get_hermes_home
    from gateway.session_context import get_session_env, session_context_engaged
    from tools.browser_tool_session import _run_browser_command

    try:
        if set(args) - {"width", "height"}:
            raise ValueError("Only viewport width and height are accepted")
        width, height = args.get("width"), args.get("height")
        if type(width) is not int or type(height) is not int or not (320 <= width <= 2560 and 320 <= height <= 2048):
            raise ValueError("width must be 320..2560 and height 320..2048 pixels")
        home = get_hermes_home()
        if (not session_context_engaged() or home.name != profile or profile not in ROLES
                or get_session_env("HERMES_SESSION_PROFILE", "") != profile):
            raise ValueError("Wrong profile scope")
        task = kwargs.get("task_id")
        if not isinstance(task, str) or not task or not get_session_env("HERMES_SESSION_ID", ""):
            raise ValueError("A framework task and originating session are required")
        workspace = home / "workspace"
        root = workspace / "ui-inspection"
        if workspace.is_symlink() or root.is_symlink():
            raise ValueError("Evidence directory must not redirect outside its profile")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        owner = hashlib.sha256(task.encode()).hexdigest()[:16]
        path = root / (owner + "-" + uuid.uuid4().hex + ".png")
        resized = _run_browser_command(task, "set", ["viewport", str(width), str(height)])
        if not resized.get("success"):
            raise ValueError("Browser did not confirm the requested viewport")
        captured = _run_browser_command(task, "screenshot", [str(path)])
        if not captured.get("success") or not path.is_file() or path.is_symlink():
            raise ValueError("Browser did not produce a screenshot")
        path.chmod(0o600)
        if path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("Screenshot exceeds the 8 MiB inspection limit")
        image = path.read_bytes()
        if image[:8] != b"\x89PNG\r\n\x1a\n" or len(image) < 24:
            raise ValueError("Screenshot is not PNG")
        actual = struct.unpack(">II", image[16:24])
        if actual != (width, height):
            raise ValueError(f"Screenshot dimensions {actual} differ from the requested viewport")
        text = json.dumps({"screenshot_path": str(path), "width": width, "height": height,
                           "note": "Inspect the attached pixels; capture is not a review verdict."})
        return {"_multimodal": True, "text_summary": text, "meta": {"screenshot_path": str(path)},
                "content": [{"type": "text", "text": text},
                            {"type": "image_url", "image_url": {
                                "url": "data:image/png;base64," + base64.b64encode(image).decode()}}]}
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def register(ctx):
    if ctx.profile_name not in ROLES:
        return
    profile = ctx.profile_name
    description = "Resize your current native browser viewport and save/attach its PNG screenshot. No navigation, shell or arbitrary Python. Inspect the image and cite screenshot_path."
    ctx.register_tool(name="ui_capture", toolset="ui-inspection", description=description,
                      handler=lambda args, **kwargs: _capture(args, profile, **kwargs),
                      schema={"name": "ui_capture", "description": description, "parameters": {
                          "type": "object", "properties": {"width": {"type": "integer"}, "height": {"type": "integer"}},
                          "required": ["width", "height"], "additionalProperties": False}})
