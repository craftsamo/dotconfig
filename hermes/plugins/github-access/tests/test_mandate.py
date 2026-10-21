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


mandate = _load("hermes_github_access_mandate", ROOT / "mandate.py")
access = mandate.access
KEY = bytes(range(32))
BOARD = {"kind": "board", "id": "PVT_me_1", "name": "me/1 Roadmap", "tier": "own"}
APP = {"kind": "repo", "id": "R_app", "name": "me/app", "tier": "own"}
WEB = {"kind": "repo", "id": "R_web", "name": "team/web", "tier": "shared"}


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(mandate, "key", lambda home, create=False: KEY)
    return tmp_path


def terms(**over):
    import time
    t = {"boards": [{"id": "PVT_me_1", "name": "me/1 Roadmap", "tier": "own"}],
         "repos": [{"id": "R_app", "name": "me/app", "tier": "own"}, {"id": "R_web", "name": "team/web", "tier": "shared"}],
         "parent": None, "classes": ["create", "routine"], "days": 7, "purpose": "Run the release"}
    t.update(over)
    t.setdefault("expires", int(time.time()) + t["days"] * 86400)
    return t


def plan(*steps):
    return {"steps": list(steps)}


def step(op, cls, *targets, **extra):
    return {"change": {"op": op, **extra.pop("change", {})}, "class": cls, "targets": list(targets), **extra}


def test_a_mandate_is_made_listed_and_revoked(home):
    made = mandate.create(home, terms())
    assert mandate.ID.match(made["id"]) and made["classes"] == ["create", "routine"]
    assert [m["id"] for m in mandate.active(home)] == [made["id"]]
    assert mandate.revoke(home, made["id"]) == {"revoked": made["id"]}
    assert mandate.active(home) == []
    log = [json.loads(l)["event"] for l in (home / "github-access" / "mandates.jsonl").read_text().splitlines()]
    assert log == ["made", "revoked"]


def test_an_edited_mandate_or_head_puts_nothing_in_force(home):
    made = mandate.create(home, terms(classes=["routine"]))
    path = home / "github-access" / "mandates" / f"{made['id']}.json"
    body = json.loads(path.read_text())
    body["classes"] = ["create", "routine"]
    path.write_text(json.dumps(body))
    assert mandate.active(home) == []
    other = mandate.create(home, terms())
    head = home / "github-access" / "head.json"
    data = json.loads(head.read_text())
    data["active"].append("m00000000")
    head.write_text(json.dumps(data))
    assert mandate.active(home) == []


def test_deleting_the_history_does_not_change_what_is_in_force(home):
    made = mandate.create(home, terms())
    (home / "github-access" / "mandates.jsonl").unlink()
    assert [m["id"] for m in mandate.active(home)] == [made["id"]]


def test_a_mandate_ends_when_its_card_said_not_when_it_was_approved(home):
    shown = terms(days=1, expires=int(__import__("time").time()) + 600)
    made = mandate.create(home, shown)
    assert mandate.active(home, now=shown["expires"] - 1)
    assert mandate.active(home, now=shown["expires"]) == []
    with pytest.raises(access.AccessError, match="already passed"):
        mandate.create(home, terms(expires=1))
    assert made["id"]


def test_a_renamed_repository_is_not_the_one_approved(home):
    mandate.create(home, terms())
    impostor = {"kind": "repo", "id": "R_new", "name": "me/app", "tier": "own"}
    got, misses = mandate.covering(home, plan(step("issue_edit", "routine", impostor, repo={"repo": "me/app"}, number=2)))
    assert got is None and "me/app is outside the mandate" in misses[0]


def test_the_key_is_read_from_the_keychain_every_time(tmp_path, monkeypatch):
    cli = tmp_path / "secret"
    keyfile = tmp_path / "key"
    cli.write_text(f"#!/bin/sh\n[ \"$1\" = get ] && [ -f {keyfile} ] && cat {keyfile} && exit 0\n"
                   f"[ \"$1\" = show ] && [ -f {keyfile} ] && exit 0\nexit 1\n")
    cli.chmod(0o755)
    monkeypatch.setattr(mandate, "SECRET", cli)
    keyfile.write_text("ab" * 32)
    made = mandate.create(tmp_path, terms())
    assert [m["id"] for m in mandate.active(tmp_path)] == [made["id"]]
    keyfile.unlink()  # the key removed from the Keychain
    assert mandate.active(tmp_path) == []
    keyfile.write_text("cd" * 32)  # replaced
    assert mandate.active(tmp_path) == []


def test_without_a_readable_key_nothing_is_in_force(home, monkeypatch):
    mandate.create(home, terms())
    monkeypatch.setattr(mandate, "key", lambda home, create=False: None)
    assert mandate.active(home) == []
    assert mandate.covering(home, plan(step("item_set", "routine", BOARD)))[0] is None


def test_a_list_fits_only_inside_scope_classes_and_tier_caps(home):
    m = mandate.create(home, terms())
    routine_board = plan(step("item_set", "routine", BOARD))
    assert mandate.covering(home, routine_board)[0] == m["id"]
    create_own = plan(step("issue_create", "create", APP, repo={"repo": "me/app"}))
    assert mandate.covering(home, create_own)[0] == m["id"]
    create_shared = plan(step("issue_comment", "create", WEB, repo={"repo": "team/web"}, number=4))
    got, misses = mandate.covering(home, create_shared)
    assert got is None and "team/web is shared: a mandate never covers create changes there" in misses[0]
    routine_shared = plan(step("issue_edit", "routine", WEB, repo={"repo": "team/web"}, number=4))
    assert mandate.covering(home, routine_shared)[0] == m["id"]
    outside = plan(step("item_set", "routine", {"kind": "board", "id": "PVT_x", "name": "x/9 Other", "tier": "own"}))
    assert "outside the mandate" in mandate.covering(home, outside)[1][0]


def test_a_tier_that_grew_stricter_since_the_mandate_was_made_wins(home):
    mandate.create(home, terms())
    now_public = dict(APP, tier="shared")
    got, misses = mandate.covering(home, plan(step("issue_create", "create", now_public, repo={"repo": "me/app"})))
    assert got is None and "me/app is shared" in misses[0]
    gone = dict(APP, tier="other")
    got, misses = mandate.covering(home, plan(step("issue_edit", "routine", gone, repo={"repo": "me/app"}, number=2)))
    assert got is None and "me/app is other" in misses[0]


def test_a_routine_only_mandate_never_covers_a_create(home):
    mandate.create(home, terms(classes=["routine"]))
    got, misses = mandate.covering(home, plan(step("draft_add", "create", BOARD)))
    assert got is None and "covers routine" in misses[0]


def test_one_change_outside_makes_the_whole_list_ask(home):
    mandate.create(home, terms())
    mixed = plan(step("item_set", "routine", BOARD),
                 step("issue_comment", "create", {"kind": "repo", "id": "R_acme", "name": "acme/web", "tier": "other"},
                      repo={"repo": "acme/web"}, number=1))
    assert mandate.covering(home, mixed)[0] is None


def test_an_earlier_change_of_the_list_counts_inside_the_tree_only_as_a_direct_child(home, monkeypatch):
    m = mandate.create(home, terms(parent="me/app#3"))
    monkeypatch.setattr(access, "issue", lambda repo, number, comments=0: {"parent": None})
    child = step("issue_create", "create", APP, repo={"repo": "me/app"}, change={"parent": "#3"})
    sibling = step("issue_create", "create", APP, repo={"repo": "me/app"}, change={"parent": "#3", "blocked_by": ["$1"]})
    assert mandate.covering(home, plan(child, sibling))[0] == m["id"]
    grandchild = step("issue_create", "create", APP, repo={"repo": "me/app"}, change={"parent": "$1"})
    assert mandate.covering(home, plan(child, grandchild))[0] is None
    outside = step("issue_create", "create", APP, repo={"repo": "me/app"}, change={"title": "x"})
    after_outside = step("issue_create", "create", APP, repo={"repo": "me/app"}, change={"parent": "#3", "blocked_by": ["$1"]})
    assert mandate.covering(home, plan(outside, after_outside))[0] is None
    dangling = step("issue_create", "create", APP, repo={"repo": "me/app"}, change={"parent": "#3", "blocked_by": ["$4"]})
    assert mandate.covering(home, plan(child, dangling))[0] is None


def test_a_parent_bounds_issue_changes_to_its_direct_sub_issues(home, monkeypatch):
    m = mandate.create(home, terms(parent="me/app#3"))
    parents = {5: {"repo": "me/app", "number": 3}, 6: {"repo": "me/app", "number": 9}}
    monkeypatch.setattr(access, "issue", lambda repo, number, comments=0: {"parent": parents.get(number)})
    under = plan(step("issue_edit", "routine", APP, repo={"repo": "me/app"}, number=5))
    assert mandate.covering(home, under)[0] == m["id"]
    itself = plan(step("issue_edit", "routine", APP, repo={"repo": "me/app"}, number=3))
    assert mandate.covering(home, itself)[0] == m["id"]
    elsewhere = plan(step("issue_edit", "routine", APP, repo={"repo": "me/app"}, number=6))
    assert "outside issue me/app#3" in mandate.covering(home, elsewhere)[1][0]
    new_child = plan(step("issue_create", "create", APP, repo={"repo": "me/app"}, change={"parent": "#3"}))
    assert mandate.covering(home, new_child)[0] == m["id"]
    orphan = plan(step("issue_create", "create", APP, repo={"repo": "me/app"}))
    assert mandate.covering(home, orphan)[0] is None


@pytest.mark.parametrize("change,number,fits", [
    ({"parent": "#9"}, 5, False),               # moves a child under an unrelated issue
    ({"remove_parent": True}, 5, False),        # takes it out of the tree
    ({"parent": "#3"}, 6, False),               # pulls an outside issue in: it changes that issue
    ({"add_blocked_by": ["#7"]}, 5, False),     # #7 is outside: its blocking list changes
    ({"add_blocked_by": ["#4"]}, 5, True),      # a sibling inside the tree
    ({"add_sub_issues": ["#4"]}, 5, False),     # a child's own sub-issues are outside
    ({"add_sub_issues": ["#6"]}, 3, False),     # the parent taking an outside issue
    ({"remove_sub_issues": ["#4"]}, 3, True),   # the parent letting one of its own go
])
def test_a_parent_mandate_checks_every_issue_a_relation_touches(home, monkeypatch, change, number, fits):
    m = mandate.create(home, terms(parent="me/app#3"))
    parents = {4: {"repo": "me/app", "number": 3}, 5: {"repo": "me/app", "number": 3}, 6: None, 7: None,
               9: None, 3: None}
    monkeypatch.setattr(access, "issue", lambda repo, number, comments=0: {"parent": parents.get(number)})
    listing = plan(step("issue_relate", "create", APP, repo={"repo": "me/app"}, number=number, change=change))
    assert (mandate.covering(home, listing)[0] == m["id"]) is fits


def test_still_fits_rechecks_against_what_is_in_force_now(home):
    m = mandate.create(home, terms())
    listing = plan(step("item_set", "routine", BOARD))
    assert mandate.still_fits(home, m["id"], listing) is None
    mandate.revoke(home, m["id"])
    assert "no longer in force" in mandate.still_fits(home, m["id"], listing)


@pytest.fixture
def gh(monkeypatch):
    fake = F.FakeGh([F.viewer("me"), F.member({"team"}),
                     F.repos(F.repo("me/app"), F.repo("team/web", "Organization"), F.repo("me/ro", permission="READ")),
                     F.owner_types({"me": "User"}),
                     (r"user\(login:\$login\)\{projectV2\(number:\$n\)", {"user": {"projectV2": F.board("me", 1)}})])
    monkeypatch.setattr(access, "run_gh", fake)
    access.forget()
    return fake


def test_terms_read_their_targets_and_are_bounded(gh):
    t = mandate.terms({"boards": ["me/1"], "repos": ["me/app", "team/web"], "parent": "#3", "classes": ["routine"],
                       "days": 30, "purpose": "Ship  the\nrelease"})
    assert t.pop("expires") > 0
    assert t == {"boards": [{"id": "PVT_me_1", "name": "me/1 Roadmap", "tier": "own"}],
                 "repos": [{"id": "R_app", "name": "me/app", "tier": "own"}, {"id": "R_web", "name": "team/web", "tier": "shared"}],
                 "parent": "me/app#3", "classes": ["routine"], "days": 30, "purpose": "Ship the release"}
    again = mandate.terms({"boards": ["me/1"], "repos": ["me/app", "team/web"], "parent": "#3", "classes": ["routine"],
                           "days": 30, "purpose": "Ship the release"})
    assert mandate.same_terms(again, {**t, "expires": 1})
    for args, message in (({"repos": ["me/app"], "days": 31, "purpose": "x"}, "1 to 30"),
                          ({"repos": ["me/app"], "days": 3}, "purpose"),
                          ({"days": 3, "purpose": "x"}, "at least one board or repository"),
                          ({"repos": ["me/ro"], "days": 3, "purpose": "x"}, "no write permission"),
                          ({"repos": ["me/app"], "classes": ["structure"], "days": 3, "purpose": "x"}, "classes"),
                          ({"repos": ["me/app"], "parent": "acme/x#1", "days": 3, "purpose": "x"}, "not in repos")):
        with pytest.raises(access.AccessError, match=message):
            mandate.terms(args)


def test_a_real_plan_meets_a_real_mandate(gh, home):
    changes = _load("hermes_github_access_changes", ROOT / "changes.py")
    gh.add(*F.linked([]))
    gh.add(*F.viewer_boards([F.board("me", 1)]))
    gh.add(r"fields\(first:50\)", {"node": {"fields": {"nodes": [
        {"__typename": "ProjectV2SingleSelectField", "id": "F_S", "name": "Status", "dataType": "SINGLE_SELECT",
         "options": [{"id": "o", "name": "Done"}]}]}}})
    gh.add(r"ProjectV2Item\{id isArchived", {"node": {"id": "PVTI_1", "isArchived": False, "project": F.board("me", 1),
                                                     "content": {"__typename": "DraftIssue", "id": "DI", "title": "t", "body": ""}}})
    m = mandate.create(home, mandate.terms({"boards": ["me/1"], "repos": ["me/app", "team/web"], "classes": ["routine"],
                                            "days": 3, "purpose": "Track"}))
    routine = changes.plan({"changes": [{"op": "item_set", "item": "PVTI_1", "fields": {"Status": "Done"}}]})
    assert mandate.covering(home, routine)[0] == m["id"]
    shared_comment = changes.plan({"changes": [{"op": "issue_comment", "issue": "team/web#4", "body": "x"}]})
    assert mandate.covering(home, shared_comment)[0] is None


def test_the_mandate_card_names_every_bound(home):
    text = mandate.card(terms(parent="me/app#3"), lambda s, n: s)
    lines = text.splitlines()
    assert lines[:2] == ["GitHub · Mandate", "⚠️ Changes inside it skip the card"]
    assert "Board: me/1 Roadmap (own)" in lines and "Repository: team/web (shared)" in lines
    assert "Only issue me/app#3 and its direct sub-issues" in lines
    assert any(l.startswith("Until: ") and "(7 days)" in l for l in lines)
    fixed = terms(expires=1767225600)  # the card prints the end it will store
    assert __import__("time").strftime("%Y-%m-%d %H:%M", __import__("time").localtime(1767225600)) in \
        mandate.card(fixed, lambda s, n: s)
    assert "Purpose: Run the release" in lines
