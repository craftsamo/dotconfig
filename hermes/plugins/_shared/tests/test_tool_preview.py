"""tool_preview: a plugin tool's progress line names its operation, never what the call carries."""

import importlib.util
from pathlib import Path
import sys
import types

import pytest

spec = importlib.util.spec_from_file_location("tool_preview_under_test",
                                              Path(__file__).resolve().parent.parent / "tool_preview.py")
tp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tp)


def schema(**enums):
    return {"name": "t", "parameters": {"type": "object", "properties": {
        key: {"type": "string", "enum": list(values)} for key, values in enums.items()}}}


@pytest.fixture
def table(monkeypatch):
    """A stand-in for Hermes' preview table, with a builder Hermes owns."""
    display = types.ModuleType("agent.display")
    display._PREVIEW_BUILDERS = {"terminal": lambda args, max_len: "hermes"}
    agent = types.ModuleType("agent")
    agent.display = display
    monkeypatch.setitem(sys.modules, "agent", agent)
    monkeypatch.setitem(sys.modules, "agent.display", display)
    monkeypatch.setattr(tp, "_CHOICES", {})
    return display._PREVIEW_BUILDERS


def test_enums_show_only_declared_choices(table):
    assert tp.enums("chat", schema(action=["send", "search"], kind=["dm"]), "action", "kind")
    line = lambda **args: table["chat"](args, 0)
    assert line(action="send", text="the whole private message") == "send"
    assert line(action="search", kind="dm", query="someone's name") == "search dm"
    assert line(action="send; rm -rf ~") is None
    assert line(text="no action at all") is None


def test_choices_of_every_registering_profile_are_kept(table):
    tp.enums("note", schema(action=["status", "search"]), "action")
    tp.enums("note", schema(action=["check"]), "action")
    assert [table["note"]({"action": a}, 0) for a in ("search", "check")] == ["search", "check"]


def test_array_item_choices_count_as_choices():
    assert tp.choices({"parameters": {"properties": {"modes": {"type": "array", "items": {
        "type": "string", "enum": ["outline", "terms"]}}}}}, "modes") == {"outline", "terms"}


def test_hermes_own_builder_is_never_replaced(table):
    assert tp.fixed("terminal", "mine") is False
    assert table["terminal"]({}, 0) == "hermes"


def test_a_reinstall_replaces_the_plugins_own_builder(table):
    tp.fixed("speech", "speech")
    assert tp.fixed("speech", "voice") is True
    assert table["speech"]({"text": "x"}, 0) == "voice"


def test_a_failing_builder_shows_the_bare_tool(table):
    tp.install("broken", lambda args: 1 / 0)
    assert table["broken"]({"action": "x"}, 0) is None


def test_long_labels_are_clipped(table):
    tp.fixed("long", "a" * 50)
    assert table["long"]({"x": 1}, 10) == "a" * 9 + "…"
    assert table["long"]({"x": 1}, 0) == "a" * 50


def test_without_the_table_the_tool_still_registers(monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "agent", types.ModuleType("agent"))
    monkeypatch.setitem(sys.modules, "agent.display", None)
    assert tp.fixed("anything", "x") is False
    assert "not installed" in caplog.text
