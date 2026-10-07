# Writer

Writer leaves and v8 routing, the six families, craft and editorial QA, and the Japanese inspector. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Writer leaves

Writer's production surface is 18 leaves at
`writer-pipeline/<write|edit|analyze>/<subject>/SKILL.md`, category `writing`,
across six families: post, article, document, message, copy and script. Each
leaf has a named output and owns its form, Procedure, QA and Report; selected
reference options need local backing files and direct body links
(`validate_writer_leaves` checks this without changing Creator hands' verbs or
media cost contract). The three operations stay distinct: write constructs a
usable artifact, edit changes only the authorized scope, and analyze supports
findings without replacing its target. A request to edit or evaluate a target
selects that target's leaf. Unsupported combinations return to the requester for
clarification, never a generic fallback or restored review pipeline. A text
in a named person's or character's own name takes its voice from the
`characters` package in every family (kernel `<Voice>`): Writer reads the guide
and medium examples itself, the requester names only the slug, and requester
acceptance checks the text against that guide. Keep new
families in separate layers rather than bundling them. Japanese text in every
leaf follows the shared `japanese-writing` workflow, which the kernel maps onto
write / edit / analyze (skill:
[agents/README.md "Japanese writing core"](../../../agents/README.md#japanese-writing-core));
the leaf adds its form-specific checks.
Humanizer is explicit-request only for every leaf, and no legacy
four-pass/lint inspection runs in addition to a leaf's checks.

Pre-draft advice uses `writer-pipeline/consult-writer/SKILL.md`, one independent
non-production direct child — not a fourth production verb or form. It preserves
structure/tone/sizing advice without producing or approving a draft, and may
propose bounds but cannot present them as actual producer requirements or
measured evidence, nor execute a writing workflow. An explicit outline release
still uses a write leaf.

Every Writer execution entry, including consultation, follows the shared
[entry loading contract](../topology.md#entry-loading-contract): full kernel,
selected entry body and current required detail references on each inbound turn,
completion notification and before a midturn operation/subject/scope change.
Status (v8): deployed in the live checkout and exercised with real models
through Assistant resident `work` calls from both CLI and Telegram. The
root name `writer-pipeline`, all 18 production leaf names, paths and forms, and
the canonical shared `references/acceptance/` stay unchanged; `consult-writer`
is the one new entry. Rollback restores matched producer/caller contracts
together (see [topology](../topology.md) "Candidate rollout and cutover").

## Writer post family

Post text is a Writer artifact, not a requester-side paraphrase of a brief.
The post leaves (`write-post`, `edit-post`, `analyze-post`) serve X/Instagram,
each with its own platform references. Source text and style examples are
distinct from claim evidence. X Articles are not posts; Instagram captions are
not image text. Metadata and unresolved insertion markers never enter published
bodies.

The requester (for marketing, the Assistant) accepts the actual draft, checks
platform fit, claims and legal conditions and requires exact remote-save
consent; Marketer may review it as advice. Text
defects go back to Writer. A changed draft needs new approval. Service-draft
support is verified separately; the user publishes. Analyze returns a report and
never publishes or silently rewrites its target.

## Writer article family

Article leaves live under `writer-pipeline/<write|edit|analyze>/article/`, with
destination-format references. They distinguish source drafts from destination
rendering: Zenn's Markdown source is distinguished from X Article rich-text
editor features and unspecified blog engines. A note source is written in the
`note` tool's Markdown dialect, which the requester saves; Writer's `note` tool
offers only the offline `check` action, on CLI and A2A
([note-access.md](../note-access.md)). Platform capability notes stay local to
each leaf. Documented support is not a live preview test; do not promise X
Article Markdown import, unknown HTML support or untested embeds, and assume no
universal platform cap or HTML-comment hiding.

`[[image:id]]`, `[[embed:id]]` and `[[table:id]]` are internal insertion
requirements, bound to stable IDs and same-stem `.production.md` notes. They are
not publishable markup, media-generation authority or evidence that assets
exist. Missing sources and editor operations remain needs-assets/needs-editor;
they are never removed to manufacture a publication-ready result, and text
acceptance does not certify assembly or publication. Editing preserves protected
claims and marker bindings; analysis evaluates a report without rewriting the
article. The requester's independent QA uses the served leaf contract, not
legacy lint or the four-pass receipt.

Article is the Writer Client-guide pilot: Assistant's existing
`plan/writing/article.md` holds outcome questions, optional reference comparison
and acceptance, not a second form catalog. Editorial decisions remain with the
requester; Writer still interprets its form and owns craft. The pilot migrates
no other family and retires no writing QA.

`edit-article` distinguishes `proofread` (minimal correction) from `wording`
(polishing, still the default), `structure` and `rewrite`. Proofreading requests
select `proofread`; findings-only proofreading uses `analyze-article` — never a
fourth verb or shared proofreading pipeline. Preserve protected text and
intentional variation; uncertain names/numbers are findings, not inferred
replacements. No qualifying errors is a valid unchanged result. Assistant's
article guide and acceptance branches exempt bounded correction and analysis
from new-writing outline/tone/research requirements and do not automatically
commission external fact-checking; Assistant checks actual scope and preserved
text. Structure/rewrite units retain source trace and their applicable full gate;
explicitly requested factual checks are never waived by proofreading scope.
Publication and unresolved asset/editor work retain their separate gates.

## Writer document family

Document leaves live under `writer-pipeline/<write|edit|analyze>/document/`,
including legacy briefs named documentation/business-document. Formats are local
form options, not new profiles: readme, guide, reference, report, minutes,
proposal, slides, release-notes and issue, with custom formats accepted as
described constraints. Factual release notes are documents; promotional
announcements remain copy.

The leaves preserve facts, recorded decisions, identifiers, conditions and
uncertainty. Keep absent records distinct from explicit decisions: never infer
owners, deadlines, release status or runtime success. Editing checks the
original and named scope; analysis returns a report, not a replacement document
or a new document's template. No source-only result claims executed commands,
reproduced research, rendered slides or repository changes. The requester
accepts actual evidence under the document gate; the engineer still owns
repository integration. Business-format guidance re-expresses ideas from the
earlier natural-japanese adaptation without its constitution or fixed-count
rules; provenance is in `agents/README.md`.

## Writer message family

Message leaves live under `writer-pipeline/<write|edit|analyze>/message/`, for
email, chat, notification, UI and error wording — not sending or system
diagnosis. A custom channel follows its supplied constraints rather than being
coerced into a listed format. Social posts and promotional mail retain their
separate subjects.

The requester supplies relevant recipient/context and the intended stance.
Writer uses supplied context only: it does not resolve contacts, decide
relationships or look up private records. Preserve the sender's intent; warming
a message cannot create an apology, agreement or commitment, and editing
preserves protected fields and placeholders. Unknown send/transaction results
remain unknown, and a retry button is not evidence of safe repetition. Analysis
reports quote only necessary text and distinguish possible readings from actual
recipient reactions; they do not draft an unsolicited reply.

The requester independently checks the draft/report under the message gate.
User-facing fields are separate from role labels and review notes. Source
assertions, actual runtime state and rendered UI fit are separate evidence
questions: text QA does not prove delivery, interface fit or implemented
behavior; sending and integration require their own authorized owner.

## Writer copy family

Copy lives under `writer-pipeline/<write|edit|analyze>/copy/` for landing pages,
promotional mail and announcements (open destination choices with
operation-specific local references); existing marketing-copy briefs select
these leaves. Ordinary correspondence, X/Instagram posts and factual release
notes retain their own families.

The requester fixes the message, audience, offer and evidence. Writer expresses
them without new positioning, scarcity, testimonials or unqualified guarantees.
Approved claims, price, eligibility, dates and disclosures stay associated with
the claims they limit; evidence conflicts are never solved by inventing proof or
silently weakening a protected promise. A CTA is required only when the released
purpose calls for action. Edits compare the full revision with protected and
untouched fields; analysis quotes observations without producing replacement
copy or claiming conversion performance/legal clearance.

The requester independently accepts the actual draft/report, consumes
accepted copy fields unchanged, performs its inspection and requires
exact-candidate remote-save consent; it saves drafts only and the user
publishes. A direct Writer peer response is not independently accepted merely
because it includes self-review. Text defects go back to Writer, not through
local shortening or a humanizer rewrite. This layer adds no page rendering,
email delivery, channel integration, tool or profile.

## Writer script family

Script leaves live at `writer-pipeline/<write|edit|analyze>/script/`, with local
narration, comic, storyboard, screenplay and slide-script references; custom
contracts are accepted as supplied. The actual producer contract decides units,
fields and limits — never impose genre-wide counts or timing. An outline remains
an outline; plain narration has no forced scene table. Written slide structure
alone remains a Document job.

Separate exact spoken/displayed text from instructions. Plain spoken files
contain only the intended words — no labels, fences or notes; a whole-file speech
consumer receives that words-only input, not the structural master or
accompanying `.production.md`. Keep `.production.md` and any required raw unit
exports consistent with the master and mapped to units/speakers. Edits preserve
existing unit IDs and untouched fields, record retired units without speaking
their markers and never recycle retired IDs; re-identification needs explicit
requester/consumer agreement.

Counts cite an actual method; intended timing does not prove playback, acting,
pronunciation, synchronization or rendered lettering. Changed words invalidate
dependent media/timing evidence until rechecked. The requester checks actual
script evidence and renewed approval before releasing production; consumers do
not rewrite approved words. Analysis is judged as a report, not a new production
input, and need not provide new dialogue, unit fields or raw speech files. This
layer adds no tools, produces no media and does not promise that an arbitrary
video backend accepts a storyboard.

## Writer craft and independent editorial QA

All existing leaf references across the six families carry conditional craft
guidance, locally authored examples grounded in their stated material, and
retain conditions, preserving operation-specific scope. `natural-japanese`
v1.5.0 is the craft reference baseline, reconstructed rather than imported;
source links, local adaptations and provenance are in `agents/README.md`. No
adopted rule mandates a genre template, personal anecdote, fixed sentence count
or universal conclusion-first structure.

The requester's shared Writing QA independently scores the actual released unit
from quoted evidence on six 0-100 axes: naturalness, density and concision,
function and navigation, logical clarity, integrity and demonstration. Purpose
and fidelity are hard gates that fail the unit regardless of scores; then every
applicable axis must reach 90 and the scored mean 92, with mandatory evidence
checked — the mean never offsets a failing axis. Unverified evidence has no
numeric score, and n/a exclusions need a reason. No-op edits and accurate
findings-only reports can pass. Scores describe reader cost, never authorship.
Writer never accepts its own work: its self-review is checked / unmet /
unverified, plus the shared skill's six-axis final review at full depth, and
neither replaces the requester's score.

The QA contract is self-contained for QA-mode loading and owns the
pre-acceptance ceiling of two corrective returns per released unit, with earlier
escalation for missing material or changed scope. Execute communicates that
budget and relays quote-anchored defects and revision rules. Each round reads
the latest artifact and affected exports; old scores cannot approve changed
text. After acceptance, a new consumer defect suspends acceptance and returns to
the same Writer under an explicit corrective release, never a silent reset of an
unresolved finding. User, production and Publish approvals remain separate.
Neither static tests nor isolated model trials establish live-session
reliability or statistical score calibration.

The canonical requester contract is public at
`profiles/writer/skills/writer-pipeline/references/acceptance/{index,prose,script}.md`
and is not copied elsewhere. Assistant's private QA files are thin adapters;
caller external skill roots must expose Writer's pipeline for name-based reads (default's filesystem fallback: see
[topology](../topology.md) "Default is the assistant's CLI counterpart"). No
private task records or purchased source text moved. All 19 Writer non-kernel
names stay disabled on the Assistant (18 production leaves plus
`consult-writer`) so reference access does not import an execution menu; the
root remains readable and consultation stays delegated to Writer. Reading a form
or acceptance contract as a Client does not execute Writer's procedure. An
unavailable contract blocks acceptance.

## Japanese inspector

The shared skill's read-only inspector (`scripts/inspect_text.py`, report
schema 2; modes and report fields in its `references/inspection.md`) is the
inspection step of the `japanese-writing` workflow. Writer reaches it only
through `writing_inspect`, as the kernel maps write / edit / analyze. Findings
are candidates the leaf judges as fix, keep with a reason or insufficient
information; the inspector never edits or decides acceptance. The naturalness
mode's mechanical score measures reader cost, never authorship, and is evidence
for a diagnosis or the requester's reading, not a pass.

The `writing_inspect` tool (toolset `writing-inspection`) is transport, not
inspection rules. It accepts `text` plus optional `modes` (`naturalness`,
`expression`, `notation`, `reading-load`, `outline`, `terms`, `structure`,
`revision`), `genre`, `experimental`, `stance` and `original`; `revision` and
`original` require each other. Default modes are all but `revision`, plus
`revision` when `original` is given. Each text is bounded to 131072 UTF-8 bytes,
with a 20-second deadline, reachable only from a Writer session. A gateway (A2A)
turn must be bound to the Writer profile; a resident CLI turn binds no session
profile, so the Writer home identifies it and any profile it inherits must be
Writer's. Without the dedicated Python from `agents/README.md` the tool returns
`unavailable`. It runs the canonical inspector as a `subprocess` with no
shell, no source writes and no network, and rejects a report whose schema or
input hashes do not match. To fit the transport budget it trims revision detail
lists first, then the longest of findings / outline / terms, counting every
removal in the report's truncation metadata (status `partial`). Ordinary host
conversation-history persistence still applies to whatever text is sent. The
old Writer routing/review cluster and its legacy catalogs, scripts and pass
receipts are retired; do not place an archive back under a discovered skill
root. Attribution and provisioning live in `agents/README.md`.
