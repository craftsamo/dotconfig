"""The Cloudflare Tunnel connector service: the launcher refuses without the Keychain token and
names the command that stores it, renders a loadable plist with no hostname in it, and the run
script hands the token to cloudflared through the environment, never on its command line."""

from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path

import pytest

HERMES = Path(__file__).resolve().parents[2]


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """An isolated HOME whose ~/.config/hermes is this checkout, with stub secret, cloudflared,
    launchctl and curl on PATH so nothing real is touched."""
    h = tmp_path / "home"
    (h / ".config").mkdir(parents=True)
    (h / ".config" / "hermes").symlink_to(HERMES)
    stubs = h / ".config" / "bin"
    stubs.mkdir()
    (stubs / "secret").write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        '  show) [ -f "$HOME/.token" ] || exit 1 ;;\n'
        '  get) [ -f "$HOME/.token" ] && cat "$HOME/.token" || exit 1 ;;\n'
        "  *) exit 2 ;;\n"
        "esac\n", encoding="utf-8")
    (stubs / "cloudflared").write_text(
        "#!/bin/sh\n"
        'printf "argv:%s\\n" "$*" > "$HOME/.cloudflared-call"\n'
        'printf "token:%s\\n" "${TUNNEL_TOKEN:-}" >> "$HOME/.cloudflared-call"\n', encoding="utf-8")
    (stubs / "launchctl").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (stubs / "curl").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    for stub in stubs.iterdir():
        stub.chmod(0o755)
    return h


def run(home: Path, script: str, *args: str) -> subprocess.CompletedProcess:
    env = {"HOME": str(home), "PATH": f"{home / '.config' / 'bin'}:/usr/bin:/bin",
           "SECRET_CLI": str(home / ".config" / "bin" / "secret")}
    return subprocess.run(["sh", str(HERMES / script), *args], env=env, capture_output=True, text=True)


def test_install_refuses_without_the_token_and_says_how_to_store_it(home: Path):
    done = run(home, "launchd/cloudflared-launchctl.sh", "install")
    assert done.returncode != 0
    assert "secret set CLOUDFLARE_TUNNEL_TOKEN -p hermes --scope cloudflare-access" in done.stderr
    assert not (home / "Library" / "LaunchAgents" / "local.hermes.cloudflared.tunnel.plist").exists()


def test_install_renders_a_loadable_plist_that_names_no_hostname(home: Path):
    (home / ".token").write_text("tok\n")
    done = run(home, "launchd/cloudflared-launchctl.sh", "install")
    assert done.returncode == 0, done.stderr
    plist = home / "Library" / "LaunchAgents" / "local.hermes.cloudflared.tunnel.plist"
    data = plistlib.loads(plist.read_bytes())
    assert data["Label"] == "local.hermes.cloudflared.tunnel" and data["KeepAlive"] is True
    assert data["ProgramArguments"][0] == f"{home}/.config/hermes/launchd/bin/hermes-cloudflared-tunnel"
    assert data["ProgramArguments"][-1] == f"{home}/.config/hermes/scripts/cloudflared-run.sh"
    assert data["EnvironmentVariables"]["TUNNEL_METRICS"] == "127.0.0.1:20241"
    text = plist.read_text()
    assert "tok" not in text and "http" not in text.replace("http://www.apple.com", "")


def test_the_run_script_hands_the_token_through_the_environment(home: Path):
    done = run(home, "scripts/cloudflared-run.sh")
    assert done.returncode == 78 and "CLOUDFLARE_TUNNEL_TOKEN" in done.stderr
    (home / ".token").write_text("tok\n")
    done = run(home, "scripts/cloudflared-run.sh")
    assert done.returncode == 0, done.stderr
    call = (home / ".cloudflared-call").read_text().splitlines()
    assert call == ["argv:tunnel --no-autoupdate run", "token:tok"]


def test_the_launcher_is_executable_in_git():
    out = subprocess.run(["git", "ls-files", "-s", "--", "launchd/cloudflared-launchctl.sh",
                          "launchd/bin/hermes-cloudflared-tunnel", "scripts/cloudflared-run.sh"],
                         cwd=HERMES, capture_output=True, text=True, check=True).stdout
    modes = {line.split()[3]: line.split()[0] for line in out.splitlines()}
    assert set(modes) == {"launchd/cloudflared-launchctl.sh", "launchd/bin/hermes-cloudflared-tunnel",
                          "scripts/cloudflared-run.sh"}
    assert all(mode == "100755" for mode in modes.values()), modes
