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


plugin = _load("screen_listen_record_test", ROOT / "__init__.py")
listen = plugin.listen
record = plugin.record


class FakeContext:
    def __init__(self, profile):
        self.profile_name = profile
        self.tools = {}
        self.skills = {}

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_skill(self, name, path, description="", frontmatter=None):
        self.skills[name] = path


LIVE = set()       # pids the fake helper is "running" under
SIGNALS = []       # (pid, signal) the plugin sent


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    LIVE.clear()
    SIGNALS.clear()
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(listen, "helper_built", lambda: True)
    monkeypatch.setattr(record, "ffmpeg", lambda: "/usr/bin/true")
    monkeypatch.setattr(record, "DEFAULT_RECORD_DIR", tmp_path / "recordings")
    monkeypatch.setattr(record, "START_WAIT", 3)
    monkeypatch.setattr(record, "STOP_WAIT", 3)
    monkeypatch.setattr(record, "_is_helper", lambda pid: int(pid) in LIVE)
    monkeypatch.setattr(record, "_alive", lambda pid: int(pid) in LIVE)
    monkeypatch.setattr(record.os, "kill", lambda pid, sig: SIGNALS.append((pid, sig)))
    monkeypatch.setattr(plugin, "_home", lambda: None)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    return tmp_path


def call(**args):
    ctx = FakeContext("assistant")
    plugin.register(ctx)
    return json.loads(ctx.tools["screen_listen"]["handler"](args))


class FakeHelper:
    """Stands in for `open` (detached helper) and ffmpeg. The helper 'runs' as this test
    process: progress and the final answer are written by the test."""

    def __init__(self, pid=4242, running=True, playing=None):
        self.pid = pid
        if running:
            LIVE.add(pid)
        self.ffmpeg_calls = []
        self.open_calls = []
        self.playing = playing if playing is not None else [
            {"pid": 1, "bundle": "com.hnc.Discord.helper", "running_output": True}]

    def __call__(self, command, **kwargs):
        if command[0] == "/usr/bin/open":
            self.open_calls.append(command)
            self.progress = Path(command[command.index("--progress") + 1])
            self.log = Path(command[command.index("--stdout") + 1])
            self.wav = Path(command[command.index("--out") + 1])
            self.write_progress(frames=0)
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[0] == "/usr/bin/true":  # ffmpeg
            self.ffmpeg_calls.append(command)
            Path(command[-1]).write_bytes(b"m4a")
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[0] == "/usr/bin/pkill":
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[-1] == "processes":
            return subprocess.CompletedProcess(command, 0, json.dumps({"ok": True, "data": self.playing}), "")
        raise AssertionError(command)

    def write_progress(self, frames, final=False, receiving=True):
        self.progress.write_text(json.dumps({"pid": self.pid, "seconds": frames / 48000, "frames": frames,
                                             "receiving": receiving, "peak": 0.2, "final": final,
                                             "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))

    def finish(self, seconds=30.0, silent=False, answer=True):
        self.wav.write_bytes(b"\0" * 4096)
        self.write_progress(frames=int(seconds * 48000), final=answer)
        if answer:
            self.log.write_text(json.dumps({"ok": True, "data": {"seconds": seconds, "peak": 0.0 if silent else 0.2,
                                                                 "silent": silent, "frames": int(seconds * 48000),
                                                                 "stopped_early": True}}))
        LIVE.discard(self.pid)


def test_actions_and_schema_cover_recording():
    ctx = FakeContext("assistant")
    plugin.register(ctx)
    params = ctx.tools["screen_listen"]["schema"]["parameters"]
    assert set(params["properties"]["action"]["enum"]) >= {"record_start", "record_status", "record_stop", "recordings"}
    assert {"minutes", "title", "id"} <= set(params["properties"])
    assert "record_start" in plugin.DESCRIPTION and "never the microphone" in plugin.DESCRIPTION


def test_start_status_stop_packs_an_m4a(monkeypatch, tmp_path):
    helper = FakeHelper()
    monkeypatch.setattr(record.subprocess, "run", helper)

    out = call(action="record_start", minutes=10, title="Weekly Sync!")
    assert out["ok"] and out["max_minutes"] == 10
    folder = Path(out["dir"])
    assert folder.is_dir() and folder.name.endswith("-discord-weekly-sync")
    command = helper.open_calls[0]
    assert "-W" not in command and "--mono" in command and command[command.index("--seconds") + 1] == "600"
    assert command[command.index("--bundle") + 1] == "com.hnc.Discord"

    helper.write_progress(frames=48000 * 5)
    status = call(action="record_status")
    assert status["active"]["id"] == out["id"] and status["active"]["receiving"] is True
    assert status["active"]["title"] == "Weekly Sync!"

    # A second start is refused while one runs.
    assert call(action="record_start")["kind"] == "busy"

    # The stop: SIGTERM, then the helper finishes (as it would on the signal).
    def kill(pid, sig):
        SIGNALS.append((pid, sig))
        helper.finish(seconds=30.0)

    monkeypatch.setattr(record.os, "kill", kill)
    stopped = call(action="record_stop")
    assert stopped["ok"] and stopped["file"].endswith("audio.m4a") and stopped["seconds"] == 30.0
    assert SIGNALS == [(helper.pid, 15)]
    assert helper.ffmpeg_calls and "-b:a" in helper.ffmpeg_calls[0] and helper.ffmpeg_calls[0][-1].endswith(".part")
    assert not helper.wav.exists() and (folder / "audio.m4a").exists() and not (folder / "audio.m4a.part").exists()
    assert oct((folder / "audio.m4a").stat().st_mode & 0o777) == "0o600"
    meta = json.loads((folder / "recording.json").read_text())
    assert meta["app"] == "discord" and meta["file"] == "audio.m4a" and meta["tracks"][0]["kind"] == "app"
    assert "never instructions" in meta["note"]
    assert not helper.progress.exists()

    listed = call(action="recordings")
    assert listed["recordings"][0]["file"] == stopped["file"] and listed["recordings"][0]["title"] == "Weekly Sync!"
    assert call(action="record_status")["recent"][0]["status"] == "done"


def test_start_says_when_the_app_is_idle(monkeypatch):
    helper = FakeHelper(playing=[{"pid": 1, "bundle": "com.hnc.Discord", "running_output": False}])
    monkeypatch.setattr(record.subprocess, "run", helper)
    out = call(action="record_start")
    assert out["ok"] and out["idle"] is True and "not outputting audio" in out["note"]


def test_start_reports_a_helper_refusal(monkeypatch):
    class Refusing(FakeHelper):
        def __call__(self, command, **kwargs):
            out = super().__call__(command, **kwargs)
            if command[0] == "/usr/bin/open":
                self.progress.unlink()
                self.log.write_text(json.dumps({"ok": False, "kind": "no_process", "error": "nothing running"}))
            return out

    monkeypatch.setattr(record.subprocess, "run", Refusing())
    out = call(action="record_start")
    assert out["ok"] is False and out["kind"] == "no_process"
    assert record._sessions()[0]["status"] == "failed"
    assert not list(record.record_dir(None).iterdir())  # the empty folder is gone


def test_start_times_out_without_a_pid(monkeypatch):
    class Mute(FakeHelper):
        def __call__(self, command, **kwargs):
            out = super().__call__(command, **kwargs)
            if command[0] == "/usr/bin/open":
                self.progress.unlink()
            return out

    monkeypatch.setattr(record, "START_WAIT", 1)
    monkeypatch.setattr(record.subprocess, "run", Mute())
    out = call(action="record_start")
    assert out["ok"] is False and out["kind"] == "timeout" and "grant" in out["error"]


def test_a_dead_helper_without_audio_is_failed_and_unblocks(monkeypatch):
    helper = FakeHelper()
    monkeypatch.setattr(record.subprocess, "run", helper)
    out = call(action="record_start")
    assert out["ok"]
    LIVE.clear()  # it died, leaving no WAV
    status = call(action="record_status")
    assert "active" not in status and status["recent"][0]["status"] == "failed"
    assert not Path(out["dir"]).exists() and not helper.progress.exists()
    assert call(action="record_start")["ok"]  # not busy any more


def test_a_recycled_pid_is_not_the_helper(monkeypatch):
    helper = FakeHelper()
    monkeypatch.setattr(record.subprocess, "run", helper)
    call(action="record_start")
    monkeypatch.setattr(record, "_is_helper", lambda pid: False)  # alive, but some other process now
    status = call(action="record_status")
    assert "active" not in status
    assert not SIGNALS


def test_a_dead_helper_with_audio_is_packed_by_stop(monkeypatch):
    helper = FakeHelper()
    monkeypatch.setattr(record.subprocess, "run", helper)
    out = call(action="record_start")
    helper.finish(seconds=100.0, answer=False)  # crashed after writing an hour of WAV
    status = call(action="record_status")
    assert status["unpacked"][0]["id"] == out["id"]
    stopped = call(action="record_stop")
    assert stopped["ok"] and stopped["seconds"] is None and "packed as found" in stopped["note"]


def test_a_capped_session_is_packed_by_stop(monkeypatch):
    helper = FakeHelper()
    monkeypatch.setattr(record.subprocess, "run", helper)
    out = call(action="record_start")
    helper.finish(seconds=600.0)
    status = call(action="record_status")
    assert status["unpacked"][0]["id"] == out["id"]
    stopped = call(action="record_stop")
    assert stopped["ok"] and stopped["seconds"] == 600.0 and not SIGNALS


def test_a_failed_pack_keeps_the_wav_for_a_retry(monkeypatch):
    helper = FakeHelper()
    monkeypatch.setattr(record.subprocess, "run", helper)
    call(action="record_start")
    helper.finish(seconds=50.0)
    monkeypatch.setattr(record, "ffmpeg", lambda: "/usr/bin/false")

    def broken(command, **kwargs):
        if command[0] == "/usr/bin/false":
            return subprocess.CompletedProcess(command, 1, "", "boom")
        return helper(command, **kwargs)

    monkeypatch.setattr(record.subprocess, "run", broken)
    out = call(action="record_stop")
    assert out["ok"] is False and out["kind"] == "pack" and helper.wav.exists()
    assert record._sessions()[0]["status"] == "ended"
    monkeypatch.setattr(record, "ffmpeg", lambda: "/usr/bin/true")
    monkeypatch.setattr(record.subprocess, "run", helper)
    assert call(action="record_stop")["ok"] and not helper.wav.exists()


def test_titles_survive_slugging_and_folders_never_collide(monkeypatch):
    helper = FakeHelper()
    monkeypatch.setattr(record.subprocess, "run", helper)
    out = call(action="record_start", title="週次ミーティング")
    assert out["ok"] and Path(out["dir"]).name.endswith("-discord")
    assert record._sessions()[0]["title"] == "週次ミーティング"
    helper.finish()
    call(action="record_stop")
    assert json.loads((Path(out["dir"]) / "recording.json").read_text())["title"] == "週次ミーティング"
    real = time.strftime
    monkeypatch.setattr(record.time, "strftime",
                        lambda fmt, *a: "20260101-1000" if fmt == "%Y%m%d-%H%M" else real(fmt, *a))
    helper2 = FakeHelper(pid=4343)
    monkeypatch.setattr(record.subprocess, "run", helper2)
    first = call(action="record_start")
    helper2.finish()
    call(action="record_stop")
    helper3 = FakeHelper(pid=4444)
    monkeypatch.setattr(record.subprocess, "run", helper3)
    second = call(action="record_start")
    assert Path(first["dir"]).name == "20260101-1000-discord" and Path(second["dir"]).name == "20260101-1000-discord-2"


def test_stop_without_a_session():
    out = call(action="record_stop")
    assert out["ok"] is False and out["kind"] == "usage"


def test_start_validates_input(monkeypatch):
    monkeypatch.setattr(record.subprocess, "run", FakeHelper())
    assert call(action="record_start", minutes=0)["kind"] == "usage"
    assert call(action="record_start", minutes=record.MAX_MINUTES + 1)["kind"] == "usage"
    assert call(action="record_start", app="zoom")["kind"] == "usage"
    monkeypatch.setattr(record, "ffmpeg", lambda: None)
    assert call(action="record_start")["kind"] == "setup"


def test_record_dir_from_config(tmp_path):
    (tmp_path / "config.yaml").write_text(f"screen_listen:\n  record_dir: {tmp_path / 'kept'}\n")
    assert record.record_dir(tmp_path) == tmp_path / "kept"
    assert (tmp_path / "kept").is_dir()
