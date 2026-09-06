"""No live agents: mocked dispatch plus real runner/resident integration with a fake CLI."""

import contextvars
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import signal
import socket
import sys
import time
import urllib.error
from types import SimpleNamespace

import pytest
import yaml


PLUGIN = Path(__file__).resolve().parents[1] / "__init__.py"
spec = importlib.util.spec_from_file_location("specialist_call_test", PLUGIN)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
A2A = p._a2a
EXECUTE_SYNC = p._execute_sync
RESIDENT_IMPL = p._resident


@pytest.fixture
def caller(tmp_path, monkeypatch):
    home = tmp_path / "profiles" / "assistant"
    home.mkdir(parents=True)
    (home / "config.yaml").write_text(yaml.safe_dump({
        "specialist_call": {"resident_targets": sorted(p.TARGETS["assistant"])},
        "a2a_agents": {"creator": {"url": "http://127.0.0.1:9903", "timeout": 2}},
    }))
    monkeypatch.setattr(p, "_scope", lambda: (home, "owner-one", False, False))
    monkeypatch.setattr(p, "_execute_sync", p._run)
    calls = []

    def resident(home, data, message):
        calls.append(("resident", data["target"], message))
        data.update(status="completed", resident_id="resident-sid", result="resident reply")

    def a2a(home, data, message, peer):
        calls.append(("a2a", data["target"], message))
        data.update(status="completed", backend_id="task-id", result="peer reply")

    monkeypatch.setattr(p, "_resident", resident)
    monkeypatch.setattr(p, "_a2a", a2a)
    return home, calls


def call(target="creator", **args):
    return json.loads(p.specialist_call({"target": target, "message": "hello", "kind": "inquiry", **args}, task_id="task-owner"))


def session(action, cid=None):
    return json.loads(p.specialist_session(dict(action=action, **({"conversation_id": cid} if cid else {}))))


def test_routes_pins_and_never_upgrades_inquiry(caller):
    _, calls = caller
    inquiry = call()
    work = call(kind="work")
    search = call("searcher")
    assert [x["backend"] for x in [inquiry, work, search]] == ["a2a", "resident", "resident"]
    assert call(conversation_id=inquiry["conversation_id"])["context_id"] == inquiry["context_id"]
    assert call(conversation_id=work["conversation_id"])["backend"] == "resident"
    before = len(calls)
    assert "error" in call(conversation_id=inquiry["conversation_id"], kind="work")
    assert "error" in call("writer", conversation_id=work["conversation_id"])
    assert len(calls) == before


@pytest.mark.parametrize("target", ["researcher", "assistant", "../creator", "http://localhost", "creator/../../writer"])
def test_target_policy(caller, target):
    assert "error" in call(target)
    assert not caller[1]


def test_owner_and_profile_isolation(caller, monkeypatch):
    home, calls = caller
    data = call()
    cid = data["conversation_id"]
    monkeypatch.setattr(p, "_scope", lambda: (home, "owner-two", False, False))
    assert session("list") == []
    for action in ["status", "close"]:
        assert "error" in session(action, cid)
    assert "error" in call(conversation_id=cid)
    creator = home.parent / "creator"
    creator.mkdir()
    (creator / "config.yaml").write_text("specialist_call:\n  resident_targets: [researcher]\n")
    monkeypatch.setattr(p, "_scope", lambda: (creator, "owner-one", False, False))
    assert "error" in session("status", cid)
    assert "error" in call()
    assert call("researcher")["backend"] == "resident"
    assert len(calls) == 2


@pytest.mark.parametrize("backend", ["a2a", "resident"])
def test_policy_rechecked_on_every_operation(caller, backend):
    home, calls = caller
    data = call(kind="work" if backend == "resident" else "inquiry")
    (home / "config.yaml").write_text("specialist_call: {resident_targets: []}\n")
    for action in ["status", "close"]:
        assert "error" in session(action, data["conversation_id"])
    assert session("list") == []
    assert "error" in call(conversation_id=data["conversation_id"])
    assert len(calls) == 1


@pytest.mark.parametrize("field,value", [("url", "http://localhost:9999"), ("tenant", "another-agent")])
def test_changed_endpoint_does_not_fallback(caller, field, value):
    home, calls = caller
    data = call()
    config = yaml.safe_load((home / "config.yaml").read_text())
    config["a2a_agents"]["creator"][field] = value
    (home / "config.yaml").write_text(yaml.safe_dump(config))
    assert "error" in call(conversation_id=data["conversation_id"])
    assert len(calls) == 1


def test_timeout_is_unknown_no_second_dispatch(caller, monkeypatch):
    calls = []

    def timeout(*args):
        calls.append(1)
        raise TimeoutError("not proof of remote cancellation")

    monkeypatch.setattr(p, "_a2a", timeout)
    result = call()
    assert result["status"] == "unknown"
    assert result["context_id"] and result["job_id"]
    assert "error" in call(conversation_id=result["conversation_id"])
    assert "error" in session("close", result["conversation_id"])
    assert calls == [1]


def test_inbound_rejects_work_and_resident_before_launch(caller, monkeypatch):
    home, calls = caller
    monkeypatch.setattr(p, "_scope", lambda: (home, "owner-one", False, True))
    assert "reissue" in call(kind="work")["error"]
    assert "reissue" in call("searcher")["error"]
    assert not calls
    assert call()["status"] == "completed"


@pytest.mark.parametrize("value", ["..", "../../other", "http://host", "", "f" * 31])
def test_bad_session_paths(caller, value):
    assert "error" in session("status", value)


def test_identity_cannot_be_supplied(caller):
    assert "error" in call(profile="assistant")
    assert "error" in call(home="/tmp", owner="owner-one")
    assert not caller[1]


def test_initial_kind_must_be_explicit(caller):
    result = json.loads(p.specialist_call({"target": "creator", "message": "render this"}))
    assert "Initial calls require" in result["error"]
    assert not caller[1]
    started = call(kind="work")
    continued = json.loads(p.specialist_call({"target": "creator", "message": "next",
                                            "conversation_id": started["conversation_id"]}))
    assert continued["backend"] == "resident" and continued["status"] == "completed"


def background(caller, monkeypatch):
    home, _ = caller
    monkeypatch.setattr(p, "_scope", lambda: (home, "owner-one", True, False))
    commands = []

    def terminal(**kwargs):
        commands.append(kwargs)
        return json.dumps({"session_id": "process-one", "notify_on_complete": True})

    import tools.terminal_tool
    monkeypatch.setattr(tools.terminal_tool, "terminal_tool", terminal)
    return commands


def test_background_receipt_locks_and_runner(caller, monkeypatch):
    commands = background(caller, monkeypatch)
    result = call(message="untrusted ' ; $(whoami)")
    cid = result["conversation_id"]
    command = commands[0]
    assert command["background"] and command["notify_on_complete"] and command["_host_local"]
    assert command["task_id"] == "task-owner"
    assert "untrusted" not in command["command"]
    assert "error" in call(conversation_id=cid)
    request = Path(shlex.split(command["command"])[-1])
    assert request.stat().st_mode & 0o777 == 0o600
    assert request.parent.stat().st_mode & 0o777 == 0o700
    with p._locked(request.parent, cid):
        with pytest.raises(ValueError, match="busy"):
            p._run(request)
    assert p._run(request)["status"] == "completed"
    assert session("status", cid)["process_session_id"] == "process-one"
    assert not request.exists()
    with pytest.raises(FileNotFoundError):
        p._run(request)
    assert session("close", cid)["status"] == "closed"
    assert "error" in call(conversation_id=cid)


def test_runner_rechecks_policy_and_request_integrity(caller, monkeypatch):
    commands = background(caller, monkeypatch)
    result = call()
    path = Path(shlex.split(commands[0]["command"])[-1])
    req = p._read(path)
    req["owner"] = "spoofed"
    p._write(path, req)
    with pytest.raises(ValueError, match="another"):
        p._run(path)
    req["owner"] = "owner-one"
    req["message"] = "changed"
    p._write(path, req)
    with pytest.raises(ValueError, match="altered"):
        p._run(path)
    req["message"] = "hello"
    p._write(path, req)
    (caller[0] / "config.yaml").write_text("{}")
    assert p._run(path)["status"] == "failed"
    assert not caller[1]


def test_launch_exception_retains_queryable_identity(caller, monkeypatch):
    background(caller, monkeypatch)
    import tools.terminal_tool

    def broken(**kwargs):
        raise TimeoutError()

    monkeypatch.setattr(tools.terminal_tool, "terminal_tool", broken)
    result = call()
    assert result["status"] == "unknown"
    assert result["conversation_id"] and not result["notify_on_complete"]
    assert session("status", result["conversation_id"])["status"] == "unknown"
    assert (caller[0] / "specialist-sessions" / (result["job_id"] + ".request")).exists()
    assert "error" in session("close", result["conversation_id"])
    assert "error" in call(conversation_id=result["conversation_id"])


@pytest.mark.parametrize("profile,platform,source,matching,expected", [
    ("assistant", "telegram", "", True, True),
    ("creator", "discord", "discord", True, True),
    ("assistant", "telegram", "cli", True, None),
    ("assistant", "telegram", "", False, None),
    ("creator", "", "cli", True, False),
    ("creator", "a2a", "", True, False),
    ("writer", "telegram", "", True, None),
])
def test_actual_context_scope(tmp_path, monkeypatch, profile, platform, source, matching, expected):
    from hermes_constants import set_hermes_home_override, reset_hermes_home_override
    from gateway import session_context as sc

    home = tmp_path / "profiles" / profile
    monkeypatch.setattr(sc, "_session_context_engaged", False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "wrong"))

    def check():
        token = set_hermes_home_override(home)
        sc.set_session_vars(platform=platform, source=source, profile=profile if matching else "wrong",
                            session_id="sid", session_key="key", chat_id="chat")
        try:
            if expected is None:
                with pytest.raises(ValueError):
                    p._scope()
            else:
                actual_home, owner, live, inbound = p._scope()
                assert actual_home == home
                assert live is expected
                assert inbound == (platform == "a2a")
        finally:
            reset_hermes_home_override(token)

    contextvars.Context().run(check)


def test_unbound_multiplex_cannot_use_process_routing(tmp_path, monkeypatch):
    from gateway import session_context as sc
    monkeypatch.setattr(sc, "_session_context_engaged", True)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "assistant"))
    monkeypatch.setenv("HERMES_SESSION_ID", "stale")
    with pytest.raises(ValueError, match="task-local"):
        contextvars.Context().run(p._scope)


def test_reset_context_sentinel_cannot_fall_back_to_inherited_route(tmp_path, monkeypatch):
    from gateway import session_context as sc
    from hermes_constants import set_hermes_home_override, reset_hermes_home_override
    monkeypatch.setattr(sc, "_session_context_engaged", True)
    monkeypatch.setenv("HERMES_SESSION_ID", "stale-owner")
    monkeypatch.setenv("HERMES_SESSION_PLATFORM", "telegram")
    monkeypatch.setenv("HERMES_SESSION_PROFILE", "assistant")

    def check():
        token = set_hermes_home_override(tmp_path / "profiles" / "assistant")
        try:
            sc.reset_session_vars()
            with pytest.raises(ValueError, match="caller context"):
                p._scope()
        finally:
            reset_hermes_home_override(token)

    contextvars.Context().run(check)


@pytest.mark.parametrize("exit_code", [0, 3])
def test_runner_real_subprocess_scrubs_injected_scope(caller, monkeypatch, tmp_path, exit_code):
    commands = background(caller, monkeypatch)
    result = call(kind="work")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    binary = bindir / "hermes"
    binary.write_text(f"#!{sys.executable}\n" + "import json, os, sys\n"
                      "print(json.dumps({'args': sys.argv[1:], 'env': {k:v for k,v in os.environ.items() "
                      "if k.startswith(('HERMES_', 'RESIDENT_')) or k == 'TURN_TIMEOUT'}}))\n"
                      "print('session_id: child-session', file=sys.stderr)\n"
                      f"sys.exit({exit_code})\n")
    binary.chmod(0o755)
    env = {**os.environ, "PATH": f"{bindir}:/usr/bin:/bin", "HERMES": "/not/a/binary",
           "HERMES_HOME": "/spoof/profiles/writer", "HERMES_SESSION_PROFILE": "writer",
           "HERMES_SESSION_PLATFORM": "telegram", "HERMES_SESSION_ID": "stale-owner",
           "HERMES_SESSION_SOURCE": "telegram", "HERMES_KANBAN_TASK": "spoofed",
           "RESIDENT_SESSION_DIR": str(tmp_path / "wrong"), "TURN_TIMEOUT": "0"}
    run = subprocess.run(shlex.split(commands[0]["command"]), env=env, capture_output=True, text=True, timeout=15)
    assert run.returncode == exit_code, run.stderr
    data = json.loads(run.stdout)
    assert data["status"] == ("completed" if exit_code == 0 else "failed")
    assert data["exit_code"] == exit_code
    if exit_code:
        assert "rc=3" in data["error"]
        assert "child-session" in Path(data["log"]).read_text()
        return
    assert data["resident_id"] == "child-session"
    child = json.loads(data["result"])
    assert child["args"][:2] == ["-p", "creator"]
    assert not any(k.startswith("HERMES_") for k in child["env"])
    assert child["env"]["RESIDENT_SESSION_DIR"] == str(caller[0] / "resident-sessions")
    assert child["env"]["TURN_TIMEOUT"] == "5400"
    registry = caller[0] / "resident-sessions" / (result["conversation_id"] + ".json")
    assert p._read(registry)["session_id"] == "child-session"
    assert not (tmp_path / "wrong").exists()

    # Execute a continuation synchronously through the real resident adapter,
    # as a one-shot CLI caller would, without using the terminal seam at all.
    monkeypatch.setattr(p, "_scope", lambda: (caller[0], "owner-one", False, False))
    monkeypatch.setattr(p, "_execute_sync", EXECUTE_SYNC)
    # The child runner loaded a fresh module; use that same implementation here.
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)
    monkeypatch.setattr(p, "_resident", fresh._resident)
    monkeypatch.setenv("PATH", env["PATH"])
    resumed = call(conversation_id=result["conversation_id"])
    assert resumed["status"] == "completed"
    assert "--resume" in json.loads(resumed["result"])["args"]
    assert len(commands) == 1


def test_registration_is_role_gated():
    for profile in ["assistant", "creator", "writer", "engineer", "researcher", "searcher", "default"]:
        tools = []
        p.register(SimpleNamespace(profile_name=profile, register_tool=lambda **kw: tools.append(kw)))
        assert len(tools) == (2 if profile in p.TARGETS else 0)
        for tool in tools:
            assert tool["toolset"] == "specialist"
            assert tool["schema"]["parameters"]["additionalProperties"] is False


@pytest.mark.parametrize("state,status", [
    ("TASK_STATE_COMPLETED", "completed"),
    ("TASK_STATE_INPUT_REQUIRED", "input_required"),
    ("TASK_STATE_REJECTED", "failed"),
    ("TASK_STATE_FAILED", "unknown"),
    ("TASK_STATE_WORKING", "unknown"),
])
def test_real_a2a_wire_and_structured_identity(caller, monkeypatch, state, status):
    from plugins.platforms.a2a import protocol
    monkeypatch.setattr(p, "_a2a", A2A)
    sent = []

    def open_request(request, timeout):
        body = json.loads(request.data)
        sent.append((request, timeout, body))
        context_id = body["params"]["message"]["contextId"]
        payload = protocol.build_task("server-task", context_id, state,
                                      "reply text claiming context FAKE must not affect routing")
        response = {"jsonrpc": "2.0", "id": body["id"], "result": {"task": payload}}
        return io.BytesIO(json.dumps(response).encode())

    monkeypatch.setattr(p.urllib.request, "build_opener", lambda *a: SimpleNamespace(open=open_request))
    result = call()
    assert result["status"] == status
    assert result["backend_id"] == "server-task"
    request, timeout, body = sent[0]
    assert request.full_url == "http://127.0.0.1:9903"
    assert timeout == 2 and request.method == "POST"
    assert body["method"] == "SendMessage"
    assert body["id"] == result["job_id"]
    assert body["params"]["message"]["contextId"] == result["context_id"]
    assert len(sent) == 1
    if status == "unknown":
        assert "error" in call(conversation_id=result["conversation_id"])
        assert len(sent) == 1


@pytest.mark.parametrize("problem", ["timeout", "wrong_id", "wrong_context", "rpc_error"])
def test_a2a_uncertain_transport_never_dispatches_again(caller, monkeypatch, problem):
    monkeypatch.setattr(p, "_a2a", A2A)
    sent = []

    def open_request(request, timeout):
        body = json.loads(request.data)
        sent.append(body)
        if problem == "timeout":
            raise TimeoutError()
        response = {"id": "wrong" if problem == "wrong_id" else body["id"],
                    "result": {"message": {"messageId": "server-id", "contextId": "wrong"}}}
        if problem == "rpc_error":
            response["error"] = {"code": -32603, "message": "Internal error"}
        return io.BytesIO(json.dumps(response).encode())

    monkeypatch.setattr(p.urllib.request, "build_opener", lambda *a: SimpleNamespace(open=open_request))
    result = call()
    assert result["status"] == "unknown"
    assert not caller[1]
    assert "error" in call(conversation_id=result["conversation_id"])
    assert len(sent) == 1


def test_redirect_is_refused():
    with pytest.raises(ValueError, match="redirect"):
        p._NoRedirect().redirect_request(None, None, 302, "", {}, "http://other")


def test_initial_and_continuation_are_locked_during_dispatch(caller, monkeypatch):
    seen = []

    def dispatch(home, data, message):
        cid = data["conversation_id"]
        assert "error" in call(conversation_id=cid, kind="work")
        assert "error" in session("close", cid)
        assert session("status", cid)["status"] == "running"
        seen.append(cid)
        data.update(status="completed", resident_id="sid")

    monkeypatch.setattr(p, "_resident", dispatch)
    result = call(kind="work")
    assert result["status"] == "completed"
    assert call(conversation_id=result["conversation_id"])["status"] == "completed"
    assert seen == [result["conversation_id"]] * 2


def test_registry_symlink_is_refused(caller, tmp_path):
    home, calls = caller
    other = tmp_path / "other"
    other.mkdir()
    (home / "specialist-sessions").symlink_to(other, target_is_directory=True)
    assert "error" in call()
    assert not calls and not list(other.iterdir())


def test_live_requires_explicit_home_and_async_support(tmp_path, monkeypatch):
    from gateway import session_context as sc
    from hermes_constants import set_hermes_home_override, reset_hermes_home_override
    monkeypatch.setattr(sc, "_session_context_engaged", False)
    home = tmp_path / "profiles" / "assistant"
    monkeypatch.setenv("HERMES_HOME", str(home))

    def check():
        sc.set_session_vars(platform="telegram", profile="assistant", session_id="sid", session_key="key", chat_id="chat")
        with pytest.raises(ValueError, match="profile home"):
            p._scope()
        token = set_hermes_home_override(home)
        try:
            sc.declare_stateless_channel()
            with pytest.raises(ValueError, match="delivery context"):
                p._scope()
        finally:
            reset_hermes_home_override(token)

    contextvars.Context().run(check)


def test_cli_has_no_ambient_async_promise(tmp_path, monkeypatch):
    from gateway import session_context as sc
    monkeypatch.setattr(sc, "_session_context_engaged", False)
    for name in sc._VAR_MAP:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "creator"))
    monkeypatch.setenv("HERMES_SESSION_ID", "nested-sid")
    monkeypatch.setenv("HERMES_SESSION_SOURCE", "cli")
    assert contextvars.Context().run(p._scope)[2:] == (False, False)


def test_profile_configuration_and_plugin_api():
    from hermes_cli.plugins import PluginContext
    import inspect

    root = PLUGIN.parents[2]
    manifest = yaml.safe_load(PLUGIN.with_name("plugin.yaml").read_text())
    assert manifest["name"] == "specialist-call" and manifest["kind"] == "standalone"
    paths = [root / "profiles/assistant/config.example.yaml", root / "profiles/creator/config.yaml"]
    for path in paths:
        config = yaml.safe_load(path.read_text())
        assert "specialist-call" in config["plugins"]["enabled"]
        assert "specialist" in config["toolsets"]
        assert set(config["specialist_call"]["resident_targets"]) == p.TARGETS[path.parent.name]
        assert config["platform_toolsets"]["a2a"] == config["platform_toolsets"]["cli"]
        registered = []
        p.register(SimpleNamespace(profile_name=path.parent.name, register_tool=lambda **kw: registered.append(kw)))
        for tool in registered:
            inspect.signature(PluginContext.register_tool).bind(None, **tool)


def test_same_session_key_does_not_merge_owners(tmp_path, monkeypatch):
    from gateway import session_context as sc
    from hermes_constants import set_hermes_home_override, reset_hermes_home_override
    monkeypatch.setattr(sc, "_session_context_engaged", False)

    def owner(profile, session_id, chat_id):
        token = set_hermes_home_override(tmp_path / "profiles" / profile)
        try:
            sc.set_session_vars(platform="telegram", profile=profile, session_id=session_id,
                                session_key="same-key", chat_id=chat_id)
            return p._scope()[1]
        finally:
            reset_hermes_home_override(token)

    owners = [contextvars.Context().run(owner, *args) for args in [
        ("assistant", "session-one", "chat-one"), ("assistant", "session-two", "chat-one"),
        ("assistant", "session-one", "chat-two"), ("creator", "session-one", "chat-one"),
    ]]
    assert len({item["routing_digest"] for item in owners}) == 4
    assert owners[0]["session_id"] == "session-one"


@pytest.mark.parametrize("platform", ["telegram", "discord"])
@pytest.mark.parametrize("mode,allowed", [("single", True), ("config", False), ("env", False),
                                         ("ambiguous", False), ("runtime", False), ("mismatch", False)])
def test_registered_single_profile_gateway(tmp_path, monkeypatch, platform, mode, allowed):
    from gateway import session_context as sc
    from agent import secret_scope
    from hermes_constants import set_hermes_home_override, reset_hermes_home_override
    home = tmp_path / "profiles" / "assistant"
    home.mkdir(parents=True)
    (home / "config.yaml").write_text("gateway:\n  multiplex_profiles: " + ("true" if mode == "config" else "false"))
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(secret_scope, "is_multiplex_active", lambda: mode == "runtime")
    monkeypatch.setenv("GATEWAY_MULTIPLEX_PROFILES", {"env": "true", "ambiguous": "not-a-bool"}.get(mode, ""))
    monkeypatch.setattr(sc, "_session_context_engaged", False)

    def check():
        token = set_hermes_home_override(None)
        try:
            tools = []
            p.register(SimpleNamespace(profile_name="assistant", register_tool=lambda **kw: tools.append(kw)))
            sc.set_session_vars(platform=platform, source="", profile="creator" if mode == "mismatch" else "",
                                session_id="gateway-session", session_key="gateway-key", chat_id="chat")
            original = p.specialist_call
            # Exercise the registration closure and the real upstream ContextVars,
            # stopping at the scope boundary so this test cannot launch a process.
            found = []
            monkeypatch.setattr(p, "specialist_call", lambda *a, **kw: found.append(p._scope()))
            tools = []
            p.register(SimpleNamespace(profile_name="assistant", register_tool=lambda **kw: tools.append(kw)))
            if allowed:
                tools[0]["handler"]({})
                assert found[0][0] == home and found[0][2] is True
            else:
                with pytest.raises(ValueError):
                    tools[0]["handler"]({})
            monkeypatch.setattr(p, "specialist_call", original)
        finally:
            reset_hermes_home_override(token)

    contextvars.Context().run(check)


@pytest.mark.parametrize("status,expected", [(s, "failed") for s in
    ["blocked", "rejected", "error", "pending_approval", "disabled", "degraded"]])
def test_terminal_rejection_is_persisted_and_closable(caller, monkeypatch, status, expected):
    background(caller, monkeypatch)
    import tools.terminal_tool
    monkeypatch.setattr(tools.terminal_tool, "terminal_tool", lambda **kw: json.dumps({"status": status, "exit_code": -1, "error": "refused"}))
    result = call(kind="work")
    assert result["status"] == expected and not result["notify_on_complete"]
    root = caller[0] / "specialist-sessions"
    data = p._read(root / (result["conversation_id"] + ".json"))
    assert data["status"] == expected
    assert (root / (result["job_id"] + ".request")).exists() == (expected == "unknown")
    closed = session("close", result["conversation_id"])
    if expected == "failed":
        assert closed["status"] == "closed"
    else:
        assert "error" in closed


@pytest.mark.parametrize("problem", ["url", "port", "auth", "refused", "dns", "read_timeout", "spawn"])
def test_preflight_vs_uncertain_failures(caller, monkeypatch, problem):
    home, calls = caller
    monkeypatch.setattr(p, "_a2a", A2A)
    config = yaml.safe_load((home / "config.yaml").read_text())
    if problem == "url":
        config["a2a_agents"]["creator"]["url"] = "file:///tmp/agent"
    if problem == "port":
        config["a2a_agents"]["creator"]["url"] = "http://localhost:bad"
    if problem == "auth":
        config["a2a_agents"]["creator"]["auth"] = {"type": "wrong"}
    (home / "config.yaml").write_text(yaml.safe_dump(config))

    def open_request(*a, **kw):
        if problem == "refused":
            raise urllib.error.URLError(ConnectionRefusedError())
        if problem == "dns":
            raise urllib.error.URLError(socket.gaierror())
        if problem == "read_timeout":
            raise TimeoutError()
        pytest.fail("Preflight attempted HTTP")

    monkeypatch.setattr(p.urllib.request, "build_opener", lambda *a: SimpleNamespace(open=open_request))
    if problem == "spawn":
        monkeypatch.setattr(p, "_resident", RESIDENT_IMPL)
        monkeypatch.setattr(p.subprocess, "Popen", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()))
    result = call(kind="work" if problem == "spawn" else "inquiry")
    expected = "unknown" if problem == "read_timeout" else "failed"
    assert result["status"] == expected
    assert session("status", result["conversation_id"])["status"] == expected
    if expected == "failed":
        assert session("close", result["conversation_id"])["status"] == "closed"
    else:
        assert "error" in session("close", result["conversation_id"])
    assert not calls


def test_list_keeps_healthy_rows_when_one_target_is_revoked(caller):
    home, _ = caller
    revoked = call()
    healthy = call("writer", kind="work")
    config = yaml.safe_load((home / "config.yaml").read_text())
    config["specialist_call"]["resident_targets"].remove("creator")
    (home / "config.yaml").write_text(yaml.safe_dump(config))
    assert [row["conversation_id"] for row in session("list")] == [healthy["conversation_id"]]
    assert "error" in call(conversation_id=revoked["conversation_id"])


def test_sync_runner_spawn_failure_is_failed_and_closable(caller, monkeypatch):
    monkeypatch.setattr(p, "_execute_sync", EXECUTE_SYNC)
    monkeypatch.setattr(p.subprocess, "Popen", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()))
    result = call(kind="work")
    assert result["status"] == "failed"
    assert session("status", result["conversation_id"])["status"] == "failed"
    assert session("close", result["conversation_id"])["status"] == "closed"
    assert not caller[1]


@pytest.mark.parametrize("envelope,expected", [
    ({"error": "invalid tool arguments"}, "failed"),
    ({"output": "", "exit_code": -1, "error": "spawn/registration failure"}, "unknown"),
    ({"status": "error", "exit_code": -1, "error": "refused"}, "failed"),
    ({"status": "error", "exit_code": -1, "error": "process exists", "pid": 123}, "unknown"),
    ({"error": "process exists", "pid": 123}, "unknown"),
    ({"status": "error", "exit_code": -1, "session_id": "process-one"}, "accepted"),
])
def test_terminal_failure_envelopes(caller, monkeypatch, envelope, expected):
    background(caller, monkeypatch)
    import tools.terminal_tool
    monkeypatch.setattr(tools.terminal_tool, "terminal_tool", lambda **kw: json.dumps(envelope))
    result = call(kind="work")
    assert result["status"] == expected
    assert session("status", result["conversation_id"])["status"] == expected
    request = caller[0] / "specialist-sessions" / (result["job_id"] + ".request")
    assert request.exists() == (expected in {"unknown", "accepted"})
    closed = session("close", result["conversation_id"])
    assert (closed.get("status") == "closed") == (expected == "failed")


@pytest.mark.parametrize("mutated", ["completed", "failed", "input_required"])
def test_post_dispatch_exception_cannot_become_retryable(caller, monkeypatch, mutated):
    def fail_after_dispatch(home, data, message):
        data.update(status=mutated, result="backend ran")
        raise OSError("registry read or process wait failed after execution")

    monkeypatch.setattr(p, "_resident", fail_after_dispatch)
    result = call(kind="work")
    assert result["status"] == "unknown"
    assert session("status", result["conversation_id"])["status"] == "unknown"
    assert "error" in call(conversation_id=result["conversation_id"])
    assert "error" in session("close", result["conversation_id"])


def test_sync_exit_reconciliation_reads_under_lock(caller, monkeypatch):
    commands = background(caller, monkeypatch)
    accepted = call(kind="work")
    path = Path(shlex.split(commands[0]["command"])[-1])
    record = path.parent / (accepted["conversation_id"] + ".json")
    state = p._read(record)
    state["status"] = "running"
    p._write(record, state)
    real_lock = p._locked

    @__import__("contextlib").contextmanager
    def completed_before_lock(root, cid):
        current = p._read(record)
        current.update(status="completed", result="newer durable result")
        p._write(record, current)
        with real_lock(root, cid):
            yield

    monkeypatch.setattr(p, "_locked", completed_before_lock)
    monkeypatch.setattr(p.subprocess, "Popen", lambda *a, **kw: SimpleNamespace(communicate=lambda: ("", "")))
    result = EXECUTE_SYNC(path)
    assert result["status"] == "completed" and result["result"] == "newer durable result"
    assert p._read(record)["status"] == "completed"


def test_real_framework_dispatch_fresh_cached_and_reset_gateway(tmp_path, monkeypatch):
    from gateway import session_context as sc
    from agent.agent_init import _publish_session_id
    from tools.registry import ToolRegistry
    from hermes_constants import set_hermes_home_override, reset_hermes_home_override
    import model_tools
    import tools.terminal_tool

    home = tmp_path / "profiles" / "assistant"
    home.mkdir(parents=True)
    (home / "config.yaml").write_text("specialist_call: {resident_targets: [creator]}\n")
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_SESSION_ID", "wrong-process-session")
    monkeypatch.delenv("GATEWAY_MULTIPLEX_PROFILES", raising=False)
    monkeypatch.setattr(sc, "_session_context_engaged", False)
    registry = ToolRegistry()
    monkeypatch.setattr(model_tools, "registry", registry)
    stamps = []

    def terminal(**kw):
        from tools.terminal_tool_background import _stamp_gateway_routing
        process = SimpleNamespace()
        _stamp_gateway_routing(process, sc.get_session_env)
        stamps.append(process.parent_session_id)
        assert process.watcher_chat_id == "chat1"
        p._run(Path(shlex.split(kw["command"])[-1]))
        return json.dumps({"session_id": "process", "notify_on_complete": True})

    monkeypatch.setattr(tools.terminal_tool, "terminal_tool", terminal)
    monkeypatch.setattr(p, "_resident", lambda home, data, message: data.update(status="completed", result="reply"))

    def dispatch(name, args, sid="agent-session", turn="turn-session"):
        return json.loads(model_tools._execute_tool(
            name, args, args, model_tools._CallIds(task_id=turn, session_id=sid),
            user_task=None, enabled_tools=None, skip_tool_execution_middleware=True))

    def bind():
        # Exact gateway shape: no session_id passed by _set_session_env.
        sc.set_session_vars(platform="telegram", chat_id="chat1", session_key="k", profile="")
        assert sc.get_session_env("HERMES_SESSION_ID") == ""

    def check():
        token = set_hermes_home_override(None)
        try:
            p.register(SimpleNamespace(profile_name="assistant", register_tool=registry.register))
            bind()
            _publish_session_id("agent-session")  # fresh AIAgent constructor path
            first = dispatch("specialist_call", {"target": "creator", "message": "work", "kind": "work"})
            assert first["status"] == "accepted"
            cid = first["conversation_id"]
            bind()  # cached reuse: constructor/publication does not run again
            monkeypatch.setenv("HERMES_SESSION_ID", "wrong-process-session")
            second = dispatch("specialist_call", {"target": "creator", "message": "continue", "conversation_id": cid})
            assert second["status"] == "accepted"
            assert sc.get_session_env("HERMES_SESSION_ID") == ""  # scoped binding restored
            assert stamps == ["agent-session", "agent-session"]
            status_args = {"action": "status", "conversation_id": cid}
            assert dispatch("specialist_session", status_args)["status"] == "completed"
            # Cached agent id can survive a /new switch; gateway task/session id cannot.
            assert "error" in dispatch("specialist_session", status_args, turn="reset-session")
            assert "error" in dispatch("specialist_session", status_args, sid="reset-agent")
            assert "error" in dispatch("specialist_session", status_args, sid=None)
            assert "error" in dispatch("specialist_call", {"target": "creator", "message": "spoof", "kind": "work",
                                                           "session_id": "agent-session"})
            assert len(stamps) == 2
        finally:
            reset_hermes_home_override(token)

    contextvars.Context().run(check)


@pytest.mark.parametrize("end", ["deadline", "parent_killed"])
def test_nested_resident_cleanup_after_outer_exit(tmp_path, end):
    home = tmp_path / "profiles" / "creator"
    home.mkdir(parents=True)
    (home / "config.yaml").write_text("specialist_call:\n  resident_targets: [researcher]\n")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    binary = bindir / "hermes"
    binary.write_text(f"#!{sys.executable}\n" + r'''
import os, sys, json, time, runpy, subprocess
from pathlib import Path
root = Path(os.environ["TEST_ROOT"])
profile = sys.argv[sys.argv.index("-p") + 1]
(root / (profile + ".pid")).write_text(str(os.getpid()))
print("session_id: fake-" + profile, file=sys.stderr, flush=True)
if profile == "researcher":
    (root / "nested-deadline").write_text(os.environ["RESIDENT_DEADLINE"])
    print("researcher partial output", flush=True)
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    (root / "grandchild.pid").write_text(str(child.pid))
    time.sleep(60)
else:
    os.environ["HERMES_HOME"] = str(root / "profiles" / "creator")
    os.environ["HERMES_SESSION_SOURCE"] = "cli"
    os.environ["HERMES_SESSION_ID"] = "outer-session"
    plugin = runpy.run_path(os.environ["TEST_PLUGIN"])
    result = plugin["specialist_call"]({"target": "researcher", "message": "nested", "kind": "work"})
    print(result, flush=True)
    # Keep the outer CLI alive until its own timeout, even if the inner deadline won.
    time.sleep(60)
''')
    binary.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HERMES_", "RESIDENT_"))}
    env.update(TEST_ROOT=str(tmp_path), TEST_PLUGIN=str(PLUGIN), HERMES=str(binary),
               PATH=f"{bindir}:{Path(sys.executable).parent}:/usr/bin:/bin",
               RESIDENT_SESSION_DIR=str(tmp_path / "outer-registry"), TURN_TIMEOUT="6", POLL_INTERVAL="1", KILL_GRACE="1")
    outer = subprocess.Popen(["/bin/sh", str(p.RESIDENT), "start", "outer", "--profile", "creator", "-q", "brief"],
                             env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        until = time.monotonic() + 8
        while not (tmp_path / "grandchild.pid").exists() and time.monotonic() < until:
            time.sleep(0.05)
        assert (tmp_path / "grandchild.pid").exists(), "Nested researcher did not launch"
        if end == "parent_killed":
            os.kill(int((tmp_path / "creator.pid").read_text()), signal.SIGKILL)
        outer.communicate(timeout=18)
        assert outer.returncode != 0
        until = time.monotonic() + 8
        records = list((home / "specialist-sessions").glob("*.json"))
        assert len(records) == 1
        while p._read(records[0])["status"] == "running" and time.monotonic() < until:
            time.sleep(0.05)
        data = p._read(records[0])
        assert data["status"] == "unknown"
        assert float((tmp_path / "nested-deadline").read_text()) <= data["deadline"]
        assert data["deadline"] < time.time() + 7, "Nested call reset the outer deadline"
        for name in ["researcher.pid", "grandchild.pid"]:
            pid = int((tmp_path / name).read_text())
            while time.monotonic() < until:
                state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
                if not state or state.startswith("Z"):
                    break
                time.sleep(0.05)
            assert not state or state.startswith("Z"), "Nested process survived outer exit"
        assert Path(data["log"]).exists()
        assert "researcher partial output" in Path(data["log"]).read_text()
    finally:
        with __import__("contextlib").suppress(ProcessLookupError):
            os.killpg(outer.pid, signal.SIGKILL)
        outer.communicate()
