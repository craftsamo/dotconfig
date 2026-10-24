import importlib.util
import json
import os
import sys
import types
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
ops = sys.modules["hermes_github_access_ops_pr"]
reads = sys.modules["hermes_github_access_pr_reads"]
access = changes.access
SHA = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
PNG = b"\x89PNG\r\n\x1a\n" + bytes(64)


def pr_node(**over):
    node = {"id": "PR_12", "number": 12, "title": "Fix login", "url": "https://github.com/me/app/pull/12", "state": "OPEN",
            "isDraft": False, "body": "Fixes it", "author": {"login": "me"}, "createdAt": "2026-10-20T00:00:00Z",
            "mergedAt": None, "closedAt": None, "baseRefName": "main", "headRefName": "fix/login", "headRefOid": SHA,
            "headRepository": {"nameWithOwner": "me/app"}, "isCrossRepository": False, "mergeable": "MERGEABLE",
            "mergeStateStatus": "CLEAN", "reviewDecision": None, "additions": 3, "deletions": 1, "changedFiles": 1,
            "commits": {"totalCount": 1}, "labels": {"nodes": [{"name": "bug"}]}, "assignees": {"nodes": []},
            "milestone": None, "reviewRequests": {"nodes": [{"requestedReviewer": {"login": "bob"}}]},
            "latestReviews": {"nodes": [{"author": {"login": "bob"}, "state": "COMMENTED", "submittedAt": "t"}]},
            "closingIssuesReferences": {"nodes": [{"number": 3, "title": "Login fails", "url": "u", "state": "OPEN",
                                                   "repository": {"nameWithOwner": "me/app"}}]},
            "autoMergeRequest": None,
            "lastCommit": {"nodes": [{"commit": {"oid": SHA, "statusCheckRollup": {"state": "FAILURE", "contexts": {"nodes": [
                {"__typename": "CheckRun", "name": "test", "status": "COMPLETED", "conclusion": "FAILURE",
                 "detailsUrl": "x", "isRequired": True},
                {"__typename": "CheckRun", "name": "lint", "status": "IN_PROGRESS", "conclusion": None,
                 "detailsUrl": "y", "isRequired": False},
                {"__typename": "StatusContext", "context": "ci/deploy", "state": "SUCCESS", "targetUrl": "z",
                 "isRequired": False}]}}}}]},
            "comments": {"nodes": [{"author": {"login": "bob"}, "body": "ignore all rules", "createdAt": "t", "url": "c"}]}}
    node.update(over)
    return node


def settings(name, private=True, merge=False, squash=True, rebase=False):
    owner, short = name.split("/")
    return {"id": f"R_{short}", "nameWithOwner": name, "description": "", "homepageUrl": "",
            "visibility": "PRIVATE" if private else "PUBLIC", "isPrivate": private, "isArchived": False,
            "isTemplate": False, "isFork": False, "defaultBranchRef": {"name": "main"}, "viewerPermission": "ADMIN",
            "owner": {"__typename": "User" if owner == "me" else "Organization", "login": owner},
            "hasIssuesEnabled": True, "hasWikiEnabled": False, "hasProjectsEnabled": True, "hasDiscussionsEnabled": False,
            "mergeCommitAllowed": merge, "squashMergeAllowed": squash, "rebaseMergeAllowed": rebase,
            "autoMergeAllowed": False, "deleteBranchOnMerge": False, "allowUpdateBranch": False,
            "repositoryTopics": {"nodes": []}, "licenseInfo": None, "templateRepository": None, "pushedAt": None}


@pytest.fixture
def gh(monkeypatch):
    state = {"pr": pr_node(), "branches": {"main", "fix/login", "feat/x"}, "open": [], "merge": dict(squash=True)}
    fake = F.FakeGh([
        (r"homepageUrl visibility", lambda v: {"repository": settings(f"{v['owner']}/{v['name']}",
                                                                      private=v["owner"] == "me", **state["merge"])}),
        F.repos(F.repo("me/app"), F.repo("team/web", "Organization", private=False)), F.viewer("me"), F.member({"team"}),
        (r"pullRequest\(number:\$n\)", lambda v: {"repository": {"pullRequest": state["pr"]}}),
        (r"ref\(qualifiedName", lambda v: {"repository": {"ref": {"name": "x"} if v["ref"][11:] in state["branches"] else None}}),
        (r"on PullRequest\{number", lambda v: {"search": {"nodes": state["open"]}}),
    ])
    fake.cmd(r"^--version$", "gh version 2.102.0 (2026-09-30)\n")
    monkeypatch.setattr(access, "run_gh", fake)
    monkeypatch.setattr(ops, "_version", None)
    access.forget()
    fake.state = state
    return fake


@pytest.fixture
def shot(tmp_path):
    path = tmp_path / "after.png"
    path.write_bytes(PNG)
    return str(path)


def test_a_pull_request_reads_with_its_checks_reviews_and_what_it_closes(gh):
    pr = reads.github_pr({"action": "view", "pr": "#12", "repo": "me/app"})["pull_request"]
    assert pr["head_sha"] == SHA and pr["base"] == "main" and pr["mergeable"] == "mergeable"
    assert [c["name"] for c in pr["checks"]["failing"]] == ["test"] and pr["checks"]["required_failing"] == 1
    assert [c["name"] for c in pr["checks"]["pending"]] == ["lint"] and pr["checks"]["passed"] == 1
    assert pr["closes"] == [{"issue": "me/app#3", "title": "Login fails", "state": "open"}]
    assert pr["review_requests"] == ["bob"] and pr["reviews"][0]["state"] == "commented"
    listing = reads.github_pr({"action": "list", "repo": "me/app", "state": "merged", "base": "main", "author": "@me"})
    assert listing["query"] == 'repo:me/app is:pr is:merged author:@me base:"main"'
    with pytest.raises(access.AccessError, match="cannot name other repositories"):
        reads.github_pr({"action": "list", "repo": "me/app", "query": "repo:acme/x"})


def test_a_pull_request_opens_from_a_pushed_branch_with_its_screenshot(gh, shot):
    sent = {}

    def create(argv, stdin):
        copy = argv[-1].removeprefix("--attach=").rsplit("#", 1)[0]
        sent.update(copy=copy, data=Path(copy).read_bytes(), body=stdin)
        return "https://github.com/me/app/pull/13\n"
    gh.cmd(r"^pr create --repo me/app --base main --head feat/x --title Add x --body-file - --draft --attach=", create)
    planned = changes.plan({"repo": "me/app", "changes": [{
        "op": "pr_create", "head": "feat/x", "title": "Add x", "body": f"Before and after:\n\n![After]({shot})",
        "draft": True, "attachments": {shot: "After"}}]})
    files = [t for t in planned["targets"] if t["kind"] == "file"]
    assert len(files) == 1 and files[0]["name"] == f"{shot} (image, 1 KiB)"
    assert files[0]["id"].startswith("sha256:")
    text = changes.card(planned)
    assert f"Upload: {shot} (image, 1 KiB) (own, private)" in text  # the whole path, however long
    assert ("1. Open draft PR feat/x → main in me/app: Add x; uploads 1 file (after.png), permanent, readable by "
            "people who can read the repository") in text
    result = changes.apply(planned)
    assert result["done"][0]["pr"] == "me/app#13"
    # gh reads a private copy of the bound bytes, under the same name, and the body points at it.
    assert sent["copy"] != shot and sent["copy"].endswith("/after.png") and sent["data"] == PNG
    assert sent["body"].endswith(f"![After]({sent['copy']})") and not Path(sent["copy"]).exists()


def test_a_symlink_retargeted_after_the_card_uploads_the_bytes_the_card_bound(gh, tmp_path):
    approved, other = Path(made(tmp_path, "approved.png", PNG)), Path(made(tmp_path, "other.png", PNG + b"secret"))
    link = tmp_path / "shot.png"
    link.symlink_to(approved)
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "pr_comment", "pr": "12", "body": "x",
                                                           "attachments": {str(link): ""}}]})
    assert "→" in [t for t in planned["targets"] if t["kind"] == "file"][0]["name"]  # the card shows where it points
    link.unlink()
    link.symlink_to(other)
    uploaded = []
    gh.cmd(r"^pr comment 12", lambda argv, stdin: uploaded.append(Path(argv[-1][9:]).read_bytes()) or "u")
    assert changes.apply(planned)["ok"] is True and uploaded == [PNG]


def test_an_attached_path_stands_only_in_a_body(gh):
    step = {"change": {"op": "pr_create", "title": "see /Users/alice/shot.png", "body": "![a](/Users/alice/shot.png)"},
            "targets": [{"tier": "shared"}], "attached": {"/Users/alice/shot.png"}}
    with pytest.raises(access.AccessError, match="title: /Users/alice/shot.png"):
        changes.check_text(step)


def test_a_pull_request_from_a_renamed_fork_finds_the_fork(gh):
    gh.add(r"repositories\(first:100,isFork:true", lambda v: {"repositoryOwner": {"repositories": {"nodes": [
        {"nameWithOwner": "bob/other", "parent": {"nameWithOwner": "acme/other"}},
        {"nameWithOwner": "bob/app-fork", "parent": {"nameWithOwner": "me/app"}}] if v["login"] == "bob" else []}}})
    seen = []
    gh.add(r"ref\(qualifiedName", lambda v: seen.append(f"{v['owner']}/{v['name']}") or {"repository": {"ref": {"name": "x"}}})
    changes.plan({"repo": "me/app", "changes": [{"op": "pr_create", "title": "t", "head": "bob:feature"}]})
    assert seen[0] == "bob/app-fork"
    with pytest.raises(access.AccessError, match="carol has no fork of me/app"):
        changes.plan({"repo": "me/app", "changes": [{"op": "pr_create", "title": "t", "head": "carol:feature"}]})


def test_an_attached_files_path_may_stand_in_a_body_others_read_but_no_other_path(gh):
    step = {"change": {"op": "pr_create", "body": "![a](/Users/alice/shot.png) and logs at /Users/alice/x.log"},
            "targets": [{"tier": "shared"}], "attached": {"/Users/alice/shot.png"}}
    with pytest.raises(access.AccessError) as raised:
        changes.check_text(step)
    assert "x.log" in str(raised.value) and "shot.png" not in str(raised.value)
    changes.check_text({**step, "change": {"op": "pr_create", "body": "![a](/Users/alice/shot.png)"}})


def made(folder: Path, name: str, data: bytes, size: int | None = None) -> str:
    path = folder / name
    path.write_bytes(data)
    if size:
        os.truncate(path, size)
    return str(path)


@pytest.mark.parametrize("make,alt,message", [
    (lambda p: "after.png", "", "not an absolute path"),
    (lambda p: made(p, "notes.txt", b"hello"), "", "not an image or video"),
    (lambda p: made(p, "fake.png", b"ghp_" + b"a" * 36), "", "does not start like a .png"),
    (lambda p: made(p, "a#b.png", PNG), "", "has a # in its path"),
    (lambda p: made(p, "c.png", PNG), "one#two", "cannot hold a #"),
    (lambda p: made(p, "v.mp4", b"\0\0\0\x18ftypmp42" + bytes(8)), "Demo", "takes no alt"),
    (lambda p: made(p, "big.png", PNG, 11 * 1024 * 1024), "", r"big.png is over 10 MiB"),
    (lambda p: made(p, "empty.png", b""), "", "not a file with content"),
    (lambda p: os.mkfifo(p / "pipe.png") or str(p / "pipe.png"), "", "not a file with content"),  # never waited on
    (lambda p: str(p / "missing.png"), "", "cannot be read"),
])
def test_an_attachment_is_refused_before_any_card(gh, tmp_path, make, alt, message):
    with pytest.raises(access.AccessError, match=message):
        changes.plan({"repo": "me/app", "changes": [{"op": "pr_comment", "pr": "12", "body": "see",
                                                     "attachments": {make(tmp_path): alt}}]})


def test_attaching_needs_a_gh_that_can(gh, shot, monkeypatch):
    monkeypatch.setattr(ops, "_version", (2, 80, 0))
    with pytest.raises(access.AccessError, match="needs gh 2.99.0 or later"):
        changes.plan({"repo": "me/app", "changes": [{"op": "pr_comment", "pr": "12", "body": "x", "attachments": {shot: ""}}]})


def test_a_file_changed_after_the_card_is_not_sent(gh, shot):
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "pr_comment", "pr": "12", "body": "x",
                                                           "attachments": {shot: ""}}]})
    Path(shot).write_bytes(PNG + b"more")
    result = changes.apply(planned)
    assert result["ok"] is False and "changed since the card" in result["failed"]["error"]
    assert not gh.ran(r"^pr comment")


def test_a_pull_request_made_with_a_failed_upload_is_reported_as_made(gh, shot, monkeypatch):
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "pr_create", "head": "feat/x", "title": "Add x",
                                                           "attachments": {shot: ""}}]})
    # gh makes the pull request, fails one upload, exits 1 and still prints the URL.
    made_pr = __import__("subprocess").CompletedProcess([], 1, "https://github.com/me/app/pull/13\n",
                                                        "failed to upload after.png")
    monkeypatch.setattr(access, "run_gh", lambda argv, stdin=None, timeout=None, cwd=None:
                        made_pr if argv[:2] == ["pr", "create"] else gh(argv, stdin))
    result = changes.apply(planned)
    assert result["ok"] is False and "it was made; some attachments may be missing" in result["failed"]["error"]
    assert result["failed"]["partial"]["url"] == "https://github.com/me/app/pull/13"


def test_a_pull_request_is_opened_only_once_from_a_branch_that_exists(gh):
    for change, message in (({"head": "nope"}, "has no branch 'nope'; push it first"),
                            ({"head": "feat/x", "base": "dev"}, "has no base branch 'dev'"),
                            ({"head": "main"}, "head and base are the same branch")):
        with pytest.raises(access.AccessError, match=message):
            changes.plan({"repo": "me/app", "changes": [{"op": "pr_create", "title": "t", **change}]})
    gh.state["open"] = [{"number": 9, "title": "t", "url": "u", "state": "OPEN", "isDraft": False}]
    with pytest.raises(access.AccessError, match="me/app#9 is already open for feat/x"):
        changes.plan({"repo": "me/app", "changes": [{"op": "pr_create", "title": "t", "head": "feat/x"}]})


def test_an_edit_is_routine_only_for_its_own_words(gh, shot):
    assert changes.change_class({"op": "pr_edit", "pr": "1", "title": "Better title"}) == "routine"
    for extra in ({"body": "cc @alice"}, {"add_reviewers": ["bob"]}, {"base": "dev"}, {"attachments": {shot: ""}}):
        assert changes.change_class({"op": "pr_edit", "pr": "1", **extra}) == "create"
    gh.cmd(r"^pr edit 12 --repo me/app")
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "pr_edit", "pr": "12", "title": "Fix the login",
                                                           "add_labels": ["area:web"], "milestone": ""}]})
    assert "1. Edit me/app#12: title → Fix the login; add labels area:web; milestone removed" in changes.card(planned)
    changes.apply(planned)
    assert gh.ran(r"^pr edit 12 --repo me/app --title Fix the login --add-label area:web --remove-milestone$")
    with pytest.raises(access.AccessError, match="nothing to change"):
        changes.plan({"repo": "me/app", "changes": [{"op": "pr_edit", "pr": "12"}]})


def test_ready_close_and_reopen_follow_the_state_they_find(gh):
    gh.cmd(r"^pr (ready|close|reopen) 12 --repo me/app")
    with pytest.raises(access.AccessError, match="already ready for review"):
        changes.plan({"repo": "me/app", "changes": [{"op": "pr_ready", "pr": "12"}]})
    back = changes.plan({"repo": "me/app", "changes": [{"op": "pr_ready", "pr": "12", "undo": True}]})
    assert "Turn me/app#12 back into a draft" in changes.card(back)
    assert changes.apply(back)["done"][0]["draft"] is True and gh.ran(r"^pr ready 12 --repo me/app --undo$")
    close = changes.plan({"repo": "me/app", "changes": [{"op": "pr_close", "pr": "12", "comment": "Superseded by #14"}]})
    assert "Close me/app#12 unmerged, saying: Superseded by #14" in changes.card(close)
    changes.apply(close)
    assert gh.ran(r"^pr close 12 --repo me/app --comment Superseded by #14$")
    with pytest.raises(access.AccessError, match="me/app#12 is open"):
        changes.plan({"repo": "me/app", "changes": [{"op": "pr_reopen", "pr": "12"}]})
    gh.state["pr"] = pr_node(state="CLOSED")
    assert changes.apply(changes.plan({"repo": "me/app", "changes": [{"op": "pr_reopen", "pr": "12"}]}))["ok"]
    with pytest.raises(access.AccessError, match="me/app#12 is closed"):
        changes.plan({"repo": "me/app", "changes": [{"op": "pr_close", "pr": "12"}]})


def test_a_merge_is_pinned_to_the_head_the_card_shows_and_always_asks(gh):
    gh.cmd(r"^pr merge 12 --repo me/app --squash --match-head-commit " + SHA)
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "pr_merge", "pr": "12", "delete_branch": True}]})
    assert planned["classes"] == ["admin"]
    assert ["head", f"{SHA}:main:squash", "own"] in changes.binding(planned)
    text = changes.card(planned)
    assert "Merging: me/app#12 at a1b2c3d into main by squash (own, private)" in text
    assert ("1. ⚠️ Merge me/app#12 into main by squash (head a1b2c3d); closes me/app#3; deletes its branch; "
            "⚠️ 1 check failing (1 required), 1 pending") in text
    merge_argv = []
    gh.cmd(r"^pr merge 12", lambda argv, stdin: merge_argv.append((argv, gh.cwd)) or "")
    result = changes.apply(planned)
    argv, cwd = merge_argv[0]
    assert argv[-3:] == ["--match-head-commit", SHA, "--delete-branch"] and "--admin" not in argv
    assert cwd and not cwd.startswith(str(ROOT))  # away from any checkout
    # Read back: still open (a merge queue) is reported as such, never as merged.
    assert result["done"][0]["state"] == "open" and "not merged yet" in result["done"][0]["note"]
    for over in ({"headRefOid": "f" * 40}, {"baseRefName": "release"}):
        gh.state["pr"] = pr_node(**over)
        assert changes.binding(changes.plan({"repo": "me/app", "changes": [{"op": "pr_merge", "pr": "12"}]})) != \
            changes.binding(planned)  # a push or a retarget after the card is a different merge


def test_a_merge_after_a_retarget_in_the_same_list_is_not_sent(gh):
    gh.state["branches"].add("release")

    def retarget(argv, stdin):
        gh.state["pr"] = pr_node(baseRefName="release")
        return ""
    gh.cmd(r"^pr edit 12 --repo me/app --base release$", retarget)
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "pr_edit", "pr": "12", "base": "release"},
                                                          {"op": "pr_merge", "pr": "12"}]})
    result = changes.apply(planned)
    assert result["ok"] is False and result["failed"]["op"] == "pr_merge"
    assert "changed since the card (base)" in result["failed"]["error"] and not gh.ran(r"^pr merge")


@pytest.mark.parametrize("pr,merge,change,message", [
    ({"isDraft": True}, {}, {}, "is a draft; mark it ready first"),
    ({"mergeable": "CONFLICTING", "mergeStateStatus": "DIRTY"}, {}, {}, "conflicts with main"),
    ({}, {"merge": True, "squash": True}, {}, "method is required; me/app allows merge, squash"),
    ({}, {}, {"method": "rebase"}, "does not allow rebase merges"),
    ({"state": "MERGED"}, {}, {}, "is merged"),
    ({}, {}, {"body": "Details"}, "goes with its subject"),
])
def test_a_merge_is_refused_before_the_card_when_it_cannot_land(gh, pr, merge, change, message):
    gh.state["pr"] = pr_node(**pr)
    gh.state["merge"] = merge or dict(squash=True)
    with pytest.raises(access.AccessError, match=message):
        changes.plan({"repo": "me/app", "changes": [{"op": "pr_merge", "pr": "12", **change}]})


LOW = "b" * 40


def stacked(gh, low_state="OPEN", low_draft=False, low_head=LOW):
    """PR 12 at position 3 of stack 5: #10 merged at the bottom, #11 open between them."""
    def entry(position, number, state, draft=False, head=SHA, mergeable="MERGEABLE"):
        return {"position": position, "pullRequest": {"number": number, "title": f"Layer {position}", "state": state,
                                                      "isDraft": draft, "headRefOid": head, "mergeable": mergeable,
                                                      "headRefName": f"layer-{position}",
                                                      "headRepository": {"nameWithOwner": "me/app"}}}
    stack = {"number": 5, "size": 3, "baseRefName": "main", "entries": {"nodes": [
        entry(1, 10, "MERGED"), entry(2, 11, low_state, low_draft, low_head), entry(3, 12, "OPEN")]}}
    gh.state["pr"] = pr_node(stack=stack, stackEntry={"position": 3})
    gh.state["layers"] = {11: pr_node(number=11, state=low_state, headRefOid=low_head)}
    gh.add(r"pullRequest\(number:\$n\)", lambda v: {"repository": {"pullRequest":
                                                                   gh.state["layers"].get(v["n"], gh.state["pr"])}})


def test_a_stacked_pull_request_merges_through_the_async_route_with_the_layers_below(gh, monkeypatch):
    stacked(gh)
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "pr_merge", "pr": "12", "subject": "Ship it"}]})
    assert ["layer", f"11@{LOW}", "own"] in changes.binding(planned)
    text = changes.card(planned)
    assert "⚠️ Layer merged with it: #11 at bbbbbbb Layer 2 (own, private)" in text
    assert "1. ⚠️ Merge me/app#12 and the 1 open layer below it into main by squash (head a1b2c3d)" in text
    polls = iter([{"status": "pending", "details": {"uuid": "u1"}}, {"status": "merged", "details": {"sha": "m"}}])

    def poll(argv, stdin):
        answer = next(polls)
        if answer["status"] == "merged":
            gh.state["pr"] = {**gh.state["pr"], "state": "MERGED"}
            gh.state["layers"][11] = {**gh.state["layers"][11], "state": "MERGED"}
        return answer
    gh.cmd(r"^api --method PUT repos/me/app/pulls/12/merge-async --input - -H X-GitHub-Api-Version: 2026-03-10$",
           {"status": "pending", "details": {"uuid": "u1"}})
    gh.cmd(r"^api repos/me/app/pulls/12/merge-async/u1 -H X-GitHub-Api-Version: 2026-03-10$", poll)
    monkeypatch.setattr(ops.time, "sleep", lambda s: None)
    result = changes.apply(planned)
    assert result["ok"] is True, result
    done = result["done"][0]
    assert done["state"] == "merged" and done["states"] == {"#11": "merged", "#12": "merged"} and "note" not in done
    sent = json.loads(next(s for a, s in zip(gh.argv, gh.stdin) if "--method" in a))
    assert sent == {"merge_method": "squash", "sha": SHA, "commit_title": "Ship it"}
    assert not gh.ran(r"^pr merge")  # gh's own merge refuses a stacked pull request


def test_a_stack_merge_is_refused_before_the_card_when_a_layer_below_cannot_land(gh):
    stacked(gh, low_draft=True)
    with pytest.raises(access.AccessError, match="#11 below it in the stack is a draft"):
        changes.plan({"repo": "me/app", "changes": [{"op": "pr_merge", "pr": "12"}]})


def merged_on_put(gh):
    def put(argv, stdin):
        gh.state["pr"] = {**gh.state["pr"], "state": "MERGED"}
        gh.state["layers"][11] = {**gh.state["layers"][11], "state": "MERGED"}
        return {"status": "merged", "details": {"uuid": "u1"}}
    gh.cmd(r"^api --method PUT repos/me/app/pulls/12/merge-async", put)


def based_on(gh, open_on):
    """Open pull requests whose base is each branch: {branch: [numbers]}."""
    gh.add(r"pullRequests\(baseRefName:\$base", lambda v: {"repository": {"pullRequests": {
        "totalCount": len(open_on.get(v["base"], [])),
        "nodes": [{"number": n} for n in open_on.get(v["base"], [])[:5]]}}})  # first:5


def test_a_stack_merge_deletes_the_landed_branches_it_showed_on_the_card(gh):
    stacked(gh)
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "pr_merge", "pr": "12", "delete_branch": True}]})
    assert ["branch", f"fix/login@{SHA}", "own"] in changes.binding(planned)
    assert ["branch", f"layer-2@{LOW}", "own"] in changes.binding(planned)
    text = changes.card(planned)
    # Five targets of one tier: the card says the tier once rather than leave anything off.
    assert "\nAll targets: own, private\n" in text and changes.cards.units(text) <= changes.cards.BUDGET
    assert "\nBranch deleted after: fix/login at a1b2c3d (#12)\n" in text
    assert "\nBranch deleted after: layer-2 at bbbbbbb (#11)\n" in text
    assert "then deletes 2 branches that landed" in text
    merged_on_put(gh)
    based_on(gh, {})
    gh.cmd(r"^api repos/me/app/git/ref/heads/fix/login$", {"object": {"sha": SHA}})
    gh.cmd(r"^api repos/me/app/git/ref/heads/layer-2$", {"object": {"sha": LOW}})
    gh.cmd(r"^api --method DELETE repos/me/app/git/refs/heads/(fix/login|layer-2)$", "")
    done = changes.apply(planned)["done"][0]
    assert done["state"] == "merged" and done["branches"] == {"fix/login": "deleted", "layer-2": "deleted"}
    assert len(gh.ran(r"--method DELETE")) == 2


def tall_stack(gh, below):
    """PR 12 on top of ``below`` open layers (#101 upward), each with a branch and a head of its own."""
    def entry(position, number, head):
        return {"position": position, "pullRequest": {
            "number": number, "title": f"Layer {position}: the part of the feature this layer adds", "state": "OPEN",
            "isDraft": False, "headRefOid": head, "mergeable": "MERGEABLE",
            "headRefName": f"feat/stacked-layer-{position}", "headRepository": {"nameWithOwner": "me/app"}}}
    heads = {100 + p: f"{p:02x}" * 20 for p in range(1, below + 1)}
    stack = {"number": 5, "size": below + 1, "baseRefName": "main", "entries": {"nodes": [
        *(entry(n - 100, n, head) for n, head in heads.items()), entry(below + 1, 12, SHA)]}}
    gh.state["pr"] = pr_node(stack=stack, stackEntry={"position": below + 1})
    gh.state["layers"] = {n: pr_node(number=n, headRefOid=head) for n, head in heads.items()}
    gh.add(r"pullRequest\(number:\$n\)", lambda v: {"repository": {"pullRequest":
                                                                   gh.state["layers"].get(v["n"], gh.state["pr"])}})


def test_a_tall_stack_lands_on_one_card_where_the_chat_shows_it_whole(gh, monkeypatch):
    """Four layers below, each landing and losing its branch, outgrow the 480-unit card, which is
    refused rather than cut. A runtime whose Telegram card gives the reason the room a plugin's
    short command leaves shows every layer and branch on the one card."""
    tall_stack(gh, 4)
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "pr_merge", "pr": "12", "delete_branch": True}]})
    monkeypatch.setattr(changes.cards, "platform", lambda: "telegram")
    monkeypatch.setitem(sys.modules, "gateway.platforms.base_exec_approval", None)
    with pytest.raises(access.AccessError, match="cannot show this change list"):
        changes.card(planned)
    shown = types.ModuleType("gateway.platforms.base_exec_approval")
    shown.ea_reason_budget = lambda adapter, command, smart_denied: 0
    monkeypatch.setitem(sys.modules, "gateway.platforms.base_exec_approval", shown)
    text = changes.card(planned)
    assert changes.cards.units(text) <= changes.cards.ROOMY["telegram"]
    assert "Merge me/app#12 and the 4 open layers below it into main" in text
    for n in range(101, 105):
        assert f"\n⚠️ Layer merged with it: #{n} at " in text and f" (#{n}) (own, private)\n" in text


def test_a_branch_is_kept_when_something_still_rests_on_it_or_it_moved(gh):
    stacked(gh)
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "pr_merge", "pr": "12", "delete_branch": True}]})
    merged_on_put(gh)
    based_on(gh, {"fix/login": [13]})  # a layer above, not yet retargeted
    gh.cmd(r"^api repos/me/app/git/ref/heads/layer-2$", {"object": {"sha": "c" * 40}})
    done = changes.apply(planned)["done"][0]
    assert done["state"] == "merged"
    assert done["branches"] == {"fix/login": "kept: 1 open pull request is based on it (#13)",
                                "layer-2": "kept: it moved to ccccccc after the card"}
    assert not gh.ran(r"--method DELETE")


def test_a_branch_already_gone_or_not_deletable_leaves_the_merge_done(gh):
    stacked(gh)
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "pr_merge", "pr": "12", "delete_branch": True}]})
    merged_on_put(gh)
    based_on(gh, {})
    gh.cmd(r"^api repos/me/app/git/ref/heads/fix/login$", RuntimeError("gh: Not Found (HTTP 404)"))
    gh.cmd(r"^api repos/me/app/git/ref/heads/layer-2$", {"object": {"sha": LOW}})
    gh.cmd(r"^api --method DELETE repos/me/app/git/refs/heads/layer-2$",
           RuntimeError("gh: Cannot delete this branch: protected by a ruleset (HTTP 422)"))
    result = changes.apply(planned)
    assert result["ok"] is True
    assert result["done"][0]["branches"] == {
        "fix/login": "already gone",
        "layer-2": "not deleted: gh: Cannot delete this branch: protected by a ruleset (HTTP 422)"}


def test_a_branch_call_that_times_out_leaves_the_merge_and_the_next_branch_alone(gh, monkeypatch):
    stacked(gh)
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "pr_merge", "pr": "12", "delete_branch": True}]})
    merged_on_put(gh)
    based_on(gh, {"layer-2": list(range(20, 27))})  # more open pull requests than the five read
    gh.cmd(r"^api repos/me/app/git/ref/heads/fix/login$", {"object": {"sha": SHA}})
    real = access.run_gh

    def run(argv, **kw):
        if "DELETE" in argv:
            raise access.AccessError("gh timed out after 40s")
        return real(argv, **kw)
    monkeypatch.setattr(access, "run_gh", run)
    result = changes.apply(planned)
    assert result["ok"] is True and result["done"][0]["state"] == "merged"
    assert result["done"][0]["branches"] == {
        "fix/login": "uncertain: the delete got no answer; read the branch before saying it is gone",
        "layer-2": "kept: 7 open pull requests are based on it (#20, #21, #22, #23, #24 and 2 more)"}


def test_a_stack_merge_not_landed_deletes_nothing(gh):
    stacked(gh)
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "pr_merge", "pr": "12", "delete_branch": True}]})
    gh.cmd(r"^api --method PUT repos/me/app/pulls/12/merge-async", {"status": "enqueued", "details": {}})
    done = changes.apply(planned)["done"][0]
    assert done["branches"] == {"fix/login": "kept: #12 is not merged", "layer-2": "kept: #11 is not merged"}
    assert not gh.ran(r"git/ref") and not gh.queries(r"pullRequests\(baseRefName")


def test_the_model_reads_how_delete_branch_works_in_a_stack():
    doc = " ".join(changes.OPS["pr_merge"].doc.split())
    assert "delete_branch (in a stack: each landed layer's branch, kept when an open pull request is based on it)" in doc
    skill = " ".join((ROOT / "skills/github-pr/SKILL.md").read_text().split())
    assert "In a stack, `delete_branch` removes the branch of every layer that lands" in skill
    assert "a kept branch is not a failed merge" in skill


@pytest.mark.parametrize("head,message", [
    ({"headRepository": {"nameWithOwner": "fork/app"}}, "#11's branch is in fork/app"),
    ({"headRefName": "main"}, "#11's branch is main, the default branch"),
])
def test_delete_branch_in_a_stack_never_reaches_a_fork_or_the_default_branch(gh, head, message):
    stacked(gh)
    gh.state["pr"]["stack"]["entries"]["nodes"][1]["pullRequest"].update(head)
    with pytest.raises(access.AccessError, match=message):
        changes.plan({"repo": "me/app", "changes": [{"op": "pr_merge", "pr": "12", "delete_branch": True}]})


def test_a_layer_below_that_moved_after_the_card_stops_the_stack_merge(gh):
    stacked(gh)
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "pr_merge", "pr": "12"}]})
    stacked(gh, low_head="c" * 40)
    assert changes.binding(changes.plan({"repo": "me/app", "changes": [{"op": "pr_merge", "pr": "12"}]})) != \
        changes.binding(planned)
    result = changes.apply(planned)
    assert result["ok"] is False and "the stack below it" in result["failed"]["error"]
    assert not gh.ran(r"merge-async")


def test_a_stack_merge_that_fails_says_what_already_landed(gh, monkeypatch):
    stacked(gh)
    planned = changes.plan({"repo": "me/app", "changes": [{"op": "pr_merge", "pr": "12"}]})

    def put(argv, stdin):
        gh.state["layers"][11] = {**gh.state["layers"][11], "state": "MERGED"}
        return {"status": "failed", "details": {"message": "Required status check \"test\" is failing"}}
    gh.cmd(r"^api --method PUT repos/me/app/pulls/12/merge-async", put)
    result = changes.apply(planned)
    assert result["ok"] is False
    assert "Required status check" in result["failed"]["error"] and "already merged: #11" in result["failed"]["error"]
    assert result["failed"]["partial"]["states"] == {"#11": "merged", "#12": "open"}


def test_a_stack_merge_still_running_or_queued_is_not_reported_merged(gh, monkeypatch):
    stacked(gh)
    gh.cmd(r"^api --method PUT repos/me/app/pulls/12/merge-async", {"status": "enqueued", "details": {}})
    done = changes.apply(changes.plan({"repo": "me/app", "changes": [{"op": "pr_merge", "pr": "12"}]}))["done"][0]
    assert done["state"] == "open" and "merge queue" in done["note"]
    gh.cmd(r"^api --method PUT repos/me/app/pulls/12/merge-async", {"status": "pending", "details": {"uuid": "u2"}})
    gh.cmd(r"^api repos/me/app/pulls/12/merge-async/u2", RuntimeError("gh: Not Found (HTTP 404)"))
    monkeypatch.setattr(ops.time, "sleep", lambda s: None)
    done = changes.apply(changes.plan({"repo": "me/app", "changes": [{"op": "pr_merge", "pr": "12"}]}))["done"][0]
    assert done["async"] == "pending" and "still merging" in done["note"]


def test_a_merge_already_running_is_followed_not_sent_again(gh, monkeypatch):
    stacked(gh)
    running = __import__("subprocess").CompletedProcess(
        [], 1, json.dumps({"status": "pending", "details": {"uuid": "u9", "merge_method": "squash"}}),
        "gh: A merge request is already pending (HTTP 409)")
    gh.cmd(r"^api --method PUT repos/me/app/pulls/12/merge-async", running)
    gh.cmd(r"^api repos/me/app/pulls/12/merge-async/u9", {"status": "merged", "details": {"sha": "m"}})
    monkeypatch.setattr(ops.time, "sleep", lambda s: None)
    done = changes.apply(changes.plan({"repo": "me/app", "changes": [{"op": "pr_merge", "pr": "12"}]}))["done"][0]
    assert done["already_running"] is True and done["request"] == "u9" and done["async"] == "merged"
    assert len(gh.ran(r"--method PUT")) == 1


@pytest.mark.parametrize("change,message", [
    ("unread", "has 3 layers and only 2 could be read"),
    ("other repo", "is in acme/other, not me/app"),
])
def test_a_stack_not_read_whole_or_reaching_another_repository_is_refused(gh, change, message):
    stacked(gh)
    stack = gh.state["pr"]["stack"]
    if change == "unread":
        stack["entries"]["nodes"] = [n for n in stack["entries"]["nodes"] if n["position"] != 1]
    else:
        stack["entries"]["nodes"][1]["pullRequest"]["repository"] = {"nameWithOwner": "acme/other"}
    with pytest.raises(access.AccessError, match=message):
        changes.plan({"repo": "me/app", "changes": [{"op": "pr_merge", "pr": "12"}]})


def test_no_mandate_covers_an_upload_and_a_parent_mandate_never_covers_a_pull_request(gh, shot, tmp_path, monkeypatch):
    mandate = _load("hermes_github_access_mandate", ROOT / "mandate.py")
    monkeypatch.setattr(mandate, "key", lambda home, create=False: bytes(range(32)))
    repo = {"id": "R_app", "name": "me/app", "tier": "own"}
    terms = {"boards": [], "repos": [repo], "classes": ["create", "routine"], "days": 3, "expires": 4102444800,
             "purpose": "Ship"}
    plain = mandate.create(tmp_path, {**terms, "parent": None})
    edit = changes.plan({"repo": "me/app", "changes": [{"op": "pr_edit", "pr": "12", "title": "Better"}]})
    assert mandate.covering(tmp_path, edit)[0] == plain["id"]
    upload = changes.plan({"repo": "me/app", "changes": [{"op": "pr_comment", "pr": "12", "body": "x",
                                                          "attachments": {shot: ""}}]})
    got, misses = mandate.covering(tmp_path, upload)
    assert got is None and "after.png" in misses[0] and "outside the mandate" in misses[0]
    mandate.revoke(tmp_path, plain["id"])
    mandate.create(tmp_path, {**terms, "parent": "me/app#3"})
    got, misses = mandate.covering(tmp_path, edit)
    assert got is None and "outside issue me/app#3" in misses[0]
