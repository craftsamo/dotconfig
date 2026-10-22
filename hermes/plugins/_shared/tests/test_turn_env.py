"""turn_env: a per-turn value comes from the launching shell only where the turn runs there."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("turn_env_under_test",
                                              Path(__file__).resolve().parent.parent / "turn_env.py")
te = importlib.util.module_from_spec(spec)
spec.loader.exec_module(te)


@pytest.fixture
def runtime(monkeypatch):
    real = te.gateway_client_runtime

    def set_kind(gateway_client):
        monkeypatch.setattr(te, "gateway_client_runtime", lambda: gateway_client)
    yield set_kind
    real.cache_clear()


def test_a_runtime_that_runs_turns_in_the_cli_reads_its_environment(monkeypatch, runtime):
    monkeypatch.setenv("RESIDENT_TURN_KIND", "reconcile")
    runtime(False)
    assert te.value("RESIDENT_TURN_KIND") == "reconcile"
    assert te.value("RESIDENT_DEADLINE", "inf") == "inf"


def test_a_gateway_client_runtime_never_answers_from_the_gateway_environment(monkeypatch, runtime):
    """A gateway the CLI started on demand can carry a resident's stale values in its own env."""
    monkeypatch.setenv("RESIDENT_TURN_KIND", "reconcile")
    monkeypatch.setenv("RESIDENT_DEADLINE", "1")
    runtime(True)
    assert te.value("RESIDENT_TURN_KIND") == ""
    assert te.value("RESIDENT_DEADLINE", "inf") == "inf"
