# Editing Zenn Source

Preserve existing fenced code, link destinations, image sources and article
metadata unless the requested change includes them. A prose edit does not
authorize changing code behavior or adding fabricated execution output.

Zenn accepts Markdown, including tables and documented extensions. Verify
any extension actually needed against the guide rather than assuming generic
HTML support. Moving a heading can invalidate internal links; check their
meaning and known anchors without claiming a rendered preview.

If the source is repository-managed, preserve its supplied frontmatter and
file conventions. If it is editor-bound, do not add an unrequested CLI layout.
Unresolved image/table/embed IDs remain production dependencies.

Documentary source (checked 2026-09-08; no preview test):
https://zenn.dev/zenn/articles/markdown-guide

## Clarify the Code's Meaning

If authorized prose edits cover an explanation with an ambiguous code
reference, name the exact expression and what it does under the supplied
technical conditions. Keep code behavior, language/version qualifiers and
claim strength unchanged. A mismatch between a claim and protected code
is a finding to resolve, not permission to repair either by inference.

Locally authored example (wording scope, supplied `len(names)` expression):
Before: "This counts them."
After: "`len(names)` counts the list entries."
Reason: if the surrounding source already establishes that `names` is a
list, the sentence gives "this" and "them" exact referents without changing
the snippet. It does not establish an executed result or improved performance.
If the source does not establish the type, flag the missing context instead
of adding "list". Do not apply this stylistic clarification in proofread scope.

Retain: valid supplied Markdown, code fences, documented callouts, tables
and technical repetition that keeps names stable. Do not normalize code,
URLs, identifiers or quotations without item-specific permission, even when
the surrounding wording changes. A no-op preserves source bytes and layout.
An expert passage need not acquire beginner definitions during polishing.

QA evidence: compare before/after prose with the exact code object and its
source explanation. Check that technical context and the code/claim relationship
survive shortening; quote conflicts separately from optional style suggestions.
Verify protected spans unchanged, and distinguish a source check from an
unperformed run or Zenn preview. Clearer prose cannot supply missing evidence.

Local adaptation of [natural-japanese v1.5.0 readability principles](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/readability-principles.md)
(referent proximity) and [revision guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md)
(selective changes); Zenn preservation rules and the example are local adaptations.
