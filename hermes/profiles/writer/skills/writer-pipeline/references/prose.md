# Prose deliverables — copy, article, documentation

Reader-facing text where the words you write ARE the shipped artifact.
Loaded from the kernel's Procedure when the TypeTable routes the
deliverable here. The kernel owns brief parsing, tone calibration, the
review gate, and delivery; this file owns how each prose type is built.

## Structure by type

### Marketing copy (LP, 告知, release note, X post text)

- Skeleton: hook → value → proof → CTA. Every sentence earns the next.
- Medium conventions when the brief is silent:
  - X post/thread: the first line must survive alone in a timeline; one
    idea per post; hard length limits are part of the contract, count
    characters.
  - Release note: what changed → why the reader cares → how to adopt.
    Facts from the brief only — never embellish scope.
  - LP / 告知: one reader, one promise, one CTA; proof (numbers, quotes)
    only from supplied sources.
- Long-form argumentative copy also gets the `japanese-tech-prose`
  argumentation discipline (per the kernel TypeTable).

### Tech article / blog / tutorial

- Skeleton: claim → argument paragraphs (one topic each, explicit
  connectives) → close that lands the claim. The title promises the
  payoff; the opening paragraph commits to it.
- Tutorials: steps in execution order; each step states its observable
  result so the reader can self-verify.
- All three Japanese layers apply — this is the only prose type where
  `japanese-prose-rhythm` is loaded (readers go start-to-finish).

### Documentation (README, manual, reference)

- Task-ordered sections the reader can scan; every heading answers "can
  I skip this?". Flat is correct — NEVER load the rhythm layer.
- Explanatory sections (design rationale, background) get the
  `japanese-tech-prose` argumentation rules; reference tables and
  procedures do not.
- README openers: what this is + who it serves within the first screen,
  judged in ~30 seconds by a stranger.

### Business document (議事録, 調査レポート, 社内ガイド, メモ・企画書, スライド構成)

- Owned end-to-end by the `japanese-business-docs` norms layer: follow
  its Workflow (reader/purpose → one-sentence main message →
  conclusion-bearing heading skeleton → density contrast → evidence),
  draft under its 12-article constitution, and load the matching
  doctype file from its `references/doctypes/`.
- Minutes from a transcript are a restructuring job, not a polishing
  job: decisions / action items (owner + due date) / carried-over
  topics get pulled out of the discussion flow per the minutes doctype.
- Flat is correct — never load `japanese-prose-rhythm`; scannability
  beats narrative pull in every business doctype.
- At review time run the `japanese-inspection` lint with
  `--genre business` (kernel review gate, `references/review.md`).

## Length

Brief gives a range → hit it. Brief is silent → infer from the medium
(X post: platform limit; README intro: one screen; blog article:
1,500-3,000 chars unless the outline demands more) and label the choice
as an assumption in the final-message footer.

## Non-Japanese deliverables

Skip the notation layer; keep the `japanese-tech-prose` argumentation
discipline (one topic per paragraph, no unsupported assertions, no hollow
phrases) as the structural guide.

## Drafting rules

- Outline before prose; get the structure pass (see
  `references/review.md`) right at outline time — restructuring a full
  draft costs a whole rewrite. On long-form work the outline is its own
  **released unit** (kernel <UnitDiscipline>): deliver structure + 2-3
  opening samples, wait for the gate, then draft the piece units it
  fixed.
- Read every supplied source before the outline, not during the draft;
  heavy retrieval follows the kernel's source-retrieval guidance.
- Write the full text in one register; tone drift mid-document is a
  norms-pass failure.
- Write the complete final prose to the durable path named by the brief. The
  assistant's own quality-assurance pass inspects that completed file; in the
  reply, name the file and summarize its structure rather than pasting the
  whole draft.

## Pitfalls

- Copy that argues instead of hooks — copy persuades by momentum,
  articles persuade by argument; don't swap their skeletons.
- Docs written to be read instead of scanned (walls of narrative in a
  README).
- Inventing product facts to fill a proof slot — the integrity pass will
  strike them; leave the slot out and note the gap instead.
