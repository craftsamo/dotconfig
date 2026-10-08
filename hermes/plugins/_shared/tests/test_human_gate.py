"""human_gate: when no person can answer an approval card, a messaging write is refused."""

import builtins
import importlib.util
from pathlib import Path
import sys
import types

import pytest

spec = importlib.util.spec_from_file_location("human_gate_under_test",
                                              Path(__file__).resolve().parent.parent / "human_gate.py")
hg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hg)

CLI, GATEWAY, ASK, NOBODY = (None, True, False, False), (None, False, True, False), (None, False, False, True), \
    (None, False, False, False)


def hermes(monkeypatch, *, yolo=False, mode="manual", cron=False, single=False, platform="telegram",
           presence=GATEWAY):
    """A stand-in for Hermes' approval modules, so each situation can be set up on its own."""
    approval = types.SimpleNamespace(_yolo_active=lambda: yolo, _presence=lambda: presence)
    context = types.SimpleNamespace(
        _get_approval_mode=lambda: mode, _is_cron_approval_context=lambda: cron,
        _is_single_query_approval_context=lambda: single, _get_session_platform=lambda: platform)
    tools = types.ModuleType("tools")
    tools.approval, tools.approval_context = approval, context
    monkeypatch.setitem(sys.modules, "tools", tools)


# `presence` is (callback, is_cli, is_gateway, is_ask); the three that count as "a person can answer":
PERSON = {"an interactive terminal": (None, True, False, False), "a chat gateway": (None, False, True, False),
          "an ask bridge": (None, False, False, True)}


@pytest.mark.parametrize("where", sorted(PERSON))
def test_a_person_who_can_answer_lets_the_card_through(monkeypatch, where):
    hermes(monkeypatch, presence=PERSON[where])
    assert hg.no_human() is None


@pytest.mark.parametrize("setup, reason", [
    ({"yolo": True}, "yolo mode is on"),
    ({"mode": "off"}, "approvals are off (approvals.mode: off)"),
    ({"cron": True}, "this is a cron job"),
    ({"single": True}, "this is a single-query run"),
    ({"platform": "webhook"}, "this platform is unattended"),
    ({"platform": "msgraph_webhook"}, "this platform is unattended"),
    ({"platform": "api_server"}, "this platform is unattended"),
    ({"presence": (None, False, False, False)}, "nobody is present to answer"),
])
def test_each_way_around_the_card_is_named(monkeypatch, setup, reason):
    hermes(monkeypatch, **setup)
    assert hg.no_human() == reason


def test_hermes_dash_z_is_yolo_so_it_is_refused(monkeypatch):
    """`hermes -z` sets HERMES_YOLO_MODE=1 before it runs the agent; Hermes then approves every card unasked.
    Even with a person present in some other sense, YOLO wins: the card would never be shown."""
    hermes(monkeypatch, yolo=True, presence=PERSON["an interactive terminal"])
    assert hg.no_human() == "yolo mode is on"


def test_yolo_is_judged_before_the_presence_of_a_person(monkeypatch):
    hermes(monkeypatch, yolo=True, cron=True, single=True, platform="webhook")
    assert hg.no_human() == "yolo mode is on"


def test_it_fails_closed_when_hermes_cannot_be_read(monkeypatch):
    monkeypatch.setitem(sys.modules, "tools", None)             # `from tools import ...` raises ImportError
    assert hg.no_human() == "Hermes' approval context could not be read"

    real_import = builtins.__import__

    def broken(name, *args, **kwargs):
        if name == "tools":
            raise RuntimeError("no hermes here")
        return real_import(name, *args, **kwargs)

    monkeypatch.undo()
    monkeypatch.setattr(builtins, "__import__", broken)
    assert hg.no_human() == "Hermes' approval context could not be read"


def test_a_check_that_itself_breaks_fails_closed(monkeypatch):
    hermes(monkeypatch)
    sys.modules["tools"].approval._presence = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    assert hg.no_human() == "Hermes' approval context could not be read"


def test_the_refusal_says_what_did_not_happen_why_and_what_to_do():
    text = hg.refusal("discord_account", "yolo mode is on")
    assert text.startswith("discord_account: not done.") and "yolo mode is on" in text
    assert "Nothing was sent or changed" in text and "chat with the Assistant" in text
