# Creator broker shape

How Creator's Plan / Build / QA references mirror the hands, and Assistant Client guides. Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Broker shape

The migration has distinct ownership shapes, not one universal skill tree:

- **Producers** (Creator's hands and Writer today) expose one concrete operation
  and subject per `<verb>/<subject>/SKILL.md`, with the form, Procedure, QA and
  Report owned there. Other profiles adopt that pattern only as their own
  operation/output contracts are settled; Creator's verbs and media budgets
  are not imposed on writing, engineering, research or marketing.
- **Creator's broker** (pipeline v9) keeps `creator-pipeline` as its invariant
  kernel and adds three independently discoverable children outside
  `references/`: `plan-creator`, `build-creator` and `qa-creator`. Each entry's
  `SKILL.md` is its phase procedure and owns the corresponding
  `references/<hands>/<subject>.md` details. The parent keeps invariant
  contracts, `references/capabilities.md` (served families first, then the
  legacy technic table) and `references/legacy/` (technic-era routes for
  families not yet on a hands); it is a required dependency, not the sole
  discovery route. No phase-index alias, generated menu or extra common-mode
  wrapper exists.
- **Assistant's Client entries** use 19 independent child
  skills with domain details in each child's `references/` and shared mode-common
  procedures at the parent. They express what Assistant owns, not a mirror of
  every producer form.
- **Engineer's mode entries** use four independent child skills, one per actual
  mode, each owning its procedure and detail references. They depend on the
  invariant root and shared OpenCode transport, not a duplicated mode-common
  wrapper. They do not copy Assistant's six-domain matrix or change the coding,
  approval and evaluation responsibilities.

Creator's phases are `plan`, `build`, `quality-assurance`. Each phase owns one
flat `<hands>/<subject>.md` for every subject actually served by the three
hands; verb differences stay inside that file, and unavailable verb/subject
pairs are not new capabilities. Subject references are plain references, not
independent skills; hands discovery, forms and names stay unchanged. Every
inbound turn/completion and each mode/subject/scope-changing action selects an
entry, requires the full kernel — recovered through canonical `read_file`, or
the action stops when it is absent — and then reads only the selected subject
references. New subject references land together with their hands family,
never as placeholder stubs.

Each subject reference has one job per phase: Plan interprets the client's
request into the existing form and settles the applicable grants; Build relays
that form and approvals in the correct conversation and delivers directly;
explicitly requested QA reads the returned evidence against the client's intent.
Never transplant the hands' measurement commands into Creator's QA: QA never
reruns the producer's measurements, turns a sampled check into continuous-motion
proof, or claims to have heard audio. Failure and unknown flags survive every
handoff. Forms, style resources, engine implementation and measurement scripts
remain with their producers.

`validate_creator_references` collects subjects from the actual hands leaves,
deduplicates verbs, and requires exact per-hands coverage in all three phases.
It rejects missing/orphan references, unsupported nesting, unlinked subjects,
broken or escaping local links, missing kernel/recovery dependencies, and stale
`references/<phase>/` directories; a v9 root requires all three entries, while
shipped v7/v8 candidates keep their earlier checks. Once an entry tree is present
it must be complete; do not commit a partially populated tree or keep the old
indexes as aliases. Rollback restores the root, entries/references and matching
caller tests together from the preceding version; it never rewrites job
outputs, proposal hashes or approvals. Retire an actual legacy capability family
by family, only after caller coverage and a both-client soak — never merely
because a leaf exists.

### Assistant Client guides and retirement gates

For migrated creative work, the Creator-first handoff is the model: Assistant
owns the user's goal, context, constraints, durable location, grants,
cross-domain coordination and GitHub bookkeeping. Creator owns media leaf
selection, form interpretation, creative proposals and production sequencing.
Assistant's direct delivery uses the producer's returned status and evidence;
it does not add an aesthetic gate, repeat implementation QA or maintain another
catalog of sizes, providers, forms and approval hashes.

Assistant reads deliverable-first Client guides under
`plan-assistant-creative/references/<deliverable>.md`, with optional bounded
`reference-research.md`, common Execute dialogue/direct delivery and explicit-only
QA inspection. Each guide owns the outcome's Client questions and acceptance
criteria, not producer fields, providers, limits or recipes. Guide names can
match hands subjects without a parity contract: a new hands subject does not
oblige a new guide, and an absent guide never establishes an unavailable
capability. Operations and modifiers do not multiply guide files. No generated
catalog, per-deliverable Skill or per-deliverable copies of Execute and QA.

References distinguish observed evidence, suggested direction, user decisions
and open questions. Research material is inspiration only, not an authorized
production input. Creator's common Plan requires an explicit relay of
asset-and-operation upload consent; Assistant origin, a brief shape, a local
path, a public URL or "use this" alone is not consent. Budget, exact proposal
approval, rights, upload, remote analysis and Publish grants remain distinct.
Creator coordinates its production dependencies; Assistant does not duplicate
those Writer or hands requests.

Retained methods are physically isolated under `references/legacy/` within
`plan-assistant-creative`, `execute-assistant-creative` and `qa-assistant-creative`.
Only the legacy Plan leaves and QA Covers mapping retain 1:1 alignment with
Creator's technics; the legacy directories are explicitly routed from their
owning SKILL bodies. The two existing creative card definitions stay in
`execute-assistant-creative/SKILL.md` frontmatter. Relocation is not capability
retirement and does not authorize a fallback from failed or unsupported hands
work.

Assistant's fixed house formats, past-work device catalog and blanket
audiovisual recipes are retired in both paths and are not transplanted into
Creator; the underlying legacy production methods remain. Real technical
constraints stay with the current producer contract, not a second global
Assistant rulebook. In particular: generated video no longer forces brand work
to image-to-video, camera OR subject motion, muted web audio, no text or locked
faces; hands-served icons/speech are not legacy batches; HTML motion and
composites accept separately approved finished music; the external HyperFrames
core rules and CLI renderer own seek-safe timeline capture (not a hand-built
per-frame CDP recipe), with `creator-html-motion` checking job isolation and
rendered font, outline, orientation and numeric layout without hardcoding a
font or CSS treatment; audio mastering follows the current audio producer's
contract. No external skill is edited or copied into this repository. Existing
completed/frozen artifacts and approvals stay unchanged; a new look is
researched or proposed for the current purpose.

Retire an actual legacy capability, technic and QA mapping only after its
replacement covers old caller scenarios, handoffs and approvals have been
exercised, and both human and Assistant clients have soaked. A shared QA
contract stays until its last consumer moves. Merely adding a Client guide
or relocating a reference satisfies none of those retirement gates.

The rebuild is a paired public-validator/private-pipeline change. Candidate
checks resolve the candidate creative roots at call time and validate
structure without invoking live Git-boundary checks on a temporary copy.
Cutover needs approval; check real ownership and a fresh session separately.
Rollback restores the paired task-owned references and validator, never job
outputs, proposal hashes, active grants or unrelated changes.

Writer's form-based leaves do not by themselves transfer editorial authority;
its released-unit ownership is unchanged. Its current clients still release
decided outline/piece/whole-job units, and Writer returns unresolved
deliverable-defining choices. A future Writer-first contraction must first map
that ownership and caller coverage explicitly, then update the Assistant and
Writer contracts together. No Writer-first runtime instruction, private-overlay
edit, or automatic retirement of Assistant's writing leaves is part of this
change. Apply the same ownership-first gate to later profile migrations; a
shared directory shape is not permission to change who plans, approves,
publishes or verifies a result.
