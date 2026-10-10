# Writer

Writer leaves and routing, the six families, craft and editorial QA, and the Japanese inspector. Read it before changing a Writer leaf, its QA contract or the inspector tool. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Writer leaves

Writer's production surface is 18 leaves at
`writer-pipeline/<write|edit|analyze>/<subject>/SKILL.md`, category `writing`,
across six families: post, article, document, message, copy and script. Each
leaf has a named output and owns its form, Procedure, QA and Report
(`validate_writer_leaves` checks the shape without changing Creator hands'
verbs or media cost contract). The three operations stay distinct: write
constructs a usable artifact, edit changes only the authorized scope, and
analyze supports findings without replacing its target. A request to edit or
evaluate a target selects that target's leaf. Unsupported combinations return to
the requester, never a generic fallback or restored review pipeline. Keep new families in separate layers rather than bundling them.

- A text in a named person's or character's own name takes its voice from the
  `characters` package in every family (kernel `<Voice>`): Writer reads the
  guide and medium examples itself, the requester names only the slug, and
  requester acceptance checks the text against that guide.
- Japanese text in every leaf follows the shared `japanese-writing` workflow,
  which the kernel maps onto write / edit / analyze (skill:
  [agents/README.md "Japanese writing core"](../../../agents/README.md#japanese-writing-core));
  the leaf adds its form-specific checks.
- Humanizer is explicit-request only for every leaf, and no legacy
  four-pass/lint inspection runs in addition to a leaf's checks.

Pre-draft advice uses `writer-pipeline/consult-writer/SKILL.md`, one independent
non-production direct child — not a fourth production verb or form. It produces
or approves no draft, may propose bounds but not present them as actual
producer requirements or measured evidence, and executes no writing workflow.
An explicit outline release still uses a write leaf. Every Writer execution entry, including consultation,
follows the shared [entry loading contract](../topology.md#entry-loading-contract).

## Writer post family

Post text is a Writer artifact, not a requester-side paraphrase of a brief.
The post leaves serve X/Instagram. Source text and style examples are distinct from claim evidence. X Articles are
not posts; Instagram captions are not image text. Metadata and unresolved
markers never enter published bodies.

The requester (for marketing, the Assistant) accepts the actual draft, checks
platform fit, claims and legal conditions and requires exact remote-save
consent; Marketer may review it as advice. Text defects go back to Writer. A
changed draft needs new approval. Service-draft support is verified separately;
the user publishes. Analyze never publishes or silently rewrites its target.

## Writer article family

Article leaves live under `writer-pipeline/<write|edit|analyze>/article/`, with
destination-format references that distinguish source drafts from destination
rendering (Zenn Markdown, X Article rich text, unspecified blog engines). A note
source is written in the `note` tool's Markdown dialect, which the requester
saves; Writer's `note` tool offers only the offline `check` action, on CLI and
A2A ([note-access.md](../note-access.md)). Documented platform support is not a
live preview test: do not promise X Article Markdown import, unknown HTML
support or untested embeds, and assume no universal platform cap or HTML-comment
hiding.

`[[image:id]]`, `[[embed:id]]` and `[[table:id]]` are internal insertion
requirements, bound to stable IDs and same-stem `.production.md` notes. They are
not publishable markup, media-generation authority or evidence that assets
exist. Missing sources and editor operations remain needs-assets/needs-editor;
they are never removed to manufacture a publication-ready result, and text
acceptance does not certify assembly or publication. Editing preserves protected
claims and marker bindings. The requester's independent QA uses the served leaf
contract, not legacy lint or the four-pass receipt.

Article is the Writer Client-guide pilot: Assistant's `plan/writing/article.md`
holds outcome questions, optional reference comparison and acceptance, not a
second form catalog; Writer owns craft.

`edit-article` distinguishes `proofread` (minimal correction) from `wording`
(polishing, still the default), `structure` and `rewrite`. Findings-only
proofreading uses `analyze-article` — never a fourth verb or shared proofreading
pipeline. Uncertain names/numbers are findings, not inferred replacements; no
qualifying errors is a valid unchanged result. Bounded correction and analysis
are exempt from new-writing outline/tone/research requirements, but explicitly
requested factual checks are never waived by proofreading scope.

## Writer document family

Document leaves live under `writer-pipeline/<write|edit|analyze>/document/`,
including briefs named documentation or business-document. Formats are local
form options, not new profiles. Factual release notes are documents;
promotional announcements remain copy.

The leaves preserve facts, recorded decisions, identifiers, conditions and
uncertainty. Keep absent records distinct from explicit decisions: never infer
owners, deadlines, release status or runtime success. Analysis returns a report,
not a replacement document. No source-only result claims executed commands,
reproduced research, rendered slides or repository changes. The requester
accepts actual evidence under the document gate; OpenCode (driven by the
Assistant) still owns repository integration. Business-format guidance sets no
constitution or fixed-count rules; provenance is in `agents/README.md`.

## Writer message family

Message leaves live under `writer-pipeline/<write|edit|analyze>/message/`, for
email, chat, notification, UI and error wording — not sending or system
diagnosis. A custom channel follows its supplied constraints. Social posts and
promotional mail retain their separate subjects.

Writer uses supplied recipient/context only; it looks up no contacts or
private records. Preserve the sender's intent;
warming a message cannot create an apology, agreement or commitment, and editing
preserves protected fields and placeholders. Unknown send/transaction results
remain unknown, and a retry button is not evidence of safe repetition. Analysis
distinguishes possible readings from actual recipient reactions and drafts no
unsolicited reply.

Text QA does not prove delivery, interface fit or implemented behavior;
sending and integration need their own authorized owner.

## Writer copy family

Copy lives under `writer-pipeline/<write|edit|analyze>/copy/` for landing pages,
promotional mail and announcements; existing marketing-copy briefs select these
leaves. Ordinary correspondence, X/Instagram posts and factual release notes
retain their own families.

The requester fixes the message, audience, offer and evidence. Writer expresses
them without new positioning, scarcity, testimonials or unqualified guarantees.
Approved claims, price, eligibility, dates and disclosures stay associated with
the claims they limit; evidence conflicts are never solved by inventing proof or
silently weakening a protected promise. A CTA is required only when the released
purpose calls for action. Analysis claims no conversion performance or legal
clearance.

The requester independently accepts the actual draft/report, consumes accepted
copy fields unchanged and requires exact-candidate remote-save consent; it saves
drafts only and the user publishes. Text defects go back to Writer, not through
local shortening or a humanizer rewrite.

## Writer script family

Script leaves live at `writer-pipeline/<write|edit|analyze>/script/`, covering
narration, comic, storyboard, screenplay and slide scripts; custom contracts are
accepted as supplied. The actual producer contract decides units, fields and
limits — never impose genre-wide counts or timing. An outline remains an
outline; plain narration has no forced scene table. Written slide structure
alone remains a Document job.

Separate exact spoken/displayed text from instructions. Plain spoken files
contain only the intended words — no labels, fences or notes; a whole-file speech
consumer receives that words-only input, not the structural master or
`.production.md`. Keep `.production.md` and any raw unit exports consistent with
the master. Edits preserve existing unit IDs and untouched fields, record
retired units without speaking their markers and never recycle retired IDs;
re-identification needs explicit requester/consumer agreement.

Intended timing does not prove playback, acting, pronunciation, synchronization
or rendered lettering. Changed words invalidate dependent media/timing evidence
until rechecked. The requester checks actual script evidence and renewed
approval before releasing production; consumers do not rewrite approved words.

## Writer craft and independent editorial QA

Craft baseline, sources and provenance are in `agents/README.md`. No adopted
rule mandates a genre template, personal anecdote, fixed sentence count or
universal conclusion-first structure.

The requester's shared Writing QA independently scores the actual released unit
from quoted evidence on six 0-100 axes: naturalness, density and concision,
function and navigation, logical clarity, integrity and demonstration. Purpose
and fidelity are hard gates that fail the unit regardless of scores; then every
applicable axis must reach 90 and the scored mean 92 — the mean never offsets a
failing axis. Unverified evidence has no numeric score, and n/a exclusions need
a reason. No-op edits and accurate findings-only reports can pass. Scores
describe reader cost, never authorship. Writer never accepts its own work: its
self-review (checked / unmet / unverified, plus the shared skill's six-axis
final review) never replaces the requester's score.

The QA contract owns the pre-acceptance ceiling of two corrective returns per
released unit, with earlier escalation for missing material or changed scope.
Old scores cannot approve changed text. After acceptance, a new consumer defect
suspends acceptance and returns to the same Writer under an explicit corrective
release, never a silent reset of an unresolved finding. User, production and
Publish approvals remain separate.

The canonical requester contract is public at
`profiles/writer/skills/writer-pipeline/references/acceptance/{index,prose,script}.md`
and is not copied elsewhere. Assistant's private QA files are thin adapters;
caller external skill roots must expose Writer's pipeline for name-based reads
(default's filesystem fallback: see [topology](../topology.md) "Default is the
assistant's CLI counterpart"). All 19 Writer non-kernel names stay disabled on
the Assistant (18 production leaves plus `consult-writer`) so reference access
does not import an execution menu. Reading a form or acceptance contract as a
Client does not execute Writer's procedure; an unavailable contract blocks
acceptance.

## Japanese inspector

The shared skill's read-only inspector (`scripts/inspect_text.py`; modes and
report fields in its `references/inspection.md`) is the inspection step of the
`japanese-writing` workflow. Writer reaches it only through `writing_inspect`.
Findings are candidates the leaf judges (fix, keep with a reason, or
insufficient information); the inspector never edits or decides acceptance. The
naturalness mode's mechanical score measures reader cost, never authorship, and
is evidence for a diagnosis, not a pass.

The `writing_inspect` tool (toolset `writing-inspection`) is transport, not
inspection rules; arguments and limits are in the tool schema. It is reachable
only from a Writer session: a gateway (A2A) turn must be bound to the Writer
profile; a resident CLI turn binds no session profile, so the Writer home
identifies it and any profile it inherits must be Writer's. It runs the
canonical inspector as a `subprocess` with no shell, no source writes and no
network, and rejects a report whose schema or input hashes do not match; a
trimmed report counts every removal in its truncation metadata (status
`partial`). Do not place an archive back under a discovered skill root.
Attribution and provisioning live in `agents/README.md`.
