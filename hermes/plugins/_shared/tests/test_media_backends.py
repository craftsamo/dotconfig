"""media_backends: a media tool's backends are read in order and tried in order."""

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location("media_backends_under_test",
                                              Path(__file__).resolve().parent.parent / "media_backends.py")
mb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mb)

DEFAULT = ("openrouter", "xiaomi/mimo-v2.5")


def reply(content, reasoning=None, finish_reason="stop"):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content, reasoning=reasoning),
                                                    finish_reason=finish_reason)])


def test_backends_are_read_in_order_without_duplicates():
    section = {"backends": [{"provider": "a", "model": "m1"}, {"provider": "b", "model": "m2"},
                            {"provider": "a", "model": "m1"}, {"provider": "c"}, "junk"],
               "provider": "ignored", "model": "ignored"}
    assert mb.backends_from(section, DEFAULT) == [("a", "m1"), ("b", "m2")]


def test_the_single_form_and_the_default_still_read():
    assert mb.backends_from({"provider": "openrouter", "model": "x"}, DEFAULT) == [("openrouter", "x")]
    assert mb.backends_from({"backends": []}, DEFAULT) == [DEFAULT]
    assert mb.backends_from(None, DEFAULT) == [DEFAULT]


def test_an_unreadable_config_falls_back_to_the_default(monkeypatch):
    import hermes_cli.config as config

    monkeypatch.setattr(config, "load_config", lambda: (_ for _ in ()).throw(OSError("gone")))
    assert mb.configured_backends("video_analyze", DEFAULT) == [DEFAULT]


def test_answer_text_never_takes_the_reasoning():
    assert mb.answer_text(reply("  seen  ")) == "seen"
    assert mb.answer_text(reply(None, reasoning="where is the video?")) == ""
    assert mb.answer_text(reply([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}])) == "ab"
    assert mb.answer_text(object()) == ""


def _calls(*outcomes):
    seen = []

    async def call(**kwargs):
        seen.append((kwargs["provider"], kwargs["model"]))
        outcome = outcomes[len(seen) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return call, seen


def test_the_first_backend_with_text_answers_and_earlier_failures_are_listed():
    call, seen = _calls(RuntimeError("HTTP 429"), reply("from b"))
    result = asyncio.run(mb.analyze([("a", "1"), ("b", "2"), ("c", "3")], [], call=call))
    assert seen == [("a", "1"), ("b", "2")]
    assert (result["provider"], result["model"], result["analysis"]) == ("b", "2", "from b")
    assert result["failed"] == [{"provider": "a", "model": "1", "error": "RuntimeError HTTP 429"}]


def test_an_empty_reply_is_retried_once_then_the_next_backend_tries():
    call, seen = _calls(reply(None, reasoning="thinking only"), reply(""), reply("from b"))
    result = asyncio.run(mb.analyze([("a", "1"), ("b", "2")], [], call=call))
    assert seen == [("a", "1"), ("a", "1"), ("b", "2")]
    assert result["failed"][0]["error"] == "the reply had no text"


def test_a_backend_is_called_directly_and_only_that_backend(monkeypatch):
    import agent.auxiliary_client as aux

    seen = {}

    class Completions:
        async def create(self, **kwargs):
            seen["create"] = kwargs
            return reply("heard")

    def resolve(provider, model=None, async_mode=False, **_):
        seen["resolve"] = (provider, model, async_mode)
        return SimpleNamespace(chat=SimpleNamespace(completions=Completions())), model

    monkeypatch.setattr(aux, "resolve_provider_client", resolve)
    monkeypatch.setattr(aux, "async_call_llm", lambda **kw: pytest.fail("the fallback-ladder path must not be used"))
    result = asyncio.run(mb.analyze([("provider-a", "model-a")], [{"role": "user", "content": "x"}]))
    assert result["analysis"] == "heard" and seen["resolve"] == ("provider-a", "model-a", True)
    assert seen["create"]["model"] == "model-a" and seen["create"]["messages"] == [{"role": "user", "content": "x"}]


def test_a_backend_with_no_login_fails_without_a_request(monkeypatch):
    import agent.auxiliary_client as aux

    monkeypatch.setattr(aux, "resolve_provider_client", lambda *a, **k: (None, None))
    with pytest.raises(mb.AllBackendsFailed) as raised:
        asyncio.run(mb.analyze([("provider-a", "model-a")], []))
    assert raised.value.failures[0]["error"] == "RuntimeError no client for provider-a (no login or key)"


def test_an_error_summary_keeps_type_status_and_a_short_first_line():
    class HTTPError(Exception):
        status_code = 404

    assert mb._summary(HTTPError("not found\nhttps://example.com/v1?key=secret")) == "HTTPError HTTP 404 not found"
    assert len(mb._summary(RuntimeError("x" * 500))) <= len("RuntimeError ") + 120


def test_an_answer_cut_off_at_the_output_limit_moves_on_without_a_retry():
    call, seen = _calls(reply("overview, then noth", finish_reason="length"), reply("full answer"))
    result = asyncio.run(mb.analyze([("a", "1"), ("b", "2")], [], call=call))
    assert seen == [("a", "1"), ("b", "2")]
    assert (result["provider"], result["analysis"], result["truncated"]) == ("b", "full answer", False)
    assert result["failed"] == [{"provider": "a", "model": "1", "error": "the answer was cut off at the output limit"}]


def test_when_nothing_answers_in_full_the_first_partial_answer_comes_back_marked():
    call, _ = _calls(reply("first part", finish_reason="length"), RuntimeError("down"),
                     reply("second part", finish_reason="MAX_TOKENS"))
    result = asyncio.run(mb.analyze([("a", "1"), ("b", "2"), ("c", "3")], [], call=call))
    assert (result["provider"], result["analysis"], result["truncated"]) == ("a", "first part", True)
    assert [f["provider"] for f in result["failed"]] == ["b", "c"]


def test_the_output_cap_leaves_room_for_hidden_thinking():
    call, _ = _calls(reply("ok"))
    seen = {}

    async def spy(**kwargs):
        seen.update(kwargs)
        return await call(**kwargs)

    asyncio.run(mb.analyze([("a", "1")], [], call=spy))
    assert seen["max_tokens"] == mb.MAX_OUTPUT_TOKENS >= 16384


def test_no_answer_anywhere_raises_with_every_failure():
    call, _ = _calls(RuntimeError("down"), reply(""), reply(""))
    with pytest.raises(mb.AllBackendsFailed) as raised:
        asyncio.run(mb.analyze([("a", "1"), ("b", "2")], [], call=call))
    assert [f["provider"] for f in raised.value.failures] == ["a", "b"]
