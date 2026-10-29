from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE = "antigravity_provider_under_test"


def _load():
    if PACKAGE in sys.modules:
        return sys.modules[PACKAGE]
    spec = importlib.util.spec_from_file_location(
        PACKAGE, PLUGIN_DIR / "__init__.py", submodule_search_locations=[str(PLUGIN_DIR)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = module
    spec.loader.exec_module(module)
    return module


PLUGIN = _load()
wire = sys.modules[f"{PACKAGE}.wire"]
control = sys.modules[f"{PACKAGE}.control"]
oauth = sys.modules[f"{PACKAGE}.oauth"]

from agent.gemini_native_adapter import GeminiAPIError, build_gemini_request  # noqa: E402

client_module = importlib.import_module(f"{PACKAGE}.client")

TOOLS = [
    {"type": "function", "function": {
        "name": "mcp.files.read", "description": "Read a file",
        "parameters": {"type": "object", "properties": {"path": {"type": "string", "minLength": 1}},
                       "required": ["path", "gone"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "ping", "parameters": {"type": "object", "properties": {}}}},
]
HISTORY = [
    {"role": "system", "content": "Be brief."},
    {"role": "user", "content": "Read a and b"},
    {"role": "assistant", "content": "", "tool_calls": [
        {"id": "call_a", "type": "function", "function": {"name": "mcp.files.read", "arguments": '{"path": "a"}'}},
        {"id": "call_b", "type": "function", "function": {"name": "mcp.files.read", "arguments": '{"path": "b"}'}},
    ]},
    {"role": "tool", "tool_call_id": "call_a", "content": "A"},
    {"role": "tool", "tool_call_id": "call_b", "content": "B"},
]


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setattr(control, "_hub_version", "2.24.0")
    monkeypatch.setattr(control, "_projects", {})
    monkeypatch.setattr(control, "_catalog", {})
    monkeypatch.setattr(control, "_catalog_fetched_at", 0.0)
    monkeypatch.setattr(control, "_catalog_path", lambda: tmp_path / "cache" / "antigravity" / "catalog.json")


def _gemini_request(model, messages=HISTORY, tools=TOOLS, thinking=None, max_tokens=None):
    return build_gemini_request(messages=messages, tools=tools, model=model, thinking_config=thinking,
                                max_tokens=max_tokens, tools_as_json_schema=wire.is_claude(model))


def _parts(body):
    return [p for c in body["request"]["contents"] for p in c["parts"]]


# ── Thinking ────────────────────────────────────────────────────────────────


def test_claude_thinking_model_gets_a_snake_case_budget_from_the_effort():
    assert wire.thinking_config("claude-opus-4-6-thinking", None) == {"include_thoughts": True, "thinking_budget": 32768}
    assert wire.thinking_config("claude-opus-4-6-thinking", {"effort": "low"})["thinking_budget"] == 8192
    assert wire.thinking_config("claude-opus-4-6-thinking", {"effort": "xhigh"})["thinking_budget"] == 32768
    assert wire.thinking_config("claude-opus-4-6-thinking", {"enabled": False})["include_thoughts"] is False


def test_models_without_a_thinking_knob_get_none():
    assert wire.thinking_config("claude-sonnet-4-6", {"effort": "high"}) is None
    assert wire.thinking_config("gpt-oss-120b-medium", {"effort": "high"}) is None


def test_a_gemini_id_with_an_effort_suffix_keeps_its_own_effort():
    assert wire.thinking_config("gemini-3.8-flash-high", {"effort": "low"}) == {"includeThoughts": True}
    assert wire.thinking_config("gemini-3.8-flash-high", {"effort": "none"}) == {"includeThoughts": False}


def test_a_bare_gemini_id_goes_through_hermes_gemini_translation():
    config = wire.thinking_config("gemini-3-flash", {"effort": "high"})
    assert config and config.get("includeThoughts") is True


def test_the_profile_puts_thinking_in_extra_body():
    profile = PLUGIN.antigravity
    assert profile.build_extra_body(model="claude-opus-4-6-thinking", reasoning_config={"effort": "medium"}) == {
        "thinking_config": {"include_thoughts": True, "thinking_budget": 16384}}
    assert profile.build_extra_body(model="claude-sonnet-4-6", reasoning_config=None) == {}


# ── Claude schemas and names ────────────────────────────────────────────────


def test_claude_schema_keeps_what_claude_accepts():
    schema = wire.claude_tool_schema({
        "$schema": "x", "type": "object", "title": "T", "additionalProperties": False,
        "properties": {
            "mode": {"const": "fast"},
            "maybe": {"type": ["string", "null"], "format": "uri"},
            "either": {"anyOf": [{"type": "null"}, {"type": "object", "properties": {"k": {"type": "integer"}}}]},
            "pick": {"oneOf": [{"enum": ["a"]}, {"enum": ["b"]}]},
            "ref": {"$ref": "#/$defs/Thing"},
            "list": {"type": "array"},
            "empty": {"type": "object"},
        },
        "required": ["mode", "missing"],
    })
    props = schema["properties"]
    assert schema["type"] == "object" and "title" not in schema and "additionalProperties" not in schema
    assert props["mode"] == {"enum": ["fast"], "type": "string"}
    assert props["maybe"] == {"type": "string"}
    assert props["either"]["type"] == "object" and props["either"]["properties"]["k"] == {"type": "integer"}
    assert props["pick"]["enum"] == ["a", "b"]
    assert props["ref"] == {"type": "object", "description": "See: Thing"}
    assert props["list"]["items"] == {"type": "string"}
    assert props["empty"]["required"] == ["_placeholder"]
    assert schema["required"] == ["mode"]


def test_an_argument_free_tool_gets_the_placeholder():
    assert wire.claude_tool_schema({"type": "object", "properties": {}})["required"] == ["_placeholder"]
    assert wire.claude_tool_schema(None)["properties"]["_placeholder"]["type"] == "boolean"


def test_claude_tool_names_are_wire_safe_and_unique():
    names = wire.claude_tool_names(["a.b", "a_b", "x" * 80])
    assert names["a.b"] == "a_b" and names["a_b"] == "a_b_1"
    assert len(names["x" * 80]) == 64


# ── Envelope ────────────────────────────────────────────────────────────────


def test_claude_envelope():
    thinking = wire.thinking_config("claude-opus-4-6-thinking", None)
    request = _gemini_request("claude-opus-4-6-thinking")
    body, names = wire.envelope(request, model="claude-opus-4-6-thinking", project="proj", messages=HISTORY,
                                claude_thinking=thinking, max_tokens=4096)
    assert body["project"] == "proj" and body["model"] == "claude-opus-4-6-thinking"
    assert body["requestType"] == "agent" and body["userAgent"] == "antigravity"
    assert body["requestId"].startswith("agent-")
    inner = body["request"]
    assert inner["sessionId"].endswith(":claude-opus-4-6-thinking:proj:" + inner["sessionId"].rsplit(":", 1)[1])
    assert inner["toolConfig"] == {"functionCallingConfig": {"mode": "VALIDATED"}}
    declarations = inner["tools"][0]["functionDeclarations"]
    assert [d["name"] for d in declarations] == ["mcp_files_read", "ping"]
    assert declarations[0]["parameters"]["required"] == ["path"]
    assert "minLength" not in declarations[0]["parameters"]["properties"]["path"]
    assert "parametersJsonSchema" not in declarations[0]
    assert names == {"mcp_files_read": "mcp.files.read"}
    generation = inner["generationConfig"]
    assert generation["thinkingConfig"] == {"include_thoughts": True, "thinking_budget": 32768}
    assert generation["maxOutputTokens"] == 64000  # 4096 is below the thinking budget
    system = inner["systemInstruction"]
    assert system["role"] == "user"
    assert system["parts"][0]["text"].startswith(wire.SYSTEM_PREAMBLE) and "Be brief." in system["parts"][0]["text"]
    assert system["parts"][-1]["text"] == wire.INTERLEAVED_HINT
    calls = [p for p in _parts(body) if "functionCall" in p]
    responses = [p for p in _parts(body) if "functionResponse" in p]
    assert [c["functionCall"]["id"] for c in calls] == [r["functionResponse"]["id"] for r in responses]
    assert all(c["functionCall"]["name"] == "mcp_files_read" for c in calls)
    assert calls[0]["thoughtSignature"] == calls[0]["thought_signature"] == wire.SKIP_SIGNATURE
    assert "thoughtSignature" not in calls[1]


def test_claude_without_thinking_caps_output_and_sends_no_thinking():
    request = _gemini_request("claude-sonnet-4-6", tools=None, messages=HISTORY[:2], max_tokens=200000)
    body, _ = wire.envelope(request, model="claude-sonnet-4-6", project="p", messages=HISTORY[:2], max_tokens=200000)
    generation = body["request"]["generationConfig"]
    assert "thinkingConfig" not in generation and generation["maxOutputTokens"] == wire.CLAUDE_MAX_OUTPUT
    assert "toolConfig" not in body["request"]
    assert len(body["request"]["systemInstruction"]["parts"]) == 1


def test_claude_output_cap_follows_the_model_limit_it_is_given():
    request = _gemini_request("claude-opus-5-5-high", tools=None, messages=HISTORY[:2])
    unbounded, _ = wire.envelope(request, model="claude-opus-5-5-high", project="p", messages=HISTORY[:2],
                                 output_cap=128000)
    assert unbounded["request"]["generationConfig"]["maxOutputTokens"] == 128000
    asked, _ = wire.envelope(request, model="claude-opus-5-5-high", project="p", messages=HISTORY[:2],
                             max_tokens=200000, output_cap=128000)
    assert asked["request"]["generationConfig"]["maxOutputTokens"] == 128000
    smaller, _ = wire.envelope(request, model="claude-opus-5-5-high", project="p", messages=HISTORY[:2],
                               max_tokens=9000, output_cap=128000)
    assert smaller["request"]["generationConfig"]["maxOutputTokens"] == 9000


def test_gemini_envelope_keeps_a_real_signature_and_fills_a_missing_one():
    real = "s" * 60
    messages = [HISTORY[1], {"role": "assistant", "content": "", "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "ping", "arguments": "{}"},
         "extra_content": {"google": {"thought_signature": real}}}]},
        {"role": "tool", "tool_call_id": "c1", "content": "ok"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c2", "type": "function", "function": {"name": "ping", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c2", "content": "ok"}]
    request = _gemini_request("gemini-3-flash", messages=messages)
    body, names = wire.envelope(request, model="gemini-3-flash", project="p", messages=messages)
    calls = [p for p in _parts(body) if "functionCall" in p]
    assert calls[0]["thoughtSignature"] == real
    assert calls[1]["thoughtSignature"] == wire.SKIP_SIGNATURE
    assert names == {} and body["request"]["systemInstruction"]["parts"][0]["text"] == wire.SYSTEM_PREAMBLE


def test_envelope_does_not_modify_the_request_it_was_given():
    request = _gemini_request("claude-opus-4-6-thinking")
    before = json.dumps(request, sort_keys=True)
    wire.envelope(request, model="claude-opus-4-6-thinking", project="p", messages=HISTORY)
    assert json.dumps(request, sort_keys=True) == before


def test_session_id_is_stable_for_one_conversation_and_differs_across_them():
    first = wire.session_id(HISTORY, model="m", project="p")
    assert first == wire.session_id(HISTORY + [{"role": "user", "content": "more"}], model="m", project="p")
    assert first != wire.session_id([{"role": "user", "content": "other"}], model="m", project="p")


# ── Replies ─────────────────────────────────────────────────────────────────


def test_unwrap_takes_the_response_out_of_its_envelope():
    assert wire.unwrap([{"response": {"candidates": []}}]) == {"candidates": []}
    assert wire.unwrap({"candidates": [1]}) == {"candidates": [1]}


def test_retry_delay_reads_retry_info_then_quota_reset():
    body = {"error": {"details": [
        {"@type": "type.googleapis.com/google.rpc.ErrorInfo", "metadata": {"quotaResetDelay": "1h16m0.5s"}},
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "60s"}]}}
    assert wire.retry_delay(json.dumps(body)) == 60
    del body["error"]["details"][1]
    assert wire.retry_delay(json.dumps(body)) == pytest.approx(4560.5)
    assert wire.retry_delay("not json") is None


def test_catalog_keeps_selectable_chat_models_in_the_client_order():
    payload = {
        "models": {
            "claude-opus-4-6-thinking": {"displayName": "Opus", "maxTokens": 200000, "maxOutputTokens": 64000},
            "gemini-3-flash": {"maxTokens": 1048576, "maxOutputTokens": 65536, "supportsImages": True},
            "gemini-3-pro-image": {},
            "gemini-old-disabled": {},
            "chat_20706": {},
            "gpt-oss-120b-medium": {"disabled": True},
            "claude-hidden": {},
        },
        "agentModelSorts": [{"groups": [{"modelIds": ["gemini-3-flash", "claude-opus-4-6-thinking", "gemini-3-pro-image"]}]}],
    }
    catalog = wire.parse_catalog(payload)
    assert [m["id"] for m in catalog] == ["gemini-3-flash", "claude-opus-4-6-thinking"]
    assert catalog[0]["context"] == 1048576 and catalog[1]["name"] == "Opus"


# ── Client ──────────────────────────────────────────────────────────────────


def _client(handler, monkeypatch, project="proj"):
    monkeypatch.setattr(control, "project_for", lambda token, base=None: project)
    monkeypatch.setattr(control, "refresh_in_background", lambda token, base=None: None)
    return client_module.AntigravityClient(api_key="tok", base_url=wire.DAILY_ENDPOINT + "/v1",
                                           http_client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_client_sends_the_envelope_with_bearer_auth_and_restores_tool_names(monkeypatch):
    seen = {}

    def handler(request):
        seen["url"], seen["headers"], seen["body"] = str(request.url), request.headers, json.loads(request.content)
        return httpx.Response(200, json={"response": {"candidates": [{"content": {"role": "model", "parts": [
            {"functionCall": {"name": "mcp_files_read", "args": {"path": "c"}, "id": "x"}}]},
            "finishReason": "STOP"}], "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 2}}})

    client = _client(handler, monkeypatch)
    result = client.chat.completions.create(model="claude-opus-4-6-thinking", messages=HISTORY, tools=TOOLS,
                                            extra_body={"thinking_config": wire.thinking_config("claude-opus-4-6-thinking", None)})
    assert seen["url"] == "https://daily-cloudcode-pa.googleapis.com/v1internal:generateContent"
    assert seen["headers"]["authorization"] == "Bearer tok"
    assert seen["headers"]["user-agent"].startswith("antigravity/hub/2.24.0 ")
    assert seen["headers"]["anthropic-beta"] == wire.INTERLEAVED_BETA
    assert "x-goog-api-key" not in seen["headers"] and "x-goog-api-client" not in seen["headers"]
    assert seen["body"]["project"] == "proj" and seen["body"]["request"]["generationConfig"]["thinkingConfig"]["thinking_budget"] == 32768
    call = result.choices[0].message.tool_calls[0]
    assert call.function.name == "mcp.files.read" and json.loads(call.function.arguments) == {"path": "c"}


def test_client_streams_text_thoughts_and_tool_calls(monkeypatch):
    events = [
        {"response": {"candidates": [{"content": {"parts": [{"thought": True, "text": "hmm"}]}}]}},
        {"response": {"candidates": [{"content": {"parts": [{"text": "Hi"}]}}]}},
        {"response": {"candidates": [{"content": {"parts": [
            {"functionCall": {"name": "mcp_files_read", "args": {"path": "d"}, "id": "y"}}]},
            "finishReason": "STOP"}], "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1}}},
    ]
    stream_body = "".join(f"data:{json.dumps(e)}\n\n" for e in events)

    def handler(request):
        assert str(request.url).endswith("/v1internal:streamGenerateContent?alt=sse")
        assert request.headers["accept"] == "text/event-stream"
        return httpx.Response(200, text=stream_body, headers={"content-type": "text/event-stream"})

    chunks = list(_client(handler, monkeypatch).chat.completions.create(
        model="claude-sonnet-4-6", messages=HISTORY, tools=TOOLS, stream=True))
    deltas = [c.choices[0].delta for c in chunks]
    assert any(d.reasoning == "hmm" for d in deltas)
    assert "".join(d.content or "" for d in deltas) == "Hi"
    calls = [tc for d in deltas for tc in (d.tool_calls or [])]
    assert calls and calls[0].function.name == "mcp.files.read"
    assert chunks[-1].choices[0].finish_reason == "tool_calls"


def test_client_asks_claude_for_the_catalog_output_limit(monkeypatch):
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"response": {"candidates": [
            {"content": {"role": "model", "parts": [{"text": "OK"}]}, "finishReason": "STOP"}]}})

    client = _client(handler, monkeypatch)
    control._remember([{"id": "claude-sonnet-5-5-low", "name": "Sonnet", "context": 1000000, "output": 128000}],
                      control.time.time())
    client.chat.completions.create(model="claude-sonnet-5-5-low", messages=HISTORY[:2])
    assert seen["body"]["request"]["generationConfig"]["maxOutputTokens"] == 128000
    client.chat.completions.create(model="claude-sonnet-4-6", messages=HISTORY[:2])  # not in the catalog
    assert seen["body"]["request"]["generationConfig"]["maxOutputTokens"] == wire.CLAUDE_MAX_OUTPUT


def test_a_rate_limit_carries_the_server_retry_delay(monkeypatch):
    body = {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "slow down", "details": [
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "42s"}]}}
    client = _client(lambda request: httpx.Response(429, json=body), monkeypatch)
    with pytest.raises(GeminiAPIError) as raised:
        client.chat.completions.create(model="gemini-3-flash", messages=HISTORY[:2])
    assert raised.value.status_code == 429 and raised.value.retry_after == 42
    # What Hermes' retry policy and its rate-limit reset reader see. (The classifier itself is
    # not called here: it loads the gateway, which changes the card budgets other suites test.)
    from agent.error_classifier import _rate_limit_reset_seconds
    from agent.retry_utils import provider_retry_after_seconds

    assert provider_retry_after_seconds(raised.value) == 42
    assert _rate_limit_reset_seconds("", raised.value.body, {}) == 42
    assert raised.value.body["error"]["status"] == "RESOURCE_EXHAUSTED"


def test_a_streamed_rate_limit_is_raised_with_its_delay(monkeypatch):
    body = {"error": {"code": 429, "message": "x", "details": [
        {"@type": "type.googleapis.com/google.rpc.ErrorInfo", "metadata": {"quotaResetDelay": "90s"}}]}}
    client = _client(lambda request: httpx.Response(429, json=body), monkeypatch)
    stream = client.chat.completions.create(model="gemini-3-flash", messages=HISTORY[:2], stream=True)
    with pytest.raises(GeminiAPIError) as raised:
        next(iter(stream))
    from agent.retry_utils import provider_retry_after_seconds

    assert raised.value.status_code == 429 and provider_retry_after_seconds(raised.value) == 90


def test_the_async_wrapper_streams_through_this_client(monkeypatch):
    import asyncio

    from agent.gemini_native_adapter import AsyncGeminiNativeClient

    event = {"response": {"candidates": [{"content": {"parts": [{"text": "ok"}]}, "finishReason": "STOP"}],
                          "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1}}}
    client = _client(lambda request: httpx.Response(200, text=f"data: {json.dumps(event)}\n"), monkeypatch)

    async def collect():
        stream = await AsyncGeminiNativeClient(client).chat.completions.create(
            model="gemini-3-flash", messages=HISTORY[:2], stream=True)
        return [chunk async for chunk in stream]

    chunks = asyncio.run(collect())
    assert chunks[0].choices[0].delta.content == "ok"
    assert chunks[-1].usage is not None


def test_a_missing_token_is_refused_before_any_request():
    with pytest.raises(RuntimeError, match="hermes auth add antigravity"):
        client_module.AntigravityClient(api_key="")


def test_the_profile_supplies_this_client():
    created = PLUGIN.antigravity.create_client(api_key="tok", base_url=wire.DAILY_ENDPOINT)
    assert isinstance(created, client_module.AntigravityClient)
    assert created.HERMES_SKIP_TRANSPORT_WRAP is True


# ── Control plane ───────────────────────────────────────────────────────────


def _posts(monkeypatch, replies):
    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append((url.rsplit(":", 1)[1], json, headers))
        status, payload = replies.pop(0)
        return httpx.Response(status, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(control.httpx, "post", fake_post)
    return calls


def test_project_comes_from_load_code_assist(monkeypatch):
    calls = _posts(monkeypatch, [(200, {"cloudaicompanionProject": {"id": "proj-1"}})])
    assert control.discover_project("tok") == "proj-1"
    assert calls[0][0] == "loadCodeAssist" and calls[0][1] == {"metadata": {"ideType": "ANTIGRAVITY"}}


def test_an_unassigned_account_is_onboarded_on_its_default_tier(monkeypatch):
    calls = _posts(monkeypatch, [
        (200, {"allowedTiers": [{"id": "free-tier"}, {"id": "standard-tier", "isDefault": True}]}),
        (200, {"done": False}),
        (200, {"done": True, "response": {"cloudaicompanionProject": "proj-2"}}),
    ])
    assert control.discover_project("tok", sleep=lambda s: None) == "proj-2"
    assert [c[0] for c in calls] == ["loadCodeAssist", "onboardUser", "onboardUser"]
    assert calls[1][1]["tier_id"] == "standard-tier" and calls[1][1]["metadata"]["ide_version"] == "2.24.0"


def test_discovery_falls_back_when_the_service_refuses(monkeypatch):
    _posts(monkeypatch, [(403, {"error": {}})])
    assert control.discover_project("tok") == control.FALLBACK_PROJECT


def test_a_pooled_row_supplies_its_project_without_a_request(monkeypatch):
    import hermes_cli.auth as auth

    monkeypatch.setattr(auth, "read_credential_pool", lambda provider: [
        {"access_token": "other", control.PROJECT_KEY: "nope"},
        {"access_token": "tok", control.PROJECT_KEY: "stored"}])
    monkeypatch.setattr(control, "discover_project", lambda *a, **k: pytest.fail("no discovery expected"))
    assert control.project_for("tok") == "stored"


CATALOG_REPLY = {
    "models": {"claude-opus-4-6-thinking": {"maxTokens": 180000, "maxOutputTokens": 60000},
               "gemini-3-flash": {"maxTokens": 1048576, "maxOutputTokens": 65536}},
    "agentModelSorts": [{"groups": [{"modelIds": ["claude-opus-4-6-thinking", "gemini-3-flash"]}]}],
}


def test_limits_fall_back_to_family_values_before_any_catalog():
    assert control.limits("claude-sonnet-4-6") == (200000, 64000)
    assert control.limits("gemini-3.8-flash-high") == (1048576, 65536)
    assert PLUGIN.antigravity.get_model_context_length("claude-sonnet-4-6") == 200000


def test_the_saved_catalog_serves_a_new_process_and_the_picker(monkeypatch):
    monkeypatch.setattr(control, "project_for", lambda token, base=None: "proj")
    _posts(monkeypatch, [(200, CATALOG_REPLY)])
    assert [m["id"] for m in control.fetch_catalog("tok")] == ["claude-opus-4-6-thinking", "gemini-3-flash"]
    control._catalog.clear()  # as a fresh process would start
    assert PLUGIN.antigravity.fallback_models == ("claude-opus-4-6-thinking", "gemini-3-flash")
    assert PLUGIN.antigravity.get_model_context_length("claude-opus-4-6-thinking") == 180000
    assert PLUGIN.antigravity.get_max_tokens("claude-opus-4-6-thinking") == 60000


def test_the_picker_shows_the_static_list_until_a_catalog_exists():
    assert PLUGIN.antigravity.fallback_models == PLUGIN.FALLBACK_MODELS
    from hermes_cli.models import _profile_live_catalog
    from providers import get_provider_profile

    # The picker reads the registered profile's fallback_models, i.e. this property.
    registered = get_provider_profile("antigravity")
    assert type(registered).fallback_models.fget.__qualname__ == "AntigravityProfile.fallback_models"
    assert _profile_live_catalog("antigravity") == list(registered.fallback_models)


def test_a_stale_catalog_is_refreshed_once_in_the_background(monkeypatch):
    started = []

    class FakeThread:
        def __init__(self, target, **_):
            self.target = target

        def start(self):
            started.append(self.target)

    monkeypatch.setattr(control.threading, "Thread", FakeThread)
    control.refresh_in_background("tok")
    control.refresh_in_background("tok")  # one refresh at a time
    assert len(started) == 1
    control._refreshing.clear()
    control._remember([{"id": "gemini-3-flash", "context": 1, "output": 1}], control.time.time())
    control.refresh_in_background("tok")
    assert len(started) == 1  # fresh catalog: nothing to do


def test_manifest_version_is_strict_and_has_a_floor():
    assert control._manifest_version("version: 2.25.1\nfiles:\n") == "2.25.1"
    assert control._manifest_version("version: 2.22.9\n") == ""
    assert control._manifest_version("version: 2.25.1-beta\n") == ""


# ── OAuth ───────────────────────────────────────────────────────────────────


def test_login_needs_the_client_secret_from_the_keychain(monkeypatch):
    from hermes_cli.auth_constants import AuthError

    monkeypatch.delenv(oauth.CLIENT_SECRET_ENV, raising=False)
    with pytest.raises(AuthError) as raised:
        oauth.config()
    assert raised.value.code == "oauth_client_secret_missing"
    assert oauth.config(require_secret=False).extra_token_params == {}


def test_token_requests_carry_the_client_secret(monkeypatch):
    from hermes_cli.auth_oauth_pkce_plugin import validate_config

    monkeypatch.setenv(oauth.CLIENT_SECRET_ENV, "value-from-keychain")
    cfg = oauth.config()
    validate_config("antigravity", cfg)
    assert cfg.extra_token_params == {"client_secret": "value-from-keychain"}
    assert cfg.redirect_port == oauth.REDIRECT_PORT


def test_authorize_url_asks_for_offline_access_on_the_registered_redirect():
    url = httpx.URL(oauth.authorize_url("st", "ch"))
    params = dict(url.params)
    assert params["redirect_uri"] == "http://localhost:51121/oauth-callback"
    assert params["access_type"] == "offline" and params["prompt"] == "consent"
    assert params["code_challenge_method"] == "S256" and params["state"] == "st"
    assert params["scope"].split() == list(oauth.SCOPES)


def test_the_provider_is_registered_hidden_with_its_own_auth_hooks():
    from providers import get_provider_profile

    profile = get_provider_profile("antigravity")
    assert profile is not None and profile.hidden is True and profile.auth_type == "oauth_external"
    for hook, name in ((profile.auth_handler, "auth_handler"), (profile.refresh_credential, "refresh_credential")):
        assert hook.__name__ == name and hook.__module__.endswith(".oauth")
