# Editing UI text

Keep field IDs, variables, placeholders and action semantics stable. A wording
edit cannot change save to submit or make an irreversible deletion appear
reversible. Preserve known cost and consequence disclosures in visible text.

Respect supplied interface terminology and edit only the released fields.
Do not change surrounding controls, source code or translation-file structure.
If an apparent inconsistency requires knowing actual behavior, request that
evidence rather than selecting the friendlier description.

## Craft decisions

Limit authorized changes to the named values. A label should name the actual
action/object when context is unclear; nearby helper text supplies only known
consequences. If destructive warnings belong before the action, preserve that
specified relationship rather than shortening away the cost of the decision.
Protect intent and action semantics; no-op labels are valid when already clear.
If the required helper or placement is absent, report the dependency, not an
implemented control. A shorter string does not establish rendered fit.

## Worked example

Fictional material: an existing button deletes the selected draft irreversibly.
Its label 「処理する」 alone is editable. The protected helper, specified before
the button, is 「削除した下書きは元に戻せません。」 No other field is released.
Revision button: 「下書きを削除」
Why: the label names the supplied action/object instead of a generic process.
The complete revision retains the helper verbatim and does not add a confirmation
dialog, cancel button or undo control. Its actual placement remains unverified.

Retain: if the button already says 「下書きを削除」, choose a no-op; concision
does not require making it less specific. Counterexample: 「完了」 would hide
the deletion, while adding 「あとで戻せます」 would invent reversibility.

QA evidence: show the changed field and its authorized scope, compare the label
with the supplied effect, and quote the untouched warning. Separate text-order
evidence from rendered fit; do not claim to implement controls through wording.
If a warning is known to be missing but not editable, report the scope conflict.

Sources: local adaptation of [natural-japanese v1.5.0 writing constitution](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md)
and [revision guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md)
for concrete meaning and selective rewriting; [Microsoft writing style](https://learn.microsoft.com/en-us/windows/apps/design/style/writing-style)
for actual action wording. No upstream Writer UI manual or implementation
behavior is imported; examples and warning-preservation decisions are local.

QA: compare field-by-field with the original and known screen context. User-facing
values remain separate from role labels and notes. No implementation, working
interaction, rendered fit or accessibility verification follows from text alone.
