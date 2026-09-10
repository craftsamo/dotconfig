# Reference document

Use the actual names, types, units, allowed values, defaults and version scope
from supplied specifications. Decide the lookup key (command, configuration
key, API operation or term) from how readers will search the material.

Keep comparable entries structurally consistent. A table is useful when its
columns have the same meaning across rows; use explanatory prose for cases
that would otherwise hide conditions in a misleading cell. Record required
versus optional values explicitly when established by the specification.

Do not fabricate a default or example value to fill a blank cell. Unknown,
not applicable and explicitly empty are different states. Preserve spelling
and case of identifiers, and qualify differences between versions.

## Make entries answer lookup questions

Start an entry with the exact lookup key, then explain what it controls or
returns. Keep parameter semantics beside allowed inputs and return semantics
beside the corresponding output. Use tables for genuinely comparable fields;
conditional behavior may need prose. This is lookup guidance, not a required
table schema for every term or API.

Distinguish omitted input, explicitly empty input, unknown behavior,
not-applicable fields and a specified default. An omitted key may trigger a
default; an empty string need not do so. "Unknown" describes the available
knowledge, not an accepted API value. Pair each example with the supplied
schema and version so neither a return field nor an input convention is
silently borrowed from a different operation.

## Worked example and retain condition

Fictional teaching material: the supplied v2 schema defines optional `cursor`
as a nonempty string; omission starts at the first page. The response has
`items` (an array) and `next_cursor` (string or null); null means no next page.

An entry can say: "`cursor`: omit for the first page; an empty string is
invalid. `next_cursor`: pass the returned string as `cursor` to request the
next page; null means pagination is finished."
The schema example `{"items": [], "next_cursor": null}` illustrates an empty
final page, not an unknown result or an instruction to pass null as input.
The explanation connects input and return roles without inventing defaults.

Retain repeated field labels across operations because they aid lookup.
If the schema gives no default, record "not specified" rather than `0`;
use "not applicable" only where the field genuinely has no role.

QA: for the supplied entries, check example keys, types and return meaning
against their schema; absent implementation evidence does not block wording.

QA: readers can find entries, units and qualifications are unambiguous,
and repeated fields retain consistent meaning. Do not vary terminology or
entry structure merely to make the writing appear less repetitive.

Source: lookup/table distinction adapted from [natural-japanese v1.5.0 guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/doctypes/guide.md).
Value-state semantics and the fictional schema example are local applications, not upstream quotations.
