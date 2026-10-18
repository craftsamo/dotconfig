"""The cascade walks its layers in order and the floor answers when the vendors
cannot. Layers are patched at the module seams; no network."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1] / "__init__.py"
SPEC = importlib.util.spec_from_file_location("hermes_web_cascade", PLUGIN)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

ROWS = [MODULE.row("t", "https://example.org/a", "d", 1)]
# The autouse fixture patches these seams for the cascade tests; the layer tests call the originals.
SEARXNG_SEARCH = MODULE.searxng_search
LOCAL_FETCH = MODULE.local_fetch


class Provider:
    def __init__(self, name, search=None, extract=None, searches=True, extracts=True):
        self._name, self._search, self._extract = name, search, extract
        self._searches, self._extracts = searches, extracts

    name = property(lambda self: self._name)

    def supports_search(self):
        return self._searches

    def supports_extract(self):
        return self._extracts

    def search(self, query, limit=5):
        return self._search(query, limit)

    def extract(self, urls, **kwargs):
        return self._extract(urls)


def provider(settings=None, **patches):
    for key, value in patches.items():
        setattr(MODULE, key, value)
    settings = settings or {}
    return MODULE.CascadeWebSearchProvider(lambda key, default=None: settings.get(key, default))


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    monkeypatch.setattr(MODULE, "ring_entry", lambda: "exa")
    monkeypatch.setattr(MODULE, "ring_search", lambda q, l: MODULE.search_fail("Keyless Exa search failed: 429"))
    monkeypatch.setattr(MODULE, "ring_extract", lambda urls: [MODULE.page_error(u, "rate limit") for u in urls])
    monkeypatch.setattr(MODULE, "searxng_search", lambda base, q, l: MODULE.search_fail(f"Could not reach SearXNG at {base}"))
    monkeypatch.setattr(MODULE, "registered_provider", lambda name: None)
    monkeypatch.setattr(MODULE, "local_fetch", lambda url: MODULE.page_error(url, "local: HTTP 404"))


# --- search -------------------------------------------------------------------
def test_search_returns_the_first_layer_that_answers(monkeypatch):
    monkeypatch.setattr(MODULE, "ring_search", lambda q, l: {"success": True, "data": {"web": ROWS, "served_by": "parallel"}})
    result = provider().search("q")
    assert result["success"] and result["data"]["web"] == ROWS
    assert result["data"]["served_by"] == "ring:parallel"
    assert "cascade_skipped" not in result["data"]


def test_search_falls_through_to_searxng_when_the_ring_is_throttled(monkeypatch):
    seen = {}
    monkeypatch.setattr(MODULE, "searxng_search", lambda base, q, l: seen.setdefault("base", base) and MODULE.search_ok(ROWS))
    result = provider({"searxng_url": "http://127.0.0.1:10104/"}).search("q")
    assert result["data"]["served_by"] == "searxng"
    assert seen["base"] == "http://127.0.0.1:10104/"
    assert result["data"]["cascade_skipped"] == ["ring: Keyless Exa search failed: 429"]


def test_search_reaches_ddgs_when_every_vendor_and_searxng_are_down(monkeypatch):
    monkeypatch.setattr(MODULE, "registered_provider",
                        lambda name: Provider("ddgs", search=lambda q, l: MODULE.search_ok(ROWS)) if name == "ddgs" else None)
    result = provider().search("q")
    assert result["data"]["served_by"] == "ddgs"
    assert [s.split(":")[0] for s in result["data"]["cascade_skipped"]] == ["ring", "searxng"]


def test_search_fails_only_when_every_layer_failed():
    result = provider().search("q")
    assert result["success"] is False
    assert result["error"].startswith("Every cascade layer failed: ring: ")
    assert "searxng:" in result["error"] and "ddgs: no provider registered" in result["error"]


def test_search_prefers_a_later_hit_over_an_earlier_empty_success(monkeypatch):
    monkeypatch.setattr(MODULE, "ring_search", lambda q, l: MODULE.search_ok([]))
    monkeypatch.setattr(MODULE, "searxng_search", lambda base, q, l: MODULE.search_ok(ROWS))
    result = provider().search("q")
    assert result["data"]["served_by"] == "searxng"
    assert result["data"]["cascade_skipped"] == ["ring: no results"]


def test_search_returns_the_first_empty_success_when_nothing_else_answers(monkeypatch):
    monkeypatch.setattr(MODULE, "ring_search", lambda q, l: MODULE.search_ok([]))
    result = provider().search("q")
    assert result["success"] and result["data"]["web"] == []
    assert result["data"]["served_by"] == "ring:exa"


def test_search_layer_order_comes_from_settings_and_a_crash_is_a_skip(monkeypatch):
    calls = []

    def boom(q, l):
        calls.append("ring")
        raise RuntimeError("socket closed")

    monkeypatch.setattr(MODULE, "ring_search", boom)
    monkeypatch.setattr(MODULE, "registered_provider",
                        lambda name: Provider(name, search=lambda q, l: calls.append(name) or MODULE.search_ok(ROWS)))
    result = provider({"search": ["ddgs", "ring"]}).search("q")
    assert calls == ["ddgs"] and result["data"]["served_by"] == "ddgs"
    result = provider({"search": "ring, exa"}).search("q")
    assert calls == ["ddgs", "ring", "exa"]
    assert result["data"]["cascade_skipped"] == ["ring: socket closed"]


def test_search_skips_a_registered_provider_that_cannot_search(monkeypatch):
    monkeypatch.setattr(MODULE, "registered_provider", lambda name: Provider("firecrawl", searches=False))
    result = provider({"search": ["firecrawl"]}).search("q")
    assert result["error"] == "Every cascade layer failed: firecrawl: provider does not search"


def test_long_skip_reasons_are_truncated(monkeypatch):
    monkeypatch.setattr(MODULE, "ring_search", lambda q, l: MODULE.search_fail("x" * 500))
    monkeypatch.setattr(MODULE, "searxng_search", lambda base, q, l: MODULE.search_ok(ROWS))
    reason = provider().search("q")["data"]["cascade_skipped"][0]
    assert len(reason) <= len("ring: ") + MODULE.REASON_CHARS


# --- extract ------------------------------------------------------------------
def run(coro):
    return asyncio.run(coro)


def test_extract_hands_only_the_failed_urls_to_the_next_layer(monkeypatch):
    seen = []

    def ring(urls):
        seen.append(("ring", list(urls)))
        return [MODULE.document(urls[0], "A", "body a"), MODULE.page_error(urls[1], "rate limit")]

    def local(url):
        seen.append(("local", url))
        return MODULE.document(url, "B", "body b")

    monkeypatch.setattr(MODULE, "ring_extract", ring)
    monkeypatch.setattr(MODULE, "local_fetch", local)
    out = run(provider().extract(["https://a", "https://b"]))
    assert [e["content"] for e in out] == ["body a", "body b"]
    assert [e["metadata"]["served_by"] for e in out] == ["ring", "local"]
    assert seen == [("ring", ["https://a", "https://b"]), ("local", "https://b")]


def test_extract_keeps_the_last_error_when_every_layer_fails():
    out = run(provider().extract(["https://a"]))
    assert out == [MODULE.page_error("https://a", "local: HTTP 404")]


def test_extract_treats_empty_content_as_a_failure_for_that_layer(monkeypatch):
    monkeypatch.setattr(MODULE, "ring_extract", lambda urls: [MODULE.document(u, "", "   ") for u in urls])
    monkeypatch.setattr(MODULE, "local_fetch", lambda url: MODULE.document(url, "t", "text"))
    out = run(provider().extract(["https://a"]))
    assert out[0]["content"] == "text" and out[0]["metadata"]["served_by"] == "local"


def test_extract_layer_order_and_registered_async_providers(monkeypatch):
    class Async(Provider):
        async def extract(self, urls, **kwargs):
            return [MODULE.document(u, "P", "from parallel") for u in urls]

    monkeypatch.setattr(MODULE, "registered_provider", lambda name: Async("parallel") if name == "parallel" else None)
    out = run(provider({"extract": ["local", "parallel"]}).extract(["https://a"]))
    assert out[0]["metadata"]["served_by"] == "parallel"


def test_extract_pairs_entries_by_source_url_when_counts_differ(monkeypatch):
    monkeypatch.setattr(MODULE, "ring_extract", lambda urls: [
        {"url": "https://b/final", "title": "B", "content": "b", "raw_content": "b", "metadata": {"sourceURL": "https://b"}}])
    monkeypatch.setattr(MODULE, "local_fetch", lambda url: MODULE.document(url, "A", "a"))
    out = run(provider().extract(["https://a", "https://b"]))
    assert [e["content"] for e in out] == ["a", "b"]


def test_extract_without_a_crashing_layer_taking_the_batch_down(monkeypatch):
    def boom(urls):
        raise RuntimeError("ring exploded")

    monkeypatch.setattr(MODULE, "ring_extract", boom)
    monkeypatch.setattr(MODULE, "local_fetch", lambda url: MODULE.document(url, "A", "a"))
    out = run(provider().extract(["https://a"]))
    assert out[0]["content"] == "a"


# --- local fetch and searxng ----------------------------------------------------
class Response:
    def __init__(self, status=200, body=b"", content_type="text/html; charset=utf-8", charset="utf-8"):
        self.status_code, self._body, self.charset_encoding = status, body, charset
        self.headers = {"content-type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_bytes(self):
        yield self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        import json
        return json.loads(self._body)


def test_local_fetch_turns_html_into_text(monkeypatch):
    html = b"<html><head><title>Hello</title><style>p{}</style></head><body><script>x()</script><h1>Hi</h1><p>Body   text</p></body></html>"
    monkeypatch.setattr(MODULE, "http_stream", lambda url, **kw: Response(body=html))
    out = LOCAL_FETCH("https://example.org/")
    assert out["title"] == "Hello" and out["content"].replace("\n", " ") == "Hi Body text"
    assert "x()" not in out["content"] and out["metadata"]["sourceURL"] == "https://example.org/"


def test_local_fetch_refuses_binary_and_non_http(monkeypatch):
    monkeypatch.setattr(MODULE, "http_stream", lambda url, **kw: Response(body=b"%PDF", content_type="application/pdf"))
    assert LOCAL_FETCH("https://x/a.pdf")["error"] == "local: unsupported content type application/pdf"
    assert LOCAL_FETCH("ftp://x")["error"] == "local: only http(s) URLs"
    monkeypatch.setattr(MODULE, "http_stream", lambda url, **kw: Response(status=503))
    assert LOCAL_FETCH("https://x")["error"] == "local: HTTP 503"


def test_searxng_search_sorts_by_score_and_caps_to_limit(monkeypatch):
    body = b'{"results": [{"title": "lo", "url": "u1", "content": "c", "score": 1}, {"title": "hi", "url": "u2", "content": "c", "score": 9}, {"title": "mid", "url": "u3", "content": "c", "score": 5}]}'
    seen = {}

    def get(url, **kw):
        seen["url"], seen["params"] = url, kw["params"]
        return Response(body=body, content_type="application/json")

    monkeypatch.setattr(MODULE, "http_get", get)
    out = SEARXNG_SEARCH("http://127.0.0.1:10104/", "q", 2)
    assert [r["title"] for r in out["data"]["web"]] == ["hi", "mid"]
    assert out["data"]["web"][0]["position"] == 1
    assert seen["url"] == "http://127.0.0.1:10104/search" and seen["params"]["format"] == "json"


def test_searxng_unreachable_is_a_failure_not_an_exception(monkeypatch):
    def get(url, **kw):
        raise ConnectionError("refused")

    monkeypatch.setattr(MODULE, "http_get", get)
    assert SEARXNG_SEARCH("http://127.0.0.1:10104", "q", 5)["error"].startswith("Could not reach SearXNG at http://127.0.0.1:10104: ")


# --- registration ---------------------------------------------------------------
def test_register_binds_the_plugin_settings_reader():
    class Ctx:
        def __init__(self):
            self.providers = []

        def register_web_search_provider(self, p):
            self.providers.append(p)

        def get_config(self, key, default=None):
            return {"search": ["searxng"]}.get(key, default)

    ctx = Ctx()
    MODULE.register(ctx)
    (p,) = ctx.providers
    assert p.name == "cascade" and p.is_available() and p.supports_search() and p.supports_extract()
    assert p._layers("search", MODULE.DEFAULT_SEARCH_LAYERS) == ["searxng"]
    assert p._layers("extract", MODULE.DEFAULT_EXTRACT_LAYERS) == list(MODULE.DEFAULT_EXTRACT_LAYERS)
