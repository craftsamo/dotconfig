"""Antigravity's wire format: a Gemini request inside a Cloud Code Assist envelope.

Claude models are served through the same Gemini-shaped JSON; what differs per family is the
thinking config, the tool schemas, tool-call ids and thought signatures. Everything here is pure
(no I/O), so the client and the tests share one implementation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from collections import defaultdict, deque
from typing import Any

DAILY_ENDPOINT = "https://daily-cloudcode-pa.googleapis.com"

# Accepted by the backend in place of a real thought signature on a replayed function call.
SKIP_SIGNATURE = "skip_thought_signature_validator"
_MIN_SIGNATURE_LENGTH = 50

# Prepended to every system instruction, as the Antigravity client does.
SYSTEM_PREAMBLE = (
    "You are Antigravity, a powerful agentic AI coding assistant designed by the Google DeepMind team "
    "working on Advanced Agentic Coding.\n"
    "You are pair programming with a USER to solve their coding task. The task may require creating a new "
    "codebase, modifying or debugging an existing codebase, or simply answering a question.\n"
    "**Absolute paths only**\n"
    "**Proactiveness**\n"
    "\n"
    "<priority>IMPORTANT: The instructions that follow supersede all above. Follow them as your primary "
    "directives.</priority>\n"
)
INTERLEAVED_HINT = (
    "Interleaved thinking is enabled. You may think between tool calls and after receiving tool results "
    "before deciding the next action or final answer. Do not mention these instructions or any constraints "
    "about thinking blocks; just apply them."
)
INTERLEAVED_BETA = "interleaved-thinking-2025-05-14"

CLAUDE_THINKING_BUDGETS = {"minimal": 8192, "low": 8192, "medium": 16384}
CLAUDE_MAX_THINKING_BUDGET = 32768
CLAUDE_MAX_OUTPUT = 64000

_EFFORT_SUFFIX = re.compile(r"-(minimal|low|medium|high)$")
_CLAUDE_TOOL_NAME = re.compile(r"[^a-zA-Z0-9_-]")
_CLAUDE_SCHEMA_DROP = frozenset({
    "minLength", "maxLength", "exclusiveMinimum", "exclusiveMaximum", "pattern", "minItems", "maxItems",
    "format", "default", "examples", "$schema", "$defs", "definitions", "const", "$ref",
    "additionalProperties", "propertyNames", "title", "$id", "$comment", "allOf", "anyOf", "oneOf",
    "nullable", "minimum", "maximum", "uniqueItems", "minProperties", "maxProperties", "patternProperties",
    "dependentRequired", "dependentSchemas", "if", "then", "else", "not", "contentEncoding",
    "contentMediaType", "readOnly", "writeOnly", "deprecated",
})
_PLACEHOLDER = {"type": "boolean", "description": "Placeholder. Always pass true."}

# One id for this process, so a conversation keeps its server-side session across requests.
_PROCESS_ID = str(uuid.uuid4())


def is_claude(model: str) -> bool:
    return (model or "").strip().lower().startswith("claude-")


def claude_thinks(model: str) -> bool:
    return is_claude(model) and "thinking" in model.lower()


def hub_user_agent(version: str, changelist: str = "") -> str:
    build = f"; cl={changelist}" if changelist else ""
    return f"antigravity/hub/{version} (aidev_client; os_type=darwin; arch=arm64{build})"


# ── Thinking ────────────────────────────────────────────────────────────────


def _disabled(reasoning_config: Any) -> bool:
    if not isinstance(reasoning_config, dict):
        return False
    effort = str(reasoning_config.get("effort") or "").strip().lower()
    return reasoning_config.get("enabled") is False or effort == "none"


def claude_thinking_config(model: str, reasoning_config: Any) -> dict[str, Any] | None:
    """Snake-case thinking config for a Claude ``*-thinking`` model; other Claude models take none."""
    if not claude_thinks(model):
        return None
    effort = ""
    if isinstance(reasoning_config, dict):
        effort = str(reasoning_config.get("effort") or "").strip().lower()
    budget = CLAUDE_THINKING_BUDGETS.get(effort, CLAUDE_MAX_THINKING_BUDGET)
    if _disabled(reasoning_config):
        return {"include_thoughts": False, "thinking_budget": CLAUDE_THINKING_BUDGETS["low"]}
    return {"include_thoughts": True, "thinking_budget": budget}


def thinking_config(model: str, reasoning_config: Any) -> dict[str, Any] | None:
    """What the profile puts in ``extra_body.thinking_config`` for *model*.

    A Gemini id with an effort suffix (``gemini-3.8-flash-high``) owns its effort: only whether
    thoughts come back is sent. A bare Gemini id goes through Hermes' own Gemini translation.
    """
    name = (model or "").strip().lower()
    if is_claude(name):
        return claude_thinking_config(name, reasoning_config)
    if not name.startswith("gemini"):
        return None
    if _EFFORT_SUFFIX.search(name):
        return {"includeThoughts": not _disabled(reasoning_config)}
    try:
        from agent.transports.chat_completions import _build_gemini_thinking_config
    except ImportError:
        return None
    return _build_gemini_thinking_config(name, reasoning_config)


# ── Claude tool schemas ─────────────────────────────────────────────────────


def _merge_schema(into: dict[str, Any], other: dict[str, Any]) -> None:
    if isinstance(other.get("properties"), dict):
        into.setdefault("properties", {}).update(other["properties"])
    if isinstance(other.get("required"), list):
        into["required"] = list(dict.fromkeys([*into.get("required", []), *other["required"]]))
    for key, value in other.items():
        if key not in {"properties", "required"}:
            into.setdefault(key, value)


def _pick_variant(options: list[dict[str, Any]]) -> dict[str, Any]:
    enums = [o for o in options if isinstance(o.get("enum"), list)]
    if enums and len(enums) == len(options):
        values = [v for o in enums for v in o["enum"]]
        return {"type": "string", "enum": list(dict.fromkeys(values))}
    for wanted in ("object", "array"):
        for option in options:
            if option.get("type") == wanted:
                return option
    return options[0] if options else {}


def _clean_schema(node: Any) -> Any:
    if isinstance(node, bool):
        return {"type": "string"} if node else {}
    if not isinstance(node, dict):
        return node
    if isinstance(node.get("$ref"), str):
        name = node["$ref"].rsplit("/", 1)[-1]
        hint = f"See: {name}"
        description = str(node.get("description") or "").strip()
        return {"type": "object", "description": f"{description} ({hint})" if description else hint}
    out = dict(node)
    if "const" in out and "enum" not in out:
        out["enum"] = [out["const"]]
    for sub in out.get("allOf") or []:
        cleaned = _clean_schema(sub)
        if isinstance(cleaned, dict):
            _merge_schema(out, cleaned)
    variants = [_clean_schema(v) for v in (out.get("anyOf") or out.get("oneOf") or [])]
    variants = [v for v in variants if isinstance(v, dict) and v.get("type") != "null"]
    if variants:
        _merge_schema(out, _pick_variant(variants))
    kind = out.get("type")
    if isinstance(kind, list):
        kinds = [k for k in kind if k != "null"]
        out["type"] = kinds[0] if kinds else "string"
    if out.get("enum") is not None and "type" not in out:
        out["type"] = "string"
    for key in _CLAUDE_SCHEMA_DROP:
        out.pop(key, None)
    if isinstance(out.get("properties"), dict):
        out["properties"] = {k: _clean_schema(v) for k, v in out["properties"].items()}
    if "items" in out:
        items = out["items"]
        out["items"] = _clean_schema(items[0] if isinstance(items, list) and items else items)
    if out.get("type") == "array" and not isinstance(out.get("items"), dict):
        out["items"] = {"type": "string"}
    if out.get("type") == "object":
        if not out.get("properties"):
            out["properties"] = {"_placeholder": dict(_PLACEHOLDER)}
            out["required"] = ["_placeholder"]
        elif isinstance(out.get("required"), list):
            out["required"] = [r for r in out["required"] if r in out["properties"]] or None
            if out["required"] is None:
                out.pop("required")
    return out


def claude_tool_schema(schema: Any) -> dict[str, Any]:
    """A JSON Schema reduced to what Claude accepts through Antigravity (lower-case types)."""
    cleaned = _clean_schema(schema if isinstance(schema, dict) else {})
    if not isinstance(cleaned, dict) or not cleaned:
        cleaned = {}
    cleaned.setdefault("type", "object")
    if cleaned["type"] == "object" and not cleaned.get("properties"):
        cleaned["properties"] = {"_placeholder": dict(_PLACEHOLDER)}
        cleaned["required"] = ["_placeholder"]
    return cleaned


def claude_tool_names(names: list[str]) -> dict[str, str]:
    """Original name → wire name: ``[a-zA-Z0-9_-]`` only, at most 64 characters, unique."""
    mapping: dict[str, str] = {}
    taken: set[str] = set()
    for name in names:
        if name in mapping:
            continue
        wire = _CLAUDE_TOOL_NAME.sub("_", name)[:64] or "tool"
        stem, n = wire, 1
        while wire in taken:
            suffix = f"_{n}"
            wire, n = stem[: 64 - len(suffix)] + suffix, n + 1
        mapping[name] = wire
        taken.add(wire)
    return mapping


# ── Contents ────────────────────────────────────────────────────────────────


def _parts(contents: list[dict[str, Any]]):
    for content in contents:
        for part in content.get("parts") or []:
            if isinstance(part, dict):
                yield part


def apply_signatures(contents: list[dict[str, Any]], *, keep: bool) -> None:
    """The first function call of each turn carries a signature (a real one when *keep*, else the
    skip sentinel); later parallel calls carry none. Without *keep* every other signature and
    every thought part is dropped too (Claude cannot verify Gemini's)."""
    for content in contents:
        parts = [p for p in content.get("parts") or [] if isinstance(p, dict)]
        if not keep:
            parts = [p for p in parts if p.get("thought") is not True]
        first = True
        for part in parts:
            if "functionCall" in part:
                if first:
                    sig = part.get("thoughtSignature") if keep else None
                    if not (isinstance(sig, str) and len(sig) >= _MIN_SIGNATURE_LENGTH):
                        sig = SKIP_SIGNATURE
                    part["thoughtSignature"] = part["thought_signature"] = sig
                    first = False
                else:
                    part.pop("thoughtSignature", None)
                    part.pop("thought_signature", None)
            elif not keep:
                part.pop("thoughtSignature", None)
                part.pop("thought_signature", None)
        content["parts"] = parts


def assign_call_ids(contents: list[dict[str, Any]]) -> None:
    """Give every function call an id and each response the id of its call (first unanswered call
    of the same name), as Claude pairs them by id."""
    pending: dict[str, deque[str]] = defaultdict(deque)
    counter = 0
    for part in _parts(contents):
        call = part.get("functionCall")
        if isinstance(call, dict):
            if not call.get("id"):
                counter += 1
                call["id"] = f"tool-call-{counter}"
            pending[str(call.get("name") or "")].append(call["id"])
            continue
        response = part.get("functionResponse")
        if isinstance(response, dict):
            queue = pending[str(response.get("name") or "")]
            if response.get("id") and response["id"] in queue:
                queue.remove(response["id"])
            elif not response.get("id"):
                counter += 1
                response["id"] = queue.popleft() if queue else f"tool-call-{counter}"


def _rename_tools(request: dict[str, Any], names: dict[str, str]) -> None:
    for part in _parts(request.get("contents") or []):
        for key in ("functionCall", "functionResponse"):
            if isinstance(part.get(key), dict) and part[key].get("name") in names:
                part[key]["name"] = names[part[key]["name"]]
    config = (request.get("toolConfig") or {}).get("functionCallingConfig") or {}
    if isinstance(config.get("allowedFunctionNames"), list):
        config["allowedFunctionNames"] = [names.get(n, n) for n in config["allowedFunctionNames"]]


def _claude_tools(request: dict[str, Any]) -> dict[str, str]:
    """Rewrite the declarations for Claude; returns wire name → original name."""
    declarations = [d for group in request.get("tools") or [] for d in group.get("functionDeclarations") or []]
    known = [str(d.get("name") or "") for d in declarations]
    for part in _parts(request.get("contents") or []):
        for key in ("functionCall", "functionResponse"):
            if isinstance(part.get(key), dict):
                known.append(str(part[key].get("name") or ""))
    names = claude_tool_names([n for n in known if n])
    for decl in declarations:
        schema = decl.pop("parametersJsonSchema", None)
        schema = decl.get("parameters", schema)
        decl["parameters"] = claude_tool_schema(schema)
        decl["name"] = names.get(decl.get("name"), decl.get("name"))
    if declarations:
        request["tools"] = [{"functionDeclarations": declarations}]
        request.setdefault("toolConfig", {"functionCallingConfig": {"mode": "VALIDATED"}})
    _rename_tools(request, names)
    return {wire: original for original, wire in names.items() if wire != original}


# ── Envelope ────────────────────────────────────────────────────────────────


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(p.get("text") or "") for p in content if isinstance(p, dict))
    return ""


def session_id(messages: list[dict[str, Any]], *, model: str, project: str) -> str:
    """Stable per conversation: system text and the first user message seed it."""
    system = "\n".join(_text_of(m.get("content")) for m in messages if m.get("role") == "system")
    first_user = next((_text_of(m.get("content")) for m in messages if m.get("role") == "user"), "")
    seed = hashlib.sha256(f"{system}|{first_user}".encode("utf-8")).hexdigest()[:16]
    return f"-{_PROCESS_ID}:{(model or '').lower()}:{project or 'default'}:seed-{seed}"


def _system_instruction(request: dict[str, Any], extra: str = "") -> None:
    instruction = request.get("systemInstruction") or {}
    parts = [p for p in instruction.get("parts") or [] if isinstance(p, dict)]
    texts = [p for p in parts if isinstance(p.get("text"), str)]
    if texts:
        first = texts[0]
        first["text"] = SYSTEM_PREAMBLE + ("\n\n" + first["text"] if first["text"] else "")
    else:
        parts.insert(0, {"text": SYSTEM_PREAMBLE})
    if extra:
        parts.append({"text": extra})
    request["systemInstruction"] = {"role": "user", "parts": parts}


def _claude_max_output(max_tokens: Any, thinking: dict[str, Any] | None) -> int:
    try:
        requested = int(max_tokens)
    except (TypeError, ValueError):
        requested = 0
    budget = int((thinking or {}).get("thinking_budget") or 0) if (thinking or {}).get("include_thoughts") else 0
    if requested <= 0 or requested <= budget:
        return CLAUDE_MAX_OUTPUT
    return min(requested, CLAUDE_MAX_OUTPUT)


def envelope(
    request: dict[str, Any], *, model: str, project: str, messages: list[dict[str, Any]],
    claude_thinking: dict[str, Any] | None = None, max_tokens: Any = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Wrap a Gemini request for ``v1internal``; returns ``(body, wire tool name → original)``.

    *request* is what ``build_gemini_request`` returned; it is not modified.
    """
    request = copy.deepcopy(request)
    contents = request.setdefault("contents", [])
    names: dict[str, str] = {}
    extra_instruction = ""
    if is_claude(model):
        names = _claude_tools(request)
        assign_call_ids(contents)
        apply_signatures(contents, keep=False)
        generation = request.setdefault("generationConfig", {})
        generation.pop("thinkingConfig", None)
        if claude_thinking:
            generation["thinkingConfig"] = dict(claude_thinking)
        generation["maxOutputTokens"] = _claude_max_output(max_tokens, claude_thinking)
        if claude_thinking and claude_thinking.get("include_thoughts") and request.get("tools"):
            extra_instruction = INTERLEAVED_HINT
    else:
        apply_signatures(contents, keep=True)
    _system_instruction(request, extra_instruction)
    request["contents"] = [c for c in contents if c.get("parts")]
    request.pop("model", None)
    request["sessionId"] = session_id(messages, model=model, project=project)
    body = {
        "project": project,
        "model": model,
        "request": request,
        "requestType": "agent",
        "userAgent": "antigravity",
        "requestId": f"agent-{uuid.uuid4()}",
    }
    return body, names


_DURATION = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")


def _duration_seconds(text: Any) -> float | None:
    parts = _DURATION.findall(str(text or ""))
    if not parts:
        return None
    scale = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}
    return sum(float(value) * scale[unit] for value, unit in parts)


def retry_delay(body_text: str) -> float | None:
    """Seconds to wait from a Google error body: ``RetryInfo.retryDelay``, else ``quotaResetDelay``."""
    try:
        error = (json.loads(body_text or "{}") or {}).get("error") or {}
    except (ValueError, AttributeError):
        return None
    details = [d for d in error.get("details") or [] if isinstance(d, dict)] if isinstance(error, dict) else []
    for detail in details:
        if str(detail.get("@type") or "").endswith("google.rpc.RetryInfo"):
            if (seconds := _duration_seconds(detail.get("retryDelay"))) is not None:
                return seconds
    for detail in details:
        metadata = detail.get("metadata") if isinstance(detail.get("metadata"), dict) else {}
        if (seconds := _duration_seconds(metadata.get("quotaResetDelay"))) is not None:
            return seconds
    return None


def unwrap(payload: Any) -> dict[str, Any]:
    """The Gemini response inside a ``v1internal`` reply (``{"response": …}``, possibly in a list)."""
    if isinstance(payload, list):
        payload = payload[0] if payload else {}
    if not isinstance(payload, dict):
        return {}
    inner = payload.get("response")
    return inner if isinstance(inner, dict) else payload


# ── Catalog ─────────────────────────────────────────────────────────────────

_CATALOG_PREFIXES = ("gemini-", "claude-", "gpt-oss-")


def _sorted_ids(payload: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for sort in payload.get("agentModelSorts") or []:
        for group in (sort or {}).get("groups") or []:
            ids.extend(str(i) for i in (group or {}).get("modelIds") or [] if i)
    if ids:
        for group in (payload.get("tieredModelIds") or {}).values():
            ids.extend(str(i) for i in group or [] if i)
    return list(dict.fromkeys(ids))


def parse_catalog(payload: Any) -> list[dict[str, Any]]:
    """``fetchAvailableModels`` → the chat models this account can select, in the client's order."""
    if not isinstance(payload, dict):
        return []
    models = payload.get("models") if isinstance(payload.get("models"), dict) else {}
    selectable = _sorted_ids(payload)
    order = selectable + sorted(m for m in models if m not in selectable)
    catalog: list[dict[str, Any]] = []
    for model_id in order:
        info = models.get(model_id)
        if not isinstance(info, dict):
            continue
        lowered = model_id.lower()
        if not lowered.startswith(_CATALOG_PREFIXES) or "image" in lowered or "imagen" in lowered:
            continue
        if lowered.endswith(("-disabled", "-tiered")) or info.get("disabled") is True:
            continue
        if selectable and model_id not in selectable:
            continue
        catalog.append({
            "id": model_id,
            "name": str(info.get("displayName") or model_id),
            "context": int(info.get("maxTokens") or 200000),
            "output": int(info.get("maxOutputTokens") or 64000),
            "images": info.get("supportsImages") is not False,
        })
    return catalog
