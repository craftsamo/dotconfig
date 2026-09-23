# Writer

Writer families, craft and editorial QA, resource cleanup and v8 routing. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Writer post family

Post text is a Writer artifact, not a Marketer-side paraphrase of a brief.
Writer's three post leaves live under `writer-pipeline/<verb>/post/` with
category `writing`. Each has its own form, platform references, Procedure,
QA and Report. Source text and style examples are distinct from claim
evidence. X Articles are not posts; Instagram captions are not image text.
Metadata and unresolved insertion markers never enter published bodies.

The requester accepts the actual draft; Marketer then checks platform fit,
claims and legal conditions and requires exact remote-save consent. Text
defects go back to Writer. A changed draft needs new approval. Service-draft
support is verified separately; the user publishes. Analyze returns a report and never
publishes or silently rewrites its target. Humanizer is explicit-only for
these leaves; the legacy Japanese inspection path is not run in addition.
All six writing families now use their own leaves; the shared Japanese skill
contains language knowledge only.

## Writer article family

Article leaves live under `writer-pipeline/<write|edit|analyze>/article/`.
Each owns its form, selected destination references, Procedure, QA and Report.
Zenn's Markdown source is distinguished from note/X Article rich-text editor
features and unspecified blog engines. Documented support is not a live
preview test; no universal platform cap or HTML-comment hiding is assumed.

`[[image:id]]`, `[[embed:id]]` and `[[table:id]]` are internal insertion
requirements, with stable IDs and same-stem `.production.md` notes. They are
not publishable markup, media-generation authority or evidence that assets
exist. Missing sources and editor operations remain needs-assets/needs-editor;
text acceptance does not certify assembly or publication. Editing preserves
protected claims and marker bindings; analysis evaluates a report without
rewriting the article. The requester's independent QA uses the served leaf
contract, not legacy lint or the four-pass receipt. Humanizer is explicit-only.

Article is the first Writer Client-guide pilot: Assistant's existing
`plan/writing/article.md` holds outcome questions, optional reference comparison
and acceptance, not a second form catalog. Editorial decisions remain with the
requester; Writer still interprets its form and owns craft. The other five
families retain their current contracts.

`edit-article` distinguishes `proofread` (minimal correction) from `wording`
(polishing), `structure` and `rewrite`. Proofreading requests select `proofread`;
the ordinary edit default remains `wording`. Findings-only proofreading uses
`analyze-article`, never a fourth verb. Preserve protected text and intentional
variation; uncertain names/numbers are findings, not inferred replacements.
No qualifying errors is a valid unchanged result. Bounded article correction
and analysis do not reopen new-writing outline/tone decisions or automatically
commission external fact-checking. Assistant checks actual scope and preserved
text, not an extra shared proofreading pipeline; publication and unresolved
asset/editor work retain their separate gates.
Structure/rewrite units retain source trace and their applicable full gate;
explicitly requested factual checks are never waived by proofreading scope.

## Writer document family

Document leaves live under `writer-pipeline/<write|edit|analyze>/document/`.
Their format options are readme, guide, reference, report, minutes, proposal,
slides, release-notes and issue, with custom formats accepted as described
constraints. Each operation has its own form, local format guidance, Procedure,
QA and Report. Existing documentation/business-document briefs route here.
Factual release notes are documents; promotional announcements remain copy.

The leaves preserve facts, recorded decisions, identifiers, conditions and
uncertainty. A missing owner or deadline is not a new decision. Editing checks
the original and named scope; analysis checks its report against the target
rather than requiring a new document's template. No source-only result claims
executed commands, reproduced research, rendered slides or repository changes.
The requester accepts actual evidence under the document gate; the engineer
still owns repository integration. Humanizer is explicit-only and the legacy
four-pass/lint route is not added.

The business-format guidance re-expresses relevant ideas from the existing
coji/natural-japanese v1.3.0 (`b54954f`, MIT) adaptations documented in
`agents/README.md`. It does not copy the old constitution or its fixed-count
rules; historical resource and script attribution remains in Git history.
The current craft expansion uses v1.5.0; see "Writer craft and independent
editorial QA" below for the new baseline and role split.

## Writer message family

Message leaves live under `writer-pipeline/<write|edit|analyze>/message/`.
Each owns a form, local channel references, Procedure, QA and Report. Email,
chat, notification, UI and error are channel options; a custom channel follows
its supplied constraints rather than being coerced into a listed format.
Social posts and promotional mail retain their separate subjects.

The requester supplies relevant recipient/context and the intended stance.
Writer does not resolve contacts, decide relationships or look up private
records. Warming a message cannot create an apology, agreement or commitment;
editing preserves protected fields and placeholders. Unknown send/transaction
results remain unknown, and a retry button is not evidence of safe repetition.
Analysis reports quote only necessary text and distinguish possible readings
from actual recipient reactions. They do not draft an unsolicited reply.

The requester independently checks the draft/report under the message gate.
User-facing fields are separate from role labels and review notes. Text QA
does not prove actual delivery, interface fit or implemented behavior; sending
and integration require their own authorized owner. Humanizer is explicit-only,
and no additional inspection workflow runs after the message leaf's checks.

## Writer copy family

Copy lives under `writer-pipeline/<write|edit|analyze>/copy/`, with a complete
form, local destination references, Procedure, QA and Report in each leaf.
Landing page, email and announcement are open destination choices; existing
marketing-copy briefs select these leaves. Ordinary correspondence, X/Instagram
posts and factual release notes retain their own families.

The requester fixes the message, audience, offer and evidence. Writer expresses
them without new positioning, scarcity, testimonials or unqualified guarantees.
Price, eligibility, dates and disclosures stay associated with the claims they
limit. A CTA is required only when the released purpose calls for action.
Edits compare the full revision with protected and untouched fields; analysis
quotes observations without producing replacement copy or claiming conversion
performance/legal clearance. Humanizer is explicit-only; legacy inspection is
not added to served copy work.

The requester independently accepts the actual draft/report. Marketer consumes
accepted copy fields unchanged, performs its existing inspection and requires
exact-candidate remote-save consent. A direct Writer peer response is not
independently accepted merely because it includes self-review. Text defects go
back to Writer, not through local shortening or a humanizer rewrite. This layer
adds no page rendering, email delivery, channel integration, tool or profile.
Production scripts use the separate Script family described below.

## Writer script family

Script leaves live at `writer-pipeline/<write|edit|analyze>/script/`. Each has
its own form, local format references, Procedure, QA and Report. Formats are
narration, comic, storyboard, screenplay and slide-script, with custom contracts
accepted as supplied. An outline remains an outline; plain narration has no
forced scene table. Written slide structure alone remains a Document job.

Separate exact spoken/displayed text from instructions. A whole-file speech
consumer receives a words-only input, not the structural master or accompanying
`.production.md`. If raw unit exports are required, map them to units/speakers
and check their agreement with the master. Edits preserve existing IDs and
untouched fields, record retired units without speaking their markers, and
require explicit requester/consumer agreement for re-identification.

Counts cite an actual method; intended timing does not prove playback, acting,
pronunciation, synchronization or rendered lettering. Existing media/timing
evidence may be invalid after text changes. The requester checks actual script
evidence and renewed approval before releasing production; consumers do not
rewrite approved words. Analysis is judged as a report, not required to provide
new dialogue, unit fields or raw speech files. Humanizer is explicit-only and
no legacy inspection is added. This layer does not add tools, produce media,
or promise that an arbitrary video backend accepts a storyboard.

## Writer craft and independent editorial QA

All 91 existing leaf references across Article, Document, Message, Copy, Script
and Post carry conditional craft guidance, locally authored examples and retain
conditions. The three operations remain distinct: write constructs a usable
artifact, edit changes only the authorized scope, and analyze supports findings
without replacing its target. Forms, discovery and the shared `japanese-writing`
language core are unchanged. `natural-japanese` v1.5.0 (`21e6326`, MIT) is the
current reference baseline; source links and local adaptations are explicit,
with provenance in `agents/README.md`. No adopted rule mandates a genre template,
personal anecdote, fixed sentence count or universal conclusion-first structure.

The requester's shared Writing QA independently scores the actual released unit
on purpose, structure/usability, reasoning/evidence, information economy,
expression fit and fidelity/voice, using observable 0-4 anchors. Each applicable
axis must reach 3 and mandatory evidence must be checked; no average offsets
a failure. Unverified evidence has no numeric score, and exclusions need a scope
reason. No-op edits and accurate findings-only reports can pass. The numbers
are editorial judgments, not naturalness/authorship measurements; Writer does
not self-score, and its checked / unmet / unverified report stays unchanged.

The QA contract owns the pre-acceptance ceiling of two corrective returns per
released unit, with earlier escalation for missing material or changed scope.
Execute communicates that budget and relays quote-anchored defects. Each round
reads the latest artifact and affected exports; old scores cannot approve changed
text. After acceptance, a new consumer defect suspends acceptance and returns
to the same Writer under an explicit corrective release. User, production and
Publish approvals remain separate. Review cases outside runtime discovery cover
these boundaries; neither static tests nor isolated model trials establish
live-session reliability or statistical score calibration.

The canonical requester contract is public at
`profiles/writer/skills/writer-pipeline/references/acceptance/{index,prose,script}.md`.
Assistant's private QA files are thin adapters, and Marketer reads the same source
through Writer's configured external skill root. No private task records moved.
In the Writer v8 candidate, all 19 Writer non-kernel names stay disabled on both
callers (18 production leaves plus `consult-writer`); the root remains readable.
Consultation stays delegated to Writer. Reading a form or acceptance contract as
a Client does not execute Writer's procedure.
An unavailable contract blocks acceptance; Writer never uses it for self-approval.

## Writer resource cleanup

The old Writer routing/review cluster and shared Japanese catalogs, Python
inspection tools and detector fixtures are retired; at that point the
language package held only `SKILL.md`. A separate, later, bounded read-only
inspector (`references/inspection.md`, `scripts/inspect_text.py`) was added
after this cleanup — see "Writer craft and independent editorial QA" below
and `agents/README.md` for what it is and is not. Source attribution for the
retired stack is recorded in `agents/README.md` and the pre-cleanup Git
history. Do not place an archive back under a discovered skill root or
restore a generic review fallback for an unsupported request.

Pre-draft advice uses `writer-pipeline/consult-writer/SKILL.md`. It preserves
structure/tone/sizing advice without producing or approving a draft. An explicit
outline release still uses a write leaf; evaluating/editing a target selects its
own operation. Caller QA uses the actual artifact and criterion evidence, not
the removed inspection commands or pass counts. Restore matched producer/caller
contracts together if rolling back; no runtime switch is implied by this cleanup.

### Writer v8 candidate routing

The user-approved migration is implemented only in the isolated candidate,
pending explicit cutover. No Writer deployment, restart or real-model validation
is claimed; the earlier Assistant deployment status remains unchanged.
The root name `writer-pipeline` and all 18 production leaf names, paths and forms
remain unchanged across write/edit/analyze and the six subjects. One independent
non-production direct child, `consult-writer/SKILL.md`, holds the old advice body.
It adds no fourth production verb or form. Shared `references/acceptance/`
remains canonical and unchanged.

Each Writer execution entry, including consultation, checks the full kernel,
selected entry body and current required detail references on every inbound turn,
completion notification and before a midturn operation/subject/scope change.
Only full bodies present in current context are reusable; prior loads, summaries
and root preload are insufficient. Missing bodies require canonical `read_file`
recovery, following `next_offset` through truncation, or stopping the affected
action. No aliases or dedup evasion through alternate paths or artificial ranges.
Client form/acceptance reads are inspection, not local Writer execution.
