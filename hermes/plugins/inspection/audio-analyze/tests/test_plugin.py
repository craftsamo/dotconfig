from __future__ import annotations

import asyncio
import base64
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest


def load_plugin():
    path = Path(__file__).resolve().parents[1] / "__init__.py"
    spec = importlib.util.spec_from_file_location("audio_analyze_plugin", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PLUGIN = load_plugin()


class FakeContext:
    def __init__(self) -> None:
        self.tools: dict[str, dict[str, Any]] = {}

    def register_tool(self, *, name: str, **kwargs: Any) -> None:
        self.tools[name] = kwargs


def _reply(text: str, finish_reason: str = "stop") -> Any:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text), finish_reason=finish_reason)])


def _run(args: dict[str, Any], llm: AsyncMock, backends=(("provider-a", "model-a"), ("openrouter", "flash"))) -> dict:
    with patch.object(PLUGIN, "_backends", return_value=list(backends)), \
         patch.object(PLUGIN.media_backends, "direct_call", new=llm):
        return json.loads(asyncio.run(PLUGIN._audio_analyze(args)))


def test_register_adds_the_tool_on_its_own_toolset():
    ctx = FakeContext()
    PLUGIN.register(ctx)
    tool = ctx.tools["audio_analyze"]
    assert tool["toolset"] == "audio_analyze" and tool["is_async"] is True and tool["emoji"]
    assert tool["schema"]["parameters"]["required"] == ["audio_url", "question"]
    assert "leaves this machine" in tool["schema"]["description"]


def test_the_progress_line_is_a_fixed_label(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    PLUGIN.register(FakeContext())
    line = display.build_tool_preview("audio_analyze", {"audio_url": "/Users/someone/call.m4a",
                                                        "question": "private question"}, max_len=0)
    assert line == "analyze audio"


def test_a_local_recording_goes_whole_as_input_audio(tmp_path):
    recording = tmp_path / "meeting.M4A"
    recording.write_bytes(b"fake-audio")
    llm = AsyncMock(side_effect=[RuntimeError("HTTP 429"), _reply("two voices")])
    parsed = _run({"audio_url": str(recording), "question": "who speaks?"}, llm)
    assert parsed["success"] and parsed["analysis"] == "two voices"
    assert (parsed["provider"], parsed["model"]) == ("openrouter", "flash")
    assert parsed["failed_backends"][0]["provider"] == "provider-a"
    part = llm.call_args_list[0].kwargs["messages"][0]["content"][1]
    assert part == {"type": "input_audio", "input_audio": {"data": base64.b64encode(b"fake-audio").decode(),
                                                           "format": "m4a"}}
    assert recording.exists()  # the caller's file is never removed


def test_opus_goes_as_ogg_and_webm_is_refused(tmp_path):
    voice = tmp_path / "note.opus"
    voice.write_bytes(b"OggS")
    llm = AsyncMock(return_value=_reply("ok"))
    assert _run({"audio_url": str(voice), "question": "q"}, llm)["success"]
    assert llm.call_args.kwargs["messages"][0]["content"][1]["input_audio"]["format"] == "ogg"
    clip = tmp_path / "clip.webm"
    clip.write_bytes(b"x")
    refused = _run({"audio_url": str(clip), "question": "q"}, AsyncMock(side_effect=AssertionError("no request")))
    assert "Unsupported audio format" in refused["error"]


def test_no_answer_anywhere_is_a_failure_not_a_guess(tmp_path):
    recording = tmp_path / "a.wav"
    recording.write_bytes(b"x")
    parsed = _run({"audio_url": str(recording), "question": "q"}, AsyncMock(return_value=_reply("")))
    assert not parsed["success"] and "nothing is known" in parsed["error"]
    assert [f["provider"] for f in parsed["failed_backends"]] == ["provider-a", "openrouter"]


def test_an_answer_cut_off_everywhere_comes_back_marked_truncated(tmp_path):
    recording = tmp_path / "a.wav"
    recording.write_bytes(b"x")
    parsed = _run({"audio_url": str(recording), "question": "q"},
                  AsyncMock(return_value=_reply("overview only", finish_reason="length")))
    assert parsed["success"] and parsed["truncated"] is True and "unknown" in parsed["note"]
    assert parsed["provider"] == "provider-a" and parsed["failed_backends"][0]["provider"] == "openrouter"


@pytest.mark.parametrize("args, fragment", [
    ({"audio_url": "not-a-file", "question": "q"}, "Invalid audio source"),
    ({"audio_url": "", "question": "q"}, "Invalid audio source"),
    ({"audio_url": "/tmp/x.wav"}, "question"),
])
def test_bad_input_is_refused_before_any_request(args, fragment):
    llm = AsyncMock(side_effect=AssertionError("no request expected"))
    parsed = _run(args, llm)
    assert not parsed["success"] and fragment in parsed["error"]
    llm.assert_not_awaited()


def test_unsupported_and_oversized_recordings_are_refused(tmp_path, monkeypatch):
    llm = AsyncMock(side_effect=AssertionError("no request expected"))
    text = tmp_path / "notes.txt"
    text.write_bytes(b"x")
    assert "Unsupported audio format" in _run({"audio_url": str(text), "question": "q"}, llm)["error"]
    big = tmp_path / "long.mp3"
    big.write_bytes(b"x" * 11)
    monkeypatch.setattr(PLUGIN, "MAX_AUDIO_BYTES", 10)
    assert "too large" in _run({"audio_url": str(big), "question": "q"}, llm)["error"]
    llm.assert_not_awaited()


def test_a_url_without_a_known_extension_is_refused_before_download():
    with patch("tools.vision_tools._validate_image_url_async", new=AsyncMock(return_value=True)), \
         patch("tools.vision_tools._download_media", new=AsyncMock(side_effect=AssertionError("no download"))):
        parsed = _run({"audio_url": "https://example.com/stream", "question": "q"},
                      AsyncMock(side_effect=AssertionError("no request expected")))
    assert "Unsupported audio format" in parsed["error"]


def test_a_downloaded_recording_is_removed_afterwards(tmp_path, monkeypatch):
    import hermes_constants

    monkeypatch.setattr(hermes_constants, "get_hermes_dir", lambda *a: tmp_path)
    saved = []

    async def fake_download(url, destination, retries, **kwargs):
        destination.write_bytes(b"remote-audio")
        saved.append(destination)
        return destination

    with patch("tools.vision_tools._validate_image_url_async", new=AsyncMock(return_value=True)), \
         patch("tools.vision_tools._download_media", new=AsyncMock(side_effect=fake_download)), \
         patch("tools.website_policy.check_website_access", return_value=None):
        parsed = _run({"audio_url": "https://example.com/talk.mp3", "question": "q"}, AsyncMock(return_value=_reply("ok")))
    assert parsed["success"] and saved and not saved[0].exists()
