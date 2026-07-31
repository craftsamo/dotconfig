# Vendor findings — established results

Check here BEFORE investigating a vendor. Add a row whenever you research a
new one. Re-verify if a row is more than ~6 months old; brand programs change.

| Vendor | Official SVG? | Source | Verified |
| --- | --- | --- | --- |
| xAI / Grok | **Yes** | `https://data.x.ai/logos/SpaceXAI_Grok_Assets.zip` | 2026-07 |
| OpenAI / Codex | **No** | — (see below) | 2026-07 |

---

## xAI / Grok — official SVGs available

- Brand page: `https://x.ai/legal/brand-guidelines` (dated 2025-02-14)
- Asset zip: `https://data.x.ai/logos/SpaceXAI_Grok_Assets.zip`
  - 351,396 bytes, 33 files (SVG + PNG)
  - `sha256 db9129acd4efc4c2202d25afe31b70281a79f8507f75520ab5e6b3356895a7e9`
- Requires headless Chrome (Cloudflare 403s curl) — see
  `references/fetching-gated-brand-pages.md`.

Key files in the archive:

| File | viewBox | Notes |
| --- | --- | --- |
| `Grok_Logomark_Light.svg` | `0 0 1024 1024` | glyph-only, `fill="white"` — best default |
| `Grok_Logomark_Dark.svg` | `0 0 1024 1024` | glyph-only, `fill="#0A0A0A"` |
| `Grok_Wordmark_Light.svg` | `0 0 1024 400` | "Grok" as outlined paths |
| `Grok_Full_Logomark_Light.svg` | `0 0 1024 400` | glyph + wordmark lockup |
| `spacexai - symbol - white - transparent.svg` | `0 0 834 318` | SpaceXAI corporate symbol |

Also contains Dark variants of each and PNG equivalents.

**Brand color: `#0A0A0A`** — the only hex published, discoverable as the
`fill` in the Dark-variant SVGs. The guidelines state no palette.

**Terms:** permissive for nominative identification. "Use our Marks only to
accurately refer to us or our services." Logos must be used **exactly as
provided, without any alteration or adjustment**. No endorsement implication;
no adjacent elements that create a new mark. Note: xAI is a separate company
from X (formerly Twitter).

---

## OpenAI / Codex — no public SVG

Established by exhausting every public route:

- Brand page `https://openai.com/brand/` has exactly one download:
  `https://cdn.openai.com/brand/OpenAI-Partnership-Templates-2025.zip`
  (451,647 bytes) → contains **only two `.psb` Photoshop files**
  (`Brand Partnerships_Template_Horizontal.psb` 1500x409,
  `..._Vertical.psb` 1500x1344). **No vector logo.**
- The page's "full design guidelines" link goes to `http://brand.openai.com/`,
  which is **SAML-login-gated** (redirects to `/auth/`, `/api/auth/saml/`).
- `github.com/openai/codex` — full recursive tree of `main` via the GitHub API
  contains **zero `.svg` files**; no logo/brand/mark assets anywhere.

**Brand color:** not published. Hex values live behind the gated portal.
Public marks render pure black / pure white only.

**Terms:** restrictive. Non-exclusive, non-transferrable, revocable at any
time. "Use the logo only when it directly relates to OpenAI services."
"Do not feature our Marks more prominently than your own company's name or
marks." No modification, no merchandise, no incorporation into your own
branding. Model names are not permitted in app/product/company names.
Logo use beyond the enumerated cases requires written permission from
`partnercomms@openai.com`; legal via `legal@openai.com`.

**=> Use the text wordmark badge fallback.** Nominative textual reference is
tolerated; the logo itself is simply not offered as a public download.
