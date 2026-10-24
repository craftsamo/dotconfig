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
access = changes.access

BOARD = F.board("me", 1)
FIELDS = {"node": {"fields": {"nodes": [
    {"__typename": "ProjectV2SingleSelectField", "id": "F_S", "name": "Status", "dataType": "SINGLE_SELECT",
     "options": [{"id": "o_todo", "name": "Todo"}, {"id": "o_wait", "name": "Waiting"}, {"id": "o_done", "name": "Done"}]},
    {"__typename": "ProjectV2Field", "id": "F_T", "name": "Target", "dataType": "DATE"},
    {"__typename": "ProjectV2Field", "id": "F_M", "name": "Milestone", "dataType": "MILESTONE"}]}}}


def draft_item(item_id="PVTI_1", title="Idea", body="", board=BOARD):
    return {"node": {"id": item_id, "isArchived": False, "project": board,
                     "content": {"__typename": "DraftIssue", "id": "DI_" + item_id, "title": title, "body": body}}}


@pytest.fixture
def gh(monkeypatch):
    fake = F.FakeGh([F.viewer("me"), F.member({"team"}),
                     F.repos(F.repo("me/app"), F.repo("team/web", "Organization"), F.repo("acme/web", "Organization", False),
                             F.repo("me/ro", permission="READ")),
                     F.viewer_boards([BOARD]), F.linked([]), (r"fields\(first:50\)", FIELDS)])
    monkeypatch.setattr(access, "run_gh", fake)
    access.forget()
    return fake


def test_every_graphql_document_closes_where_it_ends():
    # GitHub answers an unbalanced document with a parse error at its last column, which the fake
    # gh never sees: it matches a query by substring. So every document the plugin holds as a
    # constant is checked here: each `{` and `(` closed, and depth back to zero exactly at the end.
    modules = [m for name, m in sys.modules.items() if name.startswith("hermes_github_access_")]
    documents = [(f"{m.__name__}.{k}", v) for m in modules for k, v in vars(m).items()
                 if isinstance(v, str) and v.lstrip().startswith(("query", "mutation"))]
    assert len(documents) >= 20, documents
    pairs = {"{": "}", "(": ")"}
    for name, document in documents:
        stack = []
        for i, ch in enumerate(document):
            if ch in pairs:
                stack.append(ch)
            elif ch in pairs.values():
                assert stack and pairs[stack.pop()] == ch, f"{name}: unmatched {ch!r} at column {i + 1}"
        assert not stack, f"{name}: {len(stack)} unclosed {''.join(stack)!r} at the end"
        assert document.rstrip().endswith("}"), f"{name}: does not end on its selection set"


def test_every_change_is_checked_before_anything_is_read(gh):
    for args, message in (
            ({"changes": []}, "non-empty list"),
            ({"changes": [{"op": "nope"}]}, "op must be one of"),
            ({"changes": [{"op": "issue_close", "issue": "me/app#1", "reason": "fixed"}]}, "reason is one of"),
            ({"changes": [{"op": "issue_edit", "issue": "me/app#1"}]}, "nothing to change"),
            ({"changes": [{"op": "issue_edit", "issue": "me/app#1", "body": "a", "append_body": "b"}]}, "not both"),
            ({"changes": [{"op": "draft_add", "title": "x", "secret": "y"}]}, "unknown keys"),
            ({"changes": [{"op": "item_set", "item": "PVTI_1"}]}, "fields or clear"),
            ({"changes": [{"op": "issue_comment", "issue": "me/app#1"}]}, "body is required"),
            ({"changes": [{"op": "draft_add", "title": "x"}] * 51}, "at most 50")):
        with pytest.raises(access.AccessError, match=message):
            changes.plan(args)
    assert gh.calls == []


def test_a_plan_reads_each_target_fresh_and_takes_the_strictest_tier(gh):
    planned = changes.plan({"changes": [
        {"op": "draft_add", "title": "Capture", "fields": {"Status": "Todo"}},
        {"op": "issue_comment", "issue": "team/web#4", "body": "Done here"},
        {"op": "issue_edit", "issue": "me/app#2", "append_body": "- step"}]})
    assert {(t["kind"], t["name"], t["tier"]) for t in planned["targets"]} == {
        ("board", "me/1 Roadmap", "own"), ("repo", "team/web", "shared"), ("repo", "me/app", "own")}
    assert planned["tier"] == "shared" and planned["classes"] == ["create", "routine"]
    assert [s["class"] for s in planned["steps"]] == ["create", "create", "routine"]
    planned = changes.plan({"changes": [{"op": "issue_comment", "issue": "acme/web#1", "body": "hi"}]})
    assert planned["tier"] == "other"


def test_an_issue_edit_that_notifies_counts_as_create(gh):
    assert changes.change_class({"op": "issue_edit", "issue": "x", "append_body": "y"}) == "routine"
    assert changes.change_class({"op": "issue_edit", "issue": "x", "add_assignees": ["bob"]}) == "create"
    assert changes.change_class({"op": "issue_edit", "issue": "x", "milestone": ""}) == "create"


def test_a_plan_refuses_targets_the_viewer_cannot_write(gh):
    with pytest.raises(access.AccessError, match="no write permission on me/ro"):
        changes.plan({"changes": [{"op": "issue_comment", "issue": "me/ro#1", "body": "x"}]})
    gh.add(r"ProjectV2Item\{id isArchived", draft_item(board=F.board("acme", 2, owner_type="Organization", can_update=False)))
    with pytest.raises(access.AccessError, match="read-only for the viewer"):
        changes.plan({"changes": [{"op": "item_set", "item": "PVTI_1", "fields": {"Status": "Done"}}]})


def test_a_relation_to_another_repository_needs_write_there_too(gh):
    with pytest.raises(access.AccessError, match="no write permission on me/ro"):
        changes.plan({"changes": [{"op": "issue_relate", "issue": "me/app#1", "add_blocked_by": ["me/ro#3"]}]})


def test_the_card_names_targets_with_tiers_and_spells_out_hidden_characters(gh):
    planned = changes.plan({"changes": [
        {"op": "issue_comment", "issue": "acme/web#1", "body": "safe\u202etxt.exe"},
        {"op": "draft_add", "title": "Move the domain", "fields": {"Status": "Todo"}}]})
    text = changes.card(planned)
    assert text.splitlines()[:2] == ["GitHub · 2 changes", "⚠️ Lands on something someone else owns"]
    assert "Repository: acme/web (⚠️ someone else's)" in text and "Board: me/1 Roadmap (own, private)" in text
    assert "\n\n--- Changes ---\n1. " in text
    assert "1. Comment on acme/web#1: safe⟨U+202E⟩txt.exe" in text
    assert "2. Add draft Move the domain (Status=Todo)" in text


def test_the_card_counts_links_by_site_local_paths_and_branch_code_links(gh):
    planned = changes.plan({"changes": [
        {"op": "draft_add", "title": "Move DNS", "body": "See [sheet](https://docs.google.com/spreadsheets/d/x) "
                                                         "and https://www.github.com/me/app/blob/main/dns.md#L3 "
                                                         "and ~/notes/dns.txt"},
        {"op": "issue_comment", "issue": "me/app#2", "body": "[thread](https://discord.com/channels/1/2/3) and "
                                                             "https://github.com/me/app/blob/0a1b2c3d/dns.md#L3 "
                                                             "[sheet](https://docs.google.com/spreadsheets/d/y)"}]})
    text = changes.card(planned)
    assert "Links to: docs.google.com (1, 2), github.com (1, 2), discord.com (2)" in text
    assert "Local paths in the text: 1" in text
    assert "⚠️ Code links that follow a branch (their content can change): 1" in text
    plain = changes.card(changes.plan({"changes": [{"op": "draft_add", "title": "x"}]}))
    assert "Links to" not in plain and "Local paths" not in plain and "follow a branch" not in plain


def test_a_token_is_refused_on_every_tier(gh):
    for change in ({"op": "draft_add", "title": "x", "body": "use ghp_" + "a" * 36},
                   {"op": "issue_comment", "issue": "me/app#1", "body": "-----BEGIN OPENSSH PRIVATE KEY-----"}):
        with pytest.raises(access.AccessError, match="looks like a token or a private key"):
            changes.plan({"changes": [change]})


def test_own_targets_take_local_paths_as_they_are(gh):
    body = "Fails at /Users/alice/ghq/github.com/me/app/src/a.py and ~/Workspaces/Leads/.agent/x/log.txt"
    changes.plan({"changes": [{"op": "issue_comment", "issue": "me/app#1", "body": body}]})


@pytest.mark.parametrize("path,fix", [
    ("/Users/alice/Library/Logs/app.log", "`~/Library/Logs/app.log`"),
    ("/Users/alice/ghq/github.com/team/web/src/a.py", "`src/a.py` (the repository-relative path)"),
    ("~/Worktrees/web/fix-login/src/a.py", "`src/a.py` (the repository-relative path)"),
    ("~/Workspaces/Leads/.agent/20261021-x/log.txt", "a private working path"),
    ("file:///tmp/a.log", "link the file in its repository"),
])
def test_a_target_others_read_refuses_local_paths_and_says_how_to_write_them(gh, path, fix):
    with pytest.raises(access.AccessError, match="others can read this target") as raised:
        changes.plan({"changes": [{"op": "issue_comment", "issue": "team/web#4", "body": f"Crash at {path} :("}]})
    assert fix in str(raised.value)


@pytest.mark.parametrize("path,fix", [
    ("$HOME/Workspaces/Leads/.agent/run/log.txt", "a private working path"),
    ("${HOME}/Library/Logs/app.log", "`~/Library/Logs/app.log`"),
    ("~/.agent/run/log.txt", "a private working path"),
    (".agent/20261021-x/log.txt", "a private working path"),
    ("~/Workspaces/Leads/github/web/src/a.py", "a private working path"),
])
def test_other_spellings_of_private_paths_are_caught_and_private_wins_over_checkout(gh, path, fix):
    with pytest.raises(access.AccessError, match="others can read this target") as raised:
        changes.plan({"changes": [{"op": "issue_comment", "issue": "team/web#4", "body": f"see {path}"}]})
    assert fix in str(raised.value)


def test_every_text_a_change_writes_is_checked(gh):
    gh.add(r"ProjectV2Item\{id isArchived", draft_item(board=F.board("team", 5, "Plans", "Organization")))
    gh.add(r"fields\(first:50\)", {"node": {"fields": {"nodes": [
        {"__typename": "ProjectV2Field", "id": "F_N", "name": "Notes", "dataType": "TEXT"}]}}})
    for change, message in (
            ({"op": "item_set", "item": "PVTI_1", "fields": {"Notes": "ghp_" + "a" * 36}}, "fields.Notes holds"),
            ({"op": "item_set", "item": "PVTI_1", "fields": {"Notes": "/Users/alice/x.log"}}, "others can read"),
            ({"op": "issue_edit", "issue": "team/web#4", "milestone": "/Users/alice/m", "create_milestone": True},
             "others can read"),
            ({"op": "issue_create", "repo": "team/web", "title": "x", "labels": ["~/Workspaces/Leads"]},
             "others can read")):
        with pytest.raises(access.AccessError, match=message):
            changes.plan({"changes": [change]})


def test_promoting_a_draft_checks_the_words_it_publishes(gh):
    gh.add(r"ProjectV2Item\{id isArchived", draft_item("PVTI_1", "Idea", "crash at /Users/alice/ghq/github.com/team/web/a.py"))
    with pytest.raises(access.AccessError, match="draft body") as raised:
        changes.plan({"changes": [{"op": "draft_promote", "item": "PVTI_1", "repo": "team/web"}]})
    assert "`a.py` (the repository-relative path)" in str(raised.value)
    gh.add(r"ProjectV2Item\{id isArchived", draft_item("PVTI_1", "Idea", "clean"))
    with pytest.raises(access.AccessError, match="others can read"):
        changes.plan({"changes": [{"op": "draft_note", "item": "PVTI_1", "text": "log at /Users/alice/x.log"},
                                  {"op": "draft_promote", "item": "PVTI_1", "repo": "team/web"}]})
    changes.plan({"changes": [{"op": "draft_promote", "item": "PVTI_1", "repo": "me/app"}]})
    gh.add(r"ProjectV2Item\{id isArchived", draft_item("PVTI_1", "Idea", "debug at /Users/alice/x.log"))
    changes.plan({"changes": [{"op": "draft_edit", "item": "PVTI_1", "body": "The upload fails on a 5xx."},
                              {"op": "draft_promote", "item": "PVTI_1", "repo": "team/web"}]})  # cleaned first


def test_paths_others_may_read_pass(gh):
    body = ("Homebrew's /opt/homebrew/bin/gh and /usr/lib/x; config in ~/.config/gh/hosts.yml; "
            "see https://github.com/team/web/blob/0a1b2c3/src/a.py#L1-L4 and src/a.py")
    changes.plan({"changes": [{"op": "issue_comment", "issue": "team/web#4", "body": body}]})


def test_a_plan_of_issues_refers_to_the_ones_it_creates(gh):
    numbers = iter([20, 21, 22])
    gh.cmd(r"^issue create", lambda argv, stdin: f"https://github.com/me/app/issues/{next(numbers)}\n")
    gh.cmd(r"^issue edit \d+ --repo me/app --(parent|add-blocked-by) https://github.com/me/app/issues/\d+$")
    planned = changes.plan({"repo": "me/app", "changes": [
        {"op": "issue_create", "title": "Ship the release"},
        {"op": "issue_create", "title": "Phase 1", "parent": "$1"},
        {"op": "issue_create", "title": "Phase 2", "parent": "$1", "blocked_by": ["$2"]}]})
    text = changes.card(planned)
    assert "Phase 2 (parent change 1's issue; after change 2's issue)" in text
    result = changes.apply(planned)
    assert result["ok"] is True, result
    assert result["done"][2]["parent"] == "me/app#20" and result["done"][2]["blocked_by"] == ["me/app#21"]
    assert gh.ran(r"^issue edit 22 --repo me/app --add-blocked-by https://github.com/me/app/issues/21$")


@pytest.mark.parametrize("ref,message", [("$3", "not an earlier change"), ("$0", "not an earlier change"),
                                         ("$1", "creates no issue")])
def test_a_reference_to_an_earlier_change_must_name_one_that_creates_an_issue(gh, ref, message):
    with pytest.raises(access.AccessError, match=message):
        changes.plan({"repo": "me/app", "changes": [{"op": "draft_add", "title": "x"},
                                                     {"op": "issue_create", "title": "y", "parent": ref}]})


def test_a_long_list_is_cut_on_the_card_with_the_rest_counted(gh):
    planned = changes.plan({"changes": [{"op": "draft_add", "title": f"Item {i} " + "x" * 100} for i in range(30)]})
    text = changes.card(planned)
    assert changes.cards.units(text) <= changes.cards.BUDGET and "more changes)" in text.splitlines()[-1]
    shown = [line for line in text.splitlines() if line[:1].isdigit()]
    assert text.splitlines()[-1] == f"(+{30 - len(shown)} more changes)" and shown[0].startswith("1. Add draft")
    assert "\n✅ Only your own private repositories and boards\n" in text


@pytest.fixture
def admin_op():
    op = changes.Op("test_admin", "admin", "repo: a test", lambda s, p: s.update(repo=p.repo_of(s["change"])),
                    lambda s: f"Change {s['repo']['repo']}", lambda s, out: {"ran": True}, optional=("repo",))
    changes.register(op)
    yield op
    del changes.OPS[op.name]


def test_an_admin_change_is_marked_on_the_card(gh, admin_op):
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "draft_add", "title": "x"}, {"op": "test_admin"}]})
    assert planned["classes"] == ["admin", "create"]
    text = changes.card(planned)
    assert text.splitlines()[1] == "🚨 1 admin change, never covered by a mandate"
    assert "1. Add draft x" in text and "2. ⚠️ Change me/app" in text
    assert "admin change" not in changes.card(changes.plan({"changes": [{"op": "draft_add", "title": "x"}]}))
    noted = changes.card(planned, "m1: an admin change is never covered")
    assert "\nNot covered by a mandate: m1: an admin change is never covered\n\n--- Changes ---\n" in noted
    crowded = changes.plan({"repo": "me/app", "changes": [{"op": "draft_add", "title": f"Item {i} " + "x" * 100}
                                                          for i in range(20)] + [{"op": "test_admin"}]})
    text = changes.card(crowded)
    assert "\n21. ⚠️ Change me/app" in text and changes.cards.units(text) <= changes.cards.BUDGET
    assert text.endswith("more changes)") and "\n1. Add draft Item 0" in text   # the admin one is never the hidden one


def test_apply_creates_an_issue_and_settles_kind_parent_dependency_and_board(gh):
    gh.add(r"issueTypes", {"organization": {"issueTypes": {"nodes": []}}})
    gh.cmd(r"^api --paginate --slurp repos/me/app/milestones", [[{"title": "v1"}]])
    gh.cmd(r"^issue create --repo me/app --title Fix login --body-file - --label area:web --milestone v1$",
           "https://github.com/me/app/issues/12\n")
    gh.cmd(r"^issue view 12 --repo me/app --json labels", {"labels": [{"name": "type:feature"}]})
    gh.cmd(r"^label list --repo me/app --search type:bug", [])
    gh.cmd(r"^label create type:bug --repo me/app --color D73A4A")
    gh.cmd(r"^issue edit 12 --repo me/app (--add-label type:bug|--remove-label type:feature|--parent https://github.com/me/app/issues/3|--add-blocked-by https://github.com/me/app/issues/11)$")
    gh.cmd(r"^project item-add 1 --owner me --url https://github.com/me/app/issues/12", {"id": "PVTI_12"})
    gh.cmd(r"^project item-edit --id PVTI_12 --project-id PVT_me_1 --field-id F_S --single-select-option-id o_todo$")
    planned = changes.plan({"repo": "me/app", "changes": [{
        "op": "issue_create", "title": "Fix login", "body": "Spec", "kind": "bug", "labels": ["area:web"],
        "milestone": "v1", "parent": "3", "blocked_by": ["#11"], "board_fields": {"Status": "Todo"}}]})
    result = changes.apply(planned)
    assert result["ok"] is True, result
    assert result["done"][0] == {"op": "issue_create", "issue": "me/app#12", "url": "https://github.com/me/app/issues/12",
                                 "kind": "label type:bug", "parent": "me/app#3", "blocked_by": ["me/app#11"], "item": "PVTI_12",
                                 "fields": ["Status"]}
    assert gh.stdin[gh.argv.index(gh.ran(r"^issue create")[0])] == "Spec"
    assert gh.ran(r"--remove-label type:feature")


def test_apply_adds_a_draft_notes_it_and_moves_its_status(gh):
    gh.cmd(r"^project item-create 1 --owner me --title Capture --format json --body why$", {"id": "PVTI_9"})
    gh.cmd(r"^project item-edit --id PVTI_9 --project-id PVT_me_1 --field-id F_T --date 2026-11-01$")
    gh.add(r"ProjectV2Item\{id isArchived", draft_item("PVTI_1", "Idea", "first"))
    gh.cmd(r"^project item-edit --id DI_PVTI_1 --body first\n\n2026-10-21: asked\n$")
    gh.cmd(r"^project item-edit --id PVTI_1 --project-id PVT_me_1 --field-id F_S --single-select-option-id o_wait$")
    planned = changes.plan({"changes": [
        {"op": "draft_add", "title": "Capture", "body": "why", "fields": {"Target": "2026-11-01"}},
        {"op": "draft_note", "item": "PVTI_1", "text": "2026-10-21: asked"},
        {"op": "item_set", "item": "PVTI_1", "fields": {"Status": "Waiting"}}]})
    result = changes.apply(planned)
    assert result["ok"] is True, result
    assert [d["op"] for d in result["done"]] == ["draft_add", "draft_note", "item_set"]


def test_apply_stops_at_the_first_failure_and_names_what_was_not_done(gh):
    gh.add(r"ProjectV2Item\{id isArchived", draft_item())
    gh.cmd(r"^project item-edit --id PVTI_1 .*--field-id F_S", RuntimeError("HTTP 502"))
    planned = changes.plan({"changes": [
        {"op": "item_set", "item": "PVTI_1", "fields": {"Status": "Done"}},
        {"op": "item_set", "item": "PVTI_1", "fields": {"Target": "2026-11-01"}},
        {"op": "item_archive", "item": "PVTI_1"}]})
    result = changes.apply(planned)
    assert result["ok"] is False and result["done"] == []
    assert result["failed"]["index"] == 0 and "HTTP 502" in result["failed"]["error"]
    assert result["not_done"] == ["item_set", "item_archive"]


def test_board_fields_are_checked_before_anything_is_written(gh):
    gh.add(r"ProjectV2Item\{id isArchived", draft_item())
    for change, message in (({"op": "item_set", "item": "PVTI_1", "fields": {"Status": "Blocked"}}, "no option 'Blocked'"),
                            ({"op": "item_set", "item": "PVTI_1", "fields": {"Target": "next week"}}, "YYYY-MM-DD"),
                            ({"op": "item_set", "item": "PVTI_1", "fields": {"Milestone": "v1"}}, "built-in field"),
                            ({"op": "item_set", "item": "PVTI_1", "clear": ["Nope"]}, "no field 'Nope'"),
                            ({"op": "draft_add", "title": "x", "fields": {"Status": "Later"}}, "no option 'Later'")):
        with pytest.raises(access.AccessError, match=message):
            changes.plan({"changes": [change]})
    assert not [a for a in gh.argv if a[:2] != ["api", "graphql"]]


def test_a_failure_inside_a_change_reports_what_it_already_made(gh):
    gh.cmd(r"^issue create", "https://github.com/me/app/issues/12\n")
    gh.cmd(r"^issue edit 12 --repo me/app --parent", RuntimeError("could not resolve to an issue"))
    result = changes.apply(changes.plan({"repo": "me/app", "changes": [{"op": "issue_create", "title": "x", "parent": "3"}]}))
    assert result["ok"] is False
    assert result["failed"]["partial"] == {"issue": "me/app#12", "url": "https://github.com/me/app/issues/12"}
    assert result["failed"]["uncertain"] is False
    gh.cmd(r"^issue create", access.AccessError("gh did not answer within 40s"))
    result = changes.apply(changes.plan({"repo": "me/app", "changes": [{"op": "issue_create", "title": "x"}]}))
    assert result["failed"]["uncertain"] is True and result["failed"]["partial"] == {}


def test_two_notes_on_one_draft_both_land(gh):
    bodies = ["first"]
    gh.add(r"ProjectV2Item\{id isArchived", lambda v: draft_item("PVTI_1", "Idea", bodies[-1]))
    gh.cmd(r"^project item-edit --id DI_PVTI_1 --body", lambda argv, stdin: bodies.append(argv[-1]) or "")
    changes.apply(changes.plan({"changes": [{"op": "draft_note", "item": "PVTI_1", "text": "A"},
                                            {"op": "draft_note", "item": "PVTI_1", "text": "B"}]}))
    assert bodies[-1] == "first\n\nA\n\nB\n"


def test_removing_a_parent_in_another_repository_makes_it_a_target(gh):
    gh.add(r"stateReason body", {"repository": {"issue": {
        "id": "I", "number": 1, "title": "t", "url": "u", "state": "OPEN", "body": "", "repository": {"nameWithOwner": "me/app"},
        "parent": {"number": 2, "title": "p", "url": "u2", "state": "OPEN", "repository": {"nameWithOwner": "team/web"}},
        "subIssues": {"nodes": []}, "labels": {"nodes": []}}}})
    gh.add(r"blockedBy\(first:50\)", {"repository": {"issue": {"blockedBy": {"nodes": []}, "blocking": {"nodes": []}}}})
    planned = changes.plan({"changes": [{"op": "issue_relate", "issue": "me/app#1", "remove_parent": True}]})
    assert [(t["name"], t["tier"]) for t in planned["targets"]] == [("me/app", "own"), ("team/web", "shared")]
    assert planned["tier"] == "shared"


def test_board_fields_without_values_still_put_the_issue_on_the_board(gh):
    gh.cmd(r"^issue create", "https://github.com/me/app/issues/12\n")
    gh.cmd(r"^project item-add 1 --owner me --url https://github.com/me/app/issues/12", {"id": "PVTI_12"})
    result = changes.apply(changes.plan({"repo": "me/app", "changes": [{"op": "issue_create", "title": "x", "board_fields": {}}]}))
    assert result["ok"] is True and result["done"][0]["item"] == "PVTI_12"


def test_a_mention_makes_an_issue_edit_a_create(gh):
    assert changes.change_class({"op": "issue_edit", "issue": "x", "append_body": "ask @alice"}) == "create"
    assert changes.change_class({"op": "issue_edit", "issue": "x", "body": "mail a@b.co, `@x` in code"}) == "routine"


def test_each_step_names_its_own_targets_and_the_binding_carries_tiers(gh):
    planned = changes.plan({"changes": [{"op": "draft_add", "title": "a"},
                                        {"op": "issue_comment", "issue": "team/web#4", "body": "b"}]})
    assert [[t["name"] for t in s["targets"]] for s in planned["steps"]] == [["me/1 Roadmap"], ["team/web"]]
    assert changes.binding(planned) == [["board", "PVT_me_1", "own"], ["repo", "R_web", "shared"]]


def test_an_op_registers_once_with_a_known_class_and_declared_keys():
    run = lambda s, out: out  # noqa: E731
    for op, message in ((changes.Op("draft_add", "create", "", run, run, run), "registered twice"),
                        (changes.Op("x_op", "structure", "", run, run, run), "bad class"),
                        (changes.Op("x_op", "create", "", run, run, run, optional=("nope",)), "undeclared keys")):
        with pytest.raises(ValueError, match=message):
            changes.register(op)
    with pytest.raises(ValueError, match="declared twice"):
        changes.key("title", "list")
    assert "x_op" not in changes.OPS


def test_the_texts_a_change_writes_are_read_words_first_then_lists_then_maps():
    step = {"change": {"op": "issue_create", "board_fields": {"Notes": "n"}, "labels": ["l"], "milestone": "m",
                       "title": "t", "body": "b", "kind": "k"}, "carried": [("draft body", "c")]}
    assert [name for name, _ in changes._texts(step)] == ["title", "body", "kind", "milestone", "labels",
                                                           "board_fields.Notes", "draft body"]


def test_values_of_the_wrong_type_are_refused_before_anything_is_read(gh):
    for change, message in (({"op": "draft_add", "title": 3}, "title must be text"),
                            ({"op": "item_archive", "item": "PVTI_1", "restore": "yes"}, "true or false"),
                            ({"op": "issue_edit", "issue": "me/app#1", "add_labels": ["ok", ""]}, "list of text"),
                            ({"op": "item_set", "item": "PVTI_1", "fields": {"Status": 1}}, "maps field names")):
        with pytest.raises(access.AccessError, match=message):
            changes.plan({"changes": [change]})
    assert gh.calls == []


def test_a_relation_already_in_place_is_not_sent_again(gh):
    gh.add(r"stateReason body", {"repository": {"issue": {
        "id": "I", "number": 5, "title": "t", "url": "u", "state": "OPEN", "body": "", "repository": {"nameWithOwner": "me/app"},
        "parent": {"number": 3, "title": "p", "url": "u3", "state": "OPEN", "repository": {"nameWithOwner": "me/app"}},
        "subIssues": {"nodes": []}, "labels": {"nodes": []}}}})
    gh.add(r"blockedBy\(first:50\)", {"repository": {"issue": {"blockedBy": {"nodes": [
        {"number": 2, "title": "b", "url": "u2", "state": "OPEN", "repository": {"nameWithOwner": "me/app"}}]},
        "blocking": {"nodes": []}}}})
    gh.cmd(r"^issue edit 5 --repo me/app --add-blocked-by https://github.com/me/app/issues/4$")
    result = changes.apply(changes.plan({"repo": "me/app", "changes": [
        {"op": "issue_relate", "issue": "5", "parent": "3", "add_blocked_by": ["2", "4"]}]}))
    assert result["ok"] is True and result["done"][0]["done"] == ["add blocked by me/app#4"]
    assert not gh.ran(r"--parent")
