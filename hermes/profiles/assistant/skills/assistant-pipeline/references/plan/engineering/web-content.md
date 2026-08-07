# Web content — plan recipe (LP / site / blog / portfolio)

Content-led web frontends: pages whose value is copy, imagery, and
identity — no domain database, no login. One archetype, several
shapes; the shape decides the decomposition, everything else is
shared. The code is the easy part — copy and visuals decide whether
the pages work, so they are planned as explicit stages, never left
for the engineer to improvise. Stateful needs (auth, user data, own
APIs) reclassify the work to `webapp.md`.

## Brief — fix before the session

- **Purpose & audience** — what the pages must accomplish, for whom,
  seen where; the conversion or visitor journey that defines success.
- **Shape** — LP / multi-page site / blog / portfolio (table below).
  Multi-page with an unknown sitemap → deriving the page inventory
  IS the first unit, never skipped.
- **Content sources** — who writes copy (writer stage, user-provided,
  reuse); imagery per section (creator + its Budget); posts/works
  data for blog/portfolio shapes.
- **Brand & style** — logo, palette, tone; reference sites.
- **Cross-cutting needs** — SEO/OGP metadata, analytics, contact
  form, multilingual — each named explicitly or explicitly out.
- **Deploy target & domain** — implied by the frontend starter
  derivative when new; custom domain yes/no.
- **Done criteria** — live URL + rendered screenshots at the target
  viewports.

## Cross-capability stages

Copy → writer, imagery → creator, each planned as its own stage with
your QA between them (composite-DAG rule, as in creative). Content
can run parallel to the scaffold unit, but the build unit that places
final copy/assets depends on both.

## Shapes — decomposition defaults

| Shape | Default units | Decomposition shape |
| --- | --- | --- |
| LP / campaign page | Waves | 2–4 strictly linear: scaffold → build against final copy/assets → responsive & polish → deploy. One page, one message, one CTA. |
| Multi-page site | Waves; purposes when it spans sessions | IA first (sitemap, navigation, shared layout/design tokens), then page groups on that layout — independent once the layout lands — cross-cutting concerns as named units, deploy last. |
| Blog | site shape + | the content model & publishing pipeline (markdown/CMS decision, listing/detail/feed) is its own early unit, before page production; seed posts are writer stages, not engineering units. |
| Portfolio | site shape + | the works inventory (data + assets pipeline) is its own early unit; per-work pages are generated from it, never hand-built one-offs. |

A new product noun lands here as a new row only if it keeps this
archetype's starter family, verification, and unit defaults — else it
fails the index's new-leaf test and earns its own leaf.

## Expected decomposition — inspection standard

- The shape matches the table: LP small and strictly linear; sites
  put IA/layout before any page group; blog/portfolio carry their
  data/pipeline unit early.
- Cross-cutting concerns appear as their own units, not footnotes.
- Red flags: an IA/sitemap unit for a one-page LP; one giant "build
  all pages" unit; page units before a layout unit; CMS or backend
  units the Brief never asked for; "design exploration" inside the
  engineer's units (that is creator work).

## Defaults

- New repo: the frontend-platform derivative of the local starter
  family (discovered per `bootstrap.md`) — bootstrap first.
- Authority `A1`; `A2` when the user wants a PR flow (page groups
  map naturally to PR-per-unit).
- Verification: rendered screenshots (mobile + desktop) per page or
  page group and the live URL — code-only inspection is never done
  (QA file); metadata spot-check when SEO/OGP is in scope.
