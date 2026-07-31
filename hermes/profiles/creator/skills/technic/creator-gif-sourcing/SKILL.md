---
name: creator-gif-sourcing
description: >-
  Creator's leaf technic for sourcing existing Tenor reaction and communication
  GIFs with secret-safe retrieval, comparison, provenance, and safety checks.
version: 1.0.0
author: CraftSamo
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [creator, technic, gif, sourcing, tenor, provenance, safety]
    category: technic
---

<Goal>
Find and retrieve an existing Tenor GIF that fits the brief, preserving source
identity and an auditable selection record. The canonical dispatch identity is
`creator-gif-sourcing`.
</Goal>

<Scope>
Load the official `gif-search` engine with `skill_view(name="gif-search")`.
Use it for existing reaction or communication GIFs from Tenor. GIF or video
generation and GIF authoring route to `creator-generated-video` or another
canonical leaf; this skill never creates a substitute asset.
</Scope>

<Contract>
- `creator-pipeline` owns MediaBrief, Budget, Q<n>, Review, V1-V6, and delivery.
- Retrieval has zero generation cost, but does not imply a usage license.
- Never install dependencies or use an exposed API-key example from the
  official skill. Missing preflight blocks production.
- Do not infer commercial rights. State that commercial usage is unconfirmed,
  and never alter third-party content to present it as official material.
</Contract>

<Preflight>
Check Python 3.10+ and a Keychain-injected `TENOR_API_KEY`. The bundled helper
reads the key from process environment; do not put it in `.env`, print or log
its value, or expand it into argv. Do not copy an official shell example that
exposes the key. If the key is missing, block before production.
</Preflight>

<Procedure>
1. Lock locale, contentfilter (default `high`), query, result limit, format,
   destination, and any destination dimensions before requesting results.
2. Search with
   `python3 "${HERMES_SKILL_DIR}/scripts/tenor-gif.py" search`; it writes a
   sanitized metadata file without the key. Request enough results to compare
   3-5 previews. Never blindly choose the first ranked item.
3. Save a provenance record containing source URL, Tenor item ID, query, locale,
   content filter, format, dimensions, duration, file size, and selection reason.
4. Download the selected result with `python3` and the helper's `download`
   command, then verify the local file. Retain sanitized metadata, never the
   raw request URL or response.
5. Keep the original content unmodified unless the brief explicitly routes a
   permitted edit elsewhere. Preserve attribution and flag rights uncertainty.
</Procedure>

<Verification>
Check the downloaded file with file tools and `ffprobe`, inspect multiple
frames, loop behavior, size, dimensions, content, and safety. Confirm the
selected preview matches the downloaded item and the provenance record. Attach
only the final requested media; record comparison, provenance, probe output,
and safety notes in the pipeline report unless a sidecar is explicitly required.
</Verification>

<Files>
- `scripts/tenor-gif.py` - secret-safe Tenor search and atomic download.
</Files>
