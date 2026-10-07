# Commission — audio-creator: speech

Read [commissioning](../SKILL.md) first.

## Leaves

| Deliverable | Leaf | Notes |
| --- | --- | --- |
| a house-voice or registered-character spoken line from an approved script (up to 600 characters), as narration or a voice message | `generate-speech` | free of provider cost, NOT free of an attempt allowance: 1 take + 1 corrective per script by default, counting every synthesis call including failures; house uses the language fallback chain, a qualified `<engine>:<voice>` id never falls back |
| concatenation, boundary trim, speed, loudness normalization or format conversion of existing speech | `edit-speech` | free of generation; no resynthesis, no word changes, no voice conversion |
| findings on an existing speech file against a destination format, with optional script readback | `analyze-speech` | free; measured and readback evidence only, never a listening verdict; deliver may be omitted |

## Choosing and filling

### Budget

The grant is 1 take + 1 corrective per script even though the leaf costs no
provider fee — free is not unlimited, and every synthesis call counts,
successful or failed.

### An approved script, not a draft

`generate-speech` takes an approved script file, not text to compose:
never rewrite, translate or extend what the user wrote, and keep each
section to 600 characters or less — a longer script is a finding
(split it into sections), never one paid-by-time take stretched to fit.
For Writer-produced scripts, the user first accepts the exact text from
`write-script` or `edit-script`; an `analyze-script` report is not a speech part.
Pass the approved raw spoken-text file, not a structured master, speaker labels
or `.production.md` instructions. Missing raw input or required word/section
changes go back to Writer, not local rewriting. Changing the
words requires renewed acceptance/approval; the old take's timing is not proof
for the revision. A request for sectioning is not an automatic take grant.

`voice:` is filled from a name the user actually gave (`house`, or the
exact `<engine>:<voice>` id); do not guess an id from a description. For a
library character, `characters show <slug> voice` names its `engine:id`
pairs and whether each engine is in sync. A
qualified voice's optional `style` or `seed` may only be offered from
what that engine's catalogue advertises — look it up first with a
no-synthesis `character_voices` A2A query to audio-creator, never invent
a control the user did not ask about.

`house` may reach the online Edge engine as its fallback for an
unsupported or English-dominant script; for a private or explicitly
local-only brief, ask in the SAME question round whether the user wants
a qualified local voice instead of the house default, rather than
defaulting to a fallback that leaves the machine. House and a qualified
voice never cross-fall-back into each other. The hands' readback is ASR
text-match evidence, not a listening certification: never tell the
user the line was heard, and never ask for another take merely because
the transcript came back with an alternate spelling or homophone of a
correctly spoken word.

Instrumental music routes to `create-music`/`generate-music` in
[music](music.md). Vocal-song generation and standalone audio
visualization remain withdrawn without a hands replacement — a request
for either is `no skill fits` to the user, noted for the maintainer;
never picked up through another route or external skill as a
stand-in.

## Transport

| Leaf | Transport |
| --- | --- |
| audio-creator's synthesis/ASR-heavy leaves (`generate-speech`; an `edit-speech`/`analyze-speech` that needs fresh ASR rather than reused sidecars) | `kind="work"` as in the generic `generate` row in [commissioning](../SKILL.md), even though the leaf is `cost: free` — synthesis and ASR routinely outlive the reply window. Use `kind="inquiry"` only when bounded and known to finish in one reply (reused, already-validated sidecars; no fresh ASR) |

## Round-trip and approvals

For analyze-speech, `deliver` may likewise be omitted: its report is
findings only, no new audio file, and expect no files back beyond the
reply text itself. `analyze-sfx` is the same — see [sfx](sfx.md).
