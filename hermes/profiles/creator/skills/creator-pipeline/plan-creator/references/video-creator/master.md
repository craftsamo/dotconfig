# Plan — video-creator: master

Read [common plan](../../SKILL.md) first.

`create-master` is the served route for joining finished parts: join
already-approved silent video segments in order (cut or dissolve), lay a
finished soundtrack under them (a WAV or an audio-creator Mix bundle), and
optionally burn captions in with an SRT sidecar. It is checked before the
legacy `creator-media-assembly` row. Typical uses: a silent MV visual
master plus its separately produced music, several generated clips or
promotion cuts joined into one film, a narrated piece whose Mix already
carries captions.

It decides nothing creative. Settle up front: the parts and their order,
cut or dissolve (and its length), which soundtrack, whether captions are
drawn in or only attached, and the caption position. Every part must
already be approved; this leaf never trims, reframes, retimes or recolours
one. Plan the dependencies as their own units: a segment of another size
or frame rate goes through [edit-clip](clip.md) first; a soundtrack that
does not last the joined picture (a dissolve shortens it at every join)
goes back to audio-creator ([mix](../audio-creator/mix.md) or music edit)
first; caption text comes from the Mix bundle or a supplied SRT, never
written here.

Not this leaf: overlays, logos or graphics on footage, keeping each
segment's own sound, audio mixing or ducking (create-mix), authored motion
([promotion](promotion.md)) or a piece that needs new footage. Those stay
with their own served leaf or the legacy family that covers them.
