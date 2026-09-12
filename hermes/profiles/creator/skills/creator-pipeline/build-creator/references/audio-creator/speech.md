# Build — audio-creator: speech

Read [common build](../../SKILL.md) first.

## Transport

| Leaf | Transport |
| --- | --- |
| audio-creator's synthesis/ASR-heavy leaves (`generate-speech`; an `edit-speech`/`analyze-speech` that needs fresh ASR rather than reused sidecars) | `kind="work"` as in the generic `generate` row in [common build](../../SKILL.md), even though the leaf is `cost: free` — synthesis and ASR routinely outlive the reply window. Use `kind="inquiry"` only when bounded and known to finish in one reply (reused, already-validated sidecars; no fresh ASR) |

## Supervising

For analyze-speech, `deliver` may likewise be omitted: its report is
findings only, no new audio file, and expect no files back beyond the
reply text itself. `analyze-sfx` is the same — see [sfx](sfx.md).
