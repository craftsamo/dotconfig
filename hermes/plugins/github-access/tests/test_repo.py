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

OWNERS = {"me": ("User", "U_me"), "team": ("Organization", "O_team")}
REPOS = {"me/app": {}, "me/kit": {"isTemplate": True}, "me/old": {"isArchived": True},
         "me/ro": {"viewerPermission": "WRITE"}, "team/web": {"owner": "team", "isPrivate": False}}


def settings_node(name, **over):
    owner, short = name.split("/")
    node = {"id": f"R_{short}", "nameWithOwner": name, "description": "An app", "homepageUrl": "", "visibility": None,
            "isPrivate": True, "isArchived": False, "isTemplate": False, "isFork": False,
            "defaultBranchRef": {"name": "main"}, "viewerPermission": "ADMIN",
            "owner": {"__typename": OWNERS[owner][0], "login": owner}, "hasIssuesEnabled": True,
            "hasWikiEnabled": False, "hasProjectsEnabled": True, "hasDiscussionsEnabled": False,
            "mergeCommitAllowed": False, "squashMergeAllowed": True, "rebaseMergeAllowed": False,
            "autoMergeAllowed": False, "deleteBranchOnMerge": True, "allowUpdateBranch": False,
            "repositoryTopics": {"nodes": [{"topic": {"name": "cli"}}]}, "licenseInfo": {"spdxId": "MIT"},
            "templateRepository": None, "pushedAt": "2026-10-20T00:00:00Z"}
    extra = dict(over)
    if "owner" in extra:
        extra["owner"] = {"__typename": OWNERS[extra["owner"]][0], "login": extra["owner"]}
    node.update(extra)
    node["visibility"] = node["visibility"] or ("PRIVATE" if node["isPrivate"] else "PUBLIC")
    return node


def by_name(v, shape):
    name = f"{v.get('owner')}/{v.get('name')}"
    return {"repository": shape(name) if name in REPOS else None}


def context(name):
    n = settings_node(name, **REPOS[name])
    return {k: n[k] for k in ("id", "nameWithOwner", "isPrivate", "isArchived", "viewerPermission", "owner")}


@pytest.fixture
def gh(monkeypatch):
    fake = F.FakeGh([
        (r"homepageUrl visibility", lambda v: by_name(v, lambda n: settings_node(n, **REPOS[n]))),
        (r"viewerPermission owner\{__typename login\}", lambda v: by_name(v, context)),
        F.viewer("me"), F.member({"team"}),
        (r"repositoryOwner\(login:\$login\)\{__typename id login\}",
         lambda v: {"repositoryOwner": {"__typename": OWNERS[v["login"]][0], "id": OWNERS[v["login"]][1],
                                        "login": v["login"]} if v["login"] in OWNERS else None}),
        (r"labels\(first:100", {"repository": {"labels": {"nodes": [
            {"name": "bug", "color": "d73a4a", "description": "Something is wrong"}]}}}),
        (r"milestones\(first:100", {"repository": {"milestones": {"nodes": [
            {"number": 3, "title": "v1", "state": "OPEN", "dueOn": "2026-11-01T12:00:00Z", "description": "",
             "progressPercentage": 50.0, "open": {"totalCount": 1}, "closed": {"totalCount": 1}}]}}}),
        (r"ref\(qualifiedName", lambda v: {"repository": {"ref": {"name": "dev"} if v["ref"] == "refs/heads/dev" else None}}),
    ])
    monkeypatch.setattr(access, "run_gh", fake)
    access.forget()
    return fake


def test_a_repository_reads_with_its_settings_labels_and_milestones(gh):
    view = reads.github_repo({"action": "view", "repo": "me/app"})["repository"]
    assert view["visibility"] == "private" and view["tier"] == "own" and view["default_branch"] == "main"
    assert view["features"]["has_wiki"] is False and view["merge"]["allow_squash_merge"] is True
    assert view["topics"] == ["cli"] and view["license"] == "MIT"
    labels = reads.github_repo({"action": "labels", "repo": "me/app"})
    assert labels["labels"] == [{"name": "bug", "color": "d73a4a", "description": "Something is wrong"}]
    milestones = reads.github_repo({"action": "milestones", "repo": "me/app", "state": "all"})
    assert milestones["milestones"][0] == {"number": 3, "title": "v1", "state": "open", "due": "2026-11-01",
                                           "description": "", "progress": 50.0, "open_issues": 1, "closed_issues": 1}
    assert gh.queries(r"milestones\(first:100")[-1]["variables"]["states"] == ["OPEN", "CLOSED"]
    with pytest.raises(access.AccessError, match="state is open, closed or all"):
        reads.github_repo({"action": "milestones", "repo": "me/app", "state": "late"})


def test_a_new_repository_is_private_unless_asked_and_always_on_a_card(gh):
    gh.cmd(r"^repo create me/new --private --description Notes --license mit --gitignore Python --add-readme$",
           "https://github.com/me/new\n")
    planned = changes.plan({"changes": [{"op": "repo_create", "repo": "me/new", "description": "Notes", "license": "mit",
                                         "gitignore": "Python", "add_readme": True}]})
    assert planned["targets"] == [{"kind": "new_repo", "name": "me/new (private)", "tier": "own", "id": "U_me/me/new"}]
    assert planned["classes"] == ["admin"]
    text = changes.card(planned)
    assert "New repository: me/new (private) (own, private)" in text and "⚠️ Admin changes" in text
    assert "1. ⚠️ Create private repository me/new (license mit; gitignore Python; with a README; description: Notes)" in text
    assert changes.apply(planned)["done"][0] == {"op": "repo_create", "repo": "me/new", "url": "https://github.com/me/new"}
    public = changes.plan({"changes": [{"op": "repo_create", "repo": "team/site", "visibility": "public"}]})
    assert public["targets"][0]["tier"] == "shared"
    assert "1. ⚠️ Create public repository team/site (anyone can read it)" in changes.card(public)


@pytest.mark.parametrize("change,message", [
    ({"repo": "me/app"}, "me/app already exists"),
    ({"repo": "me/new", "visibility": "internal"}, "internal visibility is for an organization"),
    ({"repo": "bob/new"}, "no user or organization named 'bob'"),
    ({"repo": "me/new", "template": "me/app"}, "me/app is not a template repository"),
    ({"repo": "me/new", "template": "me/kit", "license": "mit"}, "a template brings its own files"),
    ({"repo": "me/new", "license": "MIT License!"}, "SPDX-style key"),
])
def test_a_new_repository_is_checked_before_any_card(gh, change, message):
    with pytest.raises(access.AccessError, match=message):
        changes.plan({"changes": [{"op": "repo_create", **change}]})


def test_a_new_repository_is_made_once_and_an_unreadable_name_is_not_taken_as_free(gh):
    with pytest.raises(access.AccessError, match="made by an earlier change of this list"):
        changes.plan({"changes": [{"op": "repo_create", "repo": "me/new"}, {"op": "repo_create", "repo": "ME/new"}]})
    gh.add(r"viewerPermission owner\{__typename login\}", RuntimeError("API rate limit exceeded"))
    with pytest.raises(access.AccessError, match="rate limit"):
        changes.plan({"changes": [{"op": "repo_create", "repo": "me/new"}]})


def test_a_new_repository_from_a_template_shows_where_it_comes_from(gh):
    gh.cmd(r"^repo create me/new --private --template me/kit$", "https://github.com/me/new\n")
    planned = changes.plan({"changes": [{"op": "repo_create", "repo": "me/new", "template": "me/kit"}]})
    assert [t["kind"] for t in planned["targets"]] == ["new_repo", "template"]
    assert "Copied from: me/kit (own, private)" in changes.card(planned)
    assert changes.apply(planned)["ok"] is True


def test_settings_move_only_what_changes_and_keep_one_merge_method(gh):
    gh.cmd(r"^repo edit me/app ")
    planned = changes.plan({"repo": "me/app", "changes": [{
        "op": "repo_edit", "description": "An app", "add_topics": ["web"], "has_issues": False, "has_wiki": False,
        "allow_rebase_merge": True, "default_branch": "dev"}]})
    line = changes.card(planned).splitlines()[-1]
    assert line == ("1. ⚠️ Settings of me/app: default branch main → dev; topics + web; issues off; "
                    "rebase merges on")
    changes.apply(planned)
    argv = gh.ran(r"^repo edit me/app")[0]
    assert argv[:5] == ["repo", "edit", "me/app", "--description", "An app"]
    assert "--enable-issues=false" in argv and "--enable-rebase-merge=true" in argv and ["--add-topic", "web"] == \
        argv[argv.index("--add-topic"):argv.index("--add-topic") + 2]


@pytest.mark.parametrize("change,message", [
    ({}, "nothing to change"),
    ({"allow_squash_merge": False}, "at least one merge method"),
    ({"default_branch": "nope"}, "has no branch 'nope'"),
    ({"add_topics": ["Web App"]}, "lowercase letters, digits and hyphens"),
    ({"repo": "me/ro", "description": "x"}, "needs admin on me/ro"),
    ({"repo": "me/old", "description": "x"}, "me/old is archived"),
])
def test_a_settings_change_is_checked_before_any_card(gh, change, message):
    with pytest.raises(access.AccessError, match=message):
        changes.plan({"repo": "me/app", "changes": [{"op": "repo_edit", **change}]})


def test_visibility_and_archiving_say_what_they_do(gh):
    gh.cmd(r"^repo edit me/app --visibility public --accept-visibility-change-consequences$")
    gh.cmd(r"^repo (archive|unarchive) me/(app|old) --yes$")
    public = changes.plan({"changes": [{"op": "repo_visibility", "repo": "me/app", "visibility": "public"}]})
    assert ("1. ⚠️ Make me/app public (was private): anyone can read its code, issues and history"
            in changes.card(public))
    assert changes.apply(public)["done"][0]["visibility"] == "public"
    with pytest.raises(access.AccessError, match="already private"):
        changes.plan({"changes": [{"op": "repo_visibility", "repo": "me/app", "visibility": "private"}]})
    assert changes.apply(changes.plan({"changes": [{"op": "repo_archive", "repo": "me/app"}]}))["done"][0]["archived"]
    unarchive = changes.plan({"changes": [{"op": "repo_archive", "repo": "me/old", "unarchive": True}]})
    assert "Unarchive me/old" in changes.card(unarchive) and changes.apply(unarchive)["ok"] is True
    for repo, unarchive_, message in (("me/old", False, "already archived"), ("me/app", True, "not archived")):
        with pytest.raises(access.AccessError, match=message):
            changes.plan({"changes": [{"op": "repo_archive", "repo": repo, "unarchive": unarchive_}]})


def test_labels_are_made_and_changed_once_each(gh):
    gh.cmd(r"^label (create|edit) ")
    planned = changes.plan({"repo": "me/app", "changes": [
        {"op": "label_create", "name": "area:web", "color": "#1D76DB", "description": "Web front end"},
        {"op": "label_edit", "name": "Bug", "new_name": "type:bug"}]})
    assert planned["classes"] == ["create"]
    text = changes.card(planned)
    assert "1. Create label area:web in me/app (#1d76db, Web front end)" in text
    assert "2. Edit label bug in me/app: name → type:bug" in text
    changes.apply(planned)
    assert gh.ran(r"^label create --repo me/app --color 1d76db --description Web front end -- area:web$")
    assert gh.ran(r"^label edit --repo me/app --name type:bug -- bug$")
    changes.apply(changes.plan({"repo": "me/app", "changes": [{"op": "label_create", "name": "--color"}]}))
    assert gh.argv[-1] == ["label", "create", "--repo", "me/app", "--", "--color"]  # a name, never a flag
    gh.add(r"labels\(first:100", {"repository": {"labels": {"nodes": [
        {"name": "bug", "color": "d73a4a", "description": ""}, {"name": "type:bug", "color": "d73a4a", "description": ""}]}}})
    for change, message in (({"op": "label_create", "name": "BUG"}, "already has 'bug'"),
                            ({"op": "label_edit", "name": "nope", "color": "000000"}, "has no label 'nope'"),
                            ({"op": "label_edit", "name": "bug"}, "new_name, color or description"),
                            ({"op": "label_edit", "name": "bug", "new_name": "Type:Bug"}, "already has 'type:bug'"),
                            ({"op": "label_create", "name": "x", "color": "red"}, "six hex digits")):
        with pytest.raises(access.AccessError, match=message):
            changes.plan({"repo": "me/app", "changes": [change]})


def test_milestones_are_made_and_changed_through_the_rest_route(gh):
    gh.cmd(r"^api --method POST repos/me/app/milestones --input -$", {"title": "v2", "number": 4})
    gh.cmd(r"^api --method PATCH repos/me/app/milestones/3 --input -$", {"title": "v1"})
    planned = changes.plan({"repo": "me/app", "changes": [
        {"op": "milestone_create", "title": "v2", "due": "2026-12-01", "description": "Second release"},
        {"op": "milestone_edit", "milestone": "V1", "due": "", "state": "closed"}]})
    text = changes.card(planned)
    assert "1. Create milestone v2 in me/app (due 2026-12-01, Second release)" in text
    assert "2. Edit milestone v1 in me/app: due removed; close" in text
    result = changes.apply(planned)
    assert result["done"][0]["number"] == 4
    sent = [json.loads(s) for a, s in zip(gh.argv, gh.stdin) if a[:2] == ["api", "--method"]]
    assert sent == [{"title": "v2", "due_on": "2026-12-01T12:00:00Z", "description": "Second release"},
                    {"due_on": None, "state": "closed"}]
    gh.add(r"milestones\(first:100", {"repository": {"milestones": {"nodes": [
        {"number": n, "title": t, "state": "OPEN", "dueOn": None, "description": "", "progressPercentage": 0,
         "open": {"totalCount": 0}, "closed": {"totalCount": 0}} for n, t in ((3, "v1"), (5, "v1.1"))]}}})
    for change, message in (({"op": "milestone_create", "title": "V1"}, "already has milestone 'v1'"),
                            ({"op": "milestone_edit", "milestone": "v1", "new_title": "V1.1"}, "already has milestone 'V1.1'"),
                            ({"op": "milestone_edit", "milestone": "v9", "state": "closed"}, "has no milestone 'v9'"),
                            ({"op": "milestone_create", "title": "v3", "due": "next week"}, "YYYY-MM-DD"),
                            ({"op": "milestone_edit", "milestone": "v1"}, "new_title, due, description or state")):
        with pytest.raises(access.AccessError, match=message):
            changes.plan({"repo": "me/app", "changes": [change]})


def test_a_mandate_may_cover_labels_but_never_a_repository_setting(gh, tmp_path, monkeypatch):
    mandate = _load("hermes_github_access_mandate", ROOT / "mandate.py")
    monkeypatch.setattr(mandate, "key", lambda home, create=False: bytes(range(32)))
    made = mandate.create(tmp_path, {"boards": [], "repos": [{"id": "R_app", "name": "me/app", "tier": "own"}],
                                     "parent": None, "classes": ["create", "routine"], "days": 3,
                                     "expires": 4102444800, "purpose": "Tidy labels"})
    label = changes.plan({"repo": "me/app", "changes": [{"op": "label_create", "name": "area:web"},
                                                        {"op": "milestone_edit", "milestone": "v1", "state": "closed"}]})
    assert mandate.covering(tmp_path, label)[0] == made["id"]
    setting = changes.plan({"repo": "me/app", "changes": [{"op": "repo_edit", "has_wiki": True}]})
    got, misses = mandate.covering(tmp_path, setting)
    assert got is None and "repo_edit is an admin change" in misses[0]
