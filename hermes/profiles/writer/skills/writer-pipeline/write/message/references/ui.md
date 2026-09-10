# UI text

Use the supplied screen/state, control purpose, affected object and actual
effect. Keep save, submit, purchase and delete distinct; a shorter label must
not disguise a consequential action. Add cost or irreversible effects only
when known, but do not hide known consequences to make a control inviting.

For multiple fields, label their roles (heading, explanation, confirm button,
cancel button) outside the user-facing values. Preserve supplied variable
names and placeholders. An empty state is not automatically an error, and a
successful state cannot be inferred without evidence.

Prefer wording that identifies the action/result when context alone would be
ambiguous. Do not force an object into every small label when already obvious.
Use the interface's supplied terminology rather than a generic glossary.

## Craft decisions

Make the label name the actual action and, when needed, its object. Put only
known consequences in nearby helper text; do not compress them into vague verbs.
If an action is destructive, place its known warning before the action in the
text specification, not in an after-action reassurance. Do not invent undo.
If context makes the object obvious, keep the label short. If a helper field
is unavailable, report that dependency instead of adding a control or claiming
the warning is visible. Text order does not prove rendered fit or placement.

## Worked example

Fictional material: the supplied screen specification has helper text before
an existing button that deletes the selected draft; deletion cannot be undone.
Only the helper and button wording are requested. No other control is supplied.
Draft helper: 「削除した下書きは元に戻せません。」
Draft button: 「下書きを削除」
Why: the helper discloses the known irreversible consequence before the named
action. The button says what is deleted instead of concealing it as completion.
No cancel button, confirmation step or recovery feature has been invented.

Retain: 「保存」 can remain when its object is obvious and it truly only saves.
Counterexample: 「完了」 with 「あとで戻せます」 would obscure deletion and falsely
promise reversibility in this example, even if it sounded more welcoming.

QA evidence: compare each field's value with the supplied action/effect and
quote the warning's specified position. Mark actual placement and rendered fit
unverified without rendering evidence; a text draft does not implement controls.

Sources: local adaptation of [natural-japanese v1.5.0 writing constitution](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md)
and [revision guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md)
for concrete meaning and selective wording; [Microsoft writing style](https://learn.microsoft.com/en-us/windows/apps/design/style/writing-style)
for core facts and actual actions. These are not upstream UI manuals for Writer;
examples and consequence-placement decisions are local, not implementation rules.

QA: each field names its intended state/action, variables remain exact, and
instructions are separate from visible text. Wording does not implement the
interaction or prove layout, accessibility, truncation or actual screen fit.
