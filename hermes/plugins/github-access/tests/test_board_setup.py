import importlib.util
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
board = sys.modules["hermes_github_access_ops_board"]
access = changes.access

BOARD = F.board("me", 1)
STATUS = {"id": "F_S", "name": "Status", "dataType": "SINGLE_SELECT", "options": [
    {"id": "o1", "name": "Todo", "color": "GRAY", "description": ""},
    {"id": "o2", "name": "In Progress", "color": "YELLOW", "description": "doing"},
    {"id": "o3", "name": "Done", "color": "GREEN", "description": ""}]}
TITLE = {"id": "F_T", "name": "Title", "dataType": "TITLE"}
OWNERS = {"me": ("User", "U_me"), "team": ("Organization", "O_team"), "acme": ("Organization", "O_acme"),
          "bob": ("User", "U_bob")}


def owner(v):
    kind, node = OWNERS.get(v["login"], (None, None))
    return {"repositoryOwner": {"__typename": kind, "id": node, "login": v["login"]} if kind else None}


@pytest.fixture
def gh(monkeypatch):
    fake = F.FakeGh([F.viewer("me"), F.member({"team"}),
                     F.repos(F.repo("me/app"), F.repo("team/web", "Organization")),
                     F.owner_types({k: v[0] for k, v in OWNERS.items()}),
                     (r"repositoryOwner\(login:\$login\)\{__typename id login\}", owner),
                     F.owner_boards("user", []), F.owner_boards("organization", []),
                     F.viewer_boards([BOARD]), F.linked([]),
                     (r"fields\(first:50\)\{nodes\{__typename", {"node": {"fields": {"nodes": [
                         {"__typename": "ProjectV2SingleSelectField", **{k: STATUS[k] for k in ("id", "name", "dataType")},
                          "options": [{"id": o["id"], "name": o["name"]} for o in STATUS["options"]]},
                         {"__typename": "ProjectV2Field", **TITLE}]}}}),
                     (r"color description", {"node": {"fields": {"nodes": [STATUS, TITLE]}}}),
                     (r"views\(first:50\)", {"node": {"views": {"nodes": []}}}),
                     (r"node\(id:\$id\)\{\.\.\. on ProjectV2\{id number", {"node": F.board("me", 7)}),
                     (r"createProjectV2\(", {"createProjectV2": {"projectV2": {"id": "PVT_me_7"}}}),
                     (r"copyProjectV2\(", {"copyProjectV2": {"projectV2": {"id": "PVT_me_7"}}}),
                     (r"createProjectV2Field\(", {"createProjectV2Field": {"projectV2Field": {"id": "F_new"}}}),
                     (r"updateProjectV2Field\(", {"updateProjectV2Field": {"projectV2Field": {"id": "F_S"}}}),
                     (r"createProjectV2View\(", lambda v: {"createProjectV2View": {"projectV2View": {"id": "V_" + v["name"]}}}),
                     (r"updateProjectV2View\(", {"updateProjectV2View": {"projectV2View": {"id": "V"}}}),
                     (r"linkProjectV2ToRepository|unlinkProjectV2FromRepository", {"x": {"repository": {"id": "R"}}})])
    monkeypatch.setattr(access, "run_gh", fake)
    access.forget()
    return fake


def test_a_new_board_is_made_for_the_viewer_in_the_standard_shape(gh):
    planned = changes.plan({"changes": [{"op": "board_create"}]})
    assert planned["targets"] == [{"kind": "owner", "name": "me", "tier": "own", "id": "U_me"}]
    text = changes.card(planned)
    assert "New board for: me (own, private)" in text
    assert "1. Create board Roadmap for me (Status, Start, Target; Kanban, Backlog, Roadmap views)" in text
    result = changes.apply(planned)
    assert result["ok"] is True, result
    done = result["done"][0]
    assert done["board"] == "me/7" and done["created"] is True
    assert done["fields"] == [{"field": "Status", "created": False, "added": ["Cancelled"]},
                              {"field": "Start", "created": True, "added": []},
                              {"field": "Target", "created": True, "added": []}]
    assert [v["view"] for v in done["views"]] == ["Kanban", "Backlog", "Roadmap"]
    assert gh.queries(r"createProjectV2\(")[0]["variables"] == {"owner": "U_me", "title": "Roadmap"}
    # Existing options keep their ids, colors and descriptions, so no item's Status moves.
    options = gh.queries(r"updateProjectV2Field\(")[0]["variables"]["options"]
    assert options[:3] == [{"id": "o1", "name": "Todo", "color": "GRAY", "description": ""},
                           {"id": "o2", "name": "In Progress", "color": "YELLOW", "description": "doing"},
                           {"id": "o3", "name": "Done", "color": "GREEN", "description": ""}]
    assert options[3] == {"name": "Cancelled", "color": "RED", "description": ""}
    kanban = gh.queries(r"createProjectV2View\(")[0]["variables"]
    assert kanban["layout"] == "BOARD_LAYOUT" and kanban["fields"] == ["F_T"]  # only the columns the board has
    assert done["views"][0]["columns_missing"] == ["Assignees", "Repository", "Parent issue", "Target"]
    assert [q["variables"]["filter"] for q in gh.queries(r"updateProjectV2View\(")] == [
        "-status:Done -status:Cancelled", "-status:Done -status:Cancelled", "-status:Cancelled"]


def test_a_board_of_that_title_is_reused_not_made_again(gh):
    gh.add(*F.owner_boards("user", [BOARD]))
    planned = changes.plan({"changes": [{"op": "board_create", "owner": "@me", "views": False}]})
    assert [t["kind"] for t in planned["targets"]] == ["board"]
    assert "1. Bring board me/1 Roadmap to the standard shape (Status, Start, Target)" in changes.card(planned)
    result = changes.apply(planned)
    assert result["done"][0]["created"] is False and "views" not in result["done"][0]
    assert not gh.queries(r"createProjectV2\(") and not gh.queries(r"createProjectV2View\(")


def test_a_board_is_made_only_for_the_viewer_or_an_organization_of_theirs(gh):
    for who, message in (("bob", "for yourself"), ("acme", "not a member of acme"), ("ghost", "no user or organization")):
        with pytest.raises(access.AccessError, match=message):
            changes.plan({"changes": [{"op": "board_create", "owner": who}]})
    planned = changes.plan({"changes": [{"op": "board_create", "owner": "team", "title": "Plans"}]})
    assert planned["targets"][0] == {"kind": "owner", "name": "team", "tier": "shared", "id": "O_team"}
    gh.add(*F.owner_boards("organization", [F.board("team", 2, "Plans", "Organization"),
                                            F.board("team", 3, "Plans", "Organization")]))
    with pytest.raises(access.AccessError, match="2 open boards titled 'Plans'"):
        changes.plan({"changes": [{"op": "board_create", "owner": "team", "title": "Plans"}]})


def test_a_new_board_copies_a_template_and_links_a_repository(gh):
    gh.add(r"user\(login:\$login\)\{projectV2\(number:\$n\)", {"user": {"projectV2": F.board("me", 3, "Roadmap Template")}})
    planned = changes.plan({"changes": [{"op": "board_create", "template": "me/3", "link_repo": "me/app"}]})
    assert [t["kind"] for t in planned["targets"]] == ["owner", "template", "repo"]
    assert changes.binding(planned)[1] == ["template", "PVT_me_3", "own"]
    text = changes.card(planned)
    assert "Copied from: me/3 Roadmap Template (own, private)" in text
    assert "copied from me/3; linked to me/app)" in text
    result = changes.apply(planned)
    assert result["ok"] is True, result
    assert gh.queries(r"copyProjectV2\(")[0]["variables"] == {"project": "PVT_me_3", "owner": "U_me", "title": "Roadmap"}
    assert gh.queries(r"linkProjectV2ToRepository")[0]["variables"] == {"project": "PVT_me_7", "repo": "R_app"}
    assert result["done"][0]["linked"] == "me/app"


def test_a_field_is_made_or_given_the_options_it_lacks(gh):
    planned = changes.plan({"changes": [
        {"op": "field_ensure", "name": "Status", "data_type": "SINGLE_SELECT", "options": ["Waiting:ORANGE", "Done"]},
        {"op": "field_ensure", "name": "Priority", "data_type": "SINGLE_SELECT", "options": ["High:RED", "Low"]},
        {"op": "field_ensure", "name": "Status", "data_type": "SINGLE_SELECT", "options": ["Todo"]}]})
    text = changes.card(planned)
    assert "1. Field Status: add options Waiting" in text
    assert "2. Create field Priority (SINGLE_SELECT: High, Low)" in text
    assert "3. Field Status: already in place" in text
    result = changes.apply(planned)
    assert result["ok"] is True, result
    added = gh.queries(r"updateProjectV2Field\(")[0]["variables"]["options"]
    assert added[-1] == {"name": "Waiting", "color": "ORANGE", "description": ""} and len(added) == 4
    made = gh.queries(r"createProjectV2Field\(")[0]["variables"]
    assert made["options"] == [{"name": "High", "color": "RED", "description": ""},
                               {"name": "Low", "color": "GRAY", "description": ""}]


@pytest.mark.parametrize("change,message", [
    ({"name": "Priority", "data_type": "SINGLE_SELECT"}, "needs its options"),
    ({"name": "Labels", "data_type": "TEXT"}, "GitHub keeps for its own field"),
    ({"name": "Status", "data_type": "DATE"}, "is a SINGLE_SELECT field, not DATE"),
    ({"name": "Size", "data_type": "NUMBER", "options": ["S"]}, "options are for a SINGLE_SELECT"),
    ({"name": "Size", "data_type": "SINGLE_SELECT", "options": ["S", " s:red"]}, "named twice"),
    ({"name": "Size", "data_type": "SINGLE_SELECT", "options": [":RED"]}, "needs a name"),
    ({"name": "Size", "data_type": "COLOR"}, "data_type is one of"),
])
def test_a_field_change_is_checked_before_any_card(gh, change, message):
    with pytest.raises(access.AccessError, match=message):
        changes.plan({"changes": [{"op": "field_ensure", **change}]})
    assert not gh.queries(r"mutation")


def test_only_a_github_color_reads_as_an_option_suffix():
    assert board._options({"op": "field_ensure", "options": ["Done:green", "Release:V2", "Plan: B", "Waiting : ORANGE"]}) == [
        ("Done", "GREEN"), ("Release:V2", "GRAY"), ("Plan: B", "GRAY"), ("Waiting", "ORANGE")]


def test_a_reused_board_whose_field_has_another_type_is_refused_before_the_card(gh):
    gh.add(*F.owner_boards("user", [BOARD]))
    gh.add(r"fields\(first:50\)\{nodes\{__typename", {"node": {"fields": {"nodes": [
        {"__typename": "ProjectV2Field", "id": "F_X", "name": "Target", "dataType": "TEXT"}]}}})
    with pytest.raises(access.AccessError, match="'Target' on me/1 is a TEXT field, not DATE"):
        changes.plan({"changes": [{"op": "board_create"}]})


def test_a_board_create_that_fails_part_way_says_what_the_board_has(gh):
    gh.add(r"createProjectV2Field\(", RuntimeError("field limit reached"))
    result = changes.apply(changes.plan({"changes": [{"op": "board_create"}]}))
    assert result["ok"] is False
    partial = result["failed"]["partial"]
    assert partial["board_id"] == "PVT_me_7" and partial["board"] == "me/7" and partial["created"] is True
    assert partial["fields"] == [{"field": "Status", "created": False, "added": ["Cancelled"]}]


def test_a_view_is_made_once_with_its_columns_and_filter(gh):
    with pytest.raises(access.AccessError, match="a roadmap takes none"):
        changes.plan({"changes": [{"op": "view_ensure", "name": "Plan", "layout": "roadmap", "visible_fields": ["Title"]}]})
    with pytest.raises(access.AccessError, match="no field 'Effort'"):
        changes.plan({"changes": [{"op": "view_ensure", "name": "Mine", "layout": "table", "visible_fields": ["Effort"]}]})
    planned = changes.plan({"changes": [{"op": "view_ensure", "name": "Mine", "layout": "table", "filter": "assignee:@me",
                                         "visible_fields": ["Title", "Status"]}]})
    assert "1. Add view Mine (table, filter assignee:@me)" in changes.card(planned)
    assert changes.apply(planned)["ok"] is True
    assert gh.queries(r"createProjectV2View\(")[0]["variables"] == {"project": "PVT_me_1", "name": "Mine",
                                                                   "layout": "TABLE_LAYOUT", "fields": ["F_T", "F_S"]}
    gh.add(r"views\(first:50\)", {"node": {"views": {"nodes": [{"id": "V1", "name": "mine"}]}}})
    again = changes.plan({"changes": [{"op": "view_ensure", "name": "Mine", "layout": "table"}]})
    assert "1. View Mine: already in place" in changes.card(again)


def test_a_board_is_linked_and_unlinked_once(gh):
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "board_link"}]})
    assert [t["kind"] for t in planned["targets"]] == ["board", "repo"]
    assert "1. Link board me/1 Roadmap to me/app" in changes.card(planned)
    assert changes.apply(planned)["done"][0]["linked"] == "me/app"
    gh.add(*F.linked([BOARD]))
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "board_link"}]})
    assert changes.apply(planned)["done"][0]["linked"] == "me/app (already linked)"
    unlink = changes.plan({"repo": "me/app", "changes": [{"op": "board_link", "unlink": True}]})
    assert "1. Unlink board me/1 Roadmap from me/app" in changes.card(unlink)
    changes.apply(unlink)
    assert len(gh.queries(r"linkProjectV2ToRepository\(")) == 1 and gh.queries(r"unlinkProjectV2FromRepository")


def test_without_a_board_the_error_says_how_to_make_one(gh):
    gh.add(*F.viewer_boards([]))
    with pytest.raises(access.AccessError, match="board_create"):
        changes.plan({"repo": "me/app", "changes": [{"op": "draft_add", "title": "x"}]})
