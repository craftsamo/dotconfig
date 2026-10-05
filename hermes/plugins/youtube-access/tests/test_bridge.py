"""The yt-dlp bridge: caption choice and parsing, and the real bridge in the engine venv (no network)."""

import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT.parents[1] / "local" / "yt-dlp" / "venv" / "bin" / "python"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bridge = _load("youtube_access_bridge_test", ROOT / "bridge.py")
TRACK = [{"ext": "json3", "url": "u"}]


def test_manual_captions_in_a_requested_language_win():
    info = {"language": "en", "subtitles": {"en": TRACK, "ja": TRACK, "live_chat": TRACK},
            "automatic_captions": {"en-orig": TRACK, "ja": TRACK}}
    assert bridge.pick_track(info, ["ja"])[:2] == ("ja", "manual")
    assert bridge.pick_track(info, [])[:2] == ("en", "manual")


def test_spoken_language_then_translation():
    info = {"language": "en", "subtitles": {}, "automatic_captions": {"en-orig": TRACK, "en": TRACK, "ja": TRACK}}
    assert bridge.pick_track(info, [])[:2] == ("en-orig", "auto")
    assert bridge.pick_track(info, ["en"])[:2] == ("en-orig", "auto")
    assert bridge.pick_track(info, ["ja"])[:2] == ("ja", "translated")
    assert bridge.pick_track({"subtitles": {}, "automatic_captions": {"fr-orig": TRACK}}, ["ja"])[:2] == \
        ("fr-orig", "auto")
    assert bridge.pick_track({"subtitles": {"de-DE": TRACK}}, ["de"])[:2] == ("de-DE", "manual")
    assert bridge.pick_track({}, ["ja"]) is None


def test_selected_size_sums_merged_parts():
    assert bridge.selected_size({"requested_formats": [{"filesize": 10}, {"filesize_approx": 5}]}) == 15
    assert bridge.selected_size({"filesize": 7}) == 7
    assert bridge.selected_size({"requested_formats": [{"filesize": 10}, {}]}) is None


def test_events_drop_empty_lines():
    data = {"events": [{"tStartMs": 0}, {"tStartMs": 1200, "segs": [{"utf8": "a\n"}, {"utf8": "b"}]},
                       {"tStartMs": 2000, "segs": [{"utf8": "\n"}]}]}
    assert bridge.events(data) == [[1200, "a b"]]


def run(payload):
    proc = subprocess.run([str(VENV_PYTHON), "-I", str(ROOT / "bridge.py")], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=60, env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"})
    return json.loads(proc.stdout)


@pytest.mark.skipif(not VENV_PYTHON.exists(), reason="yt-dlp engine not installed")
def test_real_bridge_refuses_without_network():
    assert run({"op": "nope"})["kind"] == "refused"
    out = run({"op": "transcript", "id": "https://evil.example/x"})
    assert out["ok"] is False and out["error"] == "not a video id"
    out = run({"op": "download", "id": "dQw4w9WgXcQ", "dir": "relative", "max_bytes": 1})
    assert out["ok"] is False and "absolute" in out["error"]
