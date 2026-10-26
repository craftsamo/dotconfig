# Analyzing a reference

Examine lookup identity, entry consistency, units and qualifiers relevant to
the question. Repeated entry formats can be useful; do not flag repetition
or technical vocabulary alone as poor writing.

Point to the row/key when identifying an inconsistency. Distinguish empty,
unknown and not applicable. A claim that the reference is wrong about runtime
behavior needs supplied implementation evidence, not an assumption.

## Test the meaning of the entry, not the API

Identify the lookup key and version before comparing definitions. Examine
parameter and return semantics together with their paired examples in the
supplied schema. Distinguish omitted input, explicitly empty input, unknown
behavior, not-applicable fields and a specified default. A blank cell cannot
establish which state applies. These guides do not mandate tables for prose terms.

Build a finding from quote to source/evidence, mismatch and consequence for
the reader's lookup task. Classify an actual defect separately from missing
evidence and optional preference for different formatting. Request the needed
definition or identify a correction direction; do not produce a replacement
draft, invent the correct value or test the implementation.

## Worked example and retain condition

Fictional teaching material: a v2 entry says "Pass `next_cursor` as `cursor`,
including null." The supplied schema permits only nonempty input strings;
omission starts pagination and a null `next_cursor` ends it.

Quote: "including null."
Source: the supplied v2 schema distinguishes the input string from a nullable
return value and defines null as the end of pagination.
Mismatch: the example carries a return-only state into an invalid input.
Consequence: readers could construct a request outside the documented schema.
Recommend correcting the example's input/return relationship, not replacing
the reference table or claiming that an actual request failed.

Retain repeated lookup labels when their meaning is consistent; variety is
optional preference. If the schema is unavailable, flag an unverified input
definition rather than declare null invalid. "Default unknown" and "not
applicable" are not interchangeable descriptions of missing documentation.

QA: cite the exact entry/example and matching schema version within scope;
textual consistency alone does not validate parameter or return behavior.

QA: the report can identify incomplete definitions or ambiguous comparisons
without inventing the correct default/value. The analysis is not itself a
new reference table and does not test an API or configuration parser.

Source: lookup/table distinction adapted from [natural-japanese v1.5.0 guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/doctypes/guide.md).
Semantic checks and the fictional example are local applications, not upstream quotations.
