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
PROTECT = {"id": 1, "name": "Protect main", "target": "branch", "enforcement": "active", "source_type": "Repository",
           "updated_at": "t1", "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
           "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}],
           "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}]}
MANAGED = {"id": 7, "name": "Managed protection: main", "target": "branch", "enforcement": "active",
           "source_type": "Repository", "updated_at": "t2",
           "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
           "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"},
                             {"actor_id": 42, "actor_type": "Integration", "bypass_mode": "always"}],
           "rules": [{"type": "pull_request", "parameters": {"required_approving_review_count": 1,
                                                             "dismiss_stale_reviews_on_push": True,
                                                             "require_code_owner_review": False,
                                                             "require_last_push_approval": False,
                                                             "required_review_thread_resolution": False}},
                     {"type": "non_fast_forward"}, {"type": "deletion"}, {"type": "required_signatures"}]}


@pytest.fixture
def gh(monkeypatch):
    state = {"rulesets": {1: PROTECT}}
    fake = F.FakeGh([F.repos(F.repo("me/app"), F.repo("me/ro", permission="WRITE"),
                             F.repo("team/web", "Organization", private=False)), F.viewer("me"), F.member({"team"}),
                     (r"ref\(qualifiedName:\$ref\)\{name target", lambda v: {"repository": {"ref": {
                         "name": "x", "target": {"oid": "a" * 40}} if v["ref"] in ("refs/heads/main", "refs/heads/dev")
                         else None}}),
                     (r"branchProtectionRules", {"repository": {"branchProtectionRules": {"nodes": [
                         {"pattern": "release/*", "requiresApprovingReviews": True, "requiredApprovingReviewCount": 2,
                          "requiresStatusChecks": False, "requiredStatusCheckContexts": ["ci"], "allowsForcePushes": False,
                          "allowsDeletions": False, "requiresLinearHistory": True, "isAdminEnforced": False}]}}})])
    listing = lambda argv, stdin: [{k: r[k] for k in ("id", "name", "source_type", "updated_at")}  # noqa: E731
                                   for r in state["rulesets"].values()]
    fake.cmd(r"^api repos/[^/]+/[^/]+/rulesets\?", listing)
    fake.cmd(r"^api repos/me/app/rulesets/(\d+)$", lambda argv, stdin: state["rulesets"][int(argv[1].rsplit("/", 1)[1])])
    fake.cmd(r"^api --method (POST|PUT) repos/me/app/rulesets", lambda argv, stdin: {"id": 9, **json.loads(stdin)})
    monkeypatch.setattr(access, "run_gh", fake)
    access.forget()
    fake.state = state
    return fake


def sent(gh) -> dict:
    return json.loads(next(s for a, s in zip(reversed(gh.argv), reversed(gh.stdin)) if a[:2] == ["api", "--method"]))


def test_the_rules_read_with_every_ruleset_and_classic_protection(gh):
    found = reads.github_repo({"action": "rules", "repo": "me/app"})
    assert found["rulesets"][0]["name"] == "Protect main" and found["rulesets"][0]["include"] == ["~DEFAULT_BRANCH"]
    assert found["rulesets"][0]["bypass"] == ["RepositoryRole:5:always"]
    assert [r["type"] for r in found["rulesets"][0]["rules"]] == ["deletion", "non_fast_forward"]
    assert found["classic"] == [{"pattern": "release/*", "approvals": 2, "checks": [], "force_push": False,
                                 "deletion": False, "linear_history": True, "admins_too": False}]


def test_a_new_managed_rule_protects_the_branch_and_never_touches_another_ruleset(gh):
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "branch_rule", "approvals": 1,
                                                           "required_checks": ["test", "test", "lint"]}]})
    assert planned["classes"] == ["admin"]
    assert ["ruleset", "new:", "own"] in changes.binding(planned)
    text = changes.card(planned)
    assert "Ruleset: Managed protection: default branch of me/app (new) (own, private)" in text
    assert ("1. ⚠️ Protect the default branch of me/app: admins may bypass, PR with 1 approval, no force push, "
            "no deletion, 2 check(s): test, lint") in text
    result = changes.apply(planned)
    assert result["done"][0]["id"] == 9 and gh.ran(r"^api --method POST repos/me/app/rulesets --input -$")
    body = sent(gh)
    assert body["name"] == "Managed protection: default branch" and body["enforcement"] == "active"
    assert body["conditions"]["ref_name"]["include"] == ["~DEFAULT_BRANCH"]
    assert [r["type"] for r in body["rules"]] == ["pull_request", "required_status_checks", "non_fast_forward", "deletion"]
    assert body["rules"][0]["parameters"]["required_approving_review_count"] == 1
    assert body["rules"][1]["parameters"]["required_status_checks"] == [{"context": "test"}, {"context": "lint"}]
    assert body["bypass_actors"] == [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]
    assert not gh.ran(r"rulesets/1$|--method PUT")  # "Protect main" is read, never written


def test_a_managed_rule_changes_only_what_is_named_and_keeps_the_rest(gh):
    gh.state["rulesets"][7] = MANAGED
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "branch_rule", "branch": "main", "approvals": 2,
                                                           "linear_history": True, "admin_bypass": False}]})
    assert ["ruleset", "7:t2", "own"] in changes.binding(planned)
    assert ("1. ⚠️ Change the protection of branch main of me/app: admins too, no bypass; approvals 1 → 2; "
            "+ linear history") in changes.card(planned)
    changes.apply(planned)
    assert gh.ran(r"^api --method PUT repos/me/app/rulesets/7 --input -$")
    body = sent(gh)
    by_type = {r["type"]: r for r in body["rules"]}
    assert set(by_type) == {"pull_request", "non_fast_forward", "deletion", "required_linear_history",
                            "required_signatures"}  # a rule added in GitHub's page stays
    assert by_type["pull_request"]["parameters"]["dismiss_stale_reviews_on_push"] is True
    assert by_type["pull_request"]["parameters"]["required_approving_review_count"] == 2
    assert body["bypass_actors"] == [{"actor_id": 42, "actor_type": "Integration", "bypass_mode": "always"}]
    off = changes.plan({"repo": "me/app", "changes": [{"op": "branch_rule", "branch": "main", "disable": True}]})
    assert "⚠️ turned off" in changes.card(off)
    changes.apply(off)
    assert sent(gh)["enforcement"] == "disabled"


def test_an_admin_bypass_left_out_of_a_change_keeps_its_mode(gh):
    gh.state["rulesets"][7] = {**MANAGED, "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole",
                                                             "bypass_mode": "pull_request"}]}
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "branch_rule", "branch": "main", "approvals": 2}]})
    assert "admins" not in changes.card(planned).splitlines()[-1]  # nothing about the bypass moves
    changes.apply(planned)
    assert sent(gh)["bypass_actors"] == [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "pull_request"}]


def test_a_new_rule_made_off_says_so_first_and_check_names_are_checked_text(gh):
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "branch_rule", "approvals": 1, "disable": True,
                                                           "required_checks": ["c" * 60, "d" * 60]}]})
    line = changes.card(planned).splitlines()[-1]
    assert line.startswith("1. ⚠️ Protect the default branch of me/app: ⚠️ NOT ENFORCED (off), admins may bypass, PR")
    with pytest.raises(access.AccessError, match="looks like a token"):
        changes.plan({"repo": "me/app", "changes": [{"op": "branch_rule", "required_checks": ["ghp_" + "A" * 36]}]})
    with pytest.raises(access.AccessError, match="others can read this target"):
        changes.plan({"repo": "team/web", "changes": [{"op": "branch_rule",
                                                       "required_checks": ["/Users/alice/private/check"]}]})


def test_a_rule_in_evaluate_mode_counts_as_off_and_is_turned_on(gh):
    gh.state["rulesets"][7] = {**MANAGED, "enforcement": "evaluate"}
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "branch_rule", "branch": "main", "disable": False}]})
    assert changes.card(planned).splitlines()[-1].endswith("of branch main of me/app: turned on")
    changes.apply(planned)
    assert sent(gh)["enforcement"] == "active"


def test_a_rule_changed_in_github_after_the_card_is_not_written(gh):
    gh.state["rulesets"][7] = MANAGED
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "branch_rule", "branch": "main", "approvals": 2}]})
    gh.state["rulesets"][7] = {**MANAGED, "updated_at": "t3"}
    result = changes.apply(planned)
    assert result["ok"] is False and "changed since the card" in result["failed"]["error"]
    assert not gh.ran(r"--method PUT")


@pytest.mark.parametrize("change,message", [
    ({}, "nothing to change"),
    ({"approvals": 11}, "approvals is 0 to 10"),
    ({"approvals": 1, "require_pr": False}, "approvals need require_pr"),
    ({"branch": "release/*", "approvals": 1}, "not a branch name"),
    ({"branch": "nope", "approvals": 1}, "has no branch 'nope'"),
    ({"repo": "me/ro", "approvals": 1}, "needs admin on me/ro"),
    ({"block_force_push": False, "block_deletion": False}, "leaves the ruleset no rule"),
    ({"approvals": "2"}, "approvals is a whole number"),
])
def test_a_branch_rule_is_checked_before_any_card(gh, change, message):
    with pytest.raises(access.AccessError, match=message):
        changes.plan({"repo": "me/app", "changes": [{"op": "branch_rule", **change}]})
    assert not gh.ran(r"--method")


def test_a_rule_already_as_asked_and_two_of_one_name_are_refused(gh):
    gh.state["rulesets"][7] = MANAGED
    with pytest.raises(access.AccessError, match="already says this"):
        changes.plan({"repo": "me/app", "changes": [{"op": "branch_rule", "branch": "main", "approvals": 1}]})
    gh.state["rulesets"][8] = {**MANAGED, "id": 8}
    with pytest.raises(access.AccessError, match="2 rulesets named 'Managed protection: main'"):
        changes.plan({"repo": "me/app", "changes": [{"op": "branch_rule", "branch": "main", "approvals": 2}]})
