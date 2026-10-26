"""project_place: a call runs in a project only where it says so, and never in Hermes' own config."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("project_place_under_test",
                                              Path(__file__).resolve().parent.parent / "project_place.py")
place = importlib.util.module_from_spec(spec)
spec.loader.exec_module(place)


def repo(path: Path, origin: str = "git@github.com:me/shop.git") -> Path:
    (path / ".git").mkdir(parents=True)
    (path / ".git" / "config").write_text(f'[core]\n\tbare = false\n[remote "origin"]\n\turl = {origin}\n')
    return path


def worktree(path: Path, main: Path) -> Path:
    gitdir = main / ".git" / "worktrees" / path.name
    gitdir.mkdir(parents=True)
    (gitdir / "commondir").write_text("../..\n")
    path.mkdir(parents=True)
    (path / ".git").write_text(f"gitdir: {gitdir}\n")
    return path


@pytest.fixture
def roots(tmp_path, monkeypatch):
    ghq, trees = tmp_path / "ghq", tmp_path / "Worktrees"
    ghq.mkdir()
    trees.mkdir()
    monkeypatch.setattr(place, "_roots", lambda: [ghq.resolve(), trees.resolve()])
    monkeypatch.setattr(place, "_own_common", lambda: None)
    return ghq, trees


@pytest.mark.parametrize("args", [
    {"command": "cd {repo} && nps setup.google"},
    {"command": "cd '{repo}/apps/web'; pnpm exec wrangler deploy"},
    {"command": "nps setup.google", "workdir": "{repo}"},
    {"command": "zsh -lc 'cd {repo} && pnpm exec nps setup.google'"},
])
def test_a_written_out_place_in_a_project_counts(roots, args):
    project = repo(roots[0] / "github.com" / "me" / "shop")
    (project / "apps" / "web").mkdir(parents=True)
    args = {k: v.format(repo=project) for k, v in args.items()}
    assert place.project_dir(args) is not None


def test_a_task_worktree_counts(roots):
    main = repo(roots[0] / "github.com" / "me" / "shop")
    tree = worktree(roots[1] / "shop" / "feat-x", main)
    assert place.project_dir({"command": "nps setup.google", "workdir": str(tree)}) == tree.resolve()


@pytest.mark.parametrize("args", [
    {"command": "nps setup.google"},                                           # the place is not written out
    {"command": "cd $REPO && nps setup.google"},                               # nor fixed
    {"command": "cd {repo} && cd /tmp && pnpm exec wrangler deploy"},          # it moves again
    {"command": "cd {repo} && pushd x && nps setup"},
    {"command": "cd relative/dir && nps setup"},
    {"command": "cd {repo}/.. && nps setup"},                                  # `..` is read before symlinks
    {"command": "nps setup", "cwd": "{repo}"},                                 # not where the terminal runs
    {"command": "zsh -lc 'cd {repo} && true'; zsh -lc 'pnpm exec wrangler deploy'"},
    {"command": "nps setup", "workdir": "{outside}"},                          # outside the roots
    {"command": "nps setup", "workdir": "{plain}"},                            # not a repository
])
def test_no_exception_without_a_known_project_place(roots, tmp_path, args):
    project = repo(roots[0] / "github.com" / "me" / "shop")
    outside = repo(tmp_path / "elsewhere" / "shop")
    plain = roots[0] / "notes"
    plain.mkdir()
    args = {k: v.format(repo=project, outside=outside, plain=plain) for k, v in args.items()}
    assert place.project_dir(args) is None


@pytest.mark.parametrize("origin", ["git@github.com:me/dotconfig.git", "https://github.com/me/private-dotconfig",
                                    '"git@github.com:me/private-dotconfig.git"'])
def test_hermes_own_configuration_is_never_a_project(roots, origin):
    config = repo(roots[0] / "github.com" / "me" / "config", origin=origin)
    tree = worktree(roots[1] / "dotconfig" / "fix-x", config)
    assert place.project_dir({"command": "./install.sh", "workdir": str(config)}) is None
    assert place.project_dir({"command": "./install.sh", "workdir": str(tree)}) is None


def test_the_checkout_holding_the_plugin_is_never_a_project(roots, monkeypatch):
    own = repo(roots[0] / "github.com" / "me" / "renamed")
    monkeypatch.setattr(place, "_own_common", lambda: (own / ".git").resolve())
    assert place.project_dir({"command": "./x.sh", "workdir": str(own)}) is None


def test_local_bins_are_the_project_s_own(roots):
    project = repo(roots[0] / "github.com" / "me" / "shop")
    app = project / "apps" / "web"
    (app / "node_modules" / ".bin").mkdir(parents=True)
    (app / "node_modules" / ".bin" / "wrangler").write_text("")
    assert place.local_bin(app, "wrangler")
    assert not place.local_bin(project, "wrangler")
    (project / "node_modules" / ".bin").mkdir(parents=True)
    (project / "node_modules" / ".bin" / "tsx").write_text("")
    assert place.local_bin(app, "tsx")
    assert not place.local_bin(app, "gcloud")
