# Editing a reference

Preserve lookup keys, types, units, allowed values, defaults and version
qualifiers. Keep repeated entry structures when they support comparison;
synonym variety must not rename one concept or make different concepts equal.

For an authorized table change, check that every cell still belongs to its
original row/column meaning. Empty, unknown and not applicable are different;
do not fill a cell with an inferred default. Code identifiers are not prose.

## Correct semantics without changing the interface

Use the lookup key to locate the authorized entry. Correct its wording beside
the parameter or return field it describes; keep examples paired with the
same supplied schema and version. A table reorganization needs structure
scope and must preserve row identity. These are lookup guides, not an excuse
to normalize every entry or paraphrase code identifiers.

Keep omitted, explicitly empty, unknown, not applicable and specified default
distinct. An empty string is an input value, not shorthand for omission.
Leave untouched sections and protected content unchanged; a conflict with a
protected example is reported rather than silently fixed. A no-op is legitimate
when the entry already matches the supplied contract.

## Worked example and retain condition

Fictional teaching material: the supplied v2 schema allows `cursor` to be
omitted for the first page but forbids an empty string. `next_cursor: null`
means no next page. Only the `cursor` description is released for correction;
the return-field definition and other rows are protected.

Before: "`cursor`: leave empty for the first page."
After: "`cursor`: omit for the first page; an empty string is invalid."
This resolves an actual mismatch with the schema without changing the API.
The `next_cursor` definition stays unchanged; its null return is not imported
as a permitted input. Do not fabricate a request/response example to fill space.

Retain "Default not specified" when the schema is silent. Replacing it with
"not applicable" would assert something different; replacing it with `0`
would invent a default. Repeated accurate parameter labels need no variation.

QA: compare the changed entry and its paired example with the supplied schema;
report out-of-scope contradictions without expanding the correction.

QA: entry identity and cross-references survive, comparable fields remain
comparable, and corrections trace to a supplied specification. Editing a
parameter description does not verify the implementation accepts that value.

Source: reference-table guidance adapted from [natural-japanese v1.5.0 guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/doctypes/guide.md).
Value-state distinctions and the fictional edit are local applications, not upstream quotations.
