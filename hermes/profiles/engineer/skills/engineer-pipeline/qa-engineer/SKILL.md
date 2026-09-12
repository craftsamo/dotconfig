---
name: qa-engineer
description: "QA engineering: judge implementation and UI evidence."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: engineer-pipeline
    tags: [qa, engineering]
---

<ReadBeforeWork>

Re-evaluate the entry when the request, mode or scope changes, including within a turn.
Load the root with skill_view(name="engineer-pipeline") only if its full body
is not already present in the current context; reuse full-body instructions
only while present in the current context, not a past load or summary. This
entry is the mode procedure itself, not a second common mode index. Canonical
root fallback when skill_view returns unchanged without its earlier body is
`${HERMES_SKILL_DIR}/../SKILL.md`; recover this entry's own
body and its references from `${HERMES_SKILL_DIR}` via read_file and
next_offset. Stop the affected action when a required body is unavailable;
never take an alternate path or an artificial range to dodge this check.

Before the first wrapper call, or whenever transport context is lost, load
skill_view(name="engineer-pipeline", file_path="references/opencode.md") if
its full body is not already present, with fallback
`${HERMES_SKILL_DIR}/../references/opencode.md`; no generic per-mode common
transport copy. Reading the root or transport file is not implementation
approval. A cross-mode link requires loading that mode's owning entry and the
root before applying its details -- only the locally relevant details apply here.

</ReadBeforeWork>

# Quality assurance

Judge actual results against Client intent and the approved scope. A process
exit or OpenCode's completion sentence is not acceptance. Read the report,
current worktree/commit and evidence; repeat checks selectively, not every test
unconditionally. Read [OpenCode](../references/opencode.md) for inspection-call semantics.
Web changes use [visual QA](references/web-ui.md); user-flow evaluation additionally uses
[persona QA](references/ux-persona.md) when relevant. Findings-only assessment can enter here
without creating a fix or a PR.

1. Scope: inspect the actual diff and pre-existing changes. No stray files,
   unrelated edits, unapproved dependencies, protected text changes or scope creep.
2. Tests: read relevant tests and actual outcomes, not just a suite total. Check
   that assertions express the requirement and were not weakened to match a bug.
   For sensitive changes request an independent OpenCode review/debug run with
   the requirement and current diff, not the implementation conversation's claims.
3. Runtime: exercise the important behavior safely. CLI/API checks use real entry
   points against permitted test inputs. UI checks use Engineer's browser with
   explicit URL, worktree/build identity, target viewports and screenshot evidence.
   Test data/actions are scoped; browser/terminal availability is not permission
   for production writes, payments or personal-account access.
4. Intent evidence: bug fixes replay the original symptom; performance compares
   the same measured workload; refactors preserve behavior; migrations reconcile
   data and test recovery; dependency updates resolve the relevant version/advisory.
   Missing facilities or credentials leave named checks unverified, never passed.
5. Verdict: accept locally, request specific corrections through
   [Build](../build-engineer/SKILL.md), or return a material scope decision to the Client.
   Recheck affected evidence after corrections; no autonomous new feature work.
6. Delivery: verify the actual PR base/head, intended commits, scope, description,
   CI state and any Issue references after OpenCode creates it. Do not require an
   Issue when none was requested, or close a multi-PR Issue prematurely. Required
   unresolved checks prevent unqualified completion. Report pending CI distinctly.

An image-creator/video-creator/audio-creator hands leaf's option-backed
reference change uses [Hands references](references/hands-references.md) for its actual
checks.

Issue updates are writes, not QA observations: route them through Build with the
explicit issue_approval. Never mutate Git/Issues/boards during read-only inspection.
No merge, deploy or default-branch push follows acceptance automatically.

Report requested/completed work, PR URL or explicit exception, actual checks and
outcomes, screenshot/finding pointers, unmet/unverified criteria and remaining
risks. Keep raw logs, account identifiers and private paths out of public PRs.
Client acceptance is separate from Engineer's technical verdict.
