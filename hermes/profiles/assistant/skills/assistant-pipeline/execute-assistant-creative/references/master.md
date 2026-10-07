# Commission — video-creator: master

Read [commissioning](../SKILL.md) first.

## Leaves

| Deliverable | Leaf | Notes |
| --- | --- | --- |
| one finished master from already-approved parts: silent segments joined in order (cut or dissolve), a finished WAV or audio-creator Mix bundle laid under them, optional captions burned in plus an SRT | `create-master` | free, <=180 seconds, always kind="work"; no proposal round, decides nothing creative; size/fps/length mismatches return as edit-clip or audio-creator dependency requests, never trimmed, padded or stretched; captions come from the Mix bundle or a supplied SRT |

## Choosing and filling

`create-master` is the served route for joining finished parts: join
already-approved silent video segments in order (cut or dissolve), lay a
finished soundtrack under them (a WAV or an audio-creator Mix bundle), and
optionally burn captions in with an SRT sidecar. Typical uses: a silent MV
visual master plus its separately produced music, several generated clips or
promotion cuts joined into one film, a narrated piece whose Mix already
carries captions.

It decides nothing creative. Settle up front: the parts and their order,
cut or dissolve (and its length), which soundtrack, whether captions are
drawn in or only attached, and the caption position. Every part must
already be approved; this leaf never trims, reframes, retimes or recolours
one. Plan the dependencies as their own units: a segment of another size
or frame rate goes through [edit-clip](clip.md) first; a soundtrack that
does not last the joined picture (a dissolve shortens it at every join)
goes back to audio-creator ([mix](mix.md) or music edit)
first; caption text comes from the Mix bundle or a supplied SRT, never
written here.

Not this leaf: overlays, logos or graphics on footage, keeping each
segment's own sound, audio mixing or ducking (create-mix), authored motion
([promotion](promotion.md)) or a piece that needs new footage. Those stay
with their own served leaf; where none fits, that scope is not served:
`no skill fits`.

## Transport

| Leaf | Transport |
| --- | --- |
| video-creator's `create-master` | `specialist_call(target="video-creator", message=<the text>, kind="work")` even though free; joins and caption renders can outlast one reply |

## Round-trip and approvals

Send the finished parts by their durable paths: `segments` in play order,
`audio` (a WAV) or `mix_bundle` (the audio-creator bundle directory),
optional `captions`. There is no proposal round: the build runs on the
filled form, and a missing decision comes back as a question. A size, frame
rate or length mismatch comes back as a dependency request; release that
edit-clip or audio-creator unit, then resend the form with the new files.
Never ask VideoCreator to trim, pad or stretch a part to make it fit.
A revision is a new build from the original parts into a new directory.
