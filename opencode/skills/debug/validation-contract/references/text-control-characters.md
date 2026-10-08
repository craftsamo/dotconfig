# Text Control Characters and Integrity Boundaries

Load this reference when a text validator groups intended line breaks with
unsafe controls, or when CRLF normalization is being considered.

## Decision table

| Character/class | Default decision | Allow only when |
| --- | --- | --- |
| NUL `U+0000` | Reject | Never for ordinary structured text |
| TAB `U+0009` | Reject | The schema explicitly defines tabs as content |
| LF `U+000A` | Reject by default | A specific visible-text field contracts multiline content |
| CR `U+000D` | Reject | The schema explicitly accepts CR or defines pre-hash normalization |
| Other C0 `U+0001..001F` | Reject | A specialized protocol names the character |
| DEL/C1 | Preserve existing behavior unless in scope | The requirement explicitly broadens control filtering |

Exempt the exact character, not the entire numeric range. A safe LF predicate
keeps every prior C0 rejection except `c == "\n"` on an opted-in field.

## Integrity rule

Determine where canonicalization occurs relative to approval:

1. **Hash/approve raw bytes, then parse:** never normalize accepted values after
   the hash check. Reject alternate line endings not named by the contract.
2. **Parse/canonicalize, then hash canonical bytes:** normalization may be valid,
   but its algorithm and output encoding are part of the schema.
3. **No integrity binding:** normalization is still a semantic choice; infer
   neither CRLF acceptance nor whitespace collapse from convenience.

A comparison layer that collapses whitespace does not authorize storage-layer
normalization. Two strings can compare as visually equivalent while remaining
different approved artifacts.

## Regression matrix

For each opted-in field, cover one exact multiline value and assert it survives
model validation and serialization unchanged. Parameterize invalid cases with
at least NUL, TAB, CR/CRLF, ESC, and one other C0 character. Add one non-opted
field containing LF to prove the shared default did not widen. When approval
uses hashes, assert the input digest is unchanged and changed content still
fails its equality or approval check.
