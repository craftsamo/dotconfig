# Editing UI text

Keep field IDs, variables, placeholders and action semantics stable. A wording
edit cannot change save to submit or make an irreversible deletion appear
reversible. Preserve known cost and consequence disclosures in visible text.

Respect supplied interface terminology and edit only the released fields.
Do not change surrounding controls, source code or translation-file structure.
If an apparent inconsistency requires knowing actual behavior, request that
evidence rather than selecting the friendlier description.

QA: compare field-by-field with the original and known screen context. User-facing
values remain separate from role labels and notes. No implementation, working
interaction, rendered fit or accessibility verification follows from text alone.
