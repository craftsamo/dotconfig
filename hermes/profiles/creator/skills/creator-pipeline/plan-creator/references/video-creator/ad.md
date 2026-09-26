# Plan — video-creator: ad

Read [common plan](../../SKILL.md) first.

Advertising references and authored ads use analyze-ad and create-ad respectively.
Ad is a specific audience/promise/action; PV introduces qualities or a world.
Do not route by duration, presence of a CTA, or the word "promo" alone. Clarify
the main outcome only when it changes the route. A PV authored from supplied
material is [create-promotion](promotion.md); a model-generated PV is not
served; do not quietly replace it with MV or clip production.

A generated ad (its picture drawn by a video model) is a chain of existing
units, not one leaf. First settle the ad itself with the client: audience,
message, CTA, claims, duration and aspect, as for any create-ad. Then plan
the shot list: each generated shot is one [generate-clip](clip.md) form
(1..15 s, silent, text-free: no lettering, logo or UI) with its own budget,
upload and analysis consents, in the ad's aspect. Generated shots carry the
setting, mood, people and action; they never stand in for the real product.
The product and logo appear from their supplied rasters in create-ad, or a
shot animates the approved product image as its `source` with upload
consent, and a shot that alters the product's shape, colour or label is
rejected, not shipped. When the approved shots exist, create-ad receives
them in `assets` as muted MP4s, each placed with explicit timing, and binds
them in its content plan like any supplied asset. Exact copy, claims and
CTA are only ever create-ad's typeset text.

For analyze-ad pass the local source path, purpose reference/review, any known
brief/focus and remote_analysis. A readable MP4 needs local frame extraction,
not an attachment request. Use kind="work". A supplied reference authorizes
reading, not cloud video upload; no remote approval means remote_analysis: no.
Image vision still uses the existing profile policy. Ask only for missing
review criteria, not for the client to write a shot list. Retain the report at
deliver when it feeds later production, otherwise scratch evidence suffices.
Its claims are observations of the reference, not the client's usable facts.

For final create-ad settle product/audience/message/cta, approved assets, supported
claims and finished audio if needed; defaults are 15 seconds, aspect 9:16,
office/bold-graphic/claim-led. Aspect selects 9:16 (1080x1920), 16:9
(1920x1080), 1:1 (1080x1080) or 4:5 (1080x1350), all at 30fps. Author for
that canvas; do not resize/crop an approved layout from another ratio.
An explicitly requested diagnostic unit can instead use create-ad's
`purpose: study`, concrete `question` and 1..10s duration, omitting CTA. It is
never inferred from missing final fields. Read the leaf's study reference for
its supplied-only audio/copy boundaries and separate plan/preview approvals.
Ask the hands to run its zero-production asset preflight before presenting a
ready proposal; missing source/runtime/visual evidence remains unverified.
Each ratio is its own plan/source/preview and approval, not batch output.
Existing portrait plans without aspect keep their bytes and approvals;
never insert new defaults into a frozen plan. Theme builds the world, style presents it,
direction organizes persuasion; custom values and theme_detail override defaults.
An empty local assets directory permits a text/graphics-only ad, not permission
to invent a product image. Missing assets become a separately released upstream
job. Never invent statistics, endorsements, prices or deadlines. First release
only a proposal. The hands author the exact copy ledger and plan; you relay it
for client approval. Then the same work conversation authors a source/preview;
only approval of that preview releases final rendering. Changed inputs return
to content approval. Analysis is optional reference work, not a mandatory
preflight/QA subagent for every ad, and it never supplies approval itself.

create-ad's optional Audio Mix path (`audio_workflow: mix`) is handled in
[build](../../../build-creator/references/video-creator/ad.md).
