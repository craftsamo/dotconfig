import importlib.util
import json
from pathlib import Path
import signal
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

    def __init__(self, pid=4242, running=True, playing=None, video_pid=4343, video_refused=None, windows=None,
                 windows_refused=None, mic_pid=4444, mic_refused=None):
        self.pid = pid
        self.video_pid = video_pid
        self.video_refused = video_refused   # an error the capture helper answers with instead of starting
        self.video = None
        self.mic_pid = mic_pid
        self.mic_refused = mic_refused
        self.mic = None
        self.mic_muted = False
        self.windows = windows or []
        self.windows_refused = windows_refused
        if running:
            LIVE.add(pid)
        self.ffmpeg_calls = []
        self.open_calls = []
        self.playing = playing if playing is not None else [
            {"pid": 1, "bundle": "com.hnc.Discord.helper", "running_output": True}]

    def __call__(self, command, **kwargs):
        if command[0] == "/usr/bin/open" and "windows" in command:
            self.open_calls.append(command)
            answer = ({"ok": False, "kind": "permission", "error": self.windows_refused} if self.windows_refused
                      else {"ok": True, "data": self.windows})
            Path(command[command.index("--stdout") + 1]).write_text(json.dumps(answer))
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[0] == "/usr/bin/open" and "mic" in command:
            self.open_calls.append(command)
            self.mic = {"progress": Path(command[command.index("--progress") + 1]),
                        "log": Path(command[command.index("--stdout") + 1]),
                        "wav": Path(command[command.index("--out") + 1])}
            if self.mic_refused:
                self.mic["log"].write_text(json.dumps({"ok": False, "kind": "permission", "error": self.mic_refused}))
            else:
                LIVE.add(self.mic_pid)
                self.write_mic_progress(frames=0)
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[0] == "/usr/bin/open" and "capture" in command:
            self.open_calls.append(command)
            self.video = {"progress": Path(command[command.index("--progress") + 1]),
                          "log": Path(command[command.index("--stdout") + 1]),
                          "mp4": Path(command[command.index("--out") + 1])}
            if self.video_refused:
                self.video["log"].write_text(json.dumps({"ok": False, "kind": "permission", "error": self.video_refused}))
            else:
                LIVE.add(self.video_pid)
                self.write_video_progress(frames=0)
            return subprocess.CompletedProcess(command, 0, "", "")
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
        if command[0] == "/usr/bin/pkill" and "mic" in command[-1]:
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
                                                                 "started_at": 1_700_000_000_000,
                                                                 "first_frame_at": 1_700_000_000_150,
                                                                 "stopped_early": True}}))
        LIVE.discard(self.pid)
        if self.video and self.video_pid in LIVE:
            self.finish_video(seconds)
        if self.mic and self.mic_pid in LIVE:
            self.finish_mic(seconds)

    def write_mic_progress(self, frames, final=False):
        self.mic["progress"].write_text(json.dumps({"pid": self.mic_pid, "seconds": frames / 48000, "frames": frames,
                                                    "receiving": True, "muted": self.mic_muted, "peak": 0.3,
                                                    "final": final,
                                                    "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))

    def finish_mic(self, seconds=30.0, muted_spans=None, silent=False):
        self.mic["wav"].write_bytes(b"\0" * 4096)
        self.write_mic_progress(frames=int(seconds * 48000), final=True)
        self.mic["log"].write_text(json.dumps({"ok": True, "data": {
            "seconds": seconds, "started_at": 1_700_000_000_800, "first_frame_at": 1_700_000_001_050,
            "peak": 0.0 if silent else 0.3, "silent": silent, "frames": int(seconds * 48000),
            "muted_spans": muted_spans or []}}))
        LIVE.discard(self.mic_pid)

    def write_video_progress(self, frames, final=False):
        self.video["progress"].write_text(json.dumps({"pid": self.video_pid, "seconds": frames / 10, "frames": frames,
                                                      "receiving": True, "final": final,
                                                      "window": {"id": 777, "title": "Weekly", "width": 1280, "height": 800},
                                                      "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))

    def finish_video(self, seconds=30.0, frames=None, stopped_by=None):
        self.video["mp4"].write_bytes(b"\0" * 8192)
        self.write_video_progress(frames=int(seconds * 10), final=True)
        self.video["log"].write_text(json.dumps({"ok": True, "data": {
            "seconds": seconds, "frames": int(seconds * 10), "width": 1280, "height": 800, "fps": 10,
            "window": {"title": "Weekly - Discord"}, **({"stopped_by": stopped_by} if stopped_by else {})}}))
        LIVE.discard(self.video_pid)


def test_actions_and_schema_cover_recording():
    ctx = FakeContext("assistant")
    plugin.register(ctx)
    params = ctx.tools["screen_listen"]["schema"]["parameters"]
    assert set(params["properties"]["action"]["enum"]) >= {"record_start", "record_status", "record_stop", "recordings"}
    assert {"minutes", "title", "id", "video", "window", "window_id", "mic", "mute"} <= set(params["properties"])
    assert {"windows", "record_mic"} <= set(params["properties"]["action"]["enum"])
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


def test_video_records_the_window_beside_the_audio(monkeypatch):
    helper = FakeHelper()
    monkeypatch.setattr(record.subprocess, "run", helper)

    out = call(action="record_start", minutes=5, video=True, window="Weekly")
    assert out["ok"] and out["video"] is True and "video.mp4" in out["video_note"]
    assert out["video_window"] == {"id": 777, "title": "Weekly", "width": 1280, "height": 800}
    capture = [c for c in helper.open_calls if "capture" in c][0]
    assert capture[capture.index("--seconds") + 1] == "300" and capture[capture.index("--window") + 1] == "Weekly"
    assert "--window-id" not in capture
    assert capture[capture.index("--fps") + 1] == str(record.VIDEO_FPS) == "30" and "--no-audio" not in capture
    assert capture[capture.index("--max-width") + 1] == str(record.VIDEO_MAX_WIDTH) and "30 fps" in out["video_note"]
    assert capture[capture.index("--out") + 1] == str(Path(out["dir"]) / "video.mp4")

    helper.write_progress(frames=48000 * 5)
    helper.write_video_progress(frames=50)
    status = call(action="record_status")["active"]
    assert status["video"] == {"seconds": 5.0, "frames": 50, "recording": True}

    def kill(pid, sig):
        SIGNALS.append((pid, sig))
        if pid == helper.video_pid:
            helper.finish_video(seconds=29.0)
        else:
            helper.finish(seconds=30.0)

    monkeypatch.setattr(record.os, "kill", kill)
    stopped = call(action="record_stop")
    assert stopped["ok"] and stopped["seconds"] == 30.0
    assert [s for s in SIGNALS] == [(helper.video_pid, 15), (helper.pid, 15)]   # the video first, then the audio
    assert stopped["video"]["file"] == str(Path(stopped["dir"]) / "video.mp4") and stopped["video"]["width"] == 1280
    assert stopped["video"]["seconds"] == 29.0 and oct(Path(stopped["video"]["file"]).stat().st_mode & 0o777) == "0o600"
    meta = json.loads((Path(stopped["dir"]) / "recording.json").read_text())
    assert meta["video"] == "video.mp4" and [t["kind"] for t in meta["tracks"]] == ["app", "window"]
    assert meta["tracks"][1]["window"]["title"] == "Weekly - Discord"
    assert not helper.video["progress"].exists() and not helper.video["log"].exists()
    listed = call(action="recordings")["recordings"][0]
    assert listed["video"] == stopped["video"]["file"]


def test_windows_lists_what_the_video_can_record_and_window_id_picks_one(monkeypatch):
    helper = FakeHelper(windows=[{"id": 41, "title": "general | Server - Discord", "width": 1200, "height": 900,
                                  "on_screen": True, "pid": 7, "bundle": "com.hnc.Discord"},
                                 {"id": 42, "title": "general", "width": 880, "height": 500, "on_screen": True}])
    monkeypatch.setattr(record.subprocess, "run", helper)
    monkeypatch.setattr(listen.subprocess, "run", helper)
    out = call(action="windows")
    assert out["ok"] and [w["id"] for w in out["windows"]] == [41, 42] and "pop-out" in out["note"]
    assert set(out["windows"][0]) == {"id", "title", "width", "height", "on_screen"}   # no pid, no bundle
    listing = [c for c in helper.open_calls if "windows" in c][0]
    assert listing[0] == "/usr/bin/open" and "-W" in listing and listing[listing.index("--bundle") + 1] == "com.hnc.Discord"

    started = call(action="record_start", video=True, window_id=42, window="ignored")
    capture = [c for c in helper.open_calls if "capture" in c][0]
    assert started["video"] is True and capture[capture.index("--window-id") + 1] == "42" and "--window" not in capture


def test_windows_says_how_to_grant_screen_recording(monkeypatch):
    helper = FakeHelper(windows_refused="ScreenCaptureKit refused to list windows")
    monkeypatch.setattr(listen.subprocess, "run", helper)
    out = call(action="windows")
    assert out["ok"] is False and out["kind"] == "permission" and "grant-screen" in out["error"]


def test_mic_track_is_mixed_in_with_its_muted_spans(monkeypatch):
    helper = FakeHelper()
    monkeypatch.setattr(record.subprocess, "run", helper)

    out = call(action="record_start", mic=True)
    assert out["ok"] and out["mic"] is True and "record_mic" in out["mic_note"]
    mic_cmd = [c for c in helper.open_calls if "mic" in c][0]
    assert mic_cmd[mic_cmd.index("--out") + 1] == str(Path(out["dir"]) / "mic.wav") and "--muted" not in mic_cmd
    helper.write_progress(frames=48000 * 3)
    helper.write_mic_progress(frames=48000 * 3)
    status = call(action="record_status")["active"]
    assert status["mic"] == {"seconds": 3.0, "muted": False, "recording": True}

    # Pausing the user's voice: SIGUSR1 to the mic helper, confirmed from its progress file.
    def kill(pid, sig):
        SIGNALS.append((pid, sig))
        if pid == helper.mic_pid and sig in (signal.SIGUSR1, signal.SIGUSR2):
            helper.mic_muted = sig == signal.SIGUSR1
            helper.write_mic_progress(frames=48000 * 4)
        elif pid == helper.mic_pid:
            helper.finish_mic(seconds=29.0, muted_spans=[[4.0, 9.5]])
        else:
            helper.finish(seconds=30.0)

    monkeypatch.setattr(record.os, "kill", kill)
    paused = call(action="record_mic", mute=True)
    assert paused["ok"] and paused["muted"] is True and "paused" in paused["note"]
    assert call(action="record_status")["active"]["mic"]["muted"] is True
    resumed = call(action="record_mic", mute=False)
    assert resumed["muted"] is False
    assert SIGNALS == [(helper.mic_pid, signal.SIGUSR1), (helper.mic_pid, signal.SIGUSR2)]

    stopped = call(action="record_stop")
    assert stopped["ok"] and stopped["mic"] == {"mixed": True, "seconds": 29.0, "muted_spans": [[4.0, 9.5]],
                                                "note": stopped["mic"]["note"]}
    assert SIGNALS[2:] == [(helper.mic_pid, signal.SIGTERM), (helper.pid, signal.SIGTERM)]
    mix = helper.ffmpeg_calls[0]
    assert mix.count("-i") == 2 and mix[mix.index("-i") + 1].endswith("audio.wav") and "mic.wav" in " ".join(mix)
    graph = mix[mix.index("-filter_complex") + 1]
    # 1050 - 150: the gap between the two files' first audio, not between the launches (800).
    assert "adelay=900" in graph and f"volume={record.MIC_GAIN}" in graph and "amix=inputs=2" in graph
    assert record._track_offset_ms({"started_at": 500}, {"started_at": 200}) == 300          # launches as fallback
    assert record._track_offset_ms({"first_frame_at": 100}, {"first_frame_at": 400}) == 0    # never negative
    assert record._track_offset_ms({}, {"started_at": 1}) == 0
    assert mix[mix.index("-map") + 1] == "[out]"
    assert not helper.mic["wav"].exists() and not helper.mic["progress"].exists()
    meta = json.loads((Path(stopped["dir"]) / "recording.json").read_text())
    assert meta["mic"] == {"muted_spans": [[4.0, 9.5]], "seconds": 29.0}
    assert [t["kind"] for t in meta["tracks"]] == ["app", "mic"] and meta["tracks"][1]["file"] == "audio.m4a"
    assert "own voice" in meta["note"]
    assert call(action="recordings")["recordings"][0]["own_voice"] is True


def test_mic_that_cannot_start_leaves_the_recording_running(monkeypatch):
    helper = FakeHelper(mic_refused="could not start the input")
    monkeypatch.setattr(record.subprocess, "run", helper)
    out = call(action="record_start", mic=True)
    assert out["ok"] and out["mic"] is False and "grant-mic" in out["mic_detail"] and not helper.mic["wav"].exists()
    assert call(action="record_status")["active"]["mic"]["recording"] is False
    assert call(action="record_mic", mute=True)["kind"] == "usage"

    def kill(pid, sig):
        SIGNALS.append((pid, sig))
        helper.finish(seconds=12.0)

    monkeypatch.setattr(record.os, "kill", kill)
    stopped = call(action="record_stop")
    assert stopped["mic"]["mixed"] is False and "could not start" in stopped["mic"]["detail"]
    assert helper.ffmpeg_calls[0].count("-i") == 1 and "-filter_complex" not in helper.ffmpeg_calls[0]
    meta = json.loads((Path(stopped["dir"]) / "recording.json").read_text())
    assert "mic" not in meta and len(meta["tracks"]) == 1


def test_record_mic_without_a_mic_track_or_a_session_is_a_usage_error(monkeypatch):
    helper = FakeHelper()
    monkeypatch.setattr(record.subprocess, "run", helper)
    assert call(action="record_mic", mute=True)["kind"] == "usage"
    call(action="record_start")
    out = call(action="record_mic", mute=True)
    assert out["kind"] == "usage" and "no microphone track" in out["error"]
    assert call(action="record_mic")["kind"] == "usage"


def test_video_frame_rate_comes_from_the_call_then_the_profile(monkeypatch):
    helper = FakeHelper()
    monkeypatch.setattr(record.subprocess, "run", helper)
    monkeypatch.setattr(listen, "profile_config", lambda home: {"video_fps": 15, "video_max_width": 960})
    assert record.video_settings(None, {}) == (15, 960)
    assert record.video_settings(None, {"fps": 10}) == (10, 960)
    with pytest.raises(listen.ListenError):                                 # a call out of range is refused
        record.video_settings(None, {"fps": 500})
    monkeypatch.setattr(listen, "profile_config", lambda home: {"video_fps": 500, "video_max_width": True})
    assert record.video_settings(None, {}) == (60, 1280)                    # config: clamped; junk is the default
    call(action="record_start", video=True, fps=10)
    capture = [c for c in helper.open_calls if "capture" in c][0]
    assert capture[capture.index("--fps") + 1] == "10"
    assert call(action="record_start", video=True, fps="fast")["kind"] == "usage"


def test_video_that_cannot_start_leaves_the_audio_running(monkeypatch):
    helper = FakeHelper(video_refused="ScreenCaptureKit refused to list windows")
    monkeypatch.setattr(record.subprocess, "run", helper)
    out = call(action="record_start", video=True)
    assert out["ok"] and out["video"] is False and "grant-screen" in out["video_detail"]
    assert "refused" in out["video_detail"] and not helper.video["mp4"].exists()
    status = call(action="record_status")["active"]
    assert status["video"]["recording"] is False and "refused" in status["video"]["detail"]

    def kill(pid, sig):
        SIGNALS.append((pid, sig))
        helper.finish(seconds=12.0)

    monkeypatch.setattr(record.os, "kill", kill)
    stopped = call(action="record_stop")
    assert stopped["ok"] and stopped["video"]["kept"] is False and "refused" in stopped["video"]["detail"]
    assert SIGNALS == [(helper.pid, 15)]
    meta = json.loads((Path(stopped["dir"]) / "recording.json").read_text())
    assert "video" not in meta and len(meta["tracks"]) == 1


def test_video_that_ended_with_its_window_is_kept_shorter(monkeypatch):
    helper = FakeHelper()
    monkeypatch.setattr(record.subprocess, "run", helper)
    call(action="record_start", video=True)
    helper.finish_video(seconds=8.0, stopped_by="window closed")   # the window went, the audio goes on
    status = call(action="record_status")["active"]
    assert status["video"]["recording"] is False and "ended" in status["video"]["note"]

    def kill(pid, sig):
        SIGNALS.append((pid, sig))
        helper.finish(seconds=20.0)

    monkeypatch.setattr(record.os, "kill", kill)
    stopped = call(action="record_stop")
    assert stopped["video"]["seconds"] == 8.0 and "shorter" in stopped["video"]["note"]
    assert SIGNALS == [(helper.pid, 15)]


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
    assert "active" not in status and status["recent"][0]["status"] == "not_kept"
    assert "detail" in status["recent"][0] and '"error"' not in json.dumps(status) and '"failed"' not in json.dumps(status)
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
