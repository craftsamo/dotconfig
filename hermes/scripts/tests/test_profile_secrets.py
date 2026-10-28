"""profile-secrets.sh grants the localhost A2A identity to every worker without naming it, so a
profile kept in the private overlay is reachable like the tracked ones."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

HELPER = Path(__file__).resolve().parents[1] / "profile-secrets.sh"
GRANT = "A2A_ALLOWED_USERS=ip:127.0.0.1"


def run(profile: str, home: Path) -> list[str]:
    secret = home / ".config" / "bin" / "secret"
    if not secret.exists():
        secret.parent.mkdir(parents=True)
        secret.write_text("#!/bin/sh\nexit 0\n")  # no Keychain: every layer is empty
        secret.chmod(0o755)
    proc = subprocess.run(["/bin/sh", str(HELPER), profile], capture_output=True, text=True, timeout=30,
                          env={"HOME": str(home), "PATH": "/usr/bin:/bin"})
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.splitlines()


@pytest.mark.parametrize("profile", ["creator", "researcher", "searcher", "writer", "video-creator", "advisor"])
def test_every_worker_accepts_localhost_peers(tmp_path, profile):
    assert GRANT in run(profile, tmp_path)


@pytest.mark.parametrize("profile", ["assistant", "default"])
def test_the_assistant_and_the_root_profile_do_not(tmp_path, profile):
    assert GRANT not in run(profile, tmp_path)


def test_the_inbox_topic_is_the_cron_thread_and_the_home_channel_thread(tmp_path):
    """Both bare `deliver: telegram` cron jobs and webhook routes land in the Inbox: the first
    through the cron thread, the second through the home channel's thread."""
    config = tmp_path / ".hermes" / "profiles" / "assistant" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("platforms:\n  telegram:\n    extra:\n      dm_topics:\n      - chat_id: '1'\n"
                      "        topics:\n        - name: Inbox\n          thread_id: 4242\n", encoding="utf-8")
    lines = run("assistant", tmp_path)
    assert "TELEGRAM_CRON_THREAD_ID=4242" in lines and "TELEGRAM_HOME_CHANNEL_THREAD_ID=4242" in lines


def test_without_an_inbox_cron_fails_closed_and_the_home_channel_keeps_no_thread(tmp_path):
    lines = run("assistant", tmp_path)
    assert "TELEGRAM_CRON_THREAD_ID=disabled" in lines
    assert not any(line.startswith("TELEGRAM_HOME_CHANNEL_THREAD_ID=") for line in lines)
