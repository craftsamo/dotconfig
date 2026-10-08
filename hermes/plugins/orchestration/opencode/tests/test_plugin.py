import importlib.util
import json
from pathlib import Path
import re
import subprocess
import urllib.parse

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plugin = _module("opencode_test", ROOT / "__init__.py")
fakes = _module("opencode_fake_service", ROOT / "tests/fake_service.py")
api, config, policy, models, turn = plugin.api, plugin.config, plugin.policy, plugin.models, plugin.turn
PERSON_DENIES = fakes.PERSON_DENIES
REAL_WAIT_LIMIT = turn.wait_limit
MESSAGE = "Inspect only. ' ; $(not a shell)\nsecond line"
CONFIG = "opencode:\n  enabled: true\n  wait_timeout: 8\n  allowed_providers: [anthropic, openai]\n"


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    home = tmp_path / "profiles/assistant"
    home.mkdir(parents=True)
    (home / "config.yaml").write_text(CONFIG)
    directory = tmp_path / "work tree"
    directory.mkdir()
    subprocess.run(["git", "init", "-b", "topic", str(directory)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(directory), "-c", "user.name=t", "-c", "user.email=t@t", "commit",
                    "--allow-empty", "-m", "init"], check=True, capture_output=True)
    fake = fakes.Fake(directory.resolve(), api)
    monkeypatch.setattr(api, "call", fake)
    owner = {"profile": "assistant", "session_id": "client-a", "routing_digest": "a"}
    monkeypatch.setattr(plugin, "_scope", lambda: (home, owner, False))
    monkeypatch.setattr(turn, "POLL", 0.01)
    monkeypatch.setattr(turn, "NO_OUTCOME_GRACE", 0.2)
    monkeypatch.setattr(turn, "UNREACHABLE_GRACE", 0.2)
    monkeypatch.setattr(turn, "RETRY_POLL", 0)
    monkeypatch.setattr(models, "CATALOG_RETRY", 0)
    # Tests that hold a run open must not wait the configured seconds for it.
    monkeypatch.setattr(turn, "wait_limit", lambda home_arg, settings, requested=None: float(requested or 0.3))
    return home, directory.resolve(), owner, fake


def run(role="plan", directory=None, **kwargs):
    args = dict(message=MESSAGE)
    if directory:
        args["directory"] = str(directory)
    args.update(kwargs)
    return json.loads(plugin.opencode_run(role, args))


def session(action, sid=None, **kwargs):
    args = dict(action=action, **kwargs)
    if sid:
        args["session_id"] = sid
    return json.loads(plugin.opencode_session(args))


def request(action, sid, **kwargs):
    return json.loads(plugin.opencode_request(dict(action=action, session_id=sid, **kwargs)))


def scripted(fake, *steps):
    """Script the next session the service creates."""
    real = fake._route

    def route(method, parts, query, data):
        out = real(method, parts, query, data)
        if parts == ["session"] and method == "post":
            fake.scripts[out["data"]["id"]] = list(steps)
        return out
    fake._route = route


def configure(home, text):
    (home / "config.yaml").write_text(CONFIG + text)


# ---------------------------------------------------------------- a turn

def test_plan_run_creates_a_bound_session_and_completes(fixture):
    home, directory, owner, fake = fixture
    out = run("plan", directory)
    assert out["status"] == "completed" and out["result"] == "RESULT_OK", out
    assert out["role"] == "plan" and out["branch"] == "topic" and out["outcome"] == "succeeded"
    assert out["engine"] == "anthropic/claude-opus-5-5#high"
    assert out["changes"] == [{"file": "a.py", "status": "modified", "additions": 3, "deletions": 1}]
    sid = out["session_id"]
    created = fake.sessions[sid]
    assert created["agent"] == "plan"
    assert created["metadata"]["hermes"] == {"v": 2, "profile": "assistant", "owner": owner, "role": "plan",
                                             "branch": "topic"}
    assert {"action": "edit", "resource": "*", "effect": "deny"} in created["permissions"]
    assert fake.entries[sid]["hermes.note"].startswith("A Hermes agent drives this session")
    assert fake.prompts == [(sid, MESSAGE)], "the message reaches OpenCode literally"
    assert not (home / "opencode-sessions").exists(), "no run record is kept"


def test_question_tool_is_not_denied_and_no_contract_is_injected(fixture):
    _, directory, _, fake = fixture
    sid = run("plan", directory)["session_id"]
    assert policy.decide(fake.sessions[sid]["permissions"], "question", "*") == "ask"
    assert "Q<n>" not in fake.entries[sid]["hermes.note"]


def test_plan_then_build_switches_agent_model_and_ruleset_on_one_session(fixture):
    home, directory, _, fake = fixture
    configure(home, "  roles:\n    plan: {agent: plan, policy: read-only}\n"
                    "    build: {agent: build, policy: write, model: 'openai/gpt-6.1-sol#medium'}\n")
    first = run("plan", directory)
    sid = first["session_id"]
    assert "approval" in run("build", session_id=sid, approval=" ")["error"]
    built = run("build", session_id=sid, approval="Client: implement the plan", issue_approval="Client: file it")
    assert built["status"] == "completed" and built["session_id"] == sid and built["role"] == "build", built
    now = fake.sessions[sid]
    assert now["agent"] == "build"
    assert now["model"] == {"providerID": "openai", "id": "gpt-6.1-sol", "variant": "medium"}
    assert {"action": "edit", "resource": "*", "effect": "deny"} not in now["permissions"]
    assert policy.decide(now["permissions"], "shell", "git push origin topic") == "ask"
    assert {"action": "shell", "resource": "gh issue comment *", "effect": "ask"} not in now["permissions"], \
        "an Issue grant lifts the Issue-write asks"
    assert "Client implementation scope: Client: implement the plan" in fake.prompts[-1][1]
    assert "Issue management: Client: file it" in fake.prompts[-1][1]
    assert now["metadata"]["hermes"]["role"] == "build"
    assert fake.prompts[0][1] == MESSAGE, "a read-only turn adds no scope text"


def test_output_dir_opens_one_draft_directory_and_outlives_the_turn(fixture, tmp_path):
    home, directory, _, fake = fixture
    job = tmp_path / "Workspaces/Projects/Acme/.agent/20261008-ui/ui-check"
    job.mkdir(parents=True)
    first = run("plan", directory, output_dir=str(job))
    sid = first["session_id"]
    assert first["status"] == "completed", first
    rules = fake.sessions[sid]["permissions"]
    assert policy.decide(rules, "external_directory", str(job.resolve())) == "allow"
    assert policy.decide(rules, "external_directory", f"{job.resolve()}/shots/a.png") == "allow"
    assert policy.decide(rules, "external_directory", str(job.parent.resolve()) + "/other") == "ask"
    assert fake.sessions[sid]["metadata"]["hermes"]["output_dir"] == str(job.resolve())
    assert f"Output directory (outside the repository) for reports" in fake.prompts[-1][1]
    configure(home, "  roles:\n    plan: {agent: plan, policy: read-only}\n    build: {agent: build, policy: write}\n")
    built = run("build", session_id=sid, approval="Client: implement the plan")
    assert built["status"] == "completed", built
    assert policy.decide(fake.sessions[sid]["permissions"], "external_directory", f"{job.resolve()}/x") == "allow", \
        "a continuation keeps the session's output directory"
    for kind in ("read-only", "write"):
        rules = policy.rules(kind, None, {"main"}, output="/w/.agent/job")
        assert policy.decide(rules, "edit", "/w/.agent/job/report.md") == "allow", kind
        assert policy.decide(rules, "edit", "/w/.agent/job/x.env") == "deny", kind
        assert policy.decide(rules, "edit", "/w/.agent/other/report.md") == ("deny" if kind == "read-only"
                                                                              else "allow"), kind
    fake.sessions[sid]["metadata"]["hermes"]["output_dir"] = "/Users"
    assert "no longer valid" in run("plan", session_id=sid)["error"], "stored metadata is checked again"
    fake.sessions[sid]["metadata"]["hermes"]["output_dir"] = str(job.resolve())
    rules = policy.rules("write", None, {"main"}, person_denies=PERSON_DENIES, output="/secret/job")
    assert policy.decide(rules, "external_directory", "/secret/job/a") == "deny", "the person's denies still win"
    for bad, message in ((str(tmp_path), "draft directory"), (str(job / "missing"), "existing directory"),
                         ("relative/.agent/x", "absolute"), (str(job) + "/*", "wildcards"),
                         (str(job.parent.parent), "below .agent")):
        assert message in run("plan", directory, output_dir=bad)["error"], bad
    inside = directory / ".agent/job"
    inside.mkdir(parents=True)
    assert "outside the worktree" in run("plan", directory, output_dir=str(inside))["error"]


def test_write_run_needs_approval_and_a_task_branch(fixture):
    _, directory, _, fake = fixture
    assert "approval" in run("build", directory)["error"]
    subprocess.run(["git", "-C", str(directory), "branch", "-m", "main"], check=True, capture_output=True)
    assert "default branch" in run("build", directory, approval="Client: go")["error"]
    assert run("plan", directory)["status"] == "completed", "read-only runs may look at the default branch"
    assert len(fake.prompts) == 1, "the refused write runs sent nothing"


def test_arguments_are_checked_before_anything_runs(fixture):
    _, directory, _, fake = fixture
    assert "Unexpected" in run("plan", directory, approval="x")["error"], "approvals belong to write roles"
    assert "Unexpected" in run("plan", directory, agent="build")["error"]
    assert "absolute" in run("plan", "relative/dir")["error"]
    assert "absolute" in run("plan")["error"]
    assert "nonempty message" in run("plan", directory, message="  ")["error"]
    assert "timeout" in run("plan", directory, timeout=0)["error"]
    assert "Unknown role" in json.loads(plugin.opencode_run("nope", {"message": "x"}))["error"]
    assert "fork requires" in run("plan", directory, fork=True)["error"]
    assert not fake.sessions


def test_resume_is_bound_to_worktree_branch_and_caller(fixture, monkeypatch, tmp_path):
    home, directory, owner, fake = fixture
    sid = run("plan", directory)["session_id"]
    other = tmp_path / "other"
    other.mkdir()
    subprocess.run(["git", "init", "-b", "topic", str(other)], check=True, capture_output=True)
    assert "another worktree" in run("plan", other, session_id=sid)["error"]
    subprocess.run(["git", "-C", str(directory), "checkout", "-b", "moved"], check=True, capture_output=True)
    assert "branch changed" in run("plan", session_id=sid)["error"]
    subprocess.run(["git", "-C", str(directory), "checkout", "topic"], check=True, capture_output=True)
    assert run("plan", session_id=sid)["session_id"] == sid
    monkeypatch.setattr(plugin, "_scope", lambda: (home, {**owner, "session_id": "client-b"}, False))
    for call in (lambda: session("status", sid), lambda: session("wait", sid), lambda: session("diff", sid),
                 lambda: request("list", sid), lambda: run("plan", session_id=sid)):
        assert "not bound" in call()["error"]
    assert session("list")["sessions"] == []


def test_fork_runs_on_a_copy(fixture):
    _, directory, owner, fake = fixture
    sid = run("plan", directory)["session_id"]
    forked = run("plan", session_id=sid, fork=True)
    assert forked["session_id"] != sid and forked["status"] == "completed"
    assert fake.sessions[forked["session_id"]]["metadata"]["hermes"]["owner"] == owner
    assert len(fake.prompts) == 2 and fake.prompts[1][0] == forked["session_id"]


def test_a_running_session_takes_no_second_turn(fixture):
    _, directory, _, fake = fixture
    scripted(fake, "hold")
    first = run("plan", directory, timeout=1)
    assert first["status"] == "running" and first["timed_out"] is True and "never start another turn" in first["note"]
    sid = first["session_id"]
    assert "is running" in run("plan", session_id=sid)["error"]
    assert session("steer", sid, message="Focus on tests")["steered"] is True
    assert fake.steers == [(sid, "Focus on tests")]
    again = session("wait", sid, timeout=1)
    assert again["status"] == "running" and again["timed_out"] is True


def test_steer_and_interrupt_need_a_running_turn(fixture):
    _, directory, _, _ = fixture
    sid = run("plan", directory)["session_id"]
    assert "No running" in session("steer", sid, message="x")["error"]
    assert "No running" in session("interrupt", sid)["error"]
    assert session("status", sid)["status"] == "completed"


def test_interrupt_stops_the_run_and_reports_it(fixture):
    _, directory, _, fake = fixture
    scripted(fake, "hold")
    sid = run("plan", directory, timeout=1)["session_id"]
    stopped = session("interrupt", sid)
    assert stopped["status"] == "interrupted" and stopped["interrupt_requested"] is True, stopped
    assert stopped["outcome"] == "interrupted" and "Never a rollback" in stopped["note"]
    assert sid not in fake.active


def test_failed_turn_says_why_and_what_to_do(fixture):
    _, directory, _, fake = fixture
    scripted(fake, "fail-error:The usage limit has been reached")
    failed = run("plan", directory)
    assert failed["status"] == "failed", failed
    assert failed["provider_error"] == {"kind": "limit", "message": "The usage limit has been reached",
                                        "model": "anthropic/claude-opus-5-5"}
    assert "usage limit has been reached" in failed["error"] and "another model" in failed["error"]
    scripted(fake, "finish:failed:")
    plain = run("plan", directory)
    assert plain["status"] == "failed" and "provider_error" not in plain
    assert plain["error"] == "OpenCode reported a failed turn; partial effects may exist"


def test_provider_problems_are_classified():
    problem = turn.provider_problem
    assert problem({"type": "provider.error", "message": "Our servers are currently overloaded."}, None)["kind"] == "limit"
    assert problem({"name": "APIError", "data": {"message": "Too Many Requests", "statusCode": 429}},
                   {"providerID": "anthropic", "id": "claude-sonnet-5-5"}) == {
        "kind": "limit", "message": "Too Many Requests", "model": "anthropic/claude-sonnet-5-5"}
    assert problem({"type": "unknown", "message": "Claude Code credentials are unavailable or expired."},
                   None)["kind"] == "auth"
    assert problem({"type": "x", "message": "Bad Gateway"}, None)["kind"] == "other"


def test_a_turn_without_an_idle_marker_is_unknown(fixture):
    _, directory, _, fake = fixture
    scripted(fake, "vanish")
    out = run("plan", directory)
    assert out["status"] == "unknown" and "without an outcome" in out["error"], out
    assert "never replay" in out["note"]
    assert session("status", out["session_id"])["status"] == "unknown"


def test_unreachable_service_is_unknown_after_a_grace(fixture):
    _, directory, _, fake = fixture
    scripted(fake, "down")
    out = run("plan", directory)
    assert out["status"] == "unknown" and "unreachable" in out["error"], out
    assert out["session_id"]


def test_unadmitted_prompt_is_refused_or_unknown(fixture):
    _, directory, _, fake = fixture
    fake.prompt_error = api.ApiError(400, "BadRequest", "no")
    assert "Prompt refused (400)" in run("plan", directory)["error"]
    fake.prompt_error = api.Unavailable("lost")
    unknown = run("plan", directory)
    assert unknown["status"] == "unknown" and "admission not confirmed" in unknown["error"]


def test_setup_that_the_service_did_not_apply_sends_no_prompt(fixture):
    _, directory, _, fake = fixture
    fake.drop_permissions = True
    out = run("plan", directory)
    assert "did not report back" in out["error"] and "no OpenCode turn started" in out["error"]
    assert not fake.prompts


def test_refused_note_entry_falls_back_to_the_prompt(fixture):
    _, directory, _, fake = fixture
    fake.note_refused = True
    sid = run("plan", directory)["session_id"]
    assert fake.prompts[0][1].startswith("A Hermes agent drives this session") and fake.prompts[0][1].endswith(MESSAGE)
    assert "hermes.note" not in fake.entries.get(sid, {})


# ---------------------------------------------------------------- requests

def test_permission_request_hands_back_and_once_resumes(fixture):
    _, directory, _, fake = fixture
    scripted(fake, "ask-permission", "finish")
    paused = run("plan", directory)
    assert paused["status"] == "waiting", paused
    item = paused["pending"][0]
    assert item["kind"] == "permission" and item["action"] == "external_directory" and not item["subagent"]
    assert "opencode_request" in paused["note"]
    sid = paused["session_id"]
    assert request("list", sid)["pending"][0]["id"] == item["id"]
    done = request("reply", sid, request_id=item["id"], decision="once")
    assert done["status"] == "completed", done
    assert fake.replies == [(item["id"], {"decision": "once"})]


def test_reject_carries_the_reason_to_opencode(fixture):
    _, directory, _, fake = fixture
    scripted(fake, "ask-permission", "finish")
    paused = run("plan", directory)
    done = request("reply", paused["session_id"], request_id=paused["pending"][0]["id"], decision="reject",
                   reason="Outside the approved scope; use the repo.")
    assert done["status"] == "completed"
    assert fake.replies[0][1] == {"decision": "reject", "message": "Outside the approved scope; use the repo."}


def test_session_wide_and_foreign_replies_are_refused(fixture):
    _, directory, _, fake = fixture
    scripted(fake, "ask-permission", "finish")
    paused = run("plan", directory)
    sid, rid = paused["session_id"], paused["pending"][0]["id"]
    assert "never always" in request("reply", sid, request_id=rid, decision="always")["error"]
    assert "not pending" in request("reply", sid, request_id="per_foreign", decision="once")["error"]
    assert "Use list or reply" in request("answer", sid)["error"]
    assert not fake.replies


def test_a_question_is_answered_or_declined(fixture):
    _, directory, _, fake = fixture
    scripted(fake, "ask-question", "finish")
    paused = run("plan", directory)
    assert paused["status"] == "waiting"
    asked = paused["pending"][0]
    assert asked["kind"] == "question" and asked["fields"][0]["options"][0] == {"value": "Red", "label": "Red"}
    assert "answer=" in request("reply", paused["session_id"], request_id=asked["id"])["error"]
    assert "map each field" in request("reply", paused["session_id"], request_id=asked["id"], answer={"q0": {}})["error"]
    done = request("reply", paused["session_id"], request_id=asked["id"], answer={"q0": "Red"})
    assert done["status"] == "completed"
    assert fake.answers == [(asked["id"], {"answer": {"q0": "Red"}})]
    scripted(fake, "ask-question", "finish")
    again = run("plan", directory)
    declined = request("reply", again["session_id"], request_id=again["pending"][0]["id"], decision="reject")
    assert declined["status"] == "completed" and fake.cancelled == [again["pending"][0]["id"]]


def test_subagent_requests_are_found_through_the_session_tree(fixture):
    _, directory, _, fake = fixture
    scripted(fake, "ask-child", "finish")
    paused = run("plan", directory)
    item = paused["pending"][0]
    assert paused["status"] == "waiting" and item["subagent"] is True and item["session_id"].endswith("child")
    fake.sessions["ses_unrelated"] = {"id": "ses_unrelated", "location": {"directory": str(directory)},
                                      "time": {"created": 1}}
    foreign = fake.ask("ses_unrelated")
    listed = request("list", paused["session_id"])["pending"]
    assert [p["id"] for p in listed] == [item["id"]] and foreign["id"] not in {p["id"] for p in listed}
    done = request("reply", paused["session_id"], request_id=item["id"], decision="once")
    assert done["status"] == "waiting" or done["status"] == "completed"


def test_pending_requests_stay_until_answered(fixture):
    _, directory, _, fake = fixture
    scripted(fake, "ask-permission", "finish")
    paused = run("plan", directory)
    for _ in range(2):
        again = session("wait", paused["session_id"], timeout=1)
        assert again["status"] == "waiting" and again["pending"][0]["id"] == paused["pending"][0]["id"]


# ---------------------------------------------------------------- provider limits

def test_limit_retry_hands_back_and_through_retry_waits_on(fixture):
    _, directory, _, fake = fixture
    scripted(fake, "retry:The usage limit has been reached:1", "hold")
    first = run("plan", directory, timeout=1)
    assert first["status"] == "running" and not first.get("timed_out"), first
    retry = first["retrying"]
    assert retry["kind"] == "limit" and retry["model"] == "anthropic/claude-opus-5-5" and not retry["subagent"]
    assert "keeps retrying" in first["note"] and "through_retry" in first["note"]
    waited = session("wait", first["session_id"], timeout=1, through_retry=True)
    assert waited["timed_out"] is True and "retrying" not in waited
    assert "through_retry must be boolean" in session("wait", first["session_id"], through_retry="yes")["error"]
    assert "only accepted for wait" in session("status", first["session_id"], through_retry=True)["error"]


def test_transient_retry_hands_back_only_after_some_attempts(fixture):
    _, directory, _, fake = fixture
    scripted(fake, "retry:Bad Gateway:1", "hold")
    early = run("plan", directory, timeout=1)
    assert early["timed_out"] is True and "retrying" not in early
    scripted(fake, "retry:Bad Gateway:3", "hold")
    late = run("plan", directory, timeout=1)
    assert late["retrying"]["kind"] == "other" and late["retrying"]["attempt"] == 3 and not late.get("timed_out")


# ---------------------------------------------------------------- worktree and models

def test_a_write_run_refuses_a_worktree_another_session_runs_in(fixture):
    _, directory, _, fake = fixture
    fake.sessions["ses_person"] = {"id": "ses_person", "location": {"directory": str(directory)},
                                   "time": {"created": 1}}
    fake.active.add("ses_person")
    assert "already running in this worktree" in run("build", directory, approval="Client: go")["error"]
    assert run("plan", directory)["status"] == "completed", "read-only runs may look alongside"


def test_concurrent_starts_in_one_worktree_are_refused(fixture):
    home, directory, _, fake = fixture
    with plugin._starting(home, str(directory)):
        assert "Another call is starting" in run("plan", directory)["error"]
    assert run("plan", directory)["status"] == "completed"


def test_callers_own_models_are_refused_for_every_role(fixture):
    home, directory, _, fake = fixture
    (home / "config.yaml").write_text(CONFIG + "model:\n  default: claude-opus-5-5\n  provider: anthropic\n")
    pinned = run("plan", directory)
    assert "your own model" in pinned["error"], pinned
    assert "your own model" in run("plan", directory, model="anthropic/claude-opus-5-5-fast")["error"]
    ok = run("plan", directory, model="openai/gpt-6-sol", variant="high")
    assert ok["status"] == "completed" and ok["engine"] == "openai/gpt-6-sol#high"
    models.observe(session_id="hermes-1", model="claude-fable-5-1", provider="anthropic")
    args = dict(message="x", directory=str(directory), model="anthropic/claude-fable-5-1")
    assert "your own model" in json.loads(plugin.opencode_run("plan", args, session_id="hermes-1"))["error"]
    assert json.loads(plugin.opencode_run("plan", {**args, "model": "openai/gpt-6-sol", "variant": "high"},
                                          session_id="hermes-1"))["status"] == "completed"


def test_model_key_folds_speed_tiers_and_snapshots():
    key = models.model_key
    assert key("anthropic/claude-opus-5-5-fast") == key("claude-opus-5-5-20251001") == "claude-opus-5-5"
    assert key("openai/gpt-6.1-sol:free") == "gpt-6.1-sol"


def test_model_choice_is_any_catalog_model_of_an_allowed_provider(fixture):
    _, directory, _, fake = fixture
    assert "allowed_providers" in run("plan", directory, model="xai/grok-4.7")["error"]
    assert "requires a model" in run("plan", directory, variant="high")["error"]
    assert "plain name" in run("plan", directory, model="openai/gpt-6-sol; rm -rf")["error"]
    assert "does not offer" in run("plan", directory, model="openai/gpt-9")["error"]
    assert "no tool use" in run("plan", directory, model="openai/gpt-image-3")["error"]
    assert "no variant" in run("plan", directory, model="openai/gpt-6-sol", variant="max")["error"]
    first = run("plan", directory, model="openai/gpt-6-sol", variant="high")
    assert first["engine"] == "openai/gpt-6-sol#high"
    sid = first["session_id"]
    assert run("plan", session_id=sid)["engine"] == "openai/gpt-6-sol#high", "an explicit choice binds the session"
    assert run("plan", session_id=sid, model="openai/gpt-6.1-sol", variant="medium")["engine"] == \
        "openai/gpt-6.1-sol#medium"


def test_configured_role_model_carries_its_variant(fixture):
    home, directory, _, fake = fixture
    configure(home, "  roles:\n    plan: {agent: plan, policy: read-only, model: 'openai/gpt-6.1-sol#high'}\n")
    assert run("plan", directory)["engine"] == "openai/gpt-6.1-sol#high"
    assert run("plan", directory, model="openai/gpt-6-sol")["engine"] == "openai/gpt-6-sol"


def test_catalog_lists_models_defaults_and_your_own(fixture, monkeypatch):
    home, directory, _, fake = fixture
    configure(home, "  roles:\n    review: {agent: review, policy: read-only, model: 'anthropic/claude-fable-5-1#high'}"
                    "\n    build: {agent: build, policy: write}\nmodel:\n  default: claude-opus-5-5\n")
    listed = json.loads(plugin.opencode_catalog({"what": "models"}))
    names = [m["model"] for m in listed["models"]]
    assert "xai/grok-4.7" not in names and "openai/gpt-image-3" not in names
    assert {m["model"] for m in listed["models"] if m.get("yours")} == {
        "anthropic/claude-opus-5-5", "anthropic/claude-opus-5-5-fast"}
    sol = next(m for m in listed["models"] if m["model"] == "openai/gpt-6.1-sol")
    assert sol["variants"] == ["medium", "high"] and sol["context"] == 400000
    assert sol["cost_per_mtok"] == {"input": 2, "output": 10}
    assert listed["defaults"] == {"review": "anthropic/claude-fable-5-1#high",
                                  "build": "anthropic/claude-opus-5-5#medium"}


def test_catalog_reads_agents_skills_vcs_and_refuses_the_rest(fixture):
    _, directory, _, _ = fixture
    agents = json.loads(plugin.opencode_catalog({"what": "agents", "directory": str(directory)}))["agents"]
    assert {a["id"] for a in agents} == {"plan", "review", "debug", "build"}
    assert all("permissions" not in a for a in agents)
    skills = json.loads(plugin.opencode_catalog({"what": "skills", "directory": str(directory)}))["skills"]
    assert skills == [{"id": "git-commit", "name": "git-commit", "description": "d"}]
    assert json.loads(plugin.opencode_catalog({"what": "info"})) == {"version": "2.0.23"}
    assert "what must be" in json.loads(plugin.opencode_catalog({"what": "config"}))["error"]
    assert "Unexpected" in json.loads(plugin.opencode_catalog({"what": "info", "x": 1}))["error"]


# ---------------------------------------------------------------- session tool

def test_list_shows_only_the_callers_sessions(fixture):
    _, directory, owner, fake = fixture
    mine = run("plan", directory)["session_id"]
    fake.sessions["ses_person"] = {"id": "ses_person", "location": {"directory": str(directory)},
                                   "time": {"created": 1}, "metadata": {"hermes": {"owner": {"x": 1}}}}
    fake.sessions["ses_plain"] = {"id": "ses_plain", "location": {"directory": str(directory)},
                                  "time": {"created": 1}}
    rows = session("list", directory=str(directory))["sessions"]
    assert [r["session_id"] for r in rows] == [mine] and rows[0]["role"] == "plan" and rows[0]["running"] is False
    assert session("list", limit=0)["error"] == "limit must be 1..100"


def test_messages_and_diff(fixture):
    _, directory, _, fake = fixture
    sid = run("plan", directory)["session_id"]
    listed = session("messages", sid, limit=5)["messages"]
    assert [m["type"] for m in listed] == ["idle", "assistant", "user"]
    assert listed[0]["outcome"] == "succeeded" and listed[1]["text"] == "RESULT_OK"
    diff = session("diff", sid)
    assert diff["files"] == [{"file": "a.py", "status": "modified", "additions": 3, "deletions": 1}]
    assert session("diff", sid, patch=True)["files"][0]["patch"] == "x" * 100
    assert "limit must be 1..50" in session("messages", sid, limit=51)["error"]
    fresh = json.loads(plugin.opencode_session({"action": "fork", "session_id": sid}))
    assert fresh["forked_from"] == sid and fresh["session_id"] in fake.sessions
    assert fake.sessions[fresh["session_id"]]["metadata"]["hermes"]["role"] == "plan"
    assert session("bogus", sid)["error"].startswith("Use status")


def test_status_of_a_session_that_never_ran_is_idle(fixture):
    _, directory, owner, fake = fixture
    created = api.data(turn.call("post", "/api/session", {
        "agent": "plan", "model": fakes.PINS["plan"], "location": {"directory": str(directory)},
        "permissions": [], "metadata": {"hermes": {"owner": owner, "role": "plan", "branch": "topic"}}}))
    assert session("status", created["id"])["status"] == "idle"


def test_instructions_are_listed_set_and_removed(fixture):
    _, directory, _, fake = fixture
    sid = run("plan", directory)["session_id"]

    def call(**kwargs):
        return json.loads(plugin.opencode_instructions(dict(session_id=sid, **kwargs)))
    assert call(action="list")["entries"][0]["key"] == "hermes.note"
    assert call(action="put", key="hermes.scope", value="Only touch docs/")["set"] is True
    assert fake.entries[sid]["hermes.scope"] == "Only touch docs/"
    assert call(action="remove", key="hermes.scope")["removed"] is True
    assert "hermes.scope" not in fake.entries[sid]
    assert "hermes.<name>" in call(action="put", key="other", value="x")["error"]
    assert "nonempty" in call(action="put", key="hermes.x", value=" ")["error"]
    assert "Use list" in call(action="clear")["error"]


def test_reconcile_only_turns_refuse_execution_but_not_inspection(fixture, monkeypatch):
    _, directory, _, _ = fixture
    sid = run("plan", directory)["session_id"]
    monkeypatch.setenv("RESIDENT_TURN_KIND", "reconcile")
    assert "reconcile-only" in run("plan", session_id=sid)["error"]
    assert session("status", sid)["status"] == "completed"


def test_disabling_the_integration_blocks_runs_but_keeps_inspection(fixture):
    home, directory, _, _ = fixture
    sid = run("plan", directory)["session_id"]
    (home / "config.yaml").write_text("opencode:\n  enabled: false\n")
    assert "not enabled" in run("plan", session_id=sid)["error"]
    assert session("status", sid)["status"] == "completed"
    assert session("wait", sid)["status"] == "completed"


def test_live_callers_get_the_state_and_a_notifier(fixture, monkeypatch):
    home, directory, owner, fake = fixture
    monkeypatch.setattr(plugin, "_scope", lambda: (home, owner, True))
    launched = []
    monkeypatch.setattr(plugin, "_launch_notifier", lambda h, sid, task: launched.append(sid) or "proc_1")
    scripted(fake, "hold")
    started = run("plan", directory)
    assert started["status"] == "running" and started["process_session_id"] == "proc_1"
    assert launched == [started["session_id"]]
    monkeypatch.setattr(plugin, "_launch_notifier", lambda *a: None)
    again = json.loads(plugin.opencode_session({"action": "status", "session_id": started["session_id"]}))
    assert again["status"] == "running"
    scripted(fake, "ask-permission", "finish")
    paused = run("plan", directory)
    assert paused["status"] == "waiting" and paused["pending"], "a live caller sees a pause in the first state"
    assert "No completion notification" in paused["note"]


def test_notifier_returns_at_the_next_handback(fixture):
    home, directory, _, fake = fixture
    scripted(fake, "ask-permission", "finish")
    sid = run("plan", directory)["session_id"]
    assert plugin._notify(home, sid)["status"] == "waiting"
    with pytest.raises(ValueError, match="Invalid captured"):
        plugin._notify(home.parent, sid)


def test_notifier_does_not_return_on_a_provider_retry(fixture, monkeypatch):
    home, directory, _, fake = fixture
    scripted(fake, "retry:The usage limit has been reached:1", "hold")
    sid = run("plan", directory, timeout=1)["session_id"]
    monkeypatch.setattr(plugin, "NOTIFY_LIMIT", 1)
    settled = plugin._notify(home, sid)
    assert settled["timed_out"] is True and "retrying" not in settled


# ---------------------------------------------------------------- waiting

def test_wait_limit_stays_below_the_tool_deadline(fixture, monkeypatch):
    home, _, _, _ = fixture
    settings = {"wait_timeout": 3300}
    (home / "config.yaml").write_text(CONFIG + "timeouts:\n  tools:\n    sequential_call: 3660\n")
    monkeypatch.delenv("RESIDENT_DEADLINE", raising=False)
    assert REAL_WAIT_LIMIT(home, settings) == 3300
    assert REAL_WAIT_LIMIT(home, settings, 60) == 60
    (home / "config.yaml").write_text(CONFIG + "timeouts:\n  tools:\n    sequential_call: 420\n")
    assert REAL_WAIT_LIMIT(home, settings) == 390
    monkeypatch.setenv("RESIDENT_DEADLINE", str(turn.time.time() + 100))
    assert 90 < REAL_WAIT_LIMIT(home, settings) <= 95


# ---------------------------------------------------------------- ruleset

def test_session_ruleset_holds_no_broad_allow_but_worktree_edits():
    """Subagent sessions copy the ruleset and OpenCode applies it after their own
    posture, so an allow here would reopen what a subagent denies itself. The one
    exception is a write run's edits inside its worktree."""
    scratch, readable = policy.directories("/tmp/fake-opencode")
    narrow = set(scratch + readable) | set(policy.SAMPLE_READS) | set(policy.WRITE_ALLOW_AFTER_ASK)
    for kind in config.POLICIES:
        for issue in (None, "granted"):
            rules = policy.rules(kind, issue, {"main"}, tmp="/tmp/fake-opencode")
            broad = [r for r in rules if r["effect"] == "allow" and r["resource"] not in narrow]
            assert broad == ([{"action": "edit", "resource": "*", "effect": "allow"}] if kind == "write" else []), kind
            assert policy.decide(rules, "edit", "src/a.py") == ("allow" if kind == "write" else "deny")
            for protected in (f"{readable[0][:-1]}agent/x.md", f"{readable[1][:-1]}x/SKILL.md"):
                assert policy.decide(rules, "edit", protected) == "deny", (kind, protected)
            for secret in (".env", "app/.env", "key.pem", ".ssh/id_rsa"):
                assert policy.decide(rules, "edit", secret) == "deny", (kind, secret)
            assert policy.decide(rules, "edit", ".env.example") == ("allow" if kind == "write" else "deny")
            for secret in (".env", "app/.env", ".env.local", "key.pem", ".ssh/id_rsa", ".envrc"):
                assert policy.decide(rules, "read", secret) == "deny", (kind, secret)
            assert policy.decide(rules, "read", ".env.example") == "allow"
            assert policy.decide(rules, "external_directory", "/somewhere/else/*") == "ask"
            assert policy.decide(rules, "external_directory", "/tmp/fake-opencode/*") == "allow"
            for command in ("git push --force origin topic", "git push origin main", "git -C x push origin main",
                            "gh pr merge 3", "gh api repos/x", "git reset --hard HEAD~1"):
                assert policy.decide(rules, "shell", command) == "deny", (kind, command)
            assert policy.decide(rules, "github_project_item_add", "*") == "deny"


def test_read_only_never_edits_and_never_hands_work_to_an_editor():
    rules = policy.rules("read-only", None, {"main"})
    assert policy.decide(rules, "edit", "src/a.py") == "deny"
    for name in ("worker", "general"):
        assert policy.decide(rules, "subagent", name) == "deny"
    assert policy.decide(rules, "subagent", "explore-small") == "ask", "other subagents keep their own posture"
    assert policy.decide(rules, "shell", "git diff --output=x") == "deny"
    assert policy.decide(rules, "shell", "gh issue comment 1") == "deny"


def test_write_asks_for_person_gated_commands_and_keeps_person_denies():
    person = PERSON_DENIES + [{"action": "shell", "resource": "ls *", "effect": "allow"}]
    rules = policy.rules("write", None, {"main"}, tmp="/tmp/fake-opencode", person_denies=person)
    assert {"action": "shell", "resource": "ls *", "effect": "deny"} not in rules
    combined = fakes.agent_info("build")["permissions"] + rules
    for command in ("git push origin topic", "git rebase main", "git checkout other", "git -C .. status x",
                    "npm exec foo", "gh issue comment 1"):
        expected = "allow" if command.startswith("git -C .. status") else "ask"
        assert policy.decide(combined, "shell", command) == expected, command
    assert policy.decide(combined, "shell", "pytest -q") == "allow"
    assert policy.decide(combined, "shell", "sudo rm -rf /") == "deny"
    assert policy.decide(combined, "edit", "src/a.py") == "allow"
    assert policy.decide(rules, "external_directory", "/secret/x/*") == "deny"
    assert policy.decide(rules, "external_directory", "/tmp/fake-opencode/*") == "allow"
    granted = policy.rules("write", "granted", {"main"}, tmp="/tmp/fake-opencode")
    assert policy.decide(fakes.agent_info("build")["permissions"] + granted, "shell", "gh issue comment 1") == "allow"


def test_shell_wildcards_follow_opencode():
    rules = [{"action": "shell", "resource": "*", "effect": "deny"},
             {"action": "shell", "resource": "git status *", "effect": "allow"}]
    assert policy.decide(rules, "shell", "git status") == "allow"
    assert policy.decide(rules, "shell", "git status --short") == "allow"
    assert policy.decide(rules, "shell", "git statusx") == "deny"
    assert policy.decide([], "read", "x") == "ask"


# ---------------------------------------------------------------- repository guards

def test_nonstandard_remote_default_is_protected(monkeypatch):
    monkeypatch.setattr(policy, "git", lambda *args: "origin")

    def run_(command, **kwargs):
        if "ls-remote" in command:
            return subprocess.CompletedProcess(command, 0, "ref: refs/heads/trunk\tHEAD\n", "")
        if command[-1] == "HEAD":
            return subprocess.CompletedProcess(command, 0, "trunk\n", "")
        return subprocess.CompletedProcess(command, 1, "", "")
    monkeypatch.setattr(policy.subprocess, "run", run_)
    with pytest.raises(ValueError, match="default branch"):
        policy.branch("/fixture", True)


def test_unverified_remote_default_blocks_a_write_run(monkeypatch):
    monkeypatch.setattr(policy, "git", lambda *args: "origin")

    def run_(command, **kwargs):
        if command[-1] == "HEAD" and "symbolic-ref" in command:
            return subprocess.CompletedProcess(command, 0, "topic\n", "")
        return subprocess.CompletedProcess(command, 1, "", "")
    monkeypatch.setattr(policy.subprocess, "run", run_)
    with pytest.raises(ValueError, match="could not be verified"):
        policy.branch("/fixture", True)


def test_detached_checkout_allows_reading_not_writing(monkeypatch):
    monkeypatch.setattr(policy, "git", lambda *args: "a" * 40)
    monkeypatch.setattr(policy.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", ""))
    assert policy.branch("/fixture", False)[0] == "detached:" + "a" * 40
    with pytest.raises(ValueError, match="named task branch"):
        policy.branch("/fixture", True)


# ---------------------------------------------------------------- configuration and registration

class Context:
    def __init__(self, profile="assistant"):
        self.profile_name = profile
        self.hooks, self.tools = [], {}

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs


def register(monkeypatch, home, profile="assistant"):
    pytest.importorskip("hermes_constants")
    monkeypatch.setenv("HERMES_HOME", str(home))
    context = Context(profile)
    plugin.register(context)
    return context


def test_roles_become_tools(fixture, monkeypatch):
    home, _, _, _ = fixture
    context = register(monkeypatch, home)
    assert context.hooks == [("post_api_request", models.observe)]
    assert set(context.tools) == {"opencode_run_plan", "opencode_run_review", "opencode_run_debug",
                                  "opencode_run_build", "opencode_session", "opencode_request",
                                  "opencode_instructions", "opencode_catalog", "opencode_history"}
    build = context.tools["opencode_run_build"]["schema"]["parameters"]
    plan = context.tools["opencode_run_plan"]["schema"]["parameters"]
    assert {"approval", "issue_approval"} <= set(build["properties"]) and "approval" not in plan["properties"]
    assert build["required"] == ["message"] and build["additionalProperties"] is False
    assert all(t["toolset"] == "opencode" for t in context.tools.values())
    assert "read-only" in context.tools["opencode_run_plan"]["description"]
    assert "explicit approval" in context.tools["opencode_run_build"]["description"]


def test_configured_roles_replace_the_defaults(fixture, monkeypatch):
    home, _, _, _ = fixture
    configure(home, "  roles:\n    audit: {agent: review, policy: read-only, note: 'Check licences too.'}\n")
    context = register(monkeypatch, home)
    assert {n for n in context.tools if n.startswith("opencode_run_")} == {"opencode_run_audit"}
    assert config.roles(home) == {"audit": {"agent": "review", "policy": "read-only", "note": "Check licences too."}}


def test_a_broken_roles_block_keeps_the_default_tools(fixture, monkeypatch):
    home, _, _, _ = fixture
    configure(home, "  roles:\n    Bad Name: {agent: x, policy: write}\n")
    assert set(config.roles(home)) == {"plan", "review", "debug", "build"}
    with pytest.raises(ValueError, match="not a role name"):
        config.load(home)


def test_a_role_note_is_part_of_the_session_instruction(fixture):
    home, directory, _, fake = fixture
    configure(home, "  roles:\n    audit: {agent: review, policy: read-only, note: 'Check licences too.'}\n")
    sid = run("audit", directory)["session_id"]
    assert fake.entries[sid]["hermes.note"].endswith("Check licences too.")
    assert fake.sessions[sid]["agent"] == "review"


@pytest.mark.parametrize("text, message", [
    ("  wait_timeout: 0\n", "wait_timeout"),
    ("  wait_timeout: 9999\n", "wait_timeout"),
    ("  allowed_providers: openai\n", "allowed_providers"),
    ("  timeout: 3600\n", "unknown keys"),
    ("  roles: {}\n", "at least one role"),
    ("  roles:\n    a: {agent: plan, policy: admin}\n", "policy"),
    ("  roles:\n    a: {agent: plan, policy: write, extra: 1}\n", "takes agent"),
    ("  roles:\n    a: {agent: 'x y', policy: write}\n", "agent"),
    ("  roles:\n    a: {agent: plan, policy: write, model: nope}\n", "provider/model"),
    ("  roles:\n    a: {agent: plan, policy: write, model: 'a/b#bad variant'}\n", "provider/model"),
])
def test_configuration_is_validated(fixture, text, message):
    home, _, _, _ = fixture
    (home / "config.yaml").write_text("opencode:\n  enabled: true\n" + text)
    with pytest.raises(ValueError, match=message):
        config.load(home)


def test_only_the_assistant_gets_the_tools(fixture, monkeypatch, tmp_path):
    home, _, _, _ = fixture
    for profile in ("creator", "writer", "default", "engineer"):
        assert register(monkeypatch, home, profile).tools == {}
    assert register(monkeypatch, home, "assistant").tools


def test_scope_refuses_inbound_and_foreign_profiles(monkeypatch, tmp_path):
    for name, inbound in (("creator", False), ("assistant", True)):
        home = tmp_path / "profiles" / name
        home.mkdir(parents=True, exist_ok=True)
        real = plugin.dispatch
        monkeypatch.setattr(real, "_scope", lambda h=home, i=inbound: (h, {}, False, i))
        with pytest.raises(ValueError, match="requires an Assistant"):
            _module("opencode_scope_probe", ROOT / "__init__.py")._scope()


def test_live_callers_bind_to_their_topic_not_the_session_id(monkeypatch, tmp_path):
    home = tmp_path / "profiles" / "assistant"
    home.mkdir(parents=True)
    route = {"PLATFORM": "telegram", "SOURCE": "telegram", "PROFILE": "assistant", "KEY": "k:topic-1",
             "CHAT_ID": "chat", "THREAD_ID": "topic-1", "USER_ID": "person", "ID": "session-1"}
    monkeypatch.setattr("gateway.session_context.get_session_env",
                        lambda name, default="": route.get(name.removeprefix("HERMES_SESSION_"), default))
    probe = _module("opencode_topic_probe", ROOT / "__init__.py")

    def owner(live=True):
        legacy = {"profile": "assistant", "session_id": route["ID"], "turn_session_id": route["ID"]}
        monkeypatch.setattr(probe.dispatch, "_scope", lambda: (home, legacy, live, False))
        return probe._scope()[1]

    first = owner()
    assert set(first) == {"profile", "topic_digest"}
    route["ID"] = "session-2"  # /new, a compression continuation or a restart
    assert owner() == first
    for field, value in (("THREAD_ID", "topic-2"), ("USER_ID", "someone-else"), ("KEY", "k:topic-2")):
        changed = dict(route)
        route[field] = value
        assert owner() != first, field
        route.clear()
        route.update(changed)
    assert owner() == first
    # A CLI or resident caller keeps the session-id binding specialist-call derives.
    assert owner(live=False)["session_id"] == "session-2"
    route["KEY"] = ""
    with pytest.raises(ValueError, match="conversation route"):
        owner()
    route["KEY"] = "k:topic-1"
    # A delegate_task child inherits the route, so it must not act as the parent.
    monkeypatch.setattr("agent.delegation_context.is_delegated_child_context", lambda: True)
    with pytest.raises(ValueError, match="delegated subagents"):
        owner()


# ---------------------------------------------------------------- api client

def test_api_client_reads_files_not_pipes_and_maps_errors(tmp_path):
    fake = tmp_path / "opencode"
    fake.write_text("#!/bin/sh\n"
                    "case \"$3\" in\n"
                    "  /ok*) python3 -c 'print(\"{\\\"data\\\": \\\"\" + \"x\" * 300000 + \"\\\"}\")' ;;\n"
                    "  /missing) echo '{\"_tag\":\"SessionNotFoundError\",\"message\":\"Session not found\"}';"
                    " echo 'HTTP 404 Not Found' >&2; exit 1 ;;\n"
                    "  /broken) echo 'HTTP 503 Service Unavailable' >&2; exit 1 ;;\n"
                    "  /empty) exit 0 ;;\n"
                    "esac\n")
    fake.chmod(0o700)
    real = _module("opencode_api_probe", ROOT / "api.py")
    assert len(real.call("get", "/ok", executable=str(fake))["data"]) == 300000
    with pytest.raises(real.ApiError) as error:
        real.call("get", "/missing", executable=str(fake))
    assert error.value.status == 404 and error.value.tag == "SessionNotFoundError"
    with pytest.raises(real.Unavailable):
        real.call("get", "/broken", executable=str(fake))
    assert real.call("post", "/empty", {"a": 1}, executable=str(fake)) is None
    assert real.path("/api/session/{sid}/x", {"from": "msg_1", "skip": None}, sid="ses/../a") == \
        "/api/session/ses%2F..%2Fa/x?from=msg_1"
    assert re.fullmatch(r"location%5Bdirectory%5D=%2Fa\+b", urllib.parse.urlencode(real.location("/a b")))
