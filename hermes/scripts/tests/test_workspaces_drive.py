"""The Workspaces Drive mount: setup keeps keys off every command line, the launcher refuses before
setup and renders a plist with no secret, Group directories become relative links into the mount
(a real directory is reported, never moved; status only reports), the machine-local settings
override the defaults, the run script mounts the combined remote with the config password supplied
by command and stops cleanly, and migrate swaps a twice-checked copy for its link or rolls back."""

from __future__ import annotations

import os
import plistlib
import signal
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

HERMES = Path(__file__).resolve().parents[2]
LAUNCHCTL = "launchd/workspaces-drive-launchctl.sh"
RUN = "scripts/workspaces-drive-run.sh"
PASSWORD = "config-pass-value"

RCLONE_STUB = r"""#!/bin/sh
printf '%s\n' "$*" >> "$HOME/.rclone-calls"
sub=; a1=; a2=; skip=0
for arg do
  if [ "$skip" = 1 ]; then skip=0; continue; fi
  case "$arg" in
    --config|--password-command|-o|--cache-dir|--vfs-cache-mode|--vfs-cache-max-size|--vfs-cache-max-age) skip=1; continue ;;
    -*) continue ;;
  esac
  if [ -z "$sub" ]; then sub=$arg; elif [ -z "$a1" ]; then a1=$arg; elif [ -z "$a2" ]; then a2=$arg; fi
done
drive_path() { printf '%s\n' "$1" | sed -e 's|^wsdrive-drive:Workspaces/||' -e 's|^wsdrive-crypt:||'; }
case "$sub" in
  nfsmount)
    touch "$HOME/.mounted"
    trap 'rm -f "$HOME/.mounted"; exit 0' TERM
    while :; do sleep 0.1; done ;;
  listremotes) cat "$HOME/.remotes" 2>/dev/null ;;
  rcd)
    for arg do case "$arg" in unix://*) sock=${arg#unix://} ;; esac; done
    exec nc -lU "$sock" ;;
  mkdir) mkdir -p "$HOME/Workspaces/.drive/$(drive_path "$a1")" ;;
  copy)
    dest="$HOME/Workspaces/.drive/$(drive_path "$a2")"
    mkdir -p "$dest" && cp -R "$a1/." "$dest/" ;;
  check|cryptcheck)
    echo x >> "$HOME/.checks"
    [ -f "$HOME/.check-fails" ] && exit 1
    [ -f "$HOME/.second-check-fails" ] && [ "$(wc -l < "$HOME/.checks")" -ge 2 ] && exit 1 ;;
esac
exit 0
"""

# Keychain stub: one file per item under ~/.items; `set` reads the value from stdin.
SECRET_STUB = r"""#!/bin/sh
cmd=$1 name=$2
case "$cmd" in
  show) [ -f "$HOME/.items/$name" ] ;;
  get) [ -f "$HOME/.items/$name" ] && cat "$HOME/.items/$name" ;;
  set) mkdir -p "$HOME/.items" && cat > "$HOME/.items/$name" && printf '%s\n' "$*" >> "$HOME/.secret-sets" ;;
  *) exit 2 ;;
esac
"""

# curl stub for the setup socket: keeps each request body and names the created remote.
CURL_STUB = r"""#!/bin/sh
n=$(ls "$HOME"/.curl-body-* 2>/dev/null | wc -l | tr -d ' ')
body="$HOME/.curl-body-$n"
cat > "$body"
printf '%s:\n' "$(sed -n 's/^{"name":"\([^"]*\)".*/\1/p' "$body")" >> "$HOME/.remotes"
printf '{\n\t"Error": "",\n\t"State": ""\n}\n'
"""


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """An isolated HOME whose ~/.config/hermes is this checkout, with stub secret, rclone,
    launchctl, mount and diskutil on PATH; `mount` reports the Drive mount while ~/.mounted exists."""
    h = tmp_path / "home"
    (h / ".config").mkdir(parents=True)
    (h / ".config" / "hermes").symlink_to(HERMES)
    stubs = h / ".config" / "bin"
    stubs.mkdir()
    (stubs / "secret").write_text(SECRET_STUB, encoding="utf-8")
    (stubs / "rclone").write_text(RCLONE_STUB, encoding="utf-8")
    (stubs / "curl").write_text(CURL_STUB, encoding="utf-8")
    (stubs / "launchctl").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (stubs / "diskutil").write_text("#!/bin/sh\nrm -f \"$HOME/.mounted\"\n", encoding="utf-8")
    (stubs / "mount").write_text(
        "#!/bin/sh\n"
        '[ -f "$HOME/.mounted" ] && echo "localhost:/ on $HOME/Workspaces/.drive (nfs, nodev, nosuid, nobrowse)"\n'
        "exit 0\n", encoding="utf-8")
    for stub in stubs.iterdir():
        stub.chmod(0o755)
    (h / "Workspaces" / "Projects").mkdir(parents=True)
    (h / "Workspaces" / "Personal").mkdir(parents=True)
    return h


def env(home: Path) -> dict[str, str]:
    return {"HOME": str(home), "PATH": f"{home / '.config' / 'bin'}:/usr/bin:/bin",
            "SECRET_CLI": str(home / ".config" / "bin" / "secret"), "WSD_MOUNT_WAIT": "3"}


def run(home: Path, script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["sh", str(HERMES / script), *args], env=env(home), capture_output=True, text=True)


def set_up(home: Path, mounted: bool = True) -> Path:
    """What `setup` leaves behind, without the Google login: the Keychain item and a config."""
    (home / ".items").mkdir(exist_ok=True)
    (home / ".items" / "WORKSPACES_DRIVE_CONFIG_PASS").write_text(PASSWORD)
    local = home / ".hermes" / "local" / "workspaces-drive"
    local.mkdir(parents=True, exist_ok=True)
    (local / "rclone.conf").write_text("# Encrypted rclone configuration File\n")
    (home / "Workspaces" / ".drive").mkdir(exist_ok=True)
    if mounted:
        (home / ".mounted").write_text("")
    return local


def test_install_refuses_before_setup(home: Path):
    done = run(home, LAUNCHCTL, "install")
    assert done.returncode != 0
    assert "workspaces-drive-launchctl.sh setup" in done.stderr
    assert not (home / "Library" / "LaunchAgents" / "local.hermes.workspaces-drive.mount.plist").exists()


def test_install_renders_a_plist_with_no_secret(home: Path):
    set_up(home)
    done = run(home, LAUNCHCTL, "install")
    assert done.returncode == 0, done.stderr
    plist = home / "Library" / "LaunchAgents" / "local.hermes.workspaces-drive.mount.plist"
    data = plistlib.loads(plist.read_bytes())
    assert data["Label"] == "local.hermes.workspaces-drive.mount" and data["KeepAlive"] is True
    assert data["ProgramArguments"][0] == f"{home}/.config/hermes/launchd/bin/hermes-workspaces-drive-mount"
    assert data["ProgramArguments"][-1] == f"{home}/.config/hermes/scripts/workspaces-drive-run.sh"
    assert data["EnvironmentVariables"]["HERMES_LOCAL"] == f"{home}/.hermes/local"
    assert PASSWORD not in plist.read_text()


def test_setup_keeps_every_key_off_the_command_line(home: Path):
    # A unix socket path is limited to 104 bytes, so the state directory sits on a short path.
    with tempfile.TemporaryDirectory(prefix="wsd", dir="/tmp") as short:
        check_setup(home, Path(short))


def check_setup(home: Path, local_root: Path):
    environ = {**env(home), "HERMES_LOCAL": str(local_root)}

    def setup() -> subprocess.CompletedProcess:
        return subprocess.run(["sh", str(HERMES / LAUNCHCTL), "setup"], env=environ, capture_output=True,
                              text=True, timeout=60)

    done = setup()
    assert done.returncode == 0, done.stderr + done.stdout
    items = home / ".items"
    keys = [(items / n).read_text() for n in ("WORKSPACES_DRIVE_CONFIG_PASS", "WORKSPACES_DRIVE_CRYPT_PASSWORD",
                                               "WORKSPACES_DRIVE_CRYPT_SALT")]
    assert all(len(k) >= 32 for k in keys) and len(set(keys)) == 3
    argv = (home / ".rclone-calls").read_text() + (home / ".secret-sets").read_text()
    assert not any(k in argv for k in keys)
    bodies = sorted(home.glob(".curl-body-*"))
    drive, crypt = (b.read_text() for b in bodies)
    assert '"name":"wsdrive-drive","type":"drive"' in drive and '"scope":"drive"' in drive
    assert '"remote":"wsdrive-drive:Workspaces"' in crypt and keys[1] in crypt and keys[2] in crypt
    assert '"directory_name_encryption":"false"' in crypt
    assert "--no-env" in (home / ".secret-sets").read_text()
    mkdirs = [line for line in argv.splitlines() if " mkdir " in line]
    assert any(line.endswith("mkdir wsdrive-drive:Workspaces/Projects") for line in mkdirs)
    assert any(line.endswith("mkdir wsdrive-crypt:Personal") for line in mkdirs)
    assert not list((local_root / "workspaces-drive").glob("setup-rc.*"))
    assert oct((local_root / "workspaces-drive").stat().st_mode & 0o777) == "0o700"
    again = setup()
    assert again.returncode == 0, again.stderr
    assert len(list(home.glob(".curl-body-*"))) == 2


def test_an_interrupted_setup_stops_its_config_daemon(home: Path):
    (home / ".config" / "bin" / "curl").write_text("#!/bin/sh\ncat >/dev/null\nsleep 30\n", encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="wsd", dir="/tmp") as short:
        sock = Path(short) / "workspaces-drive" / "setup-rc.sock"
        proc = subprocess.Popen(["sh", str(HERMES / LAUNCHCTL), "setup"], env={**env(home), "HERMES_LOCAL": short},
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        deadline = time.time() + 15
        while not sock.exists() and time.time() < deadline:
            time.sleep(0.1)
        assert sock.exists(), "the setup daemon never opened its socket"
        time.sleep(0.5)
        os.killpg(proc.pid, signal.SIGINT)
        proc.communicate(timeout=15)
        time.sleep(0.3)
        daemons = subprocess.run(["pgrep", "-f", f"nc -lU {sock}"], capture_output=True, text=True).stdout
        assert daemons == "" and not sock.exists()


def test_status_reports_without_linking(home: Path):
    set_up(home)
    (home / "Workspaces" / "Projects" / "Alpha").mkdir()
    done = run(home, LAUNCHCTL, "status")
    assert "would link: Projects/Alpha/assets" in done.stdout
    assert not (home / "Workspaces" / "Projects" / "Alpha" / "assets").exists()
    assert not (home / "Workspaces" / ".drive" / "Projects").exists()


def test_links_wait_for_the_lock_and_a_dead_holder_releases_it(home: Path):
    local = set_up(home)
    (home / "Workspaces" / "Projects" / "Alpha").mkdir()
    lock = local / "links.lock"
    holder = subprocess.Popen(["lockf", "-k", "-t", "0", str(lock), "sleep", "60"])
    try:
        time.sleep(0.3)
        held = subprocess.run(["sh", str(HERMES / LAUNCHCTL), "links"], capture_output=True, text=True,
                              env={**env(home), "WSD_LOCK_WAIT": "1"}, timeout=60)
        assert held.returncode != 0 and "holds" in held.stderr
        assert not (home / "Workspaces" / "Projects" / "Alpha" / "assets").exists()
    finally:
        holder.kill()
        holder.wait()
    taken = run(home, LAUNCHCTL, "links")
    assert "linked: Projects/Alpha/assets" in taken.stdout


def test_migrate_refuses_while_a_file_is_open_and_rolls_back(home: Path):
    set_up(home)
    assets = home / "Workspaces" / "Projects" / "Alpha" / "assets"
    assets.mkdir(parents=True)
    (assets / "a.png").write_text("a")
    with open(assets / "a.png", "rb"):
        done = run(home, LAUNCHCTL, "migrate", "Projects/Alpha")
    assert done.returncode != 0 and "open in another process" in done.stderr
    assert assets.is_dir() and not assets.is_symlink() and (assets / "a.png").read_text() == "a"
    assert not (assets.parent / "assets.migrating").exists()


def test_links_make_relative_links_and_leave_real_directories(home: Path):
    set_up(home)
    ws = home / "Workspaces"
    (ws / "Projects" / "Alpha").mkdir()
    (ws / "Projects" / "Beta" / "assets").mkdir(parents=True)
    (ws / "Projects" / "Beta" / "assets" / "logo.png").write_text("x")
    (ws / "Personal" / "Notes").mkdir()
    done = run(home, LAUNCHCTL, "links")
    assert done.returncode == 0, done.stderr
    alpha = ws / "Projects" / "Alpha" / "assets"
    assert os.readlink(alpha) == "../../.drive/Projects/Alpha/assets"
    assert alpha.resolve() == (ws / ".drive" / "Projects" / "Alpha" / "assets").resolve()
    assert os.readlink(ws / "Personal" / "Notes" / "assets") == "../../.drive/Personal/Notes/assets"
    assert (ws / "Projects" / "Beta" / "assets").is_dir() and not (ws / "Projects" / "Beta" / "assets").is_symlink()
    assert "local: Projects/Beta/assets is a real directory" in done.stdout
    # Folders are made on Drive through rclone, never through the mount (which
    # macOS refuses to a shell that launchd started).
    calls = (home / ".rclone-calls").read_text()
    assert "mkdir wsdrive-drive:Workspaces/Projects/Alpha/assets" in calls
    assert "mkdir wsdrive-crypt:Personal/Notes/assets" in calls
    again = run(home, LAUNCHCTL, "links")
    assert "linked:" not in again.stdout


def test_the_sweep_deletes_appledouble_files_on_drive_not_into_its_trash(home: Path):
    set_up(home)
    script = f'. "{HERMES}/scripts/workspaces-drive-env.sh"; wsd_sweep'
    subprocess.run(["sh", "-c", script], env=env(home), check=True)
    call = (home / ".rclone-calls").read_text().splitlines()[-1]
    assert " delete :combine,upstreams=" in call
    assert "--include ._* --include .DS_Store --drive-use-trash=false" in call


def test_links_refuse_while_unmounted(home: Path):
    set_up(home, mounted=False)
    (home / "Workspaces" / "Projects" / "Alpha").mkdir()
    done = run(home, LAUNCHCTL, "links")
    assert "not up" in done.stderr
    assert not (home / "Workspaces" / "Projects" / "Alpha" / "assets").exists()


def test_the_machine_local_settings_override_the_defaults(home: Path):
    local = set_up(home)
    (local / "settings.env").write_text('WSD_TREES="Projects=plain"\nWSD_LINK_DIRS="assets media"\n'
                                        'WSD_SKIP_GROUPS="Projects/Skip"\n')
    ws = home / "Workspaces"
    (ws / "Projects" / "Alpha").mkdir()
    (ws / "Projects" / "Skip").mkdir()
    (ws / "Personal" / "Notes").mkdir()
    done = run(home, LAUNCHCTL, "links")
    assert done.returncode == 0, done.stderr
    assert (ws / "Projects" / "Alpha" / "assets").is_symlink() and (ws / "Projects" / "Alpha" / "media").is_symlink()
    assert not (ws / "Projects" / "Skip" / "assets").exists()
    assert not (ws / "Personal" / "Notes" / "assets").exists()


def test_remote_mapping_keeps_plain_and_encrypted_trees_apart(home: Path):
    script = (f'. "{HERMES}/scripts/workspaces-drive-env.sh"; wsd_remote Projects Alpha/assets; '
              'wsd_remote Personal Notes/assets; wsd_combine; wsd_remote Other || echo none')
    done = subprocess.run(["sh", "-c", script], env=env(home), capture_output=True, text=True)
    assert done.stdout.splitlines() == [
        "wsdrive-drive:Workspaces/Projects/Alpha/assets",
        "wsdrive-crypt:Personal/Notes/assets",
        ":combine,upstreams='Projects=wsdrive-drive:Workspaces/Projects Personal=wsdrive-crypt:Personal':",
        "none",
    ]


def test_the_run_script_refuses_a_mount_point_holding_files(home: Path):
    set_up(home, mounted=False)
    (home / "Workspaces" / ".drive" / "stray.txt").write_text("x")
    done = run(home, RUN)
    assert done.returncode == 78 and "not empty" in done.stderr


def test_the_run_script_mounts_links_and_stops_on_term(home: Path):
    set_up(home, mounted=False)
    (home / "Workspaces" / "Projects" / "Alpha").mkdir()
    proc = subprocess.Popen(["sh", str(HERMES / RUN)], env=env(home), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    link = home / "Workspaces" / "Projects" / "Alpha" / "assets"
    deadline = time.time() + 10
    while not link.is_symlink() and time.time() < deadline:
        time.sleep(0.1)
    try:
        assert link.is_symlink(), "the maintenance pass did not link the Group"
    finally:
        proc.send_signal(signal.SIGTERM)
        out, err = proc.communicate(timeout=10)
    assert proc.returncode == 0, err
    calls = (home / ".rclone-calls").read_text()
    mount_call = next(line for line in calls.splitlines() if " nfsmount " in line)
    assert "--password-command" in mount_call and PASSWORD not in calls
    assert "Projects=wsdrive-drive:Workspaces/Projects Personal=wsdrive-crypt:Personal" in mount_call
    assert "locallocks" in mount_call and "deadtimeout=30" in mount_call
    assert not (home / ".mounted").exists()


def test_migrate_swaps_a_checked_copy_for_its_link(home: Path):
    set_up(home)
    assets = home / "Workspaces" / "Projects" / "Alpha" / "assets"
    (assets / "sub").mkdir(parents=True)
    (assets / "a.png").write_text("a")
    (assets / "sub" / "b.mp4").write_text("b")
    done = run(home, LAUNCHCTL, "migrate", "Projects/Alpha")
    assert done.returncode == 0, done.stderr
    assert assets.is_symlink()
    assert (assets / "sub" / "b.mp4").read_text() == "b"
    assert not (assets.parent / "assets.migrating").exists()
    assert "moved: Projects/Alpha/assets -> Drive (2 files)" in done.stdout


def test_migrate_keeps_the_local_copy_when_the_check_fails(home: Path):
    set_up(home)
    (home / ".check-fails").write_text("")
    assets = home / "Workspaces" / "Projects" / "Alpha" / "assets"
    assets.mkdir(parents=True)
    (assets / "a.png").write_text("a")
    done = run(home, LAUNCHCTL, "migrate", "Projects/Alpha")
    assert done.returncode != 0
    assert assets.is_dir() and not assets.is_symlink() and (assets / "a.png").read_text() == "a"


def test_migrate_rolls_back_when_the_original_changed_after_the_copy(home: Path):
    set_up(home)
    (home / ".second-check-fails").write_text("")
    assets = home / "Workspaces" / "Projects" / "Alpha" / "assets"
    assets.mkdir(parents=True)
    (assets / "a.png").write_text("a")
    done = run(home, LAUNCHCTL, "migrate", "Projects/Alpha")
    assert done.returncode != 0 and "changed after it was copied" in done.stderr
    assert assets.is_dir() and not assets.is_symlink() and (assets / "a.png").read_text() == "a"
    assert not (assets.parent / "assets.migrating").exists()


def test_migrate_refuses_an_existing_staging_directory(home: Path):
    set_up(home)
    assets = home / "Workspaces" / "Projects" / "Alpha" / "assets"
    assets.mkdir(parents=True)
    (assets / "a.png").write_text("a")
    staging = assets.parent / "assets.migrating"
    staging.mkdir()
    (staging / "keep.txt").write_text("k")
    done = run(home, LAUNCHCTL, "migrate", "Projects/Alpha")
    assert done.returncode != 0 and "already exists" in done.stderr
    assert (staging / "keep.txt").read_text() == "k" and (assets / "a.png").exists()
    assert not (home / ".rclone-calls").exists() or " copy " not in (home / ".rclone-calls").read_text()


def test_the_scripts_are_executable_in_git():
    paths = ["launchd/workspaces-drive-launchctl.sh", "launchd/bin/hermes-workspaces-drive-mount",
             "scripts/workspaces-drive-run.sh"]
    out = subprocess.run(["git", "ls-files", "-s", "--", *paths], cwd=HERMES, capture_output=True,
                         text=True, check=True).stdout
    modes = {line.split()[3]: line.split()[0] for line in out.splitlines()}
    assert set(modes) == set(paths)
    assert all(mode == "100755" for mode in modes.values()), modes
