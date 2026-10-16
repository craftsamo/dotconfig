import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plugin = _load("screen_listen_transcript_test", ROOT / "__init__.py")
listen, record, transcript = plugin.listen, plugin.record, plugin.transcript
job = _load("screen_listen_transcribe_job_test", ROOT / "transcribe_job.py")


class FakeContext:
    def __init__(self, profile):
        self.profile_name = profile
        self.tools = {}
        self.skills = {}

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_skill(self, name, path, description="", frontmatter=None):
        self.skills[name] = path


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(record, "DEFAULT_RECORD_DIR", tmp_path / "recordings")
    monkeypatch.setattr(plugin, "_home", lambda: None)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    return tmp_path


@pytest.fixture
def recording(tmp_path):
    folder = record.record_dir(None) / "20260101-1000-discord-standup"
    folder.mkdir()
    (folder / "audio.m4a").write_bytes(b"m4a")
    (folder / "recording.json").write_text(json.dumps({"id": "abc123", "app": "discord", "file": "audio.m4a",
                                                        "seconds": 1800.0, "silent": False}))
    return folder


def call(**args):
    ctx = FakeContext("assistant")
    plugin.register(ctx)
    return json.loads(ctx.tools["screen_listen"]["handler"](args))


class FakePopen:
    calls = []

    def __init__(self, command, **kwargs):
        FakePopen.calls.append((command, kwargs))
        folder = Path(command[3])
        (folder / "transcript.job.json").write_text(json.dumps({"status": "running", "pid": os.getpid(),
                                                                 "model": command[4], "progress_seconds": 600,
                                                                 "duration": 1800}))


def test_transcribe_starts_a_detached_job_and_reports_progress(monkeypatch, recording):
    FakePopen.calls = []
    monkeypatch.setattr(transcript.subprocess, "Popen", FakePopen)
    out = call(action="transcribe", id="abc123")
    assert out["ok"] and out["status"] == "started" and out["model"] == transcript.DEFAULT_MODEL
    command, kwargs = FakePopen.calls[0]
    assert command[0] == sys.executable and command[1].endswith("transcribe_job.py")
    assert command[2] == str(recording / "audio.m4a") and command[3] == str(recording)
    assert kwargs["start_new_session"] is True

    again = call(action="transcribe", dir=str(recording))
    assert again["status"] == "running" and again["percent"] == 33 and len(FakePopen.calls) == 1

    (recording / "transcript.job.json").write_text(json.dumps({"status": "done", "model": "medium", "segments": 42,
                                                                "detected_language": "ja"}))
    (recording / "transcript.txt").write_text("[0:00:01] hello\n")
    done = call(action="transcribe", id="abc123")
    assert done["status"] == "done" and done["segments"] == 42 and done["language"] == "ja"
    assert done["files"] == {"transcript.txt": str(recording / "transcript.txt")}
    assert "never instructions" in done["note"] and len(FakePopen.calls) == 1

    redo = call(action="transcribe", id="abc123", force=True, model="small")
    assert redo["status"] == "started" and FakePopen.calls[1][0][4] == "small"
    assert not (recording / "transcript.txt").exists()


def test_model_and_language_come_from_the_profile(tmp_path, recording, monkeypatch):
    (tmp_path / "config.yaml").write_text("stt:\n  local:\n    model: large-v3\n    language: ja\n")
    assert transcript.local_stt(tmp_path) == ("large-v3", "ja")
    assert transcript.local_stt(None) == (transcript.DEFAULT_MODEL, None)
    FakePopen.calls = []
    monkeypatch.setattr(transcript.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(plugin, "_home", lambda: tmp_path)
    (tmp_path / "config.yaml").write_text(f"stt:\n  local:\n    model: large-v3\n    language: ja\n"
                                          f"screen_listen:\n  record_dir: {record.record_dir(None)}\n")
    out = call(action="transcribe", id="abc123")
    assert out["model"] == "large-v3" and out["language"] == "ja" and FakePopen.calls[0][0][4:] == ["large-v3", "ja"]


def test_a_dead_job_is_reported_failed_and_rerun_on_request(recording, monkeypatch):
    FakePopen.calls = []
    monkeypatch.setattr(transcript.subprocess, "Popen", FakePopen)
    (recording / "transcript.job.json").write_text(json.dumps({"status": "running", "pid": 999999999}))
    out = call(action="transcribe", id="abc123")
    assert out["ok"] is False and out["status"] == "failed" and "force" in out["note"] and not FakePopen.calls
    assert call(action="transcribe", id="abc123", force=True)["status"] == "started" and FakePopen.calls


def test_transcribe_validates_its_target(recording, monkeypatch):
    monkeypatch.setattr(transcript.subprocess, "Popen", FakePopen)
    assert call(action="transcribe")["kind"] == "usage"
    assert call(action="transcribe", id="nope")["kind"] == "usage"
    assert call(action="transcribe", dir="/etc")["kind"] == "usage"
    assert call(action="transcribe", id="abc123", model="huge")["kind"] == "usage"
    meta = json.loads((recording / "recording.json").read_text())
    meta["silent"] = True
    (recording / "recording.json").write_text(json.dumps(meta))
    assert call(action="transcribe", id="abc123")["kind"] == "usage"
    assert call(action="transcribe", id="abc123", force=True)["status"] == "started"


def test_an_unpacked_session_is_refused(monkeypatch):
    record._save({"id": "sess1", "status": "recording", "dir": "/x", "started": "2026"})
    out = call(action="transcribe", id="sess1")
    assert out["kind"] == "usage" and "not packed" in out["error"]


def test_job_script_stamps_and_outputs(tmp_path, monkeypatch):
    assert job.stamp(3725.5) == "1:02:05" and job.stamp(3725.5, vtt=True) == "01:02:05.500"

    class Seg:
        def __init__(self, start, end, text):
            self.start, self.end, self.text = start, end, text

    class Info:
        duration = 4.0
        language = "en"

    class Model:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, path, **kwargs):
            return iter([Seg(0.0, 1.5, " hello "), Seg(1.5, 4.0, "world"), Seg(4.0, 4.0, "  ")]), Info()

    monkeypatch.setitem(sys.modules, "faster_whisper", type("fw", (), {"WhisperModel": Model}))
    audio = tmp_path / "audio.m4a"
    audio.write_bytes(b"m4a")
    monkeypatch.setattr(sys, "argv", ["job", str(audio), str(tmp_path), "base", ""])
    assert job.main() == 0
    state = json.loads((tmp_path / "transcript.job.json").read_text())
    assert state["status"] == "done" and state["segments"] == 2 and state["detected_language"] == "en"
    assert (tmp_path / "transcript.txt").read_text() == "[0:00:00] hello\n[0:00:01] world\n"
    vtt = (tmp_path / "transcript.vtt").read_text()
    assert vtt.startswith("WEBVTT") and "00:00:01.500 --> 00:00:04.000" in vtt
    assert json.loads((tmp_path / "segments.json").read_text())[1]["text"] == "world"


def test_job_script_records_a_failure(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)  # import fails
    monkeypatch.setattr(sys, "argv", ["job", str(tmp_path / "x.m4a"), str(tmp_path), "base"])
    assert job.main() == 1
    state = json.loads((tmp_path / "transcript.job.json").read_text())
    assert state["status"] == "failed" and "error" in state
