"""The Workspaces Drive engine (drive.py): setup keeps keys off every command line, install refuses
before setup and renders a plist with no secret, Group assets/ become relative links into the mount
(a real folder stays and is reported), folders inside a Group move to Drive and back with checked
copies or roll back, interrupted work is finished or undone, Drive folders missing here are linked
again, and the run loop mounts the combined remote with the config password supplied by command and
stops cleanly. rclone, the Keychain, launchctl, mount and diskutil are stubs; ~/Workspaces/.drive
stands in for Drive itself."""

from __future__ import annotations

import json
import os
import plistlib
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
HERMES = Path(__file__).resolve().parents[4]
DRIVE = PLUGIN / "drive.py"
PASSWORD = "config-pass-value"

RCLONE_STUB = r"""#!/bin/sh
printf '%s\n' "$*" >> "$HOME/.rclone-calls"
sub=; a1=; a2=; skip=0
for arg do
  if [ "$skip" = 1 ]; then skip=0; continue; fi
  case "$arg" in
    --config|--password-command|-o|--cache-dir|--vfs-cache-mode|--vfs-cache-max-size|--vfs-cache-max-age|\
    --dir-cache-time|--exclude|--include|--stats|--stats-log-level|--rc-addr) skip=1; continue ;;
    -*) continue ;;
  esac
  if [ -z "$sub" ]; then sub=$arg; elif [ -z "$a1" ]; then a1=$arg; elif [ -z "$a2" ]; then a2=$arg; fi
done
drive_path() { printf '%s\n' "$1" | sed -e 's|^wsdrive-drive:Workspaces/||' -e 's|^wsdrive-crypt:||'; }
on_drive() { printf '%s/Workspaces/.drive/%s\n' "$HOME" "$(drive_path "$1")"; }
case "$sub" in
  nfsmount)
    touch "$HOME/.mounted"
    trap 'rm -f "$HOME/.mounted"; exit 0' TERM
    while :; do sleep 0.1; done ;;
  listremotes) cat "$HOME/.remotes" 2>/dev/null ;;
  rcd)
    for arg do case "$arg" in unix://*) sock=${arg#unix://} ;; esac; done
    exec "$WSD_TEST_PY" "$HOME/.rcd.py" "$sock" ;;
  mkdir) mkdir -p "$(on_drive "$a1")" ;;
  copy)
    case "$a1" in
      wsdrive-*) src=$(on_drive "$a1"); dest=$a2 ;;
      *) src=$a1; dest=$(on_drive "$a2") ;;
    esac
    mkdir -p "$dest" && cp -R "$src/." "$dest/" ;;
  check|cryptcheck)
    echo x >> "$HOME/.checks"
    [ -f "$HOME/.check-fails" ] && exit 1
    [ -f "$HOME/.second-check-fails" ] && [ "$(wc -l < "$HOME/.checks")" -ge 2 ] && exit 1 ;;
  size)
    d=$(on_drive "$a1")
    printf '{"count":%s,"bytes":%s}\n' "$(find "$d" -type f | wc -l | tr -d ' ')" "$(cat $(find "$d" -type f) /dev/null | wc -c | tr -d ' ')" ;;
  purge) [ -f "$HOME/.purge-fails" ] && exit 1; rm -rf "$(on_drive "$a1")" ;;
  lsjson) [ -e "$(on_drive "$a1")" ] || exit 3 ;;
  lsf) cat "$HOME/.drive-dirs" 2>/dev/null ;;
esac
exit 0
"""

# The setup daemon: answers one config/create request on its unix socket, keeps the body and
# names the remote (or, with ~/.rc-hang, never answers).
RCD_STUB = r"""import json, os, socket, sys, time
home = os.environ["HOME"]
srv = socket.socket(socket.AF_UNIX)
srv.bind(sys.argv[1])
srv.listen(1)
conn, _ = srv.accept()
data = b""
while b"\r\n\r\n" not in data:
    data += conn.recv(65536)
head, body = data.split(b"\r\n\r\n", 1)
length = next(int(l.split(b":")[1]) for l in head.split(b"\r\n") if l.lower().startswith(b"content-length"))
while len(body) < length:
    body += conn.recv(65536)
if os.path.exists(os.path.join(home, ".rc-hang")):
    time.sleep(60)
n = len([f for f in os.listdir(home) if f.startswith(".rc-body-")])
open(os.path.join(home, f".rc-body-{n}"), "wb").write(body)
with open(os.path.join(home, ".remotes"), "a") as f:
    f.write(json.loads(body)["name"] + ":\n")
reply = b'{"Error":""}'
conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n" % len(reply) + reply)
conn.close()
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
    (stubs / "launchctl").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (stubs / "diskutil").write_text("#!/bin/sh\nrm -f \"$HOME/.mounted\"\n", encoding="utf-8")
    (stubs / "mount").write_text(
        "#!/bin/sh\n"
        '[ -f "$HOME/.mounted" ] && echo "localhost:/ on $HOME/Workspaces/.drive (nfs, nodev, nosuid, nobrowse)"\n'
        "exit 0\n", encoding="utf-8")
    for stub in stubs.iterdir():
        stub.chmod(0o755)
    (h / ".rcd.py").write_text(RCD_STUB, encoding="utf-8")
    (h / "Workspaces" / "Projects").mkdir(parents=True)
    (h / "Workspaces" / "Personal").mkdir(parents=True)
    return h


def env(home: Path, **extra: str) -> dict[str, str]:
    return {"HOME": str(home), "PATH": f"{home / '.config' / 'bin'}:/usr/bin:/bin",
            "SECRET_CLI": str(home / ".config" / "bin" / "secret"), "WSD_MOUNT_WAIT": "3",
            "WSD_LIST_WAIT": "1", "WSD_TEST_PY": sys.executable, **extra}


def run(home: Path, *args: str, **extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(DRIVE), *args], env=env(home, **extra), capture_output=True,
                          text=True, timeout=120)


def call(home: Path, code: str) -> subprocess.CompletedProcess:
    """Run code with the engine imported as `drive` under the isolated HOME."""
    script = f"import sys; sys.path.insert(0, {str(PLUGIN)!r}); import drive\n{code}"
    return subprocess.run([sys.executable, "-c", script], env=env(home), capture_output=True, text=True,
                          timeout=60)


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


def calls(home: Path) -> list[str]:
    f = home / ".rclone-calls"
    return f.read_text().splitlines() if f.exists() else []


def make(path: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(text)
    path.mkdir(parents=True, exist_ok=True)
    return path


# --- setup and the LaunchAgent ------------------------------------------------------------

def test_install_refuses_before_setup(home: Path):
    done = run(home, "install")
    assert done.returncode != 0
    assert "ws-drive setup" in done.stderr
    assert not (home / "Library" / "LaunchAgents" / "local.hermes.workspaces-drive.mount.plist").exists()


def test_install_renders_a_plist_running_the_engine_on_this_python_with_no_secret(home: Path):
    set_up(home)
    done = run(home, "install")
    assert done.returncode == 0, done.stderr
    plist = home / "Library" / "LaunchAgents" / "local.hermes.workspaces-drive.mount.plist"
    data = plistlib.loads(plist.read_bytes())
    assert data["Label"] == "local.hermes.workspaces-drive.mount" and data["KeepAlive"] is True
    engine = f"{home}/.config/hermes/plugins/workspace/workspace-drive/drive.py"
    assert data["ProgramArguments"] == [f"{home}/.config/hermes/launchd/bin/hermes-workspaces-drive-mount",
                                        sys.executable, "-I", engine, "run"]
    assert data["EnvironmentVariables"]["HERMES_LOCAL"] == f"{home}/.hermes/local"
    assert PASSWORD not in plist.read_text()


def test_setup_keeps_every_key_off_the_command_line(home: Path):
    # A unix socket path is limited to 104 bytes, so the state directory sits on a short path.
    with tempfile.TemporaryDirectory(prefix="wsd", dir="/tmp") as short:
        local_root = Path(short)
        done = run(home, "setup", HERMES_LOCAL=short)
        assert done.returncode == 0, done.stderr + done.stdout
        items = home / ".items"
        keys = [(items / n).read_text() for n in ("WORKSPACES_DRIVE_CONFIG_PASS", "WORKSPACES_DRIVE_CRYPT_PASSWORD",
                                                   "WORKSPACES_DRIVE_CRYPT_SALT")]
        assert all(len(k) >= 32 for k in keys) and len(set(keys)) == 3
        argv = "\n".join(calls(home)) + (home / ".secret-sets").read_text()
        assert not any(k in argv for k in keys)
        drive, crypt = (json.loads(b.read_text()) for b in sorted(home.glob(".rc-body-*")))
        assert drive["name"] == "wsdrive-drive" and drive["type"] == "drive"
        assert drive["parameters"] == {"scope": "drive"}
        assert crypt["parameters"]["remote"] == "wsdrive-drive:Workspaces"
        assert crypt["parameters"]["password"] == keys[1] and crypt["parameters"]["password2"] == keys[2]
        assert crypt["parameters"]["directory_name_encryption"] == "false"
        assert "--no-env" in (home / ".secret-sets").read_text()
        assert any(line.endswith("mkdir wsdrive-drive:Workspaces/Projects") for line in calls(home))
        assert any(line.endswith("mkdir wsdrive-crypt:Personal") for line in calls(home))
        assert not list((local_root / "workspaces-drive").glob("setup-rc.*"))
        assert oct((local_root / "workspaces-drive").stat().st_mode & 0o777) == "0o700"
        again = run(home, "setup", HERMES_LOCAL=short)
        assert again.returncode == 0, again.stderr
        assert len(list(home.glob(".rc-body-*"))) == 2


def test_setup_passes_your_own_oauth_client_through_the_socket_only(home: Path):
    (home / ".items").mkdir()
    (home / ".items" / "WORKSPACES_DRIVE_CLIENT_ID").write_text("client-id-value")
    (home / ".items" / "WORKSPACES_DRIVE_CLIENT_SECRET").write_text("client-secret-value")
    with tempfile.TemporaryDirectory(prefix="wsd", dir="/tmp") as short:
        done = run(home, "setup", HERMES_LOCAL=short)
    assert done.returncode == 0, done.stderr
    drive = json.loads(sorted(home.glob(".rc-body-*"))[0].read_text())
    assert drive["parameters"]["client_secret"] == "client-secret-value"
    assert "client-secret-value" not in "\n".join(calls(home))


def test_an_interrupted_setup_stops_its_config_daemon(home: Path):
    (home / ".rc-hang").write_text("")
    with tempfile.TemporaryDirectory(prefix="wsd", dir="/tmp") as short:
        sock = Path(short) / "workspaces-drive" / "setup-rc.sock"
        proc = subprocess.Popen([sys.executable, str(DRIVE), "setup"], env=env(home, HERMES_LOCAL=short),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        deadline = time.time() + 15
        while not sock.exists() and time.time() < deadline:
            time.sleep(0.1)
        assert sock.exists(), "the setup daemon never opened its socket"
        time.sleep(0.5)
        os.killpg(proc.pid, signal.SIGINT)
        proc.communicate(timeout=15)
        time.sleep(0.3)
        daemons = subprocess.run(["pgrep", "-f", str(sock)], capture_output=True, text=True).stdout
        assert daemons == "" and not sock.exists()


def test_restart_refuses_while_a_move_holds_the_lock(home: Path):
    local = set_up(home)
    plist = home / "Library" / "LaunchAgents" / "local.hermes.workspaces-drive.mount.plist"
    plist.parent.mkdir(parents=True)
    plist.write_text("<plist/>")
    with hold_lock(local / "links.lock"):
        done = run(home, "restart")
    assert done.returncode == 75 and "running" in done.stderr
    assert run(home, "restart").returncode == 0


# --- links --------------------------------------------------------------------------------

def test_status_reports_without_linking(home: Path):
    set_up(home)
    (home / "Workspaces" / "Projects" / "Alpha").mkdir()
    done = run(home, "status")
    assert "would link: Projects/Alpha/assets" in done.stdout
    assert not (home / "Workspaces" / "Projects" / "Alpha" / "assets").exists()
    assert not (home / "Workspaces" / ".drive" / "Projects").exists()


class hold_lock:
    """Another process holding the links lock until the block ends."""

    def __init__(self, path: Path):
        self.path = path

    def __enter__(self):
        code = ("import fcntl, os, sys, time; fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT); "
                "fcntl.flock(fd, fcntl.LOCK_EX); print('held', flush=True); time.sleep(60)")
        self.proc = subprocess.Popen([sys.executable, "-c", code, str(self.path)], stdout=subprocess.PIPE, text=True)
        assert self.proc.stdout.readline().strip() == "held"
        return self

    def __exit__(self, *exc):
        self.proc.kill()
        self.proc.wait()


def test_links_wait_for_the_lock_and_a_dead_holder_releases_it(home: Path):
    local = set_up(home)
    (home / "Workspaces" / "Projects" / "Alpha").mkdir()
    with hold_lock(local / "links.lock"):
        held = run(home, "links", WSD_LOCK_WAIT="1")
        assert held.returncode == 75 and "holds" in held.stderr
        assert not (home / "Workspaces" / "Projects" / "Alpha" / "assets").exists()
    taken = run(home, "links")
    assert "linked: Projects/Alpha/assets" in taken.stdout


def test_links_make_relative_links_and_leave_real_folders(home: Path):
    set_up(home)
    ws = home / "Workspaces"
    (ws / "Projects" / "Alpha").mkdir()
    make(ws / "Projects" / "Beta" / "assets", {"logo.png": "x"})
    (ws / "Personal" / "Notes").mkdir()
    (ws / "Projects" / ".hidden").mkdir()
    done = run(home, "links")
    assert done.returncode == 0, done.stderr
    alpha = ws / "Projects" / "Alpha" / "assets"
    assert os.readlink(alpha) == "../../.drive/Projects/Alpha/assets"
    assert alpha.resolve() == (ws / ".drive" / "Projects" / "Alpha" / "assets").resolve()
    assert os.readlink(ws / "Personal" / "Notes" / "assets") == "../../.drive/Personal/Notes/assets"
    beta = ws / "Projects" / "Beta" / "assets"
    assert beta.is_dir() and not beta.is_symlink()
    assert "local: Projects/Beta/assets stays on this Mac" in done.stdout
    assert not (ws / "Projects" / ".hidden" / "assets").exists()
    # Folders are made on Drive through rclone, never through the mount (which macOS refuses to a
    # shell that launchd started).
    assert any(c.endswith("mkdir wsdrive-drive:Workspaces/Projects/Alpha/assets") for c in calls(home))
    assert any(c.endswith("mkdir wsdrive-crypt:Personal/Notes/assets") for c in calls(home))
    again = run(home, "links")
    assert "linked:" not in again.stdout


def test_links_refuse_while_unmounted(home: Path):
    set_up(home, mounted=False)
    (home / "Workspaces" / "Projects" / "Alpha").mkdir()
    done = run(home, "links")
    assert done.returncode == 1 and "not up" in done.stderr
    assert not (home / "Workspaces" / "Projects" / "Alpha" / "assets").exists()


def test_links_link_drive_folders_missing_here_at_their_highest_level(home: Path):
    set_up(home)
    ws = home / "Workspaces"
    make(ws / "Projects" / "Alpha" / "data", {"local.csv": "x"})
    (ws / "Projects" / "Alpha" / "assets").symlink_to("../../.drive/Projects/Alpha/assets")
    (home / ".drive-dirs").write_text("\n".join([
        "Projects/", "Projects/Alpha/", "Projects/Alpha/assets/", "Projects/Alpha/assets/sub/",
        "Projects/Alpha/data/", "Projects/Alpha/data/raw/", "Projects/Alpha/data/raw/2024/",
        "Projects/Alpha/docs/", "Projects/Alpha/docs/old/",
        "Projects/Alpha/github/", "Projects/Alpha/github/app/",
        "Projects/Alpha/.agent/", "Projects/Alpha/.agent/x/", "Projects/Gone/", "Projects/Gone/data/",
    ]) + "\n")
    done = run(home, "links")
    assert done.returncode == 0, done.stderr
    raw = ws / "Projects" / "Alpha" / "data" / "raw"
    assert os.readlink(raw) == "../../../.drive/Projects/Alpha/data/raw"
    assert os.readlink(ws / "Projects" / "Alpha" / "docs") == "../../.drive/Projects/Alpha/docs"
    assert not (ws / "Projects" / "Alpha" / "docs" / "old").is_symlink()
    assert not (ws / "Projects" / "Alpha" / "data").is_symlink()
    assert not (ws / "Projects" / "Alpha" / "github").exists()
    assert not (ws / "Projects" / "Alpha" / ".agent").exists()
    assert not (ws / "Projects" / "Gone").exists()
    assert not os.path.lexists(ws / "Projects" / "Alpha" / "assets" / "sub")


def test_the_sweep_deletes_appledouble_files_on_drive_not_into_its_trash(home: Path):
    set_up(home)
    done = call(home, "drive.sweep()")
    assert done.returncode == 0, done.stderr
    call_line = calls(home)[-1]
    assert " delete :combine,upstreams=" in call_line
    assert "--include ._* --include .DS_Store --drive-use-trash=false" in call_line


def test_remote_mapping_keeps_plain_and_encrypted_trees_apart(home: Path):
    done = call(home, "print(drive.remote('Projects', 'Alpha/assets')); print(drive.remote('Personal', 'Notes/assets'));"
                      "print(drive.combine())")
    assert done.stdout.splitlines() == [
        "wsdrive-drive:Workspaces/Projects/Alpha/assets",
        "wsdrive-crypt:Personal/Notes/assets",
        ":combine,upstreams='Projects=wsdrive-drive:Workspaces/Projects Personal=wsdrive-crypt:Personal':",
    ]


def test_status_json_names_what_is_on_drive_and_what_stays_here(home: Path):
    set_up(home)
    ws = home / "Workspaces"
    (ws / ".drive" / "Projects" / "Alpha" / "assets").mkdir(parents=True)
    (ws / "Projects" / "Alpha").mkdir()
    (ws / "Projects" / "Alpha" / "assets").symlink_to("../../.drive/Projects/Alpha/assets")
    make(ws / "Projects" / "Alpha" / "data", {"a.csv": "a"})
    (ws / "Projects" / "Alpha" / "data" / "raw").symlink_to("../../../.drive/Projects/Alpha/data/raw")
    make(ws / "Projects" / "Beta" / "assets", {"logo.png": "x"})
    done = run(home, "status", "--json")
    assert done.returncode == 0, done.stderr
    data = json.loads(done.stdout)
    assert data["on_drive"] == ["Projects/Alpha/assets", "Projects/Alpha/data/raw"]
    assert data["local_assets"] == ["Projects/Beta/assets"] and data["mounted"] is True


# --- move ---------------------------------------------------------------------------------

def test_move_swaps_a_checked_copy_for_its_link(home: Path):
    set_up(home)
    assets = make(home / "Workspaces" / "Projects" / "Alpha" / "assets", {"a.png": "a", "sub/b.mp4": "b"})
    done = run(home, "move", "Projects/Alpha/assets")
    assert done.returncode == 0, done.stderr
    assert os.readlink(assets) == "../../.drive/Projects/Alpha/assets"
    assert (assets / "sub" / "b.mp4").read_text() == "b"
    assert not (assets.parent / "assets.migrating").exists()
    assert "moved: Projects/Alpha/assets -> Drive (2 files)" in done.stdout
    assert not list((home / ".hermes" / "local" / "workspaces-drive" / "journal").glob("*.json"))


def test_move_takes_any_folder_inside_a_group_and_encrypts_personal_ones(home: Path):
    set_up(home)
    raw = make(home / "Workspaces" / "Personal" / "Notes" / "data" / "raw", {"r.csv": "r"})
    done = run(home, "move", str(raw))
    assert done.returncode == 0, done.stderr
    assert os.readlink(raw) == "../../../.drive/Personal/Notes/data/raw"
    assert (raw / "r.csv").read_text() == "r"
    copy = next(c for c in calls(home) if " copy " in c)
    assert copy.split(" copy ")[1].startswith(f"{raw} wsdrive-crypt:Personal/Notes/data/raw")
    assert any(" cryptcheck " in c for c in calls(home))


@pytest.mark.parametrize("path, message", [
    ("Projects/Alpha", "name a folder inside a Group"),
    ("Projects/Alpha/github", "repositories"),
    ("Projects/Alpha/.agent", "starts with '.'"),
    ("Projects/Alpha/docs/.cache", "starts with '.'"),
    ("Other/Alpha/docs", "not a tree"),
    ("Projects/Alpha/../Beta/docs", "name a folder inside a Group"),
    ("Projects/Alpha/assets/sub", "already on Drive"),
    ("Projects/Alpha/withlink", "holds links"),
    ("Projects/Alpha/withrepo", "Git repository"),
    ("Projects/Alpha/missing", "not a folder on this Mac"),
])
def test_move_refuses_what_stays_on_this_mac(home: Path, path: str, message: str):
    set_up(home)
    alpha = home / "Workspaces" / "Projects" / "Alpha"
    make(alpha / "github" / "app", {"README": "r"})
    make(alpha / ".agent" / "job", {"x": "x"})
    make(alpha / "docs" / ".cache", {"x": "x"})
    make(alpha / "withlink", {"a": "a"})
    (alpha / "withlink" / "l").symlink_to("a")
    make(alpha / "withrepo" / ".git", {"HEAD": "ref"})
    (home / "Workspaces" / ".drive" / "Projects" / "Alpha" / "assets" / "sub").mkdir(parents=True)
    (alpha / "assets").symlink_to("../../.drive/Projects/Alpha/assets")
    done = run(home, "move", path)
    assert done.returncode == 1 and message in done.stderr, done.stderr
    assert not any(" copy " in c for c in calls(home))


def test_move_refuses_while_a_file_is_open_and_rolls_back(home: Path):
    set_up(home)
    assets = make(home / "Workspaces" / "Projects" / "Alpha" / "assets", {"a.png": "a"})
    with open(assets / "a.png", "rb"):
        done = run(home, "move", "Projects/Alpha/assets")
    assert done.returncode != 0 and "open in another process" in done.stderr
    assert assets.is_dir() and not assets.is_symlink() and (assets / "a.png").read_text() == "a"
    assert not (assets.parent / "assets.migrating").exists()
    assert not list((home / ".hermes" / "local" / "workspaces-drive" / "journal").glob("*.json"))


def test_move_keeps_the_local_copy_when_the_check_fails(home: Path):
    set_up(home)
    (home / ".check-fails").write_text("")
    assets = make(home / "Workspaces" / "Projects" / "Alpha" / "assets", {"a.png": "a"})
    done = run(home, "move", "Projects/Alpha/assets")
    assert done.returncode != 0 and "does not match" in done.stderr
    assert assets.is_dir() and not assets.is_symlink() and (assets / "a.png").read_text() == "a"


def test_move_creates_the_folder_on_drive_even_when_it_is_empty(home: Path):
    set_up(home)
    assets = home / "Workspaces" / "Projects" / "Alpha" / "assets"
    (assets / "empty-sub").mkdir(parents=True)
    done = run(home, "move", "Projects/Alpha/assets")
    assert done.returncode == 0, done.stderr
    assert assets.is_symlink() and (home / "Workspaces" / ".drive" / "Projects" / "Alpha" / "assets").is_dir()
    lines = calls(home)
    mkdir = next(i for i, c in enumerate(lines) if c.endswith("mkdir wsdrive-drive:Workspaces/Projects/Alpha/assets"))
    copy = next(i for i, c in enumerate(lines) if " copy " in c)
    assert mkdir < copy and "--create-empty-src-dirs" in lines[copy]


def test_move_rolls_back_when_the_original_changed_after_the_copy(home: Path):
    set_up(home)
    (home / ".second-check-fails").write_text("")
    assets = make(home / "Workspaces" / "Projects" / "Alpha" / "assets", {"a.png": "a"})
    done = run(home, "move", "Projects/Alpha/assets")
    assert done.returncode != 0 and "changed after it was copied" in done.stderr
    assert assets.is_dir() and not assets.is_symlink() and (assets / "a.png").read_text() == "a"
    assert not (assets.parent / "assets.migrating").exists()


def test_move_refuses_an_existing_staging_folder(home: Path):
    set_up(home)
    assets = make(home / "Workspaces" / "Projects" / "Alpha" / "assets", {"a.png": "a"})
    staging = make(assets.parent / "assets.migrating", {"keep.txt": "k"})
    done = run(home, "move", "Projects/Alpha/assets")
    assert done.returncode != 0 and "already exists" in done.stderr
    assert (staging / "keep.txt").read_text() == "k" and (assets / "a.png").exists()
    assert not any(" copy " in c for c in calls(home))


def test_an_interrupted_move_is_undone_at_the_next_pass(home: Path):
    local = set_up(home)
    alpha = home / "Workspaces" / "Projects" / "Alpha"
    make(alpha / "data.migrating", {"a.csv": "a"})
    (alpha / "data").symlink_to("../../.drive/Projects/Alpha/data")
    done = call(home, "drive.journal('Projects/Alpha/data', 'move', 'swap')")
    assert done.returncode == 0, done.stderr
    status = run(home, "status")
    assert "interrupted move: Projects/Alpha/data" in status.stdout
    done = run(home, "links")
    assert done.returncode == 0, done.stderr
    assert (alpha / "data").is_dir() and not (alpha / "data").is_symlink()
    assert (alpha / "data" / "a.csv").read_text() == "a"
    assert not list((local / "journal").glob("*.json"))


# --- restore ------------------------------------------------------------------------------

def test_restore_brings_a_moved_folder_back_and_trashes_the_drive_copy(home: Path):
    set_up(home)
    data = make(home / "Workspaces" / "Projects" / "Alpha" / "data", {"a.csv": "a", "sub/b.csv": "b"})
    assert run(home, "move", "Projects/Alpha/data").returncode == 0
    done = run(home, "restore", "Projects/Alpha/data")
    assert done.returncode == 0, done.stderr
    assert data.is_dir() and not data.is_symlink() and (data / "sub" / "b.csv").read_text() == "b"
    assert not (home / "Workspaces" / ".drive" / "Projects" / "Alpha" / "data").exists()
    purge = next(c for c in calls(home) if " purge " in c)
    assert purge.endswith("purge wsdrive-drive:Workspaces/Projects/Alpha/data --drive-use-trash=true")
    assert "restored: Projects/Alpha/data" in done.stdout
    assert not (data.parent / "data.restoring").exists()


def test_restore_keeps_the_folder_on_drive_when_the_check_fails(home: Path):
    set_up(home)
    data = make(home / "Workspaces" / "Projects" / "Alpha" / "data", {"a.csv": "a"})
    assert run(home, "move", "Projects/Alpha/data").returncode == 0
    (home / ".check-fails").write_text("")
    done = run(home, "restore", "Projects/Alpha/data")
    assert done.returncode == 1 and "stays on Drive" in done.stderr
    assert os.readlink(data) == "../../.drive/Projects/Alpha/data"
    assert not (data.parent / "data.restoring").exists()
    assert not any(" purge " in c for c in calls(home))


def test_restore_waits_for_uploads_still_pending_through_the_mount(home: Path):
    local = set_up(home)
    data = make(home / "Workspaces" / "Projects" / "Alpha" / "data", {"a.csv": "a"})
    assert run(home, "move", "Projects/Alpha/data").returncode == 0
    meta = local / "cache" / "vfsMeta" / ":combine{x}" / "Projects" / "Alpha" / "data"
    meta.mkdir(parents=True)
    (meta / "new.csv").write_text(json.dumps({"Size": 3, "Dirty": True}))
    done = run(home, "restore", "Projects/Alpha/data", WSD_UPLOAD_WAIT="1")
    assert done.returncode == 1 and "still uploading" in done.stderr
    assert os.readlink(data) == "../../.drive/Projects/Alpha/data"
    assert not any(" copy wsdrive-" in c for c in calls(home))
    (meta / "new.csv").write_text(json.dumps({"Size": 3, "Dirty": False}))
    assert run(home, "restore", "Projects/Alpha/data").returncode == 0


def interrupted_restore(home: Path, phase: str) -> tuple[Path, Path]:
    """A folder moved to Drive, then a restore journal entry at phase, as a killed restore leaves it."""
    data = make(home / "Workspaces" / "Projects" / "Alpha" / "data", {"a.csv": "a"})
    assert run(home, "move", "Projects/Alpha/data").returncode == 0
    assert call(home, f"drive.journal('Projects/Alpha/data', 'restore', {phase!r})").returncode == 0
    return data, home / "Workspaces" / ".drive" / "Projects" / "Alpha" / "data"


def test_a_restore_stopped_before_the_swap_leaves_the_folder_on_drive(home: Path):
    local = set_up(home)
    data, on_drive = interrupted_restore(home, "swap")
    make(data.parent / "data.restoring", {"a.csv": "a"})
    done = run(home, "links")
    assert done.returncode == 0, done.stderr
    assert os.readlink(data) == "../../.drive/Projects/Alpha/data" and on_drive.is_dir()
    assert not (data.parent / "data.restoring").exists()
    assert not list((local / "journal").glob("*.json"))


def test_a_restore_stopped_between_unlink_and_rename_is_finished(home: Path):
    local = set_up(home)
    data, on_drive = interrupted_restore(home, "swap")
    make(data.parent / "data.restoring", {"a.csv": "a"})
    data.unlink()
    assert run(home, "links").returncode == 0
    assert data.is_dir() and not data.is_symlink() and (data / "a.csv").read_text() == "a"
    assert not on_drive.exists() and not list((local / "journal").glob("*.json"))


def test_a_restore_stopped_while_purging_finishes_the_purge(home: Path):
    local = set_up(home)
    data, on_drive = interrupted_restore(home, "purge")
    data.unlink()
    make(data, {"a.csv": "a"})
    (home / ".purge-fails").write_text("")
    first = run(home, "links")
    assert "could not be sent to the trash" in first.stdout + first.stderr
    assert on_drive.is_dir() and list((local / "journal").glob("*.json"))
    (home / ".purge-fails").unlink()
    assert run(home, "links").returncode == 0
    assert not on_drive.exists() and not list((local / "journal").glob("*.json"))
    assert (data / "a.csv").read_text() == "a"


def test_a_restore_stopped_after_its_purge_only_clears_the_journal(home: Path):
    local = set_up(home)
    data, on_drive = interrupted_restore(home, "purge")
    data.unlink()
    make(data, {"a.csv": "a"})
    shutil.rmtree(on_drive)
    assert run(home, "links").returncode == 0
    assert not list((local / "journal").glob("*.json")) and (data / "a.csv").read_text() == "a"


def test_restore_refuses_a_folder_that_is_not_on_drive(home: Path):
    set_up(home)
    make(home / "Workspaces" / "Projects" / "Alpha" / "data", {"a.csv": "a"})
    done = run(home, "restore", "Projects/Alpha/data")
    assert done.returncode == 1 and "not a folder on Drive" in done.stderr


# --- the run loop -------------------------------------------------------------------------

def test_the_run_loop_refuses_a_mount_point_holding_files(home: Path):
    set_up(home, mounted=False)
    (home / "Workspaces" / ".drive" / "stray.txt").write_text("x")
    done = run(home, "run")
    assert done.returncode == 78 and "not empty" in done.stderr


def test_the_run_loop_refuses_before_setup(home: Path):
    done = run(home, "run")
    assert done.returncode == 78 and "ws-drive setup" in done.stderr


def test_the_run_loop_mounts_links_and_stops_on_term(home: Path):
    set_up(home, mounted=False)
    (home / "Workspaces" / "Projects" / "Alpha").mkdir()
    proc = subprocess.Popen([sys.executable, str(DRIVE), "run"], env=env(home), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    link = home / "Workspaces" / "Projects" / "Alpha" / "assets"
    deadline = time.time() + 15
    while not link.is_symlink() and time.time() < deadline:
        time.sleep(0.1)
    try:
        assert link.is_symlink(), "the maintenance pass did not link the Group"
    finally:
        proc.send_signal(signal.SIGTERM)
        out, err = proc.communicate(timeout=40)
    assert proc.returncode == 0, err
    lines = calls(home)
    mount_call = next(line for line in lines if " nfsmount " in line)
    assert "--password-command" in mount_call and PASSWORD not in "\n".join(lines)
    assert "Projects=wsdrive-drive:Workspaces/Projects Personal=wsdrive-crypt:Personal" in mount_call
    assert "locallocks" in mount_call and "deadtimeout=30" in mount_call
    assert not (home / ".mounted").exists()


def test_the_launchers_are_executable_in_git():
    root = HERMES.parent
    paths = ["bin/ws-drive", "hermes/launchd/bin/hermes-workspaces-drive-mount"]
    out = subprocess.run(["git", "ls-files", "-s", "--", *paths], cwd=root, capture_output=True,
                         text=True, check=True).stdout
    modes = {line.split()[3]: line.split()[0] for line in out.splitlines()}
    assert set(modes) == set(paths)
    assert all(mode == "100755" for mode in modes.values()), modes
