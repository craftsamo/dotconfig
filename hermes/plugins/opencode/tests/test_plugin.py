import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "__init__.py"
spec = importlib.util.spec_from_file_location("engineer_opencode_test", SOURCE)
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)

FAKE = r'''
import json, os, pathlib, signal, subprocess, sys, time
args = sys.argv[1:]
directory = pathlib.Path(args[args.index("--dir") + 1])
prompt = sys.stdin.read()
behavior = os.environ.get("ENGINEER_FAKE", "ok")
(directory / "invocation.json").write_text(json.dumps({"args": args, "prompt": prompt,
    "permission": json.loads(os.environ["OPENCODE_PERMISSION"])}))
sid = args[args.index("--session") + 1] if "--session" in args else "ses_first"
if "--fork" in args:
    sid = "ses_fork"
def emit(kind, **fields):
    print(json.dumps(dict(type=kind, sessionID=sid, **fields)), flush=True)
emit("step_start", part={"messageID": "msg_a"})
if behavior == "sleep":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(90)"])
    (directory / "child-pid").write_text(str(child.pid))
    time.sleep(90)
elif behavior in {"error", "error-signal"}:
    emit("error", error={"name": "UnknownError", "data": {"message": "probe"}})
    if behavior == "error-signal":
        os.kill(os.getpid(), signal.SIGTERM)
    sys.exit(0)
elif behavior == "malformed":
    print("not-json", flush=True)
elif behavior == "incomplete":
    sys.exit(0)
elif behavior == "wrong-session":
    sid = "ses_foreign"
text = "ASK_CLIENT: choose A or B" if behavior == "question" else "RESULT_OK"
emit("text", part={"messageID": "msg_a", "text": text})
emit("step_finish", part={"messageID": "msg_a", "reason": "stop"})
'''


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    home = tmp_path / "profiles/engineer"
    home.mkdir(parents=True)
    (home / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 10\n")
    directory = tmp_path / "work tree"
    directory.mkdir()
    subprocess.run(["git", "init", "-b", "topic", str(directory)], check=True, capture_output=True)
    binary = tmp_path / "bin"
    binary.mkdir()
    executable = binary / "opencode"
    executable.write_text(f"#!{sys.executable}\n" + FAKE)
    executable.chmod(0o700)
    monkeypatch.setenv("PATH", str(binary) + os.pathsep + os.environ["PATH"])
    owner = {"profile": "engineer", "session_id": "client-a", "routing_digest": "a"}
    monkeypatch.setattr(plugin, "_scope", lambda: (home, owner, False))
    return home, directory, owner


def call(directory=None, **kwargs):
    args = dict(agent="plan", message="Inspect only. ' ; $(not a shell)\nsecond line")
    if directory:
        args["directory"] = str(directory)
    args.update(kwargs)
    return json.loads(plugin.opencode_call(args))


def session(cid, action="status", **kwargs):
    return json.loads(plugin.opencode_session(dict(action=action, conversation_id=cid, **kwargs)))


def test_new_resume_fork_and_literal_prompt(fixture):
    home, directory, owner = fixture
    first = call(directory)
    assert first["status"] == "completed", first
    assert first["session_id"] == "ses_first"
    invocation = json.loads((directory / "invocation.json").read_text())
    assert "$(not a shell)" in invocation["prompt"]
    assert "--auto" not in invocation["args"]
    assert "$(not a shell)" not in " ".join(invocation["args"])
    resumed = call(conversation_id=first["conversation_id"])
    assert resumed["conversation_id"] == first["conversation_id"]
    assert resumed["session_id"] == first["session_id"]
    forked = call(conversation_id=first["conversation_id"], fork=True)
    assert forked["status"] == "completed", forked
    assert forked["conversation_id"] != first["conversation_id"]
    assert forked["session_id"] == "ses_fork"
    assert session(first["conversation_id"])["session_id"] == "ses_first"
    assert oct(Path(first["log"]).stat().st_mode & 0o777) == "0o600"


def test_approval_and_issue_grant_are_separate(fixture):
    _, directory, _ = fixture
    assert "approval" in call(directory, agent="build")["error"]
    built = call(directory, agent="build", approval="Client: implement this plan through PR")
    assert built["status"] == "completed", built
    invocation = json.loads((directory / "invocation.json").read_text())
    assert "--auto" in invocation["args"]
    assert invocation["permission"]["bash"]["gh issue create*"] == "deny"
    updated = call(conversation_id=built["conversation_id"], agent="build",
                   issue_approval="Client: manage this job's Issues")
    assert updated["status"] == "completed", updated
    permission = json.loads((directory / "invocation.json").read_text())["permission"]
    assert "gh issue create*" not in permission["bash"]
    assert permission["bash"]["gh pr merge*"] == "deny"
    assert permission["github_project_item_add"] == "deny"


def test_readonly_does_not_inherit_build_grant(fixture):
    _, directory, _ = fixture
    first = call(directory, agent="build", approval="Implement")
    assert first["status"] == "completed"
    reviewed = call(conversation_id=first["conversation_id"], agent="review")
    assert reviewed["status"] == "completed"
    permission = json.loads((directory / "invocation.json").read_text())["permission"]
    assert permission["edit"] == permission["bash"]["*"] == "deny"
    assert permission["read"]["**/.env"] == "deny"
    assert permission["task"]["explore*"] == "allow"
    assert permission["task"]["reviewer*"] == "allow"
    assert permission["task"]["*"] == "deny"


def test_main_rejected_before_launch(fixture):
    _, directory, _ = fixture
    subprocess.run(["git", "-C", str(directory), "symbolic-ref", "HEAD", "refs/heads/main"], check=True)
    assert "default branch" in call(directory, agent="build", approval="Implement")["error"]
    assert not (directory / "invocation.json").exists()


@pytest.mark.parametrize("behavior,status", [("error", "failed"), ("error-signal", "unknown"), ("malformed", "unknown"),
                                             ("incomplete", "unknown"), ("wrong-session", "unknown")])
def test_json_errors_are_not_success_even_at_exit_zero(fixture, monkeypatch, behavior, status):
    _, directory, _ = fixture
    monkeypatch.setenv("ENGINEER_FAKE", behavior)
    result = call(directory)
    assert result["status"] == status, result
    if status == "unknown":
        assert "uncertain" in call(directory)["error"]
        assert "uncertain" in call(conversation_id=result["conversation_id"])["error"]
        reconciled = session(result["conversation_id"], "reconcile", evidence="Process stopped; inspected Git and remote state")
        assert reconciled["status"] == "reconciled", reconciled


def test_questions_remain_text_not_synthetic_acceptance(fixture, monkeypatch):
    _, directory, _ = fixture
    monkeypatch.setenv("ENGINEER_FAKE", "question")
    result = call(directory)
    assert result["status"] == "completed"
    assert "ASK_CLIENT" in result["result"]
    assert "accepted" not in result


def test_foreign_owner_cannot_access_resume_or_stop(fixture, monkeypatch):
    home, directory, _ = fixture
    first = call(directory)
    monkeypatch.setattr(plugin, "_scope", lambda: (home, {"profile": "engineer", "session_id": "other"}, False))
    for action in ("status", "stop", "reconcile"):
        assert "another originating session" in session(first["conversation_id"], action, evidence="checked")["error"]
    assert json.loads(plugin.opencode_session({"action": "list"})) == []
    assert "another originating session" in call(conversation_id=first["conversation_id"])["error"]


def test_unknown_arguments_and_nonrepo_fail_before_execution(fixture):
    _, directory, _ = fixture
    for extra in ({"command": "anything"}, {"owner": {}}, {"approval": True}, {"fork": "yes"}):
        assert "error" in call(directory, **extra)
    assert "error" in call(directory.parent)
    assert "error" in call(directory="relative")
    assert not (directory / "invocation.json").exists()


def test_runtime_deadline_stops_child_group_and_blocks_replay(fixture, monkeypatch):
    home, directory, _ = fixture
    (home / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 1\n")
    monkeypatch.setenv("ENGINEER_FAKE", "sleep")
    started = time.monotonic()
    result = call(directory)
    assert time.monotonic() - started < 15
    assert result["status"] == "unknown", result
    assert "uncertain" in call(directory)["error"]
    data = plugin.dispatch._read(home / "opencode-sessions" / (result["conversation_id"] + ".json"))
    for _ in range(20):
        if not plugin._group_alive(data["pgid"]):
            break
        time.sleep(0.1)
    assert not plugin._group_alive(data["pgid"])


def test_explicit_stop_reaches_running_process(fixture, monkeypatch):
    home, directory, _ = fixture
    monkeypatch.setenv("ENGINEER_FAKE", "sleep")
    stopped = []
    def stop_when_running():
        for _ in range(200):
            for path in (home / "opencode-sessions").glob("*.json"):
                data = plugin.dispatch._read(path)
                if data.get("status") == "running" and data.get("pgid"):
                    stopped.append(session(data["conversation_id"], "stop"))
                    return
            time.sleep(0.02)
    thread = threading.Thread(target=stop_when_running)
    thread.start()
    result = call(directory)
    thread.join(timeout=6)
    assert stopped and stopped[0]["stop_requested"] is True
    assert result["status"] == "unknown", result
    assert "uncertain" in call(directory)["error"]


def test_revoked_config_blocks_new_calls_but_keeps_owned_inspection(fixture):
    home, directory, _ = fixture
    result = call(directory)
    (home / "config.yaml").write_text("opencode_cli:\n  enabled: false\n")
    assert "not enabled" in call(directory)["error"]
    assert session(result["conversation_id"])["status"] == "completed"


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


def test_registry_symlink_refused(fixture):
    home, directory, _ = fixture
    (home / "opencode-sessions").symlink_to(directory, target_is_directory=True)
    assert "symlink" in call(directory)["error"]


def test_registration_is_engineer_only():
    class Context:
        profile_name = "writer"

        def register_tool(self, **kwargs):
            raise AssertionError("foreign profile gained OpenCode tools")

    plugin.register(Context())


def test_evaluator_resident_does_not_inherit_repository_cwd(fixture, monkeypatch):
    home, directory, owner = fixture
    target = home.parent / "ui-review"
    target.mkdir()
    (target / "config.yaml").write_text("{}\n")
    launched = []
    class Process:
        pid = 999999
        returncode = 0
        def __init__(self, command, **kwargs):
            launched.append(kwargs)
        def communicate(self, **kwargs):
            return "review complete", ""
        def wait(self, **kwargs):
            return 0
    monkeypatch.setattr(plugin.dispatch.subprocess, "Popen", Process)
    monkeypatch.setattr(plugin.dispatch.os, "killpg", lambda *args: None)
    data = {"conversation_id": "a" * 32, "job_id": "b" * 32,
            "target": "ui-review", "deadline": time.time() + 30}
    plugin.dispatch._resident(home, data, "Review the supplied test URL")
    assert Path(launched[0]["cwd"]) == target / "workspace" / ("review-" + "a" * 32)
    assert not Path(launched[0]["cwd"]).is_relative_to(directory)


def test_evaluator_git_workspace_refused_before_dispatch(fixture, monkeypatch):
    home, _, _ = fixture
    target = home.parent / "ux-persona"
    target.mkdir()
    (target / "config.yaml").write_text("{}\n")
    (target / ".git").mkdir()
    data = {"conversation_id": "a" * 32, "job_id": "b" * 32, "target": "ux-persona"}
    with pytest.raises(plugin.dispatch.NotDispatched, match="outside a Git project"):
        plugin.dispatch._resident(home, data, "Do not inherit implementation context")
