import importlib.util
import json
from pathlib import Path

from PIL import Image
import pytest


spec = importlib.util.spec_from_file_location("ui_inspection_test", Path(__file__).resolve().parents[1] / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    from hermes_constants import set_hermes_home_override, reset_hermes_home_override
    from gateway.session_context import set_session_vars, clear_session_vars
    import tools.browser_tool_session as browser
    home = tmp_path / "profiles/ui-review"
    home.mkdir(parents=True)
    token = set_hermes_home_override(str(home))
    tokens = set_session_vars(platform="cli", source="cli", profile="ui-review", session_id="client-review")
    calls = []
    size = (0, 0)
    def command(task, operation, args):
        nonlocal size
        calls.append((task, operation, args))
        if operation == "set":
            size = (int(args[1]), int(args[2]))
        else:
            Image.new("RGB", size, "white").save(args[0])
        return {"success": True}
    monkeypatch.setattr(browser, "_run_browser_command", command)
    yield home, calls
    clear_session_vars(tokens)
    reset_hermes_home_override(token)


def test_bounded_capture_attaches_exact_viewport(runtime):
    home, calls = runtime
    result = plugin._capture({"width": 375, "height": 812}, "ui-review", task_id="review-1")
    assert result["_multimodal"] is True
    info = json.loads(result["text_summary"])
    assert (info["width"], info["height"]) == (375, 812)
    path = Path(info["screenshot_path"])
    assert path.is_relative_to(home)
    assert path.stat().st_mode & 0o777 == 0o600
    assert [item[1] for item in calls] == ["set", "screenshot"]


@pytest.mark.parametrize("args", [{"width": True, "height": 900}, {"width": 9000, "height": 900},
                                  {"width": 375, "height": 812, "code": "anything"}])
def test_no_arbitrary_host_code_or_unbounded_size(runtime, args):
    _, calls = runtime
    assert "error" in json.loads(plugin._capture(args, "ui-review", task_id="review-1"))
    assert calls == []


def test_wrong_profile_and_missing_runtime_task_refused(runtime):
    _, calls = runtime
    assert "error" in json.loads(plugin._capture({"width": 375, "height": 812}, "ux-persona", task_id="review-1"))
    assert "error" in json.loads(plugin._capture({"width": 375, "height": 812}, "ui-review"))
    assert calls == []


def test_missing_session_profile_fails_closed(runtime):
    from gateway.session_context import set_session_vars
    _, calls = runtime
    set_session_vars(platform="cli", session_id="client-review", profile="")
    assert "error" in json.loads(plugin._capture({"width": 375, "height": 812}, "ui-review", task_id="review-1"))
    assert calls == []


def test_symlink_workspace_does_not_create_foreign_files(runtime, tmp_path):
    home, calls = runtime
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (home / "workspace").symlink_to(foreign, target_is_directory=True)
    assert "error" in json.loads(plugin._capture({"width": 375, "height": 812}, "ui-review", task_id="review-1"))
    assert not list(foreign.iterdir()) and not calls
