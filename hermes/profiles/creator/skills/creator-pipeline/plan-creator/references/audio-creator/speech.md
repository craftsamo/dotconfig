# Plan — audio-creator: speech

Read [common plan](../../SKILL.md) first.

## Budget

The grant is 1 take + 1 corrective per script even though the leaf costs no
provider fee — free is not unlimited, and every synthesis call counts,
successful or failed.

## An approved script, not a draft

`generate-speech` takes an approved script file, not text to compose:
never rewrite, translate or extend what the client wrote, and keep each
section to 600 characters or less — a longer script is a Plan finding
(split it into sections), never one paid-by-time take stretched to fit.
For Writer-produced scripts, the requester first accepts the exact text from
`write-script` or `edit-script`; an `analyze-script` report is not a speech part.
Pass the approved raw spoken-text file, not a structured master, speaker labels
or `.production.md` instructions. Missing raw input or required word/section
changes return to the requester for Writer, not local rewriting. Changing the
words requires renewed acceptance/approval; the old take's timing is not proof
for the revision. A request for sectioning is not an automatic take grant.

`voice:` is filled from a name the client actually gave (`house`, or the
exact `<engine>:<voice>` id); do not guess an id from a description. A
qualified voice's optional `style` or `seed` may only be offered from
what that engine's catalogue advertises — look it up first with a
no-synthesis `character_voices` A2A query to audio-creator, never invent
a control the client did not ask about.

`house` may reach the online Edge engine as its fallback for an
unsupported or English-dominant script; for a private or explicitly
local-only brief, ask in the SAME clarify round whether the client wants
a qualified local voice instead of the house default, rather than
defaulting to a fallback that leaves the machine. House and a qualified
voice never cross-fall-back into each other. The hands' readback is ASR
text-match evidence, not a listening certification: never tell the
client the line was heard, and never ask for another take merely because
the transcript came back with an alternate spelling or homophone of a
correctly spoken word.

Instrumental music now routes to `create-music`/`generate-music` in
[music](music.md). Vocal-song generation and standalone audio
visualization remain withdrawn without a hands replacement — a request
for either is `no skill fits` to the client, noted for the maintainer;
never picked up through a technic, core route, or external skill as a
stand-in.
