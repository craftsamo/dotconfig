import importlib.util
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plugin = _load("media_inspect_plugin_test", ROOT / "__init__.py")
media = plugin.media
needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                                  reason="ffmpeg/ffprobe not installed")


class FakeContext:
    def __init__(self, profile):
        self.profile_name = profile
        self.tools = {}

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    root = tmp_path / "scratch"
    monkeypatch.setattr(media, "scratch_root", lambda: root)
    return root


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("ffmpeg/ffprobe not installed")
    path = tmp_path_factory.mktemp("media") / "clip.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10:duration=3",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-shortest",
                    "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def call(profile, **args):
    ctx = FakeContext(profile)
    plugin.register(ctx)
    return json.loads(ctx.tools["media_inspect"]["handler"](args))


def test_only_listed_profiles_get_the_tool():
    for profile in ("creator", "assistant"):
        ctx = FakeContext(profile)
        plugin.register(ctx)
        tool = ctx.tools["media_inspect"]
        assert tool["toolset"] == "media_inspect"
        assert tool["schema"]["parameters"]["properties"]["action"]["enum"] == list(plugin.PROFILES[profile])
    for profile in ("image-creator", "marketer", "writer", "researcher"):
        ctx = FakeContext(profile)
        plugin.register(ctx)
        assert ctx.tools == {}


def test_action_outside_the_profile_list_is_refused(clip):
    with pytest.raises(media.MediaError, match="not offered"):
        media.run({"action": "sheet", "path": str(clip)}, "x", allowed=("probe",))


@pytest.mark.parametrize("path, message", [
    ("https://example.com/a.mp4", "never fetched"),
    ("/definitely/missing.mp4", "no such file"),
    ("", "path is required"),
])
def test_bad_paths_are_refused(path, message):
    result = call("creator", action="probe", path=path)
    assert message in result["error"]


@needs_ffmpeg
def test_probe_reports_streams(clip):
    result = call("creator", action="probe", path=str(clip))
    assert result["duration"] == pytest.approx(3, abs=0.2)
    video = next(s for s in result["streams"] if s["type"] == "video")
    assert (video["width"], video["height"], video["fps"]) == (320, 240, 10)
    assert any(s["type"] == "audio" for s in result["streams"])


@needs_ffmpeg
def test_frames_by_time_and_frame_number_land_in_scratch(clip, scratch):
    before = clip.stat().st_mtime
    by_time = call("assistant", action="frames", path=str(clip), times=[0.5, 2.0])
    by_frame = call("assistant", action="frames", path=str(clip), frames=[5, 20])
    for result in (by_time, by_frame):
        assert [f["time"] for f in result["frames"]] == [0.5, 2.0]
        for frame in result["frames"]:
            assert Path(frame["path"]).is_file()
            assert Path(frame["path"]).is_relative_to(scratch / "assistant")
    assert clip.stat().st_mtime == before
    assert sorted(p.name for p in clip.parent.iterdir()) == ["clip.mp4"]


@needs_ffmpeg
def test_frames_limits(clip):
    assert "at most" in call("creator", action="frames", path=str(clip),
                             times=[0.1] * (media.MAX_FRAMES + 1))["error"]
    assert "past the end" in call("creator", action="frames", path=str(clip), times=[9])["error"]
    assert "not both" in call("creator", action="frames", path=str(clip), times=[1], frames=[1])["error"]
    assert "needs times or frames" in call("creator", action="frames", path=str(clip))["error"]


@needs_ffmpeg
def test_sheet_even_spacing_and_grid(clip):
    result = call("creator", action="sheet", path=str(clip), count=5, columns=3, width=160)
    assert Path(result["sheet"]).is_file()
    assert (result["rows"], result["columns"]) == (2, 3)
    assert [t["tile"] for t in result["tiles"]] == [1, 2, 3, 4, 5]
    assert result["tiles"][3] == {"tile": 4, "row": 2, "column": 1, "time": result["tiles"][3]["time"]}
    times = [t["time"] for t in result["tiles"]]
    assert times == sorted(times) and 0 < times[0] < times[-1] < 3
    info = media.probe(Path(result["sheet"]))
    sheet = next(s for s in info["streams"] if s["type"] == "video")
    assert (sheet["width"], sheet["height"]) == (480, 240)


@needs_ffmpeg
def test_sheet_of_an_image(tmp_path):
    image = tmp_path / "still.png"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=200x100",
                    "-frames:v", "1", str(image)], check=True)
    result = call("creator", action="frames", path=str(image), times=[0])
    assert Path(result["frames"][0]["path"]).is_file()


def test_cleanup_removes_only_old_runs(scratch):
    old = scratch / "creator" / "old"
    new = scratch / "creator" / "new"
    old.mkdir(parents=True)
    new.mkdir(parents=True)
    stamp = time.time() - 10 * 86400
    os.utime(old, (stamp, stamp))
    assert media.cleanup(older_than_days=7) == 1
    assert not old.exists() and new.exists()
