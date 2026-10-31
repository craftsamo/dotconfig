"""ws-init: a fresh machine gets the skeleton its layout describes (root, areas, .inbox, .agent and an
empty registry), with the root and sensitive areas private; a second run, and a machine that already
has it all, change nothing; --check changes nothing; an existing file is never replaced."""

import json
import os
from pathlib import Path
import stat
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parent
INIT = HERE.parent / "workspace_init.py"
LAUNCHER = HERE.parents[3] / "bin" / "ws-init"


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h


def run(home, *args, **env):
    full = {"HOME": str(home), "PATH": "/usr/bin:/bin", **env}
    return subprocess.run([sys.executable, str(INIT), *args], env=full, capture_output=True, text=True)


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_a_fresh_machine_gets_the_whole_skeleton(home):
    done = run(home, "--json")
    assert done.returncode == 0, done.stderr
    ws = home / "Workspaces"
    for name in ("Projects", "Personal", ".inbox", ".agent", ".registry"):
        assert (ws / name).is_dir(), name
    assert sorted(p.name for p in (ws / ".registry").glob("*.csv"))       # wsreg init's empty tables
    assert mode(ws) == 0o700 and mode(ws / "Personal") == 0o700 and mode(ws / ".registry") == 0o700
    assert not (ws / "AGENTS.md").exists()
    result = json.loads(done.stdout)
    assert result["root"] == str(ws) and result["refused"] == []
    assert sorted(result["made"]) == sorted(str(p) for p in (ws, ws / "Projects", ws / "Personal", ws / ".inbox",
                                                             ws / ".agent", ws / ".registry"))


def test_a_second_run_changes_nothing(home):
    assert run(home).returncode == 0
    registry = home / "Workspaces" / ".registry"
    (registry / "people.csv").write_text("kept\n")
    again = run(home)
    assert again.returncode == 0 and "has every folder of its layout" in again.stdout
    assert (registry / "people.csv").read_text() == "kept\n"


def test_existing_folders_keep_their_contents_and_modes(home):
    ws = home / "Workspaces"
    (ws / "Projects" / "Acme").mkdir(parents=True)
    os.chmod(ws, 0o755)
    done = run(home, "--json")
    assert done.returncode == 0, done.stderr
    assert (ws / "Projects" / "Acme").is_dir() and mode(ws) == 0o755
    made = json.loads(done.stdout)["made"]
    assert str(ws) not in made and str(ws / "Projects") not in made and str(ws / "Personal") in made


def test_an_existing_registry_folder_without_tables_gets_them_but_keeps_its_mode(home):
    ws = home / "Workspaces"
    (ws / ".registry").mkdir(parents=True)
    (ws / ".registry" / "notes.txt").write_text("mine")
    os.chmod(ws / ".registry", 0o755)
    assert run(home).returncode == 0
    assert any((ws / ".registry").glob("*.csv")) and mode(ws / ".registry") == 0o755
    assert (ws / ".registry" / "notes.txt").read_text() == "mine"


def test_a_staging_registry_elsewhere_keeps_its_mode(home, tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()
    os.chmod(staging, 0o755)
    assert run(home, WSREG_DIR=str(staging)).returncode == 0
    assert any(staging.glob("*.csv")) and mode(staging) == 0o755
    assert not (home / "Workspaces" / ".registry").exists()


def test_a_file_where_the_registry_goes_is_refused(home):
    ws = home / "Workspaces"
    ws.mkdir()
    (ws / ".registry").write_text("not a folder")
    check = run(home, "--check")
    real = run(home)
    assert check.returncode == real.returncode == 1
    assert "is not a folder" in real.stderr and (ws / ".registry").read_text() == "not a folder"


def test_a_symlinked_area_is_kept_as_it_is(home, tmp_path):
    ws = home / "Workspaces"
    ws.mkdir()
    target = tmp_path / "elsewhere"
    target.mkdir()
    os.chmod(target, 0o755)
    (ws / "Personal").symlink_to(target)
    assert run(home).returncode == 0
    assert (ws / "Personal").is_symlink() and mode(target) == 0o755


def test_check_reports_and_changes_nothing(home):
    done = run(home, "--check")
    assert done.returncode == 0, done.stderr
    assert "would create: " + str(home / "Workspaces" / ".registry") in done.stdout
    assert not (home / "Workspaces").exists()


def test_the_layout_decides_the_root_and_areas(home):
    cfg = home / ".config" / "workspaces"
    cfg.mkdir(parents=True)
    (cfg / "layout.json").write_text(json.dumps({"root": "~/W", "areas": [
        {"name": "Clients", "role": "projects"}, {"name": "Home", "role": "personal", "sensitive": True},
        {"name": "Lab", "role": "personal"}]}))
    assert run(home).returncode == 0
    w = home / "W"
    assert {p.name for p in w.iterdir()} == {"Clients", "Home", "Lab", ".inbox", ".agent", ".registry"}
    assert mode(w / "Home") == 0o700 and not (home / "Workspaces").exists()


def test_a_file_in_the_way_is_refused_and_no_registry_is_made(home):
    ws = home / "Workspaces"
    ws.mkdir()
    (ws / "Personal").write_text("not a folder")
    done = run(home)
    assert done.returncode == 1 and "is not a folder" in done.stderr
    assert (ws / "Personal").read_text() == "not a folder" and not (ws / ".registry").exists()


def test_an_invalid_layout_creates_nothing(home):
    cfg = home / ".config" / "workspaces"
    cfg.mkdir(parents=True)
    (cfg / "layout.json").write_text(json.dumps({"root": "relative"}))
    done = run(home)
    assert done.returncode == 1 and "absolute" in done.stderr
    assert list(home.iterdir()) == [home / ".config"]


def test_the_example_assistant_receives_files_into_the_inbox():
    """What the Assistant downloads lands in the default root's .inbox/<source>/, inside the folder
    files may be sent from, so a received file can be passed on without copying it first."""
    yaml = pytest.importorskip("hermes_yaml")     # the runtime's loader, as test_example_configs uses
    example = HERE.parents[2] / "profiles" / "assistant" / "config.example.yaml"
    config = yaml.safe_load(example.read_text(encoding="utf-8"))
    sources = {"google_access": "google", "signal_access": "signal", "whatsapp_access": "whatsapp",
               "discord_access": "discord", "telegram_access": "telegram", "x_access": "x",
               "youtube_access": "youtube"}
    for key, folder in sources.items():
        assert config[key]["download_dir"] == f"~/Workspaces/.inbox/{folder}", key
    assert config["screen_listen"]["record_dir"] == "~/Workspaces/.inbox/recordings"


@pytest.mark.skipif(not Path("/usr/bin/python3").exists(), reason="no system python")
def test_the_launcher_runs_it_on_the_system_interpreter(home):
    """The whole run, registry included, on the system's python3 (3.9 on macOS)."""
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "WS_INIT_CLI": str(INIT)}
    done = subprocess.run(["bash", str(LAUNCHER)], env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert any((home / "Workspaces" / ".registry").glob("*.csv"))
