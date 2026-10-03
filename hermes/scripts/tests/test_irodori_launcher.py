"""Irodori launcher: register (single and multi-clip), unregister, restart and --no-restart, in an isolated HOME (no agent loaded)."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import wave

import pytest


HERMES = Path(__file__).resolve().parents[2]


def write_wav(path, seed):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(bytes((seed + i) % 256 for i in range(4800)))
    return path


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path




@pytest.fixture
def irodori_home(tmp_path):
    home = tmp_path / "home"
    config = home / ".config" / "hermes"
    (config / "engines" / "irodori-tts").mkdir(parents=True)
    shutil.copy(HERMES / "engines" / "irodori-tts" / "pinned.conf", config / "engines" / "irodori-tts" / "pinned.conf")
    runtime = config / "local" / "irodori-tts"
    (runtime / "server").mkdir(parents=True)
    write_wav(runtime / "voices" / "keep.wav", 1)
    write_wav(runtime / "voices" / "drop.wav", 2)
    write(runtime / "default-voice", "keep\n")
    return home, runtime


def launch(home, *args):
    return subprocess.run(["bash", str(HERMES / "launchd" / "irodori-tts-launchctl.sh"), *args],
                          env={**os.environ, "HOME": str(home)}, capture_output=True, text=True)


def test_irodori_unregister_removes_a_voice_without_restart(irodori_home):
    home, runtime = irodori_home
    done = launch(home, "unregister", "--id", "drop", "--no-restart")
    assert done.returncode == 0, done.stderr
    assert not (runtime / "voices" / "drop.wav").exists() and (runtime / "voices" / "keep.wav").exists()
    assert not (runtime / "server" / ".env").exists()


def test_irodori_unregister_refuses_default_and_unknown(irodori_home):
    home, runtime = irodori_home
    assert "default voice" in launch(home, "unregister", "--id", "keep").stderr
    assert "not registered" in launch(home, "unregister", "--id", "ghost").stderr
    assert launch(home, "unregister", "--id", "../x").returncode != 0
    assert (runtime / "voices" / "keep.wav").exists()


def test_irodori_restart_without_agent_only_rewrites_env(irodori_home):
    home, runtime = irodori_home
    done = launch(home, "restart")
    assert done.returncode == 0, done.stderr
    assert "IRODORI_DEFAULT_VOICE=keep" in (runtime / "server" / ".env").read_text()


def test_irodori_register_groups_several_clips_under_one_voice(irodori_home, tmp_path):
    home, runtime = irodori_home
    clips = [write_wav(tmp_path / "src" / f"c{i}.wav", 10 + i) for i in range(3)]
    write_wav(runtime / "voices" / "grp.wav", 9)          # a single-file voice the group replaces
    args = [a for clip in clips for a in ("--voice", str(clip))]
    done = launch(home, "register", *args, "--id", "grp", "--no-restart")
    assert done.returncode == 0, done.stderr
    voices = runtime / "voices"
    assert [p.name for p in sorted((voices / "grp").iterdir())] == ["01.wav", "02.wav", "03.wav"]
    assert [(voices / "grp" / f"0{i + 1}.wav").read_bytes() for i in range(3)] == [c.read_bytes() for c in clips]
    alias = json.loads((voices / "voices.json").read_text())
    assert alias == {"grp": {"ref_wavs": ["grp/01.wav", "grp/02.wav", "grp/03.wav"]}}
    assert not (voices / "grp.wav").exists() and not (voices / ".grp.partial").exists()
    assert (voices / "keep.wav").exists() and (voices / "drop.wav").exists()

    # Back to one clip: the group and its alias go, and so does the emptied voices.json.
    done = launch(home, "register", "--voice", str(clips[0]), "--id", "grp", "--no-restart")
    assert done.returncode == 0, done.stderr
    assert (voices / "grp.wav").read_bytes() == clips[0].read_bytes()
    assert not (voices / "grp").exists() and not (voices / "voices.json").exists()


def test_irodori_unregister_removes_a_group_and_only_its_alias(irodori_home, tmp_path):
    home, runtime = irodori_home
    clips = [write_wav(tmp_path / "src" / f"c{i}.wav", 20 + i) for i in range(2)]
    for voice_id in ("a", "b"):
        args = [a for clip in clips for a in ("--voice", str(clip))]
        assert launch(home, "register", *args, "--id", voice_id, "--no-restart").returncode == 0
    done = launch(home, "unregister", "--id", "a", "--no-restart")
    assert done.returncode == 0, done.stderr
    voices = runtime / "voices"
    assert not (voices / "a").exists() and (voices / "b").is_dir()
    assert json.loads((voices / "voices.json").read_text()) == {"b": {"ref_wavs": ["b/01.wav", "b/02.wav"]}}


def test_irodori_default_falls_back_to_the_first_id_of_either_shape(irodori_home, tmp_path):
    home, runtime = irodori_home
    (runtime / "default-voice").unlink()
    clips = [write_wav(tmp_path / "src" / f"c{i}.wav", 30 + i) for i in range(2)]
    args = [a for clip in clips for a in ("--voice", str(clip))]
    assert launch(home, "register", *args, "--id", "alpha", "--no-restart").returncode == 0
    done = launch(home, "restart")
    assert done.returncode == 0, done.stderr
    assert "IRODORI_DEFAULT_VOICE=alpha" in (runtime / "server" / ".env").read_text()


def test_irodori_register_rejects_a_missing_clip_without_touching_the_voice(irodori_home, tmp_path):
    home, runtime = irodori_home
    good = write_wav(tmp_path / "src" / "ok.wav", 40)
    done = launch(home, "register", "--voice", str(good), "--voice", str(tmp_path / "nope.wav"),
                  "--id", "keep", "--no-restart")
    assert done.returncode != 0 and "not found" in done.stderr
    assert (runtime / "voices" / "keep.wav").exists() and not (runtime / "voices" / "keep").exists()


def test_irodori_ignores_empty_or_misnamed_directories(irodori_home, tmp_path):
    home, runtime = irodori_home
    voices = runtime / "voices"
    (voices / "empty").mkdir()
    write_wav(voices / "bad.name" / "01.wav", 50)
    clips = [write_wav(tmp_path / "src" / f"c{i}.wav", 60 + i) for i in range(2)]
    args = [a for clip in clips for a in ("--voice", str(clip))]
    assert launch(home, "register", *args, "--id", "grp", "--no-restart").returncode == 0
    assert json.loads((voices / "voices.json").read_text()) == {"grp": {"ref_wavs": ["grp/01.wav", "grp/02.wav"]}}
    # "bad.name" and "empty" sort before "drop"; ignored, they cannot become the fallback default
    (runtime / "default-voice").unlink()
    assert launch(home, "restart").returncode == 0
    assert "IRODORI_DEFAULT_VOICE=drop" in (runtime / "server" / ".env").read_text()
