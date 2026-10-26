# Analyzing UI text

Inspect known field roles, wording, action distinctions, conditions and variable
handling. A supplied screen/context can support an ambiguity finding; an unseen
screen cannot establish where text renders or how a control actually behaves.

Separate visible-text concerns from interaction, accessibility and layout
questions that need additional evidence. Do not penalize an appropriately short
label for lacking a paragraph, or assume every control needs an explicit object.

## Craft decisions

Compare the label's action/object with the supplied effect, and nearby helper
text with only known consequences. If destructive warnings are required before
the action, inspect the supplied text order without pretending it is rendered.
For a review, connect quote, evidence, mismatch and possible consequence. If the
object is already obvious, a short label can be sufficient; avoid padding advice.
Separate a content dependency from implementation: do not implement controls or
claim rendered fit. Return observations without replacement labels or helper text.

## Worked example

Fictional material: a text specification places helper 「あとで元に戻せます。」
before a button labeled 「完了」. The supplied behavior permanently deletes the
selected draft and offers no undo. The requester asks whether these words fit.
Finding: quote both fields against the documented irreversible deletion.
Mismatch: 「完了」 does not name deletion, and the helper asserts reversibility
contrary to the supplied effect. Its position before the action does not cure this.
Consequence: the words could lead a reader to choose deletion expecting recovery.
Why: the analysis grounds the concern in a known effect, not an assumed screen;
actual placement and rendered fit remain unverified, and no replacement is supplied.

Retain: a short 「保存」 label can be clear when its object is supplied nearby
and the action only saves. Counterexample: requiring an object in every label
or declaring a button too narrow from text alone invents a defect or measurement.

QA evidence: pair the quoted values with the action/effect specification; identify
whether warning order is documented or observed. Bound the consequence as a
possible reading, not proof of a click, actual harm or implemented accessibility.

Sources: local adaptation of [natural-japanese v1.5.0 writing constitution](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md)
and [revision guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md)
for concrete evidence and selective criticism; [Microsoft writing style](https://learn.microsoft.com/en-us/windows/apps/design/style/writing-style)
for actual actions. No upstream Writer UI manual is implied; warning analysis
and examples are local adaptations, not component implementation instructions.

QA: quote the field/value under discussion and keep observations distinct from
proposed improvements. The report need not supply new button labels, perform
clicks, alter code or translation files, or claim visual testing occurred.
