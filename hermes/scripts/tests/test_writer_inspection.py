"""Offline adapter tests using the provisioned Hermes framework, never live sessions."""

from contextlib import contextmanager
import ast
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "writer_inspection_test", ROOT / "hermes/plugins/writing-inspection/__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


@contextmanager
def scope(home, profile="writer", session="test-session", platform="cli"):
    from hermes_constants import set_hermes_home_override, reset_hermes_home_override
    from gateway.session_context import set_session_vars, clear_session_vars
    token = set_hermes_home_override(home)
    tokens = set_session_vars(profile=profile, session_id=session, platform=platform, source=platform)
    try:
        yield
    finally:
        clear_session_vars(tokens)
        reset_hermes_home_override(token)


@pytest.fixture
def runtime(tmp_path):
    with scope(tmp_path / "profiles/writer"):
        yield


def call(args, profile="writer", **kwargs):
    result = json.loads(plugin._inspect(args, profile, **kwargs))
    if result["status"] == "error":
        assert set(result["error"]) == {"code", "message"}
        assert all(isinstance(value, str) for value in result["error"].values())
        assert all(isinstance(item, dict) and {"check", "reason"} <= item.keys()
                   for item in result["unverified"])
    return result


@pytest.fixture
def provisioned(monkeypatch):
    # Only fixtures substitute executable paths. Production accepts no overrides.
    monkeypatch.setattr(plugin, "PYTHON", Path(sys.executable))
    monkeypatch.setattr(plugin, "SCRIPT", Path(__file__))


def report(text="sample", status="ok"):
    return {"schema_version": 1, "status": status,
            "input_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "inspector_version": "test-1", "executed": ["outline"],
            "unverified": [{"check": "proper_noun_inventory", "reason": "missing_dependency"}]
            if status == "partial" else [],
            "error": {"code": "runtime_failure", "message": "Failed"} if status == "error" else None,
            "findings": [], "outline": [], "terms": [], "structure": {},
            "truncation": {"applied": False, "counts": {
                key: {"total": 0, "returned": 0, "omitted": 0}
                for key in ("findings", "outline", "terms")},
                "excerpt_clipped": 0, "term_clipped": 0, "output_budget_dropped": 0}}


@pytest.mark.parametrize("args", [None, [], {}, {"text": 3}, {"text": True},
    {"text": "x", "path": "/private"}, {"text": "x", "command": "id"},
    {"text": "x", "code": "print(1)"}, {"text": "x", "options": {}},
    {"text": "x", "modes": "outline"},
    {"text": "x", "modes": [True]}, {"text": "x", "modes": [[]]},
    {"text": "x", "modes": ["outline", "outline"]},
    {"text": "x", "modes": ["score"]}, {"text": "\ud800"},
    {"text": "x" * 131073}, {"text": "\u3042" * 43691}])
def test_invalid_requests_never_start_child(runtime, provisioned, monkeypatch, args):
    monkeypatch.setattr(plugin, "_run", lambda _: pytest.fail("child started"))
    assert call(args, task_id="task")["error"]["code"] == "invalid_request"


@pytest.mark.parametrize("home,profile,session,role,task", [
    ("writer", "writer", "", "writer", "task"),
    ("writer", "", "session", "writer", "task"),
    ("engineer", "writer", "session", "writer", "task"),
    ("writer", "engineer", "session", "writer", "task"),
    ("writer", "writer", "session", "engineer", "task"),
    ("writer", "writer", "session", "writer", None)])
def test_wrong_scope_fails_closed(tmp_path, provisioned, monkeypatch, home, profile, session, role, task):
    monkeypatch.setattr(plugin, "_run", lambda _: pytest.fail("child started"))
    with scope(tmp_path / home, profile, session):
        assert call({"text": "sample"}, role, task_id=task)["error"]["code"] == "wrong_scope"


def test_missing_session_context(runtime, provisioned, monkeypatch):
    # Leave home/profile/session/task valid so only the engaged-context gate fails.
    monkeypatch.setattr("gateway.session_context.session_context_engaged", lambda: False)
    monkeypatch.setattr(plugin, "_run", lambda _: pytest.fail("child started"))
    assert call({"text": "sample"}, task_id="task")["error"]["code"] == "wrong_scope"


@pytest.mark.parametrize("reason,args,role,code", [
    ("Only text and modes are accepted", {"text": "sample", "command": "id"}, "writer", "invalid_request"),
    ("text exceeds 131072 UTF-8 bytes", {"text": "\u3042" * 43691}, "writer", "invalid_request"),
    ("Writer profile, originating session and framework task required", {"text": "sample"}, "engineer", "wrong_scope"),
])
def test_gate_mutation_reaches_execution_tripwire(runtime, provisioned, monkeypatch, reason, args, role, code):
    monkeypatch.setattr(plugin, "_run", lambda _: pytest.fail("child started"))
    assert call(args, role, task_id="task")["error"]["code"] == code
    # Disable exactly one guard in an in-memory function copy, never source files.
    # A missing interpreter must not mask the execution this mutation permits.
    tree = ast.parse(inspect.getsource(plugin._inspect))
    guards = [node for node in tree.body[0].body if isinstance(node, ast.If)
              and isinstance(node.body[0], ast.Return)
              and isinstance(node.body[0].value, ast.Call)
              and node.body[0].value.args
              and isinstance(node.body[0].value.args[0], ast.Constant)
              and node.body[0].value.args[0].value == reason]
    assert len(guards) == 1
    guards[0].test = ast.Constant(value=False)
    namespace = dict(plugin.__dict__)
    exec(compile(ast.fix_missing_locations(tree), "<inspection-gate-mutant>", "exec"), namespace)
    with pytest.raises(pytest.fail.Exception, match="child started"):
        namespace["_inspect"](args, role, task_id="task")


def test_missing_interpreter(runtime, tmp_path, monkeypatch):
    monkeypatch.setattr(plugin, "PYTHON", tmp_path / "missing")
    result = call({"text": "sample"}, task_id="task")
    assert result["error"]["code"] == "unavailable"
    assert [item["check"] for item in result["unverified"]] == list(plugin.MODES)
    assert all(item["reason"] == result["error"]["message"] for item in result["unverified"])
    assert result["executed"] == []


@pytest.mark.parametrize("status", ["ok", "partial", "error"])
@pytest.mark.parametrize("platform", ["cli", "a2a"])
def test_report_passthrough_and_default_modes(tmp_path, provisioned, monkeypatch, status, platform):
    expected = report(status=status)
    def run(request):
        assert json.loads(request) == {"text": "sample", "modes": list(plugin.MODES)}
        return json.dumps(expected).encode()
    monkeypatch.setattr(plugin, "_run", run)
    with scope(tmp_path / "writer", platform=platform):
        assert call({"text": "sample"}, task_id="task") == expected


@pytest.mark.parametrize("key,value", [("schema_version", True), ("schema_version", 2),
    ("status", "success"), ("input_sha256", "wrong"), ("inspector_version", None),
    ("findings", {}), ("executed", {}), ("unverified", None), ("outline", {}),
    ("terms", {}), ("structure", []), ("truncation", False)])
def test_invalid_upstream_schema_and_hash(runtime, provisioned, monkeypatch, key, value):
    data = report()
    data[key] = value
    monkeypatch.setattr(plugin, "_run", lambda _: json.dumps(data).encode())
    assert "Invalid inspector report" in call({"text": "sample"}, task_id="task")["error"]["message"]


@pytest.mark.parametrize("payload", [b"not JSON", b"[]", b"\xff"])
def test_invalid_json(runtime, provisioned, monkeypatch, payload):
    monkeypatch.setattr(plugin, "_run", lambda _: payload)
    assert call({"text": "sample"}, task_id="task")["error"]["code"] == "invalid_report"


@pytest.mark.parametrize("program,expected", [
    ("import time; time.sleep(30)", "deadline"),
    ("import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(30)", "deadline"),
    ("import os,time; os.write(1,b'x'*300000); time.sleep(30)", "pipe limit"),
    ("import os,time; os.write(2,b'x'*20000); time.sleep(30)", "pipe limit"),
    ("import sys; sys.stderr.write('PRIVATE_CONTENT'); sys.exit(1)", "withheld")])
def test_real_pipe_bounds_timeout_and_reaping(runtime, provisioned, monkeypatch, caplog, capsys,
                                             program, expected):
    real_popen = subprocess.Popen
    children = []
    def spawn(argv, **kwargs):
        assert argv == [str(plugin.PYTHON), "-I", "-B", str(plugin.SCRIPT), "--request"]
        assert kwargs["shell"] is False and kwargs["env"] == {}
        assert "PRIVATE_CONTENT" not in repr(argv)
        child = real_popen([sys.executable, "-I", "-B", "-c", program], **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(plugin.subprocess, "Popen", spawn)
    monkeypatch.setattr(plugin, "TIMEOUT", 0.3)
    result = call({"text": "PRIVATE_CONTENT" * 8000}, task_id="task")
    assert expected in result["error"]["message"]
    assert all(child.poll() is not None for child in children) and children
    assert "PRIVATE_CONTENT" not in json.dumps(result) + caplog.text + str(capsys.readouterr())
    assert all(pipe.closed for child in children for pipe in (child.stdin, child.stdout, child.stderr))


def test_actual_plugin_context_and_multiplex_toolset_cache(tmp_path, provisioned, monkeypatch):
    import toolsets
    from tools.registry import ToolRegistry
    from hermes_cli.plugins import PluginContext, PluginManager, PluginManifest
    reg = ToolRegistry()
    monkeypatch.setattr("tools.registry.registry", reg)
    monkeypatch.setattr(toolsets, "_resolve_toolset_memo", {})
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(plugin, "_run", lambda _: pytest.fail("child started"))
    def home(role):
        return tmp_path / ".hermes" if role == "default" else tmp_path / ".hermes/profiles" / role
    manifest = PluginManifest(name="writing-inspection", kind="standalone")
    for role in ("engineer", "writer", "default", "researcher"):
        with scope(home(role), role):
            ctx = PluginContext(manifest, PluginManager())
            assert ctx.profile_name == role
            plugin.register(ctx)
    for role in ("engineer", "writer", "researcher", "writer", "default", "writer"):
        with scope(home(role), role):
            assert ("writing_inspect" in toolsets.resolve_toolset("writing-inspection")) == (role == "writer")
            entry = reg.get_entry("writing_inspect")
            if role == "writer":
                assert entry.schema["parameters"]["additionalProperties"] is False
                handler = entry.handler
            else:
                assert entry is None
    with scope(tmp_path / "profiles/engineer", "engineer"):
        assert json.loads(handler({"text": "sample"}, task_id="task"))["error"]["code"] == "wrong_scope"
    with scope(home("writer")):
        with pytest.raises(pytest.fail.Exception, match="child started"):
            handler({"text": "sample"}, task_id="task")


def test_writer_config_effective_toolsets_and_canonical_paths():
    import toolsets
    config = yaml.safe_load((ROOT / "hermes/profiles/writer/config.yaml").read_text())
    assert "writing-inspection" in config["plugins"]["enabled"]
    assert "writing-inspection" in config["toolsets"]
    for platform, names in config["platform_toolsets"].items():
        assert ("writing-inspection" in names) == (platform in ("cli", "a2a"))
        tools = set().union(*(toolsets.resolve_toolset(name) for name in names))
        assert not tools.intersection({"terminal", "execute_code", "process_manage", "browser_exec"})
    assert config["skills"]["inline_shell"] is False and config["command_allowlist"] == []
    assert plugin.ROOT == ROOT
    assert plugin.SCRIPT == ROOT / "agents/curated/japanese-writing/scripts/inspect_text.py"
    assert plugin.PYTHON == ROOT / "hermes/local/writing-inspection/venv/bin/python"
    for path in [ROOT / "hermes/config.yaml", *(ROOT / "hermes/profiles").glob("*/config.yaml")]:
        if path.parent.name != "writer":
            other = yaml.safe_load(path.read_text())
            assert "writing-inspection" not in other.get("plugins", {}).get("enabled", [])


def test_canonical_inspector_when_provisioned(runtime):
    if not plugin.PYTHON.is_file() or not plugin.SCRIPT.is_file():
        pytest.skip("Canonical shared inspector / dedicated Python not provisioned")
    text = "# Heading\n\nA short paragraph."
    result = call({"text": text}, task_id="task")
    assert result["status"] in ("ok", "partial"), result
    assert result["input_sha256"] == hashlib.sha256(text.encode()).hexdigest()


def test_opt_in_sudachi_maximum_japanese_adapter(runtime, monkeypatch):
    executable = os.environ.get("WRITING_INSPECTION_TEST_PYTHON")
    if not executable:
        pytest.skip("Set WRITING_INSPECTION_TEST_PYTHON to an already-provisioned Sudachi Python")
    python = Path(executable)
    assert python.is_absolute() and python.is_file() and os.access(python, os.X_OK)
    assert plugin.SCRIPT.is_file()
    monkeypatch.setattr(plugin, "PYTHON", python)
    # Japanese prose with particle chains and long sentence candidates, repeated
    # as separate paragraphs to exercise morphology and report-budget removals.
    unit = "# \u8abf\u67fb\n\n" + "\u6771\u4eac\u306e\u4f1a\u793e\u306e\u90e8\u7f72\u306e\u8abf\u67fb\u8cc7\u6599\u3092\u78ba\u8a8d\u3059\u308b" * 8 + "\u3002\n\n"
    raw = (unit * (plugin.INPUT_LIMIT // len(unit.encode()) + 1)).encode()[:plugin.INPUT_LIMIT]
    text = raw.decode("utf-8", errors="ignore")
    text += " " * (plugin.INPUT_LIMIT - len(text.encode()))
    assert len(text.encode()) == 131072
    started = time.perf_counter()
    serialized = plugin._inspect({"text": text}, "writer", task_id="task")
    elapsed = time.perf_counter() - started
    result = assert_framework_safe(serialized)
    assert result["status"] == "partial", result
    assert result["dependencies"]["available"] is True
    assert all(item["actual"] == item["required"]
               for item in result["dependencies"]["packages"].values())
    assert {"no_particle_chain", "double_negative", "proper_noun_inventory"} <= set(result["executed"])
    assert not result["unverified"]
    assert result["input_sha256"] == hashlib.sha256(text.encode()).hexdigest()
    assert result["truncation"]["applied"] is True
    assert result["truncation"]["output_budget_dropped"] > 0
    for key, count in result["truncation"]["counts"].items():
        assert count["returned"] == len(result[key])
        assert count["total"] == count["returned"] + count["omitted"]
    print(f"Sudachi full adapter: input_bytes={len(text.encode())} elapsed_seconds={elapsed:.3f} "
          f"report_bytes={len(serialized.encode())} report_lines={len(serialized.splitlines())} "
          f"output_budget_dropped={result['truncation']['output_budget_dropped']}")


@pytest.mark.parametrize("text,modes", [
    ("# Heading\n\nA short paragraph.", list(plugin.MODES)),
    ("# Heading\n\nA short paragraph.", ["outline", "structure"]),
    ("", []), ("\x00" * 131072, [])])
def test_real_shared_protocol_with_test_interpreter(runtime, monkeypatch, text, modes):
    if not plugin.SCRIPT.is_file():
        pytest.skip("Shared inspector not yet present")
    monkeypatch.setattr(plugin, "PYTHON", Path(sys.executable))
    source_hash = hashlib.sha256(plugin.SCRIPT.read_bytes()).hexdigest()
    result = call({"text": text, "modes": modes}, task_id="task")
    assert hashlib.sha256(plugin.SCRIPT.read_bytes()).hexdigest() == source_hash
    assert result["status"] in ("ok", "partial"), result
    assert result["input_sha256"] == hashlib.sha256(text.encode()).hexdigest()
    if result["status"] == "partial":
        assert result["unverified"] or result["truncation"]["applied"]
    if not modes:
        assert result["executed"] == []


def assert_framework_safe(serialized):
    limits = yaml.safe_load((ROOT / "hermes/profiles/writer/config.yaml").read_text())["tool_output"]
    assert limits == {"max_bytes": 50000, "max_lines": 2000, "max_line_length": 2000}
    assert len(serialized.encode("utf-8")) <= plugin.REPORT_BYTES < limits["max_bytes"]
    assert len(serialized.splitlines()) <= plugin.REPORT_LINES < limits["max_lines"]
    assert max(map(len, serialized.splitlines())) <= plugin.REPORT_LINE_LENGTH < limits["max_line_length"]
    # Apply every configured cap: no truncation marker or content loss is possible
    # if this produces the exact original JSON, even for multibyte excerpts.
    visible = serialized.encode("utf-8")[:limits["max_bytes"]].decode("utf-8")
    visible = "\n".join(line[:limits["max_line_length"]]
                        for line in visible.splitlines()[:limits["max_lines"]])
    assert visible == serialized
    return json.loads(visible)


def assert_budget_accounting(original, result):
    assert result["input_sha256"] == original["input_sha256"]
    assert result["status"] == "partial" and result["truncation"]["applied"] is True
    arrays = ("findings", "outline", "terms")
    for key in original.keys() - {*arrays, "status", "truncation"}:
        assert result[key] == original[key]
    removed = 0
    for key in arrays:
        count = result["truncation"]["counts"][key]
        before = original["truncation"]["counts"][key]
        delta = len(original[key]) - len(result[key])
        assert result[key] == original[key][:len(result[key])]
        assert count == {"total": before["total"], "returned": len(result[key]),
                         "omitted": before["omitted"] + delta}
        removed += delta
    assert removed > 0
    assert result["truncation"]["output_budget_dropped"] == original["truncation"]["output_budget_dropped"] + removed
    for key in original["truncation"].keys() - {"counts", "applied", "output_budget_dropped"}:
        assert result["truncation"][key] == original["truncation"][key]


@pytest.mark.parametrize("budget", ["bytes", "lines"])
def test_report_budget_keeps_metadata_and_accumulates_omissions(runtime, provisioned, monkeypatch, budget):
    original = report(status="partial")
    original["dependencies"] = {"available": False, "reason": "not_provisioned"}
    original["structure"] = {"counts": {"headings": 600}, "requires_context": True}
    size = 100 if budget == "bytes" else 166
    for key in ("findings", "outline", "terms"):
        original[key] = [{"line": i, "column": 1,
                          "excerpt": "\u3042" * 240 if budget == "bytes" else "x"}
                         for i in range(size)]
        original["truncation"]["counts"][key] = {"total": size + 30, "returned": size, "omitted": 30}
    original["truncation"].update(applied=True, output_budget_dropped=9, excerpt_clipped=12)
    pretty = json.dumps(original, ensure_ascii=False, indent=2)
    if budget == "lines":
        assert len(pretty.encode()) < plugin.REPORT_BYTES
        assert len(pretty.splitlines()) > plugin.REPORT_LINES
    else:
        assert len(pretty.encode()) > plugin.REPORT_BYTES
    monkeypatch.setattr(plugin, "_run", lambda _: json.dumps(original, ensure_ascii=False).encode())
    result = assert_framework_safe(plugin._inspect({"text": "sample"}, "writer", task_id="task"))
    assert_budget_accounting(original, result)


def test_maximum_request_real_inspector_survives_configured_output_limits(runtime, monkeypatch):
    if not plugin.SCRIPT.is_file():
        pytest.skip("Shared inspector not yet present")
    if not plugin.PYTHON.is_file():
        monkeypatch.setattr(plugin, "PYTHON", Path(sys.executable))
    text = "".join(f"# Heading {i}\n\nAPI{i} " + "word " * 30 + ".\n\n" for i in range(600))
    text += " " * (131072 - len(text.encode()))
    assert len(text.encode()) == plugin.INPUT_LIMIT
    original_bytes = plugin._run(json.dumps({"text": text, "modes": list(plugin.MODES)}).encode())
    assert len(original_bytes) <= plugin.OUTPUT_LIMIT == 256 * 1024
    original = json.loads(original_bytes)
    assert all(len(original[key]) >= 100 for key in ("findings", "outline", "terms"))
    assert len(json.dumps(original)) > 2000  # The previous one-line response would lose data.
    monkeypatch.setattr(plugin, "_run", lambda _: original_bytes)
    result = assert_framework_safe(plugin._inspect({"text": text}, "writer", task_id="task"))
    assert result["input_sha256"] == hashlib.sha256(text.encode()).hexdigest()
    assert_budget_accounting(original, result)


def test_metadata_over_budget_returns_explicit_error(runtime, provisioned, monkeypatch):
    original = report()
    original["dependencies"] = {"reason": "x" * 2001}
    monkeypatch.setattr(plugin, "_run", lambda _: json.dumps(original).encode())
    result = assert_framework_safe(plugin._inspect({"text": "sample"}, "writer", task_id="task"))
    assert result["error"]["code"] == "report_budget_exceeded"
    assert result["status"] == "error" and result["executed"] == []
    assert result["input_sha256"] == original["input_sha256"]
    assert all(item["reason"] for item in result["unverified"])


@pytest.mark.parametrize("field,value", [("total", -1), ("returned", 1), ("omitted", True)])
def test_invalid_truncation_counts_refused(runtime, provisioned, monkeypatch, field, value):
    original = report()
    original["truncation"]["counts"]["terms"][field] = value
    monkeypatch.setattr(plugin, "_run", lambda _: json.dumps(original).encode())
    result = call({"text": "sample"}, task_id="task")
    assert result["error"]["code"] == "invalid_report"
