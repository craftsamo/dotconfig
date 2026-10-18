# Web search backends

How Hermes picks a web search/extract backend, why every web-enabled profile
searches through the `cascade` backend with a local floor under it, and how to
verify a change. Read it before touching `web.*` keys, the cascade layer order,
the SearXNG service or a search provider's key.

Part of the Hermes mechanics docs — entry: [`README.md`](../../README.md).

## The shape

```
profile ── web.search_backend: cascade ──► plugins/web/cascade
                                              │  layers, in the profile's order
                                              ├─ exa / parallel / …  a registered vendor on its own path
                                              ├─ ring                the keyless ring (exa → parallel → firecrawl → keenable)
                                              ├─ searxng             local SearXNG (127.0.0.1:10104)
                                              ├─ ddgs                DuckDuckGo scraper (no key)
                                              └─ local               plain fetch + HTML-to-text (extract only)
```

**Why a cascade.** Hermes' own failover is the keyless ring plus one stateless
rescue of a failed keyed call (`web.keyless_rescue`, default on), and both end at
the same four vendors. When those free tiers are throttled or a pinned paid key
is out of credit, every call pays the vendor's error before the rescue answers,
and a fleet-wide throttle stops `web_search` outright. The cascade walks an
ordered list of layers until one answers and ends in two that no vendor's
billing or rate limit reaches: a SearXNG instance this host runs
([services.md](services.md) "Engines") and the DuckDuckGo scraper. A keyed
backend still never falls through to another keyed backend — the per-profile
budget isolation stands — because a cascade layer is either the profile's own
vendor, the free ring, or the floor.

**Allocation.** The Assistant (keyed Exa first), the Searcher and the Researcher
(ring first) put the vendors ahead of the floor; every other web-enabled profile
runs on the floor alone and keeps the ring only as its extract fallback, so the
low-volume profiles never spend the free tiers the retrieval profiles depend on.
`test_web_search_cascade.py` pins this table; change it there and in the configs
together. `default` keeps `search_backend` / `extract_backend` empty (neutral for
`--clone`) and pins `provider_tier.exa: free` — otherwise auto-detect resolves to
keyed Exa and spends the Assistant's grant.

| profile | search | extract |
|---|---|---|
| assistant | exa, ring, searxng, ddgs | exa, ring, local |
| searcher, researcher | ring, searxng, ddgs | ring, local |
| creator, marketer, writer | searxng, ddgs | local, ring |

The layers live in each profile's `plugins.entries.web/cascade.settings`
(`search`, `extract`, optional `searxng_url`); the plugin's docstring is the
reference for the layer names.

## Ring entry and tiers

**`web.provider_tier.<vendor>: free` is the ring's entry point.** The keyless
walk starts at the vendor the profile pins `free` and advances on rate limits and
anonymous-endpoint 401/403 (not on 5xx or timeouts); the cascade's `ring_entry`
reads the same pin, so the pins also spread the fleet's first hop across vendors
(searcher `exa`, researcher and writer `firecrawl`, creator `parallel`, marketer
`keenable`; the test keeps at least three distinct). `paid` forces the keyed
path and drops that vendor from the ring; unset = auto (key present ⇒ keyed). A
profile without a pin starts at the ring's round-robin cursor.

A vendor named as its own layer (`exa` for the Assistant) runs on its own path:
keyed when the profile's secret layer holds the key, else that vendor's keyless
endpoint. Availability is key presence, never quota — a 402 is what the cascade
skips, not what auto-detect sees.

**Never configure a backend name that no longer exists.** With a `web:`
selection present the tool refuses it ("no registered web search provider has
that name"); `tavily` is such a name (upstream replaced it with `keenable`), so a
leftover `TAVILY_API_KEY` is unused.

## Floor

`launchd/searxng-launchctl.sh install` starts SearXNG on `127.0.0.1:10104`
(Docker Desktop must be running; `status` shows the container and health). The
JSON API is enabled and the limiter is off in `engines/searxng/settings.yml.tmpl`;
the plugin's `searxng_url` setting defaults to that port. SearXNG aggregates
Google, Bing, Brave, DuckDuckGo and more, so one engine refusing leaves results
from the others. `ddgs` ships with the runtime and needs nothing; DuckDuckGo may
CAPTCHA it for a while, which is why it is last. `local` is the extract floor:
HTML becomes text through the standard library, PDFs and images are an error for
that layer.

## Reading the results

A successful search carries `data.served_by` — `ring:<vendor>`, `searxng`,
`ddgs`, or a vendor name — and, when something was skipped, `data.cascade_skipped`
with one short reason per layer. Extract results keep only url/title/content/error
for the model; the extract layer is in the gateway log (`cascade extract: <layer>
served n of m urls`). Both fields are in the profiles' session transcripts
(`state.db`, `messages` rows with `tool_name = 'web_search'`), which is where to
look when a vendor seems to be failing.

## Verify

```sh
grep -n -A3 'search_backend: cascade' hermes/profiles/*/config.yaml
grep -n -A12 'web/cascade:' hermes/profiles/*/config.yaml
launchd/searxng-launchctl.sh status
```

then, with `HERMES_HOME=~/.hermes/profiles/<p>`, `tools.web_tools._get_search_backend()`
must return `cascade`, and a `web_search_tool` call shows `data.served_by`. A
changed layer order applies on the next CLI turn (the configs are symlinks into
this repo); a new plugin or a rotated key needs a gateway restart.
