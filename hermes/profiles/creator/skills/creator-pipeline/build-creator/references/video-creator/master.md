# Build — video-creator: master

Read [common build](../../SKILL.md) first.

## Transport

| Leaf | Transport |
| --- | --- |
| video-creator's `create-master` | `specialist_call(target="video-creator", message=<the text>, kind="work")` even though free; joins and caption renders can outlast one reply |

## Supervising

Send the finished parts by their durable paths: `segments` in play order,
`audio` (a WAV) or `mix_bundle` (the audio-creator bundle directory),
optional `captions`. There is no proposal round: the build runs on the
filled form, and a missing decision comes back as `Q<n>:`. A size, frame
rate or length mismatch comes back as a dependency request; release that
edit-clip or audio-creator unit, then resend the form with the new files.
Never ask VideoCreator to trim, pad or stretch a part to make it fit.
A revision is a new build from the original parts into a new directory.
