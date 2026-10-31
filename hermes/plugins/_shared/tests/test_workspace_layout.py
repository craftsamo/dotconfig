"""workspace_layout: without a file the public defaults apply, a file overrides root and areas,
WORKSPACES_ROOT overrides the root, an invalid file is refused rather than guessed around, and the
defaults match what the workspace tools use today."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parent
MODULE = HERE.parent / "workspace_layout.py"
PLUGINS = HERE.parents[1]
spec = importlib.util.spec_from_file_location("workspace_layout_under_test", MODULE)
wl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wl)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    for name in ("XDG_CONFIG_HOME", "WORKSPACES_LAYOUT", "WORKSPACES_ROOT"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def write(home, data):
    path = home / ".config" / "workspaces" / "layout.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return path


def test_without_a_file_the_public_defaults_apply(isolated):
    layout = wl.load()
    assert layout.root == isolated / "Workspaces" and layout.source is None
    assert layout.names == ("Projects", "Personal") and layout.projects.name == "Projects"
    assert [a.sensitive for a in layout.areas] == [False, True]


def test_a_file_sets_root_and_areas(isolated):
    path = write(isolated, {"root": "~/Work", "areas": [
        {"name": "Clients", "role": "projects"}, {"name": "Home", "role": "personal", "sensitive": True},
        {"name": "Lab", "role": "personal"}]})
    layout = wl.load()
    assert layout.root == isolated / "Work" and layout.source == path
    assert layout.names == ("Clients", "Home", "Lab") and layout.projects.name == "Clients"
    assert layout.area("Lab").sensitive is False


def test_a_file_may_set_only_the_root(isolated):
    write(isolated, {"root": "/srv/ws"})
    layout = wl.load()
    assert layout.root == Path("/srv/ws") and layout.names == ("Projects", "Personal")


def test_xdg_config_home_and_an_explicit_file_are_honoured(isolated, monkeypatch):
    xdg = isolated / "xdg"
    (xdg / "workspaces").mkdir(parents=True)
    (xdg / "workspaces" / "layout.json").write_text(json.dumps({"root": "/x"}))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    assert wl.load().root == Path("/x")
    named = isolated / "other.json"
    named.write_text(json.dumps({"root": "/y"}))
    monkeypatch.setenv("WORKSPACES_LAYOUT", str(named))
    assert wl.load().root == Path("/y") and wl.config_path() == named


def test_workspaces_root_overrides_the_file(isolated, monkeypatch):
    write(isolated, {"root": "/from-file"})
    monkeypatch.setenv("WORKSPACES_ROOT", str(isolated / "elsewhere"))
    layout = wl.load()
    assert layout.root == isolated / "elsewhere" and layout.names == ("Projects", "Personal")


def test_a_relative_workspaces_root_is_taken_from_the_working_directory(isolated, monkeypatch):
    """As the scanners always took it; the result is absolute, so it can bound sends."""
    monkeypatch.chdir(isolated)
    monkeypatch.setenv("WORKSPACES_ROOT", "fixture/ws")
    assert wl.load().root == isolated / "fixture" / "ws"


def test_a_layout_link_to_a_missing_file_is_refused_not_ignored(isolated):
    """A broken link must not fall back to the defaults, which could widen a narrowed root."""
    path = isolated / ".config" / "workspaces" / "layout.json"
    path.parent.mkdir(parents=True)
    path.symlink_to(isolated / "gone.json")
    with pytest.raises(wl.LayoutError, match="cannot read"):
        wl.load()


@pytest.mark.parametrize("data, message", [
    ("{not json", "cannot read"),
    ([], "JSON object"),
    ({"root": "relative/path"}, "absolute"),
    ({"root": ""}, "non-empty"),
    ({"areas": []}, "non-empty list"),
    ({"areas": [{"name": "A", "role": "personal"}]}, "exactly one area"),
    ({"areas": [{"name": "A", "role": "projects"}, {"name": "B", "role": "projects"}]}, "exactly one area"),
    ({"areas": [{"name": "A", "role": "projects"}, {"name": "a", "role": "personal"}]}, "listed twice"),
    ({"areas": [{"name": ".hidden", "role": "projects"}]}, "plain folder name"),
    ({"areas": [{"name": "a/b", "role": "projects"}]}, "plain folder name"),
    ({"areas": [{"name": "A", "role": "work"}]}, "role must be"),
    ({"areas": [{"name": "A", "role": "projects", "sensitive": "yes"}]}, "true or false"),
    ({"areas": [{"name": "A", "role": "projects", "path": "x"}]}, "unknown key"),
    ({"rooot": "/x"}, "unknown key"),
])
def test_an_invalid_file_is_refused(isolated, data, message):
    write(isolated, data)
    with pytest.raises(wl.LayoutError, match=message):
        wl.load()


def test_area_of_and_sensitive_follow_the_path(isolated):
    layout = wl.load()
    root = isolated / "Workspaces"
    assert layout.area_of(root / "Personal" / "Budget" / "data" / "x.csv").name == "Personal"
    assert layout.sensitive(root / "Personal" / "Budget") is True
    assert layout.sensitive(root / "Projects" / "Acme" / "docs") is False
    assert layout.area_of(root / ".inbox" / "a.pdf") is None
    assert layout.area_of(root) is None and layout.area_of(isolated / "elsewhere") is None
    assert layout.area_of(root / "Projects" / ".." / "Personal" / "x").name == "Personal"
    assert layout.area_of("~/Workspaces/Personal/x").name == "Personal"


def run_cli(isolated, *args):
    env = {"HOME": str(isolated), "PATH": "/usr/bin:/bin"}
    return subprocess.run([sys.executable, str(MODULE), *args], env=env, capture_output=True, text=True)


def test_the_cli_prints_the_layout(isolated):
    data = json.loads(run_cli(isolated).stdout)
    assert data == {"root": str(isolated / "Workspaces"), "source": None, "areas": [
        {"name": "Projects", "role": "projects", "sensitive": False},
        {"name": "Personal", "role": "personal", "sensitive": True}]}
    assert run_cli(isolated, "--root").stdout.strip() == str(isolated / "Workspaces")
    assert run_cli(isolated, "--areas").stdout.split() == ["Projects", "Personal"]
    assert run_cli(isolated, "--projects").stdout.strip() == "Projects"
    assert run_cli(isolated, "--path").stdout.strip() == str(isolated / ".config" / "workspaces" / "layout.json")
    write(isolated, {"root": "nope"})
    bad = run_cli(isolated, "--root")
    assert bad.returncode == 1 and "absolute" in bad.stderr


@pytest.mark.skipif(not Path("/usr/bin/python3").exists(), reason="no system python")
def test_the_system_interpreter_runs_it(isolated):
    """The ws-* launchers run python3 from PATH, which may be the system's 3.9."""
    done = subprocess.run(["/usr/bin/python3", str(MODULE), "--areas"], env={"HOME": str(isolated)},
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.split() == ["Projects", "Personal"]


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def test_the_defaults_are_what_the_workspace_tools_use_today():
    """Characterization: until each tool reads the layout, its own names must equal the defaults."""
    defaults = tuple(a["name"] for a in wl.DEFAULT["areas"])
    drafts = _load("layout_drafts", PLUGINS / "workspace" / "workspace-drafts" / "drafts.py")
    repos = _load("layout_repos", PLUGINS / "workspace" / "workspace-repos" / "repos.py")
    assert tuple(drafts.AREAS) == defaults and tuple(repos.AREAS) == defaults
    registry = (PLUGINS / "workspace" / "workspace-registry" / "registry.py").read_text(encoding="utf-8")
    projects = next(a["name"] for a in wl.DEFAULT["areas"] if a["role"] == "projects")
    assert f'"{projects}"' in registry
    assert wl.DEFAULT["root"] == "~/Workspaces"
