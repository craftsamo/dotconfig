---
name: creator-brand-asset-sourcing
description: Creator's leaf technic for sourcing official third-party logos/marks with provenance; never redraw.
version: 1.0.0
metadata:
  hermes:
    tags: [creator, technic, brand, logo, svg, sourcing, provenance]
    category: technic
---

# Creator Brand Asset Sourcing

Use when a deliverable needs a real company/product logo or brand mark —
video, deck, comparison table, README badge, landing page, icon row
(logo, brand mark, wordmark, logomark, ロゴ, ブランドロゴ, 企業ロゴ).
Establish whether the vendor officially distributes the mark, obtain it
unmodified from the authoritative source, verify provenance and that it
actually renders, and fall back to an approved text wordmark when no
official asset exists. Never redraw, trace, or approximate a logo.

<Goal>

Get the *real* mark, or knowingly fall back. Two failure modes to avoid:
shipping a hand-drawn approximation of a trademark (legally and visually
wrong), and burning an hour on a vendor that simply does not publish one.
Decide which case you're in early, then verify what you got.

</Goal>

<Scope>
<UseWhen>

- Any deliverable that shows third-party company/product logos.
- "Get me the X logo", tool comparison rows, sponsor walls, icon strips.

</UseWhen>
<DoNotUseWhen>

- The user's OWN brand assets (ask them for the file).
- Generic iconography (arrows, UI glyphs) — that's an icon search.

</DoNotUseWhen>
</Scope>

<Steps>

1. **Try the aggregators first.** They are faster than vendor pages and
   already normalized: `svgl` → `simple-icons` → GitHub org avatar →
   favicon. In a HyperFrames project this is one call:
   `resolve --type logo` (see the `media-use` skill). Only escalate to
   step 2 when the aggregators miss, the mark looks stale, or the task
   explicitly demands the vendor's own authoritative file.
2. **Find the vendor's brand page.** Conventional paths:
   `/brand`, `/brand-guidelines`, `/legal/brand-guidelines`, `/press`,
   `/newsroom`, `/media-kit`. Read it for BOTH the download link and the
   usage terms — you need both in the report.
3. **Determine if a vector mark is actually distributed.** A brand page
   existing does NOT mean an SVG exists. Check what the download really
   contains before claiming success. Common dead ends: partnership
   templates (`.psb`/`.ai` only), PNG-only kits, or a login-gated portal
   (SAML) behind a public-looking "full guidelines" link.
4. **Download unmodified.** If plain `curl` 403s, see
   `references/fetching-gated-brand-pages.md` — most vendor CDNs sit
   behind bot protection and need a real browser.
5. **Verify** per <Verification> below.
6. **Read the terms and record them.** Nominative use ("only to refer to
   us") is typically fine; note whether modification is forbidden, whether
   permission is revocable, and any "not more prominent than your own
   mark" clause. Put this in the report — the requester may be shipping
   commercially.
7. **No official mark? Apply the spec's fallback policy explicitly.** The
   released spec says whether to fall back to a plain text wordmark badge (set
   in the deliverable's own typography) or stop and ask; absent a policy, that is
   a spec gap. Say so in the report and name the reason. Do NOT substitute a
   third-party redraw or an AI-generated lookalike.

</Steps>

<Verification>

Three independent checks — a downloaded file is a claim, not evidence:

1. **Parses.** `xmllint --noout *.svg`. Catches truncated downloads and
   HTML error pages saved with a `.svg` name.
2. **Provenance.** `cmp` each extracted file against the original inside
   the vendor archive — proves you shipped their bytes, not an edit.
   Record the archive's `sha256` and that `unzip -t` is clean.
3. **Renders non-blank.** Rasterize and count ink pixels. A structurally
   valid SVG can still be visually empty (bad viewBox, white-on-white,
   zero-size paths). Use `scripts/verify-svg-renders.mjs` — it preserves
   aspect ratio and counts pixels differing from a mid-grey backdrop, so
   both white-ink and black-ink marks register.

Also confirm: correct variant for the background (light-ink vs dark-ink),
`viewBox` present, and glyph-only vs lockup matches what the layout wants.

</Verification>

<Pitfalls>

- **Never redraw, trace, or "recreate" a logo** — not by hand, not with an
  image model. If there's no official file, use the text fallback.
- Assuming a brand page implies a downloadable SVG. Open the archive and
  list it before reporting success.
- Treating file byte-size or PNG length as a render check — it is not.
  A wide mark squashed into a square box also produces false failures;
  preserve aspect ratio. (Both bit this skill's author.)
- Grabbing the light/dark variant that matches your editor rather than the
  destination background.
- Shipping the lockup (glyph + wordmark) where the layout wants the
  glyph-only logomark — they have different aspect ratios.
- Modifying the mark (recolor, crop, round corners) when the terms say
  "exactly as provided, without alteration".
- Reporting only the file and not the source URL + terms. The requester
  needs provenance to defend the usage.
- Forgetting the brand color. It's often only discoverable as the `fill`
  in the vendor's own dark-variant SVG.

</Pitfalls>

<Reference>

- `references/fetching-gated-brand-pages.md` — getting past Cloudflare/bot
  protection on vendor CDNs with headless Chrome.
- `references/vendor-findings.md` — per-vendor results already established
  (which vendors publish SVGs, exact URLs, terms). Check here first; add
  a row whenever you investigate a new vendor.
- `scripts/verify-svg-renders.mjs` — the ink-pixel render check.

</Reference>
