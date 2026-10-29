"""OpenAI-shaped client over Antigravity's ``v1internal`` inference.

Built on Hermes' native Gemini client: the same request builder and response translation, with
a Bearer token instead of an API key, the Cloud Code envelope around each request and the
``response`` wrapper taken off each reply. Subclassing ``GeminiNativeClient`` also gives the
auxiliary path its async wrapper.
"""

from __future__ import annotations

import json
from typing import Any, Iterator, Optional
from urllib.parse import urlparse

import httpx

from agent.gemini_native_adapter import (
    GeminiAPIError,
    GeminiNativeClient,
    build_gemini_request,
    gemini_http_error,
    translate_gemini_response,
    translate_stream_event,
)

from . import control, wire

try:
    from agent.bounded_response import read_streaming_error_body
except ImportError:  # older runtimes
    def read_streaming_error_body(response: httpx.Response) -> str:
        return response.read().decode("utf-8", errors="replace")


def _origin(base_url: Optional[str]) -> str:
    parsed = urlparse(str(base_url or "").strip())
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return wire.DAILY_ENDPOINT


def _events(response: httpx.Response) -> Iterator[dict[str, Any]]:
    buffer = ""
    for chunk in response.iter_text():
        buffer += chunk or ""
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            if (event := _event(line)) is not None:
                yield event
    if buffer and (event := _event(buffer)) is not None:
        yield event


def _event(line: str) -> Optional[dict[str, Any]]:
    line = line.rstrip("\r")
    if not line.startswith("data:"):
        return None
    data = line[5:].strip()
    if not data or data == "[DONE]":
        return None
    try:
        return wire.unwrap(json.loads(data))
    except json.JSONDecodeError:
        return None


def _restore_names(choice_part: Any, names: dict[str, str]) -> None:
    for call in getattr(choice_part, "tool_calls", None) or []:
        function = getattr(call, "function", None)
        if function is not None and getattr(function, "name", None) in names:
            function.name = names[function.name]


class AntigravityClient(GeminiNativeClient):
    MISSING_KEY_ERROR = "Antigravity: no signed-in account. Run `hermes auth add antigravity`."

    def __init__(self, *, api_key: str, base_url: Optional[str] = None, timeout: Any = None,
                 http_client: Optional[httpx.Client] = None, **_: Any) -> None:
        # Configured default headers are left out on purpose: the request carries the
        # Antigravity client's own identity and nothing else.
        super().__init__(api_key=api_key, timeout=timeout, http_client=http_client)
        self.base_url = _origin(base_url)

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _request_headers(self, model: str, *, stream: bool) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
            **self._auth_headers(),
            "User-Agent": control.user_agent(),
        }
        if wire.claude_thinks(model):
            headers["anthropic-beta"] = wire.INTERLEAVED_BETA
        return headers

    def _http_error(self, response: httpx.Response, body_text: Optional[str] = None) -> GeminiAPIError:
        if body_text is None:
            try:
                body_text = response.text
            except Exception:
                body_text = ""
        error = gemini_http_error(response, body_text=body_text, key_guidance=False)
        delay = wire.retry_delay(body_text or "")
        if delay is not None:
            # Hermes' retry policy and rate-limit classifier read ``body.retry_after`` (or a
            # Retry-After header), not this exception's attribute.
            try:
                body = json.loads(body_text or "{}")
            except ValueError:
                body = {}
            body = body if isinstance(body, dict) else {}
            if isinstance(body.get("error"), dict):
                body["error"]["retry_after"] = delay
            body["retry_after"] = delay
            error.body = body
            if error.retry_after is None:
                error.retry_after = delay
        return error

    def _create_chat_completion(
        self, *, model: str = "", messages: Optional[list[dict[str, Any]]] = None, stream: bool = False,
        tools: Any = None, tool_choice: Any = None, temperature: Optional[float] = None,
        max_tokens: Optional[int] = None, top_p: Optional[float] = None, stop: Any = None,
        response_format: Any = None, extra_body: Optional[dict[str, Any]] = None, timeout: Any = None, **_: Any,
    ) -> Any:
        messages = messages or []
        extra = extra_body if isinstance(extra_body, dict) else {}
        thinking = extra.get("thinking_config") or extra.get("thinkingConfig")
        claude = wire.is_claude(model)
        request = build_gemini_request(
            messages=messages, tools=tools, tool_choice=tool_choice, temperature=temperature, max_tokens=max_tokens,
            top_p=top_p, stop=stop, thinking_config=None if claude else thinking,
            response_format=response_format or extra.get("response_format"), model=model, tools_as_json_schema=claude,
        )
        project = control.project_for(self.api_key, self.base_url)
        control.refresh_in_background(self.api_key, self.base_url)
        body, names = wire.envelope(request, model=model, project=project, messages=messages,
                                    claude_thinking=thinking if claude else None, max_tokens=max_tokens,
                                    output_cap=control.limits(model)[1] if claude else None)
        url = f"{self.base_url}/v1internal:"
        if stream:
            return self._stream(model, f"{url}streamGenerateContent?alt=sse", body, names, timeout)
        response = self._http.post(url + "generateContent", json=body,
                                   headers=self._request_headers(model, stream=False), timeout=timeout)
        if response.status_code != 200:
            raise self._http_error(response)
        try:
            payload = wire.unwrap(response.json())
        except ValueError as exc:
            raise GeminiAPIError(f"Invalid JSON from Antigravity: {exc}", code="antigravity_invalid_json",
                                 status_code=response.status_code, response=response) from exc
        result = translate_gemini_response(payload, model=model)
        for choice in getattr(result, "choices", None) or []:
            _restore_names(getattr(choice, "message", None), names)
        return result

    def _stream(self, model: str, url: str, body: dict[str, Any], names: dict[str, str], timeout: Any) -> Iterator[Any]:
        tool_call_indices: dict[str, dict[str, Any]] = {}
        try:
            with self._http.stream("POST", url, json=body, headers=self._request_headers(model, stream=True),
                                   timeout=timeout) as response:
                if response.status_code != 200:
                    raise self._http_error(response, read_streaming_error_body(response))
                for event in _events(response):
                    for chunk in translate_stream_event(event, model, tool_call_indices):
                        for choice in getattr(chunk, "choices", None) or []:
                            _restore_names(getattr(choice, "delta", None), names)
                        yield chunk
        except httpx.HTTPError as exc:
            raise GeminiAPIError(f"Antigravity streaming request failed: {exc}",
                                 code="antigravity_stream_error") from exc
