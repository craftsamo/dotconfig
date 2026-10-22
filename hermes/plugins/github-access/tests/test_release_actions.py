import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fake_gh as F  # noqa: E402


def _load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


changes = _load("hermes_github_access_changes", ROOT / "changes.py")
reads = sys.modules["hermes_github_access_repo_reads"]
access = changes.access
SHA = "c0ffee" + "0" * 34


def release_node(tag, draft=True, title="", notes="Changes"):
    return {"tagName": tag, "name": title, "isDraft": draft, "isPrerelease": False, "isLatest": not draft,
            "createdAt": "t", "publishedAt": None if draft else "t", "url": f"https://github.com/me/app/releases/tag/{tag}",
            "tagCommit": None if draft else {"oid": SHA}, "releaseAssets": {"nodes": []}, "description": notes}


def run_json(status="completed", conclusion="failure", attempt=1):
    return {"databaseId": 42, "name": "CI", "displayTitle": "Fix login", "status": status, "conclusion": conclusion,
            "event": "push", "headBranch": "main", "headSha": SHA, "createdAt": "t", "url": "u", "workflowName": "CI",
            "attempt": attempt, "updatedAt": "t",
            "jobs": [{"databaseId": 7, "name": "test", "status": "completed", "conclusion": "failure",
                      "steps": [{"name": "pytest", "conclusion": "failure"}, {"name": "setup", "conclusion": "success"}]}]}


@pytest.fixture
def gh(monkeypatch):
    state = {"releases": {"v1.0.0": release_node("v1.0.0", draft=False), "v1.1.0": release_node("v1.1.0")},
             "refs": {"refs/heads/main": SHA, "refs/tags/v1.0.0": SHA, "refs/tags/v0.9.0": SHA}, "run": run_json(),
             "workflow_text": "on:\n  workflow_dispatch:\n    inputs:\n      env:\n"}
    fake = F.FakeGh([
        (r"homepageUrl visibility", {"repository": {
            "id": "R_app", "nameWithOwner": "me/app", "description": "", "homepageUrl": "", "visibility": "PRIVATE",
            "isPrivate": True, "isArchived": False, "isTemplate": False, "isFork": False, "defaultBranchRef": {"name": "main"},
            "viewerPermission": "ADMIN", "owner": {"__typename": "User", "login": "me"}, "hasIssuesEnabled": True,
            "hasWikiEnabled": False, "hasProjectsEnabled": True, "hasDiscussionsEnabled": False, "mergeCommitAllowed": True,
            "squashMergeAllowed": True, "rebaseMergeAllowed": True, "autoMergeAllowed": False, "deleteBranchOnMerge": False,
            "allowUpdateBranch": False, "repositoryTopics": {"nodes": []}, "licenseInfo": None, "templateRepository": None,
            "pushedAt": None}}),
        F.repos(F.repo("me/app"), F.repo("team/web", "Organization", private=False)), F.viewer("me"), F.member({"team"}),
        (r"release\(tagName", lambda v: {"repository": {"release": state["releases"].get(v["tag"])}}),
        (r"releases\(first", lambda v: {"repository": {"releases": {"nodes": list(state["releases"].values())}}}),
        (r"ref\(qualifiedName:\$ref\)\{name target", lambda v: {"repository": {"ref": {"name": "x", "target": {
            "oid": state["refs"][v["ref"]]}} if v["ref"] in state["refs"] else None}}),
        (r"object\(expression", lambda v: {"repository": {"object": {"text": state["workflow_text"]}}}),
    ])
    fake.cmd(r"^workflow list --repo me/app", [{"id": 9, "name": "Deploy", "path": ".github/workflows/deploy.yml",
                                                 "state": "active"},
                                                {"id": 10, "name": "Old", "path": ".github/workflows/old.yml",
                                                 "state": "disabled_manually"}])
    fake.cmd(r"^run view 42 --repo me/app --json", lambda argv, stdin: state["run"])
    fake.cmd(r"^run view 42 --repo me/app --log-failed$", "\n".join(f"line {i}" for i in range(500)))
    fake.cmd(r"^run list --repo me/app", [run_json()])
    monkeypatch.setattr(access, "run_gh", fake)
    access.forget()
    fake.state = state
    return fake


def test_releases_workflows_and_runs_read_with_a_capped_failed_log(gh):
    found = reads.github_repo({"action": "releases", "repo": "me/app"})
    assert [(r["tag"], r["draft"]) for r in found["releases"]] == [("v1.0.0", False), ("v1.1.0", True)]
    assert [w["name"] for w in reads.github_repo({"action": "workflows", "repo": "me/app"})["workflows"]] == ["Deploy", "Old"]
    runs = reads.github_repo({"action": "runs", "repo": "me/app", "branch": "main", "status": "failure", "limit": 5})
    assert runs["runs"][0]["id"] == 42 and gh.ran(r"^run list --repo me/app --limit 5 .* --branch main --status failure$")
    run = reads.github_repo({"action": "run", "repo": "me/app", "run": "https://github.com/me/app/actions/runs/42"})["run"]
    assert run["jobs"][0]["failed_steps"] == ["pytest"]
    assert run["failed_log"].splitlines()[0] == "line 380" and run["failed_log"].endswith("line 499")
    with pytest.raises(access.AccessError, match="run is a run id or its URL"):
        reads.github_repo({"action": "run", "repo": "me/app", "run": "latest"})


def test_a_release_is_made_as_a_draft_only(gh):
    gh.cmd(r"^release create v1.2.0 --repo me/app --draft --notes-file - --title Spring --target main --generate-notes$",
           "https://github.com/me/app/releases/tag/untagged-1\n")
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "release_create", "tag": "v1.2.0", "title": "Spring",
                                                           "target": "main", "generate_notes": True, "notes": "Hi"}]})
    assert planned["classes"] == ["create"]
    assert ("1. Draft release Spring in me/app, seen only by pushers until published (new tag v1.2.0 from main; "
            "generated notes + notes (2 chars))") in changes.card(planned)
    result = changes.apply(planned)
    assert result["done"][0]["draft"] is True and gh.stdin[-1] == "Hi"
    for change, message in (({"tag": "v1.1.0"}, "already has a release 'v1.1.0'"),
                            ({"tag": "v0.9.0", "target": "main"}, "tag v0.9.0 exists already"),
                            ({"tag": "v2", "target": "nope"}, "has no branch 'nope'"),
                            ({"tag": "bad tag"}, "is not a tag name"), ({"tag": "a..b"}, "is not a tag name")):
        with pytest.raises(access.AccessError, match=message):
            changes.plan({"repo": "me/app", "changes": [{"op": "release_create", **change}]})


def test_editing_a_release_is_routine_on_a_draft_and_admin_once_published(gh):
    gh.cmd(r"^release edit v1\.[01]\.0 --repo me/app")
    draft = changes.plan({"repo": "me/app", "changes": [{"op": "release_edit", "tag": "v1.1.0", "notes": "More",
                                                         "prerelease": False}]})
    assert draft["classes"] == ["routine"]
    changes.apply(draft)
    assert gh.ran(r"^release edit v1.1.0 --repo me/app --notes-file - --prerelease=false$")
    published = changes.plan({"repo": "me/app", "changes": [{"op": "release_edit", "tag": "v1.0.0", "title": "First"}]})
    assert published["classes"] == ["admin"]
    assert "1. ⚠️ Edit published release v1.0.0 in me/app: title → First" in changes.card(published)
    with pytest.raises(access.AccessError, match="its tag already points at a commit"):
        changes.plan({"repo": "me/app", "changes": [{"op": "release_edit", "tag": "v1.0.0", "target": "main"}]})
    with pytest.raises(access.AccessError, match="has no release 'v9'"):
        changes.plan({"repo": "me/app", "changes": [{"op": "release_edit", "tag": "v9", "title": "x"}]})


def test_publishing_a_release_always_asks(gh):
    gh.cmd(r"^release edit v1.1.0 --repo me/app --draft=false --latest$")
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "release_publish", "tag": "v1.1.0", "latest": True}]})
    assert planned["classes"] == ["admin"]
    text = changes.card(planned)
    assert "Release: v1.1.0 (draft) of me/app (own, private)" in text
    assert ("1. ⚠️ Publish release v1.1.0 of me/app, seen by every reader and told to watchers (creates tag v1.1.0; "
            "marked Latest)") in text
    assert changes.apply(planned)["done"][0]["published"] is True
    with pytest.raises(access.AccessError, match="v1.0.0 is published already"):
        changes.plan({"repo": "me/app", "changes": [{"op": "release_publish", "tag": "v1.0.0"}]})


def test_a_run_is_re_run_only_when_it_finished_and_its_attempt_is_bound(gh):
    gh.cmd(r"^run rerun 42 --repo me/app")
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "run_rerun", "run": "42"}]})
    assert planned["classes"] == ["admin"] and ["run", "42:1", "own"] in changes.binding(planned)
    assert "Re-running: CI run 42 on main at c0ffee0" in changes.card(planned)
    changes.apply(planned)
    assert gh.ran(r"^run rerun 42 --repo me/app --failed$")
    gh.state["run"] = run_json(attempt=2)
    assert changes.binding(changes.plan({"repo": "me/app", "changes": [{"op": "run_rerun", "run": "42"}]})) != \
        changes.binding(planned)
    changes.apply(changes.plan({"repo": "me/app", "changes": [{"op": "run_rerun", "run": "42", "failed_only": False}]}))
    assert gh.ran(r"^run rerun 42 --repo me/app$")
    for run, message in ((run_json(status="in_progress", conclusion=None), "is in_progress; wait for it"),
                         (run_json(conclusion="success"), "ended success; it has no failed jobs")):
        gh.state["run"] = run
        with pytest.raises(access.AccessError, match=message):
            changes.plan({"repo": "me/app", "changes": [{"op": "run_rerun", "run": "42"}]})


def test_a_workflow_starts_by_hand_on_the_commit_the_card_shows(gh):
    gh.cmd(r"^workflow run 9 --repo me/app --ref main --json$")
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "workflow_dispatch", "workflow": "deploy.yml",
                                                           "inputs": {"env": "staging", "note": "@/etc/passwd"}}]})
    assert planned["classes"] == ["admin"] and ["workflow", f"9@{SHA}", "own"] in changes.binding(planned)
    text = changes.card(planned)
    assert "Starting: Deploy (.github/workflows/deploy.yml) on main at c0ffee0" in text
    assert ("1. ⚠️ Run workflow Deploy, whatever it does (a deploy, a publish), on main at c0ffee0 with env=staging, "
            "note=@/etc/passwd") in text
    changes.apply(planned)
    assert json.loads(gh.stdin[-1]) == {"env": "staging", "note": "@/etc/passwd"}  # a value, never a file to read
    for change, message in (({"workflow": "Old"}, "Old is disabled_manually"), ({"workflow": "nope"}, "no workflow 'nope'"),
                            ({"workflow": "Deploy", "ref": "dev"}, "has no branch or tag 'dev'")):
        with pytest.raises(access.AccessError, match=message):
            changes.plan({"repo": "me/app", "changes": [{"op": "workflow_dispatch", **change}]})
    gh.state["workflow_text"] = "on: push\n"
    with pytest.raises(access.AccessError, match="cannot be started by hand"):
        changes.plan({"repo": "me/app", "changes": [{"op": "workflow_dispatch", "workflow": "9"}]})


def test_a_draft_published_after_the_card_is_a_different_change(gh):
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "release_edit", "tag": "v1.1.0", "title": "Spring"}]})
    assert planned["classes"] == ["routine"]
    gh.state["releases"]["v1.1.0"] = release_node("v1.1.0", draft=False)
    gh.state["refs"]["refs/tags/v1.1.0"] = SHA
    again = changes.plan({"repo": "me/app", "changes": [{"op": "release_edit", "tag": "v1.1.0", "title": "Spring"}]})
    assert again["classes"] == ["admin"] and changes.binding(again) != changes.binding(planned)


def test_a_workflow_is_named_once_and_a_trigger_in_a_comment_is_no_trigger(gh):
    gh.cmd(r"^workflow list --repo me/app", [{"id": 9, "name": "Deploy", "path": ".github/workflows/deploy.yml",
                                               "state": "active"},
                                              {"id": 11, "name": "Deploy", "path": ".github/workflows/deploy-eu.yml",
                                               "state": "active"}])
    with pytest.raises(access.AccessError, match="'Deploy' names 2 workflows"):
        changes.plan({"repo": "me/app", "changes": [{"op": "workflow_dispatch", "workflow": "Deploy"}]})
    assert changes.plan({"repo": "me/app", "changes": [{"op": "workflow_dispatch", "workflow": "11"}]})["steps"][0][
        "workflow"]["path"] == ".github/workflows/deploy-eu.yml"
    gh.state["workflow_text"] = "on: push  # add workflow_dispatch later\n# workflow_dispatch:\n"
    with pytest.raises(access.AccessError, match="cannot be started by hand"):
        changes.plan({"repo": "me/app", "changes": [{"op": "workflow_dispatch", "workflow": "9"}]})
    gh.state["workflow_text"] = "on: [push, workflow_dispatch]\n"
    assert changes.plan({"repo": "me/app", "changes": [{"op": "workflow_dispatch", "workflow": "9"}]})


def test_a_run_url_of_another_repository_is_refused_and_a_log_loses_its_control_characters(gh):
    with pytest.raises(access.AccessError, match="is a run of acme/x, not of me/app"):
        changes.plan({"repo": "me/app", "changes": [{"op": "run_rerun", "run": "https://github.com/acme/x/actions/runs/42"}]})
    gh.cmd(r"^run view 42 --repo me/app --log-failed$", "\x1b[31mError\x1b[0m: boom\u202e\x07\n")
    run = reads.github_repo({"action": "run", "repo": "me/app", "run": "42"})["run"]
    assert run["failed_log"] == "Error: boom"


def test_no_mandate_covers_a_publish_a_run_or_a_workflow(gh, tmp_path, monkeypatch):
    mandate = _load("hermes_github_access_mandate", ROOT / "mandate.py")
    monkeypatch.setattr(mandate, "key", lambda home, create=False: bytes(range(32)))
    mandate.create(tmp_path, {"boards": [], "repos": [{"id": "R_app", "name": "me/app", "tier": "own"}], "parent": None,
                              "classes": ["create", "routine"], "days": 3, "expires": 4102444800, "purpose": "Ship"})
    draft = changes.plan({"repo": "me/app", "changes": [{"op": "release_create", "tag": "v1.2.0"}]})
    assert mandate.covering(tmp_path, draft)[0] is not None
    for change in ({"op": "release_publish", "tag": "v1.1.0"}, {"op": "run_rerun", "run": "42"},
                   {"op": "workflow_dispatch", "workflow": "Deploy"}):
        got, misses = mandate.covering(tmp_path, changes.plan({"repo": "me/app", "changes": [change]}))
        assert got is None and "admin change" in misses[0]
