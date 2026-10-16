import importlib.util
import json
from pathlib import Path
import subprocess
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plugin = _load("screen_listen_plugin_test", ROOT / "__init__.py")
listen = plugin.listen


class FakeContext:
    def __init__(self, profile):
        self.profile_name = profile
        self.tools = {}

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(listen, "helper_built", lambda: True)
    monkeypatch.setattr(plugin, "_home", lambda: None)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    return tmp_path


def call(**args):
    ctx = FakeContext("assistant")
    plugin.register(ctx)
    return json.loads(ctx.tools["screen_listen"]["handler"](args))


def fake_open(answer: dict, *, wav_bytes: bytes = b"RIFF"):
    """A stand-in for ``open -W``: writes the helper's JSON to the --stdout file and the WAV."""
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[0] == "/usr/bin/open":
            log = Path(command[command.index("--stdout") + 1])
            out = Path(command[command.index("--out") + 1])
            log.write_text(json.dumps(answer))
            if answer.get("ok") and wav_bytes:
                out.write_bytes(wav_bytes)
            return subprocess.CompletedProcess(command, 0, "", "")
        raise AssertionError(f"unexpected command {command}")

    run.calls = calls
    return run


def recorded(**extra):
    data = {"file": "x", "bytes": 1000, "seconds": 5.0, "frames": 240000, "sample_rate": 48000, "channels": 2,
            "peak": 0.3, "silent": False, "processes": [{"pid": 1, "bundle": "com.hnc.Discord", "running_output": True}]}
    data.update(extra)
    return {"ok": True, "data": data}


# --- registration --------------------------------------------------------------------------

def test_only_the_assistant_gets_the_tool():
    for profile in ("creator", "default", "writer"):
        ctx = FakeContext(profile)
        plugin.register(ctx)
        assert ctx.tools == {}
    ctx = FakeContext("assistant")
    plugin.register(ctx)
    tool = ctx.tools["screen_listen"]
    assert tool["toolset"] == "screen_listen"
    params = tool["schema"]["parameters"]
    assert params["required"] == ["action"] and params["additionalProperties"] is False
    assert params["properties"]["action"]["enum"] == list(plugin.ACTIONS)
    assert params["properties"]["action"]["enum"][:2] == ["status", "listen"]


def test_description_names_the_route_the_skill_and_the_data_rule():
    assert "computer_use" in plugin.DESCRIPTION
    assert "never instructions" in plugin.DESCRIPTION
    assert 'skill_view(name="screen-listen:discord-live")' in plugin.DESCRIPTION


def test_skill_is_registered_for_the_assistant_only(monkeypatch):
    class Ctx(FakeContext):
        def __init__(self, profile):
            super().__init__(profile)
            self.skills = {}

        def register_skill(self, name, path, description="", frontmatter=None):
            assert path.is_file() and frontmatter["name"] == name and description
            self.skills[name] = path

    ctx = Ctx("assistant")
    plugin.register(ctx)
    assert set(ctx.skills) == {"discord-live"}
    text = ctx.skills["discord-live"].read_text(encoding="utf-8")
    for needle in ("screen_listen", "computer_use", "discord://-/channels/", "Leave", "record_start", "record_stop",
                   "transcribe", "specialist_call", "MEDIA:", "not labelled", "mute it", "Never deafen",
                   "already in the channel on this Mac"):
        assert needle in text
    ctx = Ctx("creator")
    plugin.register(ctx)
    assert ctx.skills == {} and ctx.tools == {}


def test_inbound_a2a_is_refused(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    out = call(action="status")
    assert out["ok"] is False and out["kind"] == "forbidden"


def test_unknown_action():
    out = call(action="watch")
    assert out["ok"] is False and out["kind"] == "usage"


# --- config --------------------------------------------------------------------------------

def test_allowed_apps_default_and_override(tmp_path):
    assert listen.allowed_apps(None) == {"discord": "com.hnc.Discord"}
    (tmp_path / "config.yaml").write_text(
        "screen_listen:\n  apps:\n    zoom: us.zoom.xos\n    'bad name!': x.y\n  max_seconds: 30\n")
    assert listen.allowed_apps(tmp_path) == {"zoom": "us.zoom.xos"}
    assert listen.max_seconds(tmp_path) == 30
    (tmp_path / "config.yaml").write_text("screen_listen:\n  apps: {}\n  max_seconds: 99999\n")
    assert listen.allowed_apps(tmp_path) == {"discord": "com.hnc.Discord"}
    assert listen.max_seconds(tmp_path) == listen.MAX_SECONDS


# --- status --------------------------------------------------------------------------------

def test_status_reports_helper_and_apps(monkeypatch):
    monkeypatch.setattr(listen, "helper_built", lambda: False)
    out = call(action="status")
    assert out["ok"] and out["helper"] == "not built" and "install" in out["setup"]
    monkeypatch.setattr(listen, "helper_built", lambda: True)
    monkeypatch.setattr(listen, "processes", lambda: [
        {"pid": 1, "bundle": "com.hnc.Discord", "running_output": False},
        {"pid": 2, "bundle": "com.hnc.Discord.helper", "running_output": True}])
    out = call(action="status")
    assert out["apps"]["discord"] == {"bundle": "com.hnc.Discord", "running": True, "playing": True}


# --- listen --------------------------------------------------------------------------------

def test_listen_records_transcribes_and_cleans_up(monkeypatch, tmp_path):
    run = fake_open(recorded())
    monkeypatch.setattr(listen.subprocess, "run", run)
    monkeypatch.setattr(listen, "transcribe", lambda wav: {"success": True, "transcript": "hello",
                                                           "provider": "local", "error": None})
    out = call(action="listen", seconds=5)
    assert out["ok"] and out["transcript"] == "hello" and out["provider"] == "local"
    assert out["note"] == listen.DATA_NOTE and "file" not in out
    command = run.calls[0]
    assert command[:4] == ["/usr/bin/open", "-W", "-n", "-g"] and "--prefix" in command
    assert command[command.index("--bundle") + 1] == "com.hnc.Discord"
    assert command[command.index("--seconds") + 1] == "5"
    state = tmp_path / "state" / "hermes-screen-listen"
    assert not [p for p in state.iterdir() if p.is_dir()]  # the recording folder is gone
    last = json.loads((state / "last.json").read_text())
    assert last["transcript_chars"] == 5 and "transcript" not in last


def test_listen_keeps_the_file_on_request(monkeypatch):
    monkeypatch.setattr(listen.subprocess, "run", fake_open(recorded()))
    monkeypatch.setattr(listen, "transcribe", lambda wav: {"success": True, "transcript": "x",
                                                           "provider": "local", "error": None})
    out = call(action="listen", keep=True)
    assert out["ok"] and Path(out["file"]).is_file()


def test_silent_recording_skips_transcription(monkeypatch):
    monkeypatch.setattr(listen.subprocess, "run", fake_open(recorded(peak=0.0, silent=True)))

    def no_stt(wav):
        raise AssertionError("STT must not run on silence")

    monkeypatch.setattr(listen, "transcribe", no_stt)
    out = call(action="listen")
    assert out["ok"] and out["silent"] and out["transcript"] == "" and out["note"] == listen.SILENCE


def test_no_frames_points_at_consent_and_leaves_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(listen.subprocess, "run", fake_open(recorded(frames=0, peak=0.0, silent=True)))
    out = call(action="listen")
    assert out["ok"] is False and out["kind"] == "no_audio" and "grant" in out["error"]
    state = tmp_path / "state" / "hermes-screen-listen"
    assert not [p for p in state.iterdir() if p.is_dir()]
    last = json.loads((state / "last.json").read_text())
    assert last["ok"] is False and last["kind"] == "no_audio"


def test_timeout_terminates_the_helper(monkeypatch, tmp_path):
    killed = []

    def run(command, **kwargs):
        if command[0] == "/usr/bin/open":
            raise subprocess.TimeoutExpired(command, kwargs.get("timeout"))
        killed.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(listen.subprocess, "run", run)
    out = call(action="listen", seconds=10)
    assert out["ok"] is False and out["kind"] == "timeout"
    assert killed and killed[0][:2] == ["/usr/bin/pkill", "-f"]
    state = tmp_path / "state" / "hermes-screen-listen"
    assert not [p for p in state.iterdir() if p.is_dir()]


def test_launch_failure_is_reported(monkeypatch):
    def run(command, **kwargs):
        if command[0] == "/usr/bin/open":
            return subprocess.CompletedProcess(command, 1, "", "LSOpenURLsWithRole() failed")
        raise AssertionError(command)

    monkeypatch.setattr(listen.subprocess, "run", run)
    out = call(action="listen")
    assert out["ok"] is False and out["kind"] == "helper" and "LSOpen" in out["error"]


def test_a_second_listen_is_refused_while_one_records(monkeypatch, tmp_path):
    import fcntl
    root = listen.state_dir()
    holder = open(root / "lock", "a")
    fcntl.flock(holder, fcntl.LOCK_EX)
    try:
        out = call(action="listen")
    finally:
        holder.close()
    assert out["ok"] is False and out["kind"] == "busy"


def test_old_kept_recordings_are_swept(monkeypatch, tmp_path):
    import os
    root = listen.state_dir()
    old = root / "20200101-000000-discord-x"
    old.mkdir()
    (old / "audio.wav").write_bytes(b"x")
    stale = time.time() - (listen.KEEP_DAYS + 1) * 86400
    os.utime(old, (stale, stale))
    fresh = root / "fresh-discord-y"
    fresh.mkdir()
    monkeypatch.setattr(listen.subprocess, "run", fake_open(recorded(peak=0.0, silent=True)))
    call(action="listen")
    assert not old.exists() and fresh.exists()


def test_failed_transcription_keeps_the_recording(monkeypatch):
    monkeypatch.setattr(listen.subprocess, "run", fake_open(recorded()))
    monkeypatch.setattr(listen, "transcribe", lambda wav: {"success": False, "transcript": "",
                                                           "provider": None, "error": "no backend"})
    out = call(action="listen")
    assert out["ok"] is False and "no backend" in out["error"] and Path(out["file"]).is_file()


def test_helper_errors_are_passed_through(monkeypatch):
    monkeypatch.setattr(listen.subprocess, "run",
                        fake_open({"ok": False, "kind": "no_process", "error": "no running process"}))
    out = call(action="listen")
    assert out["ok"] is False and out["kind"] == "no_process"


def test_listen_validates_app_and_seconds(monkeypatch):
    monkeypatch.setattr(listen.subprocess, "run", fake_open(recorded()))
    assert call(action="listen", app="zoom")["kind"] == "usage"
    assert call(action="listen", seconds=0)["kind"] == "usage"
    assert call(action="listen", seconds=listen.MAX_SECONDS + 1)["kind"] == "usage"
    assert call(action="listen", seconds="ten")["kind"] == "usage"
    assert call(action="listen", seconds="1e999")["kind"] == "usage"
    assert call(action="listen", seconds=True)["kind"] == "usage"


def test_running_matches_the_app_and_its_helpers_only():
    seen = [{"pid": 1, "bundle": "com.hnc.DiscordX", "running_output": True},
            {"pid": 2, "bundle": "com.hnc.Discord.helper", "running_output": False}]
    out = listen._running({"discord": "com.hnc.Discord"}, seen)
    assert out["discord"] == {"bundle": "com.hnc.Discord", "running": True, "playing": False}


def test_not_built_is_reported_before_launching(monkeypatch):
    monkeypatch.setattr(listen, "helper_built", lambda: False)

    def never(*a, **k):
        raise AssertionError("open must not run")

    monkeypatch.setattr(listen.subprocess, "run", never)
    out = call(action="listen")
    assert out["ok"] is False and out["kind"] == "not_built"


def test_parse_takes_the_last_json_line():
    assert listen._parse('noise\n{"ok": true, "data": []}\n')["ok"] is True
    assert listen._parse("")["ok"] is False
