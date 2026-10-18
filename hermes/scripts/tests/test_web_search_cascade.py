"""Every web-enabled profile searches through the cascade backend, with the
floor (SearXNG, then DuckDuckGo) under it.

The allocation: the Assistant, Searcher and Researcher put the vendors first
(the keyed Exa for the Assistant, the keyless ring for the other two, each ring
walk starting at the vendor the profile pins ``free``); every other profile
runs on the floor alone and uses the ring only as the extract fallback.
``default`` stays neutral for ``--clone``. Design: docs/ops/web-search.md.
"""

from __future__ import annotations

from pathlib import Path

import hermes_yaml as yaml
import pytest


HERMES = Path(__file__).resolve().parents[2]
PROFILES = sorted(p.parent.name for p in HERMES.glob("profiles/*/config.example.yaml"))
RING = ("exa", "parallel", "firecrawl", "keenable")
SEARCH_LAYERS = {"ring", "searxng", "ddgs", *RING, "xai"}
EXTRACT_LAYERS = {"ring", "local", *RING}
PROVIDER_FIRST = {"assistant", "searcher", "researcher"}


def load(profile: str) -> dict:
    return yaml.safe_load((HERMES / "profiles" / profile / "config.example.yaml").read_text()) or {}


def web_enabled(config: dict) -> bool:
    return "web" in (config.get("toolsets") or [])


WEB_PROFILES = [p for p in PROFILES if web_enabled(load(p))]


def settings(config: dict) -> dict:
    return ((config.get("plugins") or {}).get("entries") or {}).get("web/cascade", {}).get("settings") or {}


def test_the_web_profiles_are_the_expected_set():
    assert set(WEB_PROFILES) == PROVIDER_FIRST | {"creator", "marketer", "writer"}


@pytest.mark.parametrize("profile", WEB_PROFILES)
def test_web_profiles_search_and_extract_through_the_cascade(profile):
    config = load(profile)
    web = config.get("web") or {}
    assert (web.get("search_backend"), web.get("extract_backend")) == ("cascade", "cascade")
    assert "cascade" in ((config.get("plugins") or {}).get("enabled") or [])
    layers = settings(config)
    assert set(layers["search"]) <= SEARCH_LAYERS and set(layers["extract"]) <= EXTRACT_LAYERS
    assert layers["search"][-2:] == ["searxng", "ddgs"], "the floor ends every search chain"
    assert "local" in layers["extract"], "a plain fetch ends every extract chain"


@pytest.mark.parametrize("profile", WEB_PROFILES)
def test_vendors_lead_only_for_the_provider_first_profiles(profile):
    layers = settings(load(profile))
    vendor_layers = {"ring", *RING}
    if profile in PROVIDER_FIRST:
        assert layers["search"][0] in vendor_layers
        assert layers["extract"][0] in vendor_layers
    else:
        assert layers["search"] == ["searxng", "ddgs"]
        assert layers["extract"][0] == "local"


@pytest.mark.parametrize("profile", WEB_PROFILES)
def test_a_free_pin_names_a_ring_vendor(profile):
    """The ``free`` pin is what fixes where the ring walk starts (plugin ``ring_entry``)."""
    tiers = (load(profile).get("web") or {}).get("provider_tier") or {}
    free = [vendor for vendor, tier in tiers.items() if tier == "free"]
    assert len(free) <= 1 and set(free) <= set(RING)
    if profile in {"searcher", "researcher"}:
        assert free, "the ring-first profiles pin their entry vendor"


def test_ring_entries_are_spread_across_vendors():
    entries = {}
    for profile in WEB_PROFILES:
        tiers = (load(profile).get("web") or {}).get("provider_tier") or {}
        for vendor, tier in tiers.items():
            if tier == "free":
                entries.setdefault(vendor, []).append(profile)
    assert len(entries) >= 3, f"free-tier entry points collapse onto too few vendors: {entries}"


def test_default_stays_neutral():
    config = yaml.safe_load((HERMES / "config.example.yaml").read_text()) or {}
    web = config.get("web") or {}
    assert web.get("search_backend") in ("", None) and web.get("extract_backend") in ("", None)
    assert "cascade" not in ((config.get("plugins") or {}).get("enabled") or [])


@pytest.mark.parametrize("profile, floor", [("searcher", 300), ("researcher", 100)])
def test_retrieval_profiles_raise_the_per_turn_search_cap(profile, floor):
    """The cap stays a loop guard (never 0); a sweep or hunt must not hit it."""
    caps = (load(profile).get("tool_loop_guardrails") or {}).get("loop_caps") or {}
    assert caps.get("max_web_searches", 0) >= floor
