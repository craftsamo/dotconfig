# Web search backends

How Hermes picks a web search/extract backend, why paid backends are pinned
per profile, and how to verify a change. Read it before touching `web.*` keys
or rotating a search provider's key.

Part of the Hermes mechanics docs — entry: [`README.md`](../../README.md).

## Web search backends

Paid backends are pinned per profile; everyone else rides the keyless ring.

**Auto-detect.** With empty `web.search_backend` / `web.extract_backend`, Hermes
takes the first backend whose **key exists** (order: the agent checkout's web
tools), then walks the keyless tier. Availability is key presence, never quota.
Never configure a backend name that no longer exists: it does not error, it
silently resolves to `firecrawl` (and bills researcher's credits). `tavily` is
such a name — upstream replaced it with `keenable` — so never configure it; a
leftover `TAVILY_API_KEY` is unused.

**Keyless ring and rescue.** Runtime failover exists only inside the free ring
(`plugins/web/keyless_mcp.py` in the agent checkout owns its members and
order): a rate-limited keyless request advances to the next vendor, and a failed
**keyed** call gets ONE stateless keyless rescue (`web.keyless_rescue`, default
on; rescued results are never cached, so the next call retries the profile's own
backend). A keyed backend never falls through to another keyed backend —
per-profile pinning is what stops one provider's exhaustion from taking the
fleet down.

**`web.provider_tier.<vendor>` picks the lane per profile.** `free` forces the
keyless endpoint even when the key is present and pins that vendor as the ring
entry point; `paid` forces the keyed path and drops that vendor from the
profile's ring; unset = auto (key present ⇒ keyed). Editing `search_backend`
alone is not enough: with a key in the environment, auto silently bills the paid
path.

**Allocation rule.** The paid keys stay with the high-volume profiles (auto,
key present); every other profile is pinned `free` on distributed entry points,
so the free vendors' load spreads across the fleet. `default` keeps
`search_backend` / `extract_backend` empty (neutral for `--clone`) and pins
`provider_tier.exa: free` — otherwise auto-detect resolves to keyed Exa and
spends the Assistant's grant. A `free` pin resolves without a key, so no key is
needed for those profiles. The live assignment is each profile's `web:` block.

**Exhaustion signals** are per provider and each self-heals: a quota error from
a paid backend (Exa `402`, Firecrawl 4xx) is exhaustion; `401` is a dead or
rotated key, not exhaustion. Parallel has no balance endpoint, so its quota
model is unverified: if searcher starts failing while its key is valid, swap
searcher and researcher between `parallel` and `firecrawl` in their `web:`
blocks.

**Verify** a change by listing the pins and by resolving the backend per profile:

```sh
grep -n -A3 provider_tier hermes/config.yaml hermes/profiles/*/config.yaml
```

then `HERMES_HOME=~/.hermes/profiles/<p>` with
`tools.web_tools._get_search_backend()`, and run `web_search_tool`;
`data.served_by` appears only when the ring failed over, so its absence means
the pinned vendor answered. **Switch** by editing the keys in this repo (the
`~/.hermes` configs are symlinks, so a new CLI turn picks them up); rotating an
API key additionally needs a gateway restart.
