import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fake_gh as F  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


access = _load("github_access_engine_test", ROOT / "access.py")


@pytest.fixture
def gh(monkeypatch):
    fake = F.FakeGh([F.viewer("me"), F.member({"team"})])
    monkeypatch.setattr(access, "run_gh", fake)
    access.forget()
    return fake


def test_references_in_every_accepted_form():
    assert access.parse_issue("https://github.com/acme/web/issues/7#c") == ("acme/web", 7)
    assert access.parse_issue("acme/web#7") == ("acme/web", 7)
    assert access.parse_issue("#7", "me/app") == ("me/app", 7)
    with pytest.raises(access.AccessError, match="needs its repository"):
        access.parse_issue("7")
    assert access.parse_repo("git@github.com:acme/web.git") == "acme/web"
    assert access.parse_project("https://github.com/orgs/team/projects/3/views/1") == {"owner": "team", "number": 3}
    assert access.parse_project("5", "me") == {"owner": "me", "number": 5}
    assert access.parse_project("Roadmap") == {"owner": None, "title": "Roadmap"}


def test_graphql_sends_typed_variables_and_raises_github_errors(gh):
    gh.add(r"broken", RuntimeError("Could not resolve to a Repository"))
    with pytest.raises(access.AccessError, match="Could not resolve to a Repository"):
        access.graphql("query{broken}")
    assert gh.argv[-1] == ["api", "graphql", "--input", "-"]


@pytest.mark.parametrize("name,owner_type,private,orgs,expected", [
    ("me/app", "User", True, set(), "own"),
    ("me/site", "User", False, set(), "shared"),
    ("team/web", "Organization", True, {"team"}, "shared"),
    ("acme/web", "Organization", False, set(), "other"),
    ("you/app", "User", True, set(), "other"),
])
def test_a_repository_tier_comes_from_its_owner_and_visibility(gh, name, owner_type, private, orgs, expected):
    gh.add(*F.repos(F.repo(name, owner_type, private)))
    assert access.repo_context(name)["tier"] == expected


def test_a_board_tier_follows_the_same_rule(gh):
    assert access._board(F.board("me", 1))["tier"] == "own"
    assert access._board(F.board("me", 2, public=True))["tier"] == "shared"
    assert access._board(F.board("team", 3, owner_type="Organization"))["tier"] == "shared"
    assert access._board(F.board("acme", 4, owner_type="Organization"))["tier"] == "other"


def test_board_resolution_walks_linked_org_user_and_reports_each_route(gh):
    gh.add(*F.repos(F.repo("team/web", "Organization")))
    gh.add(*F.linked([F.board("team", 9, "Other", "Organization", can_update=False)]))
    gh.add(*F.owner_types({"team": "Organization"}))
    gh.add(*F.owner_boards("organization", []))
    gh.add(*F.viewer_boards([F.board("me", 1)]))
    got = access.resolve_board(repo="team/web")
    assert got["route"] == "user" and got["board"]["number"] == 1
    assert [c["route"] for c in got["considered"]] == ["linked", "org", "user"]
    assert got["considered"][0]["outcome"] == "no writable linked board"


def test_one_writable_linked_board_wins_and_several_need_a_title(gh):
    gh.add(*F.repos(F.repo("me/app")))
    gh.add(*F.linked([F.board("me", 3, "Alpha")]))
    assert access.resolve_board(repo="me/app")["board"]["number"] == 3
    gh.add(*F.linked([F.board("me", 3, "Roadmap"), F.board("me", 4, "Beta")]))
    with pytest.raises(access.AccessError, match="2 writable boards are linked"):
        access.resolve_board(repo="me/app")  # never a guess, not even the one titled Roadmap
    assert access.resolve_board(project="Beta", repo="me/app")["board"]["number"] == 4
    gh.add(*F.linked([F.board("me", 3, "Beta"), F.board("me", 4, "Beta")]))
    with pytest.raises(access.AccessError, match="2 writable boards titled 'Beta' are linked"):
        access.resolve_board(project="Beta", repo="me/app")


def test_explicit_boards_by_url_number_and_owner_title(gh):
    gh.add(*F.owner_types({"team": "Organization", "me": "User"}))
    gh.add(r"organization\(login:\$login\)\{projectV2\(number:\$n\)",
           {"organization": {"projectV2": F.board("team", 3, "Team", "Organization")}})
    gh.add(r"user\(login:\$login\)\{projectV2\(number:\$n\)", {"user": {"projectV2": F.board("me", 5)}})
    gh.add(*F.owner_boards("organization", [F.board("team", 7, "Plans", "Organization")]))
    assert access.resolve_board(project="https://github.com/orgs/team/projects/3")["board"]["number"] == 3
    assert access.resolve_board(project="5", owner="@me")["board"]["number"] == 5
    assert access.resolve_board(project="Plans", owner="team")["board"]["number"] == 7
    with pytest.raises(access.AccessError, match="needs its owner"):
        access.resolve_board(project="5")


def test_a_write_re_reads_membership_and_an_unreadable_one_is_never_cached(gh):
    gh.add(*F.repos(F.repo("team/web", "Organization")))
    assert access.repo_context("team/web")["tier"] == "shared"
    gh.add(*F.member(set()))  # the viewer left the organization
    assert access.repo_context("team/web")["tier"] == "shared"  # a read may use the cache
    assert access.repo_context("team/web", fresh=True)["tier"] == "other"
    gh.add(r"viewerIsAMember", RuntimeError("timeout"))
    access.forget()
    assert access.repo_context("team/web")["tier"] == "other"
    gh.add(*F.member({"team"}))
    assert access.repo_context("team/web", fresh=True)["tier"] == "shared"


def test_an_unknown_viewer_raises_rather_than_guessing_a_tier(gh):
    gh.add(r"^query\{viewer\{login\}\}$", RuntimeError("Bad credentials"))
    gh.add(*F.repos(F.repo("me/app")))
    with pytest.raises(access.AccessError, match="Bad credentials"):
        access.repo_context("me/app")


def test_references_are_github_com_and_a_pr_is_not_an_issue():
    with pytest.raises(access.AccessError, match="not an issue reference"):
        access.parse_issue("https://ghe.example/acme/web/issues/1")
    with pytest.raises(access.AccessError, match="is a pull request"):
        access.parse_issue("https://github.com/acme/web/pull/9")
    assert access.parse_issue("https://github.com/acme/web/pull/9", allow_pr=True) == ("acme/web", 9)


def test_no_board_names_every_route(gh):
    gh.add(*F.viewer_boards([]))
    with pytest.raises(access.AccessError, match="linked: no repository given; org: no repository given; user: no board"):
        access.resolve_board()


ISSUE = {
    "id": "I_7", "number": 7, "title": "Thing", "url": "https://github.com/me/app/issues/7", "state": "OPEN",
    "stateReason": None, "body": "Spec", "createdAt": "t0", "updatedAt": "t1", "author": {"login": "me"},
    "repository": {"nameWithOwner": "me/app"}, "assignees": {"nodes": []}, "labels": {"nodes": [{"name": "type:bug"}]},
    "milestone": {"number": 1, "title": "v1", "dueOn": None}, "issueType": None,
    "parent": {"number": 3, "title": "Goal", "url": "u3", "state": "OPEN", "repository": {"nameWithOwner": "me/app"}},
    "subIssues": {"nodes": []}, "subIssuesSummary": {"total": 0, "completed": 0, "percentCompleted": 0},
    "linkedBranches": {"nodes": [{"ref": {"name": "7-thing"}}]}, "closedByPullRequestsReferences": {"nodes": []},
    "projectItems": {"nodes": [{"id": "PVTI_1", "isArchived": False, "project": {"id": "PVT_me_1", "number": 1,
                                                                                 "title": "Roadmap", "url": "b"}}]},
}


def test_issue_view_reads_the_whole_picture_and_survives_a_refused_dependency_read(gh):
    gh.add(*F.repos(F.repo("me/app")))
    gh.add(r"stateReason body", {"repository": {"issue": dict(ISSUE)}})
    gh.add(r"blockedBy\(first:50\)", RuntimeError("Field 'blockedBy' doesn't exist"))
    out = access.github_issue({"action": "view", "issue": "me/app#7", "comments": 0})
    assert out["tier"] == "own"
    i = out["issue"]
    assert i["kind"] == "bug" and i["parent"]["number"] == 3 and i["linked_branches"] == ["7-thing"]
    assert i["boards"][0]["item"] == "PVTI_1" and i["blocked_by"] == [] and "blockedBy" in i["dependencies_error"]
    assert gh.queries(r"stateReason body")[0]["variables"]["withComments"] is False


def test_issue_list_builds_the_search_and_routes_kind_to_a_type_or_a_label(gh):
    gh.add(*F.repos(F.repo("team/web", "Organization"), F.repo("me/app")))
    gh.add(r"issueTypes\(first:25\)", {"organization": {"issueTypes": {"nodes": [{"name": "Bug", "isEnabled": True}]}}})
    gh.add(r"search\(type:ISSUE", {"search": {"pageInfo": {"hasNextPage": False}, "nodes": []}})
    org = access.github_issue({"action": "list", "repo": "team/web", "kind": "bug", "milestone": "none"})
    assert org["query"] == 'repo:team/web is:issue state:open type:"Bug" no:milestone'
    user = access.github_issue({"action": "list", "repo": "me/app", "kind": "bug", "state": "all"})
    assert user["query"] == 'repo:me/app is:issue label:"type:bug"'
    with pytest.raises(access.AccessError, match="cannot be used as a search value"):
        access.github_issue({"action": "list", "repo": "me/app", "label": 'x" repo:other/x'})
    with pytest.raises(access.AccessError, match="assignee is a login"):
        access.github_issue({"action": "list", "repo": "me/app", "assignee": "bob repo:other/x"})
    with pytest.raises(access.AccessError, match="cannot name other repositories"):
        access.github_issue({"action": "list", "repo": "me/app", "query": "sort:updated repo:other/x"})


def _item(id_, status, content):
    return {"id": id_, "isArchived": False,
            "fieldValues": {"nodes": [{"name": status, "field": {"name": "Status"}}] if status else []},
            "content": content}


def test_board_items_page_through_and_report_a_cut(gh, monkeypatch):
    monkeypatch.setattr(access, "ITEM_CAP", 3)
    gh.add(*F.viewer_boards([F.board("me", 1)]))
    pages = iter([["A", "B"], ["C"]])

    def page(v):
        ids = next(pages)
        return {"node": {"items": {"pageInfo": {"hasNextPage": ids != ["C"], "endCursor": "x"},
                                   "nodes": [_item(i, "Todo", None) for i in ids]}}}
    gh.add(r"items\(first:100,after:\$after\)", page)
    out = access.github_board({"action": "items"})
    assert [i["item"] for i in out["items"]] == ["A", "B", "C"] and out["truncated"] is False
    pages = iter([["A", "B"], ["C", "D"]])
    out = access.github_board({"action": "items"})
    assert [i["item"] for i in out["items"]] == ["A", "B", "C"] and out["truncated"] is True


def test_board_items_flatten_fields_and_filter_by_status_type_and_title(gh):
    gh.add(*F.viewer_boards([F.board("me", 1)]))
    gh.add(r"items\(first:100,after:\$after\)", {"node": {"items": {"pageInfo": {"hasNextPage": False}, "nodes": [
        _item("A", "Todo", {"__typename": "DraftIssue", "id": "DI_A", "title": "Move the domain", "body": "why"}),
        _item("B", "Done", {"__typename": "DraftIssue", "id": "DI_B", "title": "Old", "body": ""}),
        _item("C", "Waiting", {"__typename": "Issue", "id": "I_C", "number": 5, "title": "Fix login", "url": "u",
                               "state": "OPEN", "repository": {"nameWithOwner": "me/app"}, "issueType": None,
                               "labels": {"nodes": []}, "parent": None, "subIssuesSummary": None}),
        _item("D", "Cancelled", None),
    ]}}})
    out = access.github_board({"action": "items", "status": "-Done,-Cancelled"})
    assert [i["item"] for i in out["items"]] == ["A", "C"] and out["route"] == "user" and out["truncated"] is False
    assert out["items"][0]["content"] == {"type": "draft", "id": "DI_A", "title": "Move the domain", "body": "why"}
    assert [i["item"] for i in access.github_board({"action": "items", "status": "Waiting"})["items"]] == ["C"]
    assert [i["item"] for i in access.github_board({"action": "items", "content_type": "draft", "search": "domain"})["items"]] == ["A"]


def test_board_resolve_lists_fields_with_options(gh):
    gh.add(*F.viewer_boards([F.board("me", 1)]))
    gh.add(r"fields\(first:50\)", {"node": {"fields": {"nodes": [
        {"__typename": "ProjectV2SingleSelectField", "id": "F1", "name": "Status", "dataType": "SINGLE_SELECT",
         "options": [{"id": "o1", "name": "Todo"}, {"id": "o2", "name": "Done"}]},
        {"__typename": "ProjectV2Field", "id": "F2", "name": "Target", "dataType": "DATE"}]}}})
    out = access.github_board({"action": "resolve"})
    assert out["board"]["tier"] == "own"
    assert out["fields"] == [{"name": "Status", "type": "SINGLE_SELECT", "options": ["Todo", "Done"]},
                             {"name": "Target", "type": "DATE"}]


def test_bad_arguments_are_refused_before_any_request(gh):
    for args, message in (({"action": "nope"}, "action must be one of"),
                          ({"action": "view"}, "issue is required"),
                          ({"action": "list", "repo": "me/app", "limit": 0}, "positive integer")):
        with pytest.raises(access.AccessError, match=message):
            access.github_issue(args)
    assert json.dumps(gh.calls) == "[]"
