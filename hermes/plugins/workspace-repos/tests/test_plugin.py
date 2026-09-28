import asyncio
from datetime import datetime, timezone
import importlib.util
import json
import re
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


repos = _load("workspace_repos_test", ROOT / "repos.py")
plugin = _load("workspace_repos_plugin_test", ROOT / "__init__.py")
NOW = datetime(2026, 9, 28, tzinfo=timezone.utc)


def git(cwd, *args):
    subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
                    "-c", "init.defaultBranch=main", *args], cwd=cwd, check=True, capture_output=True)


def clone(tmp, name, remote_url=None):
    """A clone of a fresh bare repo with one pushed commit; origin optionally renamed."""
    bare = tmp / "remotes" / f"{name}.git"
    git(tmp, "init", "--bare", "-q", str(bare))
    work = tmp / "ghq" / name
    git(tmp, "clone", "-q", str(bare), str(work))
    (work / "README.md").write_text("x")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "init")
    git(work, "push", "-q", "-u", "origin", "HEAD:main")
    if remote_url:
        git(work, "remote", "set-url", "origin", remote_url)
    return work


@pytest.fixture
def ws(tmp_path, monkeypatch):
    for key, value in {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
                       "GIT_COMMITTER_EMAIL": "t@x", "GIT_CONFIG_GLOBAL": "/dev/null"}.items():
        monkeypatch.setenv(key, value)
    root = tmp_path / "Workspaces"
    acme = root / "Projects" / "Acme" / "github"
    acme.mkdir(parents=True)
    clean = clone(tmp_path, "site", "git@github.com:acme/site.git")
    busy = clone(tmp_path, "app", "git@github.com:acme/app.git")
    (busy / "README.md").write_text("changed")                  # dirty
    (busy / "new.txt").write_text("n")                          # untracked counts as changed
    git(busy, "stash", "push", "-q", "-m", "wip", "--", "README.md")
    (busy / "README.md").write_text("changed again")
    git(busy, "switch", "-q", "-c", "feature")
    (busy / "f.txt").write_text("f")
    git(busy, "add", "f.txt")
    git(busy, "commit", "-q", "-m", "local only")               # unpushed, no upstream
    git(busy, "worktree", "add", "-q", str(tmp_path / "wt"), "main")
    twin = clone(tmp_path, "twin", "git@github.com:acme/site.git")   # same origin as site
    upstream = clone(tmp_path, "tool", "https://github.com/someone/tool.git")
    (acme / "site").symlink_to(clean)
    (acme / "app").symlink_to(busy)
    (acme / "twin").symlink_to(twin)
    (acme / "gone").symlink_to(tmp_path / "missing")            # broken link
    budget = root / "Personal" / "Budget" / "github"
    budget.mkdir(parents=True)
    (budget / "tool").symlink_to(upstream)
    (budget / "notes").mkdir()                                  # a plain directory, not Git
    (root / "Projects" / ".registry").mkdir()                   # hidden, not a Group
    return root


def node(slug, prs=0, issues=0, permission="ADMIN", items=None):
    return {"nameWithOwner": slug, "isArchived": False, "viewerPermission": permission,
            "prs": {"totalCount": prs}, "issues": {"totalCount": issues}, "discussions": {"totalCount": 1},
            **({"items": {"nodes": items}} if items is not None else {})}


PR = {"number": 7, "title": "Add | pipe <b>", "url": "https://github.com/acme/app/pull/7", "isDraft": False,
      "createdAt": "2026-09-20T00:00:00Z", "updatedAt": "2026-09-26T00:00:00Z", "reviewDecision": None,
      "headRefName": "feature", "author": {"login": "someone"},
      "reviewRequests": {"nodes": [{"requestedReviewer": {"login": "me"}}]},
      "commits": {"nodes": [{"commit": {"statusCheckRollup": {"state": "FAILURE"}}}]}}
ISSUE = {"number": 3, "title": "Bug", "url": "https://github.com/acme/app/issues/3",
         "createdAt": "2026-09-01T00:00:00Z", "updatedAt": "2026-09-27T00:00:00Z", "author": {"login": "x"},
         "assignees": {"nodes": [{"login": "me"}]}, "labels": {"nodes": [{"name": "bug"}]},
         "comments": {"totalCount": 2}}


def fake_gh(queries):
    """A gh stand-in answering by slug; the upstream is read-only and holds foreign work."""
    def run(query):
        queries.append(query)
        detail = "items:" in query
        kind = PR if "items: pullRequests" in query else ISSUE
        data = {"viewer": {"login": "me"}}
        for alias, owner, name in re.findall(r'(r\d+): repository\(owner: "([^"]+)", name: "([^"]+)"\)', query):
            slug = f"{owner}/{name}"
            if slug == "acme/app":
                items = [kind] if detail else None
                data[alias] = node(slug, prs=1, issues=4, items=items)
            elif slug == "acme/site":
                data[alias] = node(slug, prs=2, issues=0, items=[] if detail else None)
            elif slug == "someone/tool":
                data[alias] = node(slug, prs=50, issues=50, permission="READ",
                                   items=[kind, kind] if detail else None)
        return data, []
    return run


def result_for(ws, runner=None, **args):
    return repos.run({"action": "summary", **args}, root=ws, runner=runner or fake_gh([]), now=NOW)


def by_name(result):
    return {f"{repos.label(r['group'])}/{r['name']}": r for r in result["repos"]}


def test_local_state_is_read_without_fetching(ws, monkeypatch):
    seen = []
    real = repos._git

    def spy(repo, *args):
        seen.append(args)
        return real(repo, *args)
    monkeypatch.setattr(repos, "_git", spy)
    rows = by_name(result_for(ws, github=False))
    assert set(rows) == {"Acme/app", "Acme/gone", "Acme/site", "Acme/twin", "Budget/notes", "Budget/tool"}
    app = rows["Acme/app"]
    assert app["branch"] == "feature" and app["changed"] == 2 and app["unpushed"] == 1
    assert app["stashes"] == 1 and app["worktrees"] == 2 and app["slug"] == "acme/app"
    assert {"dirty", "unpushed", "no-upstream", "stash", "worktrees"} <= set(app["flags"])
    assert rows["Acme/site"]["flags"] == ["shared-origin"] and rows["Acme/twin"]["flags"] == ["shared-origin"]
    assert rows["Acme/gone"]["flags"] == ["broken"] and rows["Budget/notes"]["flags"] == ["not-git"]
    assert repos.state_text(app) == "2 changed, 1 unpushed, feature has no upstream, 1 stash, 2 worktrees"
    assert not any(a[0] in ("fetch", "pull", "push", "commit", "gc") for a in seen)


def test_github_counts_skip_read_only_upstreams_and_count_a_repo_once(ws):
    queries = []
    result = result_for(ws, runner=fake_gh(queries))
    assert len(queries) == 1 and result["viewer"] == "me" and result["status"] == "complete"
    rows = by_name(result)
    assert "read-only" in rows["Budget/tool"]["flags"]
    # site and twin share acme/site (2 PRs): counted once; the upstream's 50 are not yours.
    assert result["totals"]["prs"] == 3 and result["totals"]["issues"] == 4
    assert result["totals"]["attention"] == 5        # app, gone, notes, site, twin


def test_prs_and_issues_list_only_writable_repos(ws):
    prs = repos.run({"action": "prs"}, root=ws, runner=fake_gh([]), now=NOW)["prs"]
    assert [(p["repo"], p["number"]) for p in prs] == [("acme/app", 7)]
    assert prs[0]["review_requested_from_you"] and prs[0]["ci"] == "FAILURE" and prs[0]["idle_days"] == 2
    assert repos.pr_state(prs[0]) == "CI failing, your review"
    issues = repos.run({"action": "issues", "group": "acme"}, root=ws, runner=fake_gh([]), now=NOW)["issues"]
    assert issues[0]["assigned_to_you"] and issues[0]["labels"] == ["bug"]


def test_github_failure_keeps_local_state(ws):
    def down(query):
        raise RuntimeError("gh: not logged in")
    result = result_for(ws, runner=down)
    assert result["status"] == "partial" and result["diagnostics"][0]["code"] == "github-unavailable"
    assert by_name(result)["Acme/app"]["changed"] == 2
    text = repos.render_rich(result)
    assert "*partial*" in text and "| Acme | 4 |" in text


@pytest.mark.parametrize("effect, message", [
    (FileNotFoundError("gh"), "gh is not installed"),
    (subprocess.TimeoutExpired("gh", 40), "gh timed out"),
    (subprocess.CompletedProcess(["gh"], 1, stdout="", stderr="\n"), "gh failed (exit 1)"),
    (subprocess.CompletedProcess(["gh"], 1, stdout="", stderr="HTTP 401\nauth required\n"), "auth required"),
])
def test_gh_failures_become_partial_diagnostics(ws, monkeypatch, effect, message):
    real = subprocess.run

    def fake(cmd, *args, **kwargs):
        if cmd[0] != "gh":
            return real(cmd, *args, **kwargs)
        if isinstance(effect, BaseException):
            raise effect
        return effect
    monkeypatch.setattr(repos.subprocess, "run", fake)
    result = repos.run({"action": "summary"}, root=ws)
    assert result["status"] == "partial" and message in result["diagnostics"][0]["detail"]
    assert by_name(result)["Acme/app"]["changed"] == 2


def test_missing_remote_is_a_finding_not_a_failed_read(ws):
    def gone(query):
        data, _ = fake_gh([])(query)
        alias = next(k for k, v in data.items() if k != "viewer" and v["nameWithOwner"] == "acme/app")
        data[alias] = None
        return data, [{"type": "NOT_FOUND", "message": "Could not resolve acme/app"}]
    result = result_for(ws, runner=gone)
    assert result["status"] == "complete" and "remote-missing" in by_name(result)["Acme/app"]["flags"]


def test_group_names_resolve_forgivingly(ws):
    assert {r["group"] for r in result_for(ws, group="BUD", github=False)["repos"]} == {"Personal/Budget"}
    with pytest.raises(repos.UnknownGroup):
        result_for(ws, group="zzz", github=False)
    with pytest.raises(ValueError):
        repos.run({"action": "prs", "github": False}, root=ws)


def test_rich_output_is_tables_folds_and_commands(ws):
    text = repos.render_rich(result_for(ws))
    assert text.startswith("## Repos") and "```" not in text
    assert "| Group | Repos | Attention | PRs | Issues |" in text
    assert text.count("<details>") == text.count("</details>") == 3
    assert "`/repos prs`" in text and "`/repos Acme`" in text and "Read-only upstreams, not counted: tool" in text
    prs = repos.render_rich(repos.run({"action": "prs"}, root=ws, runner=fake_gh([]), now=NOW), title="PRs")
    assert "[#7](https://github.com/acme/app/pull/7) Add / pipe ‹b›" in prs    # no pipe or tag leaks
    assert "CI failing, your review" in prs


def test_command_parses_subcommand_and_group(ws, monkeypatch):
    monkeypatch.setenv("WORKSPACES_ROOT", str(ws))
    monkeypatch.setattr(repos, "_gh", fake_gh([]))
    assert plugin.parse("pulls tech") == ("prs", "tech") and plugin.parse("Acme") == ("summary", "Acme")
    assert plugin.repos_text("prs acme").startswith("## Pull requests · Acme")
    assert "`/repos issues Acme`" in plugin.repos_text("acme")
    unknown = plugin.repos_text("issues zzz")
    assert unknown.startswith("No Group matches `zzz`") and "`/repos issues Budget`" in unknown
    assert asyncio.run(plugin.repos_command("")).startswith("## Repos")


def test_tool_refuses_inbound_a2a(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assert "A2A" in json.loads(plugin.workspace_repos({"action": "summary"}))["error"]


class Ctx:
    def __init__(self, profile):
        self.profile_name, self.tools, self.commands = profile, [], []

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)

    def register_command(self, name, handler, **kwargs):
        self.commands.append(name)


def test_registers_only_for_engineer_and_assistant():
    for profile, expected in (("engineer", 1), ("assistant", 1), ("creator", 0)):
        ctx = Ctx(profile)
        plugin.register(ctx)
        assert len(ctx.tools) == expected and ctx.commands == ["repos"] * expected
    schema = Ctx("engineer")
    plugin.register(schema)
    assert schema.tools[0]["schema"]["parameters"]["properties"]["action"]["enum"] == ["summary", "prs", "issues"]
