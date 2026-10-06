import importlib.util
import json
from pathlib import Path
import re
import subprocess
import threading
import time
import urllib.parse

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "__init__.py"
spec = importlib.util.spec_from_file_location("engineer_opencode_test", SOURCE)
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
api = plugin.api

REPO_ROOT = Path(__file__).resolve().parents[5]
AGENT_DIR = REPO_ROOT / "opencode/agent"
PERSON_DENIES = [{"action": "shell", "resource": "sudo *", "effect": "deny"},
                 {"action": "external_directory", "resource": "/secret/*", "effect": "deny"}]


def agent_info(name):
    """What the service reports for an installed agent: base + global rules, then the
    agent file's own posture."""
    base = [{"action": "*", "resource": "*", "effect": "allow"},
            {"action": "external_directory", "resource": "*", "effect": "ask"}]
    if name == "build":
        return {"id": "build", "mode": "primary", "permissions": base + PERSON_DENIES,
                "model": {"providerID": "anthropic", "id": "claude-opus-5-5", "variant": "medium"}}
    frontmatter = plugin.yaml.safe_load((AGENT_DIR / f"{name}.md").read_text().split("---\n", 2)[1])
    model = frontmatter.get("model", "")
    provider, _, mid = model.partition("/")
    return {"id": name, "mode": frontmatter.get("mode"), "hidden": frontmatter.get("hidden"),
            "permissions": base + PERSON_DENIES + frontmatter.get("permissions", []),
            "model": {"providerID": provider, "id": mid, **({"variant": frontmatter["variant"]}
                                                             if "variant" in frontmatter else {})}}


class Fake:
    """The shared OpenCode service, at the level of `api.call`."""

    def __init__(self, directory):
        self.directory = str(directory)
        self.sessions, self.messages, self.inbox = {}, {}, {}
        self.active, self.requests, self.replies, self.steers, self.prompts = set(), [], [], [], []
        self.calls, self.scripts, self.agents = [], {}, {}
        self.down = False
        self.clock = 1_000_000
        tools = {"capabilities": {"tools": True}, "enabled": True}
        self.models = [
            {"providerID": "anthropic", "id": "claude-opus-5-5", "variants": [{"id": "high"}, {"id": "medium"}],
             **tools},
            {"providerID": "anthropic", "id": "claude-opus-5-5-fast", "variants": [{"id": "high"}], **tools},
            {"providerID": "anthropic", "id": "claude-fable-5-1", "variants": [{"id": "high"}], **tools},
            {"providerID": "openai", "id": "gpt-6.1-sol", "variants": [{"id": "medium"}, {"id": "high"}],
             "cost": [{"input": 2, "output": 10}], "limit": {"context": 400000}, **tools},
            {"providerID": "openai", "id": "gpt-6-sol", "variants": [{"id": "high"}], **tools},
            {"providerID": "openai", "id": "gpt-image-3", "variants": [], "capabilities": {"tools": False}},
            {"providerID": "xai", "id": "grok-4.7", "variants": [], **tools},
        ]
        self.lock = threading.RLock()

    def tick(self):
        self.clock += 10
        return self.clock

    # -- scripting
    def finish(self, sid, outcome="succeeded", text="RESULT_OK", error=None):
        with self.lock:
            self.active.discard(sid)
            now = self.tick()
            message = {"id": f"msg_a{now}", "type": "assistant", "model": self.sessions[sid].get("model"),
                       "content": [{"type": "text", "text": text}] if text else []}
            if error:
                message["error"] = {"type": "provider.error", "message": error}
            self.messages[sid].append(message)
            self.sessions[sid]["time"]["idle"] = now
            self.sessions[sid]["outcome"] = outcome

    def retry(self, sid, message, attempt):
        """OpenCode sitting in a provider retry: the newest assistant message carries it."""
        with self.lock:
            last = self.messages[sid][-1] if self.messages[sid] else {}
            if last.get("type") != "assistant":
                last = {"id": f"msg_a{self.tick()}", "type": "assistant",
                        "model": self.sessions[sid].get("model"), "content": []}
                self.messages[sid].append(last)
            last["retry"] = {"attempt": attempt, "at": self.clock + 60_000,
                             "error": {"type": "provider.error", "message": message}}

    def ask(self, sid, action="external_directory", resources=("/elsewhere/*",), save=("/elsewhere/*",)):
        with self.lock:
            request = {"id": f"per_{len(self.requests) + len(self.replies)}x", "sessionID": sid, "action": action,
                       "resources": list(resources), "save": list(save)}
            self.requests.append(request)
            return request

    def _step(self, sid):
        script = self.scripts.get(sid)
        if not script:
            return
        step = script.pop(0)
        if step == "hold":
            script.insert(0, "hold")
        elif step.startswith("finish"):
            _, outcome, text = (step.split(":", 2) + ["succeeded", "RESULT_OK"])[:3]
            self.finish(sid, outcome or "succeeded", text or "RESULT_OK")
        elif step == "vanish":
            self.active.discard(sid)
        elif step.startswith("fail-error:"):
            self.finish(sid, "failed", "", step.split(":", 1)[1])
        elif step.startswith("retry:"):
            _, message, attempt = step.split(":", 2)
            self.retry(sid, message, int(attempt))
        elif step == "unretry":
            for message in self.messages[sid]:
                message.pop("retry", None)
        elif step.startswith("ask"):
            parts = step.split(":")
            self.ask(sid, *(parts[1:2] or ["external_directory"]))
            script.insert(0, "wait-reply")
        elif step == "wait-reply":
            if any(r["sessionID"] == sid for r in self.requests):
                script.insert(0, "wait-reply")

    # -- api.call
    def __call__(self, method, route, data=None, **kwargs):
        with self.lock:
            self.calls.append((method, route, data))
            if self.down:
                raise api.Unavailable("service down")
            parsed = urllib.parse.urlsplit(route)
            query = dict(urllib.parse.parse_qsl(parsed.query))
            parts = parsed.path.strip("/").split("/")[1:]
            return self._route(method, parts, query, data)

    def _session(self, sid):
        if sid not in self.sessions:
            raise api.ApiError(404, "SessionNotFoundError", "Session not found")
        return self.sessions[sid]

    def _route(self, method, parts, query, data):
        if parts == ["info"]:
            return {"version": "2.0.23", "paths": {"tmp": "/tmp/fake-opencode"}}
        if parts == ["model"]:
            return {"data": self.models}
        if parts == ["agent"]:
            return {"data": [self.agents.get(n) or agent_info(n)
                             for n in ("build", *plugin.OPENCODE_AGENTS.values())]}
        if parts[0] == "agent":
            info = self.agents.get(parts[1]) or agent_info(parts[1])
            return {"data": info}
        if parts == ["permission", "request"]:
            assert query.get("location[directory]") == self.directory
            return {"location": {"directory": self.directory}, "data": [dict(r) for r in self.requests]}
        if parts == ["session", "active"]:
            for sid in list(self.active):
                self._step(sid)
            return {"data": {sid: {"type": "running"} for sid in self.active}}
        if parts == ["session"] and method == "post":
            sid = f"ses_{len(self.sessions) + 1}abc"
            self.sessions[sid] = {"id": sid, "agent": data["agent"], "model": data["model"],
                                  "permissions": data["permissions"], "metadata": data.get("metadata"),
                                  "location": {"directory": data["location"]["directory"]},
                                  "time": {"created": self.tick(), "updated": self.clock}}
            self.messages[sid] = []
            return {"data": self.sessions[sid]}
        sid = parts[1]
        session = self._session(sid)
        rest = parts[2:]
        if not rest and method == "get":
            return {"data": json.loads(json.dumps(session))}
        if not rest and method == "patch":
            session.update(data)
            return {"data": session}
        if rest == ["fork"]:
            new = f"ses_{len(self.sessions) + 1}fork"
            self.sessions[new] = {**json.loads(json.dumps(session)), "id": new, "time": {"created": self.tick()}}
            self.sessions[new].pop("outcome", None)
            self.messages[new] = list(self.messages[sid])
            return {"data": self.sessions[new]}
        if rest == ["agent"]:
            session["agent"] = data["agent"]
            return None
        if rest == ["model"]:
            session["model"] = data["model"]
            return None
        if rest == ["prompt"]:
            now = self.tick()
            mid = f"msg_u{now}"
            if data.get("delivery") == "steer":
                self.steers.append((sid, data["text"]))
                self.inbox.setdefault(sid, []).append({"id": mid})
            else:
                self.prompts.append((sid, data["text"]))
                self.messages[sid].append({"id": mid, "type": "user", "text": data["text"]})
                self.active.add(sid)
                if not self.scripts.get(sid):
                    self.scripts[sid] = ["finish"]
            return {"data": {"id": mid, "time": {"created": now}, "type": "user"}}
        if rest == ["interrupt"]:
            was = sid in self.active
            for other in [s for s in self.active if s == sid or self.sessions[s].get("parentID") == sid]:
                self.active.discard(other)
                self.sessions[other]["time"]["idle"] = self.tick()
                self.sessions[other]["outcome"] = "interrupted"
            self.scripts.pop(sid, None)
            return {"interrupted": was}
        if rest == ["inbox"]:
            return {"data": self.inbox.get(sid, [])}
        if rest[:1] == ["inbox"] and method == "delete":
            self.inbox[sid] = [i for i in self.inbox.get(sid, []) if i["id"] != rest[1]]
            return None
        if rest == ["message"]:
            return {"data": list(reversed(self.messages[sid])), "cursor": {}}
        if rest == ["diff"]:
            return {"data": [{"file": "a.py", "status": "modified", "additions": 3, "deletions": 1,
                              "patch": "x" * 100}]}
        if rest[:1] == ["permission"] and rest[-1] == "reply":
            request = next((r for r in self.requests if r["id"] == rest[1]), None)
            if request is None:
                raise api.ApiError(404, "PermissionNotFoundError", "not pending")
            self.requests.remove(request)
            self.replies.append((rest[1], data))
            return None
        raise AssertionError(f"unrouted {method} {parts}")


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    home = tmp_path / "profiles/engineer"
    home.mkdir(parents=True)
    (home / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 30\n  wait_timeout: 8\n")
    directory = tmp_path / "work tree"
    directory.mkdir()
    subprocess.run(["git", "init", "-b", "topic", str(directory)], check=True, capture_output=True)
    fake = Fake(directory.resolve())
    monkeypatch.setattr(api, "call", fake)
    owner = {"profile": "engineer", "session_id": "client-a", "routing_digest": "a"}
    monkeypatch.setattr(plugin, "_scope", lambda: (home, owner, False))
    threads = []

    def spawn(home_arg, cid, job):
        thread = threading.Thread(target=plugin._watch, args=(home_arg, cid, job), kwargs={"poll": 0.01},
                                  daemon=True)
        thread.start()
        threads.append(thread)
    monkeypatch.setattr(plugin, "_spawn", spawn)
    monkeypatch.setattr(plugin, "WAIT_POLL", 0.01)
    monkeypatch.setattr(plugin, "NO_OUTCOME_GRACE", 0.2)
    monkeypatch.setattr(plugin, "HALT_GRACE", 0.2)
    monkeypatch.setattr(plugin, "UNREACHABLE_GRACE", 0.2)
    monkeypatch.setattr(plugin, "CATALOG_RETRY", 0)
    monkeypatch.setattr(plugin, "RETRY_POLL", 0)
    yield home, directory.resolve(), owner, fake
    for thread in threads:
        thread.join(timeout=5)


def call(directory=None, **kwargs):
    args = dict(agent="plan", message="Inspect only. ' ; $(not a shell)\nsecond line")
    if directory:
        args["directory"] = str(directory)
    args.update(kwargs)
    return json.loads(plugin.opencode_call(args))


def session(cid, action="status", **kwargs):
    return json.loads(plugin.opencode_session(dict(action=action, conversation_id=cid, **kwargs)))


def settle(cid, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = session(cid)
        if data["status"] not in plugin.ACTIVE and data["status"] != "waiting":
            return data
        time.sleep(0.02)
    raise AssertionError("run did not settle")


# ---------------------------------------------------------------- lifecycle

def test_new_resume_fork_and_literal_prompt(fixture):
    home, directory, owner, fake = fixture
    first = call(directory)
    assert first["status"] == "completed", first
    assert first["result"] == "RESULT_OK" and first["outcome"] == "succeeded"
    sid = first["session_id"]
    assert fake.sessions[sid]["agent"] == "hermes-plan"
    assert fake.sessions[sid]["metadata"] == {"hermes": {"profile": "engineer",
                                                          "conversation": first["conversation_id"]}}
    assert "$(not a shell)" in fake.prompts[-1][1]
    # The engine is the agent's pin, passed explicitly and recorded.
    assert first["engine"] == "anthropic/claude-opus-5-5#high"
    assert first["changes"] == [{"file": "a.py", "status": "modified", "additions": 3, "deletions": 1}]
    resumed = call(conversation_id=first["conversation_id"], message="And now this.")
    assert resumed["status"] == "completed" and resumed["session_id"] == sid
    assert resumed["conversation_id"] == first["conversation_id"]
    forked = call(conversation_id=first["conversation_id"], fork=True, message="Alternative")
    assert forked["status"] == "completed", forked
    assert forked["conversation_id"] != first["conversation_id"] and forked["session_id"] != sid
    assert session(first["conversation_id"])["session_id"] == sid
    record = home / "opencode-sessions" / (first["conversation_id"] + ".json")
    assert oct(record.parent.stat().st_mode & 0o777) == "0o700"


def test_plan_then_build_reapplies_agent_model_and_ruleset(fixture):
    _, directory, _, fake = fixture
    plan = call(directory)
    sid = plan["session_id"]
    assert ["edit", "*", "deny"] in [[r["action"], r["resource"], r["effect"]] for r in fake.sessions[sid]["permissions"]]
    built = call(conversation_id=plan["conversation_id"], agent="build", approval="Client: implement the plan")
    assert built["status"] == "completed", built
    assert built["session_id"] == sid
    assert fake.sessions[sid]["agent"] == "hermes-build"
    assert fake.sessions[sid]["model"] == {"providerID": "openai", "id": "gpt-6.1-sol", "variant": "medium"}
    rules = fake.sessions[sid]["permissions"]
    assert plugin._decide(rules, "edit", "src/x.py") != "deny"
    assert "Client implementation scope: Client: implement the plan" in fake.prompts[-1][1]
    assert "Issue management: not granted" in fake.prompts[-1][1]


def test_failed_and_interrupted_outcomes(fixture):
    _, directory, _, fake = fixture
    fake.scripts["ses_1abc"] = ["finish:failed:partial"]
    failed = call(directory)
    assert failed["status"] == "failed" and "partial effects" in failed["error"], failed
    resumed = call(conversation_id=failed["conversation_id"])
    assert resumed["status"] == "completed"


def test_turn_without_outcome_is_interrupted_and_resumable(fixture):
    _, directory, _, fake = fixture
    fake.scripts["ses_1abc"] = ["vanish"]
    lost = call(directory)
    assert lost["status"] == "interrupted" and "without an outcome" in lost["error"], lost
    again = call(conversation_id=lost["conversation_id"], message="Continue where you stopped.")
    assert again["status"] == "completed" and again["session_id"] == lost["session_id"]


def test_unreachable_service_past_deadline_is_unknown_and_blocks_replay(fixture):
    home, directory, _, fake = fixture
    (home / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 1\n")
    fake.scripts["ses_1abc"] = ["hold"]

    original = fake._route

    def route(method, parts, query, data):
        if parts == ["session", "active"] and fake.prompts:
            fake.down = True
        return original(method, parts, query, data)
    fake._route = route
    result = call(directory)
    data = settle(result["conversation_id"]) if result["status"] in plugin.ACTIVE else result
    fake.down = False
    assert data["status"] == "unknown" and "unreachable" in data["error"], data
    assert "uncertain" in call(conversation_id=result["conversation_id"])["error"]
    assert "Worktree has active or uncertain" in call(directory)["error"]


# ---------------------------------------------------------------- permission requests

def test_permission_request_hands_back_and_once_resumes(fixture):
    _, directory, _, fake = fixture
    fake.scripts["ses_1abc"] = ["ask", "finish"]
    paused = call(directory)
    assert paused["status"] == "waiting", paused
    assert paused["timed_out"] is False and "respond" in paused["note"]
    [request] = paused["pending"]
    assert request["action"] == "external_directory" and request["subagent"] is False
    assert request["expires_at"] > request["first_seen"]
    assert "never always" in session(paused["conversation_id"], "respond", request_id=request["id"],
                                     decision="always")["error"]
    assert "not pending" in session(paused["conversation_id"], "respond", request_id="per_foreign",
                                    decision="once")["error"]
    done = session(paused["conversation_id"], "respond", request_id=request["id"], decision="once")
    assert done["status"] == "completed", done
    assert fake.replies == [(request["id"], {"decision": "once"})]


def test_reject_carries_the_reason_to_opencode(fixture):
    _, directory, _, fake = fixture
    fake.scripts["ses_1abc"] = ["ask", "finish"]
    paused = call(directory)
    request = paused["pending"][0]
    done = session(paused["conversation_id"], "respond", request_id=request["id"], decision="reject",
                   reason="Outside the approved scope; ask the Client first.")
    assert done["status"] == "completed"
    assert fake.replies[-1][1] == {"decision": "reject", "message": "Outside the approved scope; ask the Client first."}


def test_subagent_requests_are_found_through_the_session_tree(fixture):
    _, directory, _, fake = fixture
    fake.scripts["ses_1abc"] = ["hold"]
    original = fake._step

    def step(sid):
        if sid == "ses_1abc" and "ses_child" not in fake.sessions:
            fake.sessions["ses_child"] = {"id": "ses_child", "parentID": sid, "time": {}, "location": {}}
            fake.sessions["ses_other"] = {"id": "ses_other", "time": {}, "location": {}}
            fake.ask("ses_child", "shell", ["npm run build"], ["npm run build *"])
            fake.ask("ses_other", "shell", ["rm -rf x"], ["rm *"])
        return original(sid)
    fake._step = step
    paused = call(directory)
    assert paused["status"] == "waiting", paused
    assert [p["session_id"] for p in paused["pending"]] == ["ses_child"]
    assert paused["pending"][0]["subagent"] is True
    stopped = session(paused["conversation_id"], "stop")
    assert stopped["stop_requested"] is True
    assert settle(paused["conversation_id"])["status"] == "interrupted"


def test_session_wide_approvals_are_refused(fixture):
    """A session-level allow is copied into every subagent session and evaluated
    after its own denies, so the caller can approve a request only once."""
    _, directory, _, fake = fixture
    fake.scripts["ses_1abc"] = ["ask:shell", "finish"]
    built = call(directory, agent="build", approval="Implement")
    request = built["pending"][0]
    refused = session(built["conversation_id"], "respond", request_id=request["id"], decision="conversation")
    assert "once or reject" in refused["error"]
    rules = fake.sessions["ses_1abc"]["permissions"]
    assert session(built["conversation_id"], "respond", request_id=request["id"], decision="once")["status"] == \
        "completed"
    assert fake.sessions["ses_1abc"]["permissions"] == rules


def test_dead_caller_interrupts_its_run(fixture, monkeypatch):
    home, directory, _, fake = fixture
    (home / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 30\n  wait_timeout: 1\n")
    fake.scripts["ses_1abc"] = ["hold"]
    running = call(directory)
    assert running["status"] == "running"
    monkeypatch.setattr(plugin, "_caller_alive", lambda data: False)
    data = settle(running["conversation_id"])
    assert data["status"] == "interrupted" and data["stop_reason"] == "the calling Hermes process ended", data


def test_unconfirmed_interrupt_is_resent_then_unknown(fixture, monkeypatch):
    home, directory, _, fake = fixture
    (home / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 30\n  wait_timeout: 1\n")
    monkeypatch.setattr(plugin, "HALT_GRACE", 0.05)
    monkeypatch.setattr(plugin, "HALT_LIMIT", 0.5)
    fake.scripts["ses_1abc"] = ["hold"]
    original = fake._route

    def deaf(method, parts, query, data):
        if parts[-1:] == ["interrupt"]:
            fake.calls.append(("ignored-interrupt", None, None))
            return {"interrupted": False}
        return original(method, parts, query, data)
    fake._route = deaf
    running = call(directory)
    session(running["conversation_id"], "stop")
    data = settle(running["conversation_id"])
    assert data["status"] == "unknown" and "not confirmed" in data["error"], data
    assert sum(1 for c in fake.calls if c[0] == "ignored-interrupt") >= 3


def test_failure_after_admission_still_returns_the_record(fixture, monkeypatch):
    _, directory, _, fake = fixture
    monkeypatch.setattr(plugin, "_spawn", lambda *a: (_ for _ in ()).throw(OSError("no fork")))
    result = call(directory)
    assert result["conversation_id"] and result["status"] == "running" and "never retry" in result["error"]


def test_unanswered_request_is_rejected_at_its_deadline(fixture):
    home, directory, _, fake = fixture
    (home / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 30\n  permission_timeout: 1\n")
    fake.scripts["ses_1abc"] = ["ask", "finish"]
    paused = call(directory)
    assert paused["status"] == "waiting"
    done = settle(paused["conversation_id"])
    assert done["status"] == "completed", done
    assert fake.replies[0][1]["decision"] == "reject" and "No decision from Hermes" in fake.replies[0][1]["message"]


# ---------------------------------------------------------------- steer, stop, wait, diff

def test_steer_reaches_a_running_turn_only(fixture):
    home, directory, _, fake = fixture
    (home / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 30\n  wait_timeout: 1\n")
    fake.scripts["ses_1abc"] = ["hold"]
    running = call(directory)
    assert running["status"] == "running" and running["timed_out"] is True and "never retry" in running["note"].lower()
    steered = session(running["conversation_id"], "steer", message="Also check the tests.")
    assert steered["steered"] is True and fake.steers == [("ses_1abc", "Also check the tests.")]
    fake.scripts["ses_1abc"] = ["finish"]
    assert session(running["conversation_id"], "wait")["status"] == "completed"
    assert "No running" in session(running["conversation_id"], "steer", message="late")["error"]


def test_stop_interrupts_and_drops_parked_input(fixture):
    home, directory, _, fake = fixture
    (home / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 30\n  wait_timeout: 1\n")
    fake.scripts["ses_1abc"] = ["hold"]
    running = call(directory)
    session(running["conversation_id"], "steer", message="parked")
    stopped = session(running["conversation_id"], "stop")
    assert stopped["stop_requested"] is True
    data = settle(running["conversation_id"])
    assert data["status"] == "interrupted" and data["stop_reason"] == "stop requested", data
    assert fake.inbox["ses_1abc"] == []
    assert "No active" in session(running["conversation_id"], "stop")["error"]


def test_deadline_interrupts_the_run(fixture):
    home, directory, _, fake = fixture
    (home / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 1\n")
    fake.scripts["ses_1abc"] = ["hold"]
    result = call(directory)
    data = settle(result["conversation_id"]) if result["status"] in plugin.ACTIVE else result
    assert data["status"] == "interrupted" and data["stop_reason"] == "deadline reached", data


def test_lost_watchdog_is_restarted_by_status(fixture, monkeypatch):
    home, directory, _, fake = fixture
    (home / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 30\n  wait_timeout: 1\n")
    fake.scripts["ses_1abc"] = ["hold"]
    spawned = []
    real = plugin._spawn
    monkeypatch.setattr(plugin, "_spawn", lambda *a: spawned.append(a))
    running = call(directory)
    assert running["status"] == "running" and len(spawned) >= 1
    fake.finish("ses_1abc")
    monkeypatch.setattr(plugin, "_spawn", real)
    assert settle(running["conversation_id"])["status"] == "completed"


def test_wait_validates_and_diff_lists_changes(fixture):
    _, directory, _, fake = fixture
    first = call(directory)
    cid = first["conversation_id"]
    assert "only accepted for wait" in session(cid, "status", timeout=5)["error"]
    assert "positive integer" in session(cid, "wait", timeout=0)["error"]
    settled = session(cid, "wait")
    assert settled["waited_seconds"] < 1 and settled["status"] == "completed"
    diff = session(cid, "diff")
    assert diff["files"] == [{"file": "a.py", "status": "modified", "additions": 3, "deletions": 1}]
    assert session(cid, "diff", patch=True)["files"][0]["patch"] == "x" * 100


# ---------------------------------------------------------------- policy

def test_approval_and_issue_grant_are_separate(fixture):
    _, directory, _, fake = fixture
    assert "approval" in call(directory, agent="build")["error"]
    built = call(directory, agent="build", approval="Client: implement this plan through PR")
    rules = fake.sessions[built["session_id"]]["permissions"]
    assert plugin._decide(rules, "shell", "gh issue create --title x") == "ask"
    updated = call(conversation_id=built["conversation_id"], agent="build",
                   issue_approval="Client: manage this job's Issues")
    assert updated["status"] == "completed", updated
    rules = agent_info("hermes-build")["permissions"] + fake.sessions[built["session_id"]]["permissions"]
    assert plugin._decide(rules, "shell", "gh issue create --title x") == "allow"
    assert plugin._decide(rules, "shell", "gh pr merge 1") == "deny"
    assert plugin._decide(rules, "github_project_item_add", "*") == "deny"


def test_main_rejected_before_launch(fixture):
    _, directory, _, fake = fixture
    subprocess.run(["git", "-C", str(directory), "checkout", "-q", "-b", "main"], check=True)
    assert "default branch" in call(directory, agent="build", approval="Implement")["error"]
    assert not fake.sessions


def test_build_refuses_a_worktree_another_session_is_running_in(fixture):
    _, directory, _, fake = fixture
    fake.sessions["ses_person"] = {"id": "ses_person", "time": {}, "location": {"directory": str(directory)}}
    fake.active.add("ses_person")
    built = call(directory, agent="build", approval="Implement")
    assert built["status"] == "failed" and "already running" in built["error"], built
    assert call(directory)["status"] == "completed"


@pytest.mark.parametrize("role, installed", [("plan", "hermes-plan"), ("build", "hermes-build"),
                                             ("review", "hermes-review"), ("debug", "hermes-debug")])
def test_roles_run_on_hidden_hermes_primaries(fixture, role, installed):
    _, directory, _, fake = fixture
    extra = {"approval": "Implement"} if role == "build" else {}
    result = call(directory, agent=role, **extra)
    assert result["status"] == "completed", result
    assert fake.sessions[result["session_id"]]["agent"] == installed
    assert plugin.OPENCODE_AGENTS[role] == installed


def test_agent_that_lost_its_posture_is_refused(fixture):
    _, directory, _, fake = fixture
    info = agent_info("hermes-review")
    info["permissions"] = info["permissions"] + [{"action": "edit", "resource": "*", "effect": "allow"}]
    fake.agents["hermes-review"] = info
    refused = call(directory, agent="review")
    assert refused["status"] == "failed" and "no longer read-only" in refused["error"]
    fake.agents["hermes-review"] = {**agent_info("hermes-review"), "hidden": False}
    assert "hidden primary" in call(directory, agent="review")["error"]


def configure(home, extra=""):
    (home / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 30\n" + extra)


def test_model_choice_is_any_catalog_model_of_an_allowed_provider(fixture):
    home, directory, _, fake = fixture
    assert "allowed_providers" in call(directory, model="openai/gpt-6-sol")["error"]
    configure(home, "  allowed_models: [openai/gpt-6-sol]\n")
    assert "replaced by allowed_providers" in call(directory)["error"]
    configure(home, "  allowed_providers: [anthropic, openai]\n")
    assert "requires a model" in call(directory, variant="high")["error"]
    assert "plain name" in call(directory, model="openai/gpt-6-sol; rm -rf")["error"]
    assert "allowed_providers" in call(directory, model="xai/grok-4.7")["error"]
    assert "does not offer" in call(directory, model="openai/gpt-9")["error"]
    assert "no tool use" in call(directory, model="openai/gpt-image-3")["error"]
    assert "no variant" in call(directory, model="openai/gpt-6-sol", variant="max")["error"]
    first = call(directory, model="openai/gpt-6-sol", variant="high")
    assert first["status"] == "completed", first
    assert first["model"] == "openai/gpt-6-sol" and first["variant"] == "high"
    assert fake.sessions[first["session_id"]]["model"] == {"providerID": "openai", "id": "gpt-6-sol",
                                                            "variant": "high"}
    resumed = call(conversation_id=first["conversation_id"])
    assert resumed["status"] == "completed" and resumed["engine"] == "openai/gpt-6-sol#high"


def test_configured_role_model_carries_its_variant(fixture):
    home, directory, _, fake = fixture
    configure(home, "  models: {plan: 'openai/gpt-6.1-sol#high'}\n")
    first = call(directory)
    assert first["status"] == "completed" and first["engine"] == "openai/gpt-6.1-sol#high", first
    configure(home, "  models: {plan: 'openai/gpt-6.1-sol#high'}\n  allowed_providers: [openai]\n")
    override = call(directory, variant="medium")
    assert override["engine"] == "openai/gpt-6.1-sol#medium", override
    configure(home, "  models: {plan: 'openai/gpt-6.1-sol#bad variant'}\n")
    assert "opencode_cli.models" in call(directory)["error"]


def test_recorded_variant_without_model_is_refused_at_dispatch(fixture):
    home, directory, _, _ = fixture
    configure(home, "  models: {plan: openai/gpt-6-sol}\n")
    first = call(directory, variant="high")
    assert first["status"] == "completed" and "model" not in first, first
    configure(home)
    stale = call(conversation_id=first["conversation_id"])
    assert stale["status"] == "failed" and "no model to bind" in stale["error"], stale


def test_callers_own_models_are_refused_for_every_role(fixture, monkeypatch):
    home, directory, _, _ = fixture
    monkeypatch.setattr(plugin, "CALLER_MODELS", {})
    (home / "config.yaml").write_text("model:\n  default: claude-opus-5-5\n  provider: anthropic\n"
                                      "opencode_cli:\n  enabled: true\n  timeout: 30\n"
                                      "  allowed_providers: [anthropic, openai]\n")
    pinned = call(directory)
    assert pinned["status"] == "failed" and "your own model" in pinned["error"], pinned
    assert "your own model" in call(directory, model="anthropic/claude-opus-5-5-fast")["error"]
    # A fallback the caller answered with last counts too, keyed by its Hermes session.
    plugin._observe(session_id="hermes-1", model="claude-fable-5-1", provider="anthropic")
    args = dict(agent="plan", message="Inspect", directory=str(directory), model="anthropic/claude-fable-5-1")
    assert "your own model" in json.loads(plugin.opencode_call(args, session_id="hermes-1"))["error"]
    elsewhere = json.loads(plugin.opencode_call(args, session_id="hermes-2"))
    assert elsewhere["status"] == "completed", elsewhere
    build = call(directory, agent="build", approval="Client approved: fix the typo",
                 model="openai/gpt-6.1-sol")
    assert build["status"] == "completed", build


def test_model_key_folds_speed_tiers_and_snapshots():
    key = plugin._model_key
    assert key("anthropic/claude-opus-5-5") == key("claude-opus-5-5-fast") == key("claude-opus-5-5")
    assert key("claude-haiku-4-5-20251001") == key("claude-haiku-4-5")
    assert key("openrouter/xiaomi/mimo-v2.5") == key("mimo-v2.5")
    assert key("claude-opus-5") != key("claude-opus-5-5")


def test_models_lists_allowed_tool_models_defaults_and_your_own(fixture, monkeypatch):
    home, _, _, _ = fixture
    monkeypatch.setattr(plugin, "CALLER_MODELS", {})
    (home / "config.yaml").write_text("model:\n  default: claude-opus-5-5\n"
                                      "opencode_cli:\n  enabled: true\n  allowed_providers: [anthropic, openai]\n"
                                      "  models: {review: 'anthropic/claude-fable-5-1#high'}\n")
    listed = json.loads(plugin.opencode_session({"action": "models"}))
    names = [m["model"] for m in listed["models"]]
    assert "xai/grok-4.7" not in names and "openai/gpt-image-3" not in names
    assert {"anthropic/claude-opus-5-5", "openai/gpt-6.1-sol"} <= set(names)
    mine = {m["model"] for m in listed["models"] if m.get("yours")}
    assert mine == {"anthropic/claude-opus-5-5", "anthropic/claude-opus-5-5-fast"}
    sol = next(m for m in listed["models"] if m["model"] == "openai/gpt-6.1-sol")
    assert sol["variants"] == ["medium", "high"] and sol["context"] == 400000
    assert sol["cost_per_mtok"] == {"input": 2, "output": 10}
    assert listed["defaults"]["review"] == "anthropic/claude-fable-5-1#high"
    assert listed["defaults"]["build"] == "openai/gpt-6.1-sol#medium"


def test_registration_observes_the_callers_model():
    hooks, tools = [], []

    class Context:
        profile_name = "engineer"

        def register_hook(self, name, callback):
            hooks.append((name, callback))

        def register_tool(self, **kwargs):
            tools.append(kwargs["name"])

    plugin.register(Context())
    assert hooks == [("post_api_request", plugin._observe)]
    assert {"opencode_call", "opencode_session", "opencode_history"} <= set(tools)


# ---------------------------------------------------------------- provider limits

def scripted(fake, *steps):
    """Script the next session the service creates."""
    real = fake._route

    def route(method, parts, query, data):
        out = real(method, parts, query, data)
        if parts == ["session"] and method == "post":
            fake.scripts[out["data"]["id"]] = list(steps)
        return out
    fake._route = route


def test_failed_turn_says_why_and_what_to_do(fixture):
    _, directory, _, fake = fixture
    scripted(fake, "fail-error:The usage limit has been reached")
    failed = call(directory)
    assert failed["status"] == "failed", failed
    assert failed["provider_error"] == {"kind": "limit", "message": "The usage limit has been reached",
                                        "model": "anthropic/claude-opus-5-5"}
    assert "usage limit has been reached" in failed["error"] and "another model" in failed["error"]
    scripted(fake, "finish:failed:")
    plain = call(directory)
    assert plain["status"] == "failed" and "provider_error" not in plain
    assert plain["error"] == "OpenCode reported a failed turn; partial effects may exist"


def test_provider_problems_are_classified():
    problem = plugin._provider_problem
    assert problem({"type": "provider.error", "message": "Our servers are currently overloaded."}, None)["kind"] == "limit"
    assert problem({"name": "APIError", "data": {"message": "Too Many Requests", "statusCode": 429}},
                   {"providerID": "anthropic", "id": "claude-sonnet-5-5"}) == {
        "kind": "limit", "message": "Too Many Requests", "model": "anthropic/claude-sonnet-5-5"}
    assert problem({"type": "unknown", "message": "Claude Code credentials are unavailable or expired."},
                   None)["kind"] == "auth"
    assert problem({"type": "provider.error", "message": "Not Found"}, None)["kind"] == "other"


def test_limit_retry_hands_back_once_then_waits_on(fixture):
    _, directory, _, fake = fixture
    scripted(fake, "retry:Rate limit exceeded:1", "hold")
    first = call(directory)
    assert first["status"] == "running" and not first["timed_out"], first
    assert first["retrying"]["kind"] == "limit" and first["retrying"]["attempt"] == 1
    assert first["retrying"]["model"] == "anthropic/claude-opus-5-5" and not first["retrying"]["subagent"]
    assert "keeps retrying" in first["note"] and "opencode_session models" in first["note"]
    cid, sid = first["conversation_id"], first["session_id"]
    # The same episode does not hand back again, even as its attempts grow.
    fake.scripts[sid] = ["retry:Rate limit exceeded:2", "hold"]
    again = session(cid, "wait", timeout=1)
    assert again["timed_out"] and again["retrying"]["attempt"] == 2, again
    fake.scripts[sid] = ["unretry", "finish"]
    done = session(cid, "wait")
    assert done["status"] == "completed" and "retrying" not in done, done


def test_transient_retry_hands_back_only_after_some_attempts(fixture, monkeypatch):
    _, directory, _, fake = fixture
    seen = []
    real = plugin._retrying

    def spy(*args):
        found = real(*args)
        seen.append(found and found["attempt"])
        return found
    monkeypatch.setattr(plugin, "_retrying", spy)
    # A 502 is OpenCode's to ride out at first: the blocking call keeps waiting.
    scripted(fake, "retry:Bad Gateway:1", "retry:Bad Gateway:2", "retry:Bad Gateway:3", "hold")
    third = call(directory)
    assert {1, 2} <= set(seen), seen
    assert third["retrying"]["kind"] == "other" and third["retrying"]["attempt"] == 3, third
    session(third["conversation_id"], "stop")


def test_subagent_retry_hands_back_with_its_session(fixture):
    _, directory, _, fake = fixture
    scripted(fake, "hold")
    real = fake._route
    child = "ses_child1abc"

    def route(method, parts, query, data):
        out = real(method, parts, query, data)
        if parts[:3] == ["session", "active"] or parts == ["session", "active"]:
            root = next((s for s in fake.sessions if s != child and "fork" not in s), None)
            if root and child not in fake.sessions:
                fake.sessions[child] = {"id": child, "parentID": root, "agent": "explore-medium", "time": {},
                                        "model": {"providerID": "anthropic", "id": "claude-sonnet-5-5"}}
                fake.messages[child] = []
                fake.retry(child, "usage limit reached", 1)
                fake.active.add(child)
                out["data"][child] = {"type": "running"}
        return out
    fake._route = route
    first = call(directory)
    assert first["retrying"]["subagent"] and first["retrying"]["session_id"] == child, first
    assert first["retrying"]["model"] == "anthropic/claude-sonnet-5-5"
    assert "a subagent of the run" in first["note"]
    session(first["conversation_id"], "stop")


# ---------------------------------------------------------------- ownership and gates

def test_foreign_owner_cannot_access_resume_or_respond(fixture, monkeypatch):
    home, directory, _, _ = fixture
    first = call(directory)
    other = {"profile": "engineer", "session_id": "client-b", "routing_digest": "b"}
    monkeypatch.setattr(plugin, "_scope", lambda: (home, other, False))
    assert "another originating session" in session(first["conversation_id"])["error"]
    assert "another originating session" in call(conversation_id=first["conversation_id"])["error"]
    assert "another originating session" in session(first["conversation_id"], "respond", request_id="per_x",
                                                     decision="once")["error"]
    assert json.loads(plugin.opencode_session({"action": "list"})) == []


def test_unknown_arguments_and_nonrepo_fail_before_execution(fixture, tmp_path):
    _, directory, _, fake = fixture
    assert "Unexpected" in call(directory, executable="/bin/sh")["error"]
    plain = tmp_path / "plain"
    plain.mkdir()
    assert "error" in call(plain)
    assert not fake.sessions


def test_revoked_config_blocks_new_calls_but_keeps_owned_inspection(fixture):
    home, directory, _, _ = fixture
    result = call(directory)
    (home / "config.yaml").write_text("opencode_cli:\n  enabled: false\n")
    assert "not enabled" in call(directory)["error"]
    assert session(result["conversation_id"])["status"] == "completed"


def test_reconcile_only_turn_refuses_execution(fixture, monkeypatch):
    _, directory, _, _ = fixture
    first = call(directory)
    monkeypatch.setenv("RESIDENT_TURN_KIND", "reconcile")
    assert "reconcile-only" in call(directory)["error"]
    assert "reconcile-only" in call(conversation_id=first["conversation_id"])["error"]


def test_legacy_records_block_until_reconciled_and_never_resume(fixture):
    home, directory, owner, _ = fixture
    root = plugin._root(home)
    cid, job = "c" * 32, "d" * 32
    plugin.dispatch._write(root / (cid + ".json"), {
        "conversation_id": cid, "job_id": job, "owner": owner, "directory": str(directory), "branch": "topic",
        "agent": "build", "status": "unknown", "pgid": None, "log": "/old/events"})
    assert "active or uncertain" in call(directory)["error"]
    assert "OpenCode 1 runner" in call(conversation_id=cid)["error"]
    assert session(cid)["log"] == "/old/events"
    assert "evidence" in session(cid, "reconcile")["error"]
    done = session(cid, "reconcile", evidence="git status clean; no remote branch; no process")
    assert done["status"] == "reconciled"
    assert "OpenCode 1 runner" in call(conversation_id=cid)["error"]
    assert call(directory)["status"] == "completed"


def test_reconcile_refuses_watched_or_still_running_runs(fixture):
    home, directory, owner, fake = fixture
    (home / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 30\n  wait_timeout: 1\n")
    fake.scripts["ses_1abc"] = ["hold"]
    running = call(directory)
    assert "still checking" in session(running["conversation_id"], "reconcile", evidence="x")["error"]
    session(running["conversation_id"], "stop")
    assert settle(running["conversation_id"])["status"] == "interrupted"


def test_registry_symlink_refused(fixture):
    home, directory, _, _ = fixture
    (home / "opencode-sessions").symlink_to(directory, target_is_directory=True)
    assert "symlink" in call(directory)["error"]


@pytest.mark.parametrize("profile", ["writer", "creator", "marketer", "researcher", "default"])
def test_registration_is_engineer_and_assistant_only(profile):
    class Context:
        profile_name = profile

        def register_tool(self, **kwargs):
            raise AssertionError("foreign profile gained OpenCode tools")

    plugin.register(Context())


def test_assistant_home_runs_its_own_registry(fixture, monkeypatch):
    home, directory, _, _ = fixture
    assistant = home.parent / "assistant"
    assistant.mkdir()
    (assistant / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 30\n")
    owner = {"profile": "assistant", "session_id": "client-b", "routing_digest": "b"}
    monkeypatch.setattr(plugin, "_scope", lambda: (assistant, owner, False))
    result = call(directory)
    assert result["status"] == "completed", result
    assert (assistant / "opencode-sessions" / (result["conversation_id"] + ".json")).exists()
    assert not (home / "opencode-sessions").exists() or not list((home / "opencode-sessions").glob("*.json"))
    creator = home.parent / "creator"
    creator.mkdir()
    (creator / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 30\n")
    with pytest.raises(ValueError, match="caller home"):
        plugin._watch(creator, "a" * 32, "b" * 32)


def test_live_callers_get_a_notifier_per_handback(fixture, monkeypatch):
    home, directory, owner, fake = fixture
    monkeypatch.setattr(plugin, "_scope", lambda: (home, owner, True))
    launched = []
    monkeypatch.setattr(plugin, "_launch_notifier", lambda h, cid, job, task: launched.append((cid, job)) or "proc_1")
    fake.scripts["ses_1abc"] = ["ask", "finish"]
    started = call(directory)
    assert started["process_session_id"] == "proc_1" and started["status"] == "running"
    cid = started["conversation_id"]
    deadline = time.time() + 5
    while session(cid)["status"] != "waiting" and time.time() < deadline:
        time.sleep(0.02)
    notified = plugin._notify(home, cid, started["job_id"])
    assert notified["status"] == "waiting"
    answered = session(cid, "respond", request_id=notified["pending"][0]["id"], decision="once")
    assert answered["process_session_id"] == "proc_1" and len(launched) == 2
    assert plugin._notify(home, cid, started["job_id"])["status"] == "completed"


# ---------------------------------------------------------------- ruleset and agent files

def test_session_ruleset_holds_no_broad_allow():
    """Subagent sessions copy the ruleset and OpenCode applies it after their own
    posture, so an allow here would reopen what a subagent denies itself."""
    scratch, readable = plugin._directories("/tmp/fake-opencode")
    narrow = set(scratch + readable) | set(plugin.SAMPLE_READS) | set(plugin.BUILD_ALLOW_AFTER_ASK)
    for role in plugin.AGENTS:
        for issue in (None, "granted"):
            rules = plugin._rules(role, issue, {"main"}, tmp="/tmp/fake-opencode")
            assert {r["resource"] for r in rules if r["effect"] == "allow"} <= narrow, role
            assert plugin._decide(rules, "question", "*") == "deny"
            for secret in (".env", "app/.env", ".env.local", "key.pem", ".ssh/id_rsa", ".envrc"):
                assert plugin._decide(rules, "read", secret) == "deny", (role, secret)
            assert plugin._decide(rules, "read", ".env.example") == "allow"
            assert plugin._decide(rules, "external_directory", "/somewhere/else/*") == "ask"
            assert plugin._decide(rules, "external_directory", "/tmp/fake-opencode/*") == "allow"
            for command in ("git push --force origin topic", "git push origin main", "git -C x push origin main",
                            "gh pr merge 3", "gh api repos/x", "git reset --hard HEAD~1"):
                assert plugin._decide(rules, "shell", command) == "deny", (role, command)


def test_build_asks_for_person_gated_commands_and_keeps_person_denies():
    person = PERSON_DENIES + [{"action": "shell", "resource": "ls *", "effect": "allow"}]
    rules = plugin._rules("build", None, {"main"}, tmp="/tmp/fake-opencode", person_denies=person)
    assert {"action": "shell", "resource": "ls *", "effect": "deny"} not in rules
    combined = agent_info("hermes-build")["permissions"] + rules
    for command in ("git push origin topic", "git rebase main", "git checkout other", "git -C .. status x",
                    "npm exec foo", "gh issue comment 1"):
        expected = "allow" if command.startswith("git -C .. status") else "ask"
        assert plugin._decide(combined, "shell", command) == expected, command
    assert plugin._decide(combined, "shell", "pytest -q") == "allow"
    assert plugin._decide(combined, "shell", "sudo rm -rf /") == "deny"
    assert plugin._decide(combined, "edit", "src/a.py") == "allow"
    # The person's outside-path denies stay denies (not caller-approvable asks)
    # without shadowing OpenCode's own scratch dirs, which are allowed after them.
    assert plugin._decide(rules, "external_directory", "/secret/x/*") == "deny"
    assert plugin._decide(rules, "external_directory", "/tmp/fake-opencode/*") == "allow"


def test_shell_wildcards_follow_opencode():
    rules = [{"action": "shell", "resource": "*", "effect": "deny"},
             {"action": "shell", "resource": "git status *", "effect": "allow"}]
    assert plugin._decide(rules, "shell", "git status") == "allow"
    assert plugin._decide(rules, "shell", "git status --short") == "allow"
    assert plugin._decide(rules, "shell", "git statusx") == "deny"
    assert plugin._decide([], "read", "x") == "ask"


ROLE_SUBAGENTS = {
    "hermes-plan": {"explore*", "searcher*"},
    "hermes-review": {"explore*", "searcher*", "reviewer*", "verifier"},
    "hermes-debug": {"explore*", "searcher*", "debugger", "verifier"},
    "hermes-build": {"explore*", "searcher*", "verifier", "worker", "reviewer", "reviewer-deep"},
}


@pytest.mark.parametrize("installed", sorted(ROLE_SUBAGENTS))
def test_agent_files_own_the_role_posture(installed):
    """Each hidden primary's frontmatter is the one owner of its posture; the
    plugin's ruleset only constrains. A read-only role starts from a full deny
    (which also shadows the person's global allows, so it names every tool it needs)."""
    text = (AGENT_DIR / f"{installed}.md").read_text()
    frontmatter = plugin.yaml.safe_load(text.split("---\n", 2)[1])
    assert frontmatter["mode"] == "primary" and frontmatter["hidden"] is True
    assert "permission" not in frontmatter, "V1 maps do not hold on OpenCode 2; use permissions"
    rules = frontmatter["permissions"]
    allowed = {r["resource"] for r in rules if r["action"] == "subagent" and r["effect"] == "allow"}
    assert allowed == ROLE_SUBAGENTS[installed]
    assert "opencode run" not in text
    role = next(r for r, name in plugin.OPENCODE_AGENTS.items() if name == installed)
    combined = agent_info(installed)["permissions"] + plugin._rules(role, None, {"main"})
    if role in plugin.READ_ONLY:
        assert rules[0] == {"action": "*", "resource": "*", "effect": "deny"}
        for action, resource in (("edit", "a.py"), ("shell", "touch x"), ("subagent", "worker"),
                                 ("execute", "*")):
            assert plugin._decide(combined, action, resource) == "deny", (installed, action)
        for action, resource in (("read", "src/a.py"), ("grep", "x"), ("skill", "git-commit"),
                                 ("shell", "git log --oneline"), ("git_provenance", "*")):
            assert plugin._decide(combined, action, resource) == "allow", (installed, action)
    plugin._check_agent(role, agent_info(installed), plugin._rules(role, None, {"main"}))


# ---------------------------------------------------------------- shared transport (specialist-call)

def test_nonstandard_remote_default_is_protected(monkeypatch):
    monkeypatch.setattr(plugin, "_git", lambda *args: "origin")

    def run(command, **kwargs):
        if "ls-remote" in command:
            return subprocess.CompletedProcess(command, 0, "ref: refs/heads/trunk\tHEAD\n", "")
        if command[-1] == "HEAD":
            return subprocess.CompletedProcess(command, 0, "trunk\n", "")
        return subprocess.CompletedProcess(command, 1, "", "")
    monkeypatch.setattr(plugin.subprocess, "run", run)
    with pytest.raises(ValueError, match="default branch"):
        plugin._branch("/fixture", True)


def test_unverified_remote_default_blocks_build(monkeypatch):
    monkeypatch.setattr(plugin, "_git", lambda *args: "origin")

    def run(command, **kwargs):
        if command[-1] == "HEAD" and "symbolic-ref" in command:
            return subprocess.CompletedProcess(command, 0, "topic\n", "")
        return subprocess.CompletedProcess(command, 1, "", "")
    monkeypatch.setattr(plugin.subprocess, "run", run)
    with pytest.raises(ValueError, match="could not be verified"):
        plugin._branch("/fixture", True)


def test_detached_checkout_allows_assessment_not_build(monkeypatch):
    monkeypatch.setattr(plugin, "_git", lambda *args: "a" * 40)
    monkeypatch.setattr(plugin.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", ""))
    assert plugin._branch("/fixture", False)[0] == "detached:" + "a" * 40
    with pytest.raises(ValueError, match="named task branch"):
        plugin._branch("/fixture", True)


# ---------------------------------------------------------------- api client

def test_api_client_reads_files_not_pipes_and_maps_errors(tmp_path, monkeypatch):
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
    assert len(api.call("get", "/ok", executable=str(fake))["data"]) == 300000
    with pytest.raises(api.ApiError) as error:
        api.call("get", "/missing", executable=str(fake))
    assert error.value.status == 404 and error.value.tag == "SessionNotFoundError"
    with pytest.raises(api.Unavailable):
        api.call("get", "/broken", executable=str(fake))
    assert api.call("post", "/empty", {"a": 1}, executable=str(fake)) is None
    assert api.path("/api/session/{sid}/x", {"from": "msg_1", "skip": None}, sid="ses/../a") == \
        "/api/session/ses%2F..%2Fa/x?from=msg_1"
    assert re.fullmatch(r"location%5Bdirectory%5D=%2Fa\+b",
                        urllib.parse.urlencode(api.location("/a b")))
