"""cascade: a web search/extract backend with a floor under it.

Hermes' own failover is the keyless ring (exa → parallel → firecrawl → keenable)
plus one stateless rescue of a failed keyed call. Both end at the same four
vendors, so when their free tiers are all throttled, `web_search` stops. This
provider registers as backend ``cascade`` and walks an ordered list of layers
until one answers, so a profile can put a local SearXNG instance and the
DuckDuckGo scraper under the vendors, or run on those two alone.

Layers are names in ``plugins.entries.web/cascade.settings``::

    search:  [ring, searxng, ddgs]     # default
    extract: [ring, local]             # default
    searxng_url: http://127.0.0.1:10104

``ring``   the keyless ring with its own failover; the walk starts at the vendor
           the profile pins ``web.provider_tier.<vendor>: free`` (the existing
           entry-point contract), else at the ring's round-robin cursor.
``searxng`` the local SearXNG JSON API at ``searxng_url`` (search only).
``ddgs``, ``exa``, ``xai``, ... any provider registered under that name, called
           on its own path (keyed when the profile holds the key).
``local``  a plain HTTP fetch with HTML-to-text (extract only; the last resort).

A search layer is skipped when it raises, fails, or returns no results; the
first empty success is returned only when no later layer finds anything. An
extract layer is tried per URL: the URLs it could not read go to the next
layer. A search result's ``data.served_by`` names the layer that answered and
``data.cascade_skipped`` the layers that did not, so the session transcripts
show where the floor is carrying the load; the extract wrapper keeps only
url/title/content/error, so extract layers are reported in the log.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import re
from html.parser import HTMLParser
from typing import Any, Callable, Dict, List, Optional, Sequence

from agent.web_search_provider import WebSearchProvider

logger = logging.getLogger(__name__)

NAME = "cascade"
DEFAULT_SEARCH_LAYERS = ("ring", "searxng", "ddgs")
DEFAULT_EXTRACT_LAYERS = ("ring", "local")
DEFAULT_SEARXNG_URL = "http://127.0.0.1:10104"
SEARXNG_TIMEOUT = 15
LOCAL_TIMEOUT = 20
LOCAL_MAX_BYTES = 5 * 1024 * 1024
LOCAL_MAX_CHARS = 200_000
REASON_CHARS = 160
_LOCAL_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
_TEXT_TYPES = ("text/plain", "text/markdown", "application/json", "application/xml", "text/xml", "text/csv")
_DROP_TAGS = frozenset({"script", "style", "noscript", "svg", "iframe", "template", "head"})
_BLOCK_TAGS = frozenset({"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "td", "th",
                         "table", "section", "article", "header", "footer", "nav", "aside", "main", "blockquote",
                         "pre", "dt", "dd", "figcaption", "hr"})


# --- runtime seams (module-level so tests patch them) ---------------------------
def ring_vendors() -> Sequence[str]:
    from plugins.web import keyless_mcp
    return getattr(keyless_mcp, "_KEYLESS_RING", ("exa", "parallel", "firecrawl", "keenable"))


def ring_entry() -> str:
    """The vendor the keyless walk starts at: the profile's ``free`` pin, else the first."""
    from plugins.web.keyless_mcp import provider_tier
    vendors = list(ring_vendors())
    for vendor in vendors:
        if provider_tier(vendor) == "free":
            return vendor
    return vendors[0]


def ring_search(query: str, limit: int) -> Dict[str, Any]:
    from plugins.web.keyless_mcp import search_with_failover
    return search_with_failover(ring_entry(), query, limit)


def ring_extract(urls: List[str]) -> List[Dict[str, Any]]:
    from plugins.web.keyless_mcp import extract_with_failover
    return extract_with_failover(ring_entry(), list(urls))


def registered_provider(name: str) -> Optional[Any]:
    from agent.web_search_registry import get_provider
    return get_provider(name)


def http_get(url: str, **kwargs: Any) -> Any:
    import httpx
    return httpx.get(url, **kwargs)


def http_stream(url: str, **kwargs: Any) -> Any:
    import httpx
    return httpx.stream("GET", url, **kwargs)


# --- result shapes (the legacy wire contract; key order reaches the model) ----
def search_ok(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"success": True, "data": {"web": rows}}


def search_fail(error: str) -> Dict[str, Any]:
    return {"success": False, "error": error}


def row(title: str, url: str, description: str, position: int) -> Dict[str, Any]:
    return {"title": title, "url": url, "description": description, "position": position}


def document(url: str, title: str, content: str) -> Dict[str, Any]:
    return {"url": url, "title": title, "content": content, "raw_content": content,
            "metadata": {"sourceURL": url, "title": title}}


def page_error(url: str, error: str) -> Dict[str, Any]:
    return {"url": url, "title": "", "content": "", "error": error}


def _reason(layer: str, text: Any) -> str:
    text = " ".join(str(text or "").split())
    if len(text) > REASON_CHARS:
        text = text[: REASON_CHARS - 1] + "…"
    return f"{layer}: {text or 'no results'}"


# --- layers ---------------------------------------------------------------------
def searxng_search(base_url: str, query: str, limit: int) -> Dict[str, Any]:
    base = (base_url or "").rstrip("/")
    if not base:
        return search_fail("searxng_url is not set")
    try:
        resp = http_get(f"{base}/search", params={"q": query, "format": "json", "pageno": 1},
                        headers={"Accept": "application/json"}, timeout=SEARXNG_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001 — every failure is a skip reason
        return search_fail(f"Could not reach SearXNG at {base}: {exc}")
    raw = data.get("results") or []
    raw = sorted(raw, key=lambda r: float(r.get("score", 0) or 0), reverse=True)[: max(1, int(limit))]
    return search_ok([row(str(r.get("title", "")), str(r.get("url", "")), str(r.get("content", "")), i + 1)
                      for i, r in enumerate(raw)])


class _TextExtractor(HTMLParser):
    """Stdlib HTML → text: drops script-like subtrees, keeps the title, breaks
    lines at block elements. No optional dependency, so the floor always loads."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: List[str] = []
        self.parts: List[str] = []
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in _DROP_TAGS:
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _DROP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif tag == "title":
            self._in_title = False
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        elif not self._skip:
            self.parts.append(data)


def _html_to_text(body: bytes, charset: Optional[str]) -> tuple[str, str]:
    try:
        text = body.decode(charset or "utf-8", errors="replace")
    except LookupError:
        text = body.decode("utf-8", errors="replace")
    parser = _TextExtractor()
    parser.feed(text)
    parser.close()
    title = " ".join("".join(parser.title_parts).split())
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    return title, "\n".join(line for line in lines if line)


def local_fetch(url: str) -> Dict[str, Any]:
    """Plain HTTP fetch for the last extract layer: HTML becomes text, text-like
    types pass through, anything else (PDF, images) is an error for this layer."""
    if not re.match(r"^https?://", url or "", re.IGNORECASE):
        return page_error(url, "local: only http(s) URLs")
    try:
        with http_stream(url, follow_redirects=True, timeout=LOCAL_TIMEOUT,
                         headers={"User-Agent": _LOCAL_UA, "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5"}) as resp:
            if resp.status_code >= 400:
                return page_error(url, f"local: HTTP {resp.status_code}")
            content_type = (resp.headers.get("content-type") or "").lower()
            chunks, size = [], 0
            for chunk in resp.iter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size > LOCAL_MAX_BYTES:
                    break
            body = b"".join(chunks)[:LOCAL_MAX_BYTES]
            charset = resp.charset_encoding
    except Exception as exc:  # noqa: BLE001 — every failure is a per-URL error
        return page_error(url, f"local: {exc}")
    if "html" in content_type or not content_type:
        title, text = _html_to_text(body, charset)
    elif any(content_type.startswith(t) for t in _TEXT_TYPES):
        title, text = "", body.decode(charset or "utf-8", errors="replace")
    else:
        return page_error(url, f"local: unsupported content type {content_type.split(';')[0]}")
    text = text[:LOCAL_MAX_CHARS]
    if not text.strip():
        return page_error(url, "local: page had no readable text")
    return document(url, title, text)


# --- provider -------------------------------------------------------------------
class CascadeWebSearchProvider(WebSearchProvider):
    """Walks the configured layers; see the module docstring for the names."""

    def __init__(self, settings: Callable[[str, Any], Any]) -> None:
        self._settings = settings

    name = property(lambda self: NAME)
    display_name = property(lambda self: "Cascade (ring → SearXNG → DuckDuckGo)")

    def is_available(self) -> bool:
        return True

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return True

    def get_setup_schema(self) -> Dict[str, Any]:
        return {"name": "Cascade", "badge": "free · local floor", "env_vars": [],
                "tag": "Ordered layers: keyless ring, local SearXNG, DuckDuckGo; never exhausted by one vendor."}

    # settings
    def _layers(self, key: str, default: Sequence[str]) -> List[str]:
        value = self._settings(key, None)
        if isinstance(value, str):
            value = [part for part in re.split(r"[,\s]+", value) if part]
        if not isinstance(value, (list, tuple)) or not value:
            return list(default)
        return [str(v).strip().lower() for v in value if str(v).strip()]

    def _searxng_url(self) -> str:
        return str(self._settings("searxng_url", DEFAULT_SEARXNG_URL) or DEFAULT_SEARXNG_URL)

    # search
    def _search_layer(self, layer: str, query: str, limit: int) -> tuple[Dict[str, Any], str]:
        """``(result, served_by)``; a layer that cannot search returns a failure."""
        if layer == "ring":
            result = ring_search(query, limit)
            vendor = (result.get("data") or {}).get("served_by") if result.get("success") else None
            return result, f"ring:{vendor or ring_entry()}"
        if layer == "searxng":
            return searxng_search(self._searxng_url(), query, limit), "searxng"
        if layer == "local":
            return search_fail("local is an extract-only layer"), layer
        provider = registered_provider(layer)
        if provider is None:
            return search_fail("no provider registered under that name"), layer
        if not provider.supports_search():
            return search_fail("provider does not search"), layer
        return provider.search(query, limit), layer

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        skipped: List[str] = []
        first_empty: Optional[tuple[Dict[str, Any], str]] = None
        for layer in self._layers("search", DEFAULT_SEARCH_LAYERS):
            try:
                result, served_by = self._search_layer(layer, query, limit)
            except Exception as exc:  # noqa: BLE001 — a layer's crash is a skip
                logger.warning("cascade search layer %s raised: %s", layer, exc)
                skipped.append(_reason(layer, exc))
                continue
            if not result.get("success"):
                skipped.append(_reason(layer, result.get("error")))
                continue
            rows = (result.get("data") or {}).get("web") or []
            if not rows:
                if first_empty is None:
                    first_empty = (result, served_by)
                skipped.append(_reason(layer, "no results"))
                continue
            return self._annotate(result, served_by, skipped)
        if first_empty is not None:
            result, served_by = first_empty
            return self._annotate(result, served_by, skipped)
        return search_fail("Every cascade layer failed: " + "; ".join(skipped))

    @staticmethod
    def _annotate(result: Dict[str, Any], served_by: str, skipped: List[str]) -> Dict[str, Any]:
        data = result.setdefault("data", {})
        data["served_by"] = served_by
        if skipped:
            data["cascade_skipped"] = skipped
        return result

    # extract
    async def _extract_layer(self, layer: str, urls: List[str]) -> List[Dict[str, Any]]:
        if layer == "ring":
            return await asyncio.to_thread(ring_extract, urls)
        if layer == "local":
            return await asyncio.to_thread(lambda: [local_fetch(u) for u in urls])
        if layer == "searxng":
            return [page_error(u, "searxng: search-only layer") for u in urls]
        provider = registered_provider(layer)
        if provider is None:
            return [page_error(u, f"{layer}: no provider registered under that name") for u in urls]
        if not provider.supports_extract():
            return [page_error(u, f"{layer}: provider does not extract") for u in urls]
        if inspect.iscoroutinefunction(provider.extract):
            return await provider.extract(urls)
        return await asyncio.to_thread(provider.extract, urls)

    async def extract(self, urls: List[str], **kwargs: Any) -> List[Dict[str, Any]]:
        urls = list(urls)
        done: Dict[str, Dict[str, Any]] = {}
        last: Dict[str, Dict[str, Any]] = {}
        pending = list(urls)
        for layer in self._layers("extract", DEFAULT_EXTRACT_LAYERS):
            if not pending:
                break
            try:
                results = await self._extract_layer(layer, pending)
            except Exception as exc:  # noqa: BLE001 — a layer's crash fails its URLs only
                logger.warning("cascade extract layer %s raised: %s", layer, exc)
                results = [page_error(u, f"{layer}: {exc}") for u in pending]
            served = 0
            for url, entry in _pair(pending, results):
                if entry.get("error") or not (entry.get("content") or "").strip():
                    last[url] = entry if entry.get("error") else page_error(url, f"{layer}: empty content")
                    continue
                entry.setdefault("metadata", {})["served_by"] = layer
                done[url] = entry
                served += 1
            # The tool wrapper drops ``metadata`` from what the model sees, so the log is
            # where an extract layer's share is read.
            logger.info("cascade extract: %s served %d of %d urls", layer, served, len(pending))
            pending = [u for u in pending if u not in done]
        return [done.get(u) or last.get(u) or page_error(u, "no cascade layer could extract this URL") for u in urls]


def _pair(urls: List[str], results: Any) -> List[tuple[str, Dict[str, Any]]]:
    """Match a layer's entries back to the URLs it was given: positionally when the
    counts agree (every vendor returns one entry per URL in order), else by the
    entry's ``metadata.sourceURL`` / ``url``."""
    entries = [r for r in (results or []) if isinstance(r, dict)]
    if len(entries) == len(urls):
        return list(zip(urls, entries))
    by_url = {}
    for entry in entries:
        key = (entry.get("metadata") or {}).get("sourceURL") or entry.get("url")
        by_url.setdefault(key, entry)
    return [(u, by_url.get(u) or page_error(u, "layer returned no entry for this URL")) for u in urls]


def register(ctx: Any) -> None:
    ctx.register_web_search_provider(CascadeWebSearchProvider(ctx.get_config))
