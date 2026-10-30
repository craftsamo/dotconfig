from __future__ import annotations

import importlib.util
import inspect
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest


def load_plugin() -> ModuleType:
    plugin_path = Path(__file__).resolve().parents[1] / "__init__.py"
    spec = importlib.util.spec_from_file_location("video_analyze_mimo_plugin", plugin_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load plugin from {plugin_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeContext:
    def __init__(self) -> None:
        self.tools: dict[str, dict[str, Any]] = {}

    def register_tool(self, *, name: str, **kwargs: Any) -> None:
        self.tools[name] = kwargs


def _reply(text: str) -> Any:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def _forbidden_call(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("network/LLM boundary must not be called for this input")


class VideoAnalyzeMimoRegistrationTest(unittest.TestCase):
    """The plugin overrides the built-in video_analyze tool, real vision_tools schema."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.plugin = load_plugin()

    def test_register_overrides_video_toolset(self) -> None:
        from tools.vision_tools import VIDEO_ANALYZE_SCHEMA

        ctx = FakeContext()
        self.plugin.register(ctx)

        registered = ctx.tools["video_analyze"]
        self.assertEqual(registered["toolset"], "video")
        self.assertIs(registered["override"], True)
        self.assertIs(registered["schema"], VIDEO_ANALYZE_SCHEMA)
        self.assertIs(registered["handler"], self.plugin._video_analyze_mimo)
        self.assertTrue(registered["is_async"])


def test_the_progress_line_is_a_fixed_label(monkeypatch):
    display = pytest.importorskip("agent.display")
    pytest.importorskip("tools.vision_tools")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    load_plugin().register(FakeContext())
    line = display.build_tool_preview("video_analyze", {"video_url": "/Users/someone/clip.mov",
                                                        "question": "private question"}, max_len=0)
    assert line == "analyze video"


class VideoAnalyzeMimoInvalidInputTest(unittest.IsolatedAsyncioTestCase):
    """Real ``tools.vision_tools`` import (not stubbed); network/LLM boundaries are mocked to
    prohibit calls, so an invalid source must short-circuit before either is reached."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.plugin = load_plugin()

    async def _run_forbidding_network(self, args: dict[str, Any]) -> dict[str, Any]:
        with patch("tools.vision_tools._download_media", new=AsyncMock(side_effect=_forbidden_call)), \
             patch.object(self.plugin.media_backends, "direct_call", new=AsyncMock(side_effect=_forbidden_call)):
            result = await self.plugin._video_analyze_mimo(args)
        return json.loads(result)

    async def test_non_url_non_file_source_returns_tool_error(self) -> None:
        parsed = await self._run_forbidding_network(
            {"video_url": "not-a-url-or-a-real-file", "question": "what happens?"}
        )

        self.assertFalse(parsed["success"])
        self.assertIn("Invalid video source", parsed["error"])

    async def test_missing_video_url_returns_tool_error(self) -> None:
        parsed = await self._run_forbidding_network({"question": "what happens?"})

        self.assertFalse(parsed["success"])
        self.assertIn("Invalid video source", parsed["error"])


class VideoAnalyzeMimoRemoteVideoTest(unittest.IsolatedAsyncioTestCase):
    """A remote URL routes through the downloader with the exact upstream arguments; no real
    network call is made."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.plugin = load_plugin()

    async def test_remote_url_downloads_then_analyzes_via_configured_backend(self) -> None:
        from tools.vision_tools import _MAX_VIDEO_BASE64_BYTES, _download_media

        real_download_signature = inspect.signature(_download_media)

        video_url = "https://example.com/clip.mp4"
        fake_response = _reply("a description")

        async def fake_download_media(url: str, destination: Path, max_retries: int, **kwargs: Any) -> Path:
            return destination

        with patch.object(self.plugin, "_backends", return_value=[("openrouter", "test-model")]), \
             patch("tools.vision_tools._validate_image_url_async", new=AsyncMock(return_value=True)), \
             patch("tools.vision_tools._download_media", new=AsyncMock(side_effect=fake_download_media)) as mock_download, \
             patch("tools.vision_tools._detect_video_mime_type", return_value="video/mp4"), \
             patch("tools.vision_tools._video_to_base64_data_url", return_value="data:video/mp4;base64,AA=="), \
             patch.object(self.plugin.media_backends, "direct_call", new=AsyncMock(return_value=fake_response)) as mock_llm:
            result = await self.plugin._video_analyze_mimo(
                {"video_url": video_url, "question": "what happens?"}
            )

        parsed = json.loads(result)
        self.assertTrue(parsed["success"])
        self.assertEqual(parsed["analysis"], "a description")
        self.assertEqual(parsed["model"], "test-model")

        mock_download.assert_awaited_once()
        # Mocks must not hide an upstream signature change at this integration boundary.
        real_download_signature.bind(*mock_download.call_args.args, **mock_download.call_args.kwargs)
        (called_url, called_destination, called_max_retries), called_kwargs = mock_download.call_args
        self.assertEqual(called_url, video_url)
        self.assertTrue(str(called_destination).endswith(".mp4"))
        self.assertEqual(called_max_retries, 3)
        self.assertEqual(
            called_kwargs,
            {
                "media_label": "Video",
                "accept": "video/*,*/*;q=0.8",
                "max_bytes": _MAX_VIDEO_BASE64_BYTES,
                "timeout": 60.0,
                "retry_all": True,
            },
        )

        mock_llm.assert_awaited_once()
        llm_kwargs = mock_llm.call_args.kwargs
        self.assertEqual(llm_kwargs["provider"], "openrouter")
        self.assertEqual(llm_kwargs["model"], "test-model")


class VideoAnalyzeMimoLocalFileTest(unittest.IsolatedAsyncioTestCase):
    """A local file path bypasses the downloader entirely and calls the configured backend
    directly; the file is not deleted afterwards (caller-owned input)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.plugin = load_plugin()

    async def test_local_file_bypasses_downloader_and_is_kept(self) -> None:
        fake_response = _reply("local description")
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
            handle.write(b"fake-video-bytes")
            local_path = Path(handle.name)

        try:
            with patch.object(self.plugin, "_backends", return_value=[("openrouter", "test-model")]), \
                 patch("tools.vision_tools._download_media", new=AsyncMock(side_effect=_forbidden_call)) as mock_download, \
                 patch.object(self.plugin.media_backends, "direct_call", new=AsyncMock(return_value=fake_response)) as mock_llm:
                result = await self.plugin._video_analyze_mimo(
                    {"video_url": str(local_path), "question": "what happens?"}
                )

            parsed = json.loads(result)
            self.assertTrue(parsed["success"])
            self.assertEqual(parsed["analysis"], "local description")

            mock_download.assert_not_awaited()
            mock_llm.assert_awaited_once()

            # Local files are caller-owned input, not the plugin's temp download — must survive.
            self.assertTrue(local_path.exists())
        finally:
            local_path.unlink(missing_ok=True)

    async def test_downloaded_temp_file_cleanup_guard_does_not_raise_when_missing(self) -> None:
        # The remote branch's temp path never materializes when the downloader is mocked; the
        # handler's cleanup guard must tolerate that (checks .exists() before unlink()).
        with patch.object(self.plugin, "_backends", return_value=[("openrouter", "test-model")]), \
             patch("tools.vision_tools._validate_image_url_async", new=AsyncMock(return_value=True)), \
             patch("tools.vision_tools._download_media", new=AsyncMock(return_value=None)), \
             patch("tools.vision_tools._detect_video_mime_type", return_value="video/mp4"), \
             patch("tools.vision_tools._video_to_base64_data_url", return_value="data:video/mp4;base64,AA=="), \
             patch.object(self.plugin.media_backends, "direct_call", new=AsyncMock(return_value=_reply("ok"))):
            result = await self.plugin._video_analyze_mimo(
                {"video_url": "https://example.com/clip.mp4", "question": "what happens?"}
            )

        parsed = json.loads(result)
        self.assertTrue(parsed["success"])


class VideoAnalyzeMimoBackendOrderTest(unittest.IsolatedAsyncioTestCase):
    """Backends are tried in the configured order; the result says which one answered."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.plugin = load_plugin()

    async def _run(self, side_effect: Any) -> tuple[dict[str, Any], AsyncMock]:
        with tempfile.NamedTemporaryFile(suffix=".mp4") as handle:
            handle.write(b"fake-video-bytes")
            handle.flush()
            with patch.object(self.plugin, "_backends", return_value=[("provider-a", "model-a"), ("openrouter", "mimo")]), \
                 patch.object(self.plugin.media_backends, "direct_call", new=AsyncMock(side_effect=side_effect)) as mock_llm:
                result = await self.plugin._video_analyze_mimo({"video_url": handle.name, "question": "what?"})
        return json.loads(result), mock_llm

    async def test_a_failing_first_backend_hands_over_to_the_next(self) -> None:
        parsed, mock_llm = await self._run([RuntimeError("HTTP 429"), _reply("from mimo")])
        self.assertTrue(parsed["success"])
        self.assertEqual((parsed["provider"], parsed["model"], parsed["analysis"]), ("openrouter", "mimo", "from mimo"))
        self.assertEqual(parsed["failed_backends"][0]["provider"], "provider-a")
        self.assertEqual(parsed["failed_backends"][0]["error"], "RuntimeError HTTP 429")
        self.assertEqual([c.kwargs["provider"] for c in mock_llm.call_args_list], ["provider-a", "openrouter"])
        sent = mock_llm.call_args_list[0].kwargs["messages"][0]["content"]
        self.assertEqual([p["type"] for p in sent], ["text", "video_url"])

    async def test_no_answer_from_any_backend_is_a_failure_not_a_guess(self) -> None:
        parsed, _ = await self._run([RuntimeError("down"), _reply(""), _reply("")])
        self.assertFalse(parsed["success"])
        self.assertNotIn("analysis", parsed)
        self.assertEqual([f["provider"] for f in parsed["failed_backends"]], ["provider-a", "openrouter"])
        self.assertEqual(parsed["failed_backends"][1]["error"], "the reply had no text")


if __name__ == "__main__":
    unittest.main()
