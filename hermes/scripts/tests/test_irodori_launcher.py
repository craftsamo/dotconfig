"""Irodori launcher: unregister, restart and --no-restart, in an isolated HOME (no agent loaded)."""

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
