from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1] / "__init__.py"
SPEC = importlib.util.spec_from_file_location("vision_window", PLUGIN)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture(autouse=True)
def clean_state():
    MODULE._step_counts.clear()
    MODULE._turn_views.clear()


def image(blob: str) -> dict:
    return {"_multimodal": True, "content": [
        {"type": "text", "text": "Image loaded into your context"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{blob}"}}],
        "text_summary": "x"}


def call(blob, path="f.png", turn="t1", step="t1:api:1", session="s"):
    return MODULE._transform(tool_name="vision_analyze", args={"image_url": path}, result=image(blob),
                             session_id=session, turn_id=turn, api_request_id=step, tool_call_id="c")


def test_first_three_images_of_a_step_pass_through_and_the_rest_say_not_shown():
    results = [call(f"img{i}", path=f"f{i}.png") for i in range(29)]
    assert results[:3] == [None, None, None]
    assert all(r.startswith("[Image not shown: f") for r in results[3:])
    assert "f3.png" in results[3] and "request it again in your next step" in results[3]


def test_next_step_gets_a_fresh_window():
    for i in range(4):
        call(f"a{i}", step="t1:api:1")
    assert call("b0", step="t1:api:2") is None


def test_identical_image_is_shown_three_times_per_turn():
    for n in range(MODULE.REPEAT_LIMIT):
        assert call("same", step=f"t1:api:{n}") is None
    again = call("same", step="t1:api:9")
    assert again.startswith("[Image not shown again") and "3 times" in again
    assert call("changed", step="t1:api:10") is None
    assert call("same", turn="t2", step="t2:api:1") is None


def test_images_that_were_not_shown_do_not_count_as_views():
    for i in range(3):
        call(f"x{i}", step="t1:api:1")
    assert call("late", step="t1:api:1").startswith("[Image not shown:")
    for n in range(MODULE.REPEAT_LIMIT):
        assert call("late", step=f"t1:api:{n + 2}") is None


def test_other_tools_and_text_results_are_untouched():
    assert MODULE._transform(tool_name="read_file", args={}, result=image("a")) is None
    assert MODULE._transform(tool_name="vision_analyze", args={}, result='{"analysis": "text"}') is None


def test_hook_is_registered_on_transform_tool_result():
    hooks = []
    MODULE.register(type("Ctx", (), {"register_hook": lambda self, n, f: hooks.append((n, f))})())
    assert hooks == [("transform_tool_result", MODULE._transform)]
