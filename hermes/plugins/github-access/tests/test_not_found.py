"""GitHub answers a query naming something that does not exist with null at the path and an error of
type NOT_FOUND. A read says what is missing in its own words; a mutation still fails."""

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
pr_reads = sys.modules["hermes_github_access_pr_reads"]
repo_reads = sys.modules["hermes_github_access_repo_reads"]
board_ops = sys.modules["hermes_github_access_ops_board"]


@pytest.fixture
def gh(monkeypatch):
    fake = F.FakeGh([F.viewer("me")])
    monkeypatch.setattr(access, "run_gh", fake)
    access.forget()
    return fake


def test_a_missing_repository_issue_pull_request_or_board_is_said_to_be_missing(gh):
    gh.add(r"viewerPermission owner\{__typename login\}", F.NotFound("repository", name="me/gone"))
    with pytest.raises(access.AccessError, match="repository me/gone not found"):
        access.repo_context("me/gone")
    gh.add(r"homepageUrl visibility", F.NotFound("repository", name="me/gone"))
    with pytest.raises(access.AccessError, match="repository me/gone not found"):
        repo_reads.settings("me/gone")
    gh.add(r"issue\(number:\$n\)", F.NotFound("repository", "issue", what="Issue", name="me/app#9"))
    with pytest.raises(access.AccessError, match=r"issue me/app#9 not found"):
        access.issue("me/app", 9)
    gh.add(r"pullRequest\(number:\$n\)", F.NotFound("repository", "pullRequest", what="PullRequest", name="me/app#9"))
    with pytest.raises(access.AccessError, match=r"pull request me/app#9 not found"):
        pr_reads.pull_request("me/app", 9)
    gh.add(r"repositoryOwner\(login:\$login\)\{__typename\}", {"repositoryOwner": {"__typename": "User"}})
    gh.add(r"user\(login:\$login\)\{projectV2\(number:\$n\)", F.NotFound("user", "projectV2", what="ProjectV2", name="9"))
    with pytest.raises(access.AccessError, match="project me/9 not found"):
        access.board_by_number("me", 9)
    gh.add(r"node\(id:\$id\)\{\.\.\. on ProjectV2\{", F.NotFound("node", what="Node", name="PVT_gone"))
    with pytest.raises(access.AccessError, match="project PVT_gone not found"):
        access.board_context("PVT_gone")
    gh.add(r"node\(id:\$id\)\{\.\.\. on ProjectV2Item\{", F.NotFound("node", what="Node", name="PVTI_gone"))
    with pytest.raises(access.AccessError, match="board item PVTI_gone not found"):
        board_ops.read_item("PVTI_gone")


def test_a_mutation_naming_something_gone_still_fails(gh):
    gh.add(r"mutation", F.NotFound("addProjectV2ItemById", what="Node", name="PVT_gone"))
    with pytest.raises(access.AccessError, match="GitHub refused the request: Could not resolve to a Node"):
        access.graphql("mutation($p:ID!){addProjectV2ItemById(input:{projectId:$p,contentId:$p}){item{id}}}",
                       {"p": "PVT_gone"})


def test_only_an_answer_made_of_not_found_errors_passes_as_missing(gh):
    gh.add(r"query\{x\}", lambda v: F.NotFound("x"))
    assert access.lookup("query{x}") == {"x": None}
    with pytest.raises(access.AccessError, match="Could not resolve"):
        access.graphql("query{x}")
    gh.add(r"query\{y\}", RuntimeError("Something went wrong while executing your query"))
    with pytest.raises(access.AccessError, match="Something went wrong"):
        access.lookup("query{y}")
    # NOT_FOUND beside another kind of error is a refusal, not a missing thing.
    gh.add(r"query\{z\}", F.NotFound("z", also=[{"type": "FORBIDDEN", "message": "Resource not accessible"}]))
    with pytest.raises(access.AccessError, match="Could not resolve to a Repository.*Resource not accessible"):
        access.lookup("query{z}")
