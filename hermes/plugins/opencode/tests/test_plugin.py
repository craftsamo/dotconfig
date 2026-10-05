import ast
import fnmatch
import importlib.util
import json
import os
from pathlib import Path
import shlex
import signal
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
version = os.environ.get("ENGINEER_FAKE_VERSION", "1.18.34")
if args == ["--version"]:
    # A stop request that lands while the version probe runs.
    for request in pathlib.Path(os.environ.get("ENGINEER_FAKE_STOP_DIR", "/nonexistent")).glob("*.request"):
        request.with_suffix(".stop").write_text("{}")
    print(version)
    sys.exit(0)
if args[:1] == ["serve"]:
    # OpenCode 2 runs go through a private API server, never `run`.
    assert "v2." in version and args[1:] == ["--hostname", "127.0.0.1", "--port", "0"], args
    path = os.environ["ENGINEER_FAKE_SERVER"]
    exec(compile(open(path).read(), path, "exec"))
    sys.exit(0)
assert "v2." not in version, "OpenCode 2 must not be driven through `opencode run`"
directory = pathlib.Path(args[args.index("--dir") + 1])
prompt = sys.stdin.read()
behavior = os.environ.get("ENGINEER_FAKE", "ok")
(directory / "invocation.json").write_text(json.dumps({"args": args, "prompt": prompt,
    "permission": json.loads(os.environ["OPENCODE_PERMISSION"]),
    "config": json.loads(os.environ["OPENCODE_CONFIG_CONTENT"])}))
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
    # The gateway gives runners no PYTHONPATH; they must find Hermes by themselves.
    monkeypatch.delenv("PYTHONPATH", raising=False)
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


@pytest.mark.parametrize("role, installed, auto", [
    ("plan", "hermes-plan", False), ("build", "hermes-build", True),
    ("review", "hermes-review", False), ("debug", "debug", False),
])
def test_roles_run_on_hidden_hermes_primaries(fixture, role, installed, auto):
    """Hermes keeps its role names; only the CLI --agent and the injected
    per-agent permission key carry the installed OpenCode agent name."""
    _, directory, _ = fixture
    result = call(directory, agent=role, **({"approval": "Implement"} if role == "build" else {}))
    assert result["status"] == "completed", result
    assert result["agent"] == role
    invocation = json.loads((directory / "invocation.json").read_text())
    assert invocation["args"][invocation["args"].index("--agent") + 1] == installed
    assert ("--auto" in invocation["args"]) is auto
    assert list(invocation["config"]["agent"]) == [installed] + (["worker"] if role == "build" else [])
    assert invocation["config"]["agent"][installed]["permission"] == invocation["permission"]
    assert set(plugin.OPENCODE_AGENTS) == plugin.AGENTS


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


def test_model_and_variant_require_allowlist_and_reach_cli(fixture):
    home, directory, _ = fixture
    assert "allowed_models" in call(directory, model="openai/gpt-6-sol")["error"]
    assert not (directory / "invocation.json").exists()
    (home / "config.yaml").write_text(
        "opencode_cli:\n  enabled: true\n  timeout: 10\n"
        "  allowed_models: [openai/gpt-6-sol]\n  allowed_variants: [high]\n")
    assert "requires a model" in call(directory, variant="high")["error"]
    assert "allowed_variants" in call(directory, model="openai/gpt-6-sol", variant="max")["error"]
    assert "plain name" in call(directory, model="openai/gpt-6-sol; rm -rf")["error"]
    first = call(directory, model="openai/gpt-6-sol", variant="high")
    assert first["status"] == "completed", first
    assert first["model"] == "openai/gpt-6-sol" and first["variant"] == "high"
    args = json.loads((directory / "invocation.json").read_text())["args"]
    assert args[args.index("--model") + 1] == "openai/gpt-6-sol"
    assert args[args.index("--variant") + 1] == "high"
    # An omitted selection keeps the conversation's recorded engine.
    resumed = call(conversation_id=first["conversation_id"])
    assert resumed["status"] == "completed" and resumed["variant"] == "high"
    args = json.loads((directory / "invocation.json").read_text())["args"]
    assert "--variant" in args
    plain = call(directory)
    assert plain["status"] == "completed" and "model" not in plain
    args = json.loads((directory / "invocation.json").read_text())["args"]
    assert "--model" not in args and "--variant" not in args


def test_recorded_variant_without_model_is_refused_at_dispatch(fixture):
    home, directory, _ = fixture
    (home / "config.yaml").write_text(
        "opencode_cli:\n  enabled: true\n  timeout: 10\n  models: {plan: openai/gpt-6-astra}\n"
        "  allowed_variants: [high]\n")
    first = call(directory, variant="high")
    assert first["status"] == "completed" and "model" not in first, first
    # Maintainer drops the configured model: the bound variant must not ride OpenCode's default.
    (home / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 10\n  allowed_variants: [high]\n")
    stale = call(conversation_id=first["conversation_id"])
    assert stale["status"] == "failed" and "no model to bind" in stale["error"], stale


def test_wait_blocks_until_run_finishes_without_polling_turns(fixture, monkeypatch):
    home, directory, _ = fixture
    monkeypatch.setenv("ENGINEER_FAKE", "sleep")
    (home / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 3\n  wait_timeout: 60\n")
    outcome = {}
    def run():
        outcome["call"] = call(directory)
    thread = threading.Thread(target=run)
    thread.start()
    cid = None
    for _ in range(300):
        for path in (home / "opencode-sessions").glob("*.json"):
            data = plugin.dispatch._read(path)
            if data.get("status") == "running":
                cid = data["conversation_id"]
        if cid:
            break
        time.sleep(0.02)
    assert cid
    short = session(cid, "wait", timeout=1)
    assert short["timed_out"] is True and short["status"] == "running" and "note" in short
    waited = session(cid, "wait", timeout=30)
    thread.join(timeout=30)
    assert waited["timed_out"] is False
    assert waited["status"] == "unknown", waited
    assert waited["waited_seconds"] < 30
    settled = session(cid, "wait")
    assert settled["waited_seconds"] < 1 and settled["status"] == "unknown" and "note" in settled
    assert "only accepted for wait" in session(cid, "status", timeout=5)["error"]
    assert "positive integer" in session(cid, "wait", timeout=0)["error"]


AGENT_DIR = Path(__file__).resolve().parents[4] / "opencode/agent"


def external_only_opencode_scratch(permission):
    """Outside the worktree only OpenCode's own scratch dirs are readable, and
    the deny is listed first so the allows win under last-match evaluation."""
    rules = list(permission["external_directory"].items())
    assert rules[0] == ("*", "deny")
    assert {action for _, action in rules[1:]} == {"allow"}
    assert all(pattern.endswith(("/opencode/tool-output/*", "/opencode/shell/*/*", "/opencode/*"))
               for pattern, _ in rules[1:])
    return True


@pytest.mark.parametrize("installed", ["hermes-plan", "hermes-build", "hermes-review"])
def test_hidden_primaries_carry_no_permission_block(installed):
    """The plugin is the single owner of the hidden primaries' policy: a
    `permission:` key in the agent frontmatter would be deep-merged with the
    injected one (nested maps union) and reopen the two-source ambiguity."""
    text = (AGENT_DIR / f"{installed}.md").read_text()
    frontmatter = text.split("---", 2)[1]
    assert "permission" not in frontmatter, installed
    assert "hidden: true" in frontmatter and "mode: primary" in frontmatter


def test_readonly_roles_share_one_posture_and_list_every_tool_they_need():
    """An agent-level "*": deny shadows the global tool allows, so the read-only
    roles must name their own subagents, git/gh reads and custom git tools."""
    for role in ("plan", "review", "debug"):
        permission = plugin._permissions(role, None, {"main"})
        without_tasks = {k: v for k, v in permission.items() if k != "task"}
        assert without_tasks == {k: v for k, v in plugin._permissions("plan", None, {"main"}).items()
                                 if k != "task"}, role
        assert permission["*"] == permission["edit"] == "deny"
        assert permission["question"] == "deny"
        assert external_only_opencode_scratch(permission)
        assert permission["task"]["*"] == "deny"
        for name in ("explore*", "searcher*"):
            assert permission["task"][name] == "allow", (role, name)
        for name in ("git_provenance", "git_history_digest", "git_related_scan"):
            assert permission[name] == "allow", (role, name)
        for pattern in ("git blame*", "git merge-base*", "git remote -v", "gh pr status*",
                        "gh pr list*", "gh repo view*"):
            assert permission["bash"][pattern] == "allow", (role, pattern)
        assert permission["bash"]["*"] == "deny"
        assert permission["read"]["**/.env"] == "deny"


def test_subagents_are_granted_per_role():
    """Plan consults reviewer*/debugger as the human plan does, but never gets
    verifier (it may apply a formatter) or worker: a plan run never edits."""
    tasks = {role: plugin._permissions(role, None, {"main"})["task"] for role in ("plan", "review", "debug")}
    assert set(tasks["plan"]) == {"*", "explore*", "searcher*", "reviewer*", "debugger"}
    assert set(tasks["review"]) == {"*", "explore*", "searcher*", "reviewer*", "verifier"}
    assert set(tasks["debug"]) == {"*", "explore*", "searcher*", "debugger", "verifier"}


def test_build_denies_what_auto_would_otherwise_approve():
    """`run --auto` answers every ask with an approval, so anything build must
    not do is a deny, never an ask; the write surface is the explicit list."""
    permission = plugin._permissions("build", None, {"main"})
    assert permission["edit"] == "allow"
    assert permission["question"] == "deny"
    assert external_only_opencode_scratch(permission)

    def values(node):
        return [v for x in node.values() for v in (values(x) if isinstance(x, dict) else [x])]
    assert "ask" not in values(permission)
    assert permission["task"]["*"] == "deny"
    for name in ("explore*", "searcher*", "verifier", "worker", "reviewer*", "debugger"):
        assert permission["task"][name] == "allow", name
    assert permission["read"]["**/.env"] == "deny"
    assert "*" not in permission["bash"], "build keeps the user's own bash rules"
    assert permission["bash"]["git push* main"] == "deny"
    assert permission["bash"]["gh issue create*"] == "deny"
    assert "gh issue create*" not in plugin._permissions("build", "granted", {"main"})["bash"]


def test_build_recloses_worker_external_directory(fixture):
    """worker.md opens worktree homes and asks elsewhere; under --auto that ask
    is an approval, so build re-denies every outside pattern worker.md names.
    The injected map wins per key but unions with worker.md's, so a pattern
    missing from WORKER_EXTERNAL_KEYS would silently stay open."""
    frontmatter = (AGENT_DIR / "worker.md").read_text().split("---", 2)[1]
    declared = plugin.yaml.safe_load(frontmatter)["permission"]["external_directory"]
    assert set(declared) == set(plugin.WORKER_EXTERNAL_KEYS)

    _, directory, _ = fixture
    assert call(directory, agent="build", approval="Implement")["status"] == "completed"
    injected = json.loads((directory / "invocation.json").read_text())["config"]["agent"]["worker"]
    assert list(injected) == ["permission"]
    rules = injected["permission"]["external_directory"]
    merged = {**declared, **rules}
    assert list(merged)[0] == "*"
    assert {key: merged[key] for key in declared} == dict.fromkeys(declared, "deny")
    assert external_only_opencode_scratch({"external_directory": {
        key: action for key, action in merged.items() if key not in declared or key == "*"}})


@pytest.mark.parametrize("profile", ["writer", "creator", "marketer", "researcher", "default"])
def test_registration_is_engineer_and_assistant_only(profile):
    class Context:
        profile_name = profile

        def register_tool(self, **kwargs):
            raise AssertionError("foreign profile gained OpenCode tools")

    plugin.register(Context())


def test_assistant_home_runs_its_own_registry(fixture, monkeypatch):
    home, directory, owner = fixture
    assistant = home.parent / "assistant"
    assistant.mkdir()
    (assistant / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 10\n")
    owner = {"profile": "assistant", "session_id": "client-b", "routing_digest": "b"}
    monkeypatch.setattr(plugin, "_scope", lambda: (assistant, owner, False))
    result = call(directory)
    assert result["status"] == "completed", result
    assert (assistant / "opencode-sessions" / (result["conversation_id"] + ".json")).exists()
    assert not (home / "opencode-sessions").exists() or not list((home / "opencode-sessions").glob("*.json"))
    # Another Client profile cannot pass the runner's home check even with a valid record.
    creator = home.parent / "creator"
    creator.mkdir()
    (creator / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 10\n")
    monkeypatch.setattr(plugin, "_scope", lambda: (creator, {"profile": "creator", "session_id": "c", "routing_digest": "c"}, False))
    assert "error" in call(directory)


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


def test_reconcile_only_turn_refuses_execution(fixture, monkeypatch):
    home, directory, _ = fixture
    first = call(directory)
    monkeypatch.setenv("RESIDENT_TURN_KIND", "reconcile")
    assert "reconcile-only" in call(directory)["error"]
    assert "reconcile-only" in call(conversation_id=first["conversation_id"])["error"]
    assert session(first["conversation_id"])["status"] == "completed"


# ---------------------------------------------------------------- OpenCode 2

FAKE_SERVER = Path(__file__).resolve().parent / "fake_opencode2.py"
# The fake's agent pins and global denies, read as literals (it is a script).
fake = {node.targets[0].id: ast.literal_eval(node.value) for node in ast.parse(FAKE_SERVER.read_text()).body
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) in ("PINS", "GLOBAL_DENIES")}
GLOBAL_DENIES = fake["GLOBAL_DENIES"]
PROTECTED = {"main", "master"}


@pytest.fixture
def v2(fixture, monkeypatch, tmp_path):
    monkeypatch.setenv("ENGINEER_FAKE_VERSION", "opencode v2.0.23")
    monkeypatch.setenv("ENGINEER_FAKE_SERVER", str(FAKE_SERVER))
    monkeypatch.setenv("ENGINEER_FAKE_STATE", str(tmp_path / "fake-opencode-db.json"))
    # A run's policy must ride the session, never the environment.
    monkeypatch.setenv("OPENCODE_CONFIG_CONTENT", "{}")
    return fixture


def seen(directory):
    return json.loads((directory / "invocation.json").read_text())


def rules(role, issue=None):
    return plugin._rules(role, issue, PROTECTED, GLOBAL_DENIES)


def record(home, cid):
    return plugin.dispatch._read(home / "opencode-sessions" / (cid + ".json"))


def first_cid(home):
    for _ in range(400):
        for path in (home / "opencode-sessions").glob("*.json"):
            return plugin.dispatch._read(path)["conversation_id"]
        time.sleep(0.025)
    raise AssertionError("no conversation was recorded")


def wait_for(home, cid, status, limit=15):
    end = time.time() + limit
    while time.time() < end:
        data = record(home, cid)
        if data["status"] == status:
            return data
        time.sleep(0.05)
    raise AssertionError(f"{cid} never reached {status}")


def test_v2_runs_over_a_private_api_server_with_the_role_rules_and_pin(v2):
    home, directory, _ = v2
    first = call(directory)
    assert first["status"] == "completed", first
    assert first["result"] == "RESULT_OK"
    assert first["changes"] == [{"file": "a.txt", "status": "added", "additions": 1, "deletions": 0}]
    created = seen(directory)["created"]
    assert created["agent"] == "hermes-plan"
    assert created["model"] == fake["PINS"]["hermes-plan"]
    assert created["location"] == {"directory": str(directory)}
    assert created["permissions"] == rules("plan")
    assert "$(not a shell)" in seen(directory)["prompts"][0]
    assert seen(directory)["server_env_has_policy"] is False
    assert not plugin._group_alive(record(home, first["conversation_id"])["pgid"])
    assert oct(Path(first["log"]).stat().st_mode & 0o777) == "0o600"
    diff = Path(first["log"]).with_suffix(".diff")
    assert "+x" in diff.read_text() and oct(diff.stat().st_mode & 0o777) == "0o600"


def test_v2_resume_and_fork_reapply_agent_model_and_rules(v2):
    _, directory, _ = v2
    first = call(directory)
    built = call(conversation_id=first["conversation_id"], agent="build", approval="Implement the plan")
    assert built["status"] == "completed", built
    assert built["session_id"] == first["session_id"]
    session = seen(directory)["session"]
    assert session["agent"] == "hermes-build" and session["model"] == fake["PINS"]["hermes-build"]
    assert session["permissions"] == rules("build")
    forked = call(conversation_id=first["conversation_id"], fork=True, agent="plan")
    assert forked["status"] == "completed" and forked["session_id"] == "ses_fork", forked
    assert forked["conversation_id"] != first["conversation_id"]
    assert seen(directory)["session"]["permissions"] == rules("plan")


@pytest.mark.parametrize("role", ["review", "debug"])
def test_v2_review_and_debug_are_builds_subagents_not_roles(v2, role):
    _, directory, _ = v2
    result = call(directory, agent=role)
    assert result["status"] == "failed" and "not an OpenCode 2 role" in result["error"], result
    assert not (directory / "invocation.json").exists()


def test_v2_explicit_model_and_variant_replace_the_pin(v2):
    home, directory, _ = v2
    (home / "config.yaml").write_text(
        "opencode_cli:\n  enabled: true\n  timeout: 10\n"
        "  allowed_models: [openai/gpt-6-sol]\n  allowed_variants: [high]\n")
    assert call(directory, model="openai/gpt-6-sol", variant="high")["status"] == "completed"
    assert seen(directory)["created"]["model"] == {"providerID": "openai", "id": "gpt-6-sol", "variant": "high"}


def test_v2_without_any_model_fails_before_launch(v2, monkeypatch):
    _, directory, _ = v2
    monkeypatch.setenv("ENGINEER_FAKE_NO_PIN", "1")
    result = call(directory)
    assert result["status"] == "failed" and "needs a model" in result["error"], result
    assert not (directory / "invocation.json").exists()


@pytest.mark.parametrize("behavior", ["bad-rules", "bad-model"])
def test_v2_session_must_take_the_role_before_any_prompt(v2, monkeypatch, behavior):
    _, directory, _ = v2
    monkeypatch.setenv("ENGINEER_FAKE", behavior)
    result = call(directory)
    assert result["status"] == "failed" and "did not take" in result["error"], result
    assert seen(directory)["prompts"] == []


def test_v2_an_unreadable_resolved_ruleset_stops_the_run(v2, monkeypatch):
    """Without the person's resolved denies, build's `shell *` allow would reopen them."""
    _, directory, _ = v2
    monkeypatch.setenv("ENGINEER_FAKE", "no-rules")
    result = call(directory, agent="build", approval="Implement")
    assert result["status"] == "failed" and "no readable ruleset" in result["error"], result
    assert not (directory / "invocation.json").exists()


@pytest.mark.parametrize("behavior, status", [("error", "failed"), ("none", "unknown"), ("question", "completed"),
                                              ("crash", "unknown")])
def test_v2_this_turns_outcome_decides_the_status(v2, monkeypatch, behavior, status):
    _, directory, _ = v2
    monkeypatch.setenv("ENGINEER_FAKE", behavior)
    result = call(directory)
    assert result["status"] == status, result
    if behavior == "question":
        assert "ASK_CLIENT" in result["result"]


def test_v2_an_earlier_turns_outcome_is_not_this_turns(v2, monkeypatch):
    _, directory, _ = v2
    first = call(directory)
    assert first["status"] == "completed"
    monkeypatch.setenv("ENGINEER_FAKE", "stale")
    again = call(conversation_id=first["conversation_id"])
    assert again["status"] == "unknown", again
    assert again["result"] == "" and again["changes"] == []


def test_v2_deadline_interrupts_the_session_and_blocks_replay(v2, monkeypatch):
    home, directory, _ = v2
    (home / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 3\n")
    monkeypatch.setenv("ENGINEER_FAKE", "sleep")
    started = time.monotonic()
    result = call(directory)
    assert time.monotonic() - started < 30
    assert result["status"] == "unknown", result
    assert ["POST", "interrupt"] in seen(directory)["calls"]
    child = int((directory / "child-pid").read_text())
    for _ in range(40):
        try:
            os.kill(child, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        raise AssertionError("the turn's child process outlived the interrupt")
    assert "uncertain" in call(directory)["error"]


def test_v2_a_killed_runner_does_not_leave_its_server_running(v2, monkeypatch):
    home, directory, _ = v2
    (home / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 60\n")
    monkeypatch.setenv("ENGINEER_FAKE", "sleep")
    thread = threading.Thread(target=call, args=(directory,), daemon=True)
    thread.start()
    cid = first_cid(home)
    data = wait_for(home, cid, "running")
    for _ in range(100):
        data = record(home, cid)
        if data.get("pgid") and (directory / "child-pid").exists():
            break
        time.sleep(0.05)
    runner = subprocess.run(["pgrep", "-f", data["job_id"] + ".request"], capture_output=True, text=True).stdout.split()
    assert runner, "runner process not found"
    for pid in runner:
        os.kill(int(pid), signal.SIGKILL)
    for _ in range(200):
        if not plugin._group_alive(data["pgid"]):
            break
        time.sleep(0.1)
    else:
        raise AssertionError("the private server outlived its killed runner")
    thread.join(timeout=30)


@pytest.mark.parametrize("decision, expected", [("once", "PUSHED"), ("reject", "SKIPPED: not in scope")])
def test_v2_permission_request_pauses_for_the_caller(v2, monkeypatch, decision, expected):
    home, directory, _ = v2
    monkeypatch.setenv("ENGINEER_FAKE", "ask")
    paused = call(directory, agent="build", approval="Implement")
    assert paused["status"] == "waiting", paused
    assert paused["pending"] == [{"id": "per_1", "action": "shell", "resources": ["git push origin topic"]}]
    assert "answer" in paused["note"]
    cid = paused["conversation_id"]
    assert "uncertain" in call(directory)["error"]
    still = session(cid, "wait", timeout=1)
    assert still["status"] == "waiting" and still["timed_out"] is False and "answer" in still["note"]
    assert "once or reject" in session(cid, "answer", permission_id="per_1", decision="always")["error"]
    assert "No such" in session(cid, "answer", permission_id="per_9", decision="once")["error"]
    assert "only accepted for answer" in session(cid, "status", decision="once")["error"]
    answered = session(cid, "answer", permission_id="per_1", decision=decision,
                       **({"message": "not in scope"} if decision == "reject" else {}))
    assert answered["answer_recorded"] is True
    assert "No such" in session(cid, "answer", permission_id="per_1", decision="once")["error"]
    done = session(cid, "wait", timeout=20)
    assert done["status"] == "completed", done
    assert done["result"] == expected
    assert done["replies"] == [{"id": "per_1", "action": "shell", "resources": ["git push origin topic"],
                                "decision": decision, "by": "caller"}]
    assert seen(directory)["replies"][0]["decision"] == decision
    if decision == "reject":
        assert seen(directory)["replies"][0]["message"] == "not in scope"
        assert done["denied"] and done["denied"][0]["tool"] == "shell"
    assert "pending" not in done
    assert not list((home / "opencode-sessions").glob("*.answer"))


def test_v2_subagent_requests_reach_the_caller_and_the_reply_reaches_the_subagent(v2, monkeypatch):
    home, directory, _ = v2
    monkeypatch.setenv("ENGINEER_FAKE", "ask-subagent")
    paused = call(directory, agent="build", approval="Implement")
    assert paused["status"] == "waiting", paused
    assert paused["pending"] == [{"id": "per_1", "action": "shell", "resources": ["git push origin topic"],
                                  "from": "subagent"}]
    session(paused["conversation_id"], "answer", permission_id="per_1", decision="reject")
    done = session(paused["conversation_id"], "wait", timeout=20)
    assert done["status"] == "completed", done
    reply = seen(directory)["replies"][0]
    assert reply["session"] == "ses_child" and reply["message"] == plugin.REJECTED


def test_v2_live_caller_requests_are_rejected_by_the_runner(v2, monkeypatch):
    home, directory, owner = v2
    monkeypatch.setenv("ENGINEER_FAKE", "ask")
    monkeypatch.setattr(plugin, "_scope", lambda: (home, owner, True))
    launched = {}

    def terminal_tool(command, **kwargs):
        launched["run"] = subprocess.Popen(shlex.split(command))
        return json.dumps({"session_id": "proc_1"})

    module = type(sys)("tools.terminal_tool")
    module.terminal_tool = terminal_tool
    monkeypatch.setitem(sys.modules, "tools.terminal_tool", module)
    monkeypatch.setitem(sys.modules, "tools", type(sys)("tools"))
    started = call(directory, agent="build", approval="Implement")
    launched["run"].wait(timeout=30)
    done = session(started["conversation_id"])
    assert done["status"] == "completed", done
    assert done["replies"][0]["decision"] == "reject" and done["replies"][0]["by"] == "runner"
    assert seen(directory)["replies"][0]["message"] == plugin.NO_APPROVER


def test_v2_status_reports_progress_while_running(v2, monkeypatch):
    home, directory, _ = v2
    (home / "config.yaml").write_text("opencode_cli:\n  enabled: true\n  timeout: 4\n")
    monkeypatch.setenv("ENGINEER_FAKE", "sleep")
    thread = threading.Thread(target=call, args=(directory,))
    thread.start()
    cid = first_cid(home)
    wait_for(home, cid, "running")
    for _ in range(100):
        running = session(cid)
        if "progress" in running:
            break
        time.sleep(0.05)
    assert set(running["progress"]) == {"last_activity", "tool", "tokens"}
    thread.join(timeout=30)


# A model of V2 evaluation: whole-value wildcards (`*` crosses `/`, `?` is one
# character), a pattern ending in " *" also matches the bare command, the last
# matching rule wins, no match means ask.
def decide(ruleset, action, resource):
    def matches(pattern, value):
        return fnmatch.fnmatchcase(value, pattern) or (
            pattern.endswith(" *") and fnmatch.fnmatchcase(value, pattern[:-2]))
    effect = "ask"
    for rule in ruleset:
        if matches(rule["action"], action) and matches(rule["resource"], resource):
            effect = rule["effect"]
    return effect


@pytest.mark.parametrize("path, effect", [
    (".env", "deny"), ("sub/.env", "deny"), (".env.local", "deny"), (".env.example", "allow"),
    ("key.pem", "deny"), ("certs/server.key", "deny"), ("/home/u/.ssh/id_ed25519", "deny"),
    (".envrc", "deny"), (".npmrc", "deny"),
    ("src/app.py", "allow"),
])
def test_v2_secret_reads_are_closed_at_every_depth(path, effect):
    for role in ("plan", "build"):
        assert decide(rules(role), "read", path) == effect, (role, path)


@pytest.mark.parametrize("command, effect", [
    ("git status", "allow"), ("git log --oneline -5", "allow"), ("git diff --output=x.patch", "deny"),
    ("rm -rf x", "deny"), ("npm test", "deny"), ("sudo ls", "deny"), ("secret get KEY", "deny"),
])
def test_v2_plan_shell_is_read_only(command, effect):
    assert decide(rules("plan"), "shell", command) == effect
    assert decide(rules("plan"), "edit", "src/app.py") == "deny"
    assert decide(rules("plan"), "execute", "*") == "deny"
    assert decide(rules("plan"), "subagent", "verifier") == "deny"
    assert decide(rules("plan"), "subagent", "worker") == "deny"
    assert decide(rules("plan"), "subagent", "reviewer-deep") == decide(rules("plan"), "subagent", "debugger") == "allow"
    assert decide(rules("plan"), "subagent", "explore-small") == "allow"


@pytest.mark.parametrize("command, effect", [
    ("npm test", "allow"), ("git commit -m x", "allow"), ("git push origin topic", "ask"),
    ("git rebase main", "ask"), ("git -C . push origin topic", "ask"), ("npm exec foo", "ask"),
    ("git -C . status", "allow"), ("git -C sub diff --stat", "allow"), ("git -C . commit -m x", "ask"),
    ("git -C . push --force origin topic", "deny"), ("git -C . push origin main", "deny"),
    ("git -c core.x=y push origin +topic", "deny"), ("git -C . reset --hard", "deny"),
    ("git commit -m 'push --force and reset config'", "allow"),
    ("git push origin main", "deny"), ("git push origin HEAD:main", "deny"),
    ("git push origin refs/heads/main", "deny"), ("git push origin HEAD:refs/heads/master", "deny"),
    ("git push --force origin topic", "deny"), ("git push -f origin topic", "deny"),
    ("git push origin +topic", "deny"), ("git push origin :topic", "deny"), ("git push --delete origin topic", "deny"),
    ("git reset --hard", "deny"), ("git reset HEAD~1 --hard", "deny"), ("git clean -xdf", "deny"),
    ("gh pr merge 1", "deny"), ("gh issue create -t x", "deny"), ("gh api repos/x", "deny"),
    ("sudo ls", "deny"), ("secret get KEY", "deny"),
])
def test_v2_build_shell_asks_for_person_gated_commands_and_denies_the_rest(command, effect):
    assert decide(rules("build"), "shell", command) == effect


def test_v2_build_keeps_scratch_dirs_and_issue_grant_opens_issue_writes():
    build = rules("build")
    assert decide(build, "external_directory", "/elsewhere/*") == "deny"
    scratch = [r["resource"] for r in build if r["action"] == "external_directory" and r["effect"] == "allow"]
    assert scratch and all(decide(build, "external_directory", s) == "allow" for s in scratch)
    assert decide(build, "subagent", "debugger") == decide(build, "subagent", "reviewer-deep") == "allow"
    assert decide(build, "github_project_item_add", "*") == "deny"
    assert decide(rules("build", "granted"), "shell", "gh issue create -t x") == "allow"


def test_unknown_opencode_version_fails_before_launch(fixture, monkeypatch):
    _, directory, _ = fixture
    monkeypatch.setenv("ENGINEER_FAKE_VERSION", "3.1.0")
    result = call(directory)
    assert result["status"] == "failed" and "major version 3" in result["error"], result
    assert not (directory / "invocation.json").exists()


def test_v1_still_passes_dir_and_variant(fixture):
    home, directory, _ = fixture
    (home / "config.yaml").write_text(
        "opencode_cli:\n  enabled: true\n  timeout: 10\n"
        "  allowed_models: [openai/gpt-6-sol]\n  allowed_variants: [high]\n")
    assert call(directory, model="openai/gpt-6-sol", variant="high")["status"] == "completed"
    args = json.loads((directory / "invocation.json").read_text())["args"]
    assert "--standalone" not in args and args[args.index("--dir") + 1] == str(directory)
    assert args[args.index("--variant") + 1] == "high"


def test_stop_during_version_probe_launches_nothing(fixture, monkeypatch):
    home, directory, _ = fixture
    monkeypatch.setenv("ENGINEER_FAKE_STOP_DIR", str(home / "opencode-sessions"))
    result = call(directory)
    assert result["status"] == "failed" and "Stopped or expired" in result["error"], result
    assert not (directory / "invocation.json").exists()
