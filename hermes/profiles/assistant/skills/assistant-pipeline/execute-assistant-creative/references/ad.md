# Commission — video-creator: ad

Read [commissioning](../SKILL.md) first.

## Leaves

| Deliverable | Leaf | Notes |
| --- | --- | --- |
| timestamped advertising reference breakdown or ad review: copy, persuasion, visual construction and CTA | `analyze-ad` | <=60 seconds, kind="work"; overview, bounded dense windows and native copy evidence; optional retained report; not factual/provenance/performance verification |
| exact-copy advertisement from approved product/logo/media assets | `create-ad` | 6..30 seconds, 24/25/30/50/60fps (default 30); aspect 9:16 (default), 16:9, 1:1 or 4:5; native canvas per plan, no automatic crop/scale; kind="work", content-plan then preview approval; no generation/TTS/capture |

Ad means a specific audience, promise and intended action. PV primarily
introduces qualities/experience/world: neither duration nor a CTA alone decides.
A PV authored from supplied material is create-promotion. A generated ad is
not a leaf of its own: its picture is text-free generate-clip shots, and
create-ad then composes them as supplied muted footage with the exact copy,
claims, product/logo rasters, CTA and audio. A model-generated PV is not
implemented. Never silently route a requested generated ad or PV to MV.
Technical-only checks stay analyze-clip even for its what_for: ad option.

create-tour, create-ad and HyperFrames create-explainer-video
support opt-in graphics: three-webgl2 through their local Three graphics
contract, not a separate subject. you select it for actual depth or GLSL
surface requirements and verifies provisioning; no silent flat substitute.
It uses one procedural WebGL2 layer with pinned local Three/CLI/browser and
GSAP time. Addons, async asset loading, WebGPU and Motion Canvas combinations
remain outside that scope. Existing exact proposals and previews still apply.

## Choosing and filling

Advertising references and authored ads use analyze-ad and create-ad respectively.
Ad is a specific audience/promise/action; PV introduces qualities or a world.
Do not route by duration, presence of a CTA, or the word "promo" alone. Ask
about the main outcome only when it changes the route. A PV authored from
supplied material is [create-promotion](promotion.md); a model-generated PV is
not served; do not quietly replace it with MV or clip production.

A generated ad (its picture drawn by a video model) is a chain of existing
units, not one leaf. First settle the ad itself with the user: audience,
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
review criteria, not for the user to write a shot list. Retain the report at
deliver when it feeds later production, otherwise scratch evidence suffices.
Its claims are observations of the reference, not the user's usable facts.

For final create-ad settle product/audience/message/cta, approved assets, supported
claims and finished audio if needed; defaults are 15 seconds, aspect 9:16,
office/bold-graphic/claim-led. Aspect selects 9:16 (1080x1920), 16:9
(1920x1080), 1:1 (1080x1080) or 4:5 (1080x1350), at `fps` 24/25/30/50/60
(default 30; settle it only when the user cares). Author for
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
only a proposal. The hands author the exact copy ledger and plan; you show it
to the user for approval. Then the same work conversation authors a source/preview;
only approval of that preview releases final rendering. Changed inputs return
to content approval. Analysis is optional reference work, not a mandatory
preflight/QA subagent for every ad, and it never supplies approval itself.

create-ad's optional Audio Mix path (`audio_workflow: mix`) is handled in
"Round-trip and approvals" below.

## Transport

| Leaf | Transport |
| --- | --- |
| video-creator's `create-ad` / `analyze-ad` | `specialist_call(target="video-creator", message=<the text>, kind="work")`; approval turns or bounded multi-pass evidence extraction, not an inquiry |

## Round-trip and approvals

For explicit create-ad studies, relay the actual study plan and preview approvals
in the same work conversation. The hands use freeze-study/render-study; a final
render is not released. Preserve the existing allowance and require a fresh final
proposal/preview before any final ad. Never append dummy CTA copy to a study.

For analyze-ad relay the evidence-backed report, not a request for an output
movie. Optional deliver retains report/evidence for the next work unit. Do not
promote source-ad claims into approved claims of the user or re-upload/re-analyze
the same file yourself. Missing listening/continuous-motion evidence stays
unverified. A reference analysis is not authorization to produce a new ad.

For a generated ad, release each generate-clip shot as its own metered
unit first and accept or reject it against the shot list (text-free, the
product not altered) before create-ad's proposal; the proposal binds the
accepted clip files by hash, so a regenerated shot means a new proposal.

For create-ad, keep all three turns in one specialist work conversation:
proposal-only (no approval fields), approved_plan + approval_sha256 for source
authoring/preview, then preview + preview_sha256 for final render. Preserve
the full form and target/conversation_id. Relay the exact hashes only AFTER
the user's approval; never recompute a hash to approve changed bytes. Review exact
copy, claim qualifications, asset usage and action before content approval;
review the frozen preview before rendering. A hash is integrity, not caller
authentication. Changed copy/assets/direction require a new plan and preview.
Changing aspect also requires re-layout, a new plan/source/preview and both
approvals; never apply an old portrait preview to a landscape/square output.
Do not inject aspect into an existing approval-bound portrait plan that lacks it.
No media generation, TTS, capture or arbitrary API call is hidden in create-ad.
Do not require a separate analyze-ad call for its self-QA; use it when the
user asks for deeper advertising review or a reference breakdown.

For `audio_workflow: mix`, request preliminary timing from VideoCreator, relay
it to AudioCreator, then return the verified Mix bundle before formal video
approval — see [commissioning](../SKILL.md) and, for the optional
Mix leaf itself, [mix](mix.md).
